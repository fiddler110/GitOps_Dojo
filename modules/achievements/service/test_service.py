"""Unit tests for the ledger, anonymous names and event guards. No containers."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "catalog"))
import catalog as cat  # noqa: E402
import guards  # noqa: E402
import ledger as lg  # noqa: E402
import names  # noqa: E402

ROOT = os.path.join(HERE, "..", "..", "..")
CATALOG, _ = cat.load(os.path.join(ROOT, "workshops", "git-fundamentals"), os.path.join(HERE, "..", "catalog", "shared.json"))


def fresh(**cfg):
    return lg.Ledger(CATALOG, lg.Config(**cfg))


class Unlocking(unittest.TestCase):
    def test_points_once(self):
        L = fresh()
        self.assertEqual(L.unlock("a", "l1-clone", 1), 10)
        self.assertIsNone(L.unlock("a", "l1-clone", 2))
        self.assertEqual(L.score("a"), 10)

    def test_funny_scores_nothing_but_toasts(self):
        L = fresh()
        self.assertEqual(L.unlock("a", "f-wrongdir", 1), 0)
        self.assertEqual(L.score("a"), 0)
        t = L.pending("a")[0]
        self.assertEqual((t["kind"], t["ms"]), ("funny", 5000))
        self.assertTrue(t["joke"])

    def test_funny_points_env_cannot_pay_out(self):
        L = fresh(points={"funny": 5})
        self.assertEqual(L.unlock("a", "f-wrongdir", 1), 0)

    def test_cheat_penalty_and_floor(self):
        L = fresh()
        self.assertEqual(L.unlock("a", "cheat-forged", 1), -1)
        self.assertEqual(L.score("a"), 0)          # never below zero
        L.unlock("a", "l1-clone", 2)
        self.assertEqual(L.score("a"), 9)
        self.assertEqual(len(L.pending("a")), 2)   # cheating toasts too

    def test_cheat_penalty_switch(self):
        L = fresh(cheat_penalty_on=False)
        self.assertEqual(L.unlock("a", "cheat-forged", 1), 0)
        self.assertEqual(len(L.pending("a")), 1)

    def test_bad_ids(self):
        L = fresh()
        with self.assertRaises(lg.UnknownItem):
            L.unlock("a", "nope", 1)
        with self.assertRaises(lg.WrongKind):
            L.unlock("a", "c1", 1)
        with self.assertRaises(lg.WrongKind):
            L.clear("a", "l1-clone", 1)

    def test_retired_cannot_be_earned_but_keeps_points(self):
        L = fresh()
        L.unlock("a", "l1-clone", 1)
        for lab in CATALOG["labs"]:
            for m in lab["milestones"]:
                if m["id"] == "l1-clone":
                    m["retired"] = True
        try:
            L2 = lg.Ledger.from_dict(CATALOG, L.to_dict(), lg.Config())
            self.assertEqual(L2.score("a"), 10)
            with self.assertRaises(lg.UnknownItem):
                L2.unlock("b", "l1-clone", 2)
        finally:
            for lab in CATALOG["labs"]:
                for m in lab["milestones"]:
                    m.pop("retired", None)


class Challenges(unittest.TestCase):
    def test_hint_cost_is_floored_percent(self):
        self.assertEqual(fresh().hint_cost("c1"), 25)
        self.assertEqual(fresh(hint_percent=33).hint_cost("c1"), 33)
        self.assertEqual(fresh(hint_percent=7).hint_cost("c1"), 7)

    def test_hints_reduce_the_clear(self):
        L = fresh(first_blood_on=False)
        self.assertEqual(L.use_hint("a", "c1"), {"n": 1, "cost": 25, "counted": True})
        self.assertEqual(L.use_hint("a", "c1")["n"], 2)
        self.assertEqual(L.clear_points("a", "c1"), 50)
        self.assertEqual(L.clear("a", "c1", 5), 50)
        self.assertEqual(L.score("a"), 50)

    def test_hints_stop_counting_at_two(self):
        L = fresh()
        L.use_hint("a", "c1"); L.use_hint("a", "c1")
        self.assertEqual(L.use_hint("a", "c1"), {"n": 2, "cost": 0, "counted": True})
        self.assertEqual(L.hints_used("a", "c1"), 2)

    def test_reveal_needs_both_hints_and_scores_zero(self):
        L = fresh()
        L.use_hint("a", "c1")
        with self.assertRaises(lg.HintsRequired):
            L.reveal("a", "c1")
        L.use_hint("a", "c1")
        self.assertTrue(L.reveal("a", "c1"))
        self.assertEqual(L.clear("a", "c1", 9), 0)
        self.assertIn("c1", L.unlocked_ids("a"))     # still counts as completed

    def test_only_first_clear_scores_and_hints_after_are_free(self):
        L = fresh(first_blood_on=False)
        L.clear("a", "c1", 1)
        self.assertIsNone(L.clear("a", "c1", 2))
        self.assertEqual(L.use_hint("a", "c1")["cost"], 0)
        self.assertEqual(L.score("a"), 100)

    def test_capstone_is_worth_more(self):
        L = fresh(first_blood_on=False)
        self.assertEqual(L.clear("a", "capstone", 1), 300)

    def test_points_never_negative(self):
        L = fresh(hint_percent=100, first_blood_on=False)
        L.use_hint("a", "c1"); L.use_hint("a", "c1")
        self.assertEqual(L.clear("a", "c1", 1), 0)


class Bonuses(unittest.TestCase):
    def test_first_blood_once(self):
        L = fresh(class_clear_on=False)
        self.assertEqual(L.clear("a", "c1", 1), 100)
        L.clear("b", "c1", 2)
        self.assertEqual(L.score("a"), 125)
        self.assertEqual(L.score("b"), 100)
        self.assertEqual(L.first_blood["c1"], "a")

    def test_capstone_first_blood(self):
        L = fresh(class_clear_on=False)
        L.clear("a", "capstone", 1)
        self.assertEqual(L.score("a"), 350)

    def test_revealing_forfeits_first_blood(self):
        L = fresh(class_clear_on=False)
        L.use_hint("a", "c1"); L.use_hint("a", "c1"); L.reveal("a", "c1")
        L.clear("a", "c1", 1)
        self.assertNotIn("c1", L.first_blood)
        L.clear("b", "c1", 2)
        self.assertEqual(L.first_blood["c1"], "b")

    def test_first_blood_switch(self):
        L = fresh(first_blood_on=False, class_clear_on=False)
        L.clear("a", "c1", 1)
        self.assertEqual(L.score("a"), 100)

    def test_class_clear_pays_everyone_once(self):
        L = fresh(first_blood_on=False)
        L.register("a"); L.register("b")
        L.clear("a", "c1", 1)
        self.assertEqual(L.score("b"), 0)
        L.clear("b", "c1", 2)
        self.assertEqual((L.score("a"), L.score("b")), (110, 110))
        self.assertEqual(L.pending("b")[-1]["title"], "Class clear!")
        L.register("late")
        L.clear("late", "c1", 3)
        self.assertEqual(L.score("a"), 110)      # not paid again

    def test_class_clear_needs_two_students(self):
        L = fresh(first_blood_on=False)
        L.clear("a", "c1", 1)
        self.assertEqual(L.class_cleared, [])

    def test_class_clear_waits_for_the_whole_roster(self):
        L = fresh(first_blood_on=False)
        for u in "abc":
            L.register(u)
        L.clear("a", "c1", 1); L.clear("b", "c1", 2)
        self.assertEqual(L.class_cleared, [])
        L.clear("c", "c1", 3)
        self.assertEqual(L.class_cleared, ["c1"])

    def test_class_clear_switch(self):
        L = fresh(first_blood_on=False, class_clear_on=False)
        L.register("a"); L.register("b")
        L.clear("a", "c1", 1); L.clear("b", "c1", 2)
        self.assertEqual(L.score("a"), 100)


class Reading(unittest.TestCase):
    def test_leaderboard_ties_go_to_first_there(self):
        L = fresh()
        L.unlock("late", "l1-clone", 20)
        L.unlock("early", "l1-clone", 10)
        L.unlock("top", "l1-branch", 30); L.unlock("top", "l1-diff", 31)
        rows = L.leaderboard()
        self.assertEqual([r["user"] for r in rows], ["top", "early", "late"])
        self.assertEqual([r["rank"] for r in rows], [1, 2, 3])

    def test_leaderboard_shows_whole_class_including_zero(self):
        L = fresh()
        L.register("a"); L.register("b")
        self.assertEqual(len(L.leaderboard()), 2)

    def test_equal_time_shares_rank(self):
        L = fresh()
        L.unlock("a", "l1-clone", 5); L.unlock("b", "l1-clone", 5)
        self.assertEqual([r["rank"] for r in L.leaderboard()], [1, 1])

    def test_moments_are_funny_only_and_private_data(self):
        L = fresh()
        L.unlock("a", "f-wrongdir", 7)
        L.unlock("a", "cheat-forged", 8)
        L.unlock("a", "l1-clone", 9)
        m = L.moments("a")
        self.assertEqual([x["id"] for x in m], ["f-wrongdir"])
        self.assertTrue(m[0]["joke"] and m[0]["when"] and m[0]["at"] == 7)
        self.assertEqual(L.moments("nobody"), [])

    def test_recent_excludes_funny_and_orders_newest_first(self):
        L = fresh()
        L.unlock("a", "l1-clone", 1); L.unlock("a", "f-wrongdir", 2); L.unlock("a", "l1-branch", 3)
        self.assertEqual([r["id"] for r in L.recent("a")], ["l1-branch", "l1-clone"])
        self.assertTrue(L.recent("a")[0]["title"])

    def test_completion_uses_core_only_and_ignores_funny(self):
        L = fresh()
        core = [m["id"] for m in cat.core_milestones(CATALOG)]
        need = -(-len(core) * 80 // 100)
        for i in core[: need - 1]:
            L.unlock("a", i, 1)
        L.unlock("a", "f-wrongdir", 2)
        self.assertFalse(L.completion("a")[3])
        L.unlock("a", core[need - 1], 3)
        self.assertTrue(L.completion("a")[3])

    def test_award_and_reset(self):
        L = fresh()
        L.clear("a", "c1", 1)
        L.award("a", 15, "helped a neighbour", 2)
        self.assertEqual(L.score("a"), 140)
        L.award("a", -1000, "oops", 3)
        self.assertEqual(L.score("a"), 0)
        self.assertTrue(L.reset("a", 4))
        self.assertEqual(L.score("a"), 0)
        self.assertNotIn("c1", L.first_blood)
        self.assertEqual([e["action"] for e in L.log], ["award", "award", "reset"])

    def test_state_round_trips(self):
        import json
        L = fresh()
        L.unlock("a", "l1-clone", 1); L.use_hint("a", "c1"); L.clear("b", "c1", 2)
        L2 = lg.Ledger.from_dict(CATALOG, json.loads(json.dumps(L.to_dict())), lg.Config())
        self.assertEqual(L2.leaderboard(), L.leaderboard())
        self.assertEqual(L2.hints_used("a", "c1"), 1)
        self.assertEqual(L2.first_blood, L.first_blood)

    def test_config_from_env(self):
        c = lg.Config.from_env({"ACHIEVEMENTS_HINT_PERCENT": "40", "ACHIEVEMENTS_FIRST_BLOOD": "0",
                                "ACHIEVEMENTS_FUNNY_POINTS": "junk"})
        self.assertEqual((c.hint_percent, c.first_blood_on, c.points["funny"]), (40, False, 0))
        self.assertTrue(c.class_clear_on)


class Toasts(unittest.TestCase):
    def test_shown_once(self):
        L = fresh()
        L.unlock("a", "l1-clone", 1)
        self.assertEqual(len(L.claim("a", "portal", 2)), 1)
        self.assertEqual(L.claim("a", "workspace", 3), [])

    def test_terminal_echo_does_not_deliver(self):
        L = fresh()
        L.unlock("a", "f-wrongdir", 1)
        self.assertEqual(len(L.claim("a", "terminal", 2)), 1)
        self.assertEqual(len(L.claim("a", "portal", 3)), 1)
        self.assertEqual(L.claim("a", "portal", 4), [])

    def test_many_collapse_into_one(self):
        L = fresh()
        ids = [m["id"] for m in cat.milestones(CATALOG)][:6]
        for i, x in enumerate(ids):
            L.unlock("a", x, i)
        out = L.claim("a", "portal", 10)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["title"], "You unlocked 6 achievements")
        self.assertEqual(out[0]["points"], 60)
        self.assertEqual(L.claim("a", "portal", 11), [])

    def test_five_are_shown_individually(self):
        L = fresh()
        for i, x in enumerate([m["id"] for m in cat.milestones(CATALOG)][:5]):
            L.unlock("a", x, i)
        self.assertEqual(len(L.claim("a", "portal", 10)), 5)

    def test_toasts_are_per_student(self):
        L = fresh()
        L.unlock("a", "l1-clone", 1)
        self.assertEqual(L.claim("b", "portal", 2), [])

    def test_every_kind_toasts(self):
        L = fresh(first_blood_on=False)
        for x in ("l1-clone", "f-wrongdir", "cheat-masher"):
            L.unlock("a", x, 1)
        L.clear("a", "c1", 2); L.clear("a", "capstone", 3)
        self.assertEqual([t["kind"] for t in L.pending("a")],
                         ["milestone", "funny", "funny", "challenge", "capstone"])

    def test_first_blood_toasts(self):
        L = fresh(class_clear_on=False)
        L.clear("a", "c1", 1)
        self.assertEqual([t["title"] for t in L.pending("a")][-1], "First blood!")


class Names(unittest.TestCase):
    def test_stable_and_unique(self):
        b = names.NameBook("seed")
        got = {u: b.name_for(u) for u in (f"s{i}" for i in range(200))}
        self.assertEqual(len(set(got.values())), 200)
        self.assertEqual(b.name_for("s5"), got["s5"])

    def test_same_seed_same_names_different_seed_differs(self):
        a, b, c = names.NameBook("x"), names.NameBook("x"), names.NameBook("y")
        self.assertEqual(a.name_for("u"), b.name_for("u"))
        self.assertNotEqual([a.name_for(f"u{i}") for i in range(10)], [c.name_for(f"u{i}") for i in range(10)])

    def test_fills_capacity_then_numbers(self):
        b = names.NameBook("s")
        for i in range(names.CAPACITY):
            b.name_for(f"u{i}")
        self.assertEqual(len(set(b.assigned.values())), names.CAPACITY)
        self.assertTrue(b.name_for("extra").startswith("Student"))

    def test_mapping_survives_reload(self):
        b = names.NameBook("s"); n = b.name_for("a")
        self.assertEqual(names.NameBook("s", b.mapping()).name_for("a"), n)

    def test_no_name_reveals_the_user(self):
        b = names.NameBook("s")
        self.assertNotIn("alice", b.name_for("alice").lower())


class Guards(unittest.TestCase):
    def setUp(self):
        self.v = guards.Verifier("secret")

    def event(self, ts=1000, nonce="n1", user="a", ev="e"):
        return user, ev, ts, nonce, guards.sign("secret", user, ev, ts, nonce)

    def test_good_event(self):
        self.assertEqual(self.v.verify(*self.event(), now=1001), (True, None))

    def test_forged(self):
        u, e, ts, n, _ = self.event()
        self.assertEqual(self.v.verify(u, e, ts, n, "0" * 64, 1001), (False, "forged"))
        self.assertEqual(self.v.verify(u, e, ts, n, None, 1001), (False, "forged"))

    def test_tampered_user_is_forged(self):
        _, e, ts, n, s = self.event()
        self.assertEqual(self.v.verify("b", e, ts, n, s, 1001), (False, "forged"))

    def test_stale(self):
        self.assertEqual(self.v.verify(*self.event(), now=5000), (False, "stale"))

    def test_replay(self):
        ev = self.event()
        self.v.verify(*ev, now=1001)
        self.assertEqual(self.v.verify(*ev, now=1002), (False, "replay"))

    def test_wrong_secret_is_forged(self):
        other = guards.Verifier("other")
        self.assertEqual(other.verify(*self.event(), now=1001), (False, "forged"))

    def test_rate_limit(self):
        r = guards.RateLimiter(limit=3, window=10)
        self.assertEqual([r.hit("a", t) for t in (0, 1, 2, 3)], [True, True, True, False])
        self.assertTrue(r.hit("b", 3))                # per key
        self.assertTrue(r.hit("a", 11))               # window slid


if __name__ == "__main__":
    unittest.main()
