"""Dojo Cloud's fake Azure Policy API over HTTP: definitions, sets, assignments, exemptions, remediations,
enforcement on resource writes, stored compliance, the portal's Policy blade, and purge. A fake host stands in for
Docker. Run from this directory:  python3 -B -m unittest test_policy_api
"""
import datetime
import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import auth
import policy
import policy_api
import policy_engine as engine
import portal_api
import server
import state as state_mod
from test_portal_api import Headers  # noqa: F401  (dict with case-insensitive get)
from test_readiness import FakeHost

TOKEN = "gw-secret-token"
A, B, FAC = "student01", "student02", "admin"
SUB = {u: auth.subscription_id(u) for u in (A, B, FAC)}
TAGS = {"owner": "someone", "env": "dev"}
AUTHZ = "providers/Microsoft.Authorization"
CG_TYPE = {"field": "type", "equals": engine.CG}


def when_env(value):
    return {"allOf": [CG_TYPE, {"field": "tags['env']", "equals": value}]}


def definition(rule_if, effect="deny", params=None, details=None):
    then = {"effect": effect}
    if details is not None:
        then["details"] = details
    return {"properties": {"displayName": "A rule", "description": "x", "mode": "All", "policyType": "Custom",
                           "policyRule": {"if": rule_if, "then": then}, "parameters": params or {}, "metadata": {}}}


def add_tag(name="costcenter", value="dojo"):
    return definition(CG_TYPE, "modify", details={"roleDefinitionIds": [], "operations": [
        {"operation": "addOrReplace", "field": f"tags['{name}']", "value": value}]})


def assignment(definition_id, message="", **props):
    p = {"displayName": "An assignment", "policyDefinitionId": definition_id, "enforcementMode": "Default",
         "parameters": {}}
    if message:
        p["nonComplianceMessages"] = [{"message": message}]
    p.update(props)
    return {"properties": p}


class Base(unittest.TestCase):
    def setUp(self):
        self.host = FakeHost()
        self.st = state_mod.State(None)
        self.app = server.App(auth.Auth(b"k" * 32, [A, B, FAC], FAC, "iss"), self.st, self.host)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = {"GATEWAY_TOKEN": TOKEN}
        self.portal = portal_api.Portal(self.app, self.env, self.tmp.name)
        self.app.portal = self.portal
        old = (server.APP, server.log, server.LIMIT)
        server.APP, server.log, server.LIMIT = self.app, lambda msg: None, server.RateLimit(10 ** 6, 10 ** 6)
        self.addCleanup(lambda: (setattr(server, "APP", old[0]), setattr(server, "log", old[1]),
                                 setattr(server, "LIMIT", old[2])))
        self.app.reconciled.set()
        self.app.readiness.refresh()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, args=(0.01,), daemon=True).start()
        self.addCleanup(lambda: (self.httpd.shutdown(), self.httpd.server_close()))
        self.assertEqual(self.arm("PUT", f"/subscriptions/{SUB[A]}/resourceGroups/rg-aaa",
                                  {"location": "canadacentral", "tags": TAGS})[0], 201)

    # ---- plumbing ----
    def raw(self, method, path, body=None, user=A, headers=None):
        tok = {"Authorization": "Bearer " + self.app.auth.issue_token(user, "aud")} if user else {}
        tok.update(headers or {})
        conn = http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1], timeout=5)
        conn.request(method, path, body=None if body is None else json.dumps(body), headers=tok)
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        return resp, (json.loads(data) if data else None)

    def arm(self, method, path, body=None, user=A):
        resp, data = self.raw(method, path, body, user)
        return resp.status, data

    def portal_get(self, user, query=""):
        h = Headers()
        h["x-auth-user"], h["x-gateway-token"] = user, TOKEN
        status, _headers, data = self.portal.dispatch("GET", "/cloud/api/policy", parse_qs(query), h, b"")
        return status, json.loads(data)

    # ---- URLs and bodies ----
    def sub_path(self, kind, name, user=A):
        return f"/subscriptions/{SUB[user]}/{AUTHZ}/{kind}/{name}?api-version=2021-06-01"

    def def_id(self, name, user=A):
        return f"/subscriptions/{SUB[user]}/{AUTHZ}/policyDefinitions/{name}"

    def assign_path(self, name, rg=None, user=A):
        rg_part = f"/resourceGroups/{rg}" if rg else ""
        return f"/subscriptions/{SUB[user]}{rg_part}/{AUTHZ}/policyAssignments/{name}?api-version=2022-06-01"

    def assign_id(self, name, rg=None, user=A):
        return self.assign_path(name, rg, user).split("?")[0]

    def cg_path(self, name="ci-a1", rg="rg-aaa", user=A):
        return (f"/subscriptions/{SUB[user]}/resourceGroups/{rg}/providers/Microsoft.ContainerInstance/"
                f"containerGroups/{name}")

    def cg_body(self, label="site-a1", env="dev"):
        return {"location": "canadacentral", "tags": {"owner": "someone", "env": env}, "properties": {
            "osType": "Linux", "ipAddress": {"type": "Public", "dnsNameLabel": label, "ports": [{"port": 80}]},
            "containers": [{"name": "hello", "properties": {
                "image": "dojo/hello:1.0", "ports": [{"port": 80},],
                "resources": {"requests": {"cpu": 0.25, "memoryInGB": 0.125}}}}]}}

    def put_cg(self, name="ci-a1", label="site-a1", env="dev"):
        return self.arm("PUT", self.cg_path(name), self.cg_body(label, env))

    def make_def(self, name, body):
        status, out = self.arm("PUT", self.sub_path("policyDefinitions", name), body)
        self.assertIn(status, (200, 201), out)
        return out["id"]

    def make_assignment(self, name, did, **kw):
        status, out = self.arm("PUT", self.assign_path(name), assignment(did, **kw))
        self.assertIn(status, (200, 201), out)
        return out["id"]

    def compliance(self, user=A):
        status, out = self.arm("GET", f"/subscriptions/{SUB[user]}/providers/Microsoft.PolicyInsights/"
                                      "policyStates/latest/queryResults?api-version=2019-10-01")
        self.assertEqual(status, 200)
        return out["value"]

    def cg_rows(self, name="ci-a1"):
        """Stored compliance rows of one container group (the resource group has rows too)."""
        return [r for r in self.compliance() if r["resourceId"].endswith("/" + name)]


