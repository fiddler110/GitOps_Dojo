"""`dojo stop` saves feedback, scores and the roster to results/ first (engine/dojo/archive.py)."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from dojo import archive
from dojo.stackapi import StackError

ROSTER = [{"studentId": "student01", "name": "Ada", "ip": "10.0.0.5", "active": True},
          {"studentId": "testuser1", "name": "bot", "ip": "bot", "active": True}]
FEEDBACK = {"questions": {"q1": "Overall"}, "answers": [{"q1": 5, "comment": "great"}]}
RESULTS = {"students": [{"rank": 1, "user": "student01", "name": "Ada", "score": 40, "percent": 50,
                         "complete": False, "unlocks": 3, "cheats": [], "moments": []}]}


class ArchiveTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name) / "results"
        for p in (mock.patch.object(archive, "RESULTS_DIR", self.dir),
                  mock.patch.object(archive, "running", return_value=[SimpleNamespace(service="gateway"),
                                                                       SimpleNamespace(service="feedback")]),
                  mock.patch.object(archive.state, "read_current",
                                    return_value=SimpleNamespace(workshop="git-fundamentals", env_name=None,
                                                                 started_at=1_000_000.0,
                                                                 command="./dojo git-fundamentals"))):
            p.start()
            self.addCleanup(p.stop)

    def patch_data(self, roster=ROSTER, feedback=FEEDBACK, results=RESULTS):
        def pick(value):
            if isinstance(value, Exception):
                return mock.Mock(side_effect=value)
            return mock.Mock(return_value=value)
        for target, value in ((archive.results, ("roster", roster)), (archive, ("fetch_feedback", feedback)),
                              (archive.results, ("fetch_results", results))):
            name, v = value
            p = mock.patch.object(target, name, pick(v))
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.object(archive, "fetch_feedback_csv", return_value="q1,comment\n5,great\n")
        p.start()
        self.addCleanup(p.stop)

    def test_saves_a_folder_named_for_the_workshop_with_a_manifest(self):
        self.patch_data()
        d = archive.save(mock.Mock(), now=1_000_000.0 + 3600)
        self.assertTrue(d.name.endswith("_git-fundamentals"))
        m = json.loads((d / "manifest.json").read_text())
        self.assertEqual((m["workshop"], m["students"], m["demo_bots"], m["feedback_answers"], m["duration_minutes"]),
                         ("git-fundamentals", 1, 1, 1, 60.0))
        self.assertEqual(sorted(m["saved"]), ["achievements.csv", "achievements.json", "feedback.csv",
                                              "feedback.json", "roster.csv"])
        self.assertIn("5,great", (d / "feedback.csv").read_text())
        self.assertNotIn("10.0.0.5", (d / "roster.csv").read_text())  # no addresses

    def test_a_part_that_fails_is_recorded_and_the_rest_saved(self):
        self.patch_data(feedback=StackError("No 'feedback' container is running"))
        d = archive.save(mock.Mock())
        m = json.loads((d / "manifest.json").read_text())
        self.assertIn("feedback", m["skipped"])
        self.assertTrue((d / "achievements.json").exists())
        self.assertFalse((d / "feedback.csv").exists())

    def test_an_unused_stack_saves_nothing(self):
        self.patch_data(roster=[], feedback={"questions": {}, "answers": []}, results={"students": []})
        self.assertIsNone(archive.save(mock.Mock()))
        self.assertFalse(self.dir.exists())

    def test_two_saves_in_one_minute_do_not_overwrite(self):
        self.patch_data()
        a = archive.save(mock.Mock(), now=1_000_000.0)
        b = archive.save(mock.Mock(), now=1_000_000.0)
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
