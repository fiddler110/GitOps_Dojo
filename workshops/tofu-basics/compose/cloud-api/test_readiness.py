"""/readyz, the 503 gate on writes, DockerError handling and the background start-up.
No containers: a fake host stands in for the executor, and a tiny fake Docker daemon on a
unix socket stands in for cloud-host in the main() test. Run from this directory:
    python3 -B -m unittest test_readiness
"""
import copy
import http.client
import json
import os
import signal
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

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
NOT_ANSWERING = "Dojo Cloud is not ready: the cloud host is not answering."
RETRY = "Wait a minute and run the command again, or tell your facilitator."
PLAN_HINT = ("Wait a minute, run `terraform plan` to see where things stand, then run the command again, "
             "or tell your facilitator.")
HOST_STOPPED = "The cloud host stopped answering while this request was running. "
# what a refused write says, per path (exact text: a student reads it in the terminal)
MSG_NOT_READY = f"{NOT_ANSWERING} Nothing was changed. {RETRY}"
MSG_REPLACE = HOST_STOPPED + "The container group's record was left as it was, and its old container may still be running. " + PLAN_HINT
MSG_RG_DELETE = HOST_STOPPED + ("Container groups already deleted are gone; the rest and the resource group were "
                                "left in place. ") + PLAN_HINT
MSG_NET = HOST_STOPPED + ("What was recorded for your resources was left as it was; the container behind it may have "
                          "changed. ") + PLAN_HINT


class FakeHost:
    """The executor's surface, with a switch for the daemon being down and per-call failures."""

    def __init__(self):
        self.up = True
        self.images = set(policy.ALLOWED_IMAGES)
        self.containers = {}  # name -> running
        self.calls = []
        self.fail_create = False
        self.fail_remove = set()  # container names whose removal raises

    def _need_up(self):
        if not self.up:
            raise docker_api.DockerError("cloud-host unreachable: down")

    def ping(self):
        self.calls.append("ping")
        return self.up

    def image_present(self, image):
        self.calls.append(f"image_present {image}")
        self._need_up()
        return image in self.images

    def list_managed(self):
        self.calls.append("list_managed")
        self._need_up()
        return list(self.containers)

    def list_running(self):
        self._need_up()
        return {n for n, running in self.containers.items() if running}

    def state(self, name):
        self.calls.append(f"state {name}")
        self._need_up()
        return None if name not in self.containers else ("Running" if self.containers[name] else "Terminated")

    def create(self, name, image, env_pairs, host_port, cpu, memory_gb, labels):
        self.calls.append(f"create {name}")
        self._need_up()
        if self.fail_create:
            raise docker_api.DockerError("create failed (500)")
        self.containers[name] = True

    def remove(self, name):
        self.calls.append(f"remove {name}")
        self._need_up()
        if name in self.fail_remove:
            raise docker_api.DockerError("cloud-host unreachable: reset")
        self.containers.pop(name, None)
        return True

    def logs(self, name, tail=200):
        self._need_up()
        return "line\n"

    def mutating_calls(self):
        return [c for c in self.calls if c.split()[0] in ("create", "remove")]


class Base(unittest.TestCase):
    def setUp(self):
        self.host = FakeHost()
        self.st = state_mod.State(None)
        self.app = server.App(auth.Auth(b"k" * 32, [A, B, FAC], FAC, "iss"), self.st, self.host)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = {"GATEWAY_TOKEN": TOKEN}
        self.app.portal = portal_api.Portal(self.app, self.env, self.tmp.name)
        self.lines = []
        self.old_app, self.old_log = server.APP, server.log
        server.APP, server.log = self.app, self.lines.append
        self.addCleanup(lambda: (setattr(server, "APP", self.old_app), setattr(server, "log", self.old_log)))

    def go_ready(self):
        self.app.reconciled.set()
        self.app.readiness.refresh()
        self.assertTrue(self.app.readiness.snapshot()[0])

    def seed(self, user=A, rg="rg-a", name="ci-a1", label="site-a1", port=20001):
        sub = SUB[user]
        container = f"dojo-{user}-{rg}-{name}"
        self.st.rgs.setdefault(server.App.rg_key(sub, rg), {"name": rg, "location": "canadacentral", "tags": dict(TAGS)})
        body = {"properties": {"containers": [{"name": "hello", "properties": {"image": "dojo/hello:1.0"}}]}}
        self.st.cgs[server.App.cg_key(sub, rg, name)] = {
            "name": name, "rg": rg, "location": "canadacentral", "tags": dict(TAGS), "body": body,
            "spec": {"image": "dojo/hello:1.0", "env": [], "cpu": 0.25, "mem": 0.125},
            "port": port, "container": container, "dnsLabel": label, "owner": user}
        self.host.containers[container] = True
        return container

    def snapshot(self):
        return copy.deepcopy(self.st.data)