class Definitions(Base):
    def test_create_201_then_update_200_and_the_echo(self):
        body = definition(when_env("prod"))
        status, out = self.arm("PUT", self.sub_path("policyDefinitions", "no-prod"), body)
        self.assertEqual(status, 201)
        self.assertEqual((out["name"], out["type"], out["id"]),
                         ("no-prod", "Microsoft.Authorization/policyDefinitions", self.def_id("no-prod")))
        self.assertEqual(out["properties"]["provisioningState"], "Succeeded")
        self.assertEqual(out["properties"]["policyType"], "Custom")
        self.assertEqual(out["properties"]["policyRule"], body["properties"]["policyRule"])
        self.assertEqual(self.arm("PUT", self.sub_path("policyDefinitions", "no-prod"), body)[0], 201)  # ARM and azurerm: 201 on update too
        self.assertEqual(self.arm("GET", self.sub_path("policyDefinitions", "no-prod"))[1]["id"], out["id"])

    def test_builtins_by_the_global_path_and_in_the_list(self):
        status, out = self.arm("GET", "/providers/Microsoft.Authorization/policyDefinitions/dojo-max-cpu"
                                      "?api-version=2021-06-01")
        self.assertEqual((status, out["properties"]["policyType"]), (200, "BuiltIn"))
        self.assertEqual(self.arm("GET", "/providers/Microsoft.Authorization/policyDefinitions/nope")[0], 404)
        self.assertEqual(self.arm("PUT", "/providers/Microsoft.Authorization/policyDefinitions/x", {})[0], 405)
        resp, _ = self.raw("GET", "/providers/Microsoft.Authorization/policyDefinitions/dojo-max-cpu", user=None)
        self.assertEqual(resp.status, 401)
        self.make_def("no-prod", definition(when_env("prod")))
        status, out = self.arm("GET", f"/subscriptions/{SUB[A]}/{AUTHZ}/policyDefinitions?api-version=2021-06-01")
        names = [d["name"] for d in out["value"]]
        self.assertEqual(status, 200)
        self.assertIn("no-prod", names)
        self.assertIn("dojo-allowed-images", names)

    def test_invalid_rule_is_400_invalid_policy_rule(self):
        for body in (definition(when_env("prod"), effect="explode"), definition({"field": "location"}),
                     {"properties": {"policyRule": "not an object"}}):
            status, out = self.arm("PUT", self.sub_path("policyDefinitions", "bad"), body)
            self.assertEqual((status, out["error"]["code"]), (400, "InvalidPolicyRule"), body)
        self.assertEqual(self.arm("GET", self.sub_path("policyDefinitions", "bad"))[0], 404)
        self.assertEqual(self.arm("PUT", self.sub_path("policyDefinitions", "bad"), {"x": 1})[0], 400)

    def test_cross_subscription_is_refused_as_it_always_was(self):
        status, out = self.arm("PUT", self.sub_path("policyDefinitions", "x", user=B), definition(when_env("p")))
        self.assertEqual((status, out["error"]["code"]), (403, "AuthorizationFailed"))
        self.assertEqual(self.arm("GET", self.sub_path("policyDefinitions", "x", user=B))[0], 403)
        # the same error resources give today
        self.assertEqual(self.arm("GET", f"/subscriptions/{SUB[B]}/resourceGroups")[1]["error"]["code"],
                         "AuthorizationFailed")
        # the facilitator reaches any subscription
        self.assertEqual(self.arm("GET", self.sub_path("policyDefinitions", "x", user=B), user=FAC)[0], 404)

    def test_quota_is_50_per_kind(self):
        with self.st.lock:
            policy_api._pol(self.st, SUB[A])["definitions"] = {f"d{i}": {} for i in range(policy_api.QUOTA)}
        status, out = self.arm("PUT", self.sub_path("policyDefinitions", "one-more"), definition(when_env("p")))
        self.assertEqual((status, out["error"]["code"]), (400, "QuotaExceeded"))

    def test_delete_answers_200_then_204_and_get_is_404(self):
        self.make_def("no-prod", definition(when_env("prod")))
        self.assertEqual(self.arm("DELETE", self.sub_path("policyDefinitions", "no-prod"))[0], 200)
        self.assertEqual(self.arm("GET", self.sub_path("policyDefinitions", "no-prod"))[0], 404)
        self.assertEqual(self.arm("DELETE", self.sub_path("policyDefinitions", "no-prod"))[0], 204)

    def test_delete_in_use_is_400_and_works_after_the_assignment_goes(self):
        did = self.make_def("no-prod", definition(when_env("prod")))
        self.make_assignment("a1", did)
        status, out = self.arm("DELETE", self.sub_path("policyDefinitions", "no-prod"))
        self.assertEqual((status, out["error"]["code"]), (400, "PolicyDefinitionInUse"))
        self.assertEqual(self.arm("DELETE", self.assign_path("a1"))[0], 200)
        self.assertEqual(self.arm("DELETE", self.sub_path("policyDefinitions", "no-prod"))[0], 200)

    def test_an_update_that_breaks_an_assignment_is_refused(self):
        params = {"env": {"type": "String", "defaultValue": "prod"}}
        did = self.make_def("p", definition({"allOf": [CG_TYPE, {"field": "tags['env']",
                                                                   "equals": "[parameters('env')]"}]}, params=params))
        self.make_assignment("a1", did, parameters={"env": {"value": "prod"}})
        status, out = self.arm("PUT", self.sub_path("policyDefinitions", "p"),
                               definition({"allOf": [CG_TYPE, {"field": "tags['env']", "equals": "prod"}]}))
        self.assertEqual((status, out["error"]["code"]), (400, "InvalidPolicyParameters"))


