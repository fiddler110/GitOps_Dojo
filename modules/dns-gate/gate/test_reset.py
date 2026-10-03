"""Student reset hook: teardown removes only what the student's own key owns; provision re-seeds."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate  # noqa: E402
import reset  # noqa: E402


class FakePdns:
    def __init__(self, zones):
        self.zones = zones          # name -> [rrset]
        self.calls = []

    def __call__(self, method, path, doc):
        self.calls.append((method, path, doc))
        if path.endswith("/zones"):
            return 200, [{"name": z} for z in self.zones]
        zone = reset.urllib.parse.unquote(path.rsplit("/", 1)[1])
        if zone not in self.zones:
            return 404, None
        if method == "DELETE":
            del self.zones[zone]
            return 204, None
        if method == "GET":
            return 200, {"rrsets": self.zones[zone]}
        for r in doc["rrsets"]:
            self.zones[zone] = [x for x in self.zones[zone] if (x["name"], x["type"]) != (r["name"], r["type"])]
            if r["changetype"] == "REPLACE":
                self.zones[zone].append({"name": r["name"], "type": r["type"],
                                         "records": r["records"]})
        return 204, None


def rr(name, rtype="A"):
    return {"name": name, "type": rtype, "records": [{"content": "1.2.3.4"}]}


def cfg(**env):
    base = {"DNS_GATE_USER_PARENTS": "dojo.test certs.dojo.test", "DNS_GATE_SHARED_ZONES": "certs.dojo.test",
            "DNS_GATE_RESET_RECORDS": "{user}.certs.dojo.test/A/172.30.0.20 *.{user}.certs.dojo.test/A/172.30.0.20"}
    base.update(env)
    return gate.Config(base)


class ResetTests(unittest.TestCase):
    def setUp(self):
        self.p = FakePdns({
            "dojo.test.": [rr("student01-app.dojo.test.")],
            "student01.dojo.test.": [rr("student01.dojo.test.", "SOA")],
            "lab.student01.dojo.test.": [],
            "student011.dojo.test.": [],
            "student02.dojo.test.": [],
            "certs.dojo.test.": [rr("student01.certs.dojo.test."), rr("*.student01.certs.dojo.test."),
                                 rr("_acme-challenge.student01.certs.dojo.test.", "TXT"),
                                 rr("student011.certs.dojo.test."), rr("student02.certs.dojo.test.")],
        })

    def test_teardown_only_touches_the_students_names(self):
        detail = reset.run(self.p, "student01", "teardown", cfg())
        self.assertEqual(detail, "2 zone(s) deleted, 3 record set(s) cleared")
        self.assertEqual(sorted(self.p.zones), ["certs.dojo.test.", "dojo.test.", "student011.dojo.test.",
                                                "student02.dojo.test."])
        self.assertEqual([r["name"] for r in self.p.zones["certs.dojo.test."]],
                         ["student011.certs.dojo.test.", "student02.certs.dojo.test."])
        self.assertEqual(self.p.zones["dojo.test."][0]["name"], "student01-app.dojo.test.")   # CI zone left
        self.assertEqual(reset.run(self.p, "student01", "teardown", cfg()), "0 zone(s) deleted, 0 record set(s) cleared")

    def test_provision_reseeds(self):
        reset.run(self.p, "student01", "teardown", cfg())
        self.assertEqual(reset.run(self.p, "student01", "provision", cfg()), "2 seeded record set(s) back")
        names = {r["name"] for r in self.p.zones["certs.dojo.test."]}
        self.assertIn("student01.certs.dojo.test.", names)
        self.assertIn("*.student01.certs.dojo.test.", names)
        self.assertEqual(reset.run(self.p, "student01", "provision", cfg(DNS_GATE_RESET_RECORDS="")), "nothing to seed")

    def test_bad_records_setting(self):
        for bad in ("x.certs.dojo.test/A/1.2.3.4", "{user}.x/A", "{user}.x/1/2"):
            with self.assertRaises(ValueError, msg=bad):
                reset.parse_records(bad)

    def test_errors_raise(self):
        with self.assertRaises(RuntimeError):
            reset.run(lambda m, p, d: (500, None), "student01", "teardown", cfg())


if __name__ == "__main__":
    unittest.main()
