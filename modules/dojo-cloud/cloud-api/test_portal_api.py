"""Dojo Portal backend: trust model, authorisation, write-actions toggle, purge,
static allow-list. No containers: a fake executor and an in-memory State.
Run from this directory:  python3 -m unittest test_portal_api
"""
import http.client
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
from http.server import ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import auth
import docker_api
import policy
import portal_api
import server
import state as state_mod

TOKEN = "gw-secret-token"
A, B, FAC = "student01", "student02", "admin"
C, D, BOT = "student03", "student04", "testuser1"  # only used by the progress board tests
SUB = {u: auth.subscription_id(u) for u in (A, B, C, D, BOT, FAC)}
TAGS = {"owner": "someone", "env": "dev"}
CSP_START = "default-src 'none'; script-src 'self'"


class FakeExecutor:
    """Records every call and whether State.lock was held at the time."""

    def __init__(self):
        self.running, self.calls, self.under_lock = set(), [], []
        self.remove_error = False

    def _touch(self, what):
        self.calls.append(what)
        if self.app_state is not None and self.app_state.lock._is_owned():
            self.under_lock.append(what)

    app_state = None

    def list_running(self):
        self._touch("list_running")
        return set(self.running)

    def state(self, name):  # what the ARM handlers call
        self._touch(f"state {name}")
        return "Running" if name in self.running else "Terminated"

    def remove(self, name):
        self._touch(f"remove {name}")
        if self.remove_error:
            raise docker_api.DockerError("down")
        self.running.discard(name)
        return True

    def logs(self, name, tail=200):
        self._touch(f"logs {name} {tail}")
        return "line\n" * 3

    def ping(self):
        return True

    def image_present(self, image):
        return True


class Headers(dict):
    def get(self, k, default=None):
        return super().get(k.lower(), default)


def hdr(user=A, token=TOKEN):
    h = Headers()
    if user is not None:
        h["x-auth-user"] = user
    if token is not None:
        h["x-gateway-token"] = token
    return h


class Base(unittest.TestCase):
    def setUp(self):
        users = [A, B, FAC]
        self.fake = FakeExecutor()
        self.st = state_mod.State(None)
        self.fake.app_state = self.st
        self.app = server.App(auth.Auth(b"k" * 32, users, FAC, "iss"), self.st, self.fake)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = {"GATEWAY_TOKEN": TOKEN, "PUBLIC_BASE_URL": "https://dojo.example"}
        self.portal = portal_api.Portal(self.app, self.env, self.tmp.name)
        self.app.portal = self.portal
        self.app.reconciled.set()  # writes are refused until Dojo Cloud is ready (test_readiness.py)
        self.app.readiness.refresh()
        self.seed(A, "rg-a", "ci-a1", "site-a1", 20001)
        self.seed(A, "rg-a", "ci-a2", "site-a2", 20002, running=False)
        self.seed(B, "rg-b", "ci-b1", "site-b1", 20003)

    def seed(self, user, rg, name, label, port, running=True):
        sub, container = SUB[user], f"dojo-{user}-{rg}-{name}"
        self.st.rgs.setdefault(server.App.rg_key(sub, rg), {"name": rg, "location": "canadacentral", "tags": dict(TAGS)})
        body = {"properties": {"containers": [{"name": "hello", "properties": {
            "image": "dojo/hello:1.0", "environmentVariables": [{"name": "K", "secureValue": "s3cret"}]}}]}}
        self.st.cgs[server.App.cg_key(sub, rg, name)] = {
            "name": name, "rg": rg, "location": "canadacentral", "tags": dict(TAGS), "body": body,
            "spec": {"image": "dojo/hello:1.0", "env": [], "cpu": 0.25, "mem": 0.125},
            "port": port, "container": container, "dnsLabel": label, "owner": user}
        if running:
            self.fake.running.add(container)

    def call(self, method, url, user=A, token=TOKEN, body=None):
        u = urlparse(url)
        raw = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        status, headers, data = self.portal.dispatch(method, u.path, parse_qs(u.query), hdr(user, token), raw)
        return status, headers, data

    def jcall(self, method, url, **kw):
        status, headers, data = self.call(method, url, **kw)
        return status, json.loads(data)

    def cg_url(self, user, rg, name, suffix=""):
        return f"/cloud/api/containers/{SUB[user]}/{rg}/{name}{suffix}"

    def ops(self, user=None):
        return [e["operation"] for e in self.st.data["activity"] if user is None or e["caller"] == user]


class TrustModel(Base):
    def test_unconfigured_is_503(self):
        del self.env["GATEWAY_TOKEN"]
        status, body = self.jcall("GET", "/cloud/api/me")
        self.assertEqual((status, body["error"]["code"]), (503, "PortalNotConfigured"))
        self.env["GATEWAY_TOKEN"] = ""
        self.assertEqual(self.jcall("GET", "/cloud/api/me")[0], 503)

    def test_forged_user_without_token_is_401(self):
        for token in (None, "", "wrong", TOKEN + "x"):
            status, body = self.jcall("GET", "/cloud/api/me", token=token)
            self.assertEqual((status, body["error"]["code"]), (401, "Unauthenticated"), token)
        self.assertEqual(self.jcall("GET", "/cloud/api/me", user=None)[0], 401)
        self.assertEqual(self.jcall("GET", "/cloud/api/nonsense", token=None)[0], 401)  # no route probing

    def test_user_outside_roster_is_403(self):
        status, body = self.jcall("GET", "/cloud/api/me", user="mallory")
        self.assertEqual((status, body["error"]["code"]), (403, "Forbidden"))

    def test_me(self):
        status, me = self.jcall("GET", "/cloud/api/me")
        self.assertEqual(status, 200)
        self.assertEqual(me, {"user": A, "subscriptionId": SUB[A], "isFacilitator": False, "writeActions": True,
                              "quota": {"containerGroups": {"used": 2, "limit": policy.MAX_CONTAINER_GROUPS}},
                              "publicBaseUrl": "https://dojo.example"})
        self.assertTrue(self.jcall("GET", "/cloud/api/me", user=FAC)[1]["isFacilitator"])

    def test_unknown_route_and_method(self):
        self.assertEqual(self.jcall("GET", "/cloud/api/nonsense")[0], 404)
        self.assertEqual(self.jcall("POST", "/cloud/api/me")[0], 405)


