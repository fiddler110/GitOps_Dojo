"""tofu-basics pack: each wired item fires on the command or event the labs produce, and not on lookalikes;
the cloud verifier and the challenges' checks run against a faked Dojo Cloud API."""
import importlib.util
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

PACK = os.path.join(HERE, "..", "..", "..", "workshops", "tofu-basics")
SHARED = os.path.join(HERE, "..", "catalog", "shared.json")
PLUGINS = os.path.join(HERE, "..", "plugins", "cloud")
SEEDS = os.path.join(PACK, "achievements", "seeds")


def match(ev, have=()):
    c = catalog.load(PACK, SHARED)[0]
    return mt.Matcher(lg.Ledger(c, lg.Config()).index).match(ev, have=set(have))


def sh(cmd, exit=0, have=(), **kw):
    return match(mt.shell_event(dict(cmd=cmd, exit=exit, **kw)), have)


class Shell(unittest.TestCase):
    def test_track_a(self):
        for word in ("tofu", "terraform"):
            self.assertIn("t1-init", sh(f"{word} init"))
            self.assertIn("t1-validate", sh(f"{word} validate"))
            self.assertIn("t1-plan", sh(f"{word} plan -no-color"))
            self.assertIn("t1-apply", sh(f"{word} apply"))
        self.assertNotIn("t1-init", sh("terraform init", 1))
        self.assertNotIn("t1-plan", sh("terraform plan -destroy -no-color | grep x", 1))
        self.assertIn("t0-tour", sh("terraform version"))
        self.assertIn("t0-tour", sh("tofu -version"))
        self.assertNotIn("t0-tour", sh("echo terraform version"))
        self.assertIn("t0-clone", sh("git clone http://git-server:3000/amy/tofu-basics.git"))
        self.assertNotIn("t0-clone", sh("git clone http://git-server:3000/amy/other.git"))

    def test_lab2_sequence(self):
        self.assertNotIn("t2-idem", sh("terraform plan"))
        self.assertIn("t2-idem", sh("terraform plan", have=["t1-apply"]))
        self.assertIn("t2-change", sh("terraform apply", have=["t2-idem"]))
        self.assertNotIn("t2-change", sh("terraform apply"))
        self.assertIn("t2-replace", sh("terraform plan -replace=random_pet.nickname"))
        self.assertIn("t2-replace", sh("tofu apply -replace=random_pet.nickname"))
        self.assertNotIn("t2-replace", sh("terraform plan -var pet_words=9"))
        self.assertIn("t2-broke", sh("terraform plan -var pet_words=9", 1))
        self.assertIn("t2-broke", sh("terraform validate", 1))
        self.assertNotIn("t2-broke", sh("terraform validate", 0))

    def test_lab3(self):
        self.assertIn("t3-destroy", sh("terraform destroy"))
        self.assertNotIn("t3-destroy", sh("terraform plan -destroy"))
        self.assertIn("t3-state", sh("terraform state list"))
        self.assertIn("t3-state", sh("ls -la terraform.tfstate*"))
        self.assertIn("t3-state", sh("cat terraform.tfstate"))
        self.assertNotIn("t3-state", sh("terraform state show x"))

    def test_track_b_needs_the_credentials_first(self):
        self.assertIn("t4-creds", sh("env | grep -E '^(ARM_|TF_VAR_)' | grep -v SECRET | sort"))
        self.assertIn("t4-creds", sh("echo $ARM_CLIENT_ID"))
        self.assertNotIn("t4-creds", sh("echo hello"))
        self.assertNotIn("t4-provider", sh("terraform init"))
        self.assertIn("t4-provider", sh("terraform init", have=["t4-creds"]))
        self.assertIn("t5-plan", sh("terraform plan", have=["t4-provider"]))
        self.assertNotIn("t5-plan", sh("terraform plan"))
        self.assertIn("t5-apply", sh("terraform apply", have=["t4-provider"]))
        self.assertNotIn("t5-apply", sh("terraform apply", 1, have=["t4-provider"]))

    def test_lab7_to_10(self):
        self.assertNotIn("t7-restored", sh("terraform apply"))
        self.assertIn("t7-restored", sh("terraform apply", have=["t7-delete"]))
        self.assertIn("t8-forced", sh("terraform apply -replace=azurerm_container_group.hello", have=["t4-creds"]))
        self.assertNotIn("t8-forced", sh("terraform apply", have=["t4-creds"]))
        self.assertNotIn("t8-forced", sh("terraform plan -replace=x", have=["t4-creds"]))
        self.assertIn("t9-fixed", sh("terraform plan", have=["t9-quota"]))
        self.assertNotIn("t9-fixed", sh("terraform plan"))
        self.assertIn("t10-destroy", sh("terraform destroy", have=["t4-creds"]))
        self.assertNotIn("t10-destroy", sh("terraform destroy"))

    def test_funny(self):
        self.assertIn("f-yes", sh("terraform apply -auto-approve"))
        self.assertNotIn("f-yes", sh("terraform apply"))
        self.assertIn("f-statecommit", sh("git add -f sandbox/terraform.tfstate"))
        self.assertNotIn("f-statecommit", sh("git add sandbox/terraform.tfvars"))


