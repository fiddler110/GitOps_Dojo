"""Unit tests for ctf-flags' verify logic and HTTP handler (no daemon needed):

    python3 -B -m unittest discover -s modules/ctf-range/ctf-flags/tests -p 'test_*.py'
"""
import http.client
import json
import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import flags  # noqa: E402
import service as svc  # noqa: E402

SEED = "range-seed"


class FakeAdapter:
    def __init__(self):
        self.posted = []
        self.enabled = True

    def post(self, doc):
        self.posted.append(doc)
        return True


class TestVerify(unittest.TestCase):
    def setUp(self):
        self.cfg = svc.Config(env={"STUDENT_PASSWORD_SEED": SEED})

    def test_right_flag_verifies(self):
        flag = flags.render("student07", SEED, "sqli-login")
        self.assertTrue(svc.verify(self.cfg, "student07", "sqli-login", flag))

    def test_wrong_flag_fails(self):
        self.assertFalse(svc.verify(self.cfg, "student07", "sqli-login", "flag{nope}"))

    def test_another_students_flag_fails(self):
        theirs = flags.render("student08", SEED, "sqli-login")
        self.assertFalse(svc.verify(self.cfg, "student07", "sqli-login", theirs))

    def test_right_flag_wrong_challenge_fails(self):
        flag = flags.render("student07", SEED, "sqli-login")
        self.assertFalse(svc.verify(self.cfg, "student07", "idor-pcap", flag))

    def test_no_seed_dev_flag(self):
        cfg = svc.Config(env={})
        flag = flags.render("student07", "", "sqli-login")
        self.assertTrue(svc.verify(cfg, "student07", "sqli-login", flag))


class TestHTTP(unittest.TestCase):
    def setUp(self):
        self.cfg = svc.Config(env={"STUDENT_PASSWORD_SEED": SEED})
        self.adapter = FakeAdapter()
        self.srv = svc.Server(("127.0.0.1", 0), svc.make_handler(self.cfg, self.adapter))
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def _req(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        payload = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"} if payload else {}
        conn.request(method, path, body=payload, headers=headers)
        resp = conn.getresponse()
        out = (resp.status, json.loads(resp.read() or b"{}"))
        conn.close()
        return out

    def test_healthz_open(self):
        self.assertEqual(self._req("GET", "/healthz"), (200, {"ok": True}))

    def test_submit_right_flag(self):
        flag = flags.render("student07", SEED, "sqli-login")
        status, doc = self._req("POST", "/submit",
                                body={"user": "student07", "challenge": "sqli-login", "flag": flag})
        self.assertEqual((status, doc), (200, {"ok": True}))
        self.assertEqual(self.adapter.posted,
                         [{"source": "ctf", "event": "flag_solved", "user": "student07", "challenge": "sqli-login"}])

    def test_submit_wrong_flag_never_errors(self):
        status, doc = self._req("POST", "/submit",
                                body={"user": "student07", "challenge": "sqli-login", "flag": "flag{nope}"})
        self.assertEqual((status, doc), (200, {"ok": False}))
        self.assertEqual(self.adapter.posted, [])

    def test_submit_malformed_body_never_errors(self):
        for body in ({}, {"user": "student07"}, {"user": "", "challenge": "x", "flag": "y"}, []):
            status, doc = self._req("POST", "/submit", body=body)
            self.assertEqual((status, doc), (200, {"ok": False}))

    def test_unknown_route_404(self):
        self.assertEqual(self._req("GET", "/nope")[0], 404)


if __name__ == "__main__":
    unittest.main()