class Reads(Base):
    def test_check_token_reads_only_the_callers_own_overview(self):
        self.env["CLOUD_CHECK_TOKEN"] = "chk"
        def get(url, user=A, token="chk"):
            u = urlparse(url)
            h = {"x-check-token": token, "x-auth-user": user}
            st, _, data = self.portal.dispatch("GET", u.path, parse_qs(u.query), Headers(h), b"")
            return st, json.loads(data)
        st, doc = get("/cloud/api/overview?scope=mine")
        self.assertEqual(st, 200)
        self.assertEqual({c["dnsLabel"] for c in doc["containerGroups"]}, {"site-a1", "site-a2"})
        self.assertEqual(get("/cloud/api/overview?scope=class")[0], 403)
        self.assertEqual(get("/cloud/api/me")[0], 403)
        st, doc = get("/cloud/api/policy")                     # the account's own Policy blade
        self.assertEqual((st, doc["subscriptionId"]), (200, auth.subscription_id(A)))
        self.assertEqual(get(f"/cloud/api/policy?subscription={auth.subscription_id(B)}")[0], 403)
        self.assertEqual(get("/cloud/api/policy/evaluate")[0], 403)
        self.assertEqual(get("/cloud/api/activity")[0], 200)                # its own activity log only
        self.assertEqual(get("/cloud/api/activity?scope=all")[0], 403)
        self.assertEqual(get("/cloud/api/overview", token="wrong")[0], 401)
        self.assertEqual(get("/cloud/api/overview", user="nobody")[0], 401)
        u = urlparse(self.cg_url(A, "rg-a", "ci-a1", "/stop"))
        st, _, _ = self.portal.dispatch("POST", u.path, {}, Headers({"x-check-token": "chk", "x-auth-user": A}), b"")
        self.assertEqual(st, 403)

    def test_overview_mine_vs_class(self):
        _, mine = self.jcall("GET", "/cloud/api/overview?scope=mine")
        self.assertEqual({c["name"] for c in mine["containerGroups"]}, {"ci-a1", "ci-a2"})
        self.assertEqual([r["name"] for r in mine["resourceGroups"]], ["rg-a"])
        self.assertEqual(mine["resourceGroups"][0]["containerCount"], 2)
        states = {c["name"]: c["state"] for c in mine["containerGroups"]}
        self.assertEqual(states, {"ci-a1": "Running", "ci-a2": "Terminated"})
        _, cls = self.jcall("GET", "/cloud/api/overview?scope=class")
        self.assertEqual(len(cls["containerGroups"]), 3)
        b1 = next(c for c in cls["containerGroups"] if c["name"] == "ci-b1")
        self.assertFalse(b1["isMine"])
        self.assertEqual(b1["siteUrl"], "/cloud/site/site-b1/")
        self.assertEqual(self.jcall("GET", "/cloud/api/overview?scope=x")[0], 400)

    def test_class_scope_is_summaries_only(self):
        _, cls = self.jcall("GET", "/cloud/api/overview?scope=class")
        for c in cls["containerGroups"]:
            self.assertEqual(set(c), {"id", "name", "resourceGroup", "subscriptionId", "owner", "location",
                                      "state", "fqdn", "ip", "image", "cpu", "memoryGb", "tags", "dnsLabel",
                                      "siteUrl", "isMine"})
        raw = json.dumps(cls)
        self.assertNotIn("s3cret", raw)
        self.assertNotIn("properties", raw)
        self.assertNotIn("logs", raw)
        self.assertFalse(any(c.startswith("logs") for c in self.fake.calls))

    def test_status_is_one_cached_list_call(self):
        for _ in range(5):
            self.jcall("GET", "/cloud/api/overview?scope=class")
            self.jcall("GET", self.cg_url(A, "rg-a", "ci-a1"))
        self.assertEqual(self.fake.calls, ["list_running"])

    def test_docker_down_is_unknown_not_lie(self):
        self.fake.list_running = lambda: (_ for _ in ()).throw(docker_api.DockerError("down"))
        _, mine = self.jcall("GET", "/cloud/api/overview")
        self.assertEqual({c["state"] for c in mine["containerGroups"]}, {"Unknown"})

    def test_docker_down_keeps_last_answer_briefly_then_unknown(self):
        """A blip keeps "Running"; an outage that lasts longer than STATUS_STALE_MAX must not."""
        _, mine = self.jcall("GET", "/cloud/api/overview")
        self.assertIn("Running", {c["state"] for c in mine["containerGroups"]})
        self.fake.list_running = lambda: (_ for _ in ()).throw(docker_api.DockerError("down"))
        self.portal._invalidate()  # the ~2 s cache has expired; Docker is now unreachable
        _, blip = self.jcall("GET", "/cloud/api/overview")
        self.assertIn("Running", {c["state"] for c in blip["containerGroups"]})
        self.portal._run_ok -= portal_api.STATUS_STALE_MAX + 1  # ...and it has been down for a while
        self.portal._invalidate()
        _, outage = self.jcall("GET", "/cloud/api/overview")
        self.assertEqual({c["state"] for c in outage["containerGroups"]}, {"Unknown"})

    def test_no_docker_call_under_state_lock(self):
        self.jcall("GET", "/cloud/api/overview?scope=class")
        self.jcall("GET", self.cg_url(A, "rg-a", "ci-a1"))
        self.jcall("GET", self.cg_url(A, "rg-a", "ci-a1", "/logs"))
        self.jcall("PATCH", self.cg_url(A, "rg-a", "ci-a1"), body={"tags": TAGS})
        self.jcall("DELETE", self.cg_url(A, "rg-a", "ci-a2"))
        self.jcall("POST", "/cloud/api/admin/purge", user=FAC, body={"subscriptionId": SUB[B]})
        self.jcall("GET", "/cloud/api/admin/progress", user=FAC)
        self.assertGreaterEqual(len(self.fake.calls), 4)
        self.assertEqual(self.fake.under_lock, [])

    def test_detail_hides_secrets_and_has_arm_json(self):
        status, d = self.jcall("GET", self.cg_url(A, "rg-a", "ci-a1"))
        self.assertEqual(status, 200)
        self.assertEqual(d["summary"]["state"], "Running")
        self.assertEqual(d["arm"]["type"], server.ARM_TYPE_CG)
        self.assertEqual(d["arm"]["properties"]["instanceView"]["state"], "Running")
        self.assertNotIn("s3cret", json.dumps(d))

    def test_student_cannot_touch_another_students_container(self):
        for method, suffix, body in (("GET", "", None), ("GET", "/logs", None), ("DELETE", "", None),
                                     ("PATCH", "", {"tags": TAGS})):
            status, err = self.jcall(method, self.cg_url(B, "rg-b", "ci-b1", suffix), user=A, body=body)
            self.assertEqual((status, err["error"]["code"]), (403, "AuthorizationFailed"), (method, suffix))
        self.assertIn(server.App.cg_key(SUB[B], "rg-b", "ci-b1"), self.st.cgs)
        self.assertEqual(self.st.cgs[server.App.cg_key(SUB[B], "rg-b", "ci-b1")]["tags"], TAGS)
        self.assertNotIn("logs dojo-student02-rg-b-ci-b1 200", self.fake.calls)
        self.assertEqual(self.fake.calls, [])

    def test_facilitator_can_read_anyones(self):
        self.assertEqual(self.jcall("GET", self.cg_url(B, "rg-b", "ci-b1"), user=FAC)[0], 200)
        self.assertEqual(self.jcall("GET", self.cg_url(B, "rg-b", "ci-nope"), user=FAC)[0], 404)
        self.assertEqual(self.jcall("GET", "/cloud/api/containers/nope/rg/ci-x", user=FAC)[0], 404)

    def test_logs_tail_is_capped(self):
        url = self.cg_url(A, "rg-a", "ci-a1", "/logs")
        self.assertEqual(self.jcall("GET", url)[1], {"logs": "line\nline\nline\n"})
        self.jcall("GET", url + "?tail=99999")
        self.jcall("GET", url + "?tail=0")
        self.jcall("GET", url + "?tail=7")
        self.assertEqual([c.split()[-1] for c in self.fake.calls if c.startswith("logs")], ["200", "500", "1", "7"])
        self.assertEqual(self.jcall("GET", url + "?tail=abc")[0], 400)

    def test_activity_scopes(self):
        self.st.log(SUB[A], A, "op-a", "/x", "Succeeded")
        self.st.log(SUB[B], B, "op-b", "/y", "Succeeded")
        self.st.log(SUB[A], A, "op-a2", "/x", "Succeeded")
        _, mine = self.jcall("GET", "/cloud/api/activity?scope=mine")
        self.assertEqual([e["operation"] for e in mine["events"]], ["op-a2", "op-a"])
        self.assertEqual(set(mine["events"][0]), {"time", "subscription", "caller", "operation", "resourceId",
                                                  "status", "message"})
        status, err = self.jcall("GET", "/cloud/api/activity?scope=all", user=A)
        self.assertEqual((status, err["error"]["code"]), (403, "Forbidden"))
        _, allev = self.jcall("GET", "/cloud/api/activity?scope=all&limit=2", user=FAC)
        self.assertEqual([e["operation"] for e in allev["events"]], ["op-a2", "op-b"])


