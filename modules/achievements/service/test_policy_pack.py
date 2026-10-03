"""cloud-policy-as-code pack: each wired item fires on the command or event the labs produce, and not on lookalikes;
the `verify` milestones, the challenges and the capstone run against a faked Dojo Cloud API and a faked Forgejo;
and the verbs they need (plugins/cloud `cloud_policy`, plugins/ci `ci_run` and `tree_file_contains`) on their own.
Run from this directory:  python3 -B -m unittest test_policy_pack"""
import datetime
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "catalog"))
import catalog  # noqa: E402
import challenges  # noqa: E402
import ledger as lg  # noqa: E402
import matcher as mt  # noqa: E402

PACK = os.path.join(HERE, "..", "..", "..", "workshops", "cloud-policy-as-code")
SHARED = os.path.join(HERE, "..", "catalog", "shared.json")
CLOUD = os.path.join(HERE, "..", "plugins", "cloud")
CI = os.path.join(HERE, "..", "plugins", "ci")
CORE = os.path.join(HERE, "..", "achievements")
SEEDS = os.path.join(PACK, "achievements", "seeds")
FORK = "amy/cloud-policy-as-code"
SUB = "/subscriptions/0000-amy"


def cat():
    return catalog.load(PACK, SHARED)[0]


def match(ev, have=()):
    return mt.Matcher(lg.Ledger(cat(), lg.Config()).index).match(ev, have=set(have))


def sh(cmd, exit=0, have=(), **kw):
    return match(mt.shell_event(dict(cmd=cmd, exit=exit, **kw)), have)


def cloud(event, have=(), user="amy", **kw):
    return match(mt.adapter_event(dict(source="cloud", event=event, user=user, **kw)), have)


def pr(action, head, repo=FORK, user="amy", have=()):
    body = {"action": "closed" if action == "merged" else action, "repository": {"full_name": repo},
            "sender": {"login": user}, "pull_request": {"user": {"login": user}, "merged": action == "merged",
                                                         "base": {"ref": "main"}, "head": {"ref": head}}}
    return match(mt.forgejo_event("pull_request", body), have)


def push(repo=FORK, branch="main", user="amy", have=()):
    return match(mt.forgejo_event("push", {"ref": f"refs/heads/{branch}", "repository": {"full_name": repo},
                                           "pusher": {"login": user}, "sender": {"login": user}}), have)


class Catalog(unittest.TestCase):
    def test_validates_with_the_module_verbs(self):
        import validate
        c, warnings = catalog.load(PACK, SHARED, known_verbs=validate.known_verbs())
        self.assertEqual(warnings, [])
        self.assertEqual([lab["id"] for lab in c["labs"]], [f"lab{i}" for i in range(13)])
        self.assertTrue(all(m.get("core") for m in catalog.milestones(c)))
        by_lab = {}
        for m in catalog.milestones(c):
            by_lab.setdefault(m["id"].split("-")[0], []).append(m["id"])
        self.assertEqual(sorted(by_lab), sorted(f"pc{i}" for i in range(13)))   # every lab has a milestone

    def test_every_verify_milestone_is_gated_and_reads_only_the_student(self):
        for m in catalog.milestones(cat()):
            if m["match"]["source"] == "verify":
                self.assertIn("{user}", json.dumps(m["match"]["verify"]), m["id"])
                if m["id"] != "pc4-noncompliant":
                    self.assertIn("requires", m["match"], m["id"])   # not polled for a student who is not there yet


