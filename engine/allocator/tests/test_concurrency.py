"""The allocator serves each connection in its own thread (remediation T3.4):
idle sockets must not delay /auth-check, and concurrent slot claims must
never hand out the same slot. Run from engine/allocator:

  python3 -B -m unittest discover -s tests -v
"""

import os
import socket
import sys
import threading
import time
import unittest
import urllib.request
from unittest import mock
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
for _k, _v in {"FORGEJO_ADMIN_USER": "admin", "FORGEJO_ADMIN_PASSWORD": "x",
               "CONTROL_TOKEN": "control-test", "GATEWAY_TOKEN": "gateway-test",
               "STUDENT_COUNT": "30", "EXTENSIONS_FILE": os.path.join(HERE, "no-such-file.json")}.items():
    os.environ.setdefault(_k, _v)
import server  # noqa: E402


def _free_all():
    with server._state_lock:
        server.token_index.clear()
        for slot in server.slots.values():
            slot.update(name=None, ip=None, token=None, tool=None, assigned_at=None)


class IdleSocketsTest(unittest.TestCase):
    def setUp(self):
        self.httpd = server.make_server(("127.0.0.1", 0))
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.idle = []

    def tearDown(self):
        for s in self.idle:
            s.close()
        self.httpd.shutdown()
        self.httpd.server_close()

    def test_auth_check_fast_with_idle_sockets(self):
        for _ in range(5):
            self.idle.append(socket.create_connection(("127.0.0.1", self.port)))
        time.sleep(0.2)  # let the server accept them
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/auth-check?tool=ide",
                                     headers={"X-Gateway-Token": server.GATEWAY_TOKEN})

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None

        opener = urllib.request.build_opener(NoRedirect)
        start = time.monotonic()
        try:
            opener.open(req, timeout=5)
            status = 200
        except urllib.error.HTTPError as e:
            status = e.code
        elapsed = time.monotonic() - start
        self.assertEqual(status, 303)  # no cookie: sent to the login page
        self.assertLess(elapsed, 1.0, f"/auth-check took {elapsed:.2f}s with 5 idle sockets")


class HandlerCrashTest(unittest.TestCase):
    """A crashing handler leaves an audit line (RV10), without the query."""

    def test_crash_is_audited(self):
        httpd = server.make_server(("127.0.0.1", 0))
        httpd.handle_error = lambda *a: None  # keep the traceback out of the test output
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            with mock.patch.object(server.Handler, "do_GET", side_effect=ValueError("boom")), \
                    mock.patch("server.audit") as audit:
                with self.assertRaises(Exception):
                    urllib.request.urlopen(f"http://127.0.0.1:{httpd.server_address[1]}/x?secret=1", timeout=5)
            audit.assert_called_once_with("error", method="GET", path="/x", exc="ValueError", detail="boom")
        finally:
            httpd.shutdown()
            httpd.server_close()


class ClaimSlotTest(unittest.TestCase):
    def setUp(self):
        _free_all()

    def tearDown(self):
        _free_all()

    def test_parallel_claims_get_distinct_slots(self):
        n = len(server.STUDENT_IDS) + 10  # more callers than slots
        barrier = threading.Barrier(n)

        def claim(i):
            barrier.wait()
            return server.claim_slot(f"name{i}", "127.0.0.1")

        with ThreadPoolExecutor(max_workers=n) as pool:
            results = list(pool.map(claim, range(n)))
        sids = [sid for sid, _ in results if sid is not None]
        self.assertEqual(len(sids), len(server.STUDENT_IDS))
        self.assertEqual(len(set(sids)), len(sids), "a slot was handed out twice")
        self.assertEqual(sum(1 for sid, _ in results if sid is None), 10)
        for sid, token in results:
            if sid is not None:
                self.assertEqual(server.token_index[token], sid)

    def test_stale_release_leaves_new_holder(self):
        server.control_request = lambda *a, **k: None  # no web-terminal here
        sid, old = server.claim_slot("first", "127.0.0.1")
        self.assertEqual(server.release_slot(sid), "first")
        sid2, new = server.claim_slot("second", "127.0.0.1")
        self.assertEqual(sid2, sid)
        # A release decided against the first holder must not free the second.
        self.assertIsNone(server.release_slot(sid, token=old))
        self.assertEqual(server.slot_snapshot(sid)["name"], "second")
        self.assertEqual(server.token_index[new], sid)


class SlotPersistenceTest(unittest.TestCase):
    """A crash or OOM restart must not lose who holds which slot (RV1)."""

    def setUp(self):
        import tempfile
        _free_all()
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "slots.json")
        server.STATE_FILE = self.path
        server.control_request = lambda *a, **k: None

    def tearDown(self):
        server.STATE_FILE = ""
        _free_all()
        self.dir.cleanup()

    def test_claims_and_releases_survive_a_restart(self):
        sid1, tok1 = server.claim_slot("ada", "127.0.0.1")
        sid2, tok2 = server.claim_slot("bob", "127.0.0.1")
        server.release_slot(sid1)
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)
        _free_all()  # what a restart starts from
        self.assertEqual(server.load_slots(), 1)
        self.assertIsNone(server.slot_snapshot(sid1)["name"])
        self.assertEqual(server.slot_snapshot(sid2)["name"], "bob")
        self.assertEqual(server.token_index, {tok2: sid2})

    def test_bad_or_missing_file_starts_empty(self):
        self.assertEqual(server.load_slots(), 0)
        with open(self.path, "w") as f:
            f.write("{not json")
        self.assertEqual(server.load_slots(), 0)
        with open(self.path, "w") as f:
            f.write('{"slots": {"student99": {"name": "x", "token": "t"}, "student01": {"name": "y"}}}')
        self.assertEqual(server.load_slots(), 0)  # unknown slot, missing token
        self.assertEqual(server.token_index, {})

    def test_parallel_claims_leave_the_latest_snapshot(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda i: server.claim_slot(f"n{i}", "127.0.0.1"), range(12)))
        _free_all()
        self.assertEqual(server.load_slots(), 12)


class AssignLimitTest(unittest.TestCase):
    def test_parallel_take_respects_burst(self):
        limit = server.AssignLimit(10, 1)
        barrier = threading.Barrier(40)

        def take(_):
            barrier.wait()
            return limit.take()

        with ThreadPoolExecutor(max_workers=40) as pool:
            granted = sum(1 for w in pool.map(take, range(40)) if w == 0)
        self.assertEqual(granted, 10)


if __name__ == "__main__":
    unittest.main()
