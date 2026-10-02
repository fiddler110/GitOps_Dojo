"""dojo_http: the gateway-token check and the shared replies."""
import io
import unittest

import dojo_http

TOKEN = "s3cret"


class Trust(unittest.TestCase):
    def test_token_fails_closed(self):
        self.assertTrue(dojo_http.token_ok(TOKEN, TOKEN))
        for given, expected in (("", ""), ("", TOKEN), (TOKEN, ""), ("wrong", TOKEN), ("é", TOKEN)):
            self.assertFalse(dojo_http.token_ok(given, expected), (given, expected))

    def test_identity_needs_the_token(self):
        self.assertEqual(dojo_http.gateway_user({"X-Gateway-Token": TOKEN, "X-Auth-User": "student01"}, TOKEN),
                         "student01")
        self.assertIsNone(dojo_http.gateway_user({"X-Auth-User": "root"}, TOKEN))
        self.assertIsNone(dojo_http.gateway_user({"X-Gateway-Token": "x", "X-Auth-User": "root"}, TOKEN))
        self.assertIsNone(dojo_http.gateway_user({"X-Gateway-Token": "", "X-Auth-User": "root"}, ""))
        self.assertIsNone(dojo_http.gateway_user({"X-Gateway-Token": TOKEN}, TOKEN))

    def test_facilitator(self):
        fac = {"X-Gateway-Token": TOKEN, "X-Auth-User": "root"}
        self.assertTrue(dojo_http.is_facilitator(fac, TOKEN, "root"))
        self.assertFalse(dojo_http.is_facilitator(fac, TOKEN, "admin"))
        self.assertFalse(dojo_http.is_facilitator({"X-Auth-User": "root"}, TOKEN, "root"))
        self.assertFalse(dojo_http.is_facilitator({"X-Gateway-Token": TOKEN}, TOKEN, ""))


class FakeHandler:
    def __init__(self, command="GET"):
        self.command, self.wfile, self.sent = command, io.BytesIO(), []

    def send_response(self, status):
        self.sent.append(("status", status))

    def send_header(self, k, v):
        self.sent.append((k, v))

    def end_headers(self):
        self.sent.append(("end", None))


class Replies(unittest.TestCase):
    def test_send_json(self):
        h = FakeHandler()
        dojo_http.send_json(h, 200, {"ok": True})
        sent = dict(h.sent)
        self.assertEqual(h.wfile.getvalue(), b'{"ok": true}')
        self.assertEqual((sent["status"], sent["Content-Type"], sent["Content-Length"]), (200, "application/json", "12"))
        for k, v in dojo_http.SECURITY_HEADERS.items():
            self.assertEqual(sent[k], v)

    def test_head_sends_headers_only(self):
        h = FakeHandler("HEAD")
        dojo_http.send(h, 200, b"<p>page</p>", "text/html", {"Cache-Control": "no-cache"})
        self.assertEqual(h.wfile.getvalue(), b"")
        self.assertEqual(dict(h.sent)["Content-Length"], "11")
        self.assertEqual([v for k, v in h.sent if k == "Cache-Control"], ["no-cache"])  # overridden, not repeated

    def test_headers_override_leaves_the_default_alone(self):
        self.assertEqual(dojo_http.headers({"Referrer-Policy": "same-origin"})["Referrer-Policy"], "same-origin")
        self.assertEqual(dojo_http.SECURITY_HEADERS["Referrer-Policy"], "no-referrer")


if __name__ == "__main__":
    unittest.main()