class Shell(unittest.TestCase):
    def test_lab0_clone(self):
        self.assertIn("pc0-clone", sh("git clone http://git-server:3000/amy/cloud-policy-as-code.git"))
        self.assertNotIn("pc0-clone", sh("git clone http://git-server:3000/amy/other.git"))
        self.assertNotIn("pc0-clone", sh("git clone http://git-server:3000/amy/cloud-policy-as-code.git", 128))

    def test_lab9_conftest_red_then_green(self):
        line = "conftest test --policy policy/rego --namespace main plan.json"
        self.assertIn("pc9-red", sh(line, 1))
        self.assertNotIn("pc9-red", sh(line, 0))
        self.assertNotIn("pc9-green", sh(line, 0))
        self.assertIn("pc9-green", sh(line, 0, have=["pc9-red"]))
        self.assertNotIn("pc9-red", sh("echo conftest test", 1))

    def test_lab10_opa_red_green_push(self):
        line = "opa test policy/rego --ignore fixtures -v"
        self.assertIn("pc10-red", sh(line, 1))
        self.assertNotIn("pc10-green", sh(line, 0))
        self.assertIn("pc10-green", sh(line, 0, have=["pc10-red"]))
        self.assertNotIn("pc10-red", sh("opa fmt -w policy/rego", 1))
        self.assertIn("pc10-push", push(have=["pc10-green"]))
        self.assertNotIn("pc10-push", push())
        self.assertNotIn("pc10-push", push(branch="drop-costcenter", have=["pc10-green"]))
        self.assertNotIn("pc10-push", push(repo="ben/cloud-policy-as-code", user="amy", have=["pc10-green"]))

    def test_funny(self):
        self.assertIn("pcf-lock", sh("tofu apply", 1, out="Error: Error acquiring the state lock"))
        self.assertNotIn("pcf-lock", sh("tofu apply", 1, out="Error: something else"))
        self.assertIn("pcf-cleanplan", sh("conftest test plan.json"))
        self.assertNotIn("pcf-cleanplan", sh("conftest test plan.json", have=["pc9-red"]))


class Forgejo(unittest.TestCase):
    def test_fork(self):
        def fork(repo):
            return match(mt.forgejo_event("fork", {"forkee": {"full_name": "platform-team/cloud-policy-as-code"},
                                                   "repository": {"full_name": repo}, "sender": {"login": "amy"}}))
        self.assertIn("pc0-fork", fork(FORK))
        self.assertNotIn("pc0-fork", fork("amy/other"))

    def test_lab8_and_lab11_pull_requests(self):
        self.assertIn("pc8-merged", pr("merged", "waive-legacy-costcenter"))
        self.assertNotIn("pc8-merged", pr("opened", "waive-legacy-costcenter"))
        self.assertNotIn("pc8-merged", pr("merged", "waive-legacy-costcenter", repo="platform-team/cloud-policy-as-code"))
        self.assertIn("pc11-pr", pr("opened", "drop-costcenter"))
        self.assertNotIn("pc11-pr", pr("opened", "something-else"))
        self.assertIn("pc11-merged", pr("merged", "drop-costcenter"))
        self.assertNotIn("pc11-merged", pr("closed", "drop-costcenter"))


