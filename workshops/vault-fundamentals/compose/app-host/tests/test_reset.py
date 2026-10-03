"""Unit tests for app-host's student-reset hooks (no stack, no root): the
slots' teardown and provision in a temporary folder, the token checks, and
app-db's job relay over real HTTP with a stand-in worker. Run:
    python3 -B -m unittest discover -s workshops/vault-fundamentals/compose/app-host/tests
"""
import http.client
import http.server
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import apphost as P  # noqa: E402

TOKEN = "reset-token"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.dirs = mock.patch.multiple(P, APPS_DIR=os.path.join(root, "apps"), TOKEN_DIR=os.path.join(root, "run"),
                                        META_DIR=os.path.join(root, "apps", ".platform"))
        self.dirs.start()
        os.makedirs(P.META_DIR)
        self.patches = [mock.patch("os.chown"), mock.patch("pwd.getpwnam")]
        for p in self.patches:
            p.start()
        self.p = P.Platform(P.Config({"STUDENT_COUNT": "2", "RESET_TOKEN": TOKEN, "GATEWAY_TOKEN": "gw"}))
        self.p.kill_all = lambda s: None
        self.written = []
        self.p.write_token = lambda s: self.written.append(s.name)
        for s in self.p.slots.values():
            self.p.prepare_slot(s)

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.dirs.stop()
        self.tmp.cleanup()


class SlotReset(Base):
    def fill(self, s):
        os.makedirs(os.path.join(s.home, "app", "sub"))
        open(os.path.join(s.home, "app", "start.sh"), "w").close()
        os.symlink("/etc", os.path.join(s.home, "link"))
        open(os.path.join(s.token_dir, "token"), "w").close()
        with open(os.path.join(P.META_DIR, s.name + ".json"), "w") as f:
            json.dump({"sha": "abc"}, f)
        s.deployed, s.state = {"sha": "abc"}, "running"
        s.log.append("old line")

    def test_teardown_empties_both_slots_and_locks_the_capstone(self):
        lab, cap = self.p.slots["student01"], self.p.slots["student01-capstone"]
        other = self.p.slots["student02"]
        for s in (lab, cap, other):
            self.fill(s)
        detail = self.p.reset_teardown("student01")
        self.assertIn("student01 and student01-capstone", detail)
        for s in (lab, cap):
            self.assertEqual(os.listdir(s.home), [])
            self.assertEqual(os.listdir(s.token_dir), [])
            self.assertFalse(os.path.exists(os.path.join(P.META_DIR, s.name + ".json")))
            self.assertIsNone(s.deployed)
            self.assertEqual(list(s.log), [])
        self.assertTrue(os.path.isdir("/etc"))  # the symlink was removed, not followed
        self.assertEqual((lab.state, cap.state), ("empty", "locked"))
        self.assertEqual(other.state, "running")  # another student's slot is untouched
        self.assertTrue(os.path.exists(os.path.join(other.home, "app", "start.sh")))
        # Until provision: no unlock, no capstone look, no deploy.
        self.p.repo_exists = lambda repo: True
        self.p.check_capstone("student01")
        self.p.unlock(cap, "test")
        self.assertEqual(cap.state, "locked")
        self.assertEqual(self.p.deploy(lab, b"", {})[0], 409)
        # Safe to run again.
        self.p.reset_teardown("student01")

    def test_provision_makes_the_slots_again(self):
        lab, cap = self.p.slots["student01"], self.p.slots["student01-capstone"]
        self.p.reset_teardown("student01")
        os.rmdir(lab.home)
        self.written.clear()
        self.assertIn("ready", self.p.reset_provision("student01"))
        self.assertTrue(os.path.isdir(lab.home))
        self.assertEqual(oct(os.stat(lab.home).st_mode & 0o777), "0o700")
        self.assertEqual(self.written, ["student01"])  # the locked capstone slot gets no token
        self.assertEqual(cap.state, "locked")
        self.assertNotIn("student01", self.p.resetting)
        self.p.reset_provision("student01")  # again: harmless


