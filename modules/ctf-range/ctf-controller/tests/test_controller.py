"""Unit tests for the controller's reconcile / redeploy logic and HTTP control
API (no daemon needed):

    python3 -B -m unittest discover -s modules/ctf-range/ctf-controller/tests -p 'test_*.py'

A FakeExecutor stands in for ctf-host; it enforces the same image allow-list as
the real executor so the controller↔executor contract is exercised.
"""
import http.client
import json
import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import controller as c  # noqa: E402
import docker_api  # noqa: E402

TOKEN = "ctl-secret"


class FakeExecutor:
    def __init__(self, registry_prefix="registry.ctf.internal"):
        self.registry_prefix = registry_prefix
        self.containers = {}   # name -> {"state","image"}
        self.images = {"ctf-customer-portal:base"}
        self.up = True
        self.creates = []      # (name, image) history

    def ping(self):
        return self.up

    def image_present(self, image):
        return image in self.images

    def pull(self, image):
        if not docker_api.allowed_image(image, self.registry_prefix):
            raise docker_api.DockerError(f"image {image!r} is not allowed")
        self.images.add(image)

    def create(self, name, image, env_pairs, container_port, host_port,
               memory_bytes, pids_limit, labels):
        if not docker_api.allowed_image(image, self.registry_prefix):
            raise docker_api.DockerError(f"image {image!r} is not allowed")
        self.containers[name] = {"state": "running", "image": image, "env": dict(env_pairs)}
        self.creates.append((name, image))

    def remove(self, name):
        self.containers.pop(name, None)
        return True

    def state(self, name):
        info = self.containers.get(name)
        return info["state"] if info else None

    def image_of(self, name):
        info = self.containers.get(name)
        return info["image"] if info else None

    def list_managed(self):
        return list(self.containers)


def make_controller(count=2, seed="s", registry="registry.ctf.internal"):
    env = {"STUDENT_COUNT": str(count), "STUDENT_PREFIX": "student",
           "STUDENT_PASSWORD_SEED": seed, "CTF_REGISTRY": registry,
           "CTF_CONTROL_TOKEN": TOKEN, "CTF_TARGET_MEM_LIMIT": "128m"}
    cfg = c.Config(env=env)
    ex = FakeExecutor(registry_prefix=registry)
    return c.Controller(cfg, ex), cfg, ex


class TestConfig(unittest.TestCase):
    def test_mem_bytes(self):
        self.assertEqual(c._mem_bytes("128m"), 128 * 1024 ** 2)
        self.assertEqual(c._mem_bytes("1g"), 1024 ** 3)
        self.assertEqual(c._mem_bytes("536870912"), 536870912)
        self.assertEqual(c._mem_bytes("garbage"), 128 * 1024 ** 2)

    def test_roster_padding(self):
        _, cfg, _ = make_controller(count=3)
        self.assertEqual(cfg.users, ["student01", "student02", "student03"])

    def test_stable_name_and_port(self):
        _, cfg, _ = make_controller(count=2)
        self.assertEqual(cfg.slot_name("student01"), "ctf-customer-portal-student01")
        # Port is a pure function of the user's index, so it survives recreate.
        self.assertEqual(cfg.host_port("student01"), c.HOST_PORT_BASE)
        self.assertEqual(cfg.host_port("student02"), c.HOST_PORT_BASE + 1)