class CloudEvents(unittest.TestCase):
    """Items that fire on what cloud-api reports (modules/dojo-cloud/cloud-api/events.py)."""

    def test_events_fire_their_item(self):
        self.assertIn("pc0-deploy", cloud("container_created"))
        self.assertIn("pc1-region", cloud("policy_denied", reason="region"))
        self.assertIn("pc1-tag", cloud("policy_denied", reason="tag"))
        self.assertIn("pc1-size", cloud("policy_denied", reason="size"))
        self.assertIn("pc2-image", cloud("policy_denied", reason="image"))
        self.assertIn("pc3-definition", cloud("policy_written", reason="definition"))
        self.assertIn("pc3-assignment", cloud("policy_written", reason="assignment"))
        self.assertIn("pc3-refused", cloud("policy_denied", reason="assignment"))
        self.assertIn("pc6-set", cloud("policy_written", reason="set"))
        self.assertIn("pc6-refused", cloud("policy_denied", reason="assignment", have=["pc6-set"]))
        self.assertIn("pc7-remediate", cloud("policy_written", reason="remediation"))
        self.assertIn("pc12-drift", cloud("policy_written", reason="portal"))

    def test_lookalikes_do_not(self):
        self.assertNotIn("pc3-refused", cloud("policy_denied", reason="tag"))        # a platform guardrail
        self.assertNotIn("pc6-refused", cloud("policy_denied", reason="assignment"))  # no set yet
        self.assertNotIn("pc3-definition", cloud("policy_written", reason="set"))
        self.assertNotIn("pc12-drift", cloud("policy_written", reason="assignment"))  # tofu, not the portal
        self.assertNotIn("pc7-remediate", cloud("policy_written", reason="exemption"))
        self.assertNotIn("pc0-deploy", cloud("container_updated", reason="arm"))
        self.assertIsNone(mt.adapter_event(dict(source="cloud", event="policy_exploded", user="amy")))

    def test_second_tag_refusal_is_lab2(self):
        c = cat()
        led = lg.Ledger(c, lg.Config())
        m = mt.Matcher(led.index)
        ev = mt.adapter_event(dict(source="cloud", event="policy_denied", user="amy", reason="tag"))
        seen, got = {}, set()

        def bump(iid):
            seen[iid] = seen.get(iid, 0) + 1
            return seen[iid]
        got |= set(m.match(ev, have=got, bump=bump))
        self.assertEqual(got, {"pc1-tag"})
        got |= set(m.match(ev, have=got, bump=bump))
        self.assertIn("pc2-blank", got)


# ---------------------------------------------------------------- fakes


def a(name, scope=SUB, enforcement="Default", definition="d1", effect="deny", is_set=False, bad=(), exempt=0):
    aid = f"{scope}/providers/Microsoft.Authorization/policyAssignments/{name}"
    return {"id": aid, "name": name, "displayName": name, "scope": scope, "enforcementMode": enforcement,
            "policyDefinitionId": f"{SUB}/providers/Microsoft.Authorization/policyDefinitions/{definition}",
            "definitionName": definition, "isSet": is_set, "effect": effect, "compliant": 1,
            "nonCompliant": len(bad), "exempt": exempt,
            "resources": [{"resourceId": f"{SUB}/x/{r}", "name": r, "definitionReferenceId": "", "reason": "r"}
                          for r in bad]}


def d(name, rule, params=None):
    return {"id": f"{SUB}/providers/Microsoft.Authorization/policyDefinitions/{name}", "name": name,
            "displayName": name, "description": "", "rule": rule, "parameters": params or {}}


def ex(assignment, category="Waiver", days=7, expired=False):
    when = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"id": "e", "name": "e", "displayName": "e", "policyAssignmentId": assignment["id"], "category": category,
            "expiresOn": when, "expired": expired}


def refusal(name):
    return {"status": "Failed", "operation": "Create/Update container group",
            "message": f"RequestDisallowedByPolicy: Resource 'ci-amy-prod' was disallowed by policy. Policy: 'X'. "
                       f"Assignment '{name}', definition 'Prod image': image."}


RG = "/subscriptions/0000-amy/resourceGroups/"
PROD_RULE = {"if": {"allOf": [{"field": "type", "equals": "Microsoft.ContainerInstance/containerGroups"},
                              {"field": "tags['env']", "equals": "prod"},
                              {"not": {"field": "x/containers[*].image", "equals": "dojo/hello:2.0"}}]},
             "then": {"effect": "deny"}}
ENV_RULE = {"if": {"field": "tags['env']", "notIn": "[parameters('allowedEnvs')]"}, "then": {"effect": "audit"}}
REVIEW_RULE = {"if": {"field": "tags['reviewedBy']", "exists": False}, "then": {"effect": "deny"}}