class ReadinessStates(Base):
    def state(self):
        self.app.readiness.refresh()
        ready, state, detail = self.app.readiness.snapshot()
        return ready, state, detail

    def test_before_the_first_check_it_is_starting(self):
        ready, state, detail = self.app.readiness.snapshot()
        self.assertEqual((ready, state), (False, "starting"))
        self.assertEqual(detail, "Dojo Cloud is not ready: the first readiness check has not finished.")

    def test_starting_until_docker_images_and_reconcile_are_all_there(self):
        self.host.up = False
        self.assertEqual(self.state(), (False, "starting", NOT_ANSWERING))
        self.host.up = True
        self.host.images = {"dojo/hello:1.0"}  # 2.0 still being imported
        self.assertEqual(self.state(), (False, "starting",
                                        "Dojo Cloud is not ready: the cloud host is still loading its app images."))
        self.host.images = set(policy.ALLOWED_IMAGES)
        self.assertEqual(self.state(), (False, "starting",
                                        "Dojo Cloud is not ready: the control plane is still syncing with the cloud host."))
        self.app.reconciled.set()
        self.assertEqual(self.state(), (True, "ready", "Dojo Cloud is ready."))

    def test_ready_then_lost_is_unavailable_then_ready_again(self):
        self.go_ready()
        self.host.up = False
        self.assertEqual(self.state(), (False, "unavailable", "Dojo Cloud is unavailable: the cloud host is not answering."))
        self.host.up = True
        self.host.images.discard("dojo/hello:2.0")
        self.assertEqual(self.state(), (False, "unavailable",
                                        "Dojo Cloud is unavailable: the cloud host is still loading its app images."))
        self.host.images.add("dojo/hello:2.0")
        self.assertEqual(self.state(), (True, "ready", "Dojo Cloud is ready."))

    def test_an_unexpected_error_in_the_check_keeps_the_thread_alive(self):
        self.host.ping = lambda: (_ for _ in ()).throw(RuntimeError("bug"))
        stop = threading.Event()
        t = threading.Thread(target=self.app.readiness.run, args=(stop, 0.01), daemon=True)
        t.start()
        time.sleep(0.15)
        self.assertTrue(t.is_alive())
        self.assertTrue([l for l in self.lines if "readiness check error" in l])
        stop.set()
        t.join(2)
        self.assertFalse(t.is_alive())

    def test_the_background_thread_publishes_changes(self):
        stop = threading.Event()
        self.addCleanup(stop.set)
        self.app.reconciled.set()
        threading.Thread(target=self.app.readiness.run, args=(stop, 0.01), daemon=True).start()
        self.wait_for(lambda: self.app.readiness.snapshot()[1] == "ready")
        self.host.up = False
        self.wait_for(lambda: self.app.readiness.snapshot()[1] == "unavailable")

    @staticmethod
    def wait_for(cond, timeout=3):
        end = time.monotonic() + timeout
        while not cond():
            if time.monotonic() > end:
                raise AssertionError("condition not met in time")
            time.sleep(0.01)

    def test_image_present_only_asks_about_allowed_images(self):
        with self.assertRaises(docker_api.DockerError):
            docker_api.Executor("/nonexistent.sock").image_present("alpine:latest")
        with self.assertRaises(docker_api.DockerError):  # unreachable is an error, never "missing"
            docker_api.Executor("/nonexistent.sock").image_present("dojo/hello:1.0")