class Sets(Base):
    def set_body(self, *refs):
        return {"properties": {"displayName": "A set", "policyDefinitions": [
            {"policyDefinitionId": did, "policyDefinitionReferenceId": ref, "groupNames": [], "parameters": {}}
            for ref, did in refs]}}

    def test_set_create_assign_deny_and_delete_rules(self):
        did = self.make_def("no-prod", definition(when_env("prod")))
        status, out = self.arm("PUT", self.sub_path("policySetDefinitions", "s1"), self.set_body(("r1", did)))
        self.assertEqual(status, 201)
        self.assertEqual(self.arm("PUT", self.sub_path("policySetDefinitions", "s1"), self.set_body(("r1", did)))[0], 201)
        status, out = self.arm("DELETE", self.sub_path("policyDefinitions", "no-prod"))
        self.assertEqual((status, out["error"]["code"]), (400, "PolicyDefinitionInUse"))  # a set includes it
        self.make_assignment("sa", f"/subscriptions/{SUB[A]}/{AUTHZ}/policySetDefinitions/s1",
                             message="Not in prod.")
        status, out = self.put_cg(env="prod")
        self.assertEqual((status, out["error"]["code"]), (403, "RequestDisallowedByPolicy"))
        self.assertIn("Not in prod.", out["error"]["message"])
        self.assertEqual(self.put_cg(env="dev")[0], 201)

    def test_a_set_with_a_missing_member_is_404(self):
        status, out = self.arm("PUT", self.sub_path("policySetDefinitions", "s1"),
                               self.set_body(("r1", self.def_id("ghost"))))
        self.assertEqual((status, out["error"]["code"]), (404, "PolicyDefinitionNotFound"))


