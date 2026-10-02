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
from dojo.start import StartOptions, StartError, bot_count, parse_recorded
from dojo.runtime import Container, Runtime
from dojo.stop import _volumes_in_config


class Recorded(unittest.TestCase):
    def test_round_trip(self):
        for flags in ([], ["--test"], ["--test", "14"], ["--env", "home"],
                      ["--test", "3", "--env", "home", "--allow-default-passwords"]):
            o = parse_recorded(["dns-as-code", *flags])
            self.assertEqual(o.workshop, "dns-as-code")
            self.assertEqual(o.flags, flags, flags)

    def test_equals_forms(self):
        o = parse_recorded(["x", "--test=5", "--env=home"])
        self.assertEqual((o.test, o.env_name), ("5", "home"))

    def test_bot_count(self):
        self.assertIsNone(bot_count(StartOptions("x"), {}))
        self.assertEqual(bot_count(StartOptions("x", test=""), {}), "3")
        self.assertEqual(bot_count(StartOptions("x", test=""), {"BOT_COUNT": "7"}), "7")
        self.assertEqual(bot_count(StartOptions("x", test="08"), {}), "8")  # not octal
        for bad in ("0", "36", "abc"):
            with self.assertRaises(StartError):
                bot_count(StartOptions("x", test=bad), {})


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


if __name__ == "__main__":
    unittest.main()