class OverHttp(Base):
    def setUp(self):
        super().setUp()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, args=(0.01,), daemon=True).start()  # quick to stop
        self.addCleanup(lambda: (self.httpd.shutdown(), self.httpd.server_close()))

    def http(self, method, path, headers=None, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1], timeout=5)
        conn.request(method, path, body=body, headers=headers or {})
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        return resp, data

    def arm(self, method, path, body=None, user=A):
        tok = {"Authorization": "Bearer " + self.app.auth.issue_token(user, "aud")}
        resp, data = self.http(method, path, tok, None if body is None else json.dumps(body))
        return resp.status, (json.loads(data) if data else None)

    def cg_path(self, name="ci-a1", rg="rg-a", user=A):
        return f"/subscriptions/{SUB[user]}/resourceGroups/{rg}/providers/Microsoft.ContainerInstance/containerGroups/{name}"

    def put_body(self, label="site-a1", image="dojo/hello:1.0"):
        return {"location": "canadacentral", "tags": TAGS, "properties": {
            "osType": "Linux", "ipAddress": {"type": "Public", "dnsNameLabel": label, "ports": [{"port": 80}]},
            "containers": [{"name": "hello", "properties": {
                "image": image, "ports": [{"port": 80}], "resources": {"requests": {"cpu": 0.25, "memoryInGB": 0.125}}}}]}}

    # ---- /readyz ----------------------------------------------------------------
    def test_readyz_is_503_until_ready_and_needs_no_credentials(self):
        resp, data = self.http("GET", "/readyz")  # no Authorization, no gateway headers
        self.assertEqual(resp.status, 503)
        self.assertEqual(resp.getheader("Cache-Control"), "no-store")
        self.assertEqual(json.loads(data), {"ready": False, "state": "starting",
                                            "detail": "Dojo Cloud is not ready: the first readiness check has not finished."})
        self.go_ready()
        resp, data = self.http("GET", "/readyz")
        self.assertEqual((resp.status, json.loads(data)), (200, {"ready": True, "state": "ready", "detail": "Dojo Cloud is ready."}))
        self.host.up = False
        self.app.readiness.refresh()
        resp, data = self.http("GET", "/readyz/")
        self.assertEqual((resp.status, json.loads(data)["state"]), (503, "unavailable"))

    def test_readyz_answers_from_the_cache_without_asking_docker(self):
        self.go_ready()
        self.host.calls.clear()
        for _ in range(5):
            self.http("GET", "/readyz")
        self.assertEqual(self.host.calls, [])

    def test_healthz_still_means_the_process_is_up(self):
        self.host.up = False
        resp, data = self.http("GET", "/healthz")
        self.assertEqual((resp.status, json.loads(data)), (200, {"status": "ok", "cloudHost": False}))

    # ---- the 503 gate (ARM) -------------------------------------------------------
    def assert_gated(self, status, body, message=MSG_NOT_READY):
        self.assertEqual(status, server.NOT_READY_STATUS)  # never 503: the provider retries that for minutes
        self.assertEqual(body, {"error": {"code": "ServiceUnavailable", "message": message}})

    def test_arm_writes_are_refused_while_starting_and_change_nothing(self):
        self.host.up = False
        self.app.readiness.refresh()
        self.seed()
        self.seed(name="ci-a2", label="site-a2", port=20002)
        before, path = self.snapshot(), self.cg_path()
        self.assert_gated(*self.arm("PUT", self.cg_path("ci-new"), self.put_body("site-new")))
        self.assert_gated(*self.arm("PUT", path, self.put_body("site-changed")))
        self.assert_gated(*self.arm("PATCH", path, {"tags": TAGS}))
        self.assert_gated(*self.arm("DELETE", path))
        self.assert_gated(*self.arm("DELETE", f"/subscriptions/{SUB[A]}/resourceGroups/rg-a"))  # holds containers
        # resource groups too, even ones with no container: `apply` sends the group first, so refusing it fails the
        # whole run before anything is changed (no half-applied group/container pair)
        rg_new, rg_a = f"/subscriptions/{SUB[A]}/resourceGroups/rg-new", f"/subscriptions/{SUB[A]}/resourceGroups/rg-a"
        self.assert_gated(*self.arm("PUT", rg_new, {"location": "canadacentral", "tags": TAGS}))
        self.assert_gated(*self.arm("PUT", rg_a, {"location": "canadacentral", "tags": TAGS}))
        self.assert_gated(*self.arm("PATCH", rg_a, {"tags": TAGS}))
        self.assert_gated(*self.arm("DELETE", rg_new))
        self.assertEqual(self.snapshot(), before)  # nothing recorded, nothing logged
        self.assertEqual(self.host.mutating_calls(), [])

    def test_arm_reads_still_work_while_starting(self):
        self.seed()
        path = self.cg_path()
        status, body = self.arm("GET", path)
        self.assertEqual((status, body["name"]), (200, "ci-a1"))
        self.assertEqual(self.arm("GET", f"/subscriptions/{SUB[A]}/resourceGroups/rg-a")[0], 200)
        self.assertEqual(self.arm("GET", f"/subscriptions/{SUB[A]}/resourceGroups/rg-a/providers/"
                                  "Microsoft.ContainerInstance/containerGroups")[0], 200)

    def test_arm_writes_work_again_once_ready(self):
        self.go_ready()
        path = self.cg_path(rg="rg-aa")
        status, body = self.arm("PUT", f"/subscriptions/{SUB[A]}/resourceGroups/rg-aa", {"location": "canadacentral", "tags": TAGS})
        self.assertEqual(status, 201)
        status, body = self.arm("PUT", path, self.put_body())
        self.assertEqual((status, body["properties"]["instanceView"]["state"]), (201, "Running"))
        self.assertEqual(self.arm("DELETE", path)[0], 200)
        self.host.up = False
        self.app.readiness.refresh()
        self.assert_gated(*self.arm("PUT", path, self.put_body()),
                          f"Dojo Cloud is unavailable: the cloud host is not answering. Nothing was changed. {RETRY}")

    # ---- DockerError paths (ARM) --------------------------------------------------
    def test_replace_when_the_old_container_cannot_be_removed_changes_nothing(self):
        self.go_ready()
        container = self.seed()
        self.host.fail_remove.add(container)
        before = self.snapshot()
        status, body = self.arm("PUT", self.cg_path(), self.put_body("site-a1", "dojo/hello:2.0"))
        self.assert_gated(status, body, MSG_REPLACE)
        after = self.snapshot()
        self.assertEqual(after["cgs"], before["cgs"])  # the old record still matches the old container
        self.assertEqual([e["status"] for e in after["activity"]], ["Failed"])
        self.assertEqual(self.host.mutating_calls(), [f"remove {container}"])  # never tried to create

    def test_replace_when_create_fails_forgets_the_container_that_was_removed(self):
        self.go_ready()
        container = self.seed()
        self.host.fail_create = True
        status, body = self.arm("PUT", self.cg_path(), self.put_body("site-a1", "dojo/hello:2.0"))
        self.assertEqual((status, body["error"]["code"]), (500, "InternalServerError"))
        self.assertNotIn(container, self.host.containers)
        self.assertEqual(self.st.cgs, {})  # no record for a container that no longer exists
        self.assertEqual(self.arm("GET", self.cg_path())[0], 404)

    def test_new_create_failure_records_nothing(self):
        self.go_ready()
        self.st.rgs[server.App.rg_key(SUB[A], "rg-a")] = {"name": "rg-a", "location": "canadacentral", "tags": TAGS}
        self.host.fail_create = True
        self.assertEqual(self.arm("PUT", self.cg_path(), self.put_body())[0], 500)
        self.assertEqual(self.st.cgs, {})

    def test_delete_container_group_failure_keeps_the_record(self):
        self.go_ready()
        container = self.seed()
        self.host.fail_remove.add(container)
        with self.assertRaises(docker_api.DockerError):
            self.app.delete_container_group(SUB[A], "rg-a", "ci-a1", A)
        self.assertEqual(list(self.st.cgs), [server.App.cg_key(SUB[A], "rg-a", "ci-a1")])  # not forgotten
        self.assertEqual([e["status"] for e in self.st.data["activity"]], ["Failed"])
        self.host.fail_remove.clear()  # host is back: a retry now works
        self.assertTrue(self.app.delete_container_group(SUB[A], "rg-a", "ci-a1", A))
        self.assertEqual((self.st.cgs, self.host.containers), ({}, {}))
        self.assertFalse(self.app.delete_container_group(SUB[A], "rg-a", "ci-a1", A))

    def test_arm_delete_when_the_host_dies_mid_request_is_a_clean_503(self):
        self.go_ready()
        container = self.seed()
        self.host.fail_remove.add(container)  # the gate cached "ready"; the host dies after it
        before = self.snapshot()
        status, body = self.arm("DELETE", self.cg_path())
        self.assert_gated(status, body, MSG_NET)  # handle_any's safety net
        self.assertEqual(len(self.st.cgs), 1)
        self.assertEqual(self.st.cgs, before["cgs"])

    def test_resource_group_delete_keeps_records_in_step_with_containers(self):
        self.go_ready()
        first = self.seed()
        second = self.seed(name="ci-a2", label="site-a2", port=20002)
        self.host.fail_remove.add(second)
        status, body = self.arm("DELETE", f"/subscriptions/{SUB[A]}/resourceGroups/rg-a")
        self.assert_gated(status, body, MSG_RG_DELETE)
        self.assertNotIn(first, self.host.containers)  # gone, and so is its record
        self.assertEqual(list(self.st.cgs), [server.App.cg_key(SUB[A], "rg-a", "ci-a2")])
        self.assertIn(server.App.rg_key(SUB[A], "rg-a"), self.st.rgs)  # the group itself stays
        self.assertEqual(self.st.data["activity"][-1]["status"], "Failed")
        self.host.fail_remove.clear()
        self.assertEqual(self.arm("DELETE", f"/subscriptions/{SUB[A]}/resourceGroups/rg-a")[0], 200)
        self.assertEqual((self.st.cgs, self.st.rgs, self.host.containers), ({}, {}, {}))

    # ---- reads while cloud-host is down: 200 from the stored record ------------------
    RG_CGS = "/subscriptions/{sub}/resourceGroups/rg-a/providers/Microsoft.ContainerInstance/containerGroups"

    def read_all(self):
        """(status, body) of the three ARM reads that end in a Docker call."""
        return [self.arm("GET", self.cg_path()),
                self.arm("GET", self.RG_CGS.format(sub=SUB[A])),
                self.arm("GET", f"/subscriptions/{SUB[A]}/providers/Microsoft.ContainerInstance/containerGroups")]

    def test_reads_with_the_host_down_answer_200_and_the_same_json_as_when_it_was_up(self):
        self.go_ready()
        self.seed()
        self.seed(name="ci-a2", label="site-a2", port=20002)
        healthy = self.read_all()
        self.assertEqual([s for s, _ in healthy], [200, 200, 200])
        self.host.up = False
        down = self.read_all()
        self.assertEqual(down, healthy)  # byte for byte: an untouched deployment plans "No changes"
        self.assertEqual(down[0][1]["properties"]["instanceView"]["state"], "Running" if server.ASSUME_RUNNING else "Terminated")
        self.assertEqual(len(down[1][1]["value"]), 2)
        self.assertEqual(len(down[2][1]["value"]), 2)
        self.assertTrue([l for l in self.lines if "cloud-host error" in l])
        self.assertFalse([l for l in self.lines if "internal error" in l])

    def test_reads_with_the_host_down_have_the_shape_of_a_read_with_it_up(self):
        container = self.seed()
        self.host.containers[container] = False  # a stopped container reads as Terminated, same keys
        _, stopped = self.arm("GET", self.cg_path())
        self.assertEqual(stopped["properties"]["instanceView"]["state"], "Terminated")
        self.host.up = False
        status, body = self.arm("GET", self.cg_path())

        def shape(node):
            return {k: shape(v) for k, v in node.items()} if isinstance(node, dict) else \
                [shape(v) for v in node] if isinstance(node, list) else type(node).__name__
        self.assertEqual((status, shape(body)), (200, shape(stopped)))
        self.assertEqual(body["properties"]["containers"][0]["properties"]["instanceView"],
                         {"currentState": {"state": "Running"}})

    def test_a_read_with_the_host_down_changes_nothing_and_asks_docker_once_per_request(self):
        self.seed()
        self.seed(name="ci-a2", label="site-a2", port=20002)
        self.host.up = False
        before = self.snapshot()
        self.host.calls.clear()
        self.arm("GET", self.cg_path())
        self.assertEqual(self.host.calls, [f"state dojo-{A}-rg-a-ci-a1"])
        self.host.calls.clear()
        self.arm("GET", self.RG_CGS.format(sub=SUB[A]))  # two records, one failed question
        self.assertEqual(len(self.host.calls), 1)
        self.assertEqual(self.snapshot(), before)  # a host outage is not drift: the record stays, nothing is logged

    def test_reads_never_ask_docker_while_holding_the_state_lock(self):
        self.seed()
        held, real_state = [], self.host.state
        self.host.state = lambda name: (held.append(self.st.lock._is_owned()), real_state(name))[1]
        self.read_all()
        self.host.up = False
        self.read_all()
        self.assertEqual(len(held), 6)
        self.assertEqual(set(held), {False})

    def test_a_container_that_vanished_is_still_drift_when_the_host_is_up(self):
        container = self.seed()
        del self.host.containers[container]
        self.assertEqual(self.arm("GET", self.cg_path())[0], 404)
        self.assertEqual(self.st.cgs, {})
        self.assertEqual(self.st.data["activity"][-1]["operation"], "Container disappeared outside IaC")

    def test_a_record_replaced_during_the_read_is_not_forgotten(self):
        container = self.seed()
        key = server.App.cg_key(SUB[A], "rg-a", "ci-a1")

        def replaced_meanwhile(name):  # a PUT lands while the lock is released, and the container is briefly absent
            self.st.cgs[key]["spec"] = dict(self.st.cgs[key]["spec"], mem=0.25)
            return None
        self.host.state = replaced_meanwhile
        self.host.calls.clear()
        status, body = self.arm("GET", self.cg_path())
        self.assertEqual(status, 200)
        self.assertIn(key, self.st.cgs)
        self.assertEqual(self.st.data["activity"], [])

    def test_a_write_that_only_loses_the_host_for_its_reply_still_succeeds(self):
        self.go_ready()
        self.seed()

        def gone(name):
            raise docker_api.DockerError("cloud-host unreachable: reset")
        self.host.state = gone  # the gate said ready; the host drops before the response is built
        status, body = self.arm("PATCH", self.cg_path(), {"tags": {"owner": "x", "env": "y"}})
        self.assertEqual((status, body["tags"]), (200, {"owner": "x", "env": "y"}))  # tags-only: no Docker call to lose

    def test_the_container_logs_read_may_still_fail_with_the_host_down(self):
        self.seed()
        self.host.up = False
        status, body = self.arm("GET", self.cg_path() + "/logs")
        self.assertEqual((status, body["error"]["code"]), (503, "ServiceUnavailable"))  # a read: plain 503, only the portal asks
        self.assertEqual(body["error"]["message"], server.HOST_DOWN)

    def test_readyz_keeps_its_own_503_while_arm_refusals_use_the_constant(self):
        self.host.up = False
        self.app.readiness.refresh()
        resp, data = self.http("GET", "/readyz")
        self.assertEqual(resp.status, 503)  # for the allocator's probe, not for the provider
        self.assertEqual(json.loads(data)["detail"], NOT_ANSWERING)
        status, _ = self.arm("PUT", f"/subscriptions/{SUB[A]}/resourceGroups/rg-a/providers/Microsoft.ContainerInstance/"
                             "containerGroups/ci-x", self.put_body("site-x"))
        self.assertEqual(status, server.NOT_READY_STATUS)
        self.assertNotEqual(server.NOT_READY_STATUS, 503)

    # ---- the same gate on the portal ------------------------------------------------
    def portal(self, method, path, user=A, body=None):
        headers = {"X-Auth-User": user, "X-Gateway-Token": TOKEN}
        resp, data = self.http(method, path, headers, None if body is None else json.dumps(body))
        return resp.status, json.loads(data)

    def test_portal_delete_and_tags_are_refused_while_not_ready(self):
        self.seed()
        url, before = f"/cloud/api/containers/{SUB[A]}/rg-a/ci-a1", self.snapshot()
        for method, body in (("DELETE", None), ("PATCH", {"tags": {"owner": "x", "env": "y"}})):
            status, err = self.portal(method, url, body=body)
            self.assertEqual((status, err), (503, {"error": {"code": "ServiceUnavailable",
                                                             "message": "Dojo Cloud is not ready: the first readiness check has not finished."}}), method)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.host.mutating_calls(), [])
        status, body = self.portal("GET", url)  # reads keep working
        self.assertEqual((status, body["summary"]["name"]), (200, "ci-a1"))
        self.assertEqual(self.portal("GET", "/cloud/api/overview")[0], 200)
        self.go_ready()
        self.assertEqual(self.portal("PATCH", url, body={"tags": {"owner": "x", "env": "y"}})[0], 200)
        self.assertEqual(self.portal("DELETE", url)[0], 200)

    def test_portal_delete_when_the_host_dies_mid_request_keeps_the_record(self):
        self.go_ready()
        container = self.seed()
        self.host.fail_remove.add(container)
        url = f"/cloud/api/containers/{SUB[A]}/rg-a/ci-a1"
        status, err = self.portal("DELETE", url)
        self.assertEqual((status, err["error"]["code"]), (502, "CloudHostUnavailable"))
        self.assertEqual(len(self.st.cgs), 1)


