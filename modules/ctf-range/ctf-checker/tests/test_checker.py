import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import checker  # noqa: E402
import gitref  # noqa: E402

ENV = {"STUDENT_COUNT": "3", "CTF_DEFEND_TARGETS": "customer-portal policy-bypass leaky-config",
       "CTF_PORT_STRIDE": "100", "CTF_HOST_PORT_BASE": "15000"}


class Cfg(unittest.TestCase):
    def setUp(self):
        self.cfg = checker.Config(ENV)

    def test_ports(self):
        self.assertEqual(self.cfg.slot_port("student01", "customer-portal"), 15000)
        self.assertEqual(self.cfg.slot_port("student03", "leaky-config"), 15202)

    def test_check_validation(self):
        self.assertEqual(checker.validate_check({"user": "student02"}, self.cfg), ("student02", None))
        for bad in ({}, {"user": "../x"}, {"user": "student09"}, {"user": "A b"}):
            self.assertIsNotNone(checker.validate_check(bad, self.cfg)[1])

    def test_gate_validation(self):
        ok = {"user": "student01", "target": "leaky-config", "ref": "abc123"}
        self.assertIsNone(checker.validate_gate(ok, self.cfg)[1])
        for k, v in (("target", "ping-tool"), ("ref", "--upload-pack=x"), ("ref", "a..b"),
                     ("ref", ""), ("user", "nobody")):
            self.assertIsNotNone(checker.validate_gate(dict(ok, **{k: v}), self.cfg)[1], (k, v))

    def test_ref_rules(self):
        self.assertTrue(gitref.safe_ref("main"))
        self.assertFalse(gitref.safe_ref("-x"))
        self.assertFalse(gitref.safe_ref("a b"))
        self.assertFalse(gitref.safe_ref("x" * 201))


class Verdicts(unittest.TestCase):
    def test_exit_codes_win(self):
        j = '{"verdict": "contained", "note": "n"}'
        self.assertEqual(checker.parse_check_output(j, 0)[0], "exploitable")
        self.assertEqual(checker.parse_check_output(j, 1)[0], "contained")
        self.assertEqual(checker.parse_check_output(j, 3)[0], "broke-normal-use")
        self.assertEqual(checker.parse_check_output(j, 2)[0], "unreachable")

    def test_garbage(self):
        self.assertEqual(checker.parse_check_output("boom", 7)[0], "unreachable")

    def test_run_check_timeout_and_argv(self):
        seen = {}

        def runner(argv, **kw):
            seen["argv"] = argv
            return subprocess.CompletedProcess(argv, 0, stdout='{"verdict":"exploitable","note":"x"}')
        v, _ = checker.run_check("policy-bypass", "http://h:1", "F", "K", runner=runner)
        self.assertEqual(v, "exploitable")
        self.assertIn("--legit-key", seen["argv"])

        def boom(argv, **kw):
            raise subprocess.TimeoutExpired(argv, 1)
        self.assertEqual(checker.run_check("x", "u", runner=boom)[0], "unreachable")


class Rate(unittest.TestCase):
    def test_limit(self):
        t = [0.0]
        r = checker.RateLimiter(3.0, clock=lambda: t[0])
        self.assertTrue(r.allow("a"))
        self.assertFalse(r.allow("a"))
        self.assertTrue(r.allow("b"))
        t[0] = 3.1
        self.assertTrue(r.allow("a"))


if __name__ == "__main__":
    unittest.main()