class Writes(Base):
    def test_owner_delete_is_logged_as_portal_action(self):
        status, body = self.jcall("DELETE", self.cg_url(A, "rg-a", "ci-a1"))
        self.assertEqual((status, body), (200, {"deleted": True}))
        self.assertNotIn(server.App.cg_key(SUB[A], "rg-a", "ci-a1"), self.st.cgs)
        self.assertIn("remove dojo-student01-rg-a-ci-a1", self.fake.calls)
        self.assertEqual(self.ops(A), ["Delete container group (portal)"])
        self.assertEqual(self.jcall("DELETE", self.cg_url(A, "rg-a", "ci-a1"))[0], 404)

    def test_delete_when_cloud_host_down_is_502_and_logged(self):
        self.fake.remove_error = True
        self.assertEqual(self.jcall("DELETE", self.cg_url(A, "rg-a", "ci-a1"))[0], 502)
        self.assertEqual(self.st.data["activity"][-1]["status"], "Failed")

    def test_write_actions_toggle(self):
        self.assertEqual(self.jcall("GET", "/cloud/api/admin/settings", user=FAC)[1], {"writeActions": True})
        self.assertEqual(self.jcall("PUT", "/cloud/api/admin/settings", user=FAC, body={"writeActions": False})[0], 200)
        self.assertFalse(self.st.data["settings"]["writeActions"])
        self.assertFalse(self.jcall("GET", "/cloud/api/me")[1]["writeActions"])
        for method, body in (("DELETE", None), ("PATCH", {"tags": TAGS})):
            status, err = self.jcall(method, self.cg_url(A, "rg-a", "ci-a1"), body=body)
            self.assertEqual((status, err["error"]["code"]), (403, "PortalWriteActionsDisabled"), method)
        self.assertIn(server.App.cg_key(SUB[A], "rg-a", "ci-a1"), self.st.cgs)
        self.assertEqual(self.jcall("GET", self.cg_url(A, "rg-a", "ci-a1"))[0], 200)  # reads unaffected
        # the facilitator is unaffected
        self.assertEqual(self.jcall("PATCH", self.cg_url(A, "rg-a", "ci-a1"), user=FAC, body={"tags": TAGS})[0], 200)
        self.assertEqual(self.jcall("DELETE", self.cg_url(A, "rg-a", "ci-a1"), user=FAC)[0], 200)
        self.jcall("PUT", "/cloud/api/admin/settings", user=FAC, body={"writeActions": True})
        self.assertEqual(self.jcall("DELETE", self.cg_url(A, "rg-a", "ci-a2"))[0], 200)

    def test_settings_are_facilitator_only_and_validated(self):
        self.assertEqual(self.jcall("GET", "/cloud/api/admin/settings")[0], 403)
        self.assertEqual(self.jcall("PUT", "/cloud/api/admin/settings", body={"writeActions": False})[0], 403)
        self.assertTrue(self.st.data.get("settings", {}).get("writeActions", True))
        for bad in ({"writeActions": "no"}, {}, b"not json"):
            self.assertEqual(self.jcall("PUT", "/cloud/api/admin/settings", user=FAC, body=bad)[0], 400)

    def test_patch_replaces_tags_and_enforces_policy(self):
        url = self.cg_url(A, "rg-a", "ci-a1")
        status, body = self.jcall("PATCH", url, body={"tags": {"owner": "me", "env": "prod", "x": "y"}})
        self.assertEqual(status, 200)
        self.assertEqual(body["summary"]["tags"], {"owner": "me", "env": "prod", "x": "y"})
        rec = self.st.cgs[server.App.cg_key(SUB[A], "rg-a", "ci-a1")]
        self.assertEqual(rec["body"]["tags"], rec["tags"])
        status, err = self.jcall("PATCH", url, body={"tags": {"owner": "me"}})  # missing 'env'
        self.assertEqual((status, err["error"]["code"]), (403, "RequestDisallowedByPolicy"))
        self.assertEqual(rec["tags"], {"owner": "me", "env": "prod", "x": "y"})  # unchanged
        self.assertEqual(self.ops(A), ["Update container group tags (portal)"] * 2)
        self.assertEqual([e["status"] for e in self.st.data["activity"]], ["Succeeded", "Failed"])
        for bad in ({}, {"tags": ["a"]}, {"tags": {"owner": 1, "env": "x"}}, b"[]"):
            self.assertEqual(self.jcall("PATCH", url, body=bad)[0], 400, bad)

    def test_purge_removes_only_the_target_subscription(self):
        self.st.log(SUB[B], B, "old", "/z", "Succeeded")
        status, body = self.jcall("POST", "/cloud/api/admin/purge", user=FAC, body={"subscriptionId": SUB[A]})
        self.assertEqual((status, body), (200, {"removed": {"containerGroups": 2, "resourceGroups": 1}}))
        self.assertEqual(list(self.st.cgs), [server.App.cg_key(SUB[B], "rg-b", "ci-b1")])
        self.assertEqual(list(self.st.rgs), [server.App.rg_key(SUB[B], "rg-b")])
        self.assertEqual(sorted(c for c in self.fake.calls if c.startswith("remove")),
                         ["remove dojo-student01-rg-a-ci-a1", "remove dojo-student01-rg-a-ci-a2"])
        self.assertEqual(self.st.data["activity"][-1]["operation"], "Purge subscription (portal)")
        self.assertEqual(self.st.data["activity"][-1]["caller"], FAC)
        self.assertEqual(self.jcall("POST", "/cloud/api/admin/purge", user=FAC, body={"subscriptionId": "nope"})[0], 404)
        self.assertEqual(self.jcall("POST", "/cloud/api/admin/purge", user=FAC, body={})[0], 404)

    def test_student_reset_purges_through_purge(self):
        self.assertEqual(self.portal.student_reset(A, "teardown"), "removed 2 container group(s), 1 resource group(s)")
        self.assertEqual(list(self.st.cgs), [server.App.cg_key(SUB[B], "rg-b", "ci-b1")])
        self.assertEqual(self.st.data["activity"][-1]["caller"], "student-reset")
        self.assertEqual(self.portal.student_reset(A, "teardown"), "removed 0 container group(s), 0 resource group(s)")
        self.assertEqual(self.portal.student_reset(A, "provision"), "nothing to do")
        self.assertEqual(self.portal.student_reset("nobody", "teardown"), "nothing to do")

    def test_purge_is_facilitator_only(self):
        status, err = self.jcall("POST", "/cloud/api/admin/purge", user=A, body={"subscriptionId": SUB[B]})
        self.assertEqual((status, err["error"]["code"]), (403, "Forbidden"))
        self.assertEqual(len(self.st.cgs), 3)
        self.assertEqual(self.jcall("POST", "/cloud/api/admin/purge", user=A, body={"subscriptionId": SUB[A]})[0], 403)


