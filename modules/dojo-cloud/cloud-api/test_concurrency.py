"""Lock narrowing (PLAN.md 5.8): no Docker call is made while State.lock is held, and the reservations
(State.pending / State.deleting_rgs) keep concurrent writes from stepping on each other.

Real HTTP server, fake executor. Ordering is made deterministic with Events, Barriers and queues: the fake
executor's create/remove can be held at a gate (so a request is provably "in Docker"), a Barrier proves calls
overlap, and the only sleep is `create_delay`, the fake "slow Docker" of the timing test. Run from this directory:
    python3 -B -m unittest test_concurrency
"""
import concurrent.futures as futures
import copy
import http.client
import json
import queue
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer

import auth
import docker_api
import policy
import portal_api
import server
import state as state_mod

TOKEN = "gw-secret-token"
FAC = "admin"
USERS = [f"student{n:02d}" for n in range(1, 11)]
SUB = {u: auth.subscription_id(u) for u in USERS + [FAC]}
TAGS = {"owner": "someone", "env": "dev"}
WAIT = 5  # seconds: the most any wait may take. A hang is a failure, never a pass.
CREATE_DELAY = 0.5  # the fake "slow Docker" of the timing test
BUSY = "Another operation on this container group is in progress. Wait for it to finish, then try again."


class FakeExecutor:
    """The executor's surface. create()/remove() announce themselves on a queue, then wait at a gate (open by
    default), so a test can hold a request inside Docker and look at the rest of the system meanwhile."""

    def __init__(self):
        self.lock = threading.Lock()
        self.containers = {}  # name -> running
        self.created = []  # (name, host port), in call order
        self.create_delay = 0.0
        self.create_gate, self.remove_gate = threading.Event(), threading.Event()
        self.create_gate.set()
        self.remove_gate.set()
        self.entered_create, self.entered_remove = queue.Queue(), queue.Queue()
        self.barrier = None  # a Barrier every create() must reach before any continues: proves overlap
        self.fail_create = self.fail_remove = None  # an exception to raise (DockerError or anything else)

    @staticmethod
    def _pass(gate):
        if not gate.wait(WAIT * 2):
            raise RuntimeError("test bug: gate never opened")

    def ping(self):
        return True

    def image_present(self, image):
        return True

    def list_managed(self):
        with self.lock:
            return list(self.containers)

    def list_running(self):
        with self.lock:
            return {n for n, running in self.containers.items() if running}

    def state(self, name):
        with self.lock:
            return None if name not in self.containers else ("Running" if self.containers[name] else "Terminated")

    def create(self, name, image, env_pairs, host_port, cpu, memory_gb, labels):
        self.entered_create.put(name)
        if self.barrier is not None:
            self.barrier.wait(WAIT)
        self._pass(self.create_gate)
        if self.create_delay:
            time.sleep(self.create_delay)
        if self.fail_create is not None:
            raise self.fail_create
        with self.lock:
            self.containers[name] = True
            self.created.append((name, host_port))

    def remove(self, name):
        self.entered_remove.put(name)
        self._pass(self.remove_gate)
        if self.fail_remove is not None:
            raise self.fail_remove
        with self.lock:
            self.containers.pop(name, None)
        return True

    def logs(self, name, tail=200):
        return "line\n"