class Assignments(Base):
    def test_create_and_update_201_identity_and_scopes(self):
        did = self.make_def("no-prod", definition(when_env("prod")))
        body = assignment(did)
        body.update({"identity": {"type": "SystemAssigned"}, "location": "canadacentral"})
        status, out = self.arm("PUT", self.assign_path("a1"), body)
        self.assertEqual(status, 201)
        self.assertEqual(out["id"], self.assign_id("a1"))
        self.assertEqual(out["properties"]["scope"], f"/subscriptions/{SUB[A]}")
        self.assertEqual(out["identity"]["tenantId"], auth.TENANT_ID)
        principal = out["identity"]["principalId"]
        self.assertEqual(out["location"], "canadacentral")
        status, out = self.arm("PUT", self.assign_path("a1"), body)
        self.assertEqual((status, out["identity"]["principalId"]), (201, principal))  # stable; 201 on update too, which azurerm requires
        status, out = self.arm("PUT", self.assign_path("a2", rg="rg-aaa"), assignment(did))  # on a resource group
        self.assertEqual((status, out["properties"]["scope"]), (201, f"/subscriptions/{SUB[A]}/resourceGroups/rg-aaa"))
        self.assertEqual(self.arm("PUT", self.assign_path("a3", rg="rg-none"), assignment(did))[0], 404)

    def test_other_subscription_scope_and_cross_subscription_paths_are_refused(self):
        did = self.make_def("no-prod", definition(when_env("prod")))
        self.assertEqual(self.arm("PUT", self.assign_path("a1", user=B), assignment(did))[0], 403)
        for bad in ({"scope": f"/subscriptions/{SUB[B]}"}, {"notScopes": [f"/subscriptions/{SUB[B]}"]}):
            status, out = self.arm("PUT", self.assign_path("a1"), assignment(did, **bad))
            self.assertEqual((status, out["error"]["code"]), (403, "AuthorizationFailed"), bad)
        # a definition id from another subscription does not exist here
        other = self.def_id("no-prod", user=B)
        self.assertEqual(self.arm("PUT", self.assign_path("a1"), assignment(other))[0], 404)

    def test_missing_definition_is_404_policy_definition_not_found(self):
        status, out = self.arm("PUT", self.assign_path("a1"), assignment(self.def_id("ghost")))
        self.assertEqual((status, out["error"]["code"]), (404, "PolicyDefinitionNotFound"))
        self.assertEqual(self.arm("GET", self.assign_path("a1"))[0], 404)

    def test_parameters_must_resolve(self):
        params = {"env": {"type": "String"}}  # no default
        did = self.make_def("p", definition({"allOf": [CG_TYPE, {"field": "tags['env']",
                                                                   "equals": "[parameters('env')]"}]}, params=params))
        for p in ({}, {"nope": {"value": 1}}, {"env": {"value": 5}}):
            status, out = self.arm("PUT", self.assign_path("a1"), assignment(did, parameters=p))
            self.assertEqual((status, out["error"]["code"]), (400, "InvalidPolicyParameters"), p)
        self.assertEqual(self.arm("PUT", self.assign_path("a1"), assignment(did, parameters={"env": {"value": "x"}}))[0], 201)

    def test_a_builtin_can_be_assigned(self):
        bid = "/providers/Microsoft.Authorization/policyDefinitions/dojo-max-cpu"
        status, out = self.arm("PUT", self.assign_path("cpu"), assignment(bid, parameters={"maxCpu": {"value": 0.1}}))
        self.assertEqual(status, 201)
        status, out = self.put_cg()  # the platform's 0.25 passes, the student's 0.1 does not
        self.assertEqual((status, out["error"]["code"]), (403, "RequestDisallowedByPolicy"))

    def test_unset_display_name_and_parameters_are_not_echoed(self):
        # azurerm leaves both optional: a filled-in default reads as drift on every plan (Lab 12's drift job)
        bid = "/providers/Microsoft.Authorization/policyDefinitions/dojo-require-tag-env"
        body = {"properties": {"policyDefinitionId": bid, "enforcementMode": "Default"}}
        status, out = self.arm("PUT", self.assign_path("bare"), body)
        self.assertEqual(status, 201)
        status, out = self.arm("GET", self.assign_path("bare"))
        self.assertEqual(status, 200)
        self.assertNotIn("displayName", out["properties"])
        self.assertNotIn("parameters", out["properties"])


