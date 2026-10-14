import collections
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import schedule as s  # noqa: E402

T = ["customer-portal", "policy-bypass", "leaky-config"]
U = [f"student{n:02d}" for n in range(1, 21)]


class TestSchedule(unittest.TestCase):
    def test_balance_20_students(self):
        counts = collections.Counter(tuple(o) for o in s.deal(U, T, "x").values())
        self.assertEqual(len(counts), 6)
        self.assertTrue(all(c in (3, 4) for c in counts.values()), counts)

    def test_every_order_is_a_permutation(self):
        for o in s.deal(U, T, "x").values():
            self.assertEqual(sorted(o), sorted(T))

    def test_deterministic(self):
        self.assertEqual(s.deal(U, T, "abc"), s.deal(U, T, "abc"))

    def test_seeds_differ(self):
        self.assertNotEqual(s.deal(U, T, "a"), s.deal(U, T, "b"))

    def test_offsets(self):
        rows = s.rows_for(T, T, 480, 0.5)
        self.assertEqual([r["start_offset_s"] for r in rows], [0, 240, 480])
        self.assertEqual([r["severity"] for r in rows], ["high", "medium", "low"])
        self.assertEqual([r["index"] for r in rows], [0, 1, 2])

    def test_build_shape(self):
        d = s.build(U[:2], T, "z", 480, 0.5)
        self.assertEqual(set(d), {"seed", "t0", "dwell_s", "stagger", "users"})
        self.assertIsNone(d["t0"])
        self.assertEqual(set(d["users"]), set(U[:2]))

    def test_no_targets(self):
        self.assertEqual(s.deal(U[:1], [], "x"), {"student01": []})


if __name__ == "__main__":
    unittest.main()
