"""Unit tests for openbao-audit's achievements reporter (no stack needed):

    python3 -B -m unittest discover -s modules/openbao/tests -p 'test_*.py'
"""
import hashlib
import hmac
import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "audit"))
import events as ev  # noqa: E402


def entry(ns, op, path, policies=("default",), display="x", error=None, resp=None):
    return {"type": "response", "error": error,
            "request": {"namespace": {"path": ns + "/" if ns else ""}, "operation": op, "path": path},
            "auth": {"display_name": display, "policies": list(policies), "token_policies": list(policies)},
            "response": resp or {"data": {"k": "hmac-sha256:x"}}}


class Classify(unittest.TestCase):
    def test_login_success_takes_the_new_tokens_policies(self):
        e = entry("students/amy", "update", "auth/jwt-ci/login", ["default"], "",
                  resp={"auth": {"policies": ["default", "ci-read"], "display_name": "jwt-x"}})
        self.assertEqual(ev.classify(e), {"source": "bao", "event": "login", "user": "amy", "ok": True, "status": 200,
                                          "root": False, "op": "update", "path": "auth/jwt-ci/login",
                                          "mount": "jwt-ci", "role": "ci-read"})

    def test_failed_login(self):
        e = entry("students/amy", "update", "auth/jwt-ci/login", error="claim \"ref\" does not match", resp={"request_id": "1"})
        out = ev.classify(e)
        self.assertEqual((out["event"], out["ok"], out["status"], out["mount"]), ("login", False, 400, "jwt-ci"))
        self.assertNotIn("role", out)

    def test_root_namespace_oidc_login_is_attributed_by_display_name(self):
        e = entry("", "update", "auth/oidc/oidc/callback", resp={"auth": {"display_name": "oidc-student01",
                                                                          "policies": ["default"]}})
        out = ev.classify(e)
        self.assertEqual((out["user"], out["mount"], out["event"]), ("student01", "oidc", "login"))

    def test_root_namespace_without_a_student_name_is_skipped(self):
        self.assertIsNone(ev.classify(entry("", "read", "sys/policies/acl", display="root")))
        self.assertIsNone(ev.classify(entry("", "read", "secret/data/x", display="token")))

    def test_requests(self):
        out = ev.classify(entry("students/amy", "read", "team/data/app", ["default", "nightly-report"]))
        self.assertEqual((out["event"], out["role"], out["status"], out["root"]), ("request", "nightly-report", 200, False))
        denied = ev.classify(entry("students/amy", "read", "team/data/admin", error="1 error\n\t* permission denied"))
        self.assertEqual((denied["ok"], denied["status"]), (False, 403))
        missing = ev.classify(entry("students/amy", "read", "team/data/ap", resp={"request_id": "1"}))
        self.assertEqual(missing["status"], 404)
        root = ev.classify(entry("students/amy", "read", "sys/policies/acl/x", ["root"]))
        self.assertTrue(root["root"])

    def test_wrapping_and_noise(self):
        self.assertEqual(ev.classify(entry("students/amy", "update", "sys/wrapping/unwrap"))["event"], "wrapping")
        for path in ("sys/internal/ui/mounts", "sys/capabilities-self", "auth/token/lookup-self"):
            self.assertIsNone(ev.classify(entry("students/amy", "read", path)))

    def test_not_a_response_or_malformed(self):
        self.assertIsNone(ev.classify({"type": "request"}))
        self.assertIsNone(ev.classify("x"))
        self.assertIsNone(ev.classify({"type": "response", "request": {}}))

    def test_no_values_are_sent(self):
        out = ev.classify(entry("students/amy", "read", "team/data/app"))
        self.assertNotIn("hmac-sha256:x", json.dumps(out))


class Posting(unittest.TestCase):
    def reporter(self, url="http://x", secret="s"):
        sent = []
        r = ev.Reporter(url, secret, send=lambda raw, sig: sent.append((raw, sig)))
        r.live = True
        r.start()
        return r, sent

    def wait(self, r):
        r.queue.join()

    def test_posts_a_signed_event(self):
        r, sent = self.reporter()
        r.entry(entry("students/amy", "read", "team/data/app"))
        self.wait(r)
        raw, sig = sent[0]
        self.assertEqual(sig, hmac.new(b"s", raw, hashlib.sha256).hexdigest())
        self.assertEqual(json.loads(raw)["user"], "amy")

    def test_off_without_url_secret_or_before_live(self):
        for url, secret in (("", "s"), ("http://x", "")):
            r, sent = self.reporter(url, secret)
            r.entry(entry("students/amy", "read", "team/data/app"))
            time.sleep(0.05)
            self.assertEqual(sent, [])
        r, sent = self.reporter()
        r.live = False
        r.entry(entry("students/amy", "read", "team/data/app"))
        time.sleep(0.05)
        self.assertEqual(sent, [])

    def test_a_failing_send_never_raises_and_a_full_queue_drops(self):
        def boom(raw, sig):
            raise OSError("down")
        r = ev.Reporter("http://x", "s", send=boom, size=1)
        r.live = True
        for _ in range(5):
            r.entry(entry("students/amy", "read", "team/data/app"))      # no worker yet: queue fills, rest drop
        r.start()
        r.queue.join()


if __name__ == "__main__":
    unittest.main()
