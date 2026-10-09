"""ctf-defend scoring: green 2 / yellow 1 / red 0 units, +1 per bonus fixed (plan 8.10, CTF-D19),
at one configurable factor; and the bonus toggle (workshops/ctf-defend/workshop.env CTF_BONUS_FLAWS)."""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "catalog"))
import catalog  # noqa: E402
import ledger as lg  # noqa: E402
from store import Store  # noqa: E402

PACK = os.path.join(HERE, "..", "..", "..", "workshops", "ctf-defend")
SHARED = os.path.join(HERE, "..", "catalog", "shared.json")
U = "student01"
UNITS = ("d-patched", "d-unbreached")


def merged(user=U):
    return {"source": "forgejo", "event": "pull_request", "action": "merged", "user": user,
            "repo": f"{user}/customer-portal"}


def soc(event, user=U):
    return {"source": "soc", "event": event, "user": user, "challenge": "customer-portal"}


class Scoring(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def store(self, factor=5, pack=PACK):
        cfg = lg.Config(first_blood_on=False, class_clear_on=False,
                        points={"milestone": factor, "challenge": factor})
        return Store(catalog.load(pack, SHARED)[0], cfg, self.dir, "secret", facilitator="boss")

    def units(self, s):
        got = s.ledger.users[U]["unlocked"]
        return sum(got[i]["points"] for i in UNITS if i in got)

    def test_green_is_two_units(self):
        s = self.store()
        s.adapter(soc("exploit_attempt"))      # the swarm's real payload failed, never breached
        s.forgejo(merged())
        self.assertEqual(self.units(s), 10)

    def test_yellow_is_one_unit_and_never_becomes_green(self):
        s = self.store()
        s.adapter({"source": "ctf", "event": "dump_success", "user": U, "challenge": "customer-portal"})
        s.forgejo(merged())
        s.adapter(soc("contained"))
        s.adapter(soc("exploit_attempt"))      # a retry after the fix costs nothing, earns nothing
        self.assertEqual(self.units(s), 5)

    def test_red_is_zero(self):
        s = self.store()
        s.adapter({"source": "ctf", "event": "dump_success", "user": U, "challenge": "customer-portal"})
        s.adapter(soc("probe"))
        self.assertEqual(self.units(s), 0)

    def test_factor_is_the_configured_default(self):
        s = self.store(factor=3)
        s.adapter(soc("exploit_attempt"))
        self.assertEqual(self.units(s), 6)

    def test_bonus_challenge_is_one_unit_when_on_and_absent_when_off(self):
        s = self.store()
        self.assertEqual(s.ledger.index["c1"]["points"], 5)
        off = os.path.join(tempfile.mkdtemp(), "ctf-defend")
        shutil.copytree(PACK, off)
        shutil.copy(os.path.join(PACK, "achievements", "variants", "c1.off.json"),
                    os.path.join(off, "achievements", "challenges", "c1.json"))
        try:
            s2 = self.store(pack=off)
            self.assertNotIn("c1", s2.ledger.index)
        finally:
            shutil.rmtree(os.path.dirname(off))

    def test_probe_path_reaches_the_soc_row(self):
        s = self.store()
        s.adapter({"source": "soc", "event": "probe", "user": U, "challenge": "customer-portal", "path": "/portal.db"})
        self.assertEqual(s.soc_rows(U)[0]["path"], "/portal.db")

    def test_off_variant_is_the_on_file_with_enabled_false(self):
        on = json.load(open(os.path.join(PACK, "achievements", "challenges", "c1.json")))
        off = json.load(open(os.path.join(PACK, "achievements", "variants", "c1.off.json")))
        self.assertEqual(off.pop("enabled"), False)
        self.assertEqual(on, off)


if __name__ == "__main__":
    unittest.main()