class FakeForgejo:
    """api(method, path, raw=False) over a few canned answers: runs, folder listings, raw files, pulls."""

    def __init__(self):
        self.runs, self.files, self.pulls, self.calls = [], {}, [], []

    def run(self, wf, status, event="push"):
        self.runs.append({"id": len(self.runs) + 1, "workflow_id": wf, "status": status, "event": event})

    def __call__(self, method, path, body=None, raw=False):
        self.calls.append(path)
        p = path.split("?")[0]
        if p.endswith("/actions/runs"):
            page = int(re.search(r"page=(\d+)", path).group(1)) if "page=" in path else 1
            return 200, {"workflow_runs": list(reversed(self.runs))[(page - 1) * 50:page * 50]}
        if "/contents/" in p:
            folder = p.split("/contents/", 1)[1]
            rows = [{"type": "file", "name": k.rsplit("/", 1)[1], "path": k} for k in self.files
                    if k.rsplit("/", 1)[0] == folder]
            return (200, rows) if rows else (404, None)
        if "/raw/" in p:
            key = p.split("/raw/", 1)[1]
            return (200, self.files[key]) if key in self.files else (404, None)
        if p.endswith("/pulls"):
            page = int(re.search(r"page=(\d+)", path).group(1)) if "page=" in path else 1
            return 200, self.pulls if page == 1 else []
        return 404, None


class Fakes(unittest.TestCase):
    def setUp(self):
        self.cat = cat()
        self.forgejo = FakeForgejo()
        self.runner = challenges.Runner(challenges.load_plugins([CLOUD, CI, CORE]), SEEDS, self.forgejo, lambda: 0)
        self.cloudmod = self.runner.verbs["cloud_policy"][1]
        self.orig = (self.cloudmod._policy, self.cloudmod._activity, self.cloudmod._overview)
        self.addCleanup(self.restore)
        self.policy = {"assignments": [], "exemptions": [], "definitions": [], "sets": []}
        self.activity, self.groups, self.asked = [], [], []
        self.cloudmod._policy = lambda user: self.asked.append(user) or self.policy
        self.cloudmod._activity = lambda user: self.asked.append(user) or {"events": self.activity}
        self.cloudmod._overview = lambda user: self.asked.append(user) or {"containerGroups": self.groups}

    def restore(self):
        self.cloudmod._policy, self.cloudmod._activity, self.cloudmod._overview = self.orig

    def item(self, iid):
        if iid in ("c1", "c2", "capstone"):
            return next(c for c in self.cat["challenges"] + [self.cat["capstone"]] if c["id"] == iid)
        m = next(m for m in catalog.milestones(self.cat) if m["id"] == iid)
        return {"id": iid, "verify": m["match"]["verify"]}

    def ok(self, iid, step=1):
        ch = self.item(iid)
        if step == 2:
            ch = dict(ch, verify=ch["then"]["verify"])
        return self.runner.verify(ch, "amy")["passed"]


