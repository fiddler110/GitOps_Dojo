"""Unit tests for the start/stop helpers that need no container engine.
    python3 -B -m unittest discover -s engine/dojo/tests -t engine
(Rich and Click are imported by these modules: run with engine/.cache/pylib-*
on PYTHONPATH, or through boot.py once.)
"""
import json
import os
import unittest
from unittest import mock

from dojo import start, state
from dojo.monitor import clean_log_line
from dojo.start import BOTS_GO, StartOptions, StartError, bot_count, soc_time_scale, parse_recorded, release_bots
from dojo.runtime import Container, Runtime
from dojo.stop import _volumes_in_config


class Recorded(unittest.TestCase):
    def test_round_trip(self):
        for flags in ([], ["--test"], ["--test", "14"], ["--env", "home"],
                      ["--test", "3", "--env", "home", "--allow-default-passwords"],
                      ["--test", "--fast"], ["--test", "3", "--fast"],
                      ["--terminal", "zellij"], ["--env", "home", "--terminal", "code-server"]):
            o = parse_recorded(["dns-as-code", *flags])
            self.assertEqual(o.workshop, "dns-as-code")
            self.assertEqual(o.flags, flags, flags)

    def test_equals_forms(self):
        o = parse_recorded(["x", "--test=5", "--env=home"])
        self.assertEqual((o.test, o.env_name), ("5", "home"))

    def test_time_scale(self):
        self.assertIsNone(soc_time_scale(StartOptions("x"), {}))
        self.assertEqual(soc_time_scale(StartOptions("x", test=""), {}), "0.1")
        self.assertEqual(soc_time_scale(StartOptions("x", test="5", fast=True), {"CTF_TIME_SCALE": ""}), "0.1")
        self.assertEqual(soc_time_scale(StartOptions("x", test=""), {"CTF_TIME_SCALE": "1"}), "1")
        self.assertEqual(soc_time_scale(StartOptions("x", test=""), {"CTF_TIME_SCALE": "0.25"}), "0.25")

    def test_bot_count(self):
        self.assertIsNone(bot_count(StartOptions("x"), {}))
        self.assertEqual(bot_count(StartOptions("x", test=""), {}), "3")
        self.assertEqual(bot_count(StartOptions("x", test=""), {"BOT_COUNT": "7"}), "7")
        self.assertEqual(bot_count(StartOptions("x", test="08"), {}), "8")  # not octal
        for bad in ("0", "36", "abc"):
            with self.assertRaises(StartError):
                bot_count(StartOptions("x", test=bad), {})

    def test_fast_needs_test(self):
        self.assertEqual(bot_count(StartOptions("x", test="", fast=True), {}), "3")
        with self.assertRaises(StartError):
            bot_count(StartOptions("x", fast=True), {})


class ReleaseBots(unittest.TestCase):
    def test_touches_the_go_file_in_the_terminal(self):
        calls = []

        class Rt:
            def run(self, *args):
                calls.append(args)
                return type("R", (), {"returncode": 0})()

        release_bots(Rt())
        self.assertEqual(calls, [("exec", "workshop_terminal", "touch", BOTS_GO)])


class LogLines(unittest.TestCase):
    def test_cleaning(self):
        self.assertEqual(clean_log_line('{"level":"info","ts":1.5,"logger":"admin.api","msg":"received request"}\n'),
                         "info: received request")
        self.assertEqual(clean_log_line("2026/10/01 16:57:23 ...eb/routing/logger.go:109:func1() [I] router: done"),
                         "[I] router: done")
        self.assertEqual(clean_log_line("2026-10-01T16:57:23.123Z starting thing"), "starting thing")
        self.assertEqual(clean_log_line("\x1b[32mgreen\x1b[0m text\x07"), "green text")
        self.assertEqual(len(clean_log_line("x" * 1000)), 240)
        self.assertEqual(clean_log_line("[2026-10-01 17:46:08 +0000] [13] [INFO] Booting worker with pid: 13"),
                         "[INFO] Booting worker with pid: 13")


