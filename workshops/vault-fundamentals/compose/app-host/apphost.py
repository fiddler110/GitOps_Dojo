#!/usr/bin/env python3
"""app-host: the deployment target of labs 11-13, a small "platform".

One slot per student (PLAN.md §5.6, P4). Each slot is its own Linux user with
the student's name; its app runs as that user in its own user + PID
namespace, with prlimit caps (the runner pool's pattern, T0.8), so one slot
can't see or signal another's processes or read its files.

What the platform gives each slot, and what it asks of a deploy:

- **A platform identity.** Every few minutes it writes each slot a short-lived
  JWT signed with its own key (iss http://app-host:8080, aud openbao,
  sub slot:<name>) to /run/platform/<name>/token, readable by that slot's user
  only: the lab's version of a Kubernetes projected service-account token or
  an Azure managed identity. The public keys are at /.well-known/jwks.json, so
  a vault can trust them.
- **A deploy API.** POST /deploy with a tar.gz of the app and, as the bearer
  token, the CI job's own Forgejo Actions ID token (audience app-host). The
  platform checks it against Forgejo's keys and deploys to the slot of the
  repository's owner, from <owner>/<DEPLOY_REPO> on main only. No stored deploy
  secret exists. The bundle is unpacked by the slot's user, and its start.sh
  runs as that user with $PORT, $SLOT and $BAO_ADDR set.

HTTP on :8080. Direct (workshop_lab, runner_net): /healthz, the JWKS,
/deploy, and /<slot>/... proxied to that slot's app. Apps are public in the
class, like any web app; their pages are sandboxed (CSP) and get none of the
caller's cookies or headers. Through the gateway's /apps route (identity gate,
prefix stripped, X-Gateway-Token checked here): a page with your slot's state
and log, and every slot for the facilitator.
"""
import base64
import collections
import hashlib
import hmac
import http.client
import http.server
import json
import os
import pwd
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

KEY_PATH = "/var/lib/app-host/key.pem"
META_DIR = "/srv/apps/.platform"
APPS_DIR = "/srv/apps"
TOKEN_DIR = "/run/platform"
STATIC_DIR = os.path.dirname(os.path.abspath(__file__))
ISSUER = "http://app-host:8080"
AUDIENCE = "openbao"
DEPLOY_AUDIENCE = "app-host"
TOKEN_LIFETIME = 600  # seconds a platform token is valid
TOKEN_REFRESH = 300   # a new one is written this often
UID_BASE = 30000
PORT_BASE = 9000
MAX_BUNDLE = 5 * 1024 * 1024
MAX_PROXY_BODY = 1024 * 1024
MAX_PROXY_RESPONSE = 5 * 1024 * 1024
LOG_LINES = 200
# A crashing app is restarted after RESTART_DELAY, at most RESTART_LIMIT times
# in RESTART_WINDOW seconds; then it stays down until the next deploy.
RESTART_DELAY = 3
RESTART_LIMIT = 5
RESTART_WINDOW = 120
CLEAN_ENV = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"}
# What a slot's app may connect to (remediation T2.2b, FIND-04): DNS,
# OpenBao and app-db, by port. Nothing else on these networks listens on
# them, and a port rule survives either service being restarted.
SLOT_EGRESS_PORTS = {"udp": [53], "tcp": [53, 8200, 5432]}
# Proxied app pages: no script, an opaque origin, nothing loaded from elsewhere.
APP_CSP = "sandbox; default-src 'none'; img-src data:; style-src 'unsafe-inline'"
PANEL_CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
             "img-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'none'")
# Headers a request to an app keeps; everything else (Cookie, Authorization,
# the gateway's X-Auth-User and X-Gateway-Token) is dropped.
REQUEST_HEADERS_KEPT = ("accept", "accept-language", "content-type", "user-agent")
RESPONSE_HEADERS_DROPPED = ("set-cookie", "content-security-policy", "content-length", "transfer-encoding",
                            "connection", "keep-alive", "x-frame-options")


def log(msg):
    print(f"[platform] {msg}", flush=True)


