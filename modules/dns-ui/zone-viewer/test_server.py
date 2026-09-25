"""Tests for the zone viewer against an in-process fake PowerDNS API. No containers."""

import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import server

KEY = "k"
ZONE = {
    "id": "dojo.test.", "name": "dojo.test.", "serial": 7,
    "rrsets": [
        {"name": "www.dojo.test.", "type": "A", "ttl": 300, "records": [{"content": "203.0.113.10", "disabled": False}]},
        {"name": "dojo.test.", "type": "TXT", "ttl": 300, "records": [{"content": "\"<b>hi</b>\"", "disabled": False}]},
        {"name": "dojo.test.", "type": "A", "ttl": 300, "records": [{"content": "203.0.113.10", "disabled": False}]},
        {"name": "a.www.dojo.test.", "type": "A", "ttl": 60, "records": [{"content": "203.0.113.11", "disabled": True}]},
        {"name": "mail.dojo.test.", "type": "A", "ttl": 300, "records": [{"content": "203.0.113.20", "disabled": False}]},
    ],
}


class FakePDNS(BaseHTTPRequestHandler):
    zones = {"dojo.test.": ZONE}

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.headers.get("X-API-Key") != KEY:
            self.send_response(401); self.end_headers(); return
        base = "/api/v1/servers/localhost/zones"
        if self.path == base:
            body = [{"id": z["id"], "name": z["name"]} for z in self.zones.values()]
        elif self.path.startswith(base + "/") and self.path[len(base) + 1:] in self.zones:
            body = self.zones[self.path[len(base) + 1:]]
        else:
            self.send_response(404); self.end_headers(); return
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def serve(handler):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


class ZoneViewerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdns, cls.pdns_url = serve(FakePDNS)

    @classmethod
    def tearDownClass(cls):
        cls.pdns.shutdown()

    def start_viewer(self, api_url, key=KEY):
        poller = server.Poller(api_url, key, 60)
        handler = type("H", (server.Handler,), {"poller": poller})
        httpd, url = serve(handler)
        self.addCleanup(httpd.shutdown)
        return poller, url

    def test_records_sorted_apex_first_then_by_reversed_name(self):
        rows = server.zone_records(ZONE)
        self.assertEqual([(r["name"], r["type"]) for r in rows], [
            ("dojo.test.", "A"), ("dojo.test.", "TXT"), ("mail.dojo.test.", "A"),
            ("www.dojo.test.", "A"), ("a.www.dojo.test.", "A")])
        self.assertTrue(rows[-1]["disabled"])

    def test_not_ready_until_first_poll(self):
        poller, url = self.start_viewer(self.pdns_url)
        self.assertEqual(get(url + "/readyz")[0], 503)
        self.assertIsNone(json.loads(get(url + "/api/zones")[2])["zones"])
        poller.poll_once()
        self.assertEqual(get(url + "/readyz")[0], 200)
        snap = json.loads(get(url + "/api/zones")[2])
        self.assertEqual(snap["zones"][0]["name"], "dojo.test.")
        self.assertEqual(snap["zones"][0]["serial"], 7)
        self.assertEqual(len(snap["zones"][0]["records"]), 5)

    def test_error_keeps_last_good_zones(self):
        poller, url = self.start_viewer(self.pdns_url)
        poller.poll_once()
        poller.api_key = "wrong"
        poller.poll_once()
        snap = json.loads(get(url + "/api/zones")[2])
        self.assertIsNotNone(snap["error"])
        self.assertEqual(len(snap["zones"]), 1)
        self.assertEqual(get(url + "/readyz")[0], 503)

    def test_unreachable_pdns(self):
        poller, url = self.start_viewer("http://127.0.0.1:9")
        poller.poll_once()
        snap = json.loads(get(url + "/api/zones")[2])
        self.assertIsNone(snap["zones"])
        self.assertIn("not answering", snap["error"])

    def test_static_allow_list_and_headers(self):
        _, url = self.start_viewer(self.pdns_url)
        for path, ctype in [("/", "text/html"), ("/static/app.js", "text/javascript"),
                            ("/static/app.css", "text/css"), ("/static/favicon.svg", "image/svg+xml")]:
            status, headers, _ = get(url + path)
            self.assertEqual(status, 200, path)
            self.assertTrue(headers["Content-Type"].startswith(ctype), path)
            self.assertIn("frame-ancestors 'self'", headers["Content-Security-Policy"])
            self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
            self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        for path in ["/static/../server.py", "/server.py", "/static/", "/static/test_server.py", "/index.html"]:
            self.assertEqual(get(url + path)[0], 404, path)

    def test_path_prefix(self):
        _, url = self.start_viewer(self.pdns_url)
        server.PREFIX = "/dns"
        self.addCleanup(setattr, server, "PREFIX", "")
        req = urllib.request.Request(url + "/dns", method="GET")
        opener = urllib.request.build_opener(type("NoRedirect", (urllib.request.HTTPRedirectHandler,),
                                                  {"redirect_request": lambda *a: None}))
        with self.assertRaises(urllib.error.HTTPError) as cm:
            opener.open(req, timeout=5)
        self.assertEqual(cm.exception.code, 308)
        self.assertEqual(cm.exception.headers["Location"], "/dns/")
        self.assertEqual(get(url + "/dns/")[0], 200)
        self.assertEqual(get(url + "/dns/static/app.js")[0], 200)
        self.assertEqual(get(url + "/dns/healthz")[0], 200)
        for path in ["/", "/static/app.js", "/dnsx/", "/dnsstatic/app.js"]:
            self.assertEqual(get(url + path)[0], 404, path)

    def test_app_js_never_uses_innerhtml(self):
        with open(server.os.path.join(server.STATIC_DIR, "app.js")) as f:
            src = "\n".join(l for l in f if not l.lstrip().startswith("//"))
        self.assertNotIn("innerHTML", src)
        self.assertNotIn("insertAdjacentHTML", src)


if __name__ == "__main__":
    unittest.main()