class Hooks(Base):
    def setUp(self):
        super().setUp()
        self.old_timeouts = (P.DB_JOB_TIMEOUT, P.DB_POLL_WAIT)
        P.DB_JOB_TIMEOUT, P.DB_POLL_WAIT = 2, 1
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), P.make_handler(self.p))
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        P.DB_JOB_TIMEOUT, P.DB_POLL_WAIT = self.old_timeouts
        super().tearDown()

    def call(self, method, path, token=TOKEN, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=10)
        headers = {"X-Dojo-Reset-Token": token} if token is not None else {}
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        try:
            return resp.status, json.loads(raw)
        except ValueError:
            return resp.status, raw.decode()

    def test_token_required(self):
        for token in (None, "", "wrong"):
            for method, path in (("POST", "/_dojo/reset/apps/student01?phase=teardown"),
                                 ("POST", "/_dojo/reset/db/student01?phase=teardown"),
                                 ("GET", "/_dojo/db-work"), ("POST", "/_dojo/db-work/abc")):
                self.assertEqual(self.call(method, path, token)[0], 403, (token, path))
        self.assertEqual(self.p.resetting, set())

    def test_empty_reset_token_refuses_everything(self):
        self.p.cfg.reset_token = ""
        self.assertEqual(self.call("POST", "/_dojo/reset/apps/student01?phase=teardown", "")[0], 403)

    def test_bad_requests(self):
        self.assertEqual(self.call("POST", "/_dojo/reset/apps/student09?phase=teardown")[0], 400)
        self.assertEqual(self.call("POST", "/_dojo/reset/apps/student01-capstone?phase=teardown")[0], 400)
        self.assertEqual(self.call("POST", "/_dojo/reset/apps/root?phase=teardown")[0], 400)
        self.assertEqual(self.call("POST", "/_dojo/reset/apps/student01?phase=wipe")[0], 404)
        self.assertEqual(self.call("POST", "/_dojo/reset/other/student01?phase=teardown")[0], 404)

    def test_apps_phases(self):
        code, doc = self.call("POST", "/_dojo/reset/apps/student01?phase=teardown")
        self.assertEqual((code, doc["ok"]), (200, True))
        self.assertIn("student01", self.p.resetting)
        code, doc = self.call("POST", "/_dojo/reset/apps/student01?phase=provision")
        self.assertEqual((code, doc["ok"]), (200, True))
        self.assertNotIn("student01", self.p.resetting)

    def test_db_job_goes_to_the_worker_and_back(self):
        seen = []

        def worker():
            code, line = self.call("GET", "/_dojo/db-work")
            seen.append(line)
            job_id = line.split()[0]
            self.call("POST", "/_dojo/db-work/" + job_id, body=b"ok\nsome output\napp_student02 dropped and made again\n")
        threading.Thread(target=worker, daemon=True).start()
        code, doc = self.call("POST", "/_dojo/reset/db/student02?phase=teardown")
        self.assertEqual((code, doc), (200, {"ok": True, "detail": "some output app_student02 dropped and made again"}))
        self.assertTrue(seen[0].endswith(" teardown student02\n"))

    def test_db_job_failure_and_no_worker(self):
        def worker():
            line = self.call("GET", "/_dojo/db-work")[1]
            self.call("POST", "/_dojo/db-work/" + line.split()[0], body=b"fail\nERROR: boom")
        threading.Thread(target=worker, daemon=True).start()
        code, doc = self.call("POST", "/_dojo/reset/db/student01?phase=provision")
        self.assertEqual((code, doc["ok"], doc["detail"]), (502, False, "ERROR: boom"))
        started = time.monotonic()
        code, doc = self.call("POST", "/_dojo/reset/db/student01?phase=provision")
        self.assertEqual(code, 502)
        self.assertIn("not running", doc["detail"])
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(self.call("GET", "/_dojo/db-work"), (200, ""))  # the timed-out job was withdrawn
        self.assertEqual(self.call("POST", "/_dojo/db-work/deadbeef", body=b"ok\n")[0], 404)


if __name__ == "__main__":
    unittest.main()