class VerifyMilestones(Fakes):
    def test_no_unknown_verbs(self):
        self.assertEqual(self.runner.unknown_verbs(self.cat), [])
        for m in catalog.milestones(self.cat):
            for x in m["match"].get("verify") or []:
                self.assertIn(x["verb"], self.runner.verbs, m["id"])

    def test_lab4_legacy_noncompliant(self):
        self.policy["assignments"] = [a("require-costcenter", bad=["rg-amy-app"])]
        self.assertFalse(self.ok("pc4-noncompliant"))
        self.policy["assignments"] = [a("require-costcenter", bad=["rg-amy-legacy"])]
        self.assertTrue(self.ok("pc4-noncompliant"))

    def test_lab5_dry_run_and_reuse(self):
        strict = a("images-strict", scope=RG + "rg-amy-app", enforcement="DoNotEnforce", definition="allowed-images")
        self.policy["assignments"] = [strict]
        self.assertTrue(self.ok("pc5-dryrun"))
        self.assertFalse(self.ok("pc5-reuse"))
        self.policy["assignments"] = [a("images-strict", scope=RG + "rg-amy-app", definition="allowed-images"),
                                      a("images-subscription", definition="allowed-images"), a("require-costcenter")]
        self.assertFalse(self.ok("pc5-dryrun"))                                 # enforced now
        self.assertTrue(self.ok("pc5-reuse"))
        self.policy["assignments"] = [strict, a("other", scope=RG + "rg-amy-legacy", enforcement="DoNotEnforce")]
        self.assertTrue(self.ok("pc5-dryrun"))
        self.policy["assignments"] = [a("x", scope=RG + "rg-amy-legacy", enforcement="DoNotEnforce")]
        self.assertFalse(self.ok("pc5-dryrun"))                                 # wrong scope

    def test_lab6_set_and_lab8_exemption(self):
        base = a("team-baseline", definition="team-baseline", is_set=True)
        self.policy["assignments"] = [a("require-costcenter")]
        self.assertFalse(self.ok("pc6-assigned"))
        self.policy["assignments"] = [base]
        self.assertTrue(self.ok("pc6-assigned"))
        self.assertFalse(self.ok("pc8-exempt"))
        base = a("team-baseline", definition="team-baseline", is_set=True, exempt=1)
        self.policy["assignments"] = [base]
        self.policy["exemptions"] = [ex(base, category="Mitigated")]
        self.assertFalse(self.ok("pc8-exempt"))
        self.policy["exemptions"] = [ex(base, expired=True)]
        self.assertFalse(self.ok("pc8-exempt"))
        self.policy["exemptions"] = [ex(base)]
        self.assertTrue(self.ok("pc8-exempt"))

    def test_lab7_tagged(self):
        g = {"dnsLabel": "amy-app", "tags": {"owner": "amy", "env": "dev"}, "state": "Running", "isMine": True}
        self.groups = [g]
        self.assertFalse(self.ok("pc7-tagged"))
        self.groups = [dict(g, tags={"owner": "amy", "env": "dev", "managedBy": "policy"})]
        self.assertTrue(self.ok("pc7-tagged"))

    def test_ci_milestones(self):
        self.assertFalse(self.ok("pc8-apply"))
        self.forgejo.run("main.yml", "failure")
        self.assertFalse(self.ok("pc8-apply"))
        self.forgejo.run("main.yml", "success")
        self.assertTrue(self.ok("pc8-apply"))
        self.assertTrue(self.ok("pc11-applied"))
        self.assertFalse(self.ok("pc11-blocked"))
        self.forgejo.run("pr.yml", "failure", "pull_request")
        self.assertTrue(self.ok("pc11-blocked"))
        self.forgejo.run("main.yml", "running")
        self.assertTrue(self.ok("pc11-applied"))                                 # unfinished runs don't count
        self.forgejo.run("main.yml", "failure")
        self.assertFalse(self.ok("pc11-applied"))                                # only the newest finished one
        self.forgejo.run("drift.yml", "success")
        self.assertFalse(self.ok("pc12-caught"))
        self.assertFalse(self.ok("pc12-fixed"))
        self.forgejo.run("drift.yml", "failure", "workflow_dispatch")
        self.assertTrue(self.ok("pc12-caught"))
        self.assertFalse(self.ok("pc12-fixed"))
        self.forgejo.run("drift.yml", "success", "workflow_dispatch")
        self.assertTrue(self.ok("pc12-fixed"))
        self.assertTrue(all(c.startswith("/repos/amy/cloud-policy-as-code/") for c in self.forgejo.calls))


