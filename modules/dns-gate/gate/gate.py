"""PowerDNS API gate for the dns-gate module. Stdlib only.

Everyone's dnscontrol, curl and certbot hooks (students' terminals, CI jobs)
talk to this gate instead of PowerDNS: creds.json points at
http://dns-api:8081. The gate checks who is asking, swaps in PowerDNS's own
key (which only it, dns-server and the dns-ui module know), and applies the
rules below. X-API-Key carries one of three things:

  * The read key (DNS_GATE_READ_KEY, not a secret): reads only. CI's preview
    job uses it.
  * An account's own key, "<user>.<mac>", mac = base32(HMAC-SHA256(
    STUDENT_PASSWORD_SEED, "dns:<user>"))[:32] (remediation D13, FIND-11).
    The terminal writes it 0600 to ~/.config/dojo/dns-api-key and exports
    it as DNS_API_KEY. It may change names it owns: <user>.<parent> and
    below, for each parent in DNS_GATE_USER_PARENTS. In its own zone
    (<user>.dojo.test) that is anything; in a shared zone
    (DNS_GATE_SHARED_ZONES, e.g. certs.dojo.test) only a PATCH whose rrsets
    are all its own names (_acme-challenge.<user>.certs.dojo.test).
    FACILITATOR_USERNAME owns every name under each parent.
  * A Forgejo Actions ID token (remediation D6, FIND-05): an RS256 JWT
    checked against Forgejo's JWKS, with iss, aud (DNS_GATE_CI_AUDIENCE),
    exp. It may change the CI-only zones (DNS_GATE_CI_ZONES, e.g. dojo.test)
    only when repository is DNS_GATE_CI_REPO, ref is refs/heads/main and
    the event is a push: a merged change. Any other valid token reads.

Anything else (server config, TSIG keys, zones outside the lab) is refused.
"""

import base64
import hashlib
import hmac
import http.client
import http.server
import json
import os
import re
import threading
import time
import urllib.request
from urllib.parse import parse_qs, unquote, urlsplit

import events
import reset as student_reset

REPORTER = events.Reporter(os.environ.get("ACHIEVEMENTS_ADAPTER_URL", ""),
                           os.environ.get("ACHIEVEMENTS_ADAPTER_SECRET", ""))
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "8081"))
MAX_BODY = 1024 * 1024
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
ZONES_PATH = re.compile(r"^/api/v1/servers/[^/]+/zones/?$")
ZONE_PATH = re.compile(r"^/api/v1/servers/[^/]+/zones/([^/]+)(/.*)?$")
USER_NAME = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
# Hop-by-hop headers (RFC 9110 7.6.1) are not forwarded either way.
HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
              "te", "trailer", "transfer-encoding", "upgrade", "host", "content-length"}
# DER prefix of a PKCS#1 v1.5 SHA-256 DigestInfo (RFC 8017 9.2, note 1).
SHA256_DIGEST_INFO = bytes.fromhex("3031300d060960864801650304020105000420")


def zone_name(raw):
    """Zone id or name from a URL or body -> lower-case name with one trailing dot.

    PowerDNS zone ids escape odd characters as =XX (e.g. '=2E' for '.'), on top
    of the URL's own %XX escaping; undo both before comparing."""
    name = unquote(str(raw))
    name = re.sub(r"=([0-9A-Fa-f]{2})", lambda m: chr(int(m.group(1), 16)), name)
    return name.strip().rstrip(".").lower() + "."


def names(value):
    return [zone_name(z) for z in (value or "").split()]


def dns_key(seed, user):
    mac = hmac.new(seed.encode(), f"dns:{user}".encode(), hashlib.sha256).digest()
    return f"{user}.{base64.b32encode(mac).decode()[:32]}"


def _rate(env, name, default):
    try:
        return float(env.get(name, default))
    except ValueError:
        return float(default)


