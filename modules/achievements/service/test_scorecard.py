"""Scorecard (plan 8.10): units x weight x factor, per student and for the room."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(__file__))
from test_server import StoreTests


class Scorecard(StoreTests):
    def _breach(self, user, target, weight, fix=False):
        self.s.adapter({"source": "ctf", "event": "dump_success", "user": user, "challenge": target,
                        "target_severity": "HIGH", "weight": weight})
        if fix:
            self.clock.t += 30
            self.s.adapter({"source": "soc", "event": "contained", "user": user, "challenge": target})

    def test_lights_units_points_and_totals(self):
        f = self.s.config.points["milestone"]
        self.s.me("alice"); self.s.me("bob")
        self._breach("alice", "big", 3, fix=True)    # yellow: 1 x 3
        self._breach("alice", "mid", 2)              # red: 0
        self._breach("bob", "small", 1)              # makes "small" known; bob red there
        card = self.s.scorecard("alice")
        by = {t["target"]: t for t in card["targets"]}
        self.assertEqual([t["target"] for t in card["targets"]], ["big", "mid", "small"])
        self.assertEqual((by["big"]["light"], by["big"]["points"], by["big"]["mttp"]), ("yellow", 3 * f, 30))
        self.assertEqual((by["mid"]["light"], by["mid"]["points"]), ("red", 0))
        self.assertEqual((by["small"]["light"], by["small"]["points"]), ("green", 2 * f))
        self.assertEqual(card["total"], 5 * f)
        self.assertEqual(card["max"], 12 * f)

    def test_room_view_sorted_with_counts(self):
        self.s.me("alice"); self.s.me("bob")
        self._breach("bob", "big", 3)
        room = self.s.admin_scorecard()
        self.assertEqual([c["user"] for c in room["students"]], [self.s._label("alice"), self.s._label("bob")])
        self.assertEqual(room["lights"], {"green": 1, "yellow": 0, "red": 1})
        self.assertEqual(len(room["export"]), 2)
        self.assertIsNone(room["mttp_mean"])

    def test_facilitator_own_card_is_empty(self):
        self.assertEqual(self.s.scorecard(self.s.facilitator)["targets"], [])


if __name__ == "__main__":
    unittest.main()
