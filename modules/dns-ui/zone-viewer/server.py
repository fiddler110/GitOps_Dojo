"""Read-only view of every zone on the workshop's PowerDNS (dns-server).

One background thread polls the PowerDNS HTTP API every POLL_SECONDS and keeps
the latest snapshot; requests only read that snapshot, so a class polling the
page every few seconds costs PowerDNS one zone list per interval, not one per
student. Stdlib only.

Routes, all under PATH_PREFIX (/dns; the gateway passes the path through
unstripped so a bare /dns can be redirected to /dns/, where the page's
relative asset links resolve):
  GET /                 the page (index.html)
  GET /static/<file>    allow-listed assets
  GET /api/zones        the snapshot as JSON
  GET /healthz          200 while the process is up
  GET /readyz           200 once a poll has succeeded (the /admin status strip)

Nothing here is secret or per-student: it is the same data `dig` returns, so the
route uses the gateway's `shared` gate and carries no identity.
"""

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
# dojo_http: modules/_shared/ in the source tree, ./_shared/ once ./dojo has copied it (SHARED= in module.env).
sys.path[:0] = [os.path.join(HERE, "..", "..", "_shared"), os.path.join(HERE, "_shared")]
import dojo_http  # noqa: E402

PREFIX = os.environ.get("PATH_PREFIX", "").rstrip("/")
STATIC_DIR = os.environ.get("STATIC_DIR", os.path.join(HERE, "static"))
# Fixed allow-list: request path -> (file in STATIC_DIR, Content-Type). Nothing else is served.
FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/static/app.css": ("app.css", "text/css; charset=utf-8"),
    "/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/static/favicon.svg": ("favicon.svg", "image/svg+xml"),
}


def fetch_json(url, api_key, timeout=5):
    req = urllib.request.Request(url, headers={"X-API-Key": api_key, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def zone_records(zone):
    """Flatten a PowerDNS zone document into sorted record rows."""
    rows = []
    for rrset in zone.get("rrsets", []):
        for rec in rrset.get("records", []):
            rows.append({
                "name": rrset.get("name", ""),
                "type": rrset.get("type", ""),
                "ttl": rrset.get("ttl"),
                "content": rec.get("content", ""),
                "disabled": bool(rec.get("disabled")),
            })
    apex = zone.get("name", "")
    # Apex first, then by name read right to left (so www.a and mail.a group under a), then type.
    rows.sort(key=lambda r: (r["name"] != apex, list(reversed(r["name"].split("."))), r["type"], r["content"]))
    return rows


def take_snapshot(api_url, api_key, server_id="localhost"):
    base = f"{api_url.rstrip('/')}/api/v1/servers/{urllib.parse.quote(server_id, safe='')}/zones"
    zones = []
    for z in sorted(fetch_json(base, api_key), key=lambda z: z.get("name", "")):
        doc = fetch_json(f"{base}/{urllib.parse.quote(z['id'], safe='')}", api_key)
        zones.append({"name": doc.get("name", z.get("name", "")), "serial": doc.get("serial"),
                      "records": zone_records(doc)})
    return zones


class Poller:
    def __init__(self, api_url, api_key, interval):
        self.api_url, self.api_key, self.interval = api_url, api_key, interval
        self._lock = threading.Lock()
        # zones is None until the first poll succeeds; error is the last poll's failure, if any.
        self._state = {"zones": None, "updated": None, "error": None}

    def snapshot(self):
        with self._lock:
            return dict(self._state)

    def poll_once(self):
        # The HTTP calls happen outside the lock; only the swap is locked.
        try:
            zones = take_snapshot(self.api_url, self.api_key)
            update = {"zones": zones, "updated": time.time(), "error": None}
        except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
            update = {"error": f"PowerDNS is not answering ({exc.__class__.__name__})"}
        with self._lock:
            self._state.update(update)

    def run(self):
        while True:
            self.poll_once()
            time.sleep(self.interval)


class Handler(BaseHTTPRequestHandler):
    poller = None
    server_version = "zone-viewer"
    sys_version = ""

    def log_message(self, fmt, *args):
        pass  # polled every few seconds by every student; keep the container log quiet

    def _send(self, status, body, ctype):
        dojo_http.send(self, status, body, ctype)

    def _json(self, status, obj):
        dojo_http.send_json(self, status, obj)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path or "/"
        if PREFIX:
            if path == PREFIX:
                self.send_response(308)
                self.send_header("Location", PREFIX + "/")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if not path.startswith(PREFIX + "/"):
                return self._json(404, {"error": "not found"})
            path = path[len(PREFIX):]
        if path == "/healthz":
            return self._json(200, {"ok": True})
        snap = self.poller.snapshot()
        if path == "/readyz":
            ready = snap["zones"] is not None and snap["error"] is None
            return self._json(200 if ready else 503, {"ready": ready, "error": snap["error"]})
        if path == "/api/zones":
            return self._json(200, snap)
        if path in FILES:
            name, ctype = FILES[path]
            try:
                with open(os.path.join(STATIC_DIR, name), "rb") as f:
                    body = f.read()
            except OSError:
                return self._json(404, {"error": "not found"})
            return self._send(200, body, ctype)
        return self._json(404, {"error": "not found"})


def main():
    poller = Poller(os.environ.get("PDNS_API_URL", "http://dns-server:8081"),
                    os.environ.get("POWERDNS_API_KEY", "workshop-not-a-secret"),
                    float(os.environ.get("POLL_SECONDS", "2")))
    threading.Thread(target=poller.run, daemon=True).start()
    Handler.poller = poller
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), Handler).serve_forever()


if __name__ == "__main__":
    main()
