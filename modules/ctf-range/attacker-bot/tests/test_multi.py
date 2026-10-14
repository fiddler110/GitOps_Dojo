import json
import os
import random
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import multi  # noqa: E402


class ParseTargetsTests(unittest.TestCase):
    def test_space_and_comma_separated(self):
        self.assertEqual(multi.parse_targets("a b c"), ["a", "b", "c"])
        self.assertEqual(multi.parse_targets("a, b ,c"), ["a", "b", "c"])

    def test_empty_is_empty(self):
        self.assertEqual(multi.parse_targets(""), [])
        self.assertEqual(multi.parse_targets(None), [])


class TargetPortTests(unittest.TestCase):
    def test_formula(self):
        self.assertEqual(multi.target_port(15000, 1, 100, 3), 15103)


class ScheduleRowsTests(unittest.TestCase):
    def test_bare_list(self):
        rows = [{"target": "a"}]
        self.assertEqual(multi.schedule_rows(rows, "student01"), rows)

    def test_wrapped_in_targets_key(self):
        doc = {"targets": [{"target": "a"}, {"target": "b"}]}
        self.assertEqual(len(multi.schedule_rows(doc, "student01")), 2)

    def test_full_users_document(self):
        doc = {"users": {"student01": [{"target": "a"}], "student02": [{"target": "b"}]}}
        self.assertEqual(multi.schedule_rows(doc, "student01"), [{"target": "a"}])

    def test_rows_without_a_target_are_dropped(self):
        doc = {"rows": [{"target": "a"}, {"no": "target"}]}
        self.assertEqual(multi.schedule_rows(doc, "x"), [{"target": "a"}])

    def test_garbage_is_empty(self):
        self.assertEqual(multi.schedule_rows("nope", "x"), [])
        self.assertEqual(multi.schedule_rows(None, "x"), [])


class FetchScheduleTests(unittest.TestCase):
    def test_sends_bearer_and_user_query(self):
        captured = {}

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return json.dumps({"targets": [{"target": "a"}]}).encode()

        def opener(req, timeout=5):
            captured["url"] = req.full_url
            captured["auth"] = req.get_header("Authorization")
            return FakeResp()

        rows = multi.fetch_schedule("http://ctrl:9100", "tok123", "student01", opener=opener)
        self.assertEqual(rows, [{"target": "a"}])
        self.assertIn("user=student01", captured["url"])
        self.assertEqual(captured["auth"], "Bearer tok123")

    def test_a_hiccup_is_an_empty_schedule_not_an_error(self):
        def opener(req, timeout=5):
            raise OSError("refused")

        self.assertEqual(multi.fetch_schedule("http://ctrl:9100", "tok", "student01", opener=opener), [])


class PolicyBypassRequestTests(unittest.TestCase):
    def test_green_phase_is_benign_or_denied_probe(self):
        rng = random.Random(1)
        with mock.patch.object(multi, "_call", return_value=(201, 40, {})):
            rec, outcome = multi.policy_bypass_request("http://t", "green", "seckey", rng)
        self.assertIn(outcome, ("probe", "recon"))
        self.assertIn(rec["outcome"], ("denied", "allowed"))

    def test_red_phase_allowed_is_dump_success_with_developer_caller(self):
        rng = random.Random(2)
        with mock.patch.object(multi, "_call", return_value=(201, 80, {"flag": "flag{x}"})):
            rec, outcome = multi.policy_bypass_request("http://t", "red", "seckey", rng)
        if rec["outcome"] == "allowed" and not (rng.random() < 0):  # exploit branch when not benign-sampled
            pass
        # force the exploit branch deterministically by patching random() to avoid the benign draw
        rng2 = mock.Mock()
        rng2.random.return_value = 0.9       # not benign
        rng2.choice.side_effect = lambda seq: seq[0]
        rng2.randrange.return_value = 1
        with mock.patch.object(multi, "_call", return_value=(201, 80, {"flag": "flag{x}"})):
            rec, outcome = multi.policy_bypass_request("http://t", "red", "seckey", rng2)
        self.assertEqual(outcome, "dump_success")
        self.assertEqual(rec["caller"], "developer")
        self.assertEqual(rec["asserted_tag"], "security-team")
        self.assertEqual(rec["outcome"], "allowed")
        self.assertEqual(rec["resource_group"], multi.PROTECTED_RG)

    def test_red_phase_denied_is_exploit_attempt(self):
        rng2 = mock.Mock()
        rng2.random.return_value = 0.9
        rng2.choice.side_effect = lambda seq: seq[0]
        rng2.randrange.return_value = 1
        with mock.patch.object(multi, "_call", return_value=(403, 40, {})):
            rec, outcome = multi.policy_bypass_request("http://t", "red", "seckey", rng2)
        self.assertEqual(outcome, "exploit_attempt")
        self.assertEqual(rec["outcome"], "denied")