class Forgejo(unittest.TestCase):
    def push(self, repo, user="amy"):
        return mt.forgejo_event("push", {"ref": "refs/heads/my-dojo-cloud-change", "repository": {"full_name": repo},
                                         "pusher": {"login": user}, "sender": {"login": user}})

    def test_commit_after_destroy(self):
        self.assertIn("t10-commit", match(self.push("amy/tofu-basics"), ["t10-destroy"]))
        self.assertNotIn("t10-commit", match(self.push("amy/tofu-basics")))
        self.assertNotIn("t10-commit", match(self.push("amy/other"), ["t10-destroy"]))
        self.assertNotIn("t10-commit", match(self.push("ben/tofu-basics"), ["t10-destroy"]))


_spec = importlib.util.spec_from_file_location("cloudstate", os.path.join(PLUGINS, "cloudstate.py"))
cloudstate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cloudstate)


def cg(label, tags, state="Running", location="canadacentral"):
    return {"name": "ci-x", "dnsLabel": label, "tags": tags, "state": state, "location": location, "isMine": True}


def own(label, cid, **kw):
    return cg(label, {"owner": "amy", "env": "dev", "challenge": cid}, **kw)


MAIN = "output \"url\" {\n  description = \"site\"\n  value = \"${var.portal_base_url}/site/amy-second/\"\n}\n"


