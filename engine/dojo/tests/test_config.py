"""dojo.toml / dojo.local.toml / .env layering, [profile] sections, and the one-time migration.
    python3 -B -m unittest discover -s engine/dojo/tests -t engine
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from dojo import config, envfiles, migrate, paths

NAMES = ("REPO", "ENGINE", "WORKSHOPS", "MODULES", "ENV_FILE", "CONFIG", "LOCAL_CONFIG", "LEGACY_ENV")


class Sandbox(unittest.TestCase):
    """paths.* pointed at a temp checkout holding one workshop `w`."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "engine").mkdir()
        (self.root / "modules").mkdir()
        (self.root / "workshops" / "w").mkdir(parents=True)
        (self.root / "workshops" / "w" / "workshop.env").write_text("WORKSHOP_TITLE=w\n")
        self.saved = {n: getattr(paths, n) for n in NAMES}
        paths.REPO, paths.ENGINE = self.root, self.root / "engine"
        paths.WORKSHOPS, paths.MODULES = self.root / "workshops", self.root / "modules"
        paths.ENV_FILE, paths.CONFIG = self.root / ".env", self.root / "dojo.toml"
        paths.LOCAL_CONFIG, paths.LEGACY_ENV = self.root / "dojo.local.toml", self.root / "engine" / ".env"

    def tearDown(self):
        for n, v in self.saved.items():
            setattr(paths, n, v)
        shutil.rmtree(self.root)

    def write(self, name, text):
        (self.root / name).write_text(text)

    def resolve(self, profiles=None):
        return envfiles.resolve("w", profiles, base={"PATH": os.environ["PATH"]})


class Layers(Sandbox):
    def test_later_layer_wins_and_names_its_source(self):
        self.write("dojo.toml", '[network]\npublic_base_url = "http://a"\n[terminal]\nflavor = "code-server"\n')
        self.write("dojo.local.toml", '[terminal]\nflavor = "zellij"\n')
        self.write(".env", "TTYD_PASSWORD=x\n")
        res = self.resolve()
        self.assertEqual(res.env["PUBLIC_BASE_URL"], "http://a")
        self.assertEqual(res.env["TERMINAL_FLAVOR"], "zellij")
        self.assertEqual(res.source_of("TERMINAL_FLAVOR"), "dojo.local.toml [terminal] flavor")

    def test_env_beats_toml_and_workshop_beats_both(self):
        self.write("dojo.toml", '[network]\nlab_host_ip = "1.1.1.1"\n')
        self.write(".env", "LAB_HOST_IP=2.2.2.2\nTTYD_PASSWORD=x\n")
        self.assertEqual(self.resolve().env["LAB_HOST_IP"], "2.2.2.2")
        self.write("workshops/w/workshop.env", "LAB_HOST_IP=3.3.3.3\n")
        self.assertEqual(self.resolve().env["LAB_HOST_IP"], "3.3.3.3")

    def test_flavor_names_and_types(self):
        self.write("dojo.toml", '[terminal]\nflavor = "code-server"\npids_limit = 99\n[general]\nachievements = false\n')
        self.write(".env", "")
        env = self.resolve().env
        self.assertEqual((env["TERMINAL_FLAVOR"], env["WEB_TERMINAL_PIDS_LIMIT"], env["ACHIEVEMENTS_ENABLED"]),
                         ("web", "99", "0"))

    def test_typos_are_errors(self):
        self.write(".env", "")
        for bad, hint in (('[terminal]\nflavour = "zellij"\n', "unknown setting"),
                          ('[terminl]\nflavor = "zellij"\n', "unknown section"),
                          ('[terminal]\nflavor = "vim"\n', "must be one of"),
                          ('[terminal]\npids_limit = "many"\n', "whole number")):
            self.write("dojo.toml", bad)
            with self.assertRaises(envfiles.EnvError, msg=bad) as cm:
                self.resolve()
            self.assertIn(hint, str(cm.exception))


