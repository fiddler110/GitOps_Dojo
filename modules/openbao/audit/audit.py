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
"""
import collections
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

LOG_FILE = os.environ.get("AUDIT_FILE", "/logs/audit.log")
BAO_ADDR = os.environ.get("BAO_ADDR", "http://openbao:8200")
PER_NAMESPACE = 3000
ALL = 10000
MAX_LIMIT = 1000

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


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "openbao-audit"
    sys_version = ""

    def log_message(self, fmt, *args):
        pass

    def _json(self, code, doc):
        body = json.dumps(doc).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        if url.path == "/healthz":
            return self._json(200, {"ok": True})
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
    threading.Thread(target=follow, daemon=True).start()
    server = http.server.ThreadingHTTPServer(("0.0.0.0", 8080), Handler)
    server.daemon_threads = True
    log(f"following {LOG_FILE}")
    server.serve_forever()


if __name__ == "__main__":
    main()