class Progress(Base):
    """Facilitator class progress board (TOFU-BASICS-PLAN.md 5.6a)."""
    URL = "/cloud/api/admin/progress"

    def setUp(self):
        super().setUp()
        self.st.rgs.clear()  # start from an empty class; each test seeds what it needs
        self.st.cgs.clear()
        self.st.data["activity"].clear()
        self.st.rebuild_summary()
        self.fake.running.clear()
        self.app.auth.users[:] = [A, B, FAC, C, D, BOT]  # facilitator in the middle on purpose

    def board(self, user=FAC):
        status, body = self.jcall("GET", self.URL, user=user)
        self.assertEqual(status, 200, body)
        return body

    def row(self, user, board=None):
        return next(r for r in (board or self.board())["students"] if r["user"] == user)

    def add_rg(self, user, rg="rg-x"):
        self.st.rgs.setdefault(server.App.rg_key(SUB[user], rg), {"name": rg, "location": "canadacentral", "tags": {}})

    def event(self, user, status, operation="op", message="", age=0, time_text=None):
        """Append an activity entry `age` seconds old (oldest must be appended first). Written straight into
        the list (State.log always stamps "now"), then the summary is rebuilt the way a restart would."""
        stamp = time_text if time_text is not None else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - age))
        self.st.data["activity"].append({"time": stamp, "subscription": SUB[user], "caller": user,
                                         "operation": operation, "resourceId": "/x", "status": status,
                                         "message": message})
        self.st.rebuild_summary()

    def test_students_are_forbidden_and_unauthenticated_is_401(self):
        for user in (A, BOT):
            status, err = self.jcall("GET", self.URL, user=user)
            self.assertEqual((status, err["error"]["code"]), (403, "Forbidden"), user)
        self.assertEqual(self.jcall("GET", self.URL, user=FAC, token=None)[0], 401)
        self.assertEqual(self.jcall("GET", self.URL, user=None)[0], 401)
        self.assertEqual(self.jcall("GET", self.URL, user="mallory")[0], 403)
        self.assertEqual(self.fake.calls, [])  # a forbidden caller costs no Docker call

    def test_wrong_method_is_405(self):
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            status, err = self.jcall(method, self.URL, user=FAC, body={})
            self.assertEqual((status, err["error"]["code"]), (405, "MethodNotAllowed"), method)
        self.assertEqual(self.jcall("POST", self.URL, user=A, body={})[0], 403)  # same order as admin/settings
        self.assertEqual(self.jcall("GET", self.URL + "/x", user=FAC)[0], 404)

    def test_shape_and_headers(self):
        self.seed(A, "rg-a", "ci-a1", "site-a1", 20001)
        self.event(A, "Succeeded", "Create container group", "created")
        status, headers, data = self.call("GET", self.URL, user=FAC)
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        board = json.loads(data)
        self.assertEqual(set(board), {"generatedAt", "summary", "students"})
        self.assertRegex(board["generatedAt"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual(set(board["summary"]), {"total", "notStarted", "inProgress", "running", "attention"})
        self.assertEqual(self.row(A, board), {
            "user": A, "subscriptionId": SUB[A], "stage": "running", "resourceGroups": 1,
            "containerGroups": [{"name": "ci-a1", "resourceGroup": "rg-a", "state": "Running",
                                 "siteUrl": "/cloud/site/site-a1/"}],
            "lastEvent": {"time": self.st.data["activity"][0]["time"], "operation": "Create container group",
                          "status": "Succeeded", "message": "created"},
            "failures": 0})

    def test_roster_order_facilitator_excluded_bots_included(self):
        board = self.board()
        self.assertEqual([r["user"] for r in board["students"]], [A, B, C, D, BOT])
        self.assertNotIn(FAC, json.dumps(board))
        self.assertNotIn(SUB[FAC], json.dumps(board))
        self.assertEqual(board["summary"]["total"], 5)
        self.event(FAC, "Failed", "facilitator op")  # the facilitator's own activity never makes a row
        self.assertEqual([r["user"] for r in self.board()["students"]], [A, B, C, D, BOT])

    def test_not_started(self):
        board = self.board()
        for r in board["students"]:
            self.assertEqual((r["stage"], r["resourceGroups"], r["containerGroups"], r["lastEvent"], r["failures"]),
                             ("notStarted", 0, [], None, 0), r["user"])
        self.assertEqual(board["summary"], {"total": 5, "notStarted": 5, "inProgress": 0, "running": 0, "attention": 0})
        self.assertEqual(self.fake.calls, ["list_running"])  # still one list call, even with nothing to show

    def test_in_progress_with_only_a_resource_group(self):
        self.add_rg(A)  # apply is part-way: the RG exists before the container does
        r = self.row(A)
        self.assertEqual((r["stage"], r["resourceGroups"], r["containerGroups"]), ("inProgress", 1, []))

    def test_in_progress_with_only_an_event(self):
        self.event(B, "Succeeded", "Delete container group (portal)")  # e.g. a drift demo deletes everything
        self.assertEqual(self.row(B)["stage"], "inProgress")

    def test_in_progress_when_state_is_unknown(self):
        self.seed(A, "rg-a", "ci-a1", "site-a1", 20001)
        self.fake.list_running = lambda: (_ for _ in ()).throw(docker_api.DockerError("down"))
        r = self.row(A)
        self.assertEqual([c["state"] for c in r["containerGroups"]], ["Unknown"])
        self.assertEqual(r["stage"], "inProgress")

    def test_running_needs_every_container_running(self):
        self.seed(A, "rg-a", "ci-a1", "site-a1", 20001)
        self.seed(A, "rg-a", "ci-a2", "site-a2", 20002)
        self.event(A, "Succeeded")
        self.assertEqual(self.row(A)["stage"], "running")
        self.seed(A, "rg-a", "ci-a3", "site-a3", 20003, running=False)  # one of three is down
        self.fake.calls.clear()
        self.portal._invalidate()
        r = self.row(A)
        self.assertEqual(r["stage"], "attention")
        self.assertEqual([(c["name"], c["state"]) for c in r["containerGroups"]],
                         [("ci-a1", "Running"), ("ci-a2", "Running"), ("ci-a3", "Terminated")])

    def test_attention_when_last_event_failed(self):
        self.seed(A, "rg-a", "ci-a1", "site-a1", 20001)
        self.event(A, "Succeeded", "Create container group")
        self.event(A, "Failed", "Update container group tags (portal)", "RequestDisallowedByPolicy")
        r = self.row(A)
        self.assertEqual((r["stage"], r["failures"]), ("attention", 1))
        self.assertEqual(r["lastEvent"]["status"], "Failed")
        self.assertEqual(r["lastEvent"]["message"], "RequestDisallowedByPolicy")

    def test_attention_when_a_container_is_terminated(self):
        self.seed(A, "rg-a", "ci-a1", "site-a1", 20001, running=False)  # crashed / stopped
        self.event(A, "Succeeded", "Create container group")
        r = self.row(A)
        self.assertEqual((r["stage"], r["failures"]), ("attention", 0))
        self.assertEqual([c["state"] for c in r["containerGroups"]], ["Terminated"])

    def test_failed_then_succeeded_is_not_attention(self):
        self.seed(A, "rg-a", "ci-a1", "site-a1", 20001)
        self.event(A, "Failed", "Create container group", "quota")
        self.event(A, "Succeeded", "Create container group")
        r = self.row(A)
        self.assertEqual((r["stage"], r["failures"]), ("running", 1))  # recovered; the failure still counts
        self.assertEqual(r["lastEvent"]["status"], "Succeeded")

    def test_failed_event_alone_is_attention(self):
        self.event(C, "Failed", "Create resource group")
        r = self.row(C)
        self.assertEqual((r["stage"], r["resourceGroups"], r["containerGroups"]), ("attention", 0, []))

    def test_summary_counts_add_up(self):
        self.seed(A, "rg-a", "ci-a1", "site-a1", 20001)          # running
        self.add_rg(B)                                            # inProgress
        self.seed(C, "rg-c", "ci-c1", "site-c1", 20003, running=False)  # attention
        # D: notStarted; BOT: running
        self.seed(BOT, "rg-bot", "ci-bot", "site-bot", 20004)
        board = self.board()
        self.assertEqual(board["summary"], {"total": 5, "notStarted": 1, "inProgress": 1, "running": 2, "attention": 1})
        stages = [r["stage"] for r in board["students"]]
        self.assertEqual(stages, ["running", "inProgress", "attention", "notStarted", "running"])
        s = board["summary"]
        self.assertEqual(s["total"], len(board["students"]))
        self.assertEqual(s["total"], s["notStarted"] + s["inProgress"] + s["running"] + s["attention"])

    def test_failures_count_only_the_last_15_minutes(self):
        old_tz = os.environ.get("TZ")

        def restore():
            if old_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = old_tz
            time.tzset()

        self.addCleanup(restore)
        for tz in ("UTC", "Pacific/Auckland", "America/Los_Angeles"):  # event times are UTC whatever the host zone
            os.environ["TZ"] = tz
            time.tzset()
            self.st.data["activity"].clear()
            self.st.rebuild_summary()
            self.event(A, "Failed", age=3600)                       # long ago
            self.event(A, "Failed", age=16 * 60)                    # just outside the window
            self.event(A, "Failed", age=14 * 60)                    # inside
            self.event(A, "Failed", age=30)                         # inside
            self.event(A, "Succeeded", age=10)                      # not a failure
            self.event(A, "Failed", time_text="not a timestamp")    # malformed: ignored, no crash
            self.event(A, "Failed", time_text="")                   # empty: ignored
            self.event(A, "Succeeded", age=5)
            self.event(B, "Failed", age=20 * 60)
            self.assertEqual(self.row(A)["failures"], 2, tz)
            self.assertEqual(self.row(B)["failures"], 0, tz)
            self.assertEqual(self.row(B)["stage"], "attention", tz)  # last event Failed regardless of its age

    def test_last_event_message_is_truncated_to_200_chars(self):
        self.event(A, "Succeeded", "op", "x" * 500)
        self.event(B, "Succeeded", "op", "y" * 200)
        self.event(C, "Succeeded", "op", "z" * 199)
        self.assertEqual(self.row(A)["lastEvent"]["message"], "x" * 200)
        self.assertEqual(self.row(B)["lastEvent"]["message"], "y" * 200)
        self.assertEqual(self.row(C)["lastEvent"]["message"], "z" * 199)
        self.assertEqual(set(self.row(A)["lastEvent"]), {"time", "operation", "status", "message"})
        self.assertEqual(len(self.st.data["activity"][0]["message"]), 500)  # the log itself is untouched

    def test_hostile_strings_pass_through_as_data(self):
        evil = '<img src=x onerror=alert(1)>"</script><script>alert(1)</script>&amp;\u2028'
        self.add_rg(A, "rg-<b>")
        self.seed(A, "rg-<b>", "ci-<i>", "lbl-<u>", 20001)
        self.event(A, "Succeeded", evil, evil)
        status, headers, data = self.call("GET", self.URL, user=FAC)
        self.assertEqual(status, 200)
        self.assertTrue(headers["Content-Type"].startswith("application/json"))
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")  # served as JSON, never sniffed as HTML
        r = self.row(A, json.loads(data))
        self.assertEqual((r["lastEvent"]["operation"], r["lastEvent"]["message"]), (evil, evil))
        self.assertEqual(r["containerGroups"][0]["name"], "ci-<i>")
        self.assertEqual(r["containerGroups"][0]["resourceGroup"], "rg-<b>")
        self.assertEqual(r["containerGroups"][0]["siteUrl"], "/cloud/site/lbl-<u>/")
        self.assertFalse(data.lstrip().startswith(b"<"))

    def test_no_docker_call_under_state_lock_and_one_list_call_for_the_class(self):
        many = [f"student{n:02d}" for n in range(10, 40)]  # a 30-student class, one container each
        self.app.auth.users[:] = [A, B, FAC, *many]
        for i, u in enumerate(many):
            SUB[u] = auth.subscription_id(u)
            self.addCleanup(SUB.pop, u)
            self.app.auth.by_subscription[SUB[u]] = u
            self.seed(u, f"rg-{i}", f"ci-{i}", f"site-{i}", 21000 + i, running=bool(i % 2))
            self.event(u, "Succeeded")
        board = self.board()
        self.assertEqual(board["summary"]["total"], 32)
        self.assertEqual(board["summary"]["running"], 15)
        self.assertEqual(board["summary"]["attention"], 15)
        for _ in range(3):
            self.board()
        self.assertEqual(self.fake.calls, ["list_running"])  # never one call per student, cached for ~2 s
        self.assertEqual(self.fake.under_lock, [])

    def test_docker_call_is_made_after_the_lock_is_released(self):
        self.seed(A, "rg-a", "ci-a1", "site-a1", 20001)
        held = []
        original = self.fake.list_running

        def spy():
            held.append(self.st.lock._is_owned())
            return original()

        self.fake.list_running = spy
        self.board()
        self.assertEqual(held, [False])

    def test_a_students_data_does_not_leak_into_another_row(self):
        self.seed(A, "rg-a", "ci-a1", "site-a1", 20001)
        self.seed(B, "rg-b", "ci-b1", "site-b1", 20002, running=False)
        self.event(A, "Succeeded", "op-of-A", "msg-A")
        self.event(B, "Failed", "op-of-B", "msg-B")
        self.event(B, "Failed", "op-of-B2", "msg-B2")
        board = self.board()
        a, b = self.row(A, board), self.row(B, board)
        for needle in ("rg-b", "ci-b1", "site-b1", "op-of-B", "msg-B", SUB[B], B):
            self.assertNotIn(needle, json.dumps(a), needle)
        for needle in ("rg-a", "ci-a1", "site-a1", "op-of-A", "msg-A", SUB[A], A):
            self.assertNotIn(needle, json.dumps(b), needle)
        self.assertEqual((a["stage"], a["failures"]), ("running", 0))
        self.assertEqual((b["stage"], b["failures"]), ("attention", 2))
        self.assertEqual(b["lastEvent"]["operation"], "op-of-B2")
        self.assertEqual(self.row(C)["lastEvent"], None)  # untouched student picks up nothing

    def test_failure_history_survives_activity_log_eviction(self):
        """One busy student must not push another's failures out of the board (ACTIVITY_MAX cap)."""
        self.seed(A, "rg-a", "ci-a1", "site-a1", 20001)
        self.st.log(SUB[A], A, "Create/Update container group", "/a", "Failed", "quota")
        for i in range(2500):
            self.st.log(SUB[B], B, "Create/Update resource group", "/b", "Failed", f"policy {i}")
        self.assertEqual(len(self.st.data["activity"]), state_mod.ACTIVITY_MAX)
        self.assertNotIn(A, [e["caller"] for e in self.st.data["activity"]])  # A's event really is gone
        board = self.board()
        a, b = self.row(A, board), self.row(B, board)
        self.assertEqual((a["stage"], a["failures"]), ("attention", 1))
        self.assertEqual((a["lastEvent"]["operation"], a["lastEvent"]["status"], a["lastEvent"]["message"]),
                         ("Create/Update container group", "Failed", "quota"))
        self.assertEqual((b["stage"], b["failures"]), ("attention", state_mod.FAILURES_KEPT))  # capped, documented
        self.assertEqual(b["lastEvent"]["message"], "policy 2499")
        self.assertEqual(board["summary"]["attention"], 2)
        self.assertEqual(self.fake.under_lock, [])

    def test_recovery_after_eviction_still_clears_attention(self):
        self.seed(A, "rg-a", "ci-a1", "site-a1", 20001)
        self.st.log(SUB[A], A, "op", "/a", "Failed", "x")
        for _ in range(state_mod.ACTIVITY_MAX):
            self.st.log(SUB[B], B, "op", "/b", "Succeeded")
        self.assertEqual(self.row(A)["stage"], "attention")
        self.st.log(SUB[A], A, "op", "/a", "Succeeded")
        r = self.row(A)
        self.assertEqual((r["stage"], r["failures"], r["lastEvent"]["status"]), ("running", 1, "Succeeded"))

    def test_board_survives_a_restart(self):
        path = os.path.join(self.tmp.name, "state.json")
        st = state_mod.State(path)
        st.log(SUB[A], A, "op", "/a", "Failed", "boom")
        st.log(SUB[B], B, "op", "/b", "Succeeded")
        st.save()
        self.app.state = self.fake.app_state = state_mod.State(path)  # what a cloud-api restart does
        self.assertEqual((self.row(A)["stage"], self.row(A)["failures"]), ("attention", 1))
        self.assertEqual(self.row(A)["lastEvent"]["message"], "boom")
        self.assertEqual(self.row(B)["stage"], "inProgress")

    def test_actions_on_a_students_behalf_show_under_that_student(self):
        self.seed(A, "rg-a", "ci-a1", "site-a1", 20001)
        self.jcall("POST", "/cloud/api/admin/purge", user=FAC, body={"subscriptionId": SUB[A]})  # logged for A's sub
        r = self.row(A)
        self.assertEqual((r["stage"], r["resourceGroups"], r["containerGroups"]), ("inProgress", 0, []))
        self.assertEqual(r["lastEvent"]["operation"], "Purge subscription (portal)")

    def test_events_for_unknown_subscriptions_are_ignored(self):
        self.st.data["activity"].append({"time": "2026-01-01T00:00:00Z", "subscription": "not-a-sub", "caller": "x",
                                         "operation": "o", "resourceId": "/", "status": "Failed", "message": ""})
        self.st.rebuild_summary()
        self.st.rgs["ghost-sub/rg"] = {"name": "rg", "location": "canadacentral", "tags": {}}
        board = self.board()
        self.assertEqual(board["summary"], {"total": 5, "notStarted": 5, "inProgress": 0, "running": 0, "attention": 0})


class Static(Base):
    def setUp(self):
        super().setUp()
        for name, text in (("index.html", "<html>hi</html>"), ("app.js", "//js"), ("app.css", "/*c*/"),
                           ("favicon.svg", "<svg/>"), ("secret.txt", "nope")):
            with open(os.path.join(self.tmp.name, name), "w") as f:
                f.write(text)

    def get(self, path, **kw):
        return self.call("GET", path, user=None, token=None, **kw)  # static needs no identity

    def test_serves_allow_listed_files_with_types_and_csp(self):
        cases = {"/cloud/": ("text/html", b"<html>hi</html>"), "/cloud/static/index.html": ("text/html", None),
                 "/cloud/static/app.js": ("text/javascript", b"//js"), "/cloud/static/app.css": ("text/css", b"/*c*/"),
                 "/cloud/static/favicon.svg": ("image/svg+xml", b"<svg/>")}
        for path, (ctype, data) in cases.items():
            status, headers, body = self.get(path)
            self.assertEqual(status, 200, path)
            self.assertTrue(headers["Content-Type"].startswith(ctype), path)
            self.assertTrue(headers["Content-Security-Policy"].startswith(CSP_START), path)
            self.assertEqual(headers["Content-Security-Policy"], portal_api.dojo_http.CSP)
            self.assertIn("frame-ancestors 'self'", headers["Content-Security-Policy"])
            self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
            if data:
                self.assertEqual(body, data)

    def test_no_slash_redirects(self):
        status, headers, _ = self.get("/cloud")
        self.assertEqual((status, headers["Location"]), (301, "/cloud/"))

    def test_rejects_everything_else(self):
        for path in ("/cloud/static/../app.js", "/cloud/static/%2e%2e/secret.txt", "/cloud/static/..%2fsecret.txt",
                     "/cloud/static/%2e%2e%2fsecret.txt", "/cloud/static//etc/passwd", "/cloud/static/etc/passwd",
                     "/cloud/static/secret.txt", "/cloud/static/app.js/", "/cloud/static/app.js/x",
                     "/cloud/static/%2fetc%2fpasswd", "/cloud/static/APP.JS", "/cloud/static", "/cloud/nothing",
                     "/cloud/static/app.js%00.txt", "/cloud/static/app.js\\..\\secret.txt"):
            status, _, body = self.get(path)
            self.assertIn(status, (404,), path)
            self.assertNotIn(b"nope", body, path)
        self.assertEqual(self.call("POST", "/cloud/static/app.js")[0], 405)

    def test_missing_file_is_clean_404(self):
        os.remove(os.path.join(self.tmp.name, "app.js"))
        status, headers, body = self.get("/cloud/static/app.js")
        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body)["error"]["code"], "NotFound")


