"""Site Inspector against real local servers: plain HTTP and TLS with a throwaway certificate as the lab CA.
Run: python3 -B -m unittest test_server   (needs openssl on the PATH to make the certificates)
"""
import http.server
import json
import os
import shutil
import ssl
import subprocess
import tempfile
import threading
import unittest
import urllib.request

import server

NAMES = ("amy.certs.dojo.test", "www.amy.certs.dojo.test", "api.amy.certs.dojo.test")


def make_cert(directory, name):
    key, crt = os.path.join(directory, name + ".key"), os.path.join(directory, name + ".crt")
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", key, "-out", crt,
                    "-days", "1", "-subj", f"/CN={NAMES[0]}",
                    "-addext", "subjectAltName=" + ",".join("DNS:" + n for n in NAMES)],
                   check=True, capture_output=True)
    return key, crt


class Site(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        key, crt = make_cert(cls.tmp, "site")
        cls.other = make_cert(cls.tmp, "other")[1]
        cls.crt = crt
        answers, seen = cls.answers, cls.seen = {}, []

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                tls = isinstance(self.connection, ssl.SSLSocket)
                seen.append((self.headers["Host"], tls, self.path))
                status, headers, body = answers.get((self.headers["Host"], tls), (404, {}, b"nope"))
                self.send_response(status)
                for k, v in headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass
        cls.servers = []
        for tls in (False, True):
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
            srv.handle_error = lambda *a: None      # the TLS-version probes hang up without a request
            if tls:
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ctx.load_cert_chain(crt, key)
                srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            cls.servers.append(srv)

    @classmethod
    def tearDownClass(cls):
        for srv in cls.servers:
            srv.shutdown()
            srv.server_close()
        shutil.rmtree(cls.tmp)

    def setUp(self):
        self.saved = (server.TARGET, server.HTTP_PORT, server.TLS_PORT, server.CA_ROOT, server.ZONE,
                      server.FACILITATOR)
        server.TARGET, server.ZONE, server.FACILITATOR = "127.0.0.1", "certs.dojo.test", "root"
        server.HTTP_PORT, server.TLS_PORT = self.servers[0].server_port, self.servers[1].server_port
        server.CA_ROOT = self.crt
        server._hsts.clear()
        server._pages.clear()
        self.answers.clear()
        self.seen.clear()

    def tearDown(self):
        (server.TARGET, server.HTTP_PORT, server.TLS_PORT, server.CA_ROOT, server.ZONE,
         server.FACILITATOR) = self.saved

    def https_only(self, host, hsts="max-age=86400"):
        self.answers[(host, False)] = (301, {"Location": f"https://{host}/"}, b"")
        headers = {"Content-Type": "text/html", "X-Content-Type-Options": "nosniff"}
        if hsts:
            headers["Strict-Transport-Security"] = hsts
        self.answers[(host, True)] = (200, headers, f"<h1>{host}</h1>".encode())

    # -- names ---------------------------------------------------------------------------
    def test_who_may_visit_what(self):
        self.assertTrue(server.may_visit("amy", "amy.certs.dojo.test"))
        self.assertTrue(server.may_visit("amy", "www.amy.certs.dojo.test"))
        self.assertFalse(server.may_visit("amy", "bob.certs.dojo.test"))
        self.assertFalse(server.may_visit("amy", "xamy.certs.dojo.test"))
        self.assertFalse(server.may_visit("amy", "allocator"))
        self.assertTrue(server.may_visit("root", "bob.certs.dojo.test"))
        self.assertFalse(server.may_visit("root", "example.com"))

    def test_addresses(self):
        self.assertEqual(server.parse_target("amy.certs.dojo.test"), (None, "amy.certs.dojo.test", "/"))
        self.assertEqual(server.parse_target("https://Amy.certs.dojo.test/a?b=1"),
                         ("https", "amy.certs.dojo.test", "/a?b=1"))
        for bad in ("ftp://amy.certs.dojo.test/", "amy.certs.dojo.test:8080", "http://x@amy.certs.dojo.test/",
                    "", "not a host", "http://amy.certs.dojo.test/a b"):
            with self.assertRaises(ValueError, msg=bad):
                server.parse_target(bad)

    def test_only_own_names(self):
        with self.assertRaises(PermissionError):
            server.visit("amy", "bob.certs.dojo.test")

    # -- visits --------------------------------------------------------------------------
    def test_redirect_then_hsts_then_skip_http(self):
        host = NAMES[0]
        self.https_only(host)
        r = server.visit("amy", host)
        self.assertEqual([h["status"] for h in r["hops"]], [301, 200])
        self.assertEqual(r["hops"][0]["url"], f"http://{host}/")
        tls = r["hops"][1]["tls"]
        self.assertTrue(tls["verified"])
        self.assertIn(host, tls["cert"]["names"])
        self.assertIn("TLSv1.3", tls["protocols"])
        self.assertIsNone(r["stopped"])
        self.assertEqual([e["host"] for e in r["hsts"]], [host])
        sec = {s["name"]: s for s in r["final"]["security"]}
        self.assertTrue(sec["Strict-Transport-Security"]["ok"])
        self.assertTrue(sec["X-Content-Type-Options"]["ok"])
        self.assertFalse(sec["Content-Security-Policy"]["ok"])
        self.assertIn(f"<h1>{host}</h1>", r["final"]["source"])
        # The second visit never touches port 80: HSTS upgrades it first.
        self.seen.clear()
        r = server.visit("amy", host)
        self.assertEqual(r["hops"][0]["kind"], "hsts")
        self.assertEqual([s[1] for s in self.seen], [True])
        # ... for that viewer only.
        self.seen.clear()
        server.visit("root", host)
        self.assertEqual([s[1] for s in self.seen], [False, True])

    def test_hsts_max_age_zero_forgets(self):
        host = NAMES[1]
        self.https_only(host)
        server.visit("amy", host)
        self.https_only(host, hsts="max-age=0")
        r = server.visit("amy", f"https://{host}/")
        self.assertEqual(r["hsts"], [])

    def test_hsts_over_http_is_ignored(self):
        host = NAMES[0]
        self.answers[(host, False)] = (200, {"Strict-Transport-Security": "max-age=86400"}, b"hi")
        r = server.visit("amy", host)
        self.assertIn("ignored", r["hops"][0]["note"])
        self.assertEqual(r["hsts"], [])
        sec = {s["name"]: s for s in r["final"]["security"]}
        self.assertFalse(sec["Strict-Transport-Security"]["ok"])
        self.assertIn("(plain HTTP)", sec)

    def test_untrusted_certificate_stops_like_a_browser(self):
        host = NAMES[0]
        self.https_only(host)
        server.CA_ROOT = self.other
        r = server.visit("amy", f"https://{host}/")
        hop = r["hops"][0]
        self.assertFalse(hop["tls"]["verified"])
        self.assertIn("browser stops", r["stopped"])
        self.assertEqual(hop["tls"]["cert"]["subject"], host)
        self.assertIsNone(r["final"])
        self.assertEqual(self.seen, [])            # no request was sent over the untrusted connection
        self.assertEqual(r["hsts"], [])

    def test_redirects_off_your_names_are_not_followed(self):
        host = NAMES[0]
        self.answers[(host, False)] = (302, {"Location": "http://bob.certs.dojo.test/"}, b"")
        r = server.visit("amy", host)
        self.assertIn("not one of your names", r["stopped"])
        self.answers[(host, False)] = (301, {"Location": "http://amy.certs.dojo.test:8080/"}, b"")
        self.assertIn("not followed", server.visit("amy", host)["stopped"])
        self.answers[(host, False)] = (301, {"Location": "/"}, b"")
        self.assertIn("itself", server.visit("amy", host)["stopped"])

    def test_temporary_redirect_and_relative_location(self):
        host = NAMES[2]
        self.answers[(host, False)] = (302, {"Location": "https://api.amy.certs.dojo.test/home"}, b"")
        self.answers[(host, True)] = (200, {"Content-Type": "text/plain"}, b"api")
        r = server.visit("amy", host)
        self.assertEqual([h["status"] for h in r["hops"]], [302, 200])
        self.assertEqual(self.seen[-1], (host, True, "/home"))

    def test_nothing_listening(self):
        server.TLS_PORT = 1
        r = server.visit("amy", f"https://{NAMES[0]}/")
        self.assertIn("couldn't connect", r["stopped"])


class Http(unittest.TestCase):
    """The HTTP surface: the gateway token, the page store and the forget button."""
    @classmethod
    def setUpClass(cls):
        server.GATEWAY_TOKEN = "t" * 64
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def call(self, path, user="amy", token="t" * 64, method="GET", headers=None):
        h = dict(headers or {})
        if token:
            h["X-Gateway-Token"] = token
        if user:
            h["X-Auth-User"] = user
        req = urllib.request.Request(self.base + path, method=method, headers=h, data=b"" if method == "POST" else None)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def test_token_required(self):
        self.assertEqual(self.call("/api/me", token="x" * 64)[0], 403)
        self.assertEqual(self.call("/api/me", token=None)[0], 403)
        self.assertEqual(self.call("/healthz", token=None)[0], 200)
        status, headers, body = self.call("/api/me")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["suggestions"][0], "amy.certs.dojo.test")

    def test_page_is_sandboxed_and_private(self):
        page = server.keep_page("amy", "text/html", b"<script>alert(1)</script>")
        status, headers, body = self.call(f"/api/page/{page}")
        self.assertEqual(status, 200)
        self.assertTrue(headers["Content-Security-Policy"].startswith("sandbox"))
        self.assertEqual(self.call(f"/api/page/{page}", user="bob")[0], 404)

    def test_static_has_csp(self):
        status, headers, body = self.call("/")
        self.assertEqual(status, 200)
        self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(self.call("/static/../server.py")[0], 404)

    def test_forget_needs_the_header(self):
        server._hsts["amy"] = {"amy.certs.dojo.test": 9e18}
        self.assertEqual(self.call("/api/forget", method="POST")[0], 404)
        self.assertIn("amy", server._hsts)
        self.assertEqual(self.call("/api/forget", method="POST", headers={"X-Requested-With": "inspector"})[0], 200)
        self.assertNotIn("amy", server._hsts)

    def test_bad_address_is_a_400(self):
        status, _, body = self.call("/api/visit?url=ftp%3A%2F%2Fx")
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
