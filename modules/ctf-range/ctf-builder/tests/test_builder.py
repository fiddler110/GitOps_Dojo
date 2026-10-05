"""Unit tests for builder's validation, auth and HTTP control API (no git, no
daemon, no real ctf-host needed — a FakeExecutor stands in):

    python3 -B -m unittest discover -s modules/ctf-range/ctf-builder/tests -p 'test_*.py'
"""
import http.client
import json
import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import builder as b  # noqa: E402

TOKEN = "build-secret"


class FakeExecutor:
    """Never actually called in these tests: every request here is refused
    (auth, bad user/ref, oversized body) before do_build touches the
    executor, same scope as ctf-controller's test style for pure functions."""

    def ping(self):
        return True

    def build(self, *a, **k):  # pragma: no cover - not reached in these tests
        raise AssertionError("build() should not be called")

    def push(self, *a, **k):  # pragma: no cover
        raise AssertionError("push() should not be called")


def make_config(**overrides):
    env = {"CTF_BUILD_TOKEN": TOKEN, "CTF_REGISTRY": "registry:5000"}
    env.update(overrides)
    return b.Config(env=env)


class TestDoBuildValidation(unittest.TestCase):
    """do_build validates before touching git or the executor at all."""

    def test_no_registry_configured(self):
        cfg = make_config(CTF_REGISTRY="")
        ok, msg = b.do_build(cfg, FakeExecutor(), "student01", "main")
        self.assertFalse(ok)
        self.assertIn("registry", msg)

    def test_bad_user_rejected(self):
        cfg = make_config()
        ok, msg = b.do_build(cfg, FakeExecutor(), "../etc", "main")
        self.assertFalse(ok)
        self.assertEqual(msg, "bad user")

    def test_bad_ref_rejected(self):
        cfg = make_config()
        ok, msg = b.do_build(cfg, FakeExecutor(), "student01", "--upload-pack=x")
        self.assertFalse(ok)
        self.assertEqual(msg, "bad ref")


class TestHTTP(unittest.TestCase):
    def setUp(self):
        self.cfg = make_config()
        self.ex = FakeExecutor()
        import threading as th
        self.srv = b.Server(("127.0.0.1", 0), b.make_handler(self.cfg, self.ex, th.Lock()))
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def _req(self, method, path, token=None, raw_body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {}
        if token:
            headers["Authorization"] = "Bearer " + token
        if raw_body is not None:
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=raw_body, headers=headers)
        resp = conn.getresponse()
        body = resp.read()
        try:
            doc = json.loads(body or b"{}")
        except ValueError:
            doc = None
        conn.close()
        return resp.status, doc

    def test_healthz_open_no_token(self):
        status, doc = self._req("GET", "/healthz")
        self.assertEqual(status, 200)
        self.assertTrue(doc["ok"])

    def test_build_requires_token(self):
        body = json.dumps({"user": "student01", "ref": "main"}).encode()
        self.assertEqual(self._req("POST", "/build", raw_body=body)[0], 403)
        self.assertEqual(self._req("POST", "/build", token="wrong", raw_body=body)[0], 403)

    def test_bad_ref_returns_400_not_500(self):
        body = json.dumps({"user": "student01", "ref": "-x"}).encode()
        status, doc = self._req("POST", "/build", token=TOKEN, raw_body=body)
        self.assertEqual(status, 400)
        self.assertEqual(doc["error"], "bad ref")

    def test_oversized_body_rejected(self):
        # MAX_BODY is 1024; pad well past it under a valid-looking ref so only
        # size, not content, is at fault.
        padding = "a" * (b.MAX_BODY + 200)
        body = json.dumps({"user": "student01", "ref": "main", "pad": padding}).encode()
        self.assertGreater(len(body), b.MAX_BODY)
        status, doc = self._req("POST", "/build", token=TOKEN, raw_body=body)
        self.assertEqual(status, 400)
        self.assertEqual(doc["error"], "bad request")

    def test_unknown_route_404(self):
        self.assertEqual(self._req("GET", "/nope")[0], 404)
        body = json.dumps({"user": "student01", "ref": "main"}).encode()
        self.assertEqual(self._req("POST", "/nope", token=TOKEN, raw_body=body)[0], 404)


if __name__ == "__main__":
    unittest.main()
