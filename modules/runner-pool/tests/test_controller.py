"""Unit tests for runner-controller (no stack needed):

    python3 -B -m unittest discover -s modules/runner-pool/tests -p 'test_*.py'

A fake Forgejo and a temporary spool stand in for the real ones; the
supervisor's state.json is written by hand.
"""
import http.client
import json
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "controller"))
import controller as c  # noqa: E402

TOKEN = "gw-token"


class FakeForgejo:
    def __init__(self):
        self.regs = {}  # name -> {"id","name","status"}
        self.jobs = []
        self.next_id = 1
        self.deleted = []
        self.down = False

    def _check(self):
        if self.down:
            raise c.ForgejoError("GET /admin/actions/runners: connection refused")

    def runners(self):
        self._check()
        return list(self.regs.values())

    def waiting_jobs(self, labels):
        self._check()
        return list(self.jobs)

    def register(self, name):
        self._check()
        self.regs[name] = {"id": self.next_id, "name": name, "status": "offline"}
        self.next_id += 1
        return "uuid-" + name, "token-" + name

    def delete_runner(self, runner_id):
        self.deleted.append(runner_id)
        for name, r in list(self.regs.items()):
            if r["id"] == runner_id:
                del self.regs[name]

    def repo_name(self, repo_id):
        return f"student0{repo_id}/vault-fundamentals"


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        env = {"RUNNER_MIN_IDLE": "2", "RUNNER_MAX": "4", "GATEWAY_TOKEN": TOKEN,
               "FACILITATOR_USERNAME": "root", "SPOOL_DIR": self.tmp.name}
        self.cfg = c.Config(env)
        self.fj = FakeForgejo()
        self.spool = c.Spool(self.tmp.name)
        self.clock = Clock()
        self.ctl = c.Controller(self.cfg, self.fj, self.spool, clock=self.clock)
        self.sup = {}

    def tearDown(self):
        self.tmp.cleanup()

    def supervise(self, state="idle", since=None):
        """Play the supervisor: take every start file as a runner in `state`."""
        for f in os.listdir(self.spool.start_dir):
            if f.endswith(".yaml"):
                name = f[:-5]
                with open(os.path.join(self.spool.start_dir, f)) as fh:
                    cfg = json.load(fh)
                self.assertEqual(cfg["server"]["connections"]["dojo"]["token"], "token-" + name)
                os.unlink(os.path.join(self.spool.start_dir, f))
                self.sup[name] = {"state": state, "started": self.clock(), "since": since or self.clock()}
        for f in os.listdir(self.spool.stop_dir):
            os.unlink(os.path.join(self.spool.stop_dir, f))
            if self.sup.get(f, {}).get("state") in ("starting", "idle"):
                self.sup[f]["state"] = "removed"
        self.write_state()

    def write_state(self):
        with open(os.path.join(self.tmp.name, "state.json"), "w") as f:
            json.dump({"updated": self.clock(), "shim_ca": "ready", "runners": self.sup}, f)

    def pending(self):
        return sorted(self.spool.pending())

    def alive(self):
        return {n: s["state"] for n, s in self.sup.items() if s["state"] in c.ALIVE}


class TestConfig(unittest.TestCase):
    def test_max_from_students(self):
        self.assertEqual(c.Config({"STUDENT_COUNT": "10"}).max, 4)
        self.assertEqual(c.Config({"STUDENT_COUNT": "3"}).max, 2)
        self.assertEqual(c.Config({"STUDENT_COUNT": "100"}).max, 12)
        self.assertEqual(c.Config({"STUDENT_COUNT": "10", "RUNNER_MAX": "7"}).max, 7)

    def test_min_idle_capped_by_max(self):
        self.assertEqual(c.Config({"RUNNER_MIN_IDLE": "9", "RUNNER_MAX": "3"}).min_idle, 3)

    def test_runner_config(self):
        cfg = json.loads(c.runner_config("u", "t", ["host:host"], 900))
        self.assertEqual(cfg["runner"]["labels"], ["host:host"])
        self.assertEqual(cfg["runner"]["capacity"], 1)
        self.assertEqual(cfg["runner"]["timeout"], "900s")


