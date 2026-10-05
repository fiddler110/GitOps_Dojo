import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# adapter_client: see bot.py's own sys.path dance; running from a repo checkout, the canonical
# copy lives at modules/_shared/, not under ./_shared/ (only populated once ./run.sh runs).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "_shared"))
import bot  # noqa: E402


class RosterTests(unittest.TestCase):
    def test_matches_controller_padding(self):
        self.assertEqual(bot.roster("student", 3), ["student01", "student02", "student03"])

    def test_zero_is_empty(self):
        self.assertEqual(bot.roster("student", 0), [])


class TargetUrlTests(unittest.TestCase):
    def test_offset_by_index(self):
        self.assertEqual(bot.target_url("ctf-host", 15000, 0), "http://ctf-host:15000")
        self.assertEqual(bot.target_url("ctf-host", 15000, 3), "http://ctf-host:15003")


class FakeClient:
    def __init__(self):
        self.posted = []

    def post(self, doc):
        self.posted.append(doc)
        return True


class PostEventTests(unittest.TestCase):
    def test_dump_success_goes_to_ctf_client(self):
        clients = {"ctf": FakeClient(), "soc": FakeClient()}
        attacker = bot.Swarm(["student01"], rng=random.Random(1), started_at=0.0).attackers[0]
        bot.post_event(clients, attacker, "dump_success", "customer-portal")
        self.assertEqual(len(clients["ctf"].posted), 1)
        self.assertEqual(len(clients["soc"].posted), 0)

    def test_everything_else_goes_to_soc_client(self):
        clients = {"ctf": FakeClient(), "soc": FakeClient()}
        attacker = bot.Swarm(["student01"], rng=random.Random(1), started_at=0.0).attackers[0]
        for outcome in ("recon", "probe", "exploit_attempt", "contained"):
            bot.post_event(clients, attacker, outcome, "customer-portal")
        self.assertEqual(len(clients["soc"].posted), 4)
        self.assertEqual(len(clients["ctf"].posted), 0)
        self.assertEqual(clients["soc"].posted[0]["user"], "student01")


class RunTests(unittest.TestCase):
    """`run()` with a fake clock/sleep that advances deterministically and stops after a fixed
    number of attempts per thread, so this never actually sleeps or hits a network."""

    def test_emits_one_post_per_attempt_per_user(self):
        state = {"now": 0.0}
        calls = {"n": 0}

        def clock():
            return state["now"]

        def sleep(seconds):
            state["now"] += seconds
            calls["n"] += 1
            if calls["n"] > 12:   # stop the (otherwise infinite) attacker loops
                raise SystemExit

        import threading
        real_thread = threading.Thread

        class OneShotThread(real_thread):
            """Runs the target directly (no real OS thread) so the test is deterministic and
            fast; SystemExit from `sleep` above ends that thread's loop cleanly."""
            def start(self):
                try:
                    self._target(*self._args, **self._kwargs)
                except SystemExit:
                    pass

            def join(self, timeout=None):
                pass

        threading.Thread = OneShotThread
        try:
            users = ["student01", "student02"]
            target_urls = {u: "http://example.invalid" for u in users}
            clients = {"ctf": FakeClient(), "soc": FakeClient()}
            bot.run(users, target_urls, "customer-portal", started_at=0.0, clients=clients,
                   clock=clock, sleep=sleep, rng=random.Random(1))
        finally:
            threading.Thread = real_thread

        posted = clients["ctf"].posted + clients["soc"].posted
        self.assertTrue(posted)
        self.assertTrue({d["user"] for d in posted} <= {"student01", "student02"})


class MakeExploitFnTests(unittest.TestCase):
    def test_operational_error_is_not_a_breach(self):
        exploit = bot.make_exploit_fn("http://127.0.0.1:1", timeout=0.2)  # nothing listens here
        self.assertFalse(exploit())


if __name__ == "__main__":
    unittest.main()