class Profiles(Sandbox):
    def setUp(self):
        super().setUp()
        self.write("dojo.toml", '[network]\npublic_base_url = "http://localhost:8080"\n'
                                '[terminal]\nflavor = "zellij"\n'
                                '[profiles.mac.env]\nRUNNER = "mac"\n')
        self.write("dojo.local.toml", '[profiles.home.network]\npublic_base_url = "https://home"\n'
                                      'allow_default_passwords = true\n')
        self.write(".env", "TTYD_PASSWORD=shared\n\n[home]\nTTYD_PASSWORD=student\n")

    def test_profile_overrides_and_keeps_independent_flavor(self):
        res = self.resolve("home")
        self.assertEqual(res.env["PUBLIC_BASE_URL"], "https://home")
        self.assertEqual(res.env["ALLOW_DEFAULT_PASSWORDS"], "1")
        self.assertEqual(res.env["TTYD_PASSWORD"], "student")
        self.assertEqual(res.env["TERMINAL_FLAVOR"], "zellij")   # --env home does not touch the flavor

    def test_without_profile_the_section_is_ignored(self):
        res = self.resolve()
        self.assertEqual(res.env["TTYD_PASSWORD"], "shared")
        self.assertEqual(res.env["PUBLIC_BASE_URL"], "http://localhost:8080")

    def test_profiles_join_with_commas_last_wins(self):
        res = self.resolve("mac,home")
        self.assertEqual((res.env["RUNNER"], res.env["PUBLIC_BASE_URL"]), ("mac", "https://home"))

    def test_unknown_profile_is_an_error_listing_known(self):
        with self.assertRaises(envfiles.EnvError) as cm:
            self.resolve("nope")
        self.assertIn("home", str(cm.exception))

    def test_shared_env_rows_do_not_override_a_profile_after_it(self):
        self.write(".env", "PUBLIC_BASE_URL=http://shared\n[home]\nTTYD_PASSWORD=p\n")
        self.assertEqual(self.resolve("home").env["PUBLIC_BASE_URL"], "https://home")

    def test_operator_env_tolerates_a_deleted_profile(self):
        self.assertEqual(envfiles.operator_env("gone")["PUBLIC_BASE_URL"], "http://localhost:8080")


class SetValue(Sandbox):
    def test_writes_into_sections_and_round_trips(self):
        config.set_value("WEB_TERMINAL_MEM_LIMIT", "6g")
        config.set_value("WEB_TERMINAL_PIDS_LIMIT", "512")
        config.set_value("WEB_TERMINAL_MEM_LIMIT", "8g")           # replaces in place
        config.set_value("TERMINAL_FLAVOR", "web")
        config.set_value("PUBLIC_BASE_URL", "https://h", profile="home")
        config.set_value("SOMETHING_ELSE", "1")                    # unknown -> [env]
        rows = {k: v for k, v, _ in config.base_rows(paths.LOCAL_CONFIG)}
        self.assertEqual(rows, {"WEB_TERMINAL_MEM_LIMIT": "8g", "WEB_TERMINAL_PIDS_LIMIT": "512",
                                "TERMINAL_FLAVOR": "web", "SOMETHING_ELSE": "1"})
        self.assertEqual([k for k, *_ in config.profile_rows(paths.LOCAL_CONFIG, "home")], ["PUBLIC_BASE_URL"])
        self.assertIn('flavor = "code-server"', paths.LOCAL_CONFIG.read_text())


class Sections(unittest.TestCase):
    def test_parse_sections(self):
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as fh:
            fh.write("A=1\n# c\n[home]\nA=2\nB=3\n[live]\nA=4\n")
        p = Path(fh.name)
        try:
            self.assertEqual(envfiles.parse_literal(p, sections=True), [("A", "1", 1)])
            self.assertEqual([(k, v) for k, v, _ in envfiles.parse_literal(p, "home", sections=True)],
                             [("A", "1"), ("A", "2"), ("B", "3")])
            self.assertEqual(envfiles.env_sections(p), ["home", "live"])
        finally:
            p.unlink()


class Migration(Sandbox):
    def test_old_layout_moves_secrets_and_settings(self):
        self.write("dojo.toml", '[network]\npublic_base_url = "http://localhost:8080"\n')
        self.write("engine/.env", "PUBLIC_BASE_URL=http://localhost:8080\nSTUDENT_COUNT=7\nTERMINAL_FLAVOR=zellij\n"
                                  "TTYD_PASSWORD=pw$1\nSTUDENT_PASSWORD_SEED=seed\n")
        self.write("engine/.env.home", "PUBLIC_BASE_URL=https://h\nALLOW_DEFAULT_PASSWORDS=1\nTTYD_PASSWORD=student\n"
                                       "STUDENT_PASSWORD_SEED=seed\n")
        self.assertTrue(migrate.needed())
        migrate.migrate()
        self.assertFalse(migrate.needed())
        self.assertEqual(oct(paths.ENV_FILE.stat().st_mode & 0o777), "0o600")
        before = {"TTYD_PASSWORD": "student", "ALLOW_DEFAULT_PASSWORDS": "1", "PUBLIC_BASE_URL": "https://h",
                  "STUDENT_COUNT": "7", "TERMINAL_FLAVOR": "zellij", "STUDENT_PASSWORD_SEED": "seed"}
        got = self.resolve("home").env
        self.assertEqual({k: got[k] for k in before}, before)
        plain = self.resolve().env
        self.assertEqual((plain["TTYD_PASSWORD"], plain["PUBLIC_BASE_URL"]), ("pw$1", "http://localhost:8080"))
        self.assertEqual(paths.ENV_FILE.read_text().count("STUDENT_PASSWORD_SEED"), 1)   # not repeated in [home]
        self.assertTrue((self.root / "engine" / ".env.migrated").is_file())
        self.assertNotIn("PUBLIC_BASE_URL", paths.LOCAL_CONFIG.read_text().split("[profiles")[0])  # equal to default


if __name__ == "__main__":
    unittest.main()