class Enforcement(Base):
    def test_deny_on_a_container_group_names_assignment_definition_and_message(self):
        did = self.make_def("no-prod", definition(when_env("prod")))
        self.make_assignment("block-prod", did, message="Production is off limits here.")
        self.host.calls.clear()
        status, out = self.put_cg(env="prod")
        self.assertEqual((status, out["error"]["code"], out["error"]["target"]), (403, "RequestDisallowedByPolicy", "ci-a1"))
        msg = out["error"]["message"]
        self.assertIn("block-prod", msg)
        self.assertIn("A rule", msg)
        self.assertIn("Production is off limits here.", msg)
        self.assertEqual(self.host.mutating_calls(), [])  # nothing was created
        self.assertEqual(self.arm("GET", self.cg_path())[0], 404)
        self.assertEqual(self.put_cg(env="dev")[0], 201)
        self.assertEqual(self.st.data["activity"][-2]["status"], "Failed")

    def test_deny_on_a_resource_group(self):
        did = self.make_def("no-rg-prod", definition({"allOf": [{"field": "type", "equals": engine.RG},
                                                                {"field": "tags['env']", "equals": "prod"}]}))
        self.make_assignment("a1", did)
        status, out = self.arm("PUT", f"/subscriptions/{SUB[A]}/resourceGroups/rg-b2",
                               {"location": "canadacentral", "tags": {"owner": "x", "env": "prod"}})
        self.assertEqual((status, out["error"]["code"]), (403, "RequestDisallowedByPolicy"))

    def test_a_tags_only_patch_cannot_sidestep_a_deny(self):
        self.assertEqual(self.put_cg()[0], 201)
        did = self.make_def("no-prod", definition(when_env("prod")))
        self.make_assignment("a1", did)
        rg_did = self.make_def("no-rg-prod", definition({"allOf": [{"field": "type", "equals": engine.RG},
                                                                   {"field": "tags['env']", "equals": "prod"}]}))
        self.make_assignment("a2", rg_did)
        prod = {"tags": {"owner": "x", "env": "prod"}}
        status, out = self.arm("PATCH", f"/subscriptions/{SUB[A]}/resourceGroups/rg-aaa", prod)
        self.assertEqual((status, out["error"]["code"]), (403, "RequestDisallowedByPolicy"))
        status, out = self.arm("PATCH", self.cg_path(), prod)
        self.assertEqual((status, out["error"]["code"]), (403, "RequestDisallowedByPolicy"))
        self.assertEqual(self.arm("GET", self.cg_path())[1]["tags"]["env"], "dev")

    def test_modify_adds_a_tag_that_is_stored(self):
        did = self.make_def("tagger", add_tag())
        self.make_assignment("a1", did)
        status, out = self.put_cg()
        self.assertEqual(status, 201)
        self.assertEqual(out["tags"]["costcenter"], "dojo")
        self.assertEqual(self.arm("GET", self.cg_path())[1]["tags"]["costcenter"], "dojo")
        self.assertEqual(self.cg_rows()[0]["complianceState"], "Compliant")

    def test_audit_lets_the_write_through_and_records_it(self):
        did = self.make_def("audit-dev", definition(when_env("dev"), "audit"))
        self.make_assignment("a1", did)
        self.assertEqual(self.put_cg()[0], 201)
        rows = [r for r in self.compliance() if r["resourceId"].endswith("/ci-a1")]
        self.assertEqual([(r["policyAssignmentId"], r["policyDefinitionId"], r["complianceState"]) for r in rows],
                         [(self.assign_id("a1"), did, "NonCompliant")])
        for key in ("timestamp", "policyDefinitionReferenceId", "resourceId"):
            self.assertIn(key, rows[0])

    def test_do_not_enforce_never_blocks(self):
        did = self.make_def("no-prod", definition(when_env("prod")))
        self.make_assignment("a1", did, enforcementMode="DoNotEnforce")
        self.assertEqual(self.put_cg(env="prod")[0], 201)

    def exempt(self, expires=None, category="Waiver"):
        body = {"properties": {"policyAssignmentId": self.assign_id("block"), "exemptionCategory": category,
                               "displayName": "waive", "description": "why"}}
        if expires:
            body["properties"]["expiresOn"] = expires
        return self.arm("PUT", f"/subscriptions/{SUB[A]}/resourceGroups/rg-aaa/{AUTHZ}/policyExemptions/ex1"
                                "?api-version=2020-07-01-preview", body)

    def test_an_exemption_bypasses_a_deny(self):
        self.make_assignment("block", self.make_def("no-prod", definition(when_env("prod"))))
        self.assertEqual(self.put_cg(env="prod")[0], 403)
        status, out = self.exempt()
        self.assertEqual((status, out["type"]), (201, "Microsoft.Authorization/policyExemptions"))
        self.assertEqual(self.exempt()[0], 200)
        self.assertEqual(self.put_cg(env="prod")[0], 201)
        self.assertEqual([r["complianceState"] for r in self.compliance() if r["resourceId"].endswith("/ci-a1")],
                         ["Exempt"])

    def test_an_expired_exemption_does_not_bypass(self):
        self.make_assignment("block", self.make_def("no-prod", definition(when_env("prod"))))
        past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).isoformat()
        self.assertEqual(self.exempt(expires=past)[0], 201)
        self.assertEqual(self.put_cg(env="prod")[0], 403)
        future = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).isoformat()
        self.assertEqual(self.exempt(expires=future)[0], 200)
        self.assertEqual(self.put_cg(env="prod")[0], 201)

    def test_exemption_needs_a_real_assignment_and_category(self):
        self.make_assignment("block", self.make_def("no-prod", definition(when_env("prod"))))
        path = f"/subscriptions/{SUB[A]}/resourceGroups/rg-aaa/{AUTHZ}/policyExemptions/ex1"
        self.assertEqual(self.arm("PUT", path, {"properties": {"policyAssignmentId": self.assign_id("ghost"),
                                                               "exemptionCategory": "Waiver"}})[0], 404)
        self.assertEqual(self.arm("PUT", path, {"properties": {"policyAssignmentId": self.assign_id("block"),
                                                               "exemptionCategory": "Maybe"}})[0], 400)

    def test_remediation_applies_modify_to_existing_resources(self):
        self.assertEqual(self.put_cg()[0], 201)  # before any policy
        self.make_assignment("a1", self.make_def("tagger", add_tag()))
        self.assertEqual(self.cg_rows()[0]["complianceState"], "NonCompliant")
        self.assertNotIn("costcenter", self.arm("GET", self.cg_path())[1]["tags"])
        path = (f"/subscriptions/{SUB[A]}/resourceGroups/rg-aaa/providers/Microsoft.PolicyInsights/remediations/r1"
                "?api-version=2021-10-01")
        status, out = self.arm("PUT", path, {"properties": {"policyAssignmentId": self.assign_id("a1"),
                                                            "resourceDiscoveryMode": "ExistingNonCompliant"}})
        self.assertEqual(status, 201)
        self.assertEqual(out["properties"]["provisioningState"], "Succeeded")
        self.assertEqual(out["properties"]["deploymentStatus"],
                         {"totalDeployments": 1, "successfulDeployments": 1, "failedDeployments": 0})
        self.assertEqual(self.arm("GET", self.cg_path())[1]["tags"]["costcenter"], "dojo")
        self.assertEqual(self.cg_rows()[0]["complianceState"], "Compliant")
        self.assertEqual(self.arm("GET", path)[0], 200)
        self.assertEqual(self.arm("PUT", path, {"properties": {"policyAssignmentId": self.assign_id("ghost")}})[0], 404)

    def test_compliance_is_computed_on_writes_and_trigger_never_on_a_poll(self):
        self.make_assignment("a1", self.make_def("audit-dev", definition(when_env("dev"), "audit")))
        self.assertEqual(self.put_cg()[0], 201)
        self.assertEqual(len([r for r in self.compliance() if r["resourceId"].endswith("/ci-a1")]), 1)
        with self.st.lock:  # change the world behind policy's back
            self.st.cgs.clear()
        self.assertEqual(len([r for r in self.compliance() if r["resourceId"].endswith("/ci-a1")]), 1)  # a poll is stale
        trigger = f"/subscriptions/{SUB[A]}/providers/Microsoft.PolicyInsights/policyStates/latest/triggerEvaluation"
        resp, _ = self.raw("POST", trigger)
        self.assertEqual(resp.status, 202)
        self.assertIn("asyncOperationResults", resp.getheader("Location"))
        self.assertEqual(self.cg_rows(), [])
        self.assertEqual(self.arm("GET", resp.getheader("Location").replace(server.MGMT, ""))[0], 200)
        # POST works for the query too
        status, out = self.arm("POST", f"/subscriptions/{SUB[A]}/providers/Microsoft.PolicyInsights/"
                                       "policyStates/latest/queryResults")
        self.assertEqual((status, [r["resourceId"] for r in out["value"] if "ci-a1" in r["resourceId"]]), (200, []))

    def test_deleting_a_resource_updates_compliance(self):
        self.make_assignment("a1", self.make_def("audit-dev", definition(when_env("dev"), "audit")))
        self.put_cg()
        self.assertEqual(self.arm("DELETE", self.cg_path())[0], 200)
        self.assertEqual([r for r in self.compliance() if r["resourceId"].endswith("/ci-a1")], [])