class OverHttp(Base):
    """Real Handler: routes are wired, /cloud/site/* is not shadowed, ARM shares the same code."""

    def setUp(self):
        super().setUp()
        with open(os.path.join(self.tmp.name, "index.html"), "w") as f:
            f.write("<html></html>")
        self.old_app, self.old_log = server.APP, server.log
        server.APP, server.log = self.app, lambda msg: None
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.stop)

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        server.APP, server.log = self.old_app, self.old_log

    def http(self, method, path, headers=None, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1], timeout=5)
        conn.request(method, path, body=body, headers=headers or {})
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        return resp, data

    def test_routes(self):
        resp, data = self.http("GET", "/cloud/")
        self.assertEqual((resp.status, data), (200, b"<html></html>"))
        self.assertTrue(resp.getheader("Content-Security-Policy").startswith(CSP_START))
        resp, _ = self.http("HEAD", "/cloud/")
        self.assertEqual(resp.status, 200)
        resp, _ = self.http("GET", "/cloud")
        self.assertEqual((resp.status, resp.getheader("Location")), (301, "/cloud/"))
        resp, data = self.http("GET", "/cloud/api/me")
        self.assertEqual(resp.status, 401)
        resp, data = self.http("GET", "/cloud/api/me", {"X-Auth-User": A, "X-Gateway-Token": TOKEN})
        self.assertEqual((resp.status, json.loads(data)["user"]), (200, A))
        resp, data = self.http("GET", "/cloud/site/site-a1/")  # still the site proxy, not the portal
        self.assertNotIn(b"NotFound", data)
        self.assertIn(b"No site is deployed", self.http("GET", "/cloud/site/nothing-here/")[1])

    def test_arm_delete_and_patch_share_the_implementation(self):
        tok = {"Authorization": "Bearer " + self.app.auth.issue_token(A, "aud")}
        base = f"/subscriptions/{SUB[A]}/resourceGroups/rg-a/providers/Microsoft.ContainerInstance/containerGroups"
        resp, data = self.http("PATCH", f"{base}/ci-a1", tok, json.dumps({"tags": {"owner": "x"}}))
        self.assertEqual((resp.status, json.loads(data)["error"]["code"]), (403, "RequestDisallowedByPolicy"))
        resp, data = self.http("PATCH", f"{base}/ci-a1", tok, json.dumps({"tags": {"owner": "x", "env": "y"}}))
        self.assertEqual((resp.status, json.loads(data)["tags"]), (200, {"owner": "x", "env": "y"}))
        self.assertEqual(self.http("PATCH", f"{base}/nope", tok, b"{}")[0].status, 404)
        self.assertEqual(self.http("PATCH", f"{base}/ci-a1", tok, b"[")[0].status, 400)
        self.assertEqual(self.http("DELETE", f"{base}/ci-a1", tok)[0].status, 200)
        self.assertEqual(self.http("DELETE", f"{base}/ci-a1", tok)[0].status, 204)
        self.assertEqual(self.ops(A), ["Update container group tags", "Update container group tags",
                                       "Delete container group"])  # no "(portal)": it came via ARM
        self.assertEqual(self.fake.under_lock, [])


