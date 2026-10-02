"""Unit tests for the pool supervisor (RV17), no stack or root needed:

    python3 -B -m unittest discover -s modules/runner-pool/tests -p 'test_*.py'

The spool is a temporary folder shared with the controller's own Spool class,
so the start/stop files and state.json are checked from both sides of the
handoff. useradd, su and forgejo-runner are faked.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SPOOL = tempfile.mkdtemp(prefix="spool-")
os.environ["SPOOL_DIR"] = SPOOL
sys.path.insert(0, os.path.join(HERE, "..", "pool"))
sys.path.insert(0, os.path.join(HERE, "..", "controller"))
import controller as c  # noqa: E402
import supervise as s  # noqa: E402


def tearDownModule():
    shutil.rmtree(SPOOL, ignore_errors=True)


class FakeProc:
    """forgejo-runner one-job: prints `lines`, then exits with `rc`."""

    def __init__(self, lines=(), rc=0):
        self.stdout = iter(line + "\n" for line in lines)
        self.rc = rc

    def wait(self):
        return self.rc


class SupervisorTest(unittest.TestCase):
    def setUp(self):
        self.spool = c.Spool(SPOOL)    # the controller's side, which also makes start/ and stop/
        for d in (s.START_DIR, s.STOP_DIR):
            for e in os.listdir(d):
                os.unlink(os.path.join(d, e))
        s.runners.clear()
        self.addCleanup(s.runners.clear)
        self.removed = []
        p = mock.patch.object(s, "remove_user", side_effect=lambda n: self.removed.append(n) or "")
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch.object(s, "log")
        p.start()
        self.addCleanup(p.stop)
        p = mock.patch.object(s, "print", create=True)     # watch() echoes the runner's output
        p.start()
        self.addCleanup(p.stop)

    def runner(self, name="pool-a1", lines=(), rc=0, stop=False):
        r = s.Runner(name)
        r.proc = FakeProc(lines, rc)
        r.stop_requested = stop
        s.runners[name] = r
        return r


class Handoff(SupervisorTest):
    def test_controller_files_are_taken_and_junk_removed(self):
        self.spool.write_start("pool-a1", "config")
        self.spool.write_stop("pool-b2")
        for junk in ("evil.yaml", "pool-UPPER.yaml", "../x"):
            open(os.path.join(s.START_DIR, os.path.basename(junk)), "w").close()
        open(os.path.join(s.START_DIR, ".pool-c3.yaml.tmp"), "w").close()   # mid-write
        self.assertEqual(s.take_files(s.START_DIR), [("pool-a1", os.path.join(s.START_DIR, "pool-a1.yaml"))])
        self.assertEqual(sorted(os.listdir(s.START_DIR)), [".pool-c3.yaml.tmp", "pool-a1.yaml"])
        self.assertEqual([n for n, _ in s.take_files(s.STOP_DIR)], ["pool-b2"])
        self.assertEqual(s.take_files(os.path.join(SPOOL, "missing")), [])

    def test_state_json_is_what_the_controller_reads(self):
        r = self.runner("pool-a1")
        self.runner("pool-b2").proc = None      # useradd still running: no process yet
        s.write_state(ca_ready=False)
        doc = self.spool.read_state()
        self.assertEqual(doc["shim_ca"], "waiting")
        self.assertEqual({n: x["state"] for n, x in doc["runners"].items()},
                         {"pool-a1": "starting", "pool-b2": "starting"})
        self.assertFalse(os.path.exists(s.STATE_FILE + ".tmp"))
        r.started -= s.IDLE_AFTER
        s.runners["pool-b2"].started -= s.IDLE_AFTER
        s.write_state(ca_ready=True)
        doc = self.spool.read_state()
        self.assertEqual(doc["shim_ca"], "ready")
        self.assertEqual({n: x["state"] for n, x in doc["runners"].items()},
                         {"pool-a1": "idle", "pool-b2": "starting"})   # idle only with a process
        self.assertEqual(set(doc["runners"]["pool-a1"]),
                         {"state", "repo", "task", "started", "since", "exit", "detail"})

    def test_finished_runners_are_kept_for_a_while_then_dropped(self):
        for name, state in (("pool-a1", "done"), ("pool-b2", "failed"), ("pool-c3", "removed"), ("pool-d4", "busy")):
            r = self.runner(name)
            r.state, r.since = state, time.time() - s.KEEP_FINISHED - 1
        self.runner("pool-e5").state = "done"
        s.write_state(True)
        self.assertEqual(sorted(self.spool.read_state()["runners"]), ["pool-d4", "pool-e5"])


class Lifecycle(SupervisorTest):
    def test_job_taken_then_done(self):
        r = self.runner(lines=["Runner registered", "task 42 repo is student01/dns-zone", "job done"], rc=0)
        s.watch(r)
        self.assertEqual((r.state, r.task, r.repo, r.exit), ("done", 42, "student01/dns-zone", 0))
        self.assertEqual(self.removed, ["pool-a1"])

    def test_cancelled_job_exit_code_is_not_a_failure(self):
        r = self.runner(lines=["task 7 repo is a/b"], rc=1)
        s.watch(r)
        self.assertEqual(r.state, "done")

    def test_exit_before_a_job_is_a_failure_with_the_last_line(self):
        r = self.runner(lines=["starting", "cannot reach git-server", ""], rc=1)
        s.watch(r)
        self.assertEqual(r.state, "failed")
        self.assertIn("exited (1) before taking a job: cannot reach git-server", r.detail)

    def test_stopped_idle_runner_is_removed(self):
        r = self.runner(stop=True, rc=137)
        s.watch(r)
        self.assertEqual(r.state, "removed")

    def test_cleanup_error_fails_it(self):
        r = self.runner(lines=["task 1 repo is a/b"])
        with mock.patch.object(s, "remove_user", return_value="userdel: busy"):
            s.watch(r)
        self.assertEqual((r.state, r.detail), ("failed", "userdel: busy"))

    def test_start_runs_the_runner_as_its_own_user(self):
        with mock.patch.object(s, "create_user") as create, \
                mock.patch.object(s.subprocess, "Popen", return_value=FakeProc()) as popen, \
                mock.patch.object(s.threading, "Thread") as thread:
            s.start("pool-a1", "config")
        create.assert_called_once_with("pool-a1", "config")
        args = popen.call_args[0][0]
        self.assertEqual(args[:2], ["su", "pool-a1"])
        self.assertIn("unshare -U --map-current-user -p -f --mount-proc", args[-1])
        self.assertIn("umask 077", args[-1])
        self.assertEqual(popen.call_args[1]["env"], s.CLEAN_ENV)
        self.assertEqual(s.runners["pool-a1"].state, "starting")
        thread.return_value.start.assert_called_once()

    def test_failed_start_cleans_up(self):
        with mock.patch.object(s, "create_user", side_effect=RuntimeError("useradd: exists")):
            s.start("pool-a1", "config")
        r = s.runners["pool-a1"]
        self.assertEqual(r.state, "failed")
        self.assertIn("useradd: exists", r.detail)
        self.assertEqual(self.removed, ["pool-a1"])


class Stop(SupervisorTest):
    def test_stops_only_idle_or_starting_runners(self):
        idle, busy, starting = self.runner("pool-a1"), self.runner("pool-b2"), self.runner("pool-c3")
        idle.state, busy.state = "idle", "busy"
        nostart = self.runner("pool-d4")
        nostart.proc = None
        with mock.patch.object(s, "run") as run:
            for name in ("pool-a1", "pool-b2", "pool-c3", "pool-d4", "pool-zz"):
                s.stop(name)
        self.assertEqual([call[0][0][1] for call in run.call_args_list], ["pool-a1", "pool-c3"])
        self.assertEqual([r.stop_requested for r in (idle, busy, starting, nostart)], [True, False, True, False])


class RemoveUser(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def remove(self, userdel_rc):
        pw = mock.Mock(pw_uid=os.getuid())
        done = subprocess.CompletedProcess([], userdel_rc, stdout="userdel: user busy\n")
        with mock.patch.object(s.pwd, "getpwnam", return_value=pw), \
                mock.patch.object(s, "TEMP_DIRS", (self.tmp, os.path.join(self.tmp, "missing"))), \
                mock.patch.object(s, "run", return_value=done) as run:
            return s.remove_user("pool-a1"), run

    def test_kills_deletes_its_temp_files_and_the_user(self):
        os.mkdir(os.path.join(self.tmp, "build"))
        open(os.path.join(self.tmp, "build", "f"), "w").close()
        open(os.path.join(self.tmp, "sock"), "w").close()
        err, run = self.remove(0)
        self.assertEqual(err, "")
        self.assertEqual(os.listdir(self.tmp), [])
        self.assertEqual([a[0][0][0] for a in run.call_args_list], ["su", "userdel"])

    def test_home_already_gone_is_fine_other_errors_are_reported(self):
        self.assertEqual(self.remove(12)[0], "")
        self.assertEqual(self.remove(8)[0], "userdel: userdel: user busy")

    def test_unknown_user_is_nothing_to_do(self):
        with mock.patch.object(s.pwd, "getpwnam", side_effect=KeyError), mock.patch.object(s, "run") as run:
            self.assertEqual(s.remove_user("pool-a1"), "")
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
