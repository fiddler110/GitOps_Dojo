import unittest

import docker_api
import policy


class TemplateTests(unittest.TestCase):
    def spec(self, **over):
        args = dict(image="dojo/hello:1.0", env_pairs=[("MESSAGE", "hi")], host_port=20001,
                    cpu=0.25, memory_gb=0.125, labels={"dojo.owner": "student01"})
        args.update(over)
        return docker_api.build_create_request(**args)

    def test_hardened_defaults(self):
        hc = self.spec()["HostConfig"]
        self.assertFalse(hc["Privileged"])
        self.assertEqual(hc["CapDrop"], ["ALL"])
        self.assertIn("no-new-privileges", hc["SecurityOpt"])
        self.assertEqual(hc["Memory"], 128 * 1024 * 1024)
        for forbidden in ("Binds", "Mounts", "Devices", "NetworkMode", "PidMode", "IpcMode",
                          "UsernsMode", "CapAdd", "Links", "ExtraHosts"):
            self.assertNotIn(forbidden, hc)

    def test_only_expected_top_level_keys(self):
        self.assertEqual(set(self.spec()), {"Image", "Env", "Labels", "ExposedPorts", "HostConfig"})

    def test_caps_are_clamped(self):
        s = self.spec(cpu=64, memory_gb=512)
        self.assertEqual(s["HostConfig"]["NanoCpus"], int(policy.MAX_CPU * 1e9))
        self.assertEqual(s["HostConfig"]["Memory"], int(policy.MAX_MEMORY_GB * 1024 ** 3))

    def test_image_allow_list_enforced_even_if_policy_bypassed(self):
        with self.assertRaises(docker_api.DockerError):
            self.spec(image="alpine:latest")
        with self.assertRaises(docker_api.DockerError):
            self.spec(image="dojo/hello:1.0 --privileged")

    def test_label_cannot_unmark_managed(self):
        self.assertEqual(self.spec(labels={"dojo.managed": "false"})["Labels"]["dojo.managed"], "true")

    def test_port_is_a_number_only(self):
        self.assertEqual(self.spec(host_port="20005")["HostConfig"]["PortBindings"]["80/tcp"][0]["HostPort"], "20005")
        with self.assertRaises(ValueError):
            self.spec(host_port="1; rm -rf /")


if __name__ == "__main__":
    unittest.main()
