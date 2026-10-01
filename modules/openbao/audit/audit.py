#!/usr/bin/env python3
"""openbao-audit: the class audit log, each namespace's admin sees their own.

OpenBao writes one audit file for every namespace, and only its operator can
read it. This service follows that file (the openbao_logs volume, read-only)
and answers "what happened in this namespace?" to whoever can prove they
administer it: the caller sends their own vault token (X-Vault-Token), and
OpenBao itself says what that token may do (sys/capabilities-self). A token
with sudo on sys/audit (the facilitator) may read every namespace.

GET /entries?ns=students/<name>[&accessor=...][&path=...][&limit=N]
  (ns=* for every namespace, the facilitator only)
  → the newest N (default 100) request/response pairs in that namespace,
    oldest first, trimmed to what an incident drill needs: time, operation,
    path, the caller's accessor, display name and policies, the result, and
    for token creation the new token's accessor. Strings OpenBao HMACs stay
    HMACed (accessors don't: hmac_accessor = false in config.hcl).
GET /healthz

The terminal's `bao-audit` command calls it. No gateway identity is involved:
OpenBao's answer about the token is the only thing trusted.

The facilitator's Audit tab in /admin (route /vault-audit, facilitator gate)
is served here too: /, /panel.js, /panel.css and
GET /api/entries?student=<name>|*[&accessor=][&path=][&op=][&errors=1][&limit=N]
  → newest first. A student's entries are those in their namespace, plus
    those in the root namespace (the shared secret/) made by them or on their
    folder. workshop_lab can reach this port directly, so these check
    X-Gateway-Token and X-Auth-User == FACILITATOR_USERNAME, as the Runners
    panel does.
"""
import collections
import hmac
import http.server
import json
import os
import signal
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import events  # noqa: E402

LOG_FILE = os.environ.get("AUDIT_FILE", "/logs/audit.log")
BAO_ADDR = os.environ.get("BAO_ADDR", "http://openbao:8200")
PER_NAMESPACE = 3000
ALL = 10000
MAX_LIMIT = 1000
GATEWAY_TOKEN = os.environ.get("GATEWAY_TOKEN", "")
FACILITATOR = os.environ.get("FACILITATOR_USERNAME", "root")
HERE = os.path.dirname(os.path.abspath(__file__))
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
                               "img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'",
    "X-Frame-Options": "SAMEORIGIN",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}
STATIC = {"/": ("panel.html", "text/html; charset=utf-8"),
          "/panel.js": ("panel.js", "text/javascript; charset=utf-8"),
          "/panel.css": ("panel.css", "text/css; charset=utf-8")}

reporter = events.Reporter(os.environ.get("ACHIEVEMENTS_ADAPTER_URL", ""),
                           os.environ.get("ACHIEVEMENTS_ADAPTER_SECRET", ""))
lock = threading.Lock()
by_ns = collections.defaultdict(lambda: collections.deque(maxlen=PER_NAMESPACE))
everything = collections.deque(maxlen=ALL)


def log(msg):
    print(f"[openbao-audit] {msg}", flush=True)


def compact(entry):
    req = entry.get("request") or {}
    auth = entry.get("auth") or {}
    resp = entry.get("response") or {}
    out = {
        "time": entry.get("time"),
        "namespace": ((req.get("namespace") or {}).get("path") or "").rstrip("/"),
        "operation": req.get("operation"),
        "path": req.get("path"),
        "remote_address": req.get("remote_address"),
        "accessor": auth.get("accessor"),
        "display_name": auth.get("display_name"),
        "policies": auth.get("policies"),
        "token_type": auth.get("token_type"),
        "error": entry.get("error") or None,
    }
    new_auth = resp.get("auth") or {}
    if new_auth.get("accessor"):
        out["created_accessor"] = new_auth["accessor"]
    return out


read_lock = threading.Lock()
tail = {"pos": 0, "inode": None}


def catch_up():
    """Read what the audit file gained since last time, reopening it if it
    was replaced. Called every second and before each answer, so a query sees
    the request made just before it."""
    with read_lock:
        try:
            st = os.stat(LOG_FILE)
            if st.st_ino != tail["inode"] or st.st_size < tail["pos"]:
                tail["pos"], tail["inode"] = 0, st.st_ino
            if st.st_size <= tail["pos"]:
                return
            with open(LOG_FILE, "rb") as f:
                f.seek(tail["pos"])
                data = f.read(st.st_size - tail["pos"])
        except OSError:
            return
        end = data.rfind(b"\n") + 1  # leave a half-written line for next time
        tail["pos"] += end
        for line in data[:end].splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get("type") != "response":
                continue
            reporter.entry(entry)
            c = compact(entry)
            with lock:
                everything.append(c)
                by_ns[c["namespace"]].append(c)


def follow():
    while True:
        catch_up()
        time.sleep(1)