class Concurrency(unittest.TestCase):
    def setUp(self):
        self.host = FakeExecutor()
        self.st = state_mod.State(None)
        self.app = server.App(auth.Auth(b"k" * 32, USERS + [FAC], FAC, "iss"), self.st, self.host)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app.portal = portal_api.Portal(self.app, {"GATEWAY_TOKEN": TOKEN}, self.tmp.name)
        self.lines = []
        self.old_app, self.old_log = server.APP, server.log
        server.APP, server.log = self.app, self.lines.append
        self.addCleanup(lambda: (setattr(server, "APP", self.old_app), setattr(server, "log", self.old_log)))
        self.app.reconciled.set()
        self.app.readiness.refresh()
        self.assertTrue(self.app.readiness.snapshot()[0])
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.httpd.daemon_threads = True
        threading.Thread(target=self.httpd.serve_forever, args=(0.01,), daemon=True).start()
        self.pool = futures.ThreadPoolExecutor(max_workers=24)

        def cleanup():  # open every gate first, so a failed test cannot leave a request stuck in the fake
            self.host.create_gate.set()
            self.host.remove_gate.set()
            if self.host.barrier is not None:
                self.host.barrier.abort()
            self.pool.shutdown(wait=True)
            self.httpd.shutdown()
            self.httpd.server_close()
        self.addCleanup(cleanup)

    # ---- helpers ----------------------------------------------------------------
    def request(self, method, path, headers, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.httpd.server_address[1], timeout=WAIT)
        try:
            conn.request(method, path, body=None if body is None else json.dumps(body), headers=headers)
            resp = conn.getresponse()
            data = resp.read()
            return resp.status, (json.loads(data) if data else None)
        finally:
            conn.close()

    def arm(self, method, path, body=None, user=USERS[0]):
        return self.request(method, path, {"Authorization": "Bearer " + self.app.auth.issue_token(user, "aud")}, body)

    def portal(self, method, path, user=USERS[0]):
        return self.request(method, path, {"X-Gateway-Token": TOKEN, "X-Auth-User": user})

    def go(self, fn, *args, **kw):
        """Start a request on another thread -> a Future."""
        return self.pool.submit(fn, *args, **kw)

    def first(self, futs, n):
        """The first n of `futs` to finish (waits for them, with a bound)."""
        return [f for _, f in zip(range(n), futures.as_completed(futs, timeout=WAIT))]

    def entered(self, q, n=1):
        """Blocks until n calls have reached the fake executor's queue `q`; -> their container names."""
        return [q.get(timeout=WAIT) for _ in range(n)]

    def cg_path(self, user=USERS[0], name="ci-a1", rg="rg-a"):
        return (f"/subscriptions/{SUB[user]}/resourceGroups/{rg}/providers/"
                f"Microsoft.ContainerInstance/containerGroups/{name}")

    def rg_path(self, user=USERS[0], rg="rg-a"):
        return f"/subscriptions/{SUB[user]}/resourceGroups/{rg}"

    def put_body(self, label="site-a1", image="dojo/hello:1.0"):
        return {"location": "canadacentral", "tags": TAGS, "properties": {
            "osType": "Linux", "ipAddress": {"type": "Public", "dnsNameLabel": label, "ports": [{"port": 80}]},
            "containers": [{"name": "hello", "properties": {
                "image": image, "ports": [{"port": 80}], "resources": {"requests": {"cpu": 0.25, "memoryInGB": 0.125}}}}]}}

    def put(self, user=USERS[0], name="ci-a1", rg="rg-a", label="site-a1", image="dojo/hello:1.0"):
        return self.arm("PUT", self.cg_path(user, name, rg), self.put_body(label, image), user)

    def seed_rg(self, user=USERS[0], rg="rg-a"):
        self.st.rgs[server.App.rg_key(SUB[user], rg)] = {"name": rg, "location": "canadacentral", "tags": dict(TAGS)}

    def seed(self, user=USERS[0], rg="rg-a", name="ci-a1", label="site-a1", port=20000):
        self.seed_rg(user, rg)
        container = f"dojo-{user}-{rg}-{name}"
        body = self.put_body(label)
        self.st.cgs[server.App.cg_key(SUB[user], rg, name)] = {
            "name": name, "rg": rg, "location": "canadacentral", "tags": dict(TAGS), "body": body,
            "spec": {"image": "dojo/hello:1.0", "env": [], "cpu": 0.25, "mem": 0.125},
            "port": port, "container": container, "dnsLabel": label, "owner": user}
        self.host.containers[container] = True
        return container

    def hold_create(self, **put_args):
        """Starts a PUT and waits until it is inside the executor's create (gate closed) -> its Future."""
        self.host.create_gate.clear()
        fut = self.go(self.put, **put_args)
        self.entered(self.host.entered_create)
        return fut

    def assert_nothing_reserved(self):
        self.assertEqual((self.st.pending, self.st.deleting_rgs), ({}, set()))

    def assert_busy(self, result):
        self.assertEqual(result, (409, {"error": {"code": "Conflict", "message": BUSY}}))

    # ---- parallel writes overlap ----------------------------------------------------
    def test_puts_from_different_subscriptions_are_in_docker_at_the_same_time(self):
        n = 8
        for user in USERS[:n]:
            self.seed_rg(user)
        self.host.barrier = threading.Barrier(n)  # every create waits for all n: only possible if they overlap
        futs = [self.go(self.put, user, label=f"site-{user}") for user in USERS[:n]]
        self.assertEqual([f.result(WAIT * 2)[0] for f in futs], [201] * n)
        self.assert_nothing_reserved()

    def test_parallel_puts_take_about_one_create_not_n(self):
        n = 8
        for user in USERS[:n]:
            self.seed_rg(user)
        self.host.create_delay = CREATE_DELAY
        start = time.monotonic()
        futs = [self.go(self.put, user, label=f"site-{user}") for user in USERS[:n]]
        self.assertEqual([f.result(WAIT * 2)[0] for f in futs], [201] * n)
        self.elapsed = time.monotonic() - start
        # one delay plus request overhead; serialised behind the lock it would be n * CREATE_DELAY = 4 s
        self.assertLess(self.elapsed, CREATE_DELAY * n / 2)

    def test_ten_parallel_puts_get_ten_distinct_ports(self):
        for user in USERS:
            self.seed_rg(user)
        self.host.barrier = threading.Barrier(len(USERS))  # all ten reservations exist at the same moment
        futs = [self.go(self.put, user, label=f"site-{user}") for user in USERS]
        self.assertEqual([f.result(WAIT * 2)[0] for f in futs], [201] * len(USERS))
        ports = [port for _, port in self.host.created]
        self.assertEqual(sorted(ports), list(range(20000, 20000 + len(USERS))))
        self.assertEqual(sorted(rec["port"] for rec in self.st.cgs.values()), sorted(ports))

    # ---- readers are not held up by a slow create ----------------------------------------
    def test_reads_answer_while_a_create_is_stuck_in_docker(self):
        self.seed(USERS[1], rg="rg-b", name="ci-b1", label="site-b1", port=20000)
        self.seed_rg(USERS[0])
        put = self.hold_create(user=USERS[0], label="site-a1")
        # Each of these returns while the create is still blocked at its gate: with the lock held across
        # Docker they would wait for it, and the client timeout would fail the test.
        self.assertEqual(self.arm("GET", self.cg_path(USERS[0]))[0], 404)  # not committed yet
        self.assertEqual(self.arm("GET", self.cg_path(USERS[1], "ci-b1", "rg-b"), user=USERS[1])[0], 200)
        self.assertEqual(self.arm("GET", self.rg_path(USERS[0]))[0], 200)
        self.assertEqual(self.arm("GET", self.rg_path(USERS[0]) + "/providers/Microsoft.ContainerInstance/"
                                  "containerGroups")[0], 200)
        self.assertEqual(self.portal("GET", "/cloud/api/overview?scope=class")[0], 200)
        self.assertEqual(self.portal("GET", "/cloud/api/me")[0], 200)
        self.assertEqual(self.portal("GET", "/cloud/api/activity?scope=all", FAC)[0], 200)
        self.assertEqual(self.portal("GET", "/cloud/api/admin/progress", FAC)[0], 200)
        self.assertEqual(self.arm("PUT", self.rg_path(USERS[2], "rg-cc"), {"location": "canadacentral", "tags": TAGS},
                                  USERS[2])[0], 201)  # resource-group writes too
        self.assertFalse(put.done())
        self.host.create_gate.set()
        self.assertEqual(put.result(WAIT)[0], 201)

    def test_a_get_during_a_replace_does_not_report_the_container_as_gone(self):
        container = self.seed()
        put = self.hold_create(image="dojo/hello:2.0")  # the old container is already removed, the new one not yet
        self.assertIsNone(self.host.state(container))
        status, body = self.arm("GET", self.cg_path())
        self.assertEqual(status, 200)
        self.assertEqual(body["name"], "ci-a1")
        self.assertIn(server.App.cg_key(SUB[USERS[0]], "rg-a", "ci-a1"), self.st.cgs)  # the record was not dropped
        self.assertEqual([e for e in self.st.data["activity"] if "disappeared" in e["operation"]], [])
        self.host.create_gate.set()
        self.assertEqual(put.result(WAIT)[0], 200)
        self.assertEqual(self.arm("GET", self.cg_path())[0], 200)
        self.assertEqual([e for e in self.st.data["activity"] if "disappeared" in e["operation"]], [])

    def test_a_container_that_really_vanished_is_still_reported_as_drift(self):
        container = self.seed()
        self.host.containers.pop(container)
        self.assertEqual(self.arm("GET", self.cg_path())[0], 404)
        self.assertEqual([e["operation"] for e in self.st.data["activity"]], ["Container disappeared outside IaC"])

    # ---- reservations count -------------------------------------------------------------
    def test_five_parallel_puts_from_one_subscription_get_exactly_the_quota(self):
        self.seed_rg()
        self.host.create_gate.clear()  # the accepted ones stay in Docker while the rest are decided
        futs = [self.go(self.put, name=f"ci-a{i}", label=f"site-a{i}") for i in range(5)]
        refused = self.first(futs, 3)
        self.assertEqual({f.result()[0] for f in refused}, {409})
        self.assertEqual({f.result()[1]["error"]["code"] for f in refused}, {"QuotaExceeded"})
        self.assertEqual(len(self.entered(self.host.entered_create, 2)), 2)
        self.host.create_gate.set()
        self.assertEqual(sorted(f.result(WAIT)[0] for f in futs), [201, 201, 409, 409, 409])
        self.assertEqual(len(self.st.cgs), policy.MAX_CONTAINER_GROUPS)
        self.assert_nothing_reserved()

    def test_two_puts_for_the_same_dns_label_one_wins(self):
        self.seed_rg(USERS[0])
        self.seed_rg(USERS[1])
        self.host.create_gate.clear()
        futs = [self.go(self.put, user, label="site-shared") for user in USERS[:2]]
        (loser,) = self.first(futs, 1)  # the winner is held in Docker, so the first answer is the refusal
        self.assertEqual(loser.result()[0], 409)
        self.assertEqual(loser.result()[1]["error"]["code"], "DnsNameLabelInUse")
        self.host.create_gate.set()
        self.assertEqual(sorted(f.result(WAIT)[0] for f in futs), [201, 409])
        self.assertEqual([rec["dnsLabel"] for rec in self.st.cgs.values()], ["site-shared"])
        self.assert_nothing_reserved()

    def test_a_dns_label_stays_reserved_while_its_group_is_being_replaced(self):
        self.seed(label="site-old")
        self.seed_rg(USERS[1], "rg-b")
        put = self.hold_create(label="site-new", image="dojo/hello:2.0")
        for label in ("site-old", "site-new"):  # the old one is still recorded, the new one is reserved
            status, body = self.put(USERS[1], "ci-b1", "rg-b", label)
            self.assertEqual((status, body["error"]["code"]), (409, "DnsNameLabelInUse"))
        self.host.create_gate.set()
        self.assertEqual(put.result(WAIT)[0], 200)

    def test_two_puts_for_the_same_key_one_creates_and_one_is_told_to_wait(self):
        self.seed_rg()
        self.host.create_gate.clear()
        futs = [self.go(self.put) for _ in range(2)]
        (loser,) = self.first(futs, 1)
        self.assert_busy(loser.result())
        self.host.create_gate.set()
        self.assertEqual(sorted(f.result(WAIT)[0] for f in futs), [201, 409])
        self.assertEqual(len(self.host.created), 1)
        self.assertEqual(len(self.st.cgs), 1)
        ops = [e["operation"] for e in self.st.data["activity"]]
        self.assertEqual(ops, ["Create/Update container group"])  # the busy answer is not logged

    def test_a_busy_answer_changes_nothing(self):
        self.seed_rg()
        put = self.hold_create()
        before = copy.deepcopy((self.st.data, self.st.pending))
        self.assert_busy(self.put(label="site-other"))
        self.assertEqual(copy.deepcopy((self.st.data, self.st.pending)), before)
        self.host.create_gate.set()
        put.result(WAIT)

    # ---- PUT against a resource-group DELETE, both orders ----------------------------------
    def test_rg_delete_during_a_create_is_refused_and_leaves_no_orphan(self):
        self.seed_rg()
        put = self.hold_create()
        self.assert_busy(self.arm("DELETE", self.rg_path()))
        self.host.create_gate.set()
        self.assertEqual(put.result(WAIT)[0], 201)
        self.assertIn(server.App.rg_key(SUB[USERS[0]], "rg-a"), self.st.rgs)
        self.assertEqual(len(self.st.cgs), 1)
        self.assert_nothing_reserved()
        self.assertEqual(self.arm("DELETE", self.rg_path())[0], 200)  # and once it is over, the delete works
        self.assertEqual((self.st.rgs, self.st.cgs, self.host.containers), ({}, {}, {}))

    def test_put_during_an_rg_delete_is_refused_and_leaves_no_orphan(self):
        self.seed()
        self.host.remove_gate.clear()
        delete = self.go(self.arm, "DELETE", self.rg_path())
        self.entered(self.host.entered_remove)
        self.assert_busy(self.put(name="ci-a2", label="site-a2"))  # a new group in the doomed rg
        self.assert_busy(self.put(label="site-a1", image="dojo/hello:2.0"))  # a replace of the one being removed
        self.assertEqual(self.host.created, [])
        self.host.remove_gate.set()
        self.assertEqual(delete.result(WAIT)[0], 200)
        self.assertEqual((self.st.rgs, self.st.cgs), ({}, {}))
        self.assertEqual(self.put(name="ci-a2", label="site-a2")[1]["error"]["code"], "ResourceGroupNotFound")
        self.assert_nothing_reserved()

    def test_reads_answer_while_an_rg_delete_is_stuck_in_docker(self):
        self.seed()
        self.seed(USERS[1], rg="rg-b", name="ci-b1", label="site-b1", port=20001)
        self.host.remove_gate.clear()
        delete = self.go(self.arm, "DELETE", self.rg_path())
        self.entered(self.host.entered_remove)
        self.assertEqual(self.arm("GET", self.rg_path())[0], 200)  # still there until the delete commits
        self.assertEqual(self.arm("GET", self.cg_path())[0], 200)  # the record is still answered
        self.assertEqual(self.arm("GET", self.rg_path(USERS[1], "rg-b"), user=USERS[1])[0], 200)
        self.assertEqual(self.portal("GET", "/cloud/api/overview?scope=class")[0], 200)
        self.assertEqual(self.arm("PUT", self.rg_path(USERS[2], "rg-cc"), {"location": "canadacentral", "tags": TAGS},
                                  USERS[2])[0], 201)
        self.assertFalse(delete.done())
        self.host.remove_gate.set()
        self.assertEqual(delete.result(WAIT)[0], 200)

    def test_rg_delete_failing_part_way_drops_only_the_removed_records_and_releases_everything(self):
        first = self.seed(name="ci-a1", label="site-a1", port=20000)
        second = self.seed(name="ci-a2", label="site-a2", port=20001)
        original_remove = self.host.remove

        def remove(name):  # the second container cannot be removed
            if name == second:
                raise docker_api.DockerError("cloud-host unreachable: reset")
            return original_remove(name)
        self.host.remove = remove
        status, body = self.arm("DELETE", self.rg_path())
        self.assertEqual((status, body["error"]["code"]), (409, "ServiceUnavailable"))
        self.assertIn("Container groups already deleted are gone; the rest and the resource group were left in place.",
                      body["error"]["message"])
        self.assertEqual(sorted(rec["container"] for rec in self.st.cgs.values()), [second])
        self.assertNotIn(first, self.host.containers)
        self.assertEqual(len(self.st.rgs), 1)
        self.assertEqual(self.st.data["activity"][-1]["status"], "Failed")
        self.assert_nothing_reserved()
        self.host.remove = original_remove  # the host is back: a retry finishes the job
        self.assertEqual(self.arm("DELETE", self.rg_path())[0], 200)
        self.assertEqual((self.st.rgs, self.st.cgs), ({}, {}))

    # ---- deleting one container group ---------------------------------------------------
    def test_delete_during_a_create_or_a_delete_is_refused(self):
        self.seed_rg()
        put = self.hold_create()
        self.assert_busy(self.arm("DELETE", self.cg_path()))  # ARM
        status, body = self.portal("DELETE", "/cloud/api/containers/" + SUB[USERS[0]] + "/rg-a/ci-a1")  # portal
        self.assertEqual((status, body), (409, {"error": {"code": "Conflict", "message": BUSY}}))
        self.host.create_gate.set()
        self.assertEqual(put.result(WAIT)[0], 201)
        self.host.remove_gate.clear()  # now the other way round: a delete in flight
        delete = self.go(self.arm, "DELETE", self.cg_path())
        self.entered(self.host.entered_remove)
        self.assert_busy(self.arm("DELETE", self.cg_path()))
        self.assert_busy(self.put(label="site-a1", image="dojo/hello:2.0"))
        self.host.remove_gate.set()
        self.assertEqual(delete.result(WAIT)[0], 200)
        self.assertEqual(self.st.cgs, {})
        self.assert_nothing_reserved()

    def test_delete_holds_the_quota_slot_until_it_is_over(self):
        for name, label, port in (("ci-a1", "site-a1", 20000), ("ci-a2", "site-a2", 20001)):
            self.seed(name=name, label=label, port=port)
        self.host.remove_gate.clear()
        delete = self.go(self.arm, "DELETE", self.cg_path())
        self.entered(self.host.entered_remove)
        self.assertEqual(self.put(name="ci-a3", label="site-a3")[1]["error"]["code"], "QuotaExceeded")
        self.host.remove_gate.set()
        self.assertEqual(delete.result(WAIT)[0], 200)
        self.assertEqual(self.put(name="ci-a3", label="site-a3")[0], 201)

    def test_deletes_of_different_groups_run_at_the_same_time(self):
        self.seed(name="ci-a1", label="site-a1", port=20000)
        self.seed(USERS[1], rg="rg-b", name="ci-b1", label="site-b1", port=20001)
        self.host.remove_gate.clear()
        futs = [self.go(self.arm, "DELETE", self.cg_path()),
                self.go(self.arm, "DELETE", self.cg_path(USERS[1], "ci-b1", "rg-b"), None, USERS[1])]
        self.assertEqual(len(self.entered(self.host.entered_remove, 2)), 2)  # both are inside Docker together
        self.host.remove_gate.set()
        self.assertEqual([f.result(WAIT)[0] for f in futs], [200, 200])

    # ---- a reservation is released on every path -------------------------------------------
    def test_a_failed_create_releases_the_reservation_and_the_retry_reuses_the_port(self):
        self.seed_rg()
        self.host.fail_create = docker_api.DockerError("create failed (500)")
        status, body = self.put()
        self.assertEqual((status, body["error"]["code"]), (500, "InternalServerError"))
        self.assert_nothing_reserved()
        self.assertEqual(self.st.cgs, {})
        self.host.fail_create = None
        self.assertEqual(self.put()[0], 201)
        self.assertEqual(self.host.created, [("dojo-student01-rg-a-ci-a1", 20000)])  # the port came back

    def test_a_create_that_raises_something_unexpected_releases_the_reservation_too(self):
        self.seed_rg()
        self.host.fail_create = RuntimeError("a bug in the executor")
        status, body = self.put()
        self.assertEqual((status, body["error"]["code"]), (500, "InternalServerError"))
        self.assertNotIn("bug", json.dumps(body))
        self.assert_nothing_reserved()
        self.assertEqual(self.st.cgs, {})
        self.host.fail_create = None
        self.assertEqual(self.put()[0], 201)  # not "busy", not "quota", not "label in use"
        self.assertEqual(self.host.created, [("dojo-student01-rg-a-ci-a1", 20000)])
        self.assert_nothing_reserved()

    def test_a_replace_that_raises_something_unexpected_releases_the_reservation_too(self):
        container = self.seed()
        for broken in ("fail_remove", "fail_create"):
            setattr(self.host, broken, RuntimeError("a bug in the executor"))
            self.assertEqual(self.put(label="site-a1", image="dojo/hello:2.0")[0], 500)
            self.assert_nothing_reserved()
            setattr(self.host, broken, None)
            self.host.containers[container] = True
        self.assertEqual(self.put(label="site-a1", image="dojo/hello:2.0")[0], 200)
        self.assert_nothing_reserved()

    def test_a_failure_while_recording_the_result_releases_the_reservation_too(self):
        self.seed_rg()
        real_save = self.st.save

        def broken_save():
            raise OSError("disk full")
        self.st.save = broken_save
        self.assertEqual(self.put()[0], 500)  # the commit itself blew up, after Docker had finished
        self.assert_nothing_reserved()
        self.st.save = real_save
        self.assertEqual(self.put()[0], 200)  # the record was made, so this is now an update of it
        self.assert_nothing_reserved()

    def test_deletes_that_raise_something_unexpected_release_their_claims(self):
        self.seed()
        self.host.fail_remove = RuntimeError("a bug in the executor")
        self.assertEqual(self.arm("DELETE", self.cg_path())[0], 500)  # ARM
        self.assertEqual(self.portal("DELETE", "/cloud/api/containers/" + SUB[USERS[0]] + "/rg-a/ci-a1")[0], 500)
        self.assertEqual(self.arm("DELETE", self.rg_path())[0], 500)  # resource group
        self.assert_nothing_reserved()
        self.assertEqual(len(self.st.cgs), 1)
        self.host.fail_remove = None
        self.assertEqual(self.arm("DELETE", self.cg_path())[0], 200)
        self.assertEqual(self.arm("DELETE", self.rg_path())[0], 200)
        self.assert_nothing_reserved()

    def test_a_delete_that_fails_in_docker_releases_its_claim(self):
        self.seed()
        self.host.fail_remove = docker_api.DockerError("cloud-host unreachable: reset")
        self.assertEqual(self.arm("DELETE", self.cg_path())[0], 409)
        self.assert_nothing_reserved()
        self.assertEqual(len(self.st.cgs), 1)  # a failed delete changes nothing
        self.host.fail_remove = None
        self.assertEqual(self.arm("DELETE", self.cg_path())[0], 200)


if __name__ == "__main__":
    unittest.main()
