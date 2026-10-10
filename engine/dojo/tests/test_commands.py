"""Unit tests for the stack-tool commands (exec, urls, wait, logs, roster, reset-student, backup,
restore, export-results, prune, doctor --fix, validate, test, version). No container engine is
used: Runtime is a fake and `call` is patched.
    python3 -B -m unittest discover -s engine/dojo/tests -t engine
"""
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from click.testing import CliRunner

from dojo import backup, cli, logs, maintain, paths, results, stackapi, testrun, tools, validate
from dojo.runtime import Container
from dojo.stackapi import StackError


def C(service, status="Up 1 minute (healthy)", name=None):
    return Container(service, name or f"workshop_{service}", status, service[:6] + "id")


class FakeRt:
    cli = "podman"
    available = True

    def __init__(self, containers=(), volumes=(), runs=None):
        self._c, self._v, self.runs, self.calls = list(containers), list(volumes), runs or {}, []

    def containers(self, project):
        return self._c

    def volumes(self, project):
        return self._v

    def run(self, *args, **kw):
        self.calls.append(args)
        fn = self.runs.get(args[0] if args[0] != "volume" else "volume " + args[1])
        res = fn(*args) if fn else SimpleNamespace(returncode=0, stdout="", stderr="")
        return res

    def out(self, *args, **kw):
        return ""

    def version(self):
        return "5.0"

    def compose_version(self):
        return "c1"


