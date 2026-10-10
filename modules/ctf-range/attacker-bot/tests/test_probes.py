import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "_shared"))
import bot  # noqa: E402
import probes  # noqa: E402


class FakeClient:
    def __init__(self):
        self.posted = []

    def post(self, doc):
        self.posted.append(doc)
        return True


class ProbePathTests(unittest.TestCase):
    def test_bonus_off_never_draws_the_bonus_area(self):
        rng = random.Random(7)
        got = {probes.probe_path(rng, bonus_on=False) for _ in range(2000)}
        self.assertTrue(got <= set(probes.MAIN_PATHS))

    def test_bonus_on_mixes_in_the_bonus_area_unlabelled(self):
        rng = random.Random(7)
        got = [probes.probe_path(rng, bonus_on=True) for _ in range(2000)]
        share = sum(p in probes.BONUS_PATHS for p in got) / len(got)
        self.assertTrue(0.2 < share < 0.4)
        self.assertTrue(all(isinstance(p, str) and p.startswith("/") for p in got))

    def test_env_toggle(self):
        self.assertTrue(probes.bonus_enabled({}))
        self.assertTrue(probes.bonus_enabled({"CTF_BONUS_FLAWS": "on"}))
        self.assertFalse(probes.bonus_enabled({"CTF_BONUS_FLAWS": "off"}))

    def test_probe_and_recon_carry_a_request_line_and_none_are_exploits(self):
        clients = {"ctf": FakeClient(), "soc": FakeClient()}
        attacker = bot.Swarm(["student01"], rng=random.Random(1), started_at=0.0).attackers[0]
        bot.post_event(clients, attacker, "probe", "customer-portal")
        bot.post_event(clients, attacker, "recon", "customer-portal")
        for doc in clients["soc"].posted:
            self.assertIn("path", doc)
            self.assertNotEqual(doc["klass"], "exploit")
            self.assertNotIn("%27+OR", doc["query"])


if __name__ == "__main__":
    unittest.main()