class StartUp(Base):
    """The background 'wait for cloud-host, then reconcile' that replaced the 60 s wait in main()."""

    def run_start_up(self):
        self.stop = threading.Event()
        self.addCleanup(self.stop.set)
        self.thread = threading.Thread(target=self.app.start_up, args=(self.stop, 0.01), daemon=True)
        self.thread.start()

    def test_host_down_at_start_then_appears_and_reconcile_runs_once_it_does(self):
        self.host.up = False
        vanished = self.seed()  # recorded, but its container is gone
        del self.host.containers[vanished]
        self.host.containers["dojo-orphan"] = True  # a container nobody recorded
        self.run_start_up()
        time.sleep(0.15)
        self.assertFalse(self.app.reconciled.is_set())
        self.assertEqual(len(self.st.cgs), 1)  # nothing reconciled while the host was down
        self.assertEqual(self.host.mutating_calls(), [])
        self.host.up = True
        self.assertTrue(self.app.reconciled.wait(3))
        self.thread.join(2)
        self.assertFalse(self.thread.is_alive())  # done: it does not keep polling
        self.assertEqual(self.st.cgs, {})
        self.assertEqual(self.host.containers, {})  # orphan removed
        self.assertEqual(len([l for l in self.lines if "cloud-host is not ready yet" in l]), 1)  # said once

    def test_a_failing_reconcile_is_retried(self):
        self.host.containers["dojo-orphan"] = True
        self.host.fail_remove.add("dojo-orphan")
        self.run_start_up()
        time.sleep(0.15)
        self.assertFalse(self.app.reconciled.is_set())
        self.host.fail_remove.clear()
        self.assertTrue(self.app.reconciled.wait(3))
        self.assertEqual(self.host.containers, {})

    def test_reconcile_reports_whether_it_worked_and_removes_orphans_outside_the_lock(self):
        held = []
        real_remove = self.host.remove
        self.host.remove = lambda name: (held.append(self.st.lock._is_owned()), real_remove(name))[1]
        self.host.containers["dojo-orphan"] = True
        self.assertTrue(self.app.reconcile())
        self.assertEqual(held, [False])
        self.host.up = False
        self.assertFalse(self.app.reconcile())

    def test_an_unexpected_error_is_logged_and_retried(self):
        calls = []

        def flaky_ping():
            calls.append(1)
            if len(calls) < 3:
                raise RuntimeError("bug")
            return True

        self.host.ping = flaky_ping
        self.run_start_up()
        self.assertTrue(self.app.reconciled.wait(3))
        self.assertTrue([l for l in self.lines if "start-up error" in l])

    def test_stopping_ends_the_wait_without_reconciling(self):
        self.host.up = False
        self.run_start_up()
        self.stop.set()
        self.thread.join(2)
        self.assertFalse(self.thread.is_alive())
        self.assertFalse(self.app.reconciled.is_set())


