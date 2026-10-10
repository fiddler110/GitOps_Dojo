import os
import random
import sys
import unittest
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "_shared"))
import bot  # noqa: E402
import probes  # noqa: E402
import traffic  # noqa: E402


class FakeClient:
    def __init__(self):
        self.posted = []

    def post(self, doc):
        self.posted.append(doc)
        return True


def attacker():
    return bot.Swarm(["student01"], rng=random.Random(1), started_at=0.0).attackers[0]


class ClassShapeTests(unittest.TestCase):
    def test_scan_noise_is_background_and_varies_agents(self):
        rng = random.Random(3)
        recs = [traffic.scan_request(rng) for _ in range(300)]
        self.assertTrue(all(r["klass"] == "scan" and r["path"].startswith("/") and not r["query"] for r in recs))
        self.assertGreater(len({r["ua"] for r in recs}), 4)
        paths = {r["path"] for r in recs}
        self.assertTrue({"/robots.txt", "/.env", "/wp-login.php", "/favicon.ico", "/server-status"} <= paths)
        self.assertEqual({r["status"] for r in recs if r["path"] == "/.env"}, {404})

    def test_probe_class_has_fuzzing_and_login_guessing(self):
        rng = random.Random(4)
        recs = [traffic.probe_request(rng, bonus_on=False) for _ in range(500)]
        tags = {r["tag"] for r in recs}
        self.assertIn("SQL meta-characters in parameter q", tags)
        self.assertIn("SQL boolean test in parameter q", tags)
        self.assertIn("failed login (credential guessing)", tags)
        login = next(r for r in recs if r["path"] == "/login")
        self.assertEqual((login["method"], login["status"]), ("POST", 401))
        self.assertTrue(all(r["klass"] == "probe" for r in recs))

    def test_no_probe_is_the_real_payload(self):
        rng = random.Random(5)
        import dump
        for _ in range(500):
            r = traffic.probe_request(rng, bonus_on=True)
            self.assertNotIn(urllib.parse.urlencode({"q": dump.PAYLOAD}), r["query"])
            self.assertLess(r["bytes"], 2000)

    def test_bonus_off_never_names_bonus_paths_anywhere(self):
        rng = random.Random(6)
        recs = [traffic.request_for(o, rng, bonus_on=False) for o in ("recon", "probe") * 800]
        self.assertFalse({r["path"] for r in recs} & set(probes.BONUS_PATHS))

    def test_bonus_on_draws_them_with_the_data_at_rest_tag(self):
        rng = random.Random(6)
        recs = [traffic.probe_request(rng, bonus_on=True) for _ in range(1000)]
        bonus = [r for r in recs if r["path"] in probes.BONUS_PATHS]
        self.assertTrue(0.2 < len(bonus) / len(recs) < 0.4)
        self.assertEqual({r["tag"] for r in bonus}, {"sensitive file requested"})

    def test_exploit_request_carries_observed_status_size_rows(self):
        obs = {"status": 200, "bytes": 48213, "rows": [{"a": 1}] * 40}
        r = traffic.exploit_request("q=%25%27+OR", obs, breached=True)
        self.assertEqual((r["status"], r["bytes"], r["rows_returned"]), (200, 48213, 40))
        self.assertEqual(r["tag"], "bulk data egress")
        self.assertEqual(r["query"], "q=%25%27+OR")
        self.assertEqual(r["klass"], "exploit")

    def test_failed_exploit_is_tagged_as_the_payload_with_no_rows(self):
        r = traffic.exploit_request("q=x", {"status": 200, "bytes": 14, "rows": []}, breached=False)
        self.assertEqual((r["rows_returned"], r["tag"]), (0, "SQL injection payload in parameter q"))

    def test_unreachable_target_is_a_gateway_error_not_a_breach(self):
        self.assertEqual(traffic.exploit_request("q=x", None)["status"], 502)

    def test_tags_never_name_a_fix(self):
        every = {t[5] for t in traffic.SCAN + traffic.FUZZ} | {traffic.BONUS_TAG, "bulk data egress",
                                                              "SQL injection payload in parameter q"}
        for tag in every:
            for word in ("parameteriz", "prepared", "hash", "patch", "sanitiz", "escape"):
                self.assertNotIn(word, tag.lower())


class PostEventShapeTests(unittest.TestCase):
    def test_dump_success_reports_what_the_bot_observed_to_the_ctf_source(self):
        clients = {"ctf": FakeClient(), "soc": FakeClient()}
        obs = {"status": 200, "bytes": 9000, "rows": [{}] * 12}
        bot.post_event(clients, attacker(), "dump_success", "customer-portal", observed=obs)
        doc = clients["ctf"].posted[0]
        self.assertEqual((doc["method"], doc["path"], doc["status"], doc["bytes"], doc["rows_returned"]),
                         ("GET", "/search", 200, 9000, 12))
        self.assertIn("OR", urllib.parse.unquote_plus(doc["query"]))
        self.assertEqual(doc["tag"], "bulk data egress")

    def test_hint_burst_is_all_probing_no_background_scans(self):
        clients = {"ctf": FakeClient(), "soc": FakeClient()}
        rng = random.Random(2)
        for _ in range(100):
            bot.post_event(clients, attacker(), "probe", "customer-portal", rng=rng, focused=True)
        self.assertEqual({d["klass"] for d in clients["soc"].posted}, {"probe"})

    def test_exploit_fn_exposes_the_observed_response(self):
        import dump
        real = dump.dump_detail
        dump.dump_detail = lambda url, timeout=5: {"status": 200, "bytes": 77, "rows": [{"x": 1}], "query": "q"}
        try:
            fn = bot.make_exploit_fn("http://x")
            self.assertTrue(fn())
            self.assertEqual(fn.observed()["bytes"], 77)
            dump.dump_detail = lambda url, timeout=5: {"status": 200, "bytes": 14, "rows": [], "query": "q"}
            self.assertFalse(fn())
            self.assertEqual(fn.observed()["rows"], [])
        finally:
            dump.dump_detail = real


if __name__ == "__main__":
    unittest.main()
