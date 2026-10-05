"""Unit tests for per-slot flag rendering (§5)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import flags  # noqa: E402

SEED = "range-wide-secret-seed"


class TestFlags(unittest.TestCase):
    def test_format(self):
        f = flags.render("student01", SEED)
        self.assertTrue(f.startswith("flag{customer-portal-"))
        self.assertTrue(f.endswith("}"))

    def test_deterministic_survives_recreate(self):
        # Same (seed, user) always yields the same value, so stop/start/redeploy
        # keep the flag (§4 "Flags and state").
        self.assertEqual(flags.render("student01", SEED), flags.render("student01", SEED))

    def test_per_user_unique(self):
        self.assertNotEqual(flags.render("student01", SEED), flags.render("student02", SEED))

    def test_depends_on_seed(self):
        self.assertNotEqual(flags.render("student01", SEED), flags.render("student01", "other-seed"))

    def test_dev_fallback_marked(self):
        f = flags.render("student01", "")
        self.assertIn("dev", f)
        self.assertIn("student01", f)

    def test_hmac_matches_spec(self):
        # flag{<challenge>-<HMAC-SHA256(seed, "ctf:<challenge>:<user>")[:16]>}
        import hashlib
        import hmac as _hmac
        want = _hmac.new(SEED.encode(), b"ctf:customer-portal:student01", hashlib.sha256).hexdigest()[:16]
        self.assertEqual(flags.render("student01", SEED), f"flag{{customer-portal-{want}}}")


if __name__ == "__main__":
    unittest.main()
