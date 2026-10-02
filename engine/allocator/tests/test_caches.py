"""The ready and status caches (RV3, RV4): a burst of identical requests
makes one control call, and any stop or reset of a user forgets them. Run
from engine/allocator:

  python3 -B -m unittest discover -s tests -v
"""

import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
for _k, _v in {"FORGEJO_ADMIN_USER": "admin", "FORGEJO_ADMIN_PASSWORD": "x",
               "CONTROL_TOKEN": "control-test", "GATEWAY_TOKEN": "gateway-test",
               "STUDENT_COUNT": "30", "EXTENSIONS_FILE": os.path.join(HERE, "no-such-file.json")}.items():
    os.environ.setdefault(_k, _v)
import server  # noqa: E402


class TTLCacheTest(unittest.TestCase):
    def test_expires(self):
        cache = server.TTLCache(5)
        with mock.patch("server.time.monotonic", return_value=100.0):
            cache.put("k", 1)
            self.assertEqual(cache.get("k"), 1)
        with mock.patch("server.time.monotonic", return_value=105.0):
            self.assertIsNone(cache.get("k"))

    def test_forget_user_drops_only_that_user(self):
        cache = server.TTLCache(60)
        cache.put(("ide", "student01"), True)
        cache.put(("term", "student01"), True)
        cache.put(("ide", "student02"), True)
        cache.forget_user("student01")
        self.assertIsNone(cache.get(("ide", "student01")))
        self.assertIsNone(cache.get(("term", "student01")))
        self.assertTrue(cache.get(("ide", "student02")))


class ControlRequestForgetsTest(unittest.TestCase):
    def setUp(self):
        server.READY_CACHE.put(("ide", "student01"), True)
        server.READY_CACHE.put(("ide", "student02"), True)

    def tearDown(self):
        server.READY_CACHE.forget_user("student01")
        server.READY_CACHE.forget_user("student02")

    def test_stop_and_reset_forget_the_user(self):
        for path in ("/stop/student01", "/reset/student01"):
            server.READY_CACHE.put(("ide", "student01"), True)
            with mock.patch("server._control_call", return_value=b"{}"):
                server.control_request("POST", path)
            self.assertIsNone(server.READY_CACHE.get(("ide", "student01")))
        self.assertTrue(server.READY_CACHE.get(("ide", "student02")))

    def test_a_start_keeps_it(self):
        with mock.patch("server._control_call", return_value=b"{}"):
            server.control_request("POST", "/start/ide/student01")
            server.control_request("GET", "/status?users=student01")
        self.assertTrue(server.READY_CACHE.get(("ide", "student01")))

    def test_forgets_even_when_the_call_fails(self):
        with mock.patch("server._control_call", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                server.control_request("POST", "/stop/student01")
        self.assertIsNone(server.READY_CACHE.get(("ide", "student01")))


if __name__ == "__main__":
    unittest.main()