class TestAuto(Base):
    def test_starts_warm_pool(self):
        self.ctl.tick()
        self.assertEqual(len(self.pending()), 2)
        self.ctl.tick()  # still pending: no more starts
        self.assertEqual(len(self.pending()), 2)
        self.supervise()
        self.ctl.tick()
        self.assertEqual(len(self.alive()), 2)
        self.assertEqual(self.pending(), [])

    def test_scales_up_per_waiting_job_to_max(self):
        self.ctl.tick(); self.supervise()
        self.fj.jobs = [{"id": i, "repo_id": i, "name": "ci", "status": "waiting"} for i in range(5)]
        self.ctl.tick()
        # 2 idle + 5 waiting wants 7, capped at max 4.
        self.assertEqual(len(self.pending()) + len(self.alive()), 4)
        self.assertEqual(len(self.ctl.snapshot["waiting"]), 5)

    def test_busy_runners_count_and_warm_pool_is_kept(self):
        self.ctl.tick(); self.supervise()
        for s in self.sup.values():
            s["state"] = "busy"
        self.write_state()
        self.ctl.tick()
        self.assertEqual(len(self.pending()), 2)  # 2 busy + 2 new idle = 4 = max

    def test_idle_above_minimum_removed_only_after_timeout(self):
        self.ctl.tick(); self.supervise()
        self.fj.jobs = [{"id": 1, "repo_id": 1, "name": "ci"}]
        self.ctl.tick(); self.supervise()
        self.assertEqual(len(self.alive()), 3)
        self.fj.jobs = []
        self.clock.t += 60
        self.ctl.tick()
        self.assertEqual(os.listdir(self.spool.stop_dir), [])
        self.clock.t += 61
        self.ctl.tick()
        self.assertEqual(len(os.listdir(self.spool.stop_dir)), 1)
        self.supervise()
        self.ctl.tick()
        self.assertEqual(len(self.alive()), 2)

    def test_never_removes_busy(self):
        self.cfg.max = 6
        self.ctl.min_idle = 0
        self.ctl.tick()
        self.sup = {f"pool-b{i}": {"state": "busy", "started": 0, "since": 0} for i in range(3)}
        self.write_state()
        self.clock.t += 10_000
        self.ctl.tick()
        self.assertEqual(os.listdir(self.spool.stop_dir), [])

    def test_pauses_after_repeated_failures(self):
        self.ctl.tick()
        self.supervise(state="failed")
        self.ctl.tick()  # 2 failures: still starting
        self.supervise(state="failed")
        self.ctl.tick()
        self.assertTrue(self.ctl.snapshot["paused"])
        self.assertEqual(self.pending(), [])
        self.assertEqual(len(self.ctl.snapshot["problems"]), 4)
        self.clock.t += c.FAIL_WINDOW + 1
        self.ctl.tick()
        self.assertEqual(len(self.pending()), 2)


class TestManual(Base):
    def test_does_nothing_by_itself(self):
        self.ctl.set_mode("manual")
        self.fj.jobs = [{"id": 1, "repo_id": 1, "name": "ci"}]
        self.ctl.tick()
        self.assertEqual(self.pending(), [])

    def test_plus_and_minus(self):
        self.ctl.set_mode("manual")
        ok, _ = self.ctl.scale(1)
        self.assertTrue(ok)
        self.assertEqual(len(self.pending()), 1)
        ok, msg = self.ctl.scale(-1)
        self.assertFalse(ok)  # still starting, not idle yet
        self.supervise()
        self.ctl.tick()
        ok, _ = self.ctl.scale(-1)
        self.assertTrue(ok)
        self.assertEqual(len(os.listdir(self.spool.stop_dir)), 1)

    def test_minus_never_takes_a_busy_runner(self):
        self.ctl.set_mode("manual")
        self.ctl.scale(1)
        self.supervise(state="busy")
        self.ctl.tick()
        ok, msg = self.ctl.scale(-1)
        self.assertFalse(ok)
        self.assertIn("busy", msg)

    def test_plus_stops_at_max(self):
        self.ctl.set_mode("manual")
        for _ in range(4):
            self.assertTrue(self.ctl.scale(1)[0])
        self.assertFalse(self.ctl.scale(1)[0])

    def test_auto_plus_minus_moves_min_idle(self):
        self.ctl.scale(1)
        self.assertEqual(self.ctl.min_idle, 3)
        for _ in range(9):
            self.ctl.scale(-1)
        self.assertEqual(self.ctl.min_idle, 0)
        for _ in range(9):
            self.ctl.scale(1)
        self.assertEqual(self.ctl.min_idle, 4)