class FakeDockerd(socketserver.ThreadingUnixStreamServer):
    """Just enough Docker Engine API for the executor calls readiness and reconcile make."""
    daemon_threads = True

    def __init__(self, path):
        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                p = unquote(urlparse(self.path).path)
                if p == "/_ping":
                    code, body = 200, b"OK"
                elif p.startswith("/images/") and p.endswith("/json"):
                    code, body = (200, b"{}") if p[len("/images/"):-len("/json")] in policy.ALLOWED_IMAGES else (404, b"{}")
                elif p == "/containers/json":
                    code, body = 200, b"[]"
                else:
                    code, body = 404, b"{}"
                self.send_response(code)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        super().__init__(path, H)


class MainProcess(unittest.TestCase):
    """The real main(): it listens at once with the host absent and becomes ready when the host shows up."""
    SCRIPT = """
import sys
import server
server.log = lambda msg: None
server.READY_INTERVAL = server.RECONCILE_RETRY = 0.1
sys.exit(server.main())
"""

    def free_port(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    def readyz(self, port):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            conn.request("GET", "/readyz")
            resp = conn.getresponse()
            return resp.status, json.loads(resp.read())
        except OSError:
            return None, None
        finally:
            conn.close()

    def test_listens_immediately_and_turns_ready_when_cloud_host_appears(self):
        here = os.path.dirname(os.path.abspath(__file__))
        tmp = tempfile.mkdtemp()
        sock, port = os.path.join(tmp, "docker.sock"), self.free_port()
        env = dict(os.environ, CLOUD_DATA_DIR=tmp + "/data", CLOUD_PKI_DIR=tmp + "/pki", CLOUD_SECRETS_DIR=tmp + "/sec",
                   CLOUD_DOCKER_SOCKET=sock, CLOUD_HTTP_PORT=str(port), CLOUD_HTTPS_PORT=str(self.free_port()),
                   STUDENT_COUNT="2", GATEWAY_TOKEN=TOKEN, PYTHONDONTWRITEBYTECODE="1")
        proc = subprocess.Popen([sys.executable, "-B", "-c", self.SCRIPT], cwd=here, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(proc.kill)
        end = time.monotonic() + 15  # openssl makes the CA first
        status = None
        while status is None and time.monotonic() < end:
            status, body = self.readyz(port)
            time.sleep(0.05)
        self.assertEqual((status, body["state"]), (503, "starting"), proc.poll())
        time.sleep(0.4)  # several check cycles with no host: still starting, not crashed
        self.assertEqual(self.readyz(port)[1]["ready"], False)
        dockerd = FakeDockerd(sock)
        threading.Thread(target=dockerd.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (dockerd.shutdown(), dockerd.server_close()))
        end = time.monotonic() + 5
        while self.readyz(port)[0] != 200 and time.monotonic() < end:
            time.sleep(0.05)
        self.assertEqual(self.readyz(port), (200, {"ready": True, "state": "ready", "detail": "Dojo Cloud is ready."}))
        started = time.monotonic()
        proc.send_signal(signal.SIGTERM)
        out, err = proc.communicate(timeout=5)
        self.assertEqual(proc.returncode, 0, err)
        self.assertLess(time.monotonic() - started, 4)


if __name__ == "__main__":
    unittest.main()