class RateLimit:
    """A token bucket per authenticated identity: a tripwire against a runaway
    loop, far above what a lab does, not a budget (0 = off). Never keyed by
    source IP (all students share one address). The lock covers arithmetic
    only, no I/O."""

    def __init__(self, burst, per_sec, clock=time.monotonic):
        self.burst, self.rate, self.clock = float(burst), float(per_sec), clock
        self.buckets = {}  # key -> [tokens, last]
        self.lock = threading.Lock()

    def take(self, key, scale=1):
        """0 if the request may go now, else seconds until one may. `scale`
        widens the bucket for shared identities (CI, the read key)."""
        if self.burst <= 0 or self.rate <= 0:
            return 0
        burst, rate = self.burst * scale, self.rate * scale
        with self.lock:
            now = self.clock()
            tokens, last = self.buckets.get(key, (burst, now))
            tokens = min(burst, tokens + (now - last) * rate)
            if tokens >= 1:
                self.buckets[key] = (tokens - 1, now)
                return 0
            self.buckets[key] = (tokens, now)
            return max(1, int((1 - tokens) / rate + 0.999))


class Config:
    def __init__(self, env=os.environ):
        # Per-identity request tripwire (DNS_API_RATE_*, module.env; 0 = off).
        self.rate_burst = _rate(env, "DNS_API_RATE_BURST", 200)
        self.rate_per_sec = _rate(env, "DNS_API_RATE_PER_SEC", 50)
        self.upstream = urlsplit(env.get("PDNS_API_URL", "http://dns-server:8081"))
        self.upstream_key = env.get("PDNS_UPSTREAM_KEY", "")
        self.read_key = env.get("DNS_GATE_READ_KEY", "workshop-not-a-secret")
        self.seed = env.get("STUDENT_PASSWORD_SEED", "")
        self.facilitator = env.get("FACILITATOR_USERNAME") or "root"
        self.user_parents = names(env.get("DNS_GATE_USER_PARENTS", "dojo.test"))
        self.shared_zones = set(names(env.get("DNS_GATE_SHARED_ZONES", "")))
        self.ci_zones = set(names(env.get("DNS_GATE_CI_ZONES", "")))
        self.ci_repo = env.get("DNS_GATE_CI_REPO", "")
        self.ci_audience = env.get("DNS_GATE_CI_AUDIENCE", "dns-api")
        self.ci_issuer = env.get("PUBLIC_BASE_URL", "").rstrip("/") + "/git/api/actions"
        self.jwks_url = env.get("FORGEJO_JWKS_URL") or "http://git-server:3000/api/actions/.well-known/keys"
        # Student reset (engine `resets` hook, reset.py): its token, and the records to seed again.
        self.reset_token = env.get("RESET_TOKEN", "")
        self.reset_records = student_reset.parse_records(env.get("DNS_GATE_RESET_RECORDS", ""))


# --- who is asking -------------------------------------------------------------

class Caller:
    def __init__(self, kind, name, ci_writes=False):
        self.kind, self.name, self.ci_writes = kind, name, ci_writes

    def __repr__(self):
        return f"{self.kind}:{self.name}"