class Challenges(unittest.TestCase):
    def setUp(self):
        self.cat = catalog.load(PACK, SHARED)[0]
        self.runner = challenges.Runner(
            challenges.load_plugins([PLUGINS, os.path.join(HERE, "..", "achievements")]), SEEDS, None, lambda: 0)
        self.cloud = self.runner.verbs["cloud_containers"][1]
        self.forgejo = self.runner.verbs["file_contains"][1]
        self.orig = (self.cloud._overview, self.forgejo._raw)
        self.asked = []
        self.files = {}

    def tearDown(self):
        self.cloud._overview, self.forgejo._raw = self.orig

    def check(self, cid, groups, files=None, step=1):
        def overview(user):
            self.asked.append(user)
            return None if groups is None else {"containerGroups": groups}
        self.cloud._overview = overview
        self.forgejo._raw = lambda api, repo, ref, path: (files or {}).get((repo, path))
        ch = next(c for c in self.cat["challenges"] + [self.cat["capstone"]] if c["id"] == cid)
        return self.runner.verify(dict(ch, verify=ch["then"]["verify"]) if step == 2 else ch, "amy")

    def test_no_unknown_verbs(self):
        self.assertEqual(self.runner.unknown_verbs(self.cat), [])

    def test_c1(self):
        good = [own("amy-second", "c1")]
        f = {("amy/challenge-c1", "main.tf"): MAIN}
        self.assertTrue(self.check("c1", good, f)["passed"])
        self.assertFalse(self.check("c1", [], f)["passed"])                                     # nothing deployed
        self.assertFalse(self.check("c1", [own("amy-second", "c1", state="Terminated")], f)["passed"])
        self.assertFalse(self.check("c1", [own("second", "c1")], f)["passed"])                  # label without the user
        self.assertFalse(self.check("c1", [cg("amy-second", {"challenge": "c1"})], f)["passed"])  # missing tags
        self.assertFalse(self.check("c1", [own("amy-second", "c1", location="eastus")], f)["passed"])
        self.assertFalse(self.check("c1", [own("amy-third", "c1")], f)["passed"])
        self.assertFalse(self.check("c1", good + [own("amy-second2", "c1")], f)["passed"])      # only one expected
        self.assertFalse(self.check("c1", good, {("amy/challenge-c1", "main.tf"): "resource x {}"})["passed"])
        self.assertFalse(self.check("c1", good, {})["passed"])                                  # not pushed
        bare = {("amy/challenge-c1", "main.tf"): 'output "url" {\n  value = azurerm_container_group.s.fqdn\n}\n'}
        self.assertFalse(self.check("c1", good, bare)["passed"])                                # a host, not a URL
        https = {("amy/challenge-c1", "main.tf"): 'output "url" { value = "https://${azurerm_container_group.s.fqdn}" }'}
        self.assertTrue(self.check("c1", good, https)["passed"])
        # lab leftovers never count (other tag)
        self.assertTrue(self.check("c1", good + [own("hello-dev-amy", "lab")], f)["passed"])

    def test_c2(self):
        seeded = 'locals {\n  sites = ["alpha", "bravo", "charlie", "delta", "echo"]\n}\n'
        fixed = 'locals {\n  sites = ["alpha"]\n}\n'
        key = ("amy/challenge-c2", "main.tf")
        one, two = [own("amy-c2-alpha", "c2")], [own("amy-c2-alpha", "c2"), own("amy-c2-bravo", "c2")]
        self.assertTrue(self.check("c2", one, {key: fixed})["passed"])
        self.assertTrue(self.check("c2", two, {key: fixed})["passed"])
        self.assertFalse(self.check("c2", one, {key: seeded})["passed"])        # code still declares five
        self.assertFalse(self.check("c2", [], {key: fixed})["passed"])
        self.assertFalse(self.check("c2", [own("hello-dev-amy", "c2")], {key: fixed})["passed"])

    def test_capstone(self):
        f = {("amy/site-factory", "main.tf"): "for_each = toset([\"a\", \"b\"])"}
        two = [own("amy-a", "capstone"), own("amy-b", "capstone")]
        self.assertTrue(self.check("capstone", two, f)["passed"])
        self.assertFalse(self.check("capstone", two[:1], f)["passed"])
        self.assertFalse(self.check("capstone", two + [own("amy-c", "capstone")], f)["passed"])
        self.assertFalse(self.check("capstone", two, {("amy/site-factory", "main.tf"): "resource x {}"})["passed"])
        self.assertFalse(self.check("capstone", [], f)["passed"])
        # step 2: destroyed, nothing of the capstone left in any state; lab sites don't matter
        self.assertTrue(self.check("capstone", [], step=2)["passed"])
        self.assertTrue(self.check("capstone", [own("hello-dev-amy", "lab")], step=2)["passed"])
        self.assertFalse(self.check("capstone", two[:1], step=2)["passed"])
        self.assertFalse(self.check("capstone", [own("amy-a", "capstone", state="Terminated")], step=2)["passed"])

    def test_an_unreachable_cloud_is_not_a_failure_of_the_student(self):
        self.cloud._overview = lambda user: (_ for _ in ()).throw(cloudstate.Unavailable("down"))
        ch = next(c for c in self.cat["challenges"] if c["id"] == "c1")
        with self.assertRaises(cloudstate.Unavailable):
            self.runner.verify(ch, "amy")

    def test_a_check_only_asks_for_the_checking_students_subscription(self):
        self.check("c1", [own("amy-second", "c1")], {})
        self.assertEqual(set(self.asked), {"amy"})
        # the verb has no account argument, and a stray one is ignored
        self.cloud._overview = lambda user: self.asked.append(user) or {"containerGroups": []}
        self.cloud.cloud_containers(None, {"user": "ben", "min": 0}, {"user": "amy"})
        self.assertEqual(self.asked[-1], "amy")

    def test_the_request_names_the_student_and_carries_the_token(self):
        seen = {}

        class R:
            def __enter__(s): return s
            def __exit__(s, *a): return False
            def read(s): return b'{"containerGroups": []}'

        orig, url = cloudstate.urllib.request.urlopen, cloudstate.os.environ.copy()
        cloudstate.urllib.request.urlopen = lambda req, timeout: seen.update(u=req.full_url, h=dict(req.header_items())) or R()
        cloudstate.os.environ.update(CLOUD_API_URL="http://cloud-api:8080/", CLOUD_CHECK_TOKEN="tok")
        try:
            self.assertEqual(cloudstate._overview("amy"), {"containerGroups": []})
        finally:
            cloudstate.urllib.request.urlopen = orig
            cloudstate.os.environ.clear()
            cloudstate.os.environ.update(url)
        self.assertEqual(seen["u"], "http://cloud-api:8080/cloud/api/overview?scope=mine")
        self.assertEqual(seen["h"]["X-auth-user"], "amy")
        self.assertEqual(seen["h"]["X-check-token"], "tok")

    def test_seed_plans_are_complete(self):
        for ch in self.cat["challenges"] + [self.cat["capstone"]]:
            plan = json.load(open(os.path.join(SEEDS, ch["seed_plan"])))
            vals = self.runner.values(ch, "amy")
            for c in plan["commits"]:
                for f in c["files"]:
                    text = challenges.fill_text(open(os.path.join(SEEDS, f["from"])).read(), vals)
                    self.assertNotRegex(text, re.compile(r"\{user\}"), f["from"])
            self.assertTrue(challenges.fill_text(plan["repo"], vals).startswith("amy/"))
            self.assertEqual(challenges.fill_text(plan["repo"], vals).split("/")[1],
                             {"c1": "challenge-c1", "c2": "challenge-c2", "capstone": "site-factory"}[ch["id"]])


