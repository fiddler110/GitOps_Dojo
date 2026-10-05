"""Unit tests for gitref's validation and argv builders:

    python3 -B -m unittest discover -s modules/ctf-range/ctf-builder/tests -p 'test_*.py'

No git, no subprocess, no daemon needed — everything here is pure.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import gitref as g  # noqa: E402


class TestSafeUser(unittest.TestCase):
    def test_roster_style_accepted(self):
        for user in ("student01", "student40", "a"):
            self.assertTrue(g.safe_user(user), user)

    def test_rejected(self):
        for user in ("", "Student01", "student-01", "../etc/passwd",
                      "student01;id", "student01 ", "a" * 33, "0student"):
            self.assertFalse(g.safe_user(user), user)


class TestSafeRef(unittest.TestCase):
    def test_branches_and_shas_accepted(self):
        for ref in ("main", "feature/fix-sqli", "a" * 40, "abc123.def"):
            self.assertTrue(g.safe_ref(ref), ref)

    def test_option_injection_rejected(self):
        for ref in ("-x", "--upload-pack=/bin/sh", "--help"):
            self.assertFalse(g.safe_ref(ref), ref)

    def test_other_bad_refs_rejected(self):
        for ref in ("", "a..b", "a b", "ref\twith\ttab", "a" * 201,
                    "/absolute", "x.lock", "a\nb"):
            self.assertFalse(g.safe_ref(ref), ref)


class TestArgvBuilders(unittest.TestCase):
    def test_clone_argv_uses_double_dash_and_no_shell_string(self):
        argv = g.clone_argv("http://git-server:3000/student01/customer-portal.git", "/tmp/x")
        self.assertIsInstance(argv, list)
        self.assertEqual(argv[0], "git")
        self.assertIn("--", argv)
        # The URL and dest are the last two positional args, after "--".
        self.assertEqual(argv[-2:], ["http://git-server:3000/student01/customer-portal.git",
                                      "/tmp/x"])

    def test_checkout_argv_uses_double_dash(self):
        # ref before `--` (a revision checkout), not after -- `checkout --
        # <ref>` treats <ref> as a pathspec and fails on any real commit.
        argv = g.checkout_argv("/tmp/x", "deadbeef")
        self.assertEqual(argv, ["git", "-C", "/tmp/x", "checkout", "--quiet", "deadbeef", "--"])

    def test_repo_url_for(self):
        url = g.repo_url_for("student01", "git-server:3000", "customer-portal")
        self.assertEqual(url, "http://git-server:3000/student01/customer-portal.git")


if __name__ == "__main__":
    unittest.main()
