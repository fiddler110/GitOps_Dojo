"""Known-answer test for the per-student password helper (remediation D13):
the allocator's dojo_secret.py, the terminal's copy and the shell twin in
engine/git-server/dojo-secret.sh must all give the same answers. Run in the
allocator image with the whole engine/ mounted, so the other two are found:

  podman run --rm --network none -v ./engine:/src:ro -w /src/allocator \
    gitopsdojo/allocator:local python3 -B -m unittest discover -s tests -v
"""

import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(HERE, ".."))
import dojo_secret  # noqa: E402

# (seed, label, name) -> expected. The seeds cover a key exactly one HMAC
# block long (env-setup.sh's 64 hex characters), a longer one (hashed
# first) and a short one (zero-padded).
KNOWN = [
    ("0f" * 32, "forgejo", "student07", "TRLNIHJNNOAWA2IL"),
    ("x" * 100, "forgejo", "student07", "ZB7MZZ4YEWE4XD27"),
    ("short", "forgejo", "student07", "RUOJJYZPKZ4ECVV6"),
]


class DojoSecretTest(unittest.TestCase):
    def test_known_answers(self):
        for seed, label, name, want in KNOWN:
            self.assertEqual(dojo_secret.derive(seed, label, name), want)

    def test_per_student(self):
        seed = "0f" * 32
        self.assertNotEqual(dojo_secret.derive(seed, "forgejo", "student01"),
                            dojo_secret.derive(seed, "forgejo", "student02"))
        self.assertNotEqual(dojo_secret.derive(seed, "forgejo", "student01"),
                            dojo_secret.derive(seed, "dns", "student01"))

    def test_fallback_without_seed(self):
        env = {"STUDENT_PASSWORD": "shared"}
        self.assertEqual(dojo_secret.forgejo_password("student01", env), "shared")
        self.assertEqual(dojo_secret.forgejo_password("student01", {}), dojo_secret.FALLBACK_PASSWORD)
        env = {"STUDENT_PASSWORD": "shared", "STUDENT_PASSWORD_SEED": "0f" * 32}
        self.assertEqual(dojo_secret.forgejo_password("student07", env), "TRLNIHJNNOAWA2IL")

    def test_terminal_copy_is_identical(self):
        other = os.path.join(ENGINE, "web-terminal", "dojo_secret.py")
        if not os.path.exists(other):
            self.skipTest("engine/web-terminal not mounted")
        with open(os.path.join(HERE, "..", "dojo_secret.py"), "rb") as a, open(other, "rb") as b:
            self.assertEqual(a.read(), b.read(), "copy allocator/dojo_secret.py to web-terminal/")

    def test_shell_twin(self):
        script = os.path.join(ENGINE, "git-server", "dojo-secret.sh")
        if not os.path.exists(script):
            self.skipTest("engine/git-server not mounted")
        if not (shutil.which("xxd") and shutil.which("sha256sum")):
            self.skipTest("no xxd/sha256sum here")
        for seed, label, name, want in KNOWN:
            out = subprocess.run(
                ["sh", "-c", '. "$1"; dojo_derive "$(cat)" "$2" "$3"', "sh", script, label, name],
                input=seed, capture_output=True, text=True, check=True).stdout.strip()
            self.assertEqual(out, want, seed)
        out = subprocess.run(["sh", "-c", '. "$1"; forgejo_password student01', "sh", script],
                             env={"PATH": os.environ["PATH"], "STUDENT_PASSWORD": "shared"},
                             capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(out, "shared")


if __name__ == "__main__":
    unittest.main()