def cloud(event, user="amy", **kw):
    return match(mt.adapter_event(dict(source="cloud", event=event, user=user, **kw)))


class CloudEvents(unittest.TestCase):
    """Track B items that fire on what cloud-api reports (modules/dojo-cloud/cloud-api/events.py)."""

    def test_events_fire_their_item(self):
        self.assertIn("t4-portal", cloud("portal_request"))
        self.assertIn("t5-site", cloud("site_request"))
        self.assertIn("t6-tag", cloud("policy_denied", reason="tag"))
        self.assertIn("t6-region", cloud("policy_denied", reason="region"))
        self.assertIn("t6-size", cloud("policy_denied", reason="size"))
        self.assertIn("t7-tag", cloud("container_updated", reason="portal"))
        self.assertIn("t7-delete", cloud("container_deleted", reason="portal"))
        self.assertIn("t8-replace", cloud("container_replaced"))
        self.assertIn("t9-quota", cloud("quota_denied"))

    def test_lookalikes_do_not(self):
        self.assertNotIn("t6-region", cloud("policy_denied", reason="tag"))
        self.assertNotIn("t6-tag", cloud("quota_denied"))
        self.assertNotIn("t7-tag", cloud("container_updated", reason="arm"))      # tofu's PATCH is not the portal
        self.assertNotIn("t7-delete", cloud("container_deleted", reason="arm"))
        self.assertNotIn("t8-replace", cloud("container_created"))
        self.assertNotIn("t9-quota", cloud("policy_denied", reason="size"))

    def test_fork(self):
        def fork(repo):
            return match(mt.forgejo_event("fork", {"forkee": {"full_name": "iac-team/tofu-basics"}, "repository": {"full_name": repo},
                                                   "sender": {"login": "amy"}}))
        self.assertIn("t0-fork", fork("amy/tofu-basics"))
        self.assertNotIn("t0-fork", fork("amy/other"))


class ShellOutput(unittest.TestCase):
    """Items read from what the command printed (`out`, from the tmux pane)."""

    APPLY_INPLACE = ("azurerm_container_group.hello: Modifying... [id=/subscriptions/x]\n"
                     "azurerm_container_group.hello: Modifications complete after 2s\n\nApply complete! 0 added, 1 changed")
    APPLY_REPLACE = ("azurerm_container_group.hello: Destroying... [id=x]\nazurerm_container_group.hello: Destruction complete after 3s\n"
                     "azurerm_container_group.hello: Creating...\nazurerm_container_group.hello: Creation complete after 9s")
    APPLY_EXTRA = ('azurerm_container_group.extra["blue"]: Creation complete after 13s [id=x]\n\nError: QuotaExceeded')

    def test_inplace_vs_replace(self):
        self.assertIn("t8-inplace", sh("tofu apply", out=self.APPLY_INPLACE))
        self.assertNotIn("t8-inplace", sh("tofu apply", 1, out=self.APPLY_INPLACE))
        self.assertNotIn("t8-inplace", sh("tofu apply", out="Apply complete! 1 added"))
        self.assertIn("t8-replace", sh("terraform apply", out=self.APPLY_REPLACE))
        self.assertNotIn("t8-replace", sh("terraform apply", out=self.APPLY_INPLACE))

    def test_foreach(self):
        self.assertIn("t9-foreach", sh("terraform apply", 1, out=self.APPLY_EXTRA))
        self.assertIn("t9-foreach", sh("terraform state list", out='azurerm_container_group.extra["blue"]\nazurerm_container_group.hello'))
        self.assertNotIn("t9-foreach", sh("terraform state list", out="azurerm_container_group.hello"))
        self.assertNotIn("t9-foreach", sh("terraform apply", out="azurerm_container_group.hello: Creation complete"))

    def test_funny(self):
        self.assertIn("f-nolock", sh("tofu plan", 1, out="Error: Error acquiring the state lock"))
        self.assertNotIn("f-nolock", sh("tofu plan", 1, out="Error: something else"))
        self.assertNotIn("f-nolock", sh("echo hi", 0, out="Error acquiring the state lock"))
        self.assertIn("f-typo", sh("tofu validate", 1, out="Error: Reference to undeclared resource"))
        self.assertNotIn("f-typo", sh("tofu validate", 0, out="Reference to undeclared"))
        self.assertNotIn("f-typo", sh("tofu validate", 1, out="Error: Missing required argument"))

    def test_destroy_first(self):
        self.assertIn("f-destroyfirst", sh("tofu destroy"))
        self.assertNotIn("f-destroyfirst", sh("tofu destroy", have=["t1-apply"]))
        self.assertNotIn("f-destroyfirst", sh("tofu plan"))


if __name__ == "__main__":
    unittest.main()
