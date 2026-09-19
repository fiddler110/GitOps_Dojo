"""Guards the one piece of logic duplicated across two images: the terminal
broker (terminal/dojo-broker.py) and the control plane (cloud-api/auth.py) must
derive identical ids and secrets. Run from this directory:
    python3 -m unittest test_parity
"""
import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "cloud-api"))


def load(name, path):
    spec = importlib.util.spec_from_loader(name, importlib.machinery.SourceFileLoader(name, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


import importlib.machinery  # noqa: E402

auth = load("cloud_auth", os.path.join(HERE, "cloud-api", "auth.py"))
broker = load("dojo_broker", os.path.join(HERE, "terminal", "dojo-broker.py"))


class Parity(unittest.TestCase):
    def test_same_derivations(self):
        key = b"0123456789abcdef" * 2
        for user in ("student01", "testuser03", "admin"):
            self.assertEqual(auth.app_id(user), broker.app_id(user))
            self.assertEqual(auth.subscription_id(user), broker.subscription_id(user))
            self.assertEqual(auth.client_secret(key, user), broker.client_secret(key, user))
        self.assertEqual(auth.TENANT_ID, broker.TENANT_ID)

    def test_same_roster(self):
        env = {"STUDENT_PREFIX": "s", "STUDENT_COUNT": "4", "BOT_PREFIX": "b", "BOT_COUNT": "2",
               "FACILITATOR_USERNAME": "fac"}
        self.assertEqual(auth.roster(env), broker.roster(env))

    def test_broker_secret_verifies_in_control_plane(self):
        key = b"k" * 32
        a = auth.Auth(key, ["student01"], "", "iss")
        creds = broker.credentials_for("student01", key, {"PUBLIC_BASE_URL": "http://x"})
        self.assertEqual(a.authenticate_client(creds["ARM_CLIENT_ID"], creds["ARM_CLIENT_SECRET"]), "student01")
        self.assertEqual(creds["ARM_SUBSCRIPTION_ID"], auth.subscription_id("student01"))


if __name__ == "__main__":
    unittest.main()