class ComposeConfig(unittest.TestCase):
    def test_top_level_volumes(self):
        cfg = "\n".join(["services:", "  web:", "    volumes:", "      - data:/data", "volumes:",
                         "  forgejo_data:", "    name: engine_forgejo_data", "  terminal_home: {}",
                         "  runner_config:", "networks:", "  lab:"])
        self.assertEqual(_volumes_in_config(cfg), ["forgejo_data", "terminal_home", "runner_config"])


class Dependents(unittest.TestCase):
    """restart SERVICE also recreates what podman links to it (podman won't remove a container others need)."""
    def runtime(self, cli, deps):
        rt = Runtime.__new__(Runtime)
        rt.cli, rt._oneshot = cli, {}
        ids = {svc: f"{i:02d}" * 32 for i, svc in enumerate(deps, 1)}
        rows = [Container(svc, f"c_{svc}", "Up", ids[svc][:12]) for svc in deps]
        lines = "\n".join(f"{ids[s]}|{json.dumps([ids[d] for d in deps[s]] or None)}" for s in deps)
        rt.out = lambda *a, **k: lines
        return rt, rows

    def test_transitive_and_podman_only(self):
        deps = {"dns-server": [], "step-ca": ["dns-server"], "web-terminal": ["step-ca", "dns-server"],
                "site-inspector": ["step-ca"], "sensei": ["web-terminal"], "gateway": []}
        rt, rows = self.runtime("podman", deps)
        self.assertEqual(rt.dependents(rows, ["step-ca"]), ["sensei", "site-inspector", "web-terminal"])
        self.assertEqual(rt.dependents(rows, ["gateway"]), [])
        self.assertEqual(rt.dependents(rows, ["step-ca", "web-terminal"]), ["sensei", "site-inspector"])
        rt.cli = "docker"
        self.assertEqual(rt.dependents(rows, ["step-ca"]), [])


class StaleContainers(unittest.TestCase):
    """A rebuild keeps the tag, so podman-compose's `up -d` keeps the old container
    (and the superseded image it holds); dojo finds and recreates those."""

    def runtime(self, cli, rows, inspect, tags):
        rt = Runtime.__new__(Runtime)
        rt.cli, rt._oneshot = cli, {}
        self.calls = []

        def out(*a, **k):
            self.calls.append(a)
            if a[:2] == ("image", "inspect"):
                return tags.get(a[-1], "") + "\n"
            return "\n".join(inspect)
        rt.out = out
        return rt

    def test_podman_finds_only_rebuilt_running_containers(self):
        rows = [Container("web-terminal", "t", "Up 1 minute (healthy)", "aa" * 6),
                Container("gateway", "g", "Up 1 minute (healthy)", "bb" * 6),
                Container("bootstrap", "b", "Exited (0) 1 minute ago", "cc" * 6)]
        inspect = ["aa" * 32 + "|old1|localhost/gitopsdojo/web-terminal:x",
                   "bb" * 32 + "|same|localhost/gitopsdojo/gateway:local"]
        tags = {"localhost/gitopsdojo/web-terminal:x": "new1", "localhost/gitopsdojo/gateway:local": "same"}
        rt = self.runtime("podman", rows, inspect, tags)
        self.assertEqual(rt.stale_services(rows), ["web-terminal"])
        self.assertNotIn("cc" * 6, self.calls[0])                 # an exited one-shot isn't asked about
        self.assertIn("{{.ImageName}}", self.calls[0][2])

    def test_docker_ids_compare_without_prefix_and_missing_tag_is_not_stale(self):
        rows = [Container("allocator", "a", "Up 2 minutes", "dd" * 6),
                Container("sensei", "s", "Up 2 minutes", "ee" * 6)]
        inspect = ["dd" * 32 + "|sha256:abc|gitopsdojo/allocator:local", "ee" * 32 + "|sha256:def|gone:tag"]
        rt = self.runtime("docker", rows, inspect, {"gitopsdojo/allocator:local": "sha256:abc"})
        self.assertEqual(rt.stale_services(rows), [])
        self.assertIn("{{.Config.Image}}", self.calls[0][2])

    def plan(self, recreate=None, stale=(), also=()):
        rt = mock.Mock(spec=Runtime)
        rt.compose_cmd = ["podman-compose"]
        rt.stale_services.return_value = list(stale)
        rt.dependents.return_value = list(also)
        res = mock.Mock(env={})
        return start.Plan(StartOptions("x", recreate=recreate), rt, res, "engine", [], ["a.yml"], [], "")

    def recreate(self, p):
        mon = mock.Mock()
        with mock.patch.object(start.subprocess, "Popen") as popen:
            popen.return_value.wait.return_value = 0
            rc = start._recreate_stale(p, mon, None)
        return rc, popen, mon

    def test_rebuilt_services_and_their_dependents_are_recreated(self):
        rc, popen, mon = self.recreate(self.plan(stale=["web-terminal"], also=["sensei"]))
        self.assertEqual(rc, 0)
        args = popen.call_args[0][0]
        self.assertEqual(args[-5:], ["-d", "--force-recreate", "--no-deps", "web-terminal", "sensei"])
        self.assertIn("web-terminal", mon.note.call_args[0][1])

    def test_nothing_stale_or_a_restart_runs_nothing(self):
        for p in (self.plan(), self.plan(recreate=[], stale=["gateway"]), self.plan(recreate=["gateway"], stale=["x"])):
            rc, popen, mon = self.recreate(p)
            self.assertEqual(rc, 0)
            popen.assert_not_called()
            mon.note.assert_not_called()


