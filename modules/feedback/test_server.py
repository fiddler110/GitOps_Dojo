import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import server  # noqa: E402
from server import Denied, Store  # noqa: E402


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.t = 0
        self.s = Store(clock=lambda: self.t)

    def test_submit_replaces_and_summarises(self):
        self.s.submit("a", {"ratings": {"pace": 4, "overall": 5}, "comment": "good"})
        self.t = 1
        self.s.submit("b", {"ratings": {"pace": 2}, "comment": ""})
        self.s.submit("a", {"ratings": {"pace": 5}, "comment": "better"})
        sm = self.s.summary()
        self.assertEqual(sm["responses"], 2)
        pace = sm["questions"][0]
        self.assertEqual((pace["count"], pace["mean"], pace["counts"]), (2, 3.5, [0, 1, 0, 0, 1]))
        self.assertEqual(sm["comments"], ["better"])
        self.assertEqual(self.s.mine("a")["comment"], "better")
        self.assertIsNone(self.s.mine("c"))

    def test_rejects_bad_input(self):
        for doc in ({"ratings": {"pace": 6}}, {"ratings": {"pace": True}}, {"ratings": {}, "comment": " "},
                    {"ratings": "x"}, {"ratings": {"pace": "3"}}):
            with self.assertRaises(Denied):
                self.s.submit("a", dict(doc, comment=doc.get("comment", "")))

    def test_unknown_question_ignored_and_comment_capped(self):
        self.s.submit("a", {"ratings": {"nope": 3, "pace": 3}, "comment": "x" * 5000})
        row = self.s.rows()[0]
        self.assertEqual(list(row["ratings"]), ["pace"])
        self.assertEqual(len(row["comment"]), server.MAX_COMMENT)

    def test_csv_blocks_formulas_and_has_no_user(self):
        self.s.submit("alice", {"ratings": {"pace": 3}, "comment": "=1+1"})
        out = server.export_csv(self.s.rows())
        self.assertIn("'=1+1", out)
        self.assertNotIn("alice", out)

    def test_persistence(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "f.json")
            Store(p).submit("a", {"ratings": {"pace": 3}, "comment": ""})
            self.assertEqual(Store(p).mine("a")["ratings"], {"pace": 3})


if __name__ == "__main__":
    unittest.main()