class Clock:
    """Stands in for time.time() so State.log can be stamped in the past."""

    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


class StateSummary(unittest.TestCase):
    """The per-subscription summary State.log() keeps (last event + recent Failed times)."""
    S, T = "sub-s", "sub-t"

    def setUp(self):
        self.clock = Clock(1_800_000_000)
        patcher = mock.patch.object(state_mod.time, "time", self.clock)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.st = state_mod.State(None)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def log(self, sub, status="Failed", message="", ago=0):
        self.clock.now = 1_800_000_000 - ago
        self.st.log(sub, "u", "op", "/r", status, message)

    def since(self, window=15 * 60):
        return 1_800_000_000 - window

    def test_last_event_and_failure_count(self):
        self.log(self.S, "Failed", "one")
        self.log(self.S, "Succeeded", "two")
        self.log(self.T, "Failed", "three")
        out = self.st.activity_summary(self.since())
        self.assertEqual((out[self.S][0]["message"], out[self.S][1]), ("two", 1))
        self.assertEqual((out[self.T][0]["message"], out[self.T][1]), ("three", 1))
        self.assertEqual(self.st.activity_summary(self.since()).keys(), {self.S, self.T})

    def test_window_uses_injected_timestamps(self):
        for ago in (3600, 16 * 60, 15 * 60 + 1, 15 * 60, 14 * 60, 30, 0):
            self.log(self.S, "Failed", ago=ago)
        self.log(self.S, "Succeeded", ago=0)  # not a failure
        self.assertEqual(self.st.activity_summary(self.since())[self.S][1], 4)  # 15:00 exactly, 14:00, 0:30, now
        self.assertEqual(self.st.activity_summary(self.since(60))[self.S][1], 2)  # (this read pruned the older ones)

    def test_old_failures_are_pruned_on_read(self):
        self.log(self.S, "Failed", ago=3600)
        self.log(self.S, "Failed", ago=10)
        self.assertEqual(len(self.st._summary[self.S]["failed"]), 2)
        self.st.activity_summary(self.since())
        self.assertEqual(len(self.st._summary[self.S]["failed"]), 1)

    def test_failure_times_are_bounded_per_subscription(self):
        for _ in range(state_mod.FAILURES_KEPT * 3):
            self.log(self.S, "Failed")
            self.assertLessEqual(len(self.st._summary[self.S]["failed"]), state_mod.FAILURES_KEPT)
        self.assertEqual(self.st.activity_summary(self.since())[self.S][1], state_mod.FAILURES_KEPT)
        self.assertEqual(len(self.st._summary), 1)  # one small entry per subscription, nothing per event

    def test_survives_the_log_cap(self):
        self.log(self.S, "Failed", "old")
        for _ in range(state_mod.ACTIVITY_MAX + 5):
            self.log(self.T, "Succeeded")
        self.assertNotIn(self.S, [e["subscription"] for e in self.st.data["activity"]])
        last, failures = self.st.activity_summary(self.since())[self.S]
        self.assertEqual((last["message"], failures), ("old", 1))

    def test_rebuilt_from_the_persisted_log(self):
        path = os.path.join(self.tmp.name, "state.json")
        self.st = state_mod.State(path)
        self.log(self.S, "Failed", "hour ago", ago=3600)
        self.log(self.S, "Failed", "eleven min ago", ago=11 * 60)
        self.log(self.S, "Failed", "recent", ago=5)
        self.log(self.T, "Succeeded", "ok")
        self.st.save()
        again = state_mod.State(path)
        self.assertEqual(again.activity_summary(self.since()), self.st.activity_summary(self.since()))
        last, failures = again.activity_summary(self.since())[self.S]
        self.assertEqual((last["message"], failures), ("recent", 2))
        self.st = again  # and it keeps counting after the restart
        self.log(self.S, "Failed", "after restart")
        self.assertEqual(again.activity_summary(self.since())[self.S][1], 3)

    def test_rebuild_is_bounded_and_ignores_junk(self):
        path = os.path.join(self.tmp.name, "state.json")
        events = [{"time": "2027-01-15T08:00:00Z", "subscription": self.S, "status": "Failed", "message": str(i)}
                  for i in range(state_mod.ACTIVITY_MAX)]
        events += ["junk", 7, None, {"subscription": None, "status": "Failed"}, {"status": "Failed"},
                   {"time": "garbage", "subscription": self.T, "status": "Failed", "message": "m"}]
        with open(path, "w") as f:
            json.dump({"activity": events}, f)
        st = state_mod.State(path)
        self.assertEqual(len(st._summary[self.S]["failed"]), state_mod.FAILURES_KEPT)
        self.assertEqual(st._summary[self.T]["failed"], type(st._summary[self.T]["failed"])(maxlen=state_mod.FAILURES_KEPT))
        self.assertEqual(st.activity_summary(0)[self.T][0]["message"], "m")  # last event kept; bad time never counts
        self.assertEqual(set(st._summary), {self.S, self.T})

    def test_log_works_while_the_caller_holds_the_lock(self):
        with self.st.lock:  # callers log while holding the lock (ARM handlers)
            self.log(self.S, "Failed")
        self.assertFalse(self.st.lock._is_owned())


