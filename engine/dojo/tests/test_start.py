"""Unit tests for the start/stop helpers that need no container engine.
    python3 -B -m unittest discover -s engine/dojo/tests -t engine
(Rich and Click are imported by these modules: run with engine/.cache/pylib-*
on PYTHONPATH, or through boot.py once.)
"""
import unittest

from dojo.monitor import clean_log_line
from dojo.start import StartOptions, StartError, bot_count, parse_recorded
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


if __name__ == "__main__":
    unittest.main()