def b64url_decode(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def rs256_ok(signing_input, sig, jwk):
    """PKCS#1 v1.5 RSA-SHA256 check: rebuild the expected encoded message and
    compare it whole (no parsing of the decrypted block)."""
    n = int.from_bytes(b64url_decode(jwk["n"]), "big")
    e = int.from_bytes(b64url_decode(jwk["e"]), "big")
    k = (n.bit_length() + 7) // 8
    if k < 256 or len(sig) != k:
        return False
    s = int.from_bytes(sig, "big")
    if s >= n:
        return False
    t = SHA256_DIGEST_INFO + hashlib.sha256(signing_input).digest()
    expected = b"\x00\x01" + b"\xff" * (k - len(t) - 3) + b"\x00" + t
    return hmac.compare_digest(pow(s, e, n).to_bytes(k, "big"), expected)


def verify_jwt(token, jwks):
    """The claims of an RS256 JWT one of jwks' keys signed; ValueError otherwise."""
    try:
        header_b64, claims_b64, sig_b64 = token.split(".")
        header = json.loads(b64url_decode(header_b64))
        claims = json.loads(b64url_decode(claims_b64))
        sig = b64url_decode(sig_b64)
    except (ValueError, TypeError) as e:
        raise ValueError(f"not a JWT: {e}") from None
    if not isinstance(header, dict) or header.get("alg") != "RS256":
        raise ValueError("only RS256 tokens are accepted")
    if not isinstance(claims, dict):
        raise ValueError("claims are not an object")
    keys = [k for k in jwks if k.get("kty") == "RSA" and (not header.get("kid") or k.get("kid") == header["kid"])]
    signing_input = f"{header_b64}.{claims_b64}".encode()
    for k in keys:
        try:
            if rs256_ok(signing_input, sig, k):
                return claims
        except (KeyError, ValueError, TypeError):
            continue
    raise ValueError("no Forgejo key signed this token")


def check_ci_claims(claims, cfg, now=None):
    """Caller for a verified Forgejo Actions token, or ValueError."""
    now = time.time() if now is None else now
    if claims.get("iss") != cfg.ci_issuer:
        raise ValueError(f"issuer {claims.get('iss')!r} is not this Forgejo's Actions ({cfg.ci_issuer})")
    aud = claims.get("aud")
    if cfg.ci_audience not in (aud if isinstance(aud, list) else [aud]):
        raise ValueError(f"audience must be {cfg.ci_audience!r}")
    try:
        if float(claims["exp"]) < now - 30:
            raise ValueError("token expired")
        if float(claims.get("nbf", now)) > now + 60:
            raise ValueError("token not valid yet")
    except (KeyError, TypeError):
        raise ValueError("token has no valid exp") from None
    repo, ref = claims.get("repository") or "", claims.get("ref") or ""
    event = claims.get("event_name") or ""
    writes = bool(cfg.ci_repo) and repo == cfg.ci_repo and ref == "refs/heads/main" and event == "push"
    return Caller("ci", f"{repo}@{ref}#{event}", ci_writes=writes)


class ForgejoKeys:
    """Forgejo's Actions signing keys, fetched again when a token names a key
    we don't have (at most every 30 s). The fetch happens outside the lock."""

    def __init__(self, url):
        self.url, self.keys, self.fetched = url, [], 0.0
        self.lock = threading.Lock()

    def get(self, kid):
        with self.lock:
            stale = (not self.keys or (kid and not any(k.get("kid") == kid for k in self.keys))) \
                and time.time() - self.fetched > 30
            if stale:
                self.fetched = time.time()
            keys = list(self.keys)
        if not stale:
            return keys
        try:
            with urllib.request.urlopen(self.url, timeout=5) as r:
                keys = json.load(r).get("keys", [])
        except (OSError, ValueError):
            return keys
        with self.lock:
            self.keys = keys
        return list(keys)


def identify(key, cfg, forgejo_keys, now=None):
    """Caller for an X-API-Key value; ValueError when it is none of the three."""
    if key and hmac.compare_digest(key.encode(), cfg.read_key.encode()):
        return Caller("reader", "read-key")
    if key.count(".") == 2 and key.startswith("eyJ"):
        try:
            kid = json.loads(b64url_decode(key.split(".")[0])).get("kid")
        except (ValueError, TypeError, AttributeError):
            raise ValueError("not a JWT") from None
        return check_ci_claims(verify_jwt(key, forgejo_keys.get(kid)), cfg, now)
    user, _, _ = key.rpartition(".")
    if cfg.seed and USER_NAME.match(user) and hmac.compare_digest(key.encode(), dns_key(cfg.seed, user).encode()):
        return Caller("user", user)
    raise ValueError("unknown key")


# --- what they may do ----------------------------------------------------------

def owns(caller, name, cfg):
    """Does this account own this DNS name (<user>.<parent> or below)? The
    facilitator owns every name under a parent, but never a parent or a
    shared or CI zone itself (certs.dojo.test sits under dojo.test)."""
    if caller.name == cfg.facilitator and (name in cfg.user_parents or name in cfg.shared_zones
                                           or name in cfg.ci_zones):
        return False
    for parent in cfg.user_parents:
        if caller.name == cfg.facilitator:
            if name.endswith("." + parent):
                return True
            continue
        mine = f"{caller.name}.{parent}"
        if name == mine or name.endswith("." + mine):
            return True
    return False


def rrset_names(body):
    try:
        rrsets = json.loads(body or b"{}").get("rrsets")
    except (ValueError, AttributeError):
        return None
    if not isinstance(rrsets, list) or not rrsets:
        return None
    out = []
    for r in rrsets:
        if not isinstance(r, dict) or not isinstance(r.get("name"), str):
            return None
        out.append(zone_name(r["name"]))
    return out


def decide(method, path, body, caller, cfg):
    """Return None to forward the request, or an error message for a 403."""
    if method not in WRITE_METHODS:
        return None
    m = ZONE_PATH.match(path)
    if m:
        zone, sub = zone_name(m.group(1)), m.group(2) or ""
    elif ZONES_PATH.match(path) and method == "POST":
        try:
            zone, sub = zone_name(json.loads(body or b"{}").get("name", "")), ""
        except (ValueError, AttributeError):
            return "Zone creation needs a JSON body with a name."
    else:
        return "This API only allows zone changes."
    shown = zone.rstrip(".")
    if caller.kind == "reader":
        return "The read key only reads. Your own key is in $DNS_API_KEY."
    if zone in cfg.ci_zones:
        if caller.kind == "ci" and caller.ci_writes:
            return None
        if caller.kind == "ci":
            return (f"{shown} changes only from a push to main of {cfg.ci_repo or 'the class repo'} "
                    f"(this job: {caller.name}).")
        return (f"{shown} is the shared zone: only CI changes it. Open a pull request; "
                f"the DNS Apply job pushes it after the merge.")
    if caller.kind != "user":
        return f"CI changes only {' '.join(sorted(z.rstrip('.') for z in cfg.ci_zones)) or 'nothing'} here."
    if owns(caller, zone, cfg):
        return None
    if zone in cfg.shared_zones:
        if method != "PATCH" or sub:
            return f"In {shown} you can only PATCH records under your own name."
        rr = rrset_names(body)
        if rr is None:
            return "A PATCH needs a JSON body with rrsets, each with a name."
        theirs = [n.rstrip(".") for n in rr if not owns(caller, n, cfg)]
        if theirs:
            return f"{', '.join(theirs[:3])}: not yours. You may change names under {caller.name}.{shown}."
        return None
    parents = " or ".join(f"{caller.name}.{p.rstrip('.')}" for p in cfg.user_parents)
    return f"{shown} is not yours. You may change {parents} (and names under it)."


# --- the proxy -----------------------------------------------------------------

CFG = Config()
KEYS = ForgejoKeys(CFG.jwks_url)
LIMIT = RateLimit(CFG.rate_burst, CFG.rate_per_sec)


def pdns(method, path, doc):
    """One PowerDNS API call with the upstream key (student reset): (status, parsed JSON or None)."""
    conn = http.client.HTTPConnection(CFG.upstream.hostname, CFG.upstream.port or 80, timeout=30)
    try:
        body = json.dumps(doc).encode() if doc is not None else None
        conn.request(method, path, body=body, headers={"X-API-Key": CFG.upstream_key, "Content-Type": "application/json"})
        resp = conn.getresponse()
        raw = resp.read()
    finally:
        conn.close()
    try:
        return resp.status, json.loads(raw) if raw else None
    except ValueError:
        return resp.status, None


def _zone_of(path):
    m = ZONE_PATH.match(path)
    return unquote(m.group(1)) if m else ""


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "dojo-dns-api"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def audit(self, who, method, path, result, why=""):
        # One JSON line per zone-write decision (remediation T1.4, FIND-13).
        line = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": "zone-write",
                "account": who, "ip": self.client_address[0], "action": method, "target": path[:200],
                "result": result}
        if why:
            line["why"] = why[:200]
        print(json.dumps(line, separators=(",", ":")), flush=True)

    def log_message(self, fmt, *args):
        pass

    def send_json(self, status, message):
        self.send_json_headers(status, message, {})

    def send_json_headers(self, status, message, extra):
        data = json.dumps({"error": message}).encode()
        self.send_response(status)
        for k, v in extra.items():
            self.send_header(k, v)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def handle_any(self):
        method = self.command
        path = urlsplit(self.path).path
        if path == "/healthz":
            return self.send_json(200, "") if method == "GET" else self.send_json(405, "GET only")
        if path.startswith("/_dojo/reset/"):
            return self.student_reset(method, path)
        try:
            caller = identify(self.headers.get("X-API-Key", ""), CFG, KEYS)
        except ValueError as e:
            self.audit("-", method, path, 401, str(e))
            return self.send_json(401, "Unauthorized: use your own key ($DNS_API_KEY)")
        # Shared identities (CI, the read key) serve the whole class: x5.
        wait = LIMIT.take(repr(caller), 1 if caller.kind == "user" else 5)
        if wait:
            self.audit(repr(caller), method, path, 429, "rate limit")
            return self.send_json_headers(429, "Too many requests: slow down and retry", {"Retry-After": str(wait)})
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self.send_json(400, "Bad Content-Length")
        if length < 0 or length > MAX_BODY or "chunked" in self.headers.get("Transfer-Encoding", "").lower():
            return self.send_json(413, "Request body too large or chunked")
        body = self.rfile.read(length) if length else b""

        refusal = decide(method, path, body, caller, CFG)
        if refusal:
            self.audit(repr(caller), method, path, 403, refusal)
            if caller.kind == "user" and method in WRITE_METHODS:
                REPORTER.refused(caller.name, _zone_of(path))
            return self.send_json(403, refusal)
        if method in WRITE_METHODS:
            self.audit(repr(caller), method, path, "allow")

        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP and k.lower() != "x-api-key"}
        headers["X-API-Key"] = CFG.upstream_key
        try:
            conn = http.client.HTTPConnection(CFG.upstream.hostname, CFG.upstream.port or 80, timeout=30)
            conn.request(method, self.path, body=body if (body or method in WRITE_METHODS) else None, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
            conn.close()
        except OSError as e:
            return self.send_json(502, f"PowerDNS unreachable: {e.__class__.__name__}")
        if caller.kind == "user" and method == "PATCH" and 200 <= resp.status < 300:
            REPORTER.patched(caller.name, _zone_of(path), body)
        self.send_response(resp.status, resp.reason)
        for k, v in resp.getheaders():
            if k.lower() not in HOP_BY_HOP:
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def student_reset(self, method, path):
        given = self.headers.get("X-Dojo-Reset-Token", "")
        if method != "POST" or not CFG.reset_token or not hmac.compare_digest(given.encode(), CFG.reset_token.encode()):
            return self.send_json(403, "reset token required")
        user = unquote(path[len("/_dojo/reset/"):])
        phase = parse_qs(urlsplit(self.path).query).get("phase", [""])[0]
        if not USER_NAME.match(user) or user == CFG.facilitator or phase not in ("teardown", "provision"):
            return self.send_json(404, "not found")
        try:
            detail = student_reset.run(pdns, user, phase, CFG)
        except (RuntimeError, OSError) as e:
            self.audit("reset", "RESET", user, 500, str(e))
            return self.send_json(500, str(e)[:200])
        self.audit("reset", "RESET", user, "allow", f"{phase}: {detail}")
        data = json.dumps({"ok": True, "detail": detail}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = handle_any


def main():
    if not CFG.upstream_key:
        raise SystemExit("PDNS_UPSTREAM_KEY is empty (the workshop derives POWERDNS_API_KEY in workshop.env)")
    if not CFG.seed:
        print("dns-api: STUDENT_PASSWORD_SEED is empty, so no account key works: only reads and CI "
              "(./dojo setup writes a seed to .env)", flush=True)
    server = http.server.ThreadingHTTPServer(("", LISTEN_PORT), Handler)
    server.daemon_threads = True
    print(f"dns-api gate on :{LISTEN_PORT} -> {CFG.upstream.geturl()}; accounts own <user>."
          f"{{{','.join(p.rstrip('.') for p in CFG.user_parents)}}}; shared: "
          f"{' '.join(sorted(CFG.shared_zones)) or '-'}; CI only: {' '.join(sorted(CFG.ci_zones)) or '-'} "
          f"(from {CFG.ci_repo or '-'})", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