def capabilities(token, paths):
    body = json.dumps({"paths": paths}).encode()
    req = urllib.request.Request(f"{BAO_ADDR}/v1/sys/capabilities-self", data=body, method="POST",
                                 headers={"X-Vault-Token": token, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        doc = json.load(r)
    return {p: doc.get(p) or (doc.get("data") or {}).get(p) or [] for p in paths}


def allowed(token, ns):
    """(True, "") if this token administers namespace ns, or reads every
    namespace's audit trail; else (False, why)."""
    if not token:
        return False, "send your vault token as X-Vault-Token"
    probe = f"{ns}/sys/policies/acl/audit-probe" if ns else "sys/policies/acl/audit-probe"
    try:
        caps = capabilities(token, ["sys/audit", probe])
    except urllib.error.HTTPError as e:
        return False, f"OpenBao refused the token ({e.code})"
    except OSError as e:
        return False, f"could not ask OpenBao: {e}"
    if "sudo" in caps["sys/audit"] or "root" in caps["sys/audit"]:
        return True, ""
    if ns and "update" in caps[probe]:
        return True, ""
    return False, f"your token doesn't administer {ns or 'the root namespace'}"


def of_student(e, name):
    """Is entry e about this student? Their namespace, or the root
    namespace's requests made by them or on their shared folder."""
    if e["namespace"] == f"students/{name}":
        return True
    if e["namespace"]:
        return False
    return name in (e["display_name"] or "") or f"students/{name}/" in (e["path"] or "")


def panel_query(q):
    """The Audit tab's query: newest first, capped."""
    try:
        limit = max(1, min(MAX_LIMIT, int(q.get("limit", "200"))))
    except ValueError:
        limit = 200
    student, accessor = q.get("student", "*"), q.get("accessor")
    path, op, errors = q.get("path"), q.get("op"), q.get("errors") == "1"
    catch_up()
    with lock:
        source = list(everything)
        namespaces = sorted(n for n in by_ns if n)
    out = []
    for e in reversed(source):
        if student != "*" and not of_student(e, student):
            continue
        if accessor and accessor not in (e["accessor"], e.get("created_accessor")):
            continue
        if path and not (e["path"] or "").startswith(path):
            continue
        if op and e["operation"] != op:
            continue
        if errors and not e["error"]:
            continue
        out.append(e)
        if len(out) >= limit:
            break
    students = [n.split("/", 1)[1] for n in namespaces if n.startswith("students/")]
    return {"entries": out, "students": students, "total": len(source)}


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "openbao-audit"
    sys_version = ""

    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, doc):
        self._send(code, json.dumps(doc).encode(), "application/json")

    def _facilitator(self):
        given = self.headers.get("X-Gateway-Token") or ""
        if not GATEWAY_TOKEN or not hmac.compare_digest(given.encode(), GATEWAY_TOKEN.encode()):
            return False
        return self.headers.get("X-Auth-User") == FACILITATOR

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        if url.path == "/healthz":
            return self._json(200, {"ok": True})
        if url.path in STATIC or url.path == "/api/entries":
            if not self._facilitator():
                return self._json(403, {"error": "facilitator only"})
            if url.path in STATIC:
                fname, ctype = STATIC[url.path]
                with open(os.path.join(HERE, fname), "rb") as f:
                    return self._send(200, f.read(), ctype)
            q = {k: v[-1] for k, v in urllib.parse.parse_qs(url.query).items()}
            return self._json(200, panel_query(q))
        if url.path != "/entries":
            return self._json(404, {"error": "not found"})
        q = {k: v[-1] for k, v in urllib.parse.parse_qs(url.query).items()}
        token = self.headers.get("X-Vault-Token", "")
        ns = q.get("ns", "").strip("/")
        ok, why = allowed(token, "" if ns == "*" else ns)
        if not ok:
            return self._json(403, {"error": why})
        try:
            limit = max(1, min(MAX_LIMIT, int(q.get("limit", "100"))))
        except ValueError:
            limit = 100
        accessor, path = q.get("accessor"), q.get("path")
        catch_up()
        with lock:
            source = list(everything if ns == "*" else by_ns.get(ns, ()))
        out = [e for e in source
               if (not accessor or e["accessor"] == accessor or e.get("created_accessor") == accessor)
               and (not path or (e["path"] or "").startswith(path))]
        self._json(200, {"namespace": ns, "entries": out[-limit:]})


def main():
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    catch_up()              # what was logged before we started is history: not reported
    reporter.live = True
    reporter.start()
    threading.Thread(target=follow, daemon=True).start()
    server = http.server.ThreadingHTTPServer(("0.0.0.0", 8080), Handler)
    server.daemon_threads = True
    log(f"following {LOG_FILE}")
    server.serve_forever()


if __name__ == "__main__":
    main()