class TestCleanupAndLights(Base):
    def test_finished_runner_registration_deleted(self):
        self.ctl.tick(); self.supervise()
        name = sorted(self.sup)[0]
        self.sup[name]["state"] = "done"
        self.write_state()
        self.ctl.tick()
        self.assertNotIn(name, self.fj.regs)

    def test_unknown_registration_deleted_after_grace_but_not_pending(self):
        self.ctl.set_mode("manual")
        self.fj.register("pool-stale")
        self.ctl.scale(1)  # pending, not yet picked up
        self.clock.t += c.GRACE + 1
        self.ctl.tick()
        self.assertNotIn("pool-stale", self.fj.regs)
        self.assertEqual(len(self.fj.regs), 1)  # the pending one stays

    def test_other_runners_left_alone(self):
        self.fj.regs["someone-else"] = {"id": 99, "name": "someone-else", "status": "idle"}
        self.clock.t += 1000
        self.ctl.tick()
        self.assertIn("someone-else", self.fj.regs)

    def test_lights(self):
        self.ctl.set_mode("manual")
        self.sup = {"pool-a": {"state": "idle", "started": 1000, "since": 1000},
                    "pool-b": {"state": "busy", "started": 1000, "since": 1000, "repo": "student01/x"},
                    "pool-c": {"state": "failed", "started": 1000, "since": 1000, "detail": "exited (1)"}}
        for n in self.sup:
            self.fj.regs[n] = {"id": len(self.fj.regs) + 1, "name": n, "status": "idle"}
        self.write_state()
        self.ctl.tick()
        lights = {r["name"]: r["light"] for r in self.ctl.snapshot["runners"]}
        self.assertEqual(lights, {"pool-a": "green", "pool-b": "yellow", "pool-c": "red"})
        # Stuck job, and a live runner Forgejo sees offline.
        self.fj.regs["pool-a"]["status"] = "offline"
        self.ctl.tick()
        self.clock.t += self.cfg.job_timeout + 1
        self.ctl.tick()
        rows = {r["name"]: r for r in self.ctl.snapshot["runners"]}
        self.assertEqual(rows["pool-a"]["light"], "red")
        self.assertEqual(rows["pool-b"]["light"], "red")
        self.assertIn("stuck", rows["pool-b"]["detail"])
        self.assertNotIn("pool-c", rows)  # an old failure leaves the table (it stays in problems)

    def test_forgejo_down_is_reported_not_raised(self):
        self.fj.down = True
        self.ctl.tick()
        self.assertIn("Forgejo", self.ctl.snapshot["error"])
        self.assertFalse(self.ctl.healthy())


class TestHTTP(Base):
    def setUp(self):
        super().setUp()
        self.srv = c.Server(("127.0.0.1", 0), c.make_handler(self.ctl))
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.ctl.tick()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        super().tearDown()

    def req(self, method, path, headers=None, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1], timeout=5)
        conn.request(method, path, body=body, headers=headers or {})
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        return resp.status, resp.headers, data

    FAC = {"X-Gateway-Token": TOKEN, "X-Auth-User": "root"}

    def test_healthz_needs_no_token(self):
        self.assertEqual(self.req("GET", "/healthz")[0], 200)

    def test_needs_token_and_facilitator(self):
        self.assertEqual(self.req("GET", "/api/state")[0], 403)
        self.assertEqual(self.req("GET", "/api/state", {"X-Auth-User": "root"})[0], 403)
        self.assertEqual(self.req("GET", "/api/state", {"X-Gateway-Token": "nope", "X-Auth-User": "root"})[0], 403)
        self.assertEqual(self.req("GET", "/api/state", {"X-Gateway-Token": TOKEN, "X-Auth-User": "student01"})[0], 403)
        status, headers, data = self.req("GET", "/api/state", self.FAC)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["mode"], "auto")

    def test_page_and_headers(self):
        for path in ("/", "/panel.js", "/panel.css"):
            status, headers, _ = self.req("GET", path, self.FAC)
            self.assertEqual(status, 200, path)
            self.assertIn("frame-ancestors 'self'", headers["Content-Security-Policy"])
            self.assertNotIn("unsafe-inline", headers["Content-Security-Policy"])

    def test_post_needs_csrf_header(self):
        body = json.dumps({"mode": "manual"})
        self.assertEqual(self.req("POST", "/api/mode", dict(self.FAC), body)[0], 403)
        self.assertEqual(self.ctl.mode, "auto")
        h = dict(self.FAC, **{"X-Requested-With": "dojo-runners", "Content-Type": "application/json"})
        status, _, data = self.req("POST", "/api/mode", h, body)
        self.assertEqual(status, 200)
        self.assertEqual(self.ctl.mode, "manual")
        self.assertEqual(self.req("POST", "/api/scale", h, json.dumps({"delta": 5}))[0], 400)
        self.assertEqual(self.req("POST", "/api/scale", h, "not json")[0], 400)
        status, _, data = self.req("POST", "/api/scale", h, json.dumps({"delta": -1}))
        self.assertEqual(status, 409)  # nothing idle to remove
        self.assertFalse(json.loads(data)["ok"])

    def test_student_cannot_post(self):
        h = {"X-Gateway-Token": TOKEN, "X-Auth-User": "student01", "X-Requested-With": "dojo-runners"}
        self.assertEqual(self.req("POST", "/api/scale", h, json.dumps({"delta": 1}))[0], 403)


if __name__ == "__main__":
    unittest.main()
