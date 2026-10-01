"""dns-as-code pack: each wired item fires on the command or event the labs produce, and not on lookalikes."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "catalog"))
import catalog  # noqa: E402
import ledger as lg  # noqa: E402
import matcher as mt  # noqa: E402

PACK = os.path.join(HERE, "..", "..", "..", "workshops", "dns-as-code")
SHARED = os.path.join(HERE, "..", "catalog", "shared.json")
R = "dns-team/dns-as-code"


def ids(ev):
    c = catalog.load(PACK, SHARED)[0]
    return mt.Matcher(lg.Ledger(c, lg.Config()).index).match(ev)


def sh(cmd, exit=0, **kw):
    return ids(mt.shell_event(dict(cmd=cmd, exit=exit, **kw)))


def fj(kind, payload):
    return ids(mt.forgejo_event(kind, payload))


class DnsPack(unittest.TestCase):
    def test_dnscontrol(self):
        self.assertIn("d1-preview", sh("dnscontrol preview"))
        self.assertIn("d1-push", sh("dnscontrol push"))
        self.assertNotIn("d1-push", sh("dnscontrol push", 1))
        self.assertIn("d1-dot", sh("dnscontrol preview", 1))
        self.assertNotIn("d1-dot", sh("dnscontrol preview", 0))
        self.assertIn("d6-preview", sh("dnscontrol preview", merging=True))
        self.assertNotIn("d6-preview", sh("dnscontrol preview"))

    def test_dnsctl_forms(self):
        for pre in ("python3 scripts/dnsctl.py", "dnsc", "python3 ~/lab/dns-as-code/scripts/dnsctl.py"):
            self.assertIn("d4-wizard", sh(pre + " record add u-api.dojo.test"))
            self.assertIn("d4-submit", sh(pre + ' submit "Add x"'))
            self.assertIn("d5-history", sh(pre + " history"))
            self.assertIn("d5-rollback", sh(pre + " rollback 7"))
            self.assertNotIn("d4-wizard", sh(pre + " record add x", 1))
        self.assertEqual(sh("echo dnsc status"), [])

    def test_funny_from_output(self):
        doubled = "+ CREATE www.amy.dojo.test.amy.dojo.test A 10.0.0.1"
        self.assertIn("f-dot2", sh("dnscontrol preview", 0, out=doubled))
        self.assertNotIn("f-dot2", sh("dnscontrol preview", 0, out="+ CREATE www.amy.dojo.test A 10.0.0.1"))
        self.assertNotIn("f-dot2", sh("echo x", 0, out=doubled))
        self.assertIn("f-nxdomain", sh("dig @dns-server nope.amy.dojo.test", 0, out=";; ->>HEADER<<- status: NXDOMAIN"))
        self.assertNotIn("f-nxdomain", sh("dig @dns-server x +short", 0, out=""))

    def test_git(self):
        self.assertIn("d3-clone", sh("git clone http://git-server:3000/dns-team/dns-as-code.git"))
        self.assertNotIn("d3-clone", sh("git clone http://git-server:3000/other/repo.git"))
        self.assertIn("d3-blocked", sh("git push", 1, branch="main", in_repo="1"))
        self.assertNotIn("d3-blocked", sh("git push", 1, branch="add-x", in_repo="1"))
        self.assertIn("d2-revert", sh("git revert --no-edit HEAD"))
        self.assertIn("d6-conflict", sh("git merge conflict-a", 1, merging_after="1"))
        self.assertNotIn("d6-conflict", sh("git merge conflict-a", 1))
        self.assertIn("d6-resolved", sh("git commit", merging="1"))
        self.assertNotIn("d6-resolved", sh("git commit -m x"))
        self.assertIn("d2-drift", sh("curl -s -X PATCH -H 'X-API-Key: k' http://dns-api:8081/api/v1/servers/localhost/zones/u.dojo.test."))

    def test_forgejo(self):
        repo = {"full_name": R}
        pr = {"pull_request": {"user": {"login": "amy"}, "base": {"ref": "main"}}, "repository": repo,
              "sender": {"login": "amy"}}
        self.assertIn("d3-pr", fj("pull_request", dict(pr, action="opened")))
        self.assertIn("d3-applied", fj("pull_request", dict(pr, action="closed",
                                                             pull_request=dict(pr["pull_request"], merged=True))))
        self.assertIn("d3-review", fj("pull_request_approved", {"repository": repo, "sender": {"login": "amy"},
                                                                "pull_request": pr["pull_request"]}))
        other = dict(pr, action="opened", repository={"full_name": "amy/x"})
        self.assertNotIn("d3-pr", fj("pull_request", other))


if __name__ == "__main__":
    unittest.main()


def dn(event, **kw):
    return ids(mt.dns_event(dict(source="dns", event=event, user="amy", zone="amy.dojo.test", **kw)))


class DnsAdapterEvents(unittest.TestCase):
    def test_zone_patches(self):
        self.assertIn("d1-add", dn("zone_patch", first=False, created=1))
        self.assertNotIn("d1-add", dn("zone_patch", first=True, created=5))
        self.assertIn("d1-change", dn("zone_patch", first=False, changed=1))
        self.assertIn("d1-remove", dn("zone_patch", first=False, deleted=1))
        self.assertIn("f-ttl", dn("zone_patch", created=1, min_ttl=30))
        self.assertNotIn("f-ttl", dn("zone_patch", created=1, min_ttl=300))
        self.assertNotIn("f-ttl", dn("zone_patch", deleted=1))

    def test_someone_elses_zone_does_not_count(self):
        ev = mt.dns_event(dict(source="dns", event="zone_patch", user="amy", zone="ben.dojo.test", first=False, created=1))
        self.assertNotIn("d1-add", ids(ev))

    def test_refusal(self):
        self.assertIn("f-rejected", dn("api_refused"))

    def test_junk_is_dropped(self):
        for bad in ({"event": "nope", "user": "a", "zone": "z"}, {"event": "zone_patch", "zone": "z"}, "x", None):
            self.assertIsNone(mt.dns_event(bad))

    def test_rollback_pr_merged(self):
        pr = {"action": "closed", "sender": {"login": "amy"}, "repository": {"full_name": R},
              "pull_request": {"user": {"login": "amy"}, "merged": True, "base": {"ref": "main"}, "head": {"ref": "dns/revert-abc"}}}
        self.assertIn("d5-gone", fj("pull_request", pr))
        pr["pull_request"]["head"]["ref"] = "add-www"
        self.assertNotIn("d5-gone", fj("pull_request", pr))


import importlib.util  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402

import challenges  # noqa: E402

_spec = importlib.util.spec_from_file_location("dnszone", os.path.join(HERE, "..", "plugins", "dns", "dnszone.py"))
dnszone = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dnszone)


def zone_doc(zone, records):
    """A PowerDNS zone document from [(name, type, content)]."""
    rrsets = {}
    for name, typ, content in records:
        rrsets.setdefault((name, typ), []).append({"content": content, "disabled": False})
    return {"rrsets": [{"name": n, "type": t, "records": r} for (n, t), r in rrsets.items()]}


class DnsChallenges(unittest.TestCase):
    def setUp(self):
        self.cat = catalog.load(PACK, SHARED)[0]
        self.runner = challenges.Runner(challenges.load_plugins([os.path.join(HERE, "..", "plugins", "dns")]),
                                        os.path.join(PACK, "achievements", "seeds"), None, lambda: 0)
        self.mod = self.runner.verbs["zone_records"][1]     # the runner's own copy of the plug-in
        self.orig = self.mod._get

    def tearDown(self):
        self.mod._get = self.orig

    def run_verify(self, cid, doc):
        ch = next(c for c in self.cat["challenges"] + [self.cat["capstone"]] if c["id"] == cid)
        self.mod._get = lambda zone: doc
        return self.runner.verify(ch, "amy")

    def base(self, extra):
        z = "amy.dojo.test."
        return zone_doc(z, [(z, "SOA", "x"), (z, "NS", "ns1.dojo.test."), (z, "A", "203.0.113.10"),
                            ("mail." + z, "A", "203.0.113.20")] + extra)

    def test_c1(self):
        ch = next(c for c in self.cat["challenges"] if c["id"] == "c1")
        label = self.runner.values(ch, "amy")["label"]
        z = "amy.dojo.test."
        good = self.base([("www." + z, "A", "203.0.113.10"), (f"{label}.{z}", "CNAME", "www." + z)])
        bad = self.base([("www." + z, "A", "203.0.113.10"), (f"{label}.{z}", "CNAME", "www.amy.dojo.test.amy.dojo.test.")])
        self.assertTrue(self.run_verify("c1", good)["passed"])
        self.assertFalse(self.run_verify("c1", bad)["passed"])
        self.assertFalse(self.run_verify("c1", None)["passed"])

    def test_c2(self):
        ch = next(c for c in self.cat["challenges"] if c["id"] == "c2")
        n = self.runner.values(ch, "amy")["n"]
        z = "amy.dojo.test."
        ok = self.base([("app." + z, "A", f"10.20.0.{n}"), ("www." + z, "CNAME", "app." + z)])
        old = self.base([("app." + z, "A", f"10.20.0.{n}"), ("www." + z, "A", "10.10.0.5")])
        self.assertTrue(self.run_verify("c2", ok)["passed"])
        self.assertFalse(self.run_verify("c2", old)["passed"])

    def test_capstone(self):
        v = self.runner.values(self.cat["capstone"], "amy")
        z = "amy.dojo.test."
        rows = [("www." + z, "A", "203.0.113.10"), (f"{v['good']}.{z}", "A", f"198.51.100.{v['good_octet']}")]
        self.assertTrue(self.run_verify("capstone", self.base(rows))["passed"])
        with_bad = self.base(rows + [(f"{v['bad']}.{z}", "A", f"192.0.2.{v['bad_octet']}")])
        self.assertFalse(self.run_verify("capstone", with_bad)["passed"])
        self.assertFalse(self.run_verify("capstone", self.base(rows[:1]))["passed"])

    def test_a_check_never_reads_another_students_zone(self):
        ok, msg = dnszone.zone_records(None, {"zone": "ben.dojo.test", "records": []}, {"user": "amy"})
        self.assertFalse(ok)

    def test_seed_plans_are_complete(self):
        seeds = os.path.join(PACK, "achievements", "seeds")
        for ch in self.cat["challenges"] + [self.cat["capstone"]]:
            plan = json.load(open(os.path.join(seeds, ch["seed_plan"])))
            vals = self.runner.values(ch, "amy")
            for c in plan["commits"]:
                for f in c["files"]:
                    text = challenges.fill_text(open(os.path.join(seeds, f["from"])).read(), vals)
                    self.assertNotRegex(text, re.compile(r"\{(user|label|n|good|bad|good_octet|bad_octet)\}"), f["from"])
            self.assertEqual(challenges.fill_text(plan["repo"], vals), "amy/challenge-zone")