class Config:
    def __init__(self, env):
        def count(name):
            try:
                return int(env.get(name) or 0)
            except ValueError:
                return 0
        # A slot per student, then per demo bot (./run.sh --test).
        prefix, bots = env.get("STUDENT_PREFIX") or "student", env.get("BOT_PREFIX") or "testuser"
        self.slots = ([f"{prefix}{n:02d}" for n in range(1, count("STUDENT_COUNT") + 1)]
                      + [f"{bots}{n}" for n in range(1, count("BOT_COUNT") + 1)])
        self.gateway_token = env.get("GATEWAY_TOKEN", "")
        self.facilitator = env.get("FACILITATOR_USERNAME") or "root"
        self.repo = env.get("DEPLOY_REPO") or "vault-fundamentals"
        self.forgejo_issuer = (env.get("PUBLIC_BASE_URL", "").rstrip("/")) + "/git/api/actions"
        self.forgejo_jwks = env.get("FORGEJO_JWKS_URL") or "http://git-server:3000/api/actions/.well-known/keys"
        self.bao_addr = env.get("BAO_ADDR") or "http://openbao:8200"
        self.limits = [f"--nproc={int(env.get('SLOT_NPROC') or 128)}",
                       f"--nofile={int(env.get('SLOT_NOFILE') or 1024)}",
                       f"--fsize={int(env.get('SLOT_FSIZE') or 64 * 1024 * 1024)}"]


# --- JWTs -------------------------------------------------------------------

