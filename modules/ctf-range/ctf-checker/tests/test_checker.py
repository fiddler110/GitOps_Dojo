import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import checker  # noqa: E402
import gitref  # noqa: E402

ENV = {"STUDENT_COUNT": "3", "CTF_DEFEND_TARGETS": "customer-portal policy-bypass leaky-config",
       "CTF_PORT_STRIDE": "100", "CTF_HOST_PORT_BASE": "15000"}
SEED = "range-seed"


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


class ResetTests(unittest.TestCase):
    def setUp(self):
        self.cfg = checker.Config(dict(ENV, CTF_CONTROL_TOKEN="tok", STUDENT_PASSWORD_SEED=SEED))
        self.calls = []

    def _post(self, body, reset=None, limiter=None, path="/reset", keyed=True):
        if keyed and "user" in body and "key" not in body:
            body = dict(body, key=checker.user_key(body["user"], SEED))
        import http.client
        import threading
        fake = reset or (lambda cfg, u, t: (self.calls.append((u, t)) or (True, "redeployed")))
        handler = checker.make_handler(self.cfg, checker.RateLimiter(), threading.Lock(),
                                       reset_limiter=limiter or checker.RateLimiter(60), reset=fake)
        srv = checker.Server(("127.0.0.1", 0), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=5)
            c.request("POST", path, json.dumps(body), {"Content-Type": "application/json"})
            r = c.getresponse()
            return r.status, json.loads(r.read())
        finally:
            srv.shutdown()

    def test_reset_forwards_user_and_target(self):
        status, doc = self._post({"user": "student02", "target": "policy-bypass"})
        self.assertEqual((status, doc["ok"], self.calls), (200, True, [("student02", "policy-bypass")]))

    def test_reset_needs_a_known_target_and_user(self):
        self.assertEqual(self._post({"user": "student02"})[0], 400)
        self.assertEqual(self._post({"user": "student02", "target": "ping-tool"})[0], 400)
        self.assertEqual(self._post({"user": "student99", "target": "leaky-config"})[0], 400)
        self.assertEqual(self.calls, [])

    def test_reset_is_rate_limited_per_user(self):
        lim = checker.RateLimiter(60)
        body = {"user": "student01", "target": "leaky-config"}
        self.assertEqual(self._post(body, limiter=lim)[0], 200)
        self.assertEqual(self._post(body, limiter=lim)[0], 429)

    def test_reset_and_check_need_the_users_own_key(self):
        # REVIEW §1.1: naming a classmate without their key does nothing, and doesn't use up their turn.
        lim = checker.RateLimiter(60)
        bad_keys = (None, "", checker.user_key("student01", SEED), checker.user_key("student02", "other-seed"))
        for path in ("/reset", "/check"):
            for key in bad_keys:
                body = {"user": "student02", "target": "leaky-config"}
                if key is not None:
                    body["key"] = key
                self.assertEqual(self._post(body, limiter=lim, path=path, keyed=False)[0], 403, (path, key))
        self.assertEqual(self.calls, [])
        self.assertEqual(self._post({"user": "student02", "target": "leaky-config"}, limiter=lim)[0], 200)

    def test_no_seed_means_no_key_works(self):
        self.cfg = checker.Config(dict(ENV, CTF_CONTROL_TOKEN="tok"))
        body = {"user": "student02", "target": "leaky-config", "key": checker.user_key("student02", "")}
        self.assertEqual(self._post(body, keyed=False)[0], 403)
        self.assertEqual(self.calls, [])

    def test_key_matches_the_flags_copies_and_the_hook(self):
        root = os.path.join(os.path.dirname(__file__), "..", "..")
        for sub in ("ctf-flags", "ctf-controller"):
            ns = {}
            with open(os.path.join(root, sub, "flags.py"), encoding="utf-8") as fh:
                exec(compile(fh.read(), sub, "exec"), ns)
            self.assertEqual(ns["user_key"]("student02", SEED), checker.user_key("student02", SEED), sub)
        hook = os.path.join(root, "terminal", "account.d", "57-ctf-key.sh")
        with open(hook, encoding="utf-8") as fh:
            src = fh.read()
        code = src[src.index("python3 -c '") + len("python3 -c '"):]
        code = code[:code.index("'")]
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                             env=dict(os.environ, STUDENT_PASSWORD_SEED=SEED, CTF_USER="student02")).stdout
        self.assertEqual(out.strip(), checker.user_key("student02", SEED))

    def test_controller_refusal_is_a_409_with_its_message(self):
        status, doc = self._post({"user": "student01", "target": "leaky-config"},
                                 reset=lambda c, u, t: (False, "base image not present"))
        self.assertEqual((status, doc["ok"], doc["message"]), (409, False, "base image not present"))

    def test_unconfigured_token_is_refused(self):
        cfg = checker.Config(ENV)
        self.assertEqual(checker.do_reset(cfg, "student01", "leaky-config")[0], False)


if __name__ == "__main__":
    unittest.main()
