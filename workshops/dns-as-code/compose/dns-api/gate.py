"""PowerDNS API gate for the dns-as-code workshop. Stdlib only.

Everyone's dnscontrol (students' terminals and the CI runner) talks to this
gate instead of PowerDNS: creds.json points at http://dns-api:8081 with the
workshop's public key. The gate swaps in PowerDNS's own key, which only it,
dns-server and the dns-ui module know, and applies one rule:

  * Reads are open.
  * Changes to the shared PROTECTED_ZONE (dojo.test) are accepted only from
    the CI runner (the forgejo-runner container, on runner_net, which no
    student terminal is on). A student's `dnscontrol push` to it gets 403,
    the same as a production API that only the pipeline holds a credential for.
  * Changes to any other zone are accepted only for zones under
    PROTECTED_ZONE (each student's own <user>.dojo.test in Part 1).
  * Any other write (server config, TSIG keys, ...) is refused, CI included.

It can't tell students apart (they share one terminal network namespace and
one key), so it doesn't try to stop one student editing another's sandbox
zone; the lab's own config only declares the student's zone.
"""

import hmac
import http.client
import http.server
import json
import os
import re
import socket
import threading
import time
from urllib.parse import unquote, urlsplit

LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "8081"))
UPSTREAM = urlsplit(os.environ.get("PDNS_API_URL", "http://dns-server:8081"))
UPSTREAM_KEY = os.environ.get("PDNS_UPSTREAM_KEY", "")
if not UPSTREAM_KEY:
    raise SystemExit("PDNS_UPSTREAM_KEY is empty (it is derived in workshop.env)")
PUBLIC_KEY = os.environ.get("PUBLIC_API_KEY", "workshop-not-a-secret")
PROTECTED_ZONE = os.environ.get("PROTECTED_ZONE", "dojo.test").strip(".").lower() + "."
CI_HOSTS = os.environ.get("CI_HOSTS", "forgejo-runner").split()
MAX_BODY = 1024 * 1024

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
ZONES_PATH = re.compile(r"^/api/v1/servers/[^/]+/zones/?$")
ZONE_PATH = re.compile(r"^/api/v1/servers/[^/]+/zones/([^/]+)(/.*)?$")
# Hop-by-hop headers (RFC 9110 7.6.1) are not forwarded either way.
HOP_BY_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
              "te", "trailer", "transfer-encoding", "upgrade", "host", "content-length"}

MSG_PROTECTED = (
    "%s is the shared zone: only CI changes it. Open a pull request against "
    "dns-team/dns-as-code; the DNS Apply job pushes it after the merge."
)
MSG_OUTSIDE = "Only zones under %s can be created or changed here (try <your-user>.%s)."


def canonical_zone(raw):
    """Zone id or name from a URL or body -> lower-case name with one trailing dot.

    PowerDNS zone ids escape odd characters as =XX (e.g. '=2E' for '.'), on top
    of the URL's own %XX escaping; undo both before comparing."""
    name = unquote(raw)
    name = re.sub(r"=([0-9A-Fa-f]{2})", lambda m: chr(int(m.group(1), 16)), name)
    return name.strip().rstrip(".").lower() + "."


def zone_allowed_for_students(zone):
    return zone != PROTECTED_ZONE and zone.endswith("." + PROTECTED_ZONE)


class CiAddresses:
    """IPs of the CI runner, re-resolved at most every few seconds."""

    def __init__(self, hosts, ttl=5.0):
        self.hosts, self.ttl = hosts, ttl
        self.lock = threading.Lock()
        self.addrs, self.expires = frozenset(), 0.0

    def get(self):
        now = time.monotonic()
        with self.lock:
            if now < self.expires:
                return self.addrs
        addrs = set()
        for host in self.hosts:  # DNS lookups happen outside the lock
            try:
                addrs.update(info[4][0] for info in socket.getaddrinfo(host, None))
            except OSError:
                pass
        with self.lock:
            self.addrs, self.expires = frozenset(addrs), now + self.ttl
        return self.addrs


CI = CiAddresses(CI_HOSTS)


def decide(method, path, body, from_ci):
    """Return None to forward the request, or an error message for a 403."""
    if method not in WRITE_METHODS:
        return None
    m = ZONE_PATH.match(path)
    if m:
        zone = canonical_zone(m.group(1))
    elif ZONES_PATH.match(path) and method == "POST":
        try:
            zone = canonical_zone(str(json.loads(body or b"{}").get("name", "")))
        except (ValueError, AttributeError):
            return "Zone creation needs a JSON body with a name."
    else:
        return "This API only allows zone changes."
    if zone == PROTECTED_ZONE:
        return None if from_ci else MSG_PROTECTED % PROTECTED_ZONE.rstrip(".")
    if zone_allowed_for_students(zone):
        return None
    return MSG_OUTSIDE % (PROTECTED_ZONE.rstrip("."), PROTECTED_ZONE.rstrip("."))


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "dojo-dns-api"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    def audit(self, who, method, path, result):
        # One JSON line per zone-write decision (remediation T1.4, FIND-13).
        # All students share one network namespace, so "ip" tells CI from a
        # terminal, not one student from another.
        print(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": "zone-write",
                          "account": who, "ip": self.client_address[0], "action": method, "target": path[:200],
                          "result": result}, separators=(",", ":")), flush=True)

    def log_message(self, fmt, *args):
        pass

    def send_json(self, status, message):
        data = json.dumps({"error": message}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def handle_any(self):
        method = self.command
        path = urlsplit(self.path).path
        if path == "/healthz":
            return self.send_json(200, "") if method == "GET" else self.send_json(405, "GET only")
        key = self.headers.get("X-API-Key", "")
        if not hmac.compare_digest(key.encode(), PUBLIC_KEY.encode()):
            self.audit("-", method, path, 401)
            return self.send_json(401, "Unauthorized")
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self.send_json(400, "Bad Content-Length")
        if length < 0 or length > MAX_BODY or "chunked" in self.headers.get("Transfer-Encoding", "").lower():
            return self.send_json(413, "Request body too large or chunked")
        body = self.rfile.read(length) if length else b""

        from_ci = self.client_address[0] in CI.get()
        refusal = decide(method, path, body, from_ci)
        who = "ci" if from_ci else "terminal"
        if refusal:
            self.audit(who, method, path, 403)
            return self.send_json(403, refusal)
        if method in WRITE_METHODS:
            self.audit(who, method, path, "allow")

        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP and k.lower() != "x-api-key"}
        headers["X-API-Key"] = UPSTREAM_KEY
        try:
            conn = http.client.HTTPConnection(UPSTREAM.hostname, UPSTREAM.port or 80, timeout=30)
            conn.request(method, self.path, body=body if (body or method in WRITE_METHODS) else None, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
            conn.close()
        except OSError as e:
            return self.send_json(502, f"PowerDNS unreachable: {e.__class__.__name__}")
        self.send_response(resp.status, resp.reason)
        for k, v in resp.getheaders():
            if k.lower() not in HOP_BY_HOP:
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = handle_any


def main():
    server = http.server.ThreadingHTTPServer(("", LISTEN_PORT), Handler)
    server.daemon_threads = True
    print(f"dns-api gate on :{LISTEN_PORT} -> {UPSTREAM.geturl()}; {PROTECTED_ZONE} writable only from {CI_HOSTS}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