class Challenges(Fakes):
    def test_c1(self):
        rg = RG + "rg-amy-c1"
        self.policy["definitions"] = [d("allowed-envs-c1", ENV_RULE, {"allowedEnvs": {"type": "Array"}})]
        good = a("allowed-envs-c1", scope=rg, definition="allowed-envs-c1", effect="audit", bad=["rg-amy-c1"])
        self.forgejo.files["main.tf"] = 'resource "azurerm_resource_group_policy_assignment" "x" {}'
        self.policy["assignments"] = [good]
        self.assertTrue(self.ok("c1"))
        self.policy["assignments"] = [dict(good, scope=SUB)]                      # subscription scope
        self.assertFalse(self.ok("c1"))
        self.policy["assignments"] = [dict(good, effect="deny")]
        self.assertFalse(self.ok("c1"))
        self.policy["assignments"] = [dict(good, nonCompliant=0, resources=[])]   # nothing reported yet
        self.assertFalse(self.ok("c1"))
        self.policy["assignments"] = [good]
        self.policy["definitions"] = [d("allowed-envs-c1", ENV_RULE, {})]          # not parameterised
        self.assertFalse(self.ok("c1"))
        self.policy["definitions"] = [d("allowed-envs-c1", ENV_RULE, {"allowedEnvs": {"type": "Array"}})]
        self.forgejo.files = {}
        self.assertFalse(self.ok("c1"))                                          # not pushed
        self.assertEqual(set(self.asked), {"amy"})

    def test_c2_two_steps(self):
        rg = RG + "rg-amy-c2"
        self.policy["definitions"] = [d("require-reviewedby-c2", REVIEW_RULE)]
        asg = a("require-reviewedby-c2", scope=rg, definition="require-reviewedby-c2", exempt=1)
        self.forgejo.files["main.tf"] = 'resource "azurerm_resource_group_policy_exemption" "w" {}'
        self.policy["assignments"] = [asg]
        self.policy["exemptions"] = [ex(asg, days=7)]
        self.assertTrue(self.ok("c2"))
        self.policy["exemptions"] = [ex(asg, days=30)]                            # deadline too far
        self.assertFalse(self.ok("c2"))
        self.policy["exemptions"] = [ex(asg, days=7)]
        self.policy["assignments"] = [dict(asg, exempt=0, nonCompliant=1)]          # not exempt yet
        self.assertFalse(self.ok("c2"))
        self.policy["assignments"] = [asg]
        self.assertFalse(self.ok("c2", step=2))                                  # still assigned
        self.policy["assignments"] = [a("team-baseline", is_set=True)]            # lab assignments don't matter
        self.assertTrue(self.ok("c2", step=2))

    def test_capstone(self):
        f = self.forgejo
        f.files = {"policy/rego/costcenter_test.rego": "test_a if {}\ntest_b if {}\ntest_c if {}\ntest_d if {}\n",
                   "policy/rego/costcenter.rego": "deny contains msg if { false }"}
        f.pulls = [{"number": 3, "merged": True, "state": "closed", "base": {"ref": "main"}, "head": {"ref": "x"}}]
        f.run("pr.yml", "success", "pull_request")
        f.run("main.yml", "success")
        f.run("drift.yml", "success", "workflow_dispatch")
        asg = a("prod-image", definition="prod-image")
        self.policy["definitions"] = [d("prod-image", PROD_RULE)]
        self.policy["assignments"] = [asg]
        self.activity = [refusal("prod-image")]
        self.assertFalse(self.ok("capstone"))                                    # no capstone Rego yet
        f.files["policy/rego/prod_image_test.rego"] = ("test_prod_2 if {}\ntest_prod_1_denied if { 'dojo/hello:1.0' }\n"
                                                        "test_dev_1 if {}\n test_delete if { 'prod' }\n")
        self.assertFalse(self.ok("capstone"))                                    # the rule itself is missing
        f.files["policy/rego/prod_image.rego"] = 'deny contains msg if { env == "prod"; image != "dojo/hello:2.0" }'
        self.assertTrue(self.ok("capstone"))
        self.activity = [refusal("require-costcenter")]
        self.assertFalse(self.ok("capstone"))                                    # refused by another assignment
        self.activity = [refusal("prod-image")]
        self.policy["definitions"] = [d("prod-image", dict(PROD_RULE, then={"effect": "audit"}))]
        self.assertTrue(self.ok("capstone"))  # the assignment row's effect is what counts (deny, from the blade)
        self.policy["assignments"] = [dict(asg, effect="audit")]
        self.assertFalse(self.ok("capstone"))
        self.policy["assignments"] = [asg]
        f.run("drift.yml", "failure", "workflow_dispatch")
        self.assertFalse(self.ok("capstone"))                                    # Drift must be green after
        # step 2: no env=prod group left in any state
        self.groups = [{"dnsLabel": "amy-prod", "tags": {"env": "prod"}, "state": "Terminated", "isMine": True}]
        self.assertFalse(self.ok("capstone", step=2))
        self.groups = [{"dnsLabel": "amy-app", "tags": {"env": "dev"}, "state": "Running", "isMine": True}]
        self.assertTrue(self.ok("capstone", step=2))

    def test_seed_plans_are_complete(self):
        for ch in self.cat["challenges"]:
            with open(os.path.join(SEEDS, ch["seed_plan"])) as fh:
                plan = json.load(fh)
            vals = self.runner.values(ch, "amy")
            self.assertEqual(challenges.fill_text(plan["repo"], vals), f"amy/challenge-{ch['id']}")
            for c in plan["commits"]:
                for fl in c["files"]:
                    with open(os.path.join(SEEDS, fl["from"])) as fh:
                        text = challenges.fill_text(fh.read(), vals)
                    self.assertNotRegex(text, re.compile(r"\{user\}"), fl["from"])
            rules = os.path.join(SEEDS, ch["id"], "rules")
            for name in os.listdir(rules):
                with open(os.path.join(rules, name)) as fh:
                    json.load(fh)                                                # starter rules are valid JSON