def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def b64url_decode(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _der(tag, body):
    n = len(body)
    if n < 0x80:
        length = bytes([n])
    else:
        raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
        length = bytes([0x80 | len(raw)]) + raw
    return bytes([tag]) + length + body


def _der_int(value):
    raw = value.to_bytes((value.bit_length() + 8) // 8, "big")  # a leading 0 keeps it positive
    return _der(0x02, raw)


def rsa_public_pem(n, e):
    """PEM (SubjectPublicKeyInfo) for an RSA key given as integers, which is
    what openssl needs to check a signature made with a JWK's key."""
    rsa_key = _der(0x30, _der_int(n) + _der_int(e))
    algorithm = _der(0x30, _der(0x06, bytes.fromhex("2a864886f70d010101")) + b"\x05\x00")
    spki = _der(0x30, algorithm + _der(0x03, b"\x00" + rsa_key))
    body = base64.encodebytes(spki).decode().replace("\n", "")
    lines = [body[i:i + 64] for i in range(0, len(body), 64)]
    return "-----BEGIN PUBLIC KEY-----\n" + "\n".join(lines) + "\n-----END PUBLIC KEY-----\n"


def sign_jwt(claims, key_path=KEY_PATH, kid=None):
    header = {"alg": "RS256", "typ": "JWT"}
    if kid:
        header["kid"] = kid
    signing_input = (b64url(json.dumps(header, separators=(",", ":")).encode()) + "."
                     + b64url(json.dumps(claims, separators=(",", ":")).encode()))
    sig = subprocess.run(["openssl", "dgst", "-sha256", "-sign", key_path], input=signing_input.encode(),
                         capture_output=True, check=True).stdout
    return signing_input + "." + b64url(sig)


def public_jwk(key_path=KEY_PATH):
    out = subprocess.run(["openssl", "rsa", "-in", key_path, "-noout", "-modulus"],
                         capture_output=True, text=True, check=True).stdout.strip()
    n = int(out.split("=", 1)[1], 16)
    n_bytes = n.to_bytes((n.bit_length() + 7) // 8, "big")
    kid = b64url(hashlib.sha256(n_bytes).digest())[:16]
    # openssl genrsa's public exponent is 65537.
    return {"kty": "RSA", "alg": "RS256", "use": "sig", "kid": kid, "n": b64url(n_bytes), "e": "AQAB"}


def verify_rs256(token, jwks):
    """The claims of an RS256 JWT whose signature one of jwks' keys checks;
    ValueError otherwise. Claims are not checked here."""
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
    if not keys:
        raise ValueError("no key matches the token's kid")
    signing_input = f"{header_b64}.{claims_b64}".encode()
    with tempfile.TemporaryDirectory() as tmp:
        sig_path = os.path.join(tmp, "sig")
        with open(sig_path, "wb") as f:
            f.write(sig)
        for i, k in enumerate(keys):
            pem_path = os.path.join(tmp, f"key{i}.pem")
            with open(pem_path, "w") as f:
                f.write(rsa_public_pem(int.from_bytes(b64url_decode(k["n"]), "big"),
                                       int.from_bytes(b64url_decode(k["e"]), "big")))
            ok = subprocess.run(["openssl", "dgst", "-sha256", "-verify", pem_path, "-signature", sig_path],
                                input=signing_input, capture_output=True).returncode == 0
            if ok:
                return claims
    raise ValueError("bad signature")


def check_deploy_claims(claims, cfg, now=None):
    """The slot a verified Forgejo Actions ID token may deploy to, or
    ValueError saying why not."""
    now = time.time() if now is None else now
    if claims.get("iss") != cfg.forgejo_issuer:
        raise ValueError(f"issuer {claims.get('iss')!r} is not Forgejo Actions ({cfg.forgejo_issuer})")
    aud = claims.get("aud")
    if DEPLOY_AUDIENCE not in (aud if isinstance(aud, list) else [aud]):
        raise ValueError(f"audience must be {DEPLOY_AUDIENCE!r} (ask for the token with &audience={DEPLOY_AUDIENCE})")
    try:
        if float(claims["exp"]) < now - 30:
            raise ValueError("token expired")
        if float(claims.get("nbf", now)) > now + 60:
            raise ValueError("token not valid yet")
    except (KeyError, TypeError):
        raise ValueError("token has no valid exp") from None
    repository = claims.get("repository") or ""
    owner = repository.split("/", 1)[0]
    if owner not in cfg.slots:
        raise ValueError(f"{repository!r}: its owner has no slot on this platform")
    if repository != f"{owner}/{cfg.repo}":
        raise ValueError(f"only {owner}/{cfg.repo} deploys to slot {owner}, not {repository!r}")
    if claims.get("ref") != "refs/heads/main":
        raise ValueError(f"only main deploys; this run is on {claims.get('ref')!r}")
    return owner


class ForgejoKeys:
    """Forgejo's Actions signing keys, fetched again when a token names a
    key we don't have (at most every 30 s)."""

    def __init__(self, url):
        self.url = url
        self.keys = []
        self.fetched = 0.0
        self.lock = threading.Lock()

    def get(self, kid):
        with self.lock:
            if (not self.keys or (kid and not any(k.get("kid") == kid for k in self.keys))) \
                    and time.time() - self.fetched > 30:
                self.fetched = time.time()
                with urllib.request.urlopen(self.url, timeout=5) as r:
                    self.keys = json.load(r).get("keys", [])
            return list(self.keys)


# --- request and response scrubbing for the app proxy -------------------------

def app_request_headers(headers):
    return {k: v for k, v in headers.items() if k.lower() in REQUEST_HEADERS_KEPT}


def app_response_headers(headers):
    out = [(k, v) for k, v in headers if k.lower() not in RESPONSE_HEADERS_DROPPED]
    out += [("Content-Security-Policy", APP_CSP), ("X-Content-Type-Options", "nosniff"),
            ("Referrer-Policy", "no-referrer")]
    return out


def listeners(port):
    """The uids with a socket listening on this TCP port. Every slot shares
    the container's network, so a slot could take another's port first: the
    proxy only forwards to a port its own slot's user holds."""
    uids = set()
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(table) as f:
                next(f, None)
                for line in f:
                    fields = line.split()
                    if len(fields) > 7 and fields[3] == "0A" and int(fields[1].rsplit(":", 1)[1], 16) == port:
                        uids.add(int(fields[7]))
        except (OSError, ValueError):
            pass
    return uids


# --- slots --------------------------------------------------------------------

def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, env=CLEAN_ENV, **kw)


class Slot:
    def __init__(self, name, index):
        self.name = name
        self.uid = UID_BASE + index
        self.port = PORT_BASE + index
        self.home = os.path.join(APPS_DIR, name)
        self.token_dir = os.path.join(TOKEN_DIR, name)
        self.state = "empty"
        self.since = time.time()
        self.proc = None
        self.generation = 0
        self.log = collections.deque(maxlen=LOG_LINES)
        self.restarts = collections.deque(maxlen=RESTART_LIMIT + 1)
        self.deployed = None
        self.token_exp = 0
        self.token_written = 0
        self.deploy_lock = threading.Lock()

    def to_json(self, with_log):
        doc = {"name": self.name, "state": self.state, "since": self.since, "port": self.port,
               "deployed": self.deployed, "restarts": len(self.restarts), "token_expires": self.token_exp}
        if with_log:
            doc["log"] = list(self.log)
        return doc


def isolate_slots(first_uid, last_uid):
    """An OUTPUT allowlist for the slot users (the DOJO_ISOLATION pattern of
    the web-terminal): loopback (this platform's proxy to each app, and the
    app's own port), SLOT_EGRESS_PORTS, and a reject for the rest, so a
    student's app can't reach the terminals, Forgejo or anything else on
    workshop_lab and runner_net. Idempotent across restarts. Needs NET_ADMIN
    (docker-compose.override.yml)."""
    def ipt(*args, check=True):
        return run(["iptables", *args], check=check)
    if ipt("-N", "DOJO_SLOT_EGRESS", check=False).returncode != 0:
        ipt("-F", "DOJO_SLOT_EGRESS")
    jump = ["OUTPUT", "-m", "owner", "--uid-owner", f"{first_uid}-{last_uid}", "-j", "DOJO_SLOT_EGRESS"]
    if ipt("-C", *jump, check=False).returncode != 0:
        ipt("-A", *jump)
    ipt("-A", "DOJO_SLOT_EGRESS", "-o", "lo", "-j", "RETURN")
    for proto, ports in SLOT_EGRESS_PORTS.items():
        ipt("-A", "DOJO_SLOT_EGRESS", "-p", proto, "-m", "multiport",
            "--dports", ",".join(map(str, ports)), "-j", "RETURN")
    ipt("-A", "DOJO_SLOT_EGRESS", "-p", "tcp", "-j", "REJECT", "--reject-with", "tcp-reset")
    ipt("-A", "DOJO_SLOT_EGRESS", "-j", "REJECT")
    log(f"slot egress: uids {first_uid}-{last_uid} reach only lo and " +
        ", ".join(f"{p}/{','.join(map(str, v))}" for p, v in SLOT_EGRESS_PORTS.items()))


class Platform:
    def __init__(self, cfg):
        self.cfg = cfg
        self.lock = threading.Lock()  # every Slot's state, since, proc, log
        self.slots = {name: Slot(name, i) for i, name in enumerate(cfg.slots, start=1)}
        self.forgejo_keys = ForgejoKeys(cfg.forgejo_jwks)
        self.jwk = None

    # set-up
    def prepare(self):
        os.makedirs(os.path.dirname(KEY_PATH), mode=0o700, exist_ok=True)
        if not os.path.exists(KEY_PATH):
            run(["openssl", "genrsa", "-out", KEY_PATH, "2048"], check=True)
            os.chmod(KEY_PATH, 0o600)
            log("made the platform's signing key")
        self.jwk = public_jwk()
        os.makedirs(META_DIR, mode=0o700, exist_ok=True)
        os.makedirs(TOKEN_DIR, exist_ok=True)
        # A tmpfs comes world-writable; each slot's own folder is 0700.
        os.chmod(TOKEN_DIR, 0o755)
        os.chmod(APPS_DIR, 0o755)
        uids = [s.uid for s in self.slots.values()]
        isolate_slots(min(uids), max(uids))
        for s in self.slots.values():
            try:
                pwd.getpwnam(s.name)
            except KeyError:
                run(["useradd", "-M", "-d", s.home, "-s", "/usr/sbin/nologin", "-u", str(s.uid), "-U", s.name],
                    check=True)
            for d in (s.home, s.token_dir):
                os.makedirs(d, exist_ok=True)
                os.chown(d, s.uid, s.uid)
                os.chmod(d, 0o700)
            self.kill_all(s)
            try:
                with open(os.path.join(META_DIR, s.name + ".json")) as f:
                    s.deployed = json.load(f)
            except (OSError, ValueError):
                s.deployed = None
            self.write_token(s)
            if s.deployed and os.path.exists(os.path.join(s.home, "app", "start.sh")):
                self.start(s, "the platform restarted")
        log(f"{len(self.slots)} slots ready")

    # platform identity
    def write_token(self, s):
        now = int(time.time())
        claims = {"iss": ISSUER, "aud": AUDIENCE, "sub": f"slot:{s.name}", "slot": s.name,
                  "iat": now, "nbf": now - 5, "exp": now + TOKEN_LIFETIME}
        token = sign_jwt(claims, kid=self.jwk["kid"])
        tmp = os.path.join(s.token_dir, ".token.tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o400)
        with os.fdopen(fd, "w") as f:
            f.write(token)
        os.chown(tmp, s.uid, s.uid)
        os.replace(tmp, os.path.join(s.token_dir, "token"))
        s.token_exp, s.token_written = claims["exp"], now

    def refresh_tokens(self):
        while True:
            time.sleep(15)
            for s in self.slots.values():
                if time.time() - s.token_written >= TOKEN_REFRESH:
                    try:
                        self.write_token(s)
                    except (OSError, subprocess.CalledProcessError) as e:
                        log(f"{s.name}: could not write its token: {e}")

    # processes
    def kill_all(self, s):
        run(["su", s.name, "-s", "/bin/sh", "-c", "kill -9 -1"])

    def note(self, s, line):
        with self.lock:
            s.log.append(f"{time.strftime('%H:%M:%S')} {line}")

    def start(self, s, why):
        env = dict(CLEAN_ENV, SLOT=s.name, PORT=str(s.port), BAO_ADDR=self.cfg.bao_addr,
                   PLATFORM_TOKEN_FILE=os.path.join(s.token_dir, "token"))
        inner = ('umask 077; cd "$HOME/app" || exit 1; export TMPDIR="$HOME/tmp"; '
                 f'exec prlimit {" ".join(self.cfg.limits)} -- unshare -U --map-current-user -p -f --mount-proc '
                 'sh ./start.sh')
        with self.lock:
            s.generation += 1
            gen = s.generation
            s.state, s.since = "starting", time.time()
        self.note(s, f"[platform] starting ({why})")
        proc = subprocess.Popen(["su", s.name, "-s", "/bin/sh", "-c", inner], env=env,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors="replace", start_new_session=True)
        with self.lock:
            s.proc = proc
        threading.Thread(target=self.watch, args=(s, proc, gen), daemon=True).start()

    def watch(self, s, proc, gen):
        for line in proc.stdout:
            with self.lock:
                if s.generation != gen:
                    continue
            self.note(s, line.rstrip("\n")[:500])
        rc = proc.wait()
        with self.lock:
            if s.generation != gen:
                return  # stopped on purpose (a new deploy)
            s.restarts.append(time.time())
            recent = [t for t in s.restarts if time.time() - t < RESTART_WINDOW]
            give_up = len(recent) > RESTART_LIMIT
            s.state, s.since = ("crashed" if give_up else "restarting"), time.time()
        self.note(s, f"[platform] the app exited ({rc})" + ("; not restarting until the next deploy" if give_up else ""))
        if give_up:
            return
        time.sleep(RESTART_DELAY)
        with self.lock:
            if s.generation != gen:
                return
        self.start(s, "restart after exit")

    def stop(self, s):
        with self.lock:
            s.generation += 1
            proc = s.proc
            s.proc = None
        self.kill_all(s)
        if proc is not None:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass

    def app_answers(self, s):
        """The slot's app is listening on its port, and no one else is."""
        return listeners(s.port) == {s.uid}

    def watch_running(self):
        """starting → running once the app accepts connections."""
        while True:
            time.sleep(1)
            with self.lock:
                starting = [s for s in self.slots.values() if s.state == "starting"]
            for s in starting:
                if self.app_answers(s):
                    with self.lock:
                        if s.state == "starting":
                            s.state, s.since = "running", time.time()

    # deploys
    def deploy(self, s, bundle, claims):
        with s.deploy_lock:
            self.stop(s)
            # A deploy starts from an empty home: nothing the last version
            # wrote (rendered secrets, a stale database login) outlives it.
            for name in os.listdir(s.home):
                p = os.path.join(s.home, name)
                if os.path.isdir(p) and not os.path.islink(p):
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    os.unlink(p)
            app, tmp = os.path.join(s.home, "app"), os.path.join(s.home, "tmp")
            for d in (app, tmp):
                os.makedirs(d)
                os.chown(d, s.uid, s.uid)
                os.chmod(d, 0o700)
            with self.lock:
                s.log.clear()
                s.restarts.clear()
            # Unpacked by the slot's own user: a crafted archive can only write
            # where that user can.
            out = subprocess.run(
                ["su", s.name, "-s", "/bin/sh", "-c",
                 f'umask 077; cd "$HOME/app" && exec prlimit {" ".join(self.cfg.limits)} -- '
                 'tar -xzf - --no-same-owner --no-same-permissions'],
                input=bundle, capture_output=True, env=CLEAN_ENV, timeout=60)
            if out.returncode != 0:
                with self.lock:
                    s.state, s.since = "failed", time.time()
                return 400, {"error": "could not unpack the bundle (a tar.gz of the app folder)",
                             "detail": out.stderr.decode(errors="replace")[-400:]}
            if not os.path.isfile(os.path.join(app, "start.sh")):
                with self.lock:
                    s.state, s.since = "failed", time.time()
                return 400, {"error": "the bundle has no start.sh at its top level"}
            s.deployed = {k: claims.get(k) for k in ("repository", "ref", "sha", "actor", "workflow", "run_number")}
            s.deployed["at"] = time.time()
            with open(os.path.join(META_DIR, s.name + ".json"), "w") as f:
                json.dump(s.deployed, f)
            sha = (claims.get("sha") or "")[:10]
            log(f"{s.name}: deployed {sha} by {claims.get('actor')}")
            self.note(s, f"[platform] deployed {sha} from {claims.get('repository')} by {claims.get('actor')}")
            self.start(s, "deploy")
        deadline = time.time() + 20
        while time.time() < deadline:
            with self.lock:
                state = s.state
            if state == "starting" and self.app_answers(s):
                with self.lock:
                    s.state, s.since = "running", time.time()
                break
            if state not in ("starting",):
                break
            time.sleep(0.5)
        with self.lock:
            doc = {"slot": s.name, "state": s.state, "url": f"http://app-host:8080/{s.name}/",
                   "deployed": s.deployed}
            if s.state != "running":
                doc["log"] = list(s.log)[-15:]
        return (200 if doc["state"] == "running" else 502), doc


# --- HTTP -----------------------------------------------------------------------

STATIC = {"/": ("panel.html", "text/html; charset=utf-8"),
          "/panel.js": ("panel.js", "text/javascript; charset=utf-8"),
          "/panel.css": ("panel.css", "text/css; charset=utf-8")}


def make_handler(platform):
    cfg = platform.cfg

    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "app-host"
        sys_version = ""
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            pass

        def _send(self, code, body, ctype, extra=()):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in extra:
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, code, doc):
            self._send(code, json.dumps(doc).encode(), "application/json")

        def _gateway_user(self):
            """The signed-in account, if this request came through the gateway."""
            token = self.headers.get("X-Gateway-Token", "")
            if not cfg.gateway_token or not hmac.compare_digest(token, cfg.gateway_token):
                return None
            return self.headers.get("X-Auth-User") or None

        def _slot_path(self):
            parts = self.path.split("?", 1)[0].split("/", 2)
            if len(parts) >= 2 and parts[1] in platform.slots:
                return platform.slots[parts[1]], ("/" + parts[2] if len(parts) == 3 else None)
            return None, None

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/healthz":
                return self._json(200, {"ok": True})
            if path == "/.well-known/jwks.json":
                return self._json(200, {"keys": [platform.jwk]})
            slot, _rest = self._slot_path()
            if slot is not None:
                return self._proxy()
            user = self._gateway_user()
            if path in STATIC or path == "/api/status":
                if user is None:
                    return self._json(403, {"error": "open this through the dojo's /apps page"})
                if path == "/api/status":
                    return self._status(user)
                name, ctype = STATIC[path]
                with open(os.path.join(STATIC_DIR, name), "rb") as f:
                    body = f.read()
                return self._send(200, body, ctype, [("Content-Security-Policy", PANEL_CSP),
                                                     ("X-Content-Type-Options", "nosniff")])
            self._json(404, {"error": "not found"})

        def do_POST(self):
            if self.path.split("?", 1)[0] == "/deploy":
                return self._deploy()
            if self._slot_path()[0] is not None:
                return self._proxy()
            self._json(404, {"error": "not found"})

        def _status(self, user):
            facilitator = user == cfg.facilitator
            with platform.lock:
                slots = [s.to_json(with_log=True) for s in platform.slots.values()
                         if facilitator or s.name == user]
            self._json(200, {"user": user, "facilitator": facilitator, "slots": slots,
                             "issuer": ISSUER, "now": time.time()})

        def _deploy(self):
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return self._json(401, {"error": "send the job's ID token (audience app-host) as a Bearer token"})
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                return self._json(411, {"error": "Content-Length required"})
            if length > MAX_BUNDLE:
                return self._json(413, {"error": f"bundle over {MAX_BUNDLE} bytes"})
            bundle = self.rfile.read(length)
            token = auth[len("Bearer "):].strip()
            try:
                header = json.loads(b64url_decode(token.split(".")[0]))
                claims = verify_rs256(token, platform.forgejo_keys.get(header.get("kid")))
                name = check_deploy_claims(claims, cfg)
            except ValueError as e:
                log(f"deploy refused: {e}")
                return self._json(403, {"error": f"deploy refused: {e}"})
            except OSError as e:
                return self._json(503, {"error": f"could not fetch Forgejo's keys: {e}"})
            code, doc = platform.deploy(platform.slots[name], bundle, claims)
            self._json(code, doc)

        def _proxy(self):
            slot, rest = self._slot_path()
            if rest is None:  # /student01 → student01/ (relative, so it works under /apps too)
                return self._send(301, b"", "text/plain", [("Location", slot.name + "/")])
            query = self.path.split("?", 1)[1] if "?" in self.path else ""
            body = None
            if self.command == "POST":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = 0
                if length > MAX_PROXY_BODY:
                    return self._json(413, {"error": "request body too large"})
                body = self.rfile.read(length)
            with platform.lock:
                state = slot.state
            if state not in ("running", "starting"):
                return self._send(503, f"No app is running in slot {slot.name} ({state}).\n".encode(),
                                  "text/plain; charset=utf-8", [("Content-Security-Policy", APP_CSP)])
            if listeners(slot.port) - {slot.uid}:
                platform.note(slot, f"[platform] port {slot.port} is held by another user: not forwarding")
                return self._send(503, f"Slot {slot.name}'s port is taken by another slot.\n".encode(),
                                  "text/plain; charset=utf-8", [("Content-Security-Policy", APP_CSP)])
            conn = http.client.HTTPConnection("127.0.0.1", slot.port, timeout=10)
            try:
                conn.request(self.command, rest + ("?" + query if query else ""), body=body,
                             headers=app_request_headers(self.headers))
                resp = conn.getresponse()
                data = resp.read(MAX_PROXY_RESPONSE + 1)[:MAX_PROXY_RESPONSE]
                headers = app_response_headers(resp.getheaders())
                code = resp.status
            except (OSError, http.client.HTTPException) as e:
                return self._send(502, f"The app in slot {slot.name} didn't answer: {e}\n".encode(),
                                  "text/plain; charset=utf-8", [("Content-Security-Policy", APP_CSP)])
            finally:
                conn.close()
            self.send_response(code)
            for k, v in headers:
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

    return Handler


def main():
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    platform = Platform(Config(os.environ))
    platform.prepare()
    threading.Thread(target=platform.refresh_tokens, daemon=True).start()
    threading.Thread(target=platform.watch_running, daemon=True).start()
    server = http.server.ThreadingHTTPServer(("0.0.0.0", 8080), make_handler(platform))
    server.daemon_threads = True
    log("listening on :8080")
    server.serve_forever()


if __name__ == "__main__":
    main()