class Sandbox(unittest.TestCase):
    """Point paths at a temp tree so no real state or pack is touched."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.saved = {k: getattr(paths, k) for k in ("REPO", "WORKSHOPS", "MODULES", "ENV_FILE", "STATE")}
        paths.REPO, paths.WORKSHOPS, paths.MODULES = self.root, self.root / "workshops", self.root / "modules"
        paths.ENV_FILE, paths.STATE = self.root / ".env", self.root / "state"
        paths.WORKSHOPS.mkdir()
        paths.MODULES.mkdir()
        self.patches = [mock.patch("dojo.stackapi.project", return_value="engine"),
                        mock.patch("dojo.state.read_current", return_value=None)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        for k, v in self.saved.items():
            setattr(paths, k, v)
        shutil.rmtree(self.root)


class ExecAndTools(Sandbox):
    def test_exec_argv_default_shell_and_command(self):
        rt = FakeRt([C("web-terminal")])
        with mock.patch("dojo.stackapi.project", return_value="engine"):
            argv = tools.exec_argv(rt, "web-terminal", [], tty=True)
            self.assertEqual(argv[:5], ["podman", "exec", "-i", "-t", "workshop_web-terminal"])
            self.assertIn("exec bash", argv[-1])
            self.assertEqual(tools.exec_argv(rt, "web-terminal", ["ls", "-l"], tty=False)[-2:], ["ls", "-l"])

    def test_exec_refuses_missing_and_waiting(self):
        with self.assertRaises(StackError):
            tools.exec_argv(FakeRt([]), "nope", [])
        with self.assertRaises(StackError):
            tools.exec_argv(FakeRt([C("x", "Created")]), "x", [])

    def test_urls_from_operator_env(self):
        env = {"PUBLIC_BASE_URL": "https://dojo.example/", "FACILITATOR_PASSWORD": "Zx9-long-secret", "TTYD_PASSWORD": "student"}
        with mock.patch("dojo.tools.operator_env", return_value=env):
            u = tools.urls()
        self.assertEqual((u["student"], u["admin"], u["slides"]), ("https://dojo.example/", "https://dojo.example/admin", "https://dojo.example/slides/"))
        self.assertEqual(u["logins"]["class"]["password"], "student")                 # public default: shown
        self.assertNotIn("secret", u["logins"]["facilitator"]["password"])             # real secret: only its length

    def test_urls_needs_address(self):
        with mock.patch("dojo.tools.operator_env", return_value={}):
            with self.assertRaises(StackError):
                tools.urls()

    def test_wait_ready_success_and_timeout(self):
        t = [0.0]
        clock, sleep = (lambda: t[0]), (lambda s: t.__setitem__(0, t[0] + s))
        rt = FakeRt([C("a"), C("b", "Up 1 minute (health: starting)")])

        def flip(_):
            rt._c[1] = C("b")
        res = tools.wait_ready(rt, 60, clock=clock, sleep=lambda s: (flip(s), sleep(s)))
        self.assertTrue(res["ok"])
        rt2 = FakeRt([C("a", "Up 1 minute (unhealthy)")])
        res = tools.wait_ready(rt2, 5, clock=clock, sleep=sleep)
        self.assertFalse(res["ok"])
        self.assertEqual(res["not_ready"], [("a", "unhealthy")])
        self.assertFalse(tools.wait_ready(FakeRt([]), 3, clock=clock, sleep=sleep)["ok"])

    def test_version_info_shape(self):
        info = tools.version_info(FakeRt())
        self.assertEqual({"git", "python", "engine", "engine_version", "compose", "wheels"}, set(info))
        self.assertTrue(any(w["name"] == "click" for w in info["wheels"]))


class Logs(unittest.TestCase):
    def test_fetch_parses_and_sorts(self):
        out = "2026-10-09T10:00:02.5+00:00 second\n2026-10-09T10:00:01.0+00:00 first\nno stamp"
        rt = FakeRt(runs={"logs": lambda *a: SimpleNamespace(returncode=0, stdout=out, stderr="")})
        rows = logs.fetch(rt, C("x"), "50", "5m")
        self.assertEqual([l for _, l in rows], ["no stamp", "first", "second"])
        args = rt.calls[0]
        self.assertIn("--since", args)
        self.assertIn("50", args)

    def test_merge_grep_and_errors(self):
        data = {"a": [("2", "Traceback (most recent call last)"), ("4", "fine")], "b": [("1", "x ERROR y"), ("3", "ok")],
                "c": [("5", "all quiet")]}
        m = logs.merged(data)
        self.assertEqual([r[0] for r in m], ["b", "a", "b", "a", "c"])
        self.assertEqual(len(logs.grep_filter(m, "ERROR|fine")), 2)
        found = logs.scan_errors(data)
        self.assertEqual(set(found), {"a", "b"})
        self.assertEqual(found["a"]["count"], 1)


class Admin(Sandbox):
    def test_roster_and_reset_outcomes(self):
        rows = [{"studentId": "s1", "name": "Amy", "ip": "1.2.3.4", "active": True, "reset": {"state": "running"}}]
        with mock.patch("dojo.results.call", return_value=(200, rows)):
            self.assertEqual(results.roster(FakeRt())[0]["studentId"], "s1")
        with mock.patch("dojo.results.call", return_value=(500, {})):
            with self.assertRaises(StackError):
                results.roster(FakeRt())
        for status, word in ((202, "queued"), (404, "No such"), (409, "already running"), (403, "refused")):
            with mock.patch("dojo.results.call", return_value=(status, {"error": "e"})) as c:
                try:
                    msg = results.reset_student(FakeRt(), "s1")
                except StackError as exc:
                    msg = str(exc)
                self.assertIn(word, msg)
        self.assertEqual(c.call_args.kwargs["form"]["confirm"], "s1")

    def test_render_csv_and_json(self):
        doc = {"students": [{"rank": 1, "user": "amy", "name": "Amy", "score": 90, "percent": 50, "complete": False,
                             "unlocks": 3, "cheats": [], "moments": ["First blood", "Ace"]}]}
        csv_text = results.render(doc, "csv").splitlines()
        self.assertEqual(csv_text[0], ",".join(results.CSV_COLUMNS))
        self.assertTrue(csv_text[1].startswith("1,amy,Amy,90,50,False,3,,First blood;Ace"))
        self.assertEqual(json.loads(results.render(doc, "json"))["students"][0]["user"], "amy")

    def test_export_fails_clearly_without_module(self):
        with self.assertRaises(StackError) as cm:
            results.fetch_results(FakeRt([C("allocator")]))
        self.assertIn("achievements module is not running", str(cm.exception))

    def test_fetch_results_merges_state_and_soc(self):
        answers = {"/achievements-admin/api/state": (200, {"students": [{"user": "a"}], "mttp": []}),
                   "/achievements-admin/api/soc": (200, {"rows": []})}
        with mock.patch("dojo.results.call", side_effect=lambda rt, svc, m, path, **k: answers[path]):
            out = results.fetch_results(FakeRt([C("achievements")]))
        self.assertEqual(out["students"], [{"user": "a"}])
        self.assertIn("soc", out)

    def test_call_runs_python_in_container_with_request_on_stdin(self):
        rt = FakeRt([C("allocator")])
        seen = {}

        def fake_run(argv, **kw):
            seen["argv"], seen["input"] = argv, kw["input"]
            return SimpleNamespace(returncode=0, stdout=json.dumps({"status": 200, "body": '{"a": 1}'}), stderr="")
        with mock.patch("subprocess.run", fake_run):
            status, doc = stackapi.call(rt, "allocator", "GET", "/x")
        self.assertEqual((status, doc), (200, {"a": 1}))
        self.assertEqual(seen["argv"][:4], ["podman", "exec", "-i", "workshop_allocator"])
        self.assertNotIn("TOKEN", " ".join(seen["argv"][4:]).replace("GATEWAY_TOKEN", ""))  # token is read inside, never passed
        self.assertEqual(json.loads(seen["input"])["path"], "/x")


class BackupRestore(Sandbox):
    def setUp(self):
        super().setUp()
        self.cwd = os.getcwd()
        os.chdir(self.root)

    def tearDown(self):
        os.chdir(self.cwd)
        super().tearDown()

    def fake_rt(self, containers=(), vols=("engine_forge", "engine_homes")):
        def export(*a):
            Path(a[a.index("--output") + 1]).write_bytes(b"data-" + a[2].encode())
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        def imp(*a):
            self.imported = getattr(self, "imported", []) + [(a[2], Path(a[3]).read_bytes())]
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return FakeRt(containers, vols, runs={"volume export": export, "volume import": imp})

    def test_round_trip_and_manifest(self):
        with mock.patch("dojo.state.last_start", return_value=["ctf-defend", "--test"]):
            rt = self.fake_rt()
            res = backup.backup(rt, self.root / "b.tar")
            m = backup.plan_restore(self.fake_rt(vols=()), Path(res["path"]))
            self.assertEqual(m["workshop"], "ctf-defend")   # nothing running: the last recorded start
            self.assertEqual(m["volumes"], ["engine_forge", "engine_homes"])
            rt2 = self.fake_rt(vols=())
            done = backup.restore(rt2, Path(res["path"]), m)
        self.assertEqual(done, ["engine_forge", "engine_homes"])
        self.assertEqual(self.imported[0], ("engine_forge", b"data-engine_forge"))
        self.assertIn(("volume", "create", "engine_forge"), rt2.calls)

    def test_backup_without_volumes_fails(self):
        with self.assertRaises(StackError):
            backup.backup(self.fake_rt(vols=()), self.root / "x.tar")

    def test_restore_refusals(self):
        with mock.patch("dojo.state.last_start", return_value=[]):
            rt = self.fake_rt()
            path = Path(backup.backup(rt, self.root / "b.tar")["path"])
            with self.assertRaises(StackError) as cm:
                backup.plan_restore(self.fake_rt(containers=[C("gateway")]), path)
            self.assertIn("stopped", str(cm.exception))
            with self.assertRaises(StackError):
                backup.plan_restore(self.fake_rt(), self.root / "missing.tar")
            (self.root / "junk.tar").write_bytes(b"not a tar")
            with self.assertRaises(StackError):
                backup.plan_restore(self.fake_rt(vols=()), self.root / "junk.tar")
        # a backup that names another workshop
        man = {"workshop": "dns-as-code", "project": "engine", "volumes": []}
        mp = self.root / "m.json"
        mp.write_text(json.dumps(man))
        with tarfile.open(self.root / "other.tar", "w") as t:
            t.add(mp, arcname="manifest.json")
        with mock.patch("dojo.state.last_start", return_value=["ctf-defend"]):
            with self.assertRaises(StackError) as cm:
                backup.plan_restore(self.fake_rt(vols=()), self.root / "other.tar")
            self.assertIn("another workshop" if False else "across workshops", str(cm.exception))

    def test_docker_is_refused(self):
        rt = self.fake_rt()
        rt.cli = "docker"
        with self.assertRaises(StackError):
            backup.backup(rt, self.root / "d.tar")


class Maintain(Sandbox):
    def test_prune_only_dangling_gitopsdojo_unused(self):
        rows = [{"Id": "a" * 64, "History": ["localhost/gitopsdojo/allocator:local"], "Containers": 0, "Size": 10},
                {"Id": "b" * 64, "History": ["localhost/gitopsdojo/web-terminal:base"], "Containers": 1, "Size": 10},
                {"Id": "c" * 64, "History": ["docker.io/library/other:tmp"], "Containers": 0, "Size": 10}]
        rt = FakeRt()
        rt.out = lambda *a, **k: json.dumps(rows)
        dry = maintain.prune(rt, True)
        self.assertEqual([i["id"] for i in dry["removed"]], ["a" * 12])
        self.assertEqual(rt.calls, [])                                    # dry run removes nothing
        maintain.prune(rt, False)
        self.assertEqual(rt.calls, [("image", "rm", "a" * 12)])           # never a volume, container or foreign image
        rt.cli = "docker"
        self.assertFalse(maintain.prune(rt, False)["supported"])

    def test_fix_stale_lock_and_env_mode(self):
        lock = self.root / "run.lock"       # never the real /tmp lock
        patcher = mock.patch("dojo.maintain._lock_dir", return_value=lock)
        patcher.start()
        self.addCleanup(patcher.stop)
        lock.mkdir()
        (lock / "pid").write_text("999999\n")
        self.assertIn("stale run lock", maintain.fix_stale_lock())
        self.assertFalse(lock.exists())
        lock.mkdir()
        (lock / "pid").write_text(f"{os.getpid()}\n")
        try:
            self.assertEqual(maintain.fix_stale_lock(), "")              # a live holder is left alone
        finally:
            (lock / "pid").unlink()
            lock.rmdir()
        paths.ENV_FILE.write_text("A=1\n")
        paths.ENV_FILE.chmod(0o644)
        self.assertIn("600", maintain.fix_env_mode())
        self.assertEqual(oct(paths.ENV_FILE.stat().st_mode & 0o777), "0o600")
        self.assertEqual(maintain.fix_env_mode(), "")

    def test_fix_missing_env_runs_setup_default(self):
        def fake(cmd, **kw):
            paths.ENV_FILE.write_text("A=1\n")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        with mock.patch("subprocess.run", fake):
            self.assertIn("created .env", maintain.fix_missing_env())
        self.assertEqual(maintain.fix_missing_env(), "")


class Validate(Sandbox):
    def pack(self, name, env="WORKSHOP_NAME=\"T\"\n", ext=None, mods=""):
        d = paths.WORKSHOPS / name
        d.mkdir()
        (d / "workshop.env").write_text(env + (f'MODULES="{mods}"\n' if mods else ""))
        if ext is not None:
            (d / "extensions.json").write_text(ext)
        return d

    def test_services_of(self):
        f = self.root / "c.yml"
        f.write_text("services:\n  a:\n    image: x\n  b-c:\n    image: y\nvolumes:\n  v: {}\n")
        self.assertEqual(validate._services_of(f), ["a", "b-c"])

    def problems(self, name):
        return {t: p for t, p in dict(validate.validate([name])[0][1]).items() if p}

    def test_good_pack(self):
        (paths.ENGINE / "docker-compose.yml").exists()
        self.pack("good")
        self.assertEqual(self.problems("good"), {})

    def test_bad_name_modules_and_env(self):
        self.pack("bad", env="NOPE=1\n", mods="ghost")
        probs = self.problems("bad")
        self.assertIn("workshop.env", probs)
        self.assertIn("modules", probs)
        self.assertIn("no such workshop", validate.validate(["absent"])[0][1][0][1][0])

    def test_extensions_json_invalid_and_rejected(self):
        self.pack("badjson", ext="{not json")
        self.assertIn("not valid JSON", self.problems("badjson")["extensions.json"][0])
        self.pack("badroute", ext=json.dumps({"version": 1, "routes": [{"id": "x", "path": "/git/x", "upstream": "nosuch:1", "gate": "shared"}]}))
        self.assertIn("extensions.json", self.problems("badroute"))

    def test_cli_exit_codes(self):
        self.pack("good")
        r = CliRunner().invoke(cli.cli, ["validate", "good"])
        self.assertEqual(r.exit_code, 0, r.output)
        r = CliRunner().invoke(cli.cli, ["validate", "absent"])
        self.assertEqual(r.exit_code, 1)


class TestRun(unittest.TestCase):
    def test_parse_matrix(self):
        self.assertEqual(testrun.parse_matrix("TERMINAL=a,b"), ("TERMINAL", ["a", "b"]))
        self.assertIsNone(testrun.parse_matrix(None))
        for bad in ("x", "=a", "K="):
            with self.assertRaises(ValueError):
                testrun.parse_matrix(bad)

    def run_it(self, matrix, start_rc=0, keep=False, done=3, boom=None):
        events, seen = [], []

        def start(w, n, env):
            events.append("start")
            seen.append(os.environ.get("KEY"))
            if boom:
                raise boom
            return start_rc
        with mock.patch("dojo.testrun.skipped_steps", return_value=["FAST: skipping it"]):
            res = testrun.run_matrix("w", 3, matrix, keep, 60, None, start, lambda: events.append("stop") or 0, FakeRt(),
                                     say=lambda *_: None, wait=lambda rt, bots, timeout, on_progress=None: done)
        return res, events, seen

    def test_pass_stops_and_env_is_exported_then_restored(self):
        res, events, seen = self.run_it(("KEY", ["a", "b"]))
        self.assertTrue(all(r.ok for r in res))
        self.assertEqual(events, ["start", "stop", "start", "stop"])
        self.assertEqual(seen, ["a", "b"])
        self.assertNotIn("KEY", os.environ)

    def test_keep_skips_last_stop_only(self):
        _, events, _ = self.run_it(("KEY", ["a", "b"]), keep=True)
        self.assertEqual(events, ["start", "stop", "start"])

    def test_failure_cases_still_stop(self):
        res, events, _ = self.run_it(None, done=1)
        self.assertFalse(res[0].ok)
        self.assertIn("timed out", res[0].note)
        self.assertEqual(events[-1], "stop")
        res, events, _ = self.run_it(None, start_rc=2)
        self.assertIn("start exited 2", res[0].note)
        self.assertEqual(events, ["start", "stop"])
        res, events, _ = self.run_it(None, boom=RuntimeError("x"))
        self.assertFalse(res[0].ok)
        self.assertEqual(events, ["start", "stop"])

    def test_ctrl_c_stops_then_reraises(self):
        events = []
        with self.assertRaises(KeyboardInterrupt):
            testrun.run_matrix("w", 3, None, False, 60, None, lambda *a: (_ for _ in ()).throw(KeyboardInterrupt()),
                               lambda: events.append("stop") or 0, FakeRt(), say=lambda *_: None)
        self.assertEqual(events, ["stop"])

    def test_wait_for_bots_polls_until_count(self):
        counts = iter([0, 1, 3])
        t = [0.0]
        with mock.patch("dojo.testrun.count_done", lambda rt: next(counts)):
            n = testrun.wait_for_bots(FakeRt(), 3, 600, clock=lambda: t[0], sleep=lambda s: t.__setitem__(0, t[0] + s))
        self.assertEqual(n, 3)


class CliSurface(unittest.TestCase):
    def test_every_new_command_has_help(self):
        for cmd in ("test", "exec", "shell", "urls", "open", "wait", "version", "roster", "reset-student", "backup",
                    "restore", "export-results", "doctor", "prune", "validate", "logs", "status", "list", "modules"):
            r = CliRunner().invoke(cli.cli, [cmd, "--help"])
            self.assertEqual(r.exit_code, 0, (cmd, r.output))

    def test_json_flags(self):
        r = CliRunner().invoke(cli.cli, ["list", "--json"])
        self.assertIsInstance(json.loads(r.output), list)
        r = CliRunner().invoke(cli.cli, ["modules", "--json"])
        self.assertTrue(any(m["name"] == "achievements" for m in json.loads(r.output)))

    def test_reset_student_asks_unless_yes(self):
        with mock.patch("dojo.results.reset_student", return_value="queued") as rs, mock.patch("dojo.cli.Runtime"):
            r = CliRunner().invoke(cli.cli, ["reset-student", "s1"], input="n\n")
            self.assertNotEqual(r.exit_code, 0)
            rs.assert_not_called()
            r = CliRunner().invoke(cli.cli, ["reset-student", "s1", "--yes"])
            self.assertEqual(r.exit_code, 0, r.output)
            rs.assert_called_once()

    def test_logs_errors_exit_code(self):
        rt = FakeRt([C("a")], runs={"logs": lambda *a: SimpleNamespace(returncode=0, stdout="2026-10-09T10:00:00Z Traceback boom\n", stderr="")})
        with mock.patch("dojo.cli.Runtime", return_value=rt), mock.patch("dojo.stackapi.project", return_value="engine"):
            r = CliRunner().invoke(cli.cli, ["logs", "--errors"])
        self.assertEqual(r.exit_code, 1, r.output)
        self.assertIn("Traceback boom", r.output)

    def test_wait_exit_codes(self):
        with mock.patch("dojo.tools.wait_ready", return_value={"ok": False, "waited": 1, "not_ready": [("a", "starting")]}):
            self.assertEqual(CliRunner().invoke(cli.cli, ["wait", "--timeout", "1"]).exit_code, 1)
        with mock.patch("dojo.tools.wait_ready", return_value={"ok": True, "waited": 1, "not_ready": []}):
            self.assertEqual(CliRunner().invoke(cli.cli, ["wait"]).exit_code, 0)

    def test_doctor_fix_lists_what_it_did(self):
        with mock.patch("dojo.maintain.apply_fixes", return_value=["removed the stale run lock"]), \
                mock.patch("dojo.doctor.run_checks", return_value=[]), mock.patch("dojo.cli.Runtime"):
            r = CliRunner().invoke(cli.cli, ["doctor", "--fix", "--json"])
        self.assertEqual(json.loads(r.output)["fixed"], ["removed the stale run lock"])