class CloudPolicyVerb(Fakes):
    def verb(self, args, user="amy"):
        return self.cloudmod.cloud_policy(None, args, {"user": user})

    def test_account_names_only_the_checking_student(self):
        self.policy["assignments"] = [a("x")]
        self.assertTrue(self.verb({"account": "amy"})[0])
        self.assertFalse(self.verb({"account": "ben"})[0])
        self.verb({"user": "ben"})                                               # a stray argument is ignored
        self.assertEqual(set(self.asked), {"amy"})

    def test_kinds_counts_and_messages(self):
        self.policy["assignments"] = [a("x"), a("y")]
        self.policy["exemptions"] = [ex(a("x")), ex(a("y"), expired=True)]
        self.policy["sets"] = [d("team-baseline", [{"policyDefinitionId": "d1"}])]
        self.assertTrue(self.verb({"kind": "assignment", "min": 2, "max": 2})[0])
        self.assertFalse(self.verb({"kind": "assignment", "max": 1})[0])
        self.assertTrue(self.verb({"kind": "exemption", "max": 1})[0])            # the expired one is not active
        self.assertTrue(self.verb({"kind": "set", "name": "TEAM-baseline"})[0])
        self.assertFalse(self.verb({"kind": "bogus"})[0])
        ok, msg = self.verb({"kind": "assignment", "enforcement": "DoNotEnforce"})
        self.assertFalse(ok)
        self.assertIn("DoNotEnforce", msg)
        self.assertTrue(self.verb({"kind": "assignment", "name": "nope", "min": 0, "max": 0})[0])

    def test_rule_text_reads_the_assigned_definition(self):
        self.policy["definitions"] = [d("d1", PROD_RULE)]
        self.policy["assignments"] = [a("x")]
        self.assertTrue(self.verb({"rule_text": ["tags['env']", "DOJO/hello:2.0"]})[0])
        self.assertFalse(self.verb({"rule_text": ["dojo/hello:3.0"]})[0])
        self.policy["definitions"] = []
        self.assertFalse(self.verb({"rule_text": ["tags['env']"]})[0])           # unknown definition

    def test_refused_reads_the_activity_log_once(self):
        self.policy["assignments"] = [a("x"), a("y")]
        self.activity = [refusal("y"), {"status": "Failed", "message": "QuotaExceeded: Assignment 'x'"}]
        self.asked.clear()
        self.assertTrue(self.verb({"refused": True, "max": 1})[0])
        self.assertEqual(self.asked, ["amy", "amy"])                              # the blade, then the log once

    def test_refused_prefers_the_assignments_own_count(self):
        x, y = a("x"), a("y")
        x["refusals"], y["refusals"] = 0, 2
        self.policy["assignments"] = [x, y]
        self.activity = [refusal("x")]                                          # the log is not read
        self.asked.clear()
        self.assertTrue(self.verb({"refused": True, "max": 1})[0])
        self.assertEqual(self.asked, ["amy"])                                     # the blade only
        y["refusals"] = 0
        self.assertFalse(self.verb({"refused": True})[0])

    def test_the_requests_name_the_student_and_carry_the_token(self):
        self.restore()
        seen = []

        class R:
            def __enter__(s): return s
            def __exit__(s, *x): return False
            def read(s): return b"{}"

        mod = self.cloudmod
        orig, env = mod.urllib.request.urlopen, mod.os.environ.copy()
        mod.urllib.request.urlopen = lambda req, timeout: seen.append((req.full_url, dict(req.header_items()))) or R()
        mod.os.environ.update(CLOUD_API_URL="http://cloud-api:8080/", CLOUD_CHECK_TOKEN="tok")
        try:
            mod._policy("amy")
            mod._activity("amy")
        finally:
            mod.urllib.request.urlopen = orig
            mod.os.environ.clear()
            mod.os.environ.update(env)
        self.assertEqual([u for u, _ in seen], ["http://cloud-api:8080/cloud/api/policy",
                                                "http://cloud-api:8080/cloud/api/activity?limit=500"])
        self.assertTrue(all(h["X-auth-user"] == "amy" and h["X-check-token"] == "tok" for _, h in seen))


