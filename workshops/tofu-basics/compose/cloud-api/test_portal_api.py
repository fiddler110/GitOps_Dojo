"""Dojo Portal backend: trust model, authorisation, write-actions toggle, purge,
static allow-list. No containers: a fake executor and an in-memory State.
Run from this directory:  python3 -m unittest test_portal_api
"""
import http.client
import json
import os
import tempfile
import threading
import unittest
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
SUB = {u: auth.subscription_id(u) for u in (A, B, FAC)}
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
        self.seed(A, "rg-a", "ci-a1", "site-a1", 20001)
        self.seed(A, "rg-a", "ci-a2", "site-a2", 20002, running=False)
        self.seed(B, "rg-b", "ci-b1", "site-b1", 20003)

    def seed(self, user, rg, name, label, port, running=True):
        sub, container = SUB[user], f"dojo-{user}-{rg}-{name}"
        self.st.rgs.setdefault(server.App.rg_key(sub, rg), {"name": rg, "location": "uksouth", "tags": dict(TAGS)})
        body = {"properties": {"containers": [{"name": "hello", "properties": {
            "image": "dojo/hello:1.0", "environmentVariables": [{"name": "K", "secureValue": "s3cret"}]}}]}}
        self.st.cgs[server.App.cg_key(sub, rg, name)] = {
            "name": name, "rg": rg, "location": "uksouth", "tags": dict(TAGS), "body": body,
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

    def test_no_docker_call_under_state_lock(self):
        self.jcall("GET", "/cloud/api/overview?scope=class")
        self.jcall("GET", self.cg_url(A, "rg-a", "ci-a1"))
        self.jcall("GET", self.cg_url(A, "rg-a", "ci-a1", "/logs"))
        self.jcall("PATCH", self.cg_url(A, "rg-a", "ci-a1"), body={"tags": TAGS})
        self.jcall("DELETE", self.cg_url(A, "rg-a", "ci-a2"))
        self.jcall("POST", "/cloud/api/admin/purge", user=FAC, body={"subscriptionId": SUB[B]})
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

    def test_purge_is_facilitator_only(self):
        status, err = self.jcall("POST", "/cloud/api/admin/purge", user=A, body={"subscriptionId": SUB[B]})
        self.assertEqual((status, err["error"]["code"]), (403, "Forbidden"))
        self.assertEqual(len(self.st.cgs), 3)
        self.assertEqual(self.jcall("POST", "/cloud/api/admin/purge", user=A, body={"subscriptionId": SUB[A]})[0], 403)


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
            self.assertEqual(headers["Content-Security-Policy"], portal_api.CSP)
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


if __name__ == "__main__":
    unittest.main()