class Unchanged(Base):
    def test_without_assignments_nothing_here_runs_and_nothing_is_stored(self):
        def boom(*a, **k):
            raise AssertionError("policy_api.enforce must not run without assignments")
        orig, policy_api.enforce = policy_api.enforce, boom
        self.addCleanup(lambda: setattr(policy_api, "enforce", orig))
        self.assertEqual(self.put_cg(env="prod")[0], 201)
        self.assertEqual(self.arm("PUT", f"/subscriptions/{SUB[A]}/resourceGroups/rg-zzz",
                                  {"location": "canadacentral", "tags": TAGS})[0], 201)
        self.assertEqual(self.arm("PATCH", self.cg_path(), {"tags": TAGS})[0], 200)
        self.assertEqual(self.arm("DELETE", self.cg_path())[0], 200)
        self.assertNotIn("policy", self.st.data)  # not even an empty document
        self.assertEqual(self.compliance(), [])

    def test_builtin_refusals_keep_their_exact_shape(self):
        status, out = self.arm("PUT", f"/subscriptions/{SUB[A]}/resourceGroups/rg-qqq",
                               {"location": "mars", "tags": TAGS})
        self.assertEqual(status, 403)
        self.assertEqual(out["error"]["code"], "RequestDisallowedByPolicy")
        self.assertEqual(set(out["error"]), {"code", "message", "target", "additionalInfo"})

    def test_a_definition_alone_does_not_enforce(self):
        self.make_def("no-prod", definition(when_env("prod")))
        self.assertEqual(self.put_cg(env="prod")[0], 201)