class TestReconcile(unittest.TestCase):
    def test_creates_one_slot_per_student(self):
        ctl, cfg, ex = make_controller(count=2)
        ctl.reconcile()
        self.assertEqual(set(ex.containers),
                         {"ctf-customer-portal-student01", "ctf-customer-portal-student02"})
        for info in ex.containers.values():
            self.assertEqual(info["image"], "ctf-customer-portal:base")
            self.assertEqual(info["state"], "running")

    def test_flag_injected_and_per_user(self):
        ctl, cfg, ex = make_controller(count=2, seed="s")
        ctl.reconcile()
        f1 = ex.containers["ctf-customer-portal-student01"]["env"]["CTF_FLAG"]
        f2 = ex.containers["ctf-customer-portal-student02"]["env"]["CTF_FLAG"]
        self.assertTrue(f1.startswith("flag{customer-portal-"))
        self.assertNotEqual(f1, f2)

    def test_running_slot_left_untouched(self):
        ctl, cfg, ex = make_controller(count=1)
        ctl.reconcile()
        ex.creates.clear()
        ctl.reconcile()  # second pass must not recreate a running slot
        self.assertEqual(ex.creates, [])

    def test_never_downgrades_a_patched_slot(self):
        ctl, cfg, ex = make_controller(count=1)
        patched = "registry.ctf.internal/ctf-customer-portal:student01"
        ok, _ = ctl.redeploy("student01", patched)
        self.assertTrue(ok)
        # A reconcile while it's running keeps the patched image.
        ctl.reconcile()
        self.assertEqual(ex.image_of("ctf-customer-portal-student01"), patched)
        # If the patched slot stops, it comes back patched, not base.
        ex.containers["ctf-customer-portal-student01"]["state"] = "stopped"
        ctl.reconcile()
        self.assertEqual(ex.image_of("ctf-customer-portal-student01"), patched)
        self.assertEqual(ex.state("ctf-customer-portal-student01"), "running")


class TestRedeploy(unittest.TestCase):
    def test_unknown_user_refused(self):
        ctl, _, _ = make_controller(count=1)
        ok, msg = ctl.redeploy("student99")
        self.assertFalse(ok)
        self.assertIn("unknown", msg)

    def test_base_requires_present_image(self):
        ctl, cfg, ex = make_controller(count=1)
        ex.images.discard("ctf-customer-portal:base")
        ok, msg = ctl.redeploy("student01")  # defaults to base
        self.assertFalse(ok)
        self.assertIn("not present", msg)

    def test_registry_tag_pulled_then_deployed(self):
        ctl, cfg, ex = make_controller(count=1)
        ctl.reconcile()
        tag = "registry.ctf.internal/ctf-customer-portal:student01"
        ok, msg = ctl.redeploy("student01", tag)
        self.assertTrue(ok, msg)
        self.assertIn(tag, ex.images)                       # pulled
        self.assertEqual(ex.image_of("ctf-customer-portal-student01"), tag)  # recreated in place

    def test_disallowed_image_refused(self):
        ctl, _, _ = make_controller(count=1)
        ok, msg = ctl.redeploy("student01", "evil/backdoor:latest")
        self.assertFalse(ok)
        self.assertIn("not allowed", msg)


class TestHTTP(unittest.TestCase):
    def setUp(self):
        self.ctl, self.cfg, self.ex = make_controller(count=1)
        self.ctl.tick()  # populate snapshot + last_ok
        self.srv = c.Server(("127.0.0.1", 0), c.make_handler(self.ctl))
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def _req(self, method, path, token=None, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {}
        if token:
            headers["Authorization"] = "Bearer " + token
        payload = json.dumps(body).encode() if body is not None else None
        if payload:
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=payload, headers=headers)
        resp = conn.getresponse()
        out = (resp.status, json.loads(resp.read() or b"{}"))
        conn.close()
        return out

    def test_healthz_open(self):
        status, doc = self._req("GET", "/healthz")
        self.assertEqual(status, 200)
        self.assertTrue(doc["ok"])

    def test_slots_requires_token(self):
        self.assertEqual(self._req("GET", "/slots")[0], 403)
        self.assertEqual(self._req("GET", "/slots", token="wrong")[0], 403)
        status, doc = self._req("GET", "/slots", token=TOKEN)
        self.assertEqual(status, 200)
        self.assertEqual(len(doc["slots"]), 1)

    def test_redeploy_requires_token(self):
        self.assertEqual(self._req("POST", "/redeploy", body={"user": "student01"})[0], 403)

    def test_redeploy_via_http(self):
        tag = "registry.ctf.internal/ctf-customer-portal:student01"
        status, doc = self._req("POST", "/redeploy", token=TOKEN,
                                body={"user": "student01", "image": tag})
        self.assertEqual(status, 200)
        self.assertTrue(doc["ok"])
        self.assertEqual(self.ex.image_of("ctf-customer-portal-student01"), tag)


if __name__ == "__main__":
    unittest.main()
