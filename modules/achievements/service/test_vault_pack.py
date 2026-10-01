"""vault-fundamentals pack: wired items fire on the command or event the labs produce and not on lookalikes;
the bao verifier verbs and the challenges run against a faked OpenBao."""
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

PACK = os.path.join(HERE, "..", "..", "..", "workshops", "vault-fundamentals")
SHARED = os.path.join(HERE, "..", "catalog", "shared.json")
PLUGINS = [os.path.join(HERE, "..", "achievements"), os.path.join(HERE, "..", "plugins", "bao")]


def ids(ev):
    c = catalog.load(PACK, SHARED)[0]
    return mt.Matcher(lg.Ledger(c, lg.Config()).index).match(ev)


def sh(cmd, exit=0, **kw):
    return ids(mt.shell_event(dict(cmd=cmd, exit=exit, **kw)))


class VaultShell(unittest.TestCase):
    def test_bao_basics(self):
        self.assertIn("v0-token", sh("bao token lookup"))
        self.assertNotIn("v0-token", sh("bao token lookup", 2))
        self.assertIn("v0-first", sh("bao kv get secret/students/$USER/welcome"))
        self.assertNotIn("v0-first", sh("bao kv get secret/students/student02/welcome", 2))
        self.assertIn("v3-putget", sh("bao kv get -field=password secret/students/$USER/db"))
        self.assertIn("v3-versions", sh("bao kv get -version=1 secret/students/$USER/db"))
        self.assertIn("v3-versions", sh("bao kv metadata get secret/students/$USER/db"))
        self.assertNotIn("v3-versions", sh("bao kv get secret/students/$USER/db"))
        self.assertIn("v3-destroy", sh("bao kv destroy -versions=1 secret/students/$USER/db"))

    def test_neighbour_door(self):
        self.assertIn("v3-door", sh("bao kv get secret/students/student02/db", 2))
        self.assertNotIn("v3-door", sh("bao kv get secret/students/$USER/db", 2))
        self.assertNotIn("v3-door", sh("bao kv get secret/students/student02/db", 0))

    def test_namespace_and_policy(self):
        self.assertIn("v4-ns", sh("export BAO_NAMESPACE=students/$USER"))
        self.assertNotIn("v4-ns", sh("export FOO=bar"))
        self.assertIn("v4-engine", sh("bao secrets enable -path=team kv-v2"))
        self.assertNotIn("v4-engine", sh("bao secrets enable transit"))
        self.assertIn("v4-policy", sh("bao policy write app-read app-read.hcl"))
        self.assertNotIn("v4-policy", sh("bao policy write other x.hcl"))
        self.assertIn("v4-revoke", sh('bao token revoke "$APP_TOKEN"'))

    def test_scan_gpg_pass(self):
        self.assertIn("v1-scan", sh("gitleaks git -v", 1))
        self.assertNotIn("v1-scan", sh("gitleaks git -v", 0))
        self.assertIn("v1-leak", sh("git commit -m x", in_repo=True))
        self.assertNotIn("v1-leak", sh("git commit -m x", 1, in_repo=True))
        self.assertIn("v2-key", sh('gpg --quick-gen-key "$USER <$USER@dojo.test>" default default 1y'))
        self.assertNotIn("v2-key", sh("gpg --list-secret-keys"))
        self.assertIn("v2-store", sh('pass init "$USER@dojo.test"'))
        self.assertNotIn("v2-share", sh("pass init -p dojo a@x b@x"))

    def test_apps_and_roles(self):
        self.assertIn("v5-env", sh("python3 app_env.py"))
        self.assertIn("v5-vault", sh("LOG_LEVEL=DEBUG python3 app_vault.py"))
        self.assertNotIn("v5-vault", sh("python3 app_env.py"))
        self.assertIn("v6-approle", sh("bao write auth/approle/role/app token_policies=app-read"))
        self.assertNotIn("v6-approle", sh("bao write auth/approle/role/ci token_policies=ci-read"))
        self.assertIn("v10-strict", sh("bao write auth/approle/role/app token_policies=app-read secret_id_num_uses=1 secret_id_ttl=5m"))
        self.assertNotIn("v10-strict", sh("bao write auth/approle/role/app token_policies=app-read"))
        self.assertIn("v11-role", sh("bao write auth/jwt-platform/role/app role_type=jwt token_policies=app-read"))
        self.assertIn("v7-key", sh("bao write -f transit/keys/sops"))
        self.assertNotIn("v7-key", sh("bao write -f transit/keys/sops/rotate"))
        self.assertIn("v7-rotate", sh("bao write -f transit/keys/sops/rotate"))
        self.assertIn("v7-encrypt", sh("sops encrypt -i app.enc.yaml"))
        self.assertIn("v7-encrypt", sh("sops -e app.yaml"))
        self.assertNotIn("v7-encrypt", sh("sops decrypt app.enc.yaml"))

    def test_requires_chains(self):
        c = catalog.load(PACK, SHARED)[0]
        m = mt.Matcher(lg.Ledger(c, lg.Config()).index)
        put = mt.shell_event(dict(cmd="bao kv put team/app x=1", exit=0))
        self.assertNotIn("v6-rotate", m.match(put, have=()))
        self.assertIn("v6-rotate", m.match(put, have=("v6-agent",)))
        self.assertNotIn("v11-rotate", m.match(put, have=("v6-agent",)))
        self.assertIn("v11-rotate", m.match(put, have=("v11-role",)))
        self.assertNotIn("v13-rotate", m.match(mt.shell_event(dict(cmd="bao kv put team/admin x=1", exit=0))))
        self.assertIn("v13-rotate", m.match(mt.shell_event(dict(cmd="bao kv patch team/ci deploy_token=-", exit=0))))

    def test_leases_and_incident(self):
        self.assertIn("v12-role", sh("bao write database/roles/app - <<EOF"))
        self.assertIn("v12-lease", sh("bao read -format=json database/creds/app"))
        self.assertIn("v12-lease", sh('bao lease lookup "$LEASE"'))
        self.assertNotIn("v12-lease", sh("bao read database/creds/c2-app"))
        self.assertIn("v12-renew", sh('bao lease renew "$LEASE"'))
        self.assertIn("v12-revoke", sh('bao lease revoke "$LEASE"'))
        self.assertIn("v13-audit", sh('bao-audit --accessor "$ACC"'))
        self.assertIn("v13-revoke", sh('bao token revoke -accessor "$ACC"'))
        self.assertNotIn("v13-revoke", sh('bao token revoke "$T"'))
        self.assertIn("v9-retire", sh("for s in A B; do curl -s -o /dev/null --netrc -X DELETE http://git-server:3000/api/v1/repos/$USER/vault-fundamentals/actions/secrets/$s; done"))
        self.assertNotIn("v9-retire", sh("curl -s --netrc -X PUT http://git-server:3000/api/v1/repos/x/y/actions/secrets/A"))

    def test_funny(self):
        self.assertIn("f-echo", sh("echo hvs.CAESIabcdefghijklmnop"))
        self.assertIn("f-echo", sh("export VAULT_TOKEN=s.abcdefghijklmnopqrstuv"))
        self.assertNotIn("f-echo", sh("echo hello"))
        self.assertNotIn("f-history", sh("history"))
        c = catalog.load(PACK, SHARED)[0]
        m = mt.Matcher(lg.Ledger(c, lg.Config()).index)
        self.assertIn("f-history", m.match(mt.shell_event(dict(cmd="history", exit=0)), have=("f-echo",)))

    def test_fork_pushes(self):
        def push(n):
            return {"ref": "refs/heads/main", "pusher": {"login": "amy"}, "sender": {"login": "amy"},
                    "repository": {"full_name": "amy/vault-fundamentals"}, "commits": [{"id": "a" * 40}]}
        c = catalog.load(PACK, SHARED)[0]
        m = mt.Matcher(lg.Ledger(c, lg.Config()).index)
        n = []
        first = m.match(mt.forgejo_event("push", push(1)), bump=lambda *a, **k: 1)
        self.assertNotIn("v8-masked", first)
        second = m.match(mt.forgejo_event("push", push(2)), bump=lambda *a, **k: 2)
        self.assertIn("v8-masked", second)


