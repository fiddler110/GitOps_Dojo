"""Unit tests for the dojo CLI's pure logic. Standard library only:
    python3 -B -m unittest discover -s engine/dojo/tests -t engine
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from dojo import checks, envfiles, paths
from dojo.runtime import classify

TRICKY = "\n".join([
    "# comment", "", "A=pa$$word", "B=two words", 'C="Git Training Lab"', "D='single $quoted'",
    "E=plain # trailing comment", "export F=exported", "G=has#hash", "H=it's", "I=`whoami`",
    "J=", "K=crlf\r", "  L=indented", "not a setting", "9X=bad key",
]) + "\n"
EXPECTED = {"A": "pa$$word", "B": "two words", "C": "Git Training Lab", "D": "single $quoted",
            "E": "plain", "F": "exported", "G": "has#hash", "H": "it's", "I": "`whoami`",
            "J": "", "K": "crlf", "L": "indented"}


class LiteralEnv(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False)
        self.tmp.write(TRICKY)
        self.tmp.close()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_python_parser(self):
        got = {k: v for k, v, _ in envfiles.parse_literal(Path(self.tmp.name))}
        self.assertEqual(got, EXPECTED)

    def test_shell_loader_agrees(self):
        """engine/scripts/lib.sh's dojo_load_env reads the same file the same way."""
        script = ('. ./scripts/lib.sh; dojo_load_env "$1"; for k in ' + " ".join(EXPECTED)
                  + '; do eval "printf \'%s=%s\\0\' $k \\"\\${$k-UNSET}\\""; done')
        out = subprocess.run(["sh", "-c", script, "sh", self.tmp.name], cwd=str(paths.ENGINE),
                             capture_output=True, text=True, check=True).stdout
        got = dict(item.split("=", 1) for item in out.split("\0") if item)
        self.assertEqual(got, EXPECTED)


class AchievementsToggle(unittest.TestCase):
    """ACHIEVEMENTS_ENABLED in the shell beats engine/.env; without it, the file decides."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "workshops" / "w" / "achievements").mkdir(parents=True)
        (self.root / "workshops" / "w" / "workshop.env").write_text("WORKSHOP_TITLE=w\n")
        (self.root / "workshops" / "w" / "achievements" / "catalog.json").write_text("{}")
        (self.root / "modules" / "achievements").mkdir(parents=True)
        (self.root / ".env").write_text("ACHIEVEMENTS_ENABLED=1\n")
        self.saved = (paths.WORKSHOPS, paths.MODULES, paths.ENV_FILE)
        paths.WORKSHOPS, paths.MODULES, paths.ENV_FILE = (
            self.root / "workshops", self.root / "modules", self.root / ".env")

    def tearDown(self):
        paths.WORKSHOPS, paths.MODULES, paths.ENV_FILE = self.saved
        import shutil
        shutil.rmtree(self.root)

    def resolve(self, base):
        return envfiles.resolve("w", base={"PATH": os.environ["PATH"], **base})

    def test_file_decides_without_shell_value(self):
        self.assertEqual(self.resolve({}).modules, ["achievements"])

    def test_shell_value_wins(self):
        res = self.resolve({"ACHIEVEMENTS_ENABLED": "0"})
        self.assertEqual(res.modules, [])
        self.assertEqual(res.env["ACHIEVEMENTS_ENABLED"], "0")
        self.assertEqual(res.origins["ACHIEVEMENTS_ENABLED"][-1].source, "environment")


class SharedFacts(unittest.TestCase):
    def test_default_passwords_match_lib_sh(self):
        lib = (paths.ENGINE / "scripts" / "lib.sh").read_text()
        block = lib.split("dojo_is_default_password()", 1)[1].split(")", 2)[0]
        shell = {w.strip() for w in block.split("case \"$1\" in", 1)[1].split("|")}
        self.assertEqual(shell, set(checks.DEFAULT_PASSWORDS))


class Checks(unittest.TestCase):
    def test_url_parts(self):
        self.assertEqual(checks.url_parts("http://localhost:8080/x"), ("http", "localhost", "8080"))
        self.assertEqual(checks.url_parts("https://dojo.example.ca"), ("https", "dojo.example.ca", None))
        self.assertEqual(checks.url_parts("http://[::1]:8080"), ("http", "::1", "8080"))

    def test_port_mismatch(self):
        self.assertIsNone(checks.port_mismatch({"PUBLIC_BASE_URL": "http://localhost:8080"}))
        self.assertIn("port 80", checks.port_mismatch({"PUBLIC_BASE_URL": "http://localhost"}))
        # Behind a TLS proxy the gateway's own listen address is what must match.
        self.assertIsNone(checks.port_mismatch({"PUBLIC_BASE_URL": "https://dojo.example.ca",
                                                "GATEWAY_LISTEN": "http://:8080"}))

    def test_local_only_and_defaults(self):
        env = {"PUBLIC_BASE_URL": "http://localhost:8080", "LAB_HOST_IP": "127.0.0.1",
               "TTYD_PASSWORD": "student", "STUDENT_PASSWORD_SEED": "x" * 64,
               "FACILITATOR_PASSWORD": "s3cret", "FORGEJO_ADMIN_PASSWORD": "admin"}
        self.assertTrue(checks.local_only(env))
        self.assertEqual(checks.default_passwords(env), ["TTYD_PASSWORD", "FORGEJO_ADMIN_PASSWORD"])
        self.assertFalse(checks.local_only({**env, "LAB_HOST_IP": "0.0.0.0"}))
        self.assertTrue(checks.plain_http_offbox({"PUBLIC_BASE_URL": "http://10.0.0.5:8080"}))


class Classify(unittest.TestCase):
    def test_states(self):
        cases = {"Up 3 minutes (healthy)": "healthy", "Up 2 seconds (starting)": "starting",
                 "Up 1 minute (health: starting)": "starting", "Up 5 minutes": "running",
                 "Exited (0) 2 minutes ago": "done", "Exited (1) 1 second ago": "failed",
                 "Created": "waiting", "Up 9 minutes (unhealthy)": "unhealthy"}
        for status, state in cases.items():
            self.assertEqual(classify(status), state, status)


class WslPath(unittest.TestCase):
    """Runtime drops Windows /mnt/* folders from PATH for podman, only on WSL."""

    def runtime_path(self, wsl: bool) -> str:
        from unittest import mock
        from dojo import runtime
        path = "/usr/bin:/mnt/c/Windows:/mnt/data/bin"
        with mock.patch.dict(os.environ, {"PATH": path}), \
                mock.patch.object(runtime.shutil, "which", return_value="/usr/bin/x"), \
                mock.patch.object(runtime, "on_wsl", return_value=wsl):
            runtime.Runtime()
            return os.environ["PATH"]

    def test_wsl_drops_mnt(self):
        self.assertEqual(self.runtime_path(True), "/usr/bin")

    def test_elsewhere_keeps_mnt(self):
        self.assertEqual(self.runtime_path(False), "/usr/bin:/mnt/c/Windows:/mnt/data/bin")


if __name__ == "__main__":
    unittest.main()
