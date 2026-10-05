"""Unit tests for the executor's fixed-template spec and image allow-list:

    python3 -B -m unittest discover -s modules/ctf-range/ctf-controller/tests -p 'test_*.py'

No daemon needed — build_create_request and allowed_image are pure functions.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import docker_api as d  # noqa: E402


class TestAllowedImage(unittest.TestCase):
    def test_base_always_allowed(self):
        self.assertTrue(d.allowed_image("ctf-customer-portal:base", ""))
        self.assertTrue(d.allowed_image("ctf-customer-portal:base", "registry.ctf.internal"))

    def test_registry_prefix_allowed(self):
        self.assertTrue(d.allowed_image("registry.ctf.internal/ctf-customer-portal:student01",
                                        "registry.ctf.internal"))

    def test_foreign_images_refused(self):
        for img in ("python:3.12-slim", "evil/backdoor:latest",
                    "registry.ctf.internal.attacker.com/x:1", "ctf-customer-portal:latest"):
            self.assertFalse(d.allowed_image(img, "registry.ctf.internal"), img)

    def test_no_registry_only_base(self):
        self.assertFalse(d.allowed_image("registry.ctf.internal/x:1", ""))


class TestCreateRequest(unittest.TestCase):
    def setUp(self):
        self.spec = d.build_create_request(
            image="ctf-customer-portal:base",
            env_pairs=[("CTF_STUDENT", "student01"), ("CTF_FLAG", "flag{x}"), ("PORT", "5000")],
            container_port=5000, host_port=15000,
            memory_bytes=128 * 1024 ** 2, pids_limit=256,
            labels={d.LABEL_SLOT: "student01", d.LABEL_USER: "student01"})

    def test_hardening(self):
        hc = self.spec["HostConfig"]
        self.assertEqual(hc["CapDrop"], ["ALL"])
        self.assertIn("no-new-privileges", hc["SecurityOpt"])
        self.assertTrue(hc["ReadonlyRootfs"])
        self.assertFalse(hc["Privileged"])
        self.assertEqual(hc["PidsLimit"], 256)
        self.assertEqual(hc["Memory"], hc["MemorySwap"])  # no swap beyond the limit

    def test_only_tmpfs_is_writable(self):
        # read-only root + exactly the two ephemeral paths the app writes.
        self.assertEqual(set(self.spec["HostConfig"]["Tmpfs"]), {"/tmp", "/data"})
        # No bind mounts, ever.
        self.assertNotIn("Binds", self.spec["HostConfig"])
        self.assertNotIn("Mounts", self.spec)

    def test_port_published(self):
        self.assertEqual(self.spec["ExposedPorts"], {"5000/tcp": {}})
        self.assertEqual(self.spec["HostConfig"]["PortBindings"],
                         {"5000/tcp": [{"HostPort": "15000"}]})

    def test_labels_mark_managed(self):
        self.assertEqual(self.spec["Labels"][d.LABEL_MANAGED], "true")
        self.assertEqual(self.spec["Labels"][d.LABEL_IMAGE], "ctf-customer-portal:base")
        self.assertEqual(self.spec["Labels"][d.LABEL_SLOT], "student01")

    def test_env_passthrough(self):
        self.assertIn("CTF_FLAG=flag{x}", self.spec["Env"])
        self.assertIn("CTF_STUDENT=student01", self.spec["Env"])


if __name__ == "__main__":
    unittest.main()