class RestartKeepsAchievements(unittest.TestCase):
    """restart repeats whether the running start had the achievements module (the environment switches it)."""
    def restart(self, files, environ):
        cur = state.Current("cert-autorenewal", [], files, None)
        seen = {}
        with mock.patch.object(state, "last_start", return_value=["cert-autorenewal"]), \
                mock.patch.object(state, "read_current", return_value=cur), \
                mock.patch.object(start, "run_start", side_effect=lambda o: seen.update(
                    on=os.environ.get("ACHIEVEMENTS_ENABLED"), recreate=o.recreate) or 0), \
                mock.patch.dict(os.environ, environ, clear=False):
            os.environ.pop("ACHIEVEMENTS_ENABLED", None) if "ACHIEVEMENTS_ENABLED" not in environ else None
            start.run_restart(["step-ca"], clean=False)
        return seen

    def test_repeats_the_running_start(self):
        on = ["../modules/sensei/compose.yml", "../modules/achievements/compose.yml", "../workshops/x/o.yml"]
        self.assertEqual(self.restart(on, {}), {"on": "1", "recreate": ["step-ca"]})
        self.assertEqual(self.restart(on[:1], {})["on"], "0")
        self.assertEqual(self.restart(on, {"ACHIEVEMENTS_ENABLED": "0"})["on"], "0")   # this shell decides


