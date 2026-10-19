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
import allocation  # noqa: E402


class TTLCacheTest(unittest.TestCase):
    def test_expires(self):
        cache = allocation.TTLCache(5)
        with mock.patch("allocation.time.monotonic", return_value=100.0):
            cache.put("k", 1)
            self.assertEqual(cache.get("k"), 1)
        with mock.patch("allocation.time.monotonic", return_value=105.0):
            self.assertIsNone(cache.get("k"))

    def test_forget_user_drops_only_that_user(self):
        cache = allocation.TTLCache(60)
        cache.put(("ide", "student01"), True)
        cache.put(("term", "student01"), True)
        cache.put(("ide", "student02"), True)
        cache.forget_user("student01")
        self.assertIsNone(cache.get(("ide", "student01")))
        self.assertIsNone(cache.get(("term", "student01")))
        self.assertTrue(cache.get(("ide", "student02")))


class ControlRequestForgetsTest(unittest.TestCase):
    def setUp(self):
        allocation.READY_CACHE.put(("ide", "student01"), True)
        allocation.READY_CACHE.put(("ide", "student02"), True)

    def tearDown(self):
        allocation.READY_CACHE.forget_user("student01")
        allocation.READY_CACHE.forget_user("student02")

    def test_stop_and_reset_forget_the_user(self):
        for path in ("/stop/student01", "/reset/student01"):
            allocation.READY_CACHE.put(("ide", "student01"), True)
            with mock.patch("allocation._control_call", return_value=b"{}"):
                allocation.control_request("POST", path)
            self.assertIsNone(allocation.READY_CACHE.get(("ide", "student01")))
        self.assertTrue(allocation.READY_CACHE.get(("ide", "student02")))

    def test_a_start_keeps_it(self):
        with mock.patch("allocation._control_call", return_value=b"{}"):
            allocation.control_request("POST", "/start/ide/student01")
            allocation.control_request("GET", "/status?users=student01")
        self.assertTrue(allocation.READY_CACHE.get(("ide", "student01")))

    def test_forgets_even_when_the_call_fails(self):
        with mock.patch("allocation._control_call", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                allocation.control_request("POST", "/stop/student01")
        self.assertIsNone(allocation.READY_CACHE.get(("ide", "student01")))


class SingleFlightTest(unittest.TestCase):
    def test_concurrent_callers_share_one_call(self):
        import threading
        flights, gate, calls, results = allocation.SingleFlight(), threading.Event(), [], []

        def slow():
            calls.append(1)
            gate.wait(5)
            return True

        threads = [threading.Thread(target=lambda: results.append(flights.do("k", slow, 5))) for _ in range(20)]
        for t in threads:
            t.start()
        for _ in range(100):  # every follower is parked on the leader
            if len(calls) == 1 and flights._calls:
                break
        gate.set()
        for t in threads:
            t.join(5)
        self.assertEqual((len(calls), results), (1, [True] * 20))
        self.assertEqual(flights._calls, {})
        self.assertEqual(flights.do("k", lambda: "again", 1), "again")  # a later call runs anew

    def test_keys_are_independent_and_waiters_time_out(self):
        import threading
        flights, gate = allocation.SingleFlight(), threading.Event()
        leader = threading.Thread(target=flights.do, args=("a", lambda: gate.wait(5), 5))
        leader.start()
        while not flights._calls:
            pass
        self.assertEqual(flights.do("b", lambda: 2, 1), 2)  # another workspace isn't held up
        self.assertIsNone(flights.do("a", lambda: 3, 0.05))  # gave up waiting: not ready
        gate.set()
        leader.join(5)

    def test_leader_exception_releases_waiters(self):
        flights = allocation.SingleFlight()
        with self.assertRaises(RuntimeError):
            flights.do("k", lambda: (_ for _ in ()).throw(RuntimeError()), 1)
        self.assertEqual(flights._calls, {})


if __name__ == "__main__":
    unittest.main()