class CiVerbs(Fakes):
    def ci(self, args, user="amy"):
        return self.runner.verbs["ci_run"][0](self.forgejo, args, {"user": user})

    def tree(self, args, user="amy"):
        return self.runner.verbs["tree_file_contains"][0](self.forgejo, args, {"user": user})

    def test_only_the_students_own_repo(self):
        self.assertFalse(self.ci({"repo": "ben/cloud-policy-as-code", "workflow": "pr.yml"})[0])
        self.assertFalse(self.tree({"repo": "ben/x", "ref": "main", "dir": "a", "regex": "."})[0])
        self.assertEqual(self.forgejo.calls, [])

    def test_ci_run_filters(self):
        self.assertFalse(self.ci({"repo": FORK, "workflow": "pr.yml"})[0])
        self.forgejo.run(".forgejo/workflows/pr.yml", "success", "pull_request")
        self.assertTrue(self.ci({"repo": FORK, "workflow": "pr.yml"})[0])        # a path also matches
        self.assertFalse(self.ci({"repo": FORK, "workflow": "pr.yml", "event": "push"})[0])
        self.assertFalse(self.ci({"repo": FORK, "workflow": "main.yml"})[0])
        self.assertFalse(self.ci({"repo": FORK, "workflow": "pr.yml", "status": "failure"})[0])
        for _ in range(60):                                                     # more than one page
            self.forgejo.run("main.yml", "success")
        self.assertTrue(self.ci({"repo": FORK, "workflow": "pr.yml"})[0])

    def test_tree_file_contains(self):
        self.forgejo.files = {"p/a_test.rego": "test_1\ntest_2\nprod", "p/a.rego": "prod 2.0", "p/sub/b.rego": "x"}
        base = {"repo": FORK, "ref": "main", "dir": "p"}
        self.assertTrue(self.tree(dict(base, name_regex="_test\\.rego$", regex="prod", count_regex="^test_",
                                       count_min=2))[0])
        self.assertFalse(self.tree(dict(base, name_regex="_test\\.rego$", regex="prod", count_regex="^test_",
                                        count_min=3))[0])
        self.assertTrue(self.tree(dict(base, name_regex="^(?!.*_test\\.rego$).*\\.rego$", regex=["prod", "2\\.0"]))[0])
        self.assertFalse(self.tree(dict(base, name_regex="^(?!.*_test\\.rego$).*\\.rego$", regex="test_"))[0])
        self.assertFalse(self.tree(dict(base, dir="missing", regex="."))[0])


if __name__ == "__main__":
    unittest.main()