class LeakyConfigRequestTests(unittest.TestCase):
    def test_green_is_benign_status_or_healthz(self):
        rng = random.Random(3)
        with mock.patch.object(multi, "_call", return_value=(200, 10, None)):
            rec, outcome = multi.leaky_config_request("http://t", "green", rng)
        self.assertEqual(outcome, "recon")
        self.assertIn(rec["path"], ("/status", "/healthz"))
        self.assertEqual(rec["auth"], "none")

    def test_red_with_leaked_creds_in_log_replays_them_and_breaches(self):
        rng2 = mock.Mock()
        rng2.random.return_value = 0.9
        rng2.choice.side_effect = lambda seq: seq[0]
        log_text = "INFO boot\nWARN leaked user=ops-admin pass=hunter2\n"
        calls = {"n": 0}

        def fake_call(method, url, body=None, headers=None, timeout=multi.TIMEOUT):
            calls["n"] += 1
            if "/admin/logs" in url:
                return 200, len(log_text), log_text
            self.assertEqual(headers["Authorization"], "Basic b3BzLWFkbWluOmh1bnRlcjI=")
            return 200, 50, {"ok": True}

        with mock.patch.object(multi, "_call", side_effect=fake_call):
            rec, outcome = multi.leaky_config_request("http://t", "red", rng2)
        self.assertEqual(outcome, "dump_success")
        self.assertEqual(rec["auth"], "basic-ok")
        self.assertEqual(rec["account"], "ops-admin")
        self.assertEqual(rec["ua"], multi.OPS_UA)
        self.assertNotIn(multi.OPS_UA, (multi.POLICY_UAS))  # the ops UA never appears in benign traffic

    def test_red_without_a_leak_is_an_exploit_attempt_not_a_breach(self):
        rng2 = mock.Mock()
        rng2.random.return_value = 0.9
        rng2.choice.side_effect = lambda seq: seq[0]
        with mock.patch.object(multi, "_call", return_value=(200, 5, "nothing interesting here")):
            rec, outcome = multi.leaky_config_request("http://t", "red", rng2)
        self.assertEqual(outcome, "exploit_attempt")
        self.assertIsNone(rec["account"])


class MakeRequestDispatchTests(unittest.TestCase):
    def test_unknown_target_falls_back_to_plain_traffic(self):
        rec, outcome = multi.make_request("some-future-target", "http://t", "green", lambda: None, "k",
                                          random.Random(1))
        self.assertEqual(outcome, "recon")
        self.assertIn("method", rec)

    def test_customer_portal_breach_reports_what_the_target_returned(self):
        def exploit_fn():
            return {"status": 200, "bytes": 999, "rows": [1, 2, 3]}

        rec, outcome = multi.make_request("customer-portal", "http://t", "red", exploit_fn, "k",
                                          random.Random(1))
        self.assertEqual(outcome, "dump_success")
        self.assertEqual(rec["status"], 200)
        self.assertEqual(rec["rows_returned"], 3)


class TargetPhaseTests(unittest.TestCase):
    def test_before_start_is_green(self):
        self.assertEqual(multi.target_phase(now=5, start_at=10, dwell_seconds=60, ramp_seconds=60), "green")

    def test_within_dwell_is_green_past_ramp_is_red(self):
        self.assertEqual(multi.target_phase(now=20, start_at=10, dwell_seconds=60, ramp_seconds=60), "green")
        self.assertEqual(multi.target_phase(now=200, start_at=10, dwell_seconds=60, ramp_seconds=60), "red")


class RunTargetTimerTests(unittest.TestCase):
    def test_waits_for_start_offset_then_posts_until_stopped(self):
        state = {"now": 0.0}
        posted = []

        def clock():
            return state["now"]

        def sleep(s):
            state["now"] += max(s, 0.01)

        calls = {"n": 0}

        def stop():
            calls["n"] += 1
            return calls["n"] > 5

        def post(user, target, outcome, rec):
            posted.append((user, target, outcome))

        row = {"target": "leaky-config", "index": 2, "start_offset_s": 5.0}
        multi.run_target_timer("student01", 0, row, "ctf-host", 15000, 100, started_at=0.0, post=post,
                               exploit_fn=lambda: None, sectm_key="k", dwell_seconds=60, ramp_seconds=60,
                               scale=0.01, clock=clock, sleep=sleep, rng=random.Random(1), stop=stop)
        self.assertTrue(posted)
        self.assertTrue(all(t == "leaky-config" for _, t, _ in posted))
        self.assertTrue(state["now"] >= 5.0 * 0.01)


class CustomerPortalRequestTests(unittest.TestCase):
    """Regressions from the first live run: recon/probe returned a bare record, a bool exploit_fn was
    read as a dict (never breached), and plain-text bodies were dropped."""

    def test_recon_and_probe_return_record_and_outcome(self):
        for outcome in ("recon", "probe"):
            rec, out = multi.customer_portal_request("http://x", outcome, None, random.Random(1))
            self.assertIsInstance(rec, dict)
            self.assertEqual(out, outcome)

    def test_bool_exploit_fn_with_observed_is_a_breach(self):
        def fn():
            return True
        fn.observed = lambda: {"status": 200, "bytes": 99, "rows": [1, 2, 3, 4, 5]}
        rec, out = multi.customer_portal_request("http://x", "exploit", fn, random.Random(1))
        self.assertEqual(out, "dump_success")
        self.assertEqual(rec["status"], 200)
        self.assertEqual(rec["rows_returned"], 5)

    def test_failed_exploit_is_not_a_breach(self):
        def fn():
            return False
        fn.observed = lambda: {"status": 200, "bytes": 5, "rows": []}
        _, out = multi.customer_portal_request("http://x", "exploit", fn, random.Random(1))
        self.assertNotEqual(out, "dump_success")

    def test_plain_text_body_is_returned_as_text(self):
        class R:
            status = 200
            def read(self): return b"line one\npassword=abc"
            def __enter__(self): return self
            def __exit__(self, *a): return False
        with mock.patch.object(multi.urllib.request, "urlopen", return_value=R()):
            status, size, body = multi._call("GET", "http://x/log")
        self.assertEqual((status, body), (200, "line one\npassword=abc"))


if __name__ == "__main__":
    unittest.main()