class ClientDisconnect(unittest.TestCase):
    """A client that hangs up mid-response is dropped quietly: no traceback, no 500."""

    class BrokenWire:
        def write(self, data):
            raise BrokenPipeError(32, "Broken pipe")

        def flush(self):
            pass

    def setUp(self):
        self.lines = []
        self.old_app, self.old_log = server.APP, server.log
        server.APP, server.log = mock.Mock(), self.lines.append
        server.APP.executor.ping.return_value = True
        self.addCleanup(lambda: (setattr(server, "APP", self.old_app), setattr(server, "log", self.old_log)))

    def handler(self, path="/healthz", wfile=None, error=None):
        h = server.Handler.__new__(server.Handler)  # no socket: only the pieces handle_any touches
        h.command, h.path, h.request_version, h.requestline = "GET", path, "HTTP/1.1", f"GET {path} HTTP/1.1"
        h.headers, h.rfile, h.wfile = {}, io.BytesIO(), wfile or self.BrokenWire()
        h.client_address, h.close_connection, h._headers_buffer = ("127.0.0.1", 1), False, []
        return h

    def test_broken_pipe_on_write_is_dropped_quietly(self):
        h = self.handler()
        h.handle_any()  # must not raise
        self.assertTrue(h.close_connection)
        self.assertFalse([l for l in self.lines if "internal error" in l or "500" in l], self.lines)

    def test_reset_and_abort_are_dropped_quietly_too(self):
        for exc in (ConnectionResetError, ConnectionAbortedError):
            self.lines.clear()
            server.APP.executor.ping.side_effect = exc
            h = self.handler()
            h.handle_any()
            self.assertTrue(h.close_connection, exc)
            self.assertEqual([l for l in self.lines if "internal error" in l or "500" in l], [], exc)

    def test_a_dead_client_during_the_500_reply_is_quiet_as_well(self):
        server.APP.executor.ping.side_effect = RuntimeError("bug")
        h = self.handler()
        h.handle_any()  # logs the bug once; the 500 cannot be delivered and that is fine
        self.assertTrue(h.close_connection)
        self.assertEqual(len([l for l in self.lines if "internal error" in l]), 1)

    def test_real_errors_still_get_a_500(self):
        server.APP.executor.ping.side_effect = RuntimeError("bug")
        wire = io.BytesIO()
        h = self.handler(wfile=wire)
        h.handle_any()
        self.assertIn(b"500", wire.getvalue().split(b"\r\n")[0])
        self.assertIn(b"InternalServerError", wire.getvalue())
        self.assertTrue([l for l in self.lines if "internal error" in l])
        self.assertFalse(h.close_connection)

    def test_normal_request_is_unchanged(self):
        wire = io.BytesIO()
        h = self.handler(wfile=wire)
        h.handle_any()
        self.assertTrue(wire.getvalue().startswith(b"HTTP/1.1 200"))
        self.assertIn(b'"status": "ok"', wire.getvalue())