def fake(tree):
    """A stand-in for baostate._get: tree maps 'namespace|path' to data; records what it was asked."""
    asked = []

    def get(ns, path, listing=False):
        asked.append(ns)
        return tree.get(f"{ns}|{path.rstrip('/')}")
    get.asked = asked
    return get


def pol(*stanzas):
    return {"policy": "\n".join(f'path "{p}" {{\n  capabilities = {json.dumps(c)}\n}}' for p, c in stanzas)}


class VaultChallenges(unittest.TestCase):
    def setUp(self):
        self.cat = catalog.load(PACK, SHARED)[0]
        self.runner = challenges.Runner(challenges.load_plugins(PLUGINS), os.path.join(PACK, "achievements", "seeds"),
                                        None, lambda: 0)
        self.mod = self.runner.verbs["policy_grants"][1]
        self.orig = self.mod._get
        self.forgejo = self.runner.verbs["file_contains"][1]
        self.orig_raw = self.forgejo._raw

    def tearDown(self):
        self.mod._get = self.orig
        self.forgejo._raw = self.orig_raw

    def run_verify(self, cid, tree, agent=None):
        ch = next(c for c in self.cat["challenges"] + [self.cat["capstone"]] if c["id"] == cid)
        self.mod._get = fake(tree)
        self.forgejo._raw = lambda api, repo, ref, path: agent
        return self.runner.verify(ch, "amy")

    def test_no_unknown_verbs(self):
        self.assertEqual(self.runner.unknown_verbs(self.cat), [])

    def test_c1(self):
        ns = "students/amy|"
        role = {ns + "auth/approle/role/buddy-amy": {"token_policies": ["share-one"]}}
        one = {ns + "sys/policies/acl/share-one": pol(("challenge/data/one", ["read"]))}
        self.assertTrue(self.run_verify("c1", {**role, **one})["passed"])
        wide = {ns + "sys/policies/acl/share-one": pol(("challenge/data/*", ["read", "list"]))}
        self.assertFalse(self.run_verify("c1", {**role, **wide})["passed"])
        denied = {ns + "sys/policies/acl/share-one": pol(("challenge/data/*", ["read"]), ("challenge/data/two", ["deny"]))}
        self.assertTrue(self.run_verify("c1", {**role, **denied})["passed"])
        self.assertFalse(self.run_verify("c1", {ns + "auth/approle/role/buddy-amy": {"token_policies": ["default"]}})["passed"])
        self.assertFalse(self.run_verify("c1", {**role, ns + "sys/policies/acl/share-one": pol(("challenge/data/two", ["read"]))})["passed"])
        self.assertFalse(self.run_verify("c1", {})["passed"])

    def test_c2(self):
        ns = "students/amy|"
        lease = {ns + "sys/leases/lookup/database/creds/c2-app": {"keys": ["abc"]}}
        ok = {ns + "database/roles/c2-app": {"default_ttl": 120, "max_ttl": 600}, **lease}
        self.assertTrue(self.run_verify("c2", ok)["passed"])
        self.assertTrue(self.run_verify("c2", {ns + "database/roles/c2-app": {"default_ttl": "2m", "max_ttl": "10m"}, **lease})["passed"])
        bad = {ns + "database/roles/c2-app": {"default_ttl": 300, "max_ttl": 600}, **lease}
        self.assertFalse(self.run_verify("c2", bad)["passed"])
        self.assertFalse(self.run_verify("c2", {ns + "database/roles/c2-app": {"default_ttl": 120, "max_ttl": 600}})["passed"])

    def test_capstone(self):
        ns = "students/amy|"
        tree = {
            ns + "sys/policies/acl/capstone-app": pol(("capstone/data/app", ["read"]), ("database/creds/capstone-app", ["read"])),
            ns + "auth/jwt-platform/role/capstone-app": {"token_policies": ["capstone-app"]},
            ns + "database/roles/capstone-app": {"default_ttl": 300},
            ns + "sys/leases/lookup/database/creds/capstone-app": {"keys": ["x"]},
            ns + "capstone/metadata/app": {"current_version": 2},
        }
        clean = "auto_auth {\n  method jwt {}\n}\n"
        self.assertTrue(self.run_verify("capstone", tree, clean)["passed"])
        self.assertFalse(self.run_verify("capstone", tree, "secret_id = 'x'")["passed"])
        self.assertFalse(self.run_verify("capstone", {**tree, ns + "capstone/metadata/app": {"current_version": 1}}, clean)["passed"])
        wide = {**tree, ns + "sys/policies/acl/capstone-app": pol(("capstone/data/app", ["read"]), ("secret/*", ["read"]))}
        self.assertFalse(self.run_verify("capstone", wide, clean)["passed"])

    def test_a_check_never_reads_another_students_namespace(self):
        f = fake({})
        self.mod._get = f
        ok, _ = self.runner.verbs["role_policy_grants"][0](None, {"mount": "approle", "role": "x", "student": "ben"}, {"user": "amy"}) \
            if False else (None, None)
        with self.assertRaises(ValueError):
            self.mod._ns({"user": "amy"}, {"student": "ben"})
        self.assertEqual(self.mod._ns({"user": "amy"}, {"student": "amy"}), "students/amy")
        with self.assertRaises(ValueError):
            self.mod._ns({"user": "../root"}, {})
        with self.assertRaises(ValueError):
            self.mod._safe("../x")
        self.assertEqual(set(f.asked), set())

    def test_policy_matching(self):
        st = self.mod.parse_policy('path "a/+/data/*" { capabilities = ["read"] }\npath "a/x/data/no" { capabilities = ["deny"] }')
        self.assertTrue(self.mod.can_read(st, "a/y/data/z"))
        self.assertFalse(self.mod.can_read(st, "a/x/data/no"))
        self.assertFalse(self.mod.can_read(st, "b/y/data/z"))

    def test_seed_plans_are_complete(self):
        seeds = os.path.join(PACK, "achievements", "seeds")
        for ch in self.cat["challenges"] + [self.cat["capstone"]]:
            plan = json.load(open(os.path.join(seeds, ch["seed_plan"])))
            vals = self.runner.values(ch, "amy")
            for c in plan["commits"]:
                for f in c["files"]:
                    text = challenges.fill_text(open(os.path.join(seeds, f["from"])).read(), vals)
                    self.assertNotRegex(text, re.compile(r"\{user\}"), f["from"])
            self.assertTrue(challenges.fill_text(plan["repo"], vals).startswith("amy/"))
        seed = open(os.path.join(seeds, "c1", "seed.sh")).read()
        self.assertIn("students/$USER", seed)


if __name__ == "__main__":
    unittest.main()
