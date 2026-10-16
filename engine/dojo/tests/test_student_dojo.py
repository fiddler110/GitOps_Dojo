"""The student's `dojo` command (engine/web-terminal/dojo): discovers commands in cmd.d, lists them, runs them."""
import os
import stat
import subprocess
import sys
import tempfile
import unittest

DOJO = os.path.join(os.path.dirname(__file__), "..", "..", "web-terminal", "dojo")


def make(d, name, body):
    p = os.path.join(d, name)
    with open(p, "w") as f:
        f.write(body)
    os.chmod(p, 0o755)
    return p


class StudentDojoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        self.addCleanup(self.tmp.cleanup)

    def run_dojo(self, *args):
        env = dict(os.environ, DOJO_CMD_DIR=self.d)
        return subprocess.run([sys.executable, "-B", DOJO, *args], capture_output=True, text=True, env=env)

    def test_help_lists_commands_with_their_summaries(self):
        make(self.d, "greet", "#!/bin/sh\n# dojo-summary: say hello\necho hi\n")
        make(self.d, "challenge", "#!/bin/sh\n# dojo-summary(challenge): start one\n# dojo-summary(check): check one\n")
        os.symlink(os.path.join(self.d, "challenge"), os.path.join(self.d, "check"))
        r = self.run_dojo("help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("say hello", r.stdout)
        self.assertRegex(r.stdout, r"challenge\s+start one")
        self.assertRegex(r.stdout, r"check\s+check one")
        self.assertLess(r.stdout.index("challenge"), r.stdout.index("greet"))  # known names come first

    def test_runs_a_command_with_its_args_and_name(self):
        make(self.d, "echo-args", '#!/bin/sh\necho "$DOJO_SUBCOMMAND:$*"\n')
        r = self.run_dojo("echo-args", "a", "b")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "echo-args:a b"))

    def test_symlink_keeps_the_subcommand_name(self):
        make(self.d, "real", '#!/bin/sh\necho "$DOJO_SUBCOMMAND $(basename "$0")"\n')
        os.symlink(os.path.join(self.d, "real"), os.path.join(self.d, "alias"))
        self.assertEqual(self.run_dojo("alias").stdout.strip(), "alias alias")

    def test_help_command_runs_that_commands_help(self):
        make(self.d, "tool", '#!/bin/sh\necho "args=$*"\n')
        self.assertEqual(self.run_dojo("help", "tool").stdout.strip(), "args=--help")

    def test_unknown_command_suggests_a_near_one(self):
        make(self.d, "challenge", "#!/bin/sh\n")
        r = self.run_dojo("chalenge")
        self.assertEqual(r.returncode, 2)
        self.assertIn("dojo challenge", r.stderr)

    def test_dangling_and_non_executable_entries_are_hidden(self):
        os.symlink("/nonexistent/target", os.path.join(self.d, "gone"))
        os.chmod(make(self.d, "plain", "#!/bin/sh\n"), stat.S_IRUSR | stat.S_IWUSR)
        self.assertNotIn("gone", self.run_dojo("help").stdout)
        self.assertNotIn("plain", self.run_dojo("help").stdout)
        self.assertEqual(self.run_dojo("gone").returncode, 2)

    def test_no_commands_still_helps(self):
        r = self.run_dojo()
        self.assertEqual(r.returncode, 0)
        self.assertIn("dojo help", r.stdout)

    def test_complete_prints_name_colon_summary(self):
        make(self.d, "greet", "#!/bin/sh\n# dojo-summary: say: hello\n")
        self.assertIn("greet:say - hello", self.run_dojo("--complete").stdout.splitlines())


if __name__ == "__main__":
    unittest.main()