class PurgeAndPortal(Base):
    def populate(self):
        did = self.make_def("no-prod", definition(when_env("prod")))
        self.make_assignment("block", did, message="Nope.")
        self.make_assignment("tag", self.make_def("tagger", add_tag()))
        self.arm("PUT", f"/subscriptions/{SUB[A]}/resourceGroups/rg-aaa/{AUTHZ}/policyExemptions/ex1",
                 {"properties": {"policyAssignmentId": self.assign_id("block"), "exemptionCategory": "Mitigated"}})
        self.put_cg()
        self.arm("PUT", self.cg_path("ci-a2"), self.cg_body("site-a2", "prod"))

    def test_purge_clears_policy_objects_and_a_reset_does_too(self):
        self.populate()
        self.assertIn(SUB[A], self.st.data["policy"])
        status, _h, raw = self.portal._purge("student-reset", SUB[A])
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["removed"]["policyObjects"], 5)
        self.assertNotIn(SUB[A], self.st.data.get("policy", {}))
        self.assertEqual(self.arm("GET", self.assign_path("block"))[0], 404)
        self.assertEqual(self.arm("GET", self.sub_path("policyDefinitions", "no-prod"))[0], 404)
        self.assertEqual(self.compliance(), [])
        self.assertEqual(self.portal.student_reset(A, "teardown"), "removed 0 container group(s), 0 resource group(s)")

    def test_purge_leaves_other_subscriptions_policy(self):
        with self.st.lock:
            policy_api._pol(self.st, SUB[B])["definitions"]["x"] = {"id": "i", "name": "x", "properties": {}}
        self.portal._purge("t", SUB[A])
        self.assertIn(SUB[B], self.st.data["policy"])

    def test_portal_policy_blade_data(self):
        self.populate()
        status, doc = self.portal_get(A)
        self.assertEqual(status, 200)
        by_name = {a["name"]: a for a in doc["assignments"]}
        self.assertEqual(set(by_name), {"block", "tag"})
        self.assertEqual(by_name["tag"]["nonCompliant"], 0)  # the modify already tagged both groups
        self.assertEqual(by_name["block"]["exempt"], 3)  # the exemption covers the group and both container groups
        self.assertEqual([e["name"] for e in doc["exemptions"]], ["ex1"])
        self.assertFalse(doc["exemptions"][0]["expired"])
        self.assertIn("dojo-max-cpu", [b["name"] for b in doc["builtIns"]])
        self.assertTrue(all(b["readOnly"] for b in doc["builtIns"]))
        self.assertEqual(doc["subscriptionId"], SUB[A])

    def test_portal_lists_failing_resources_with_reasons(self):
        self.make_assignment("a1", self.make_def("audit-dev", definition(when_env("dev"), "audit")))
        self.put_cg()
        _status, doc = self.portal_get(A)
        a = doc["assignments"][0]
        self.assertEqual(a["nonCompliant"], 1)
        self.assertEqual(a["resources"][0]["name"], "ci-a1")
        self.assertTrue(a["resources"][0]["reason"])

    def test_portal_counts_refusals_per_assignment_until_it_is_deleted(self):
        self.make_assignment("block-prod", self.make_def("no-prod", definition(when_env("prod"))))
        self.assertEqual(self.portal_get(A)[1]["assignments"][0]["refusals"], 0)
        self.assertEqual(self.put_cg(env="prod")[0], 403)
        self.assertEqual(self.put_cg(env="prod")[0], 403)
        a = self.portal_get(A)[1]["assignments"][0]
        self.assertEqual(a["refusals"], 2)
        self.assertTrue(a["lastRefusal"])
        self.assertEqual(self.arm("DELETE", self.sub_path("policyAssignments", "block-prod"))[0], 200)
        self.make_assignment("block-prod", self.make_def("no-prod", definition(when_env("prod"))))
        self.assertEqual(self.portal_get(A)[1]["assignments"][0]["refusals"], 0)

    def test_portal_access_follows_arm(self):
        self.assertEqual(self.portal_get(B, f"subscription={SUB[A]}")[0], 403)
        self.assertEqual(self.portal_get(FAC, f"subscription={SUB[A]}")[0], 200)
        self.assertEqual(self.portal_get(FAC, "subscription=nope")[0], 404)
        self.assertEqual(self.portal_get(B)[1]["assignments"], [])