class RunningStackGate(unittest.TestCase):
    """Step 2 of a start: what may start over a running stack, and restart's service names."""
    def check(self, o, running, cur, svcs=("gateway", "step-ca"), files=("a.yml",)):
        rt = mock.Mock(spec=Runtime)
        rt.containers.return_value = running
        p = start.Plan(o, rt, mock.Mock(), "engine", [], list(files), [], "")
        p._services.extend(svcs)
        with mock.patch.object(state, "read_current", return_value=cur):
            start._check_running(p)
        return p

    up = [Container("gateway", "c_gateway", "Up", "01")]

    def test_same_run_or_nothing_running_passes(self):
        self.check(StartOptions("x"), [], None)
        self.check(StartOptions("x"), self.up, state.Current("x", [], ["a.yml"], None))
        self.check(StartOptions("y", build_only=True), self.up, None)   # a build doesn't touch the stack

    def test_generated_image_override_does_not_change_stack_identity(self):
        cur = state.Current("x", [], ["a.yml", ".generated/image-tags/x.yml"], None)
        with mock.patch.object(start, "bad") as bad:
            self.check(StartOptions("x", dry_run=True), self.up, cur,
                       files=("a.yml", ".generated/dry-run/image-tags/x.yml"))
        bad.assert_not_called()

    def test_refuses_another_stack_or_other_files(self):
        for cur in (None, state.Current("y", [], ["a.yml"], None), state.Current("x", [], ["b.yml"], None)):
            with self.assertRaises(StartError):
                self.check(StartOptions("x"), self.up, cur)
        with mock.patch.object(start, "console"), mock.patch.object(start, "bad") as bad:
            self.check(StartOptions("x", dry_run=True), self.up, None)  # a dry run only says so
        bad.assert_called_once()

    def test_restart_names(self):
        cur = state.Current("x", [], ["a.yml"], None)
        self.check(StartOptions("x", recreate=["step-ca"]), self.up, cur)
        with self.assertRaisesRegex(StartError, "not a service"):
            self.check(StartOptions("x", recreate=["nope"]), self.up, cur)
        with self.assertRaisesRegex(StartError, "isn't running"):
            self.check(StartOptions("x", recreate=["step-ca"]), [], None)


class UpArgs(unittest.TestCase):
    def args(self, recreate, also=()):
        rt = mock.Mock(spec=Runtime)
        rt.dependents.return_value = list(also)
        res = mock.Mock(env={})
        p = start.Plan(StartOptions("x", recreate=recreate), rt, res, "engine", [], [], [], "")
        with mock.patch.object(start, "step"), mock.patch.object(start, "console"):
            return start._up_args(p)

    def test_start_restart_and_one_service(self):
        self.assertEqual(self.args(None), [])
        self.assertEqual(self.args([]), ["--force-recreate"])
        self.assertEqual(self.args(["step-ca"], ["sensei"]), ["--force-recreate", "--no-deps", "step-ca", "sensei"])


class OverlayWorkdirs(unittest.TestCase):
    """ctf-host's cache wipe needs the host to undo overlayfs's mode-000 work/work dirs."""

    def test_locked_workdirs_are_opened_and_the_tree_is_removable(self):
        import shutil
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "ctf-docker"
            snaps = cache / "containerd/daemon/io.containerd.snapshotter.v1.overlayfs/snapshots"
            locked = [snaps / "9/work/work", cache / "overlay2/abc/work/work"]
            for d in locked:
                d.mkdir(parents=True)
                d.chmod(0)
            (snaps / "10/fs").mkdir(parents=True)          # an ordinary dir: left alone
            self.assertEqual(start.unlock_overlay_workdirs(cache), 2)
            for d in locked:
                self.assertEqual(d.stat().st_mode & 0o700, 0o700)
            self.assertEqual(start.unlock_overlay_workdirs(cache), 0)   # nothing left to do
            shutil.rmtree(cache)                            # what ctf-host's wipe needs to succeed
            self.assertFalse(cache.exists())

    def test_missing_cache_is_fine(self):
        from pathlib import Path
        self.assertEqual(start.unlock_overlay_workdirs(Path("/nonexistent/ctf-docker")), 0)


class Mountpoints(unittest.TestCase):
    """slides/assets exists before compose up (Docker can't create it inside the read-only slides mount)."""

    def test_made_once_and_only_with_slides(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            content = Path(tmp)
            start.make_mountpoints(content)  # no slides/: nothing to mount, nothing made
            self.assertEqual(list(content.iterdir()), [])
            (content / "slides").mkdir()
            start.make_mountpoints(content)
            start.make_mountpoints(content)
            self.assertTrue((content / "slides" / "assets").is_dir())


if __name__ == "__main__":
    unittest.main()
