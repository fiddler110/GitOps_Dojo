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


class WaitForStartTests(unittest.TestCase):
    def test_no_secret_starts_immediately(self):
        self.assertEqual(bot.wait_for_start("http://unused.invalid", "", now=lambda: 42.0), 42.0)

    def test_polls_until_a_started_at_comes_back(self):
        calls = {"n": 0}
        sleeps = []

        def fake_poll(url, secret, timeout=5):
            calls["n"] += 1
            return None if calls["n"] < 3 else 1234.5

        bot.poll_control, real = fake_poll, bot.poll_control
        try:
            got = bot.wait_for_start("http://achievements.invalid/api/soc/control", "s3cret",
                                     poll_seconds=0, sleep=sleeps.append)
        finally:
            bot.poll_control = real
        self.assertEqual(got, 1234.5)
        self.assertEqual(calls["n"], 3)
        self.assertEqual(len(sleeps), 2)   # two "not started yet" polls before the third hit


class PollControlTests(unittest.TestCase):
    def test_bad_connection_is_not_started_not_an_error(self):
        self.assertIsNone(bot.poll_control("http://127.0.0.1:1", "s3cret", timeout=0.2))


class PollCommandsTests(unittest.TestCase):
    def test_bad_connection_is_no_commands_not_an_error(self):
        self.assertEqual(bot.poll_commands("http://127.0.0.1:1", "s3cret", timeout=0.2), [])

    def test_reads_the_commands_list_out_of_the_poll(self):
        bot._poll, real = lambda url, secret, timeout=5: {"commands": [{"type": "inject"}]}, bot._poll
        try:
            self.assertEqual(bot.poll_commands("http://x.invalid", "s3cret"), [{"type": "inject"}])
        finally:
            bot._poll = real

    def test_a_malformed_commands_field_is_empty_not_an_error(self):
        bot._poll, real = lambda url, secret, timeout=5: {"commands": "not a list"}, bot._poll
        try:
            self.assertEqual(bot.poll_commands("http://x.invalid", "s3cret"), [])
        finally:
            bot._poll = real


class RunInjectTests(unittest.TestCase):
    def test_posts_dump_success_on_a_breach(self):
        clients = {"ctf": FakeClient(), "soc": FakeClient()}
        attacker = bot.Swarm(["student01"], rng=random.Random(1), started_at=0.0).attackers[0]
        bot.run_inject(clients, "customer-portal", attacker, lambda: True)
        self.assertEqual(clients["ctf"].posted[0]["event"], "dump_success")

    def test_posts_exploit_attempt_when_patched(self):
        clients = {"ctf": FakeClient(), "soc": FakeClient()}
        attacker = bot.Swarm(["student01"], rng=random.Random(1), started_at=0.0).attackers[0]
        bot.run_inject(clients, "customer-portal", attacker, lambda: False)
        self.assertEqual(clients["soc"].posted[0]["event"], "exploit_attempt")


class RunHintProbeTests(unittest.TestCase):
    def test_fires_three_to_six_probes_only(self):
        clients = {"ctf": FakeClient(), "soc": FakeClient()}
        sleeps = []
        bot.run_hint_probe(clients, "customer-portal", "student03", random.Random(1), sleep=sleeps.append)
        self.assertTrue(3 <= len(clients["soc"].posted) <= 6)
        self.assertTrue(all(d["event"] == "probe" for d in clients["soc"].posted))
        self.assertTrue(all(d["user"] == "student03" for d in clients["soc"].posted))
        self.assertEqual(len(sleeps), len(clients["soc"].posted))
        self.assertTrue(all(10.0 <= s <= 60.0 for s in sleeps))


class CommandLoopTests(unittest.TestCase):
    def test_dispatches_inject_and_hint_to_their_targets(self):
        import threading
        real_thread = threading.Thread
        started = []

        class ImmediateThread(real_thread):
            def start(self):
                started.append((self._target, self._args))
                self._target(*self._args, **self._kwargs)

            def join(self, timeout=None):
                pass

        swarm = bot.Swarm(["student01", "student02"], rng=random.Random(1), started_at=0.0)
        exploit_fns = {"student01": lambda: False, "student02": lambda: False}
        clients = {"ctf": FakeClient(), "soc": FakeClient()}
        calls = {"n": 0}

        def fake_poll_commands(url, secret, timeout=5):
            calls["n"] += 1
            if calls["n"] == 1:
                return [{"type": "inject", "user": "student01"}, {"type": "hint", "user": None}]
            raise SystemExit   # stop the (otherwise infinite) loop after one round

        def fast_hint_probe(clients, challenge, user, rng, sleep=None):
            bot.post_event(clients, bot._HintPersona(user, "US"), "probe", challenge)

        bot.poll_commands, real_poll = fake_poll_commands, bot.poll_commands
        bot.run_hint_probe, real_hint = fast_hint_probe, bot.run_hint_probe
        threading.Thread = ImmediateThread
        try:
            with self.assertRaises(SystemExit):
                bot.command_loop("http://x.invalid", "s3cret", swarm, exploit_fns, clients, "customer-portal",
                                 ["student01", "student02"], poll_seconds=0, sleep=lambda s: None)
        finally:
            threading.Thread = real_thread
            bot.poll_commands = real_poll
            bot.run_hint_probe = real_hint
        # one inject (student01 only) plus one hint burst per student (student01, student02)
        self.assertEqual(len(started), 3)


class MakeExploitFnTests(unittest.TestCase):
    def test_operational_error_is_not_a_breach(self):
        exploit = bot.make_exploit_fn("http://127.0.0.1:1", timeout=0.2)  # nothing listens here
        self.assertFalse(exploit())


if __name__ == "__main__":
    unittest.main()