class PortalWrites(Base):
    def portal_call(self, user, method, path, body=None, query=""):
        h = Headers()
        h["x-auth-user"], h["x-gateway-token"] = user, TOKEN
        status, _h, data = self.portal.dispatch(method, path, parse_qs(query), h,
                                                b"" if body is None else json.dumps(body).encode())
        return status, json.loads(data)

    def audit_setup(self):
        self.make_assignment("a1", self.make_def("audit-dev", definition(when_env("dev"), "audit")))
        self.put_cg()

    def test_enforcement_toggle_recomputes_and_logs(self):
        self.make_assignment("block", self.make_def("no-dev", definition(when_env("dev"))))
        status, out = self.portal_call(A, "POST", "/cloud/api/policy/assignments/block/enforcement",
                                       {"mode": "DoNotEnforce"})
        self.assertEqual((status, out["enforcementMode"]), (200, "DoNotEnforce"))
        self.assertEqual(self.arm("GET", self.assign_path("block"))[1]["properties"]["enforcementMode"], "DoNotEnforce")
        self.assertEqual(self.arm("PUT", self.cg_path(), self.cg_body())[0], 201)  # no longer blocks
        self.assertEqual(self.portal_call(A, "POST", "/cloud/api/policy/assignments/block/enforcement",
                                          {"mode": "Default"})[0], 200)
        self.assertEqual(self.arm("PUT", self.cg_path("ci-a3"), self.cg_body("site-a3"))[0], 403)  # blocks again
        self.assertTrue(any("enforcementMode=Default" in e.get("message", "") for e in self.st.data["activity"]))

    def test_enforcement_rejects_bad_mode_and_unknown_assignment(self):
        self.audit_setup()
        self.assertEqual(self.portal_call(A, "POST", "/cloud/api/policy/assignments/a1/enforcement",
                                          {"mode": "Nope"})[0], 400)
        self.assertEqual(self.portal_call(A, "POST", "/cloud/api/policy/assignments/a1/enforcement", {})[0], 400)
        self.assertEqual(self.portal_call(A, "POST", "/cloud/api/policy/assignments/ghost/enforcement",
                                          {"mode": "Default"})[0], 404)
        self.assertEqual(self.portal_call(A, "GET", "/cloud/api/policy/assignments/a1/enforcement")[0], 405)

    def test_delete_assignment_removes_it_and_its_compliance(self):
        self.audit_setup()
        self.assertEqual(self.portal_get(A)[1]["assignments"][0]["nonCompliant"], 1)
        self.assertEqual(self.portal_call(A, "DELETE", "/cloud/api/policy/assignments/a1")[0], 200)
        self.assertEqual(self.portal_get(A)[1]["assignments"], [])
        self.assertEqual(self.compliance(), [])
        self.assertEqual(self.portal_call(A, "DELETE", "/cloud/api/policy/assignments/a1")[0], 404)

    def test_evaluate_recomputes_stored_compliance(self):
        self.audit_setup()
        with self.st.lock:  # stale on purpose: nothing recomputes until a write or this button
            policy_api._peek(self.st, SUB[A])["states"] = []
        self.assertEqual(self.portal_get(A)[1]["assignments"][0]["nonCompliant"], 0)
        self.assertEqual(self.portal_call(A, "POST", "/cloud/api/policy/evaluate")[0], 200)
        self.assertEqual(self.portal_get(A)[1]["assignments"][0]["nonCompliant"], 1)

    def test_writes_follow_ownership_and_the_facilitator_may_act_for_a_student(self):
        self.audit_setup()
        path = "/cloud/api/policy/assignments/a1"
        self.assertEqual(self.portal_call(B, "DELETE", path, query=f"subscription={SUB[A]}")[0], 403)
        self.assertEqual(self.portal_call(B, "DELETE", path)[0], 404)  # B's own subscription has none
        self.assertEqual(self.portal_call(FAC, "POST", "/cloud/api/policy/evaluate", query="subscription=nope")[0], 404)
        self.assertEqual(self.portal_call(FAC, "DELETE", path, query=f"subscription={SUB[A]}")[0], 200)

    def test_write_actions_switch_blocks_students_not_the_facilitator(self):
        self.audit_setup()
        with self.st.lock:
            self.st.data.setdefault("settings", {})["writeActions"] = False
        self.assertEqual(self.portal_call(A, "POST", "/cloud/api/policy/evaluate")[0], 403)
        self.assertEqual(self.portal_call(FAC, "POST", "/cloud/api/policy/evaluate",
                                          query=f"subscription={SUB[A]}")[0], 200)


class EventsReported(Base):
    """What policy work tells the achievements service (events.py): writes of the student's own policy objects,
    refusals by their own assignments, and a hand-made enforcement change on the portal; never the facilitator's."""

    portal_call = PortalWrites.portal_call

    def seen(self):
        return [e for e in self.rec.seen() if e[0] != "portal_request"]

    def setUp(self):
        super().setUp()
        from test_events import Recorder
        self.rec = Recorder()
        self.app.events = self.rec

    def test_writes_denials_and_portal_drift(self):
        did = self.make_def("no-prod", definition(when_env("prod")))
        self.make_assignment("block-prod", did)
        self.assertEqual(self.put_cg(env="prod")[0], 403)
        self.assertEqual(self.portal_call(A, "POST", "/cloud/api/policy/assignments/block-prod/enforcement",
                                          {"mode": "DoNotEnforce"})[0], 200)
        self.assertEqual(self.seen(), [("policy_written", A, "definition"), ("policy_written", A, "assignment"),
                                           ("policy_denied", A, "assignment"), ("policy_written", A, "portal")])

    def test_failed_writes_and_platform_refusals_are_not_policy_writes(self):
        self.assertEqual(self.arm("PUT", self.sub_path("policyDefinitions", "bad"), {"properties": {}})[0], 400)
        body = self.cg_body()
        body["location"] = "westus"
        self.assertEqual(self.arm("PUT", self.cg_path(), body)[0], 403)
        self.assertEqual(self.seen(), [("policy_denied", A, "region")])

    def test_the_facilitator_is_not_reported(self):
        st, _ = self.arm("PUT", self.sub_path("policyDefinitions", "f1", user=FAC), definition(when_env("prod")),
                         user=FAC)
        self.assertIn(st, (200, 201))
        self.assertEqual(self.seen(), [])


if __name__ == "__main__":
    unittest.main()