class Shutdown(unittest.TestCase):
    """SIGTERM/SIGINT stop the servers cleanly and flush state (python is PID 1 in the container)."""

    def test_signals_set_the_stop_event(self):
        old = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
        self.addCleanup(lambda: [signal.signal(sig, h) for sig, h in old.items()])
        for sig in (signal.SIGTERM, signal.SIGINT):
            stop = server.stop_on_signals()
            self.assertFalse(stop.is_set())
            os.kill(os.getpid(), sig)
            self.assertTrue(stop.wait(2), sig)

    def test_shutdown_stops_servers_then_saves(self):
        calls = []
        srv = mock.Mock()
        srv.shutdown.side_effect = lambda: calls.append("shutdown")
        srv.server_close.side_effect = lambda: calls.append("close")
        st = mock.Mock()
        st.lock = threading.RLock()
        st.save.side_effect = lambda: calls.append("save")
        with mock.patch.object(server, "log", lambda msg: None):
            server.shutdown([srv, srv], st)
        self.assertEqual(calls, ["shutdown", "close", "shutdown", "close", "save"])

    def test_shutdown_does_not_hang_on_a_busy_state_lock(self):
        st = state_mod.State(None)
        st.lock = mock.Mock()
        st.lock.acquire.return_value = False  # a handler is stuck holding it: skip the (redundant) save
        with mock.patch.object(server, "log", lambda msg: None):
            server.shutdown([], st)
        st.lock.acquire.assert_called_once_with(timeout=5)

    SCRIPT = """
import sys
import server, state as state_mod
server.log = lambda msg: None
st = state_mod.State(sys.argv[1])
srv = server.serve(0)
stop = server.stop_on_signals()
st.data["rgs"]["k"] = {"name": "unsaved"}  # only in memory until shutdown() flushes it
print("ready", flush=True)
stop.wait()
server.shutdown([srv], st)
print("bye", flush=True)
"""

    def test_sigterm_stops_a_real_server_process_promptly_and_flushes_state(self):
        here = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(tempfile.mkdtemp(), "state.json")
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        proc = subprocess.Popen([sys.executable, "-B", "-c", self.SCRIPT, path], cwd=here,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(proc.kill)
        self.assertEqual(proc.stdout.readline().strip(), "ready")
        started = time.monotonic()
        proc.send_signal(signal.SIGTERM)
        out, err = proc.communicate(timeout=3)
        self.assertEqual((proc.returncode, out.strip()), (0, "bye"), err)
        self.assertLess(time.monotonic() - started, 3)
        with open(path) as f:
            self.assertIn("k", json.load(f)["rgs"])


if __name__ == "__main__":
    unittest.main()
