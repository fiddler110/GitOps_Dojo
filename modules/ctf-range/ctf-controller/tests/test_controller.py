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
    def __init__(self, registry_prefix="registry.ctf.internal", extra_images=()):
        self.registry_prefix = registry_prefix
        self.extra_images = frozenset(extra_images)
        self.containers = {}   # name -> {"state","image"}
        self.images = {"ctf-customer-portal:base"}
        self.up = True
        self.creates = []      # (name, image) history

    def ping(self):
        return self.up

    def image_present(self, image):
        return image in self.images

    def pull(self, image):
        if not docker_api.allowed_image(image, self.registry_prefix, self.extra_images):
            raise docker_api.DockerError(f"image {image!r} is not allowed")
        self.images.add(image)

    def create(self, name, image, env_pairs, ports,
               memory_bytes, pids_limit, labels):
        if not docker_api.allowed_image(image, self.registry_prefix, self.extra_images):
            raise docker_api.DockerError(f"image {image!r} is not allowed")
        self.containers[name] = {"state": "running", "image": image, "env": dict(env_pairs),
                                  "ports": list(ports)}
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


def make_attack(count=2, targets=None):
    env = {"STUDENT_COUNT": str(count), "STUDENT_PREFIX": "student",
           "CTF_ATTACK_MAX_CONCURRENT": "1"}
    cfg = c.Config(env=env)
    cfg.attack_targets = targets or {"ctf-1": "img-1", "ctf-2": "img-2"}
    ex = FakeExecutor(registry_prefix="registry.ctf.internal", extra_images=cfg.attack_targets.values())
    return c.AttackManager(cfg, ex), cfg, ex


class TestParseTargets(unittest.TestCase):
    def test_blank_is_empty(self):
        self.assertEqual(c.parse_targets(""), {})
        self.assertEqual(c.parse_targets(None), {})

    def test_pairs_in_order(self):
        self.assertEqual(c.parse_targets("ctf-1=img:a, ctf-2=img:b"),
                         {"ctf-1": "img:a", "ctf-2": "img:b"})

    def test_malformed_pair_skipped(self):
        self.assertEqual(c.parse_targets("ctf-1=img:a,garbage,=noid"), {"ctf-1": "img:a"})


class TestAttackManager(unittest.TestCase):
    def test_unknown_target_refused(self):
        atk, _, _ = make_attack()
        ok, msg = atk.start("student01", "no-such-target")
        self.assertFalse(ok)
        self.assertIn("unknown", msg)

    def test_start_queues_then_process_one_makes_it_live(self):
        atk, cfg, ex = make_attack()
        ok, msg = atk.start("student01", "ctf-1")
        self.assertTrue(ok, msg)
        self.assertEqual(atk.status("student01")["state"], "queued")
        self.assertTrue(atk.process_one())
        slot = atk.status("student01")
        self.assertEqual(slot["state"], "live")
        self.assertEqual(slot["target"], "ctf-1")
        self.assertEqual(ex.image_of(cfg.attack_slot_name("student01")), "img-1")

    def test_second_start_while_queued_refused_not_stacked(self):
        atk, _, _ = make_attack()
        atk.start("student01", "ctf-1")
        ok, msg = atk.start("student01", "ctf-2")
        self.assertFalse(ok)
        self.assertIn("queued", msg)
        self.assertEqual(atk.queue.count("student01"), 1)

    def test_queue_position_reported(self):
        atk, _, _ = make_attack()
        atk.start("student01", "ctf-1")
        atk.start("student02", "ctf-1")
        self.assertEqual(atk.status("student01")["queue_position"], 1)
        self.assertEqual(atk.status("student02")["queue_position"], 2)

    def test_max_concurrent_caps_processing(self):
        atk, cfg, _ = make_attack()  # CTF_ATTACK_MAX_CONCURRENT=1 above
        atk.start("student01", "ctf-1")
        atk.start("student02", "ctf-1")
        # One worker slot: draining must happen one job per process_one() call.
        self.assertTrue(atk.process_one())
        self.assertEqual(atk.status("student01")["state"], "live")
        self.assertEqual(atk.status("student02")["state"], "queued")
        self.assertTrue(atk.process_one())
        self.assertEqual(atk.status("student02")["state"], "live")

    def test_stop_cancels_a_queued_request(self):
        atk, _, _ = make_attack()
        atk.start("student01", "ctf-1")
        ok, msg = atk.stop("student01")
        self.assertTrue(ok, msg)
        self.assertEqual(atk.status("student01")["state"], "stopped")
        self.assertNotIn("student01", atk.queue)

    def test_stop_removes_a_live_slot(self):
        atk, cfg, ex = make_attack()
        atk.start("student01", "ctf-1")
        atk.process_one()
        ok, msg = atk.stop("student01")
        self.assertTrue(ok, msg)
        self.assertNotIn(cfg.attack_slot_name("student01"), ex.containers)
        self.assertEqual(atk.status("student01")["state"], "stopped")

    def test_switching_target_stops_the_first(self):
        atk, cfg, ex = make_attack()
        atk.start("student01", "ctf-1")
        atk.process_one()
        atk.start("student01", "ctf-2")
        atk.process_one()
        self.assertEqual(ex.image_of(cfg.attack_slot_name("student01")), "img-2")

    def test_reset_requires_a_live_target(self):
        atk, _, _ = make_attack()
        ok, msg = atk.reset("student01")
        self.assertFalse(ok)
        self.assertIn("no target", msg)

    def test_reset_requeues_the_same_target(self):
        atk, cfg, ex = make_attack()
        atk.start("student01", "ctf-1")
        atk.process_one()
        ok, msg = atk.reset("student01")
        self.assertTrue(ok, msg)
        self.assertEqual(atk.status("student01")["state"], "queued")
        atk.process_one()
        self.assertEqual(atk.status("student01")["state"], "live")

    def test_flag_is_per_target_and_per_user(self):
        atk, cfg, ex = make_attack()
        cfg.seed = "s"
        atk.start("student01", "ctf-1")
        atk.process_one()
        atk.start("student02", "ctf-2")
        atk.process_one()
        f1 = ex.containers[cfg.attack_slot_name("student01")]["env"]["CTF_FLAG"]
        f2 = ex.containers[cfg.attack_slot_name("student02")]["env"]["CTF_FLAG"]
        self.assertTrue(f1.startswith("flag{ctf-1-"))
        self.assertTrue(f2.startswith("flag{ctf-2-"))
        self.assertNotEqual(f1, f2)

    def test_target_token_is_distinct_from_flag_and_per_target(self):
        atk, cfg, ex = make_attack()
        cfg.seed = "s"
        atk.start("student01", "ctf-1")
        atk.process_one()
        env = ex.containers[cfg.attack_slot_name("student01")]["env"]
        self.assertTrue(env["CTF_TARGET_TOKEN"].startswith("flag{ctf-1-token-"))
        self.assertNotEqual(env["CTF_TARGET_TOKEN"], env["CTF_FLAG"])

    def test_create_failure_sets_error_state(self):
        atk, cfg, ex = make_attack()
        atk.start("student01", "ctf-1")
        ex.images.discard("img-1")  # harmless here, FakeExecutor.create doesn't check presence
        orig_create = ex.create
        def boom(*a, **k):
            raise docker_api.DockerError("ctf-host unreachable")
        ex.create = boom
        atk.process_one()
        slot = atk.status("student01")
        self.assertEqual(slot["state"], "error")
        self.assertIn("unreachable", slot["error"])
        ex.create = orig_create

    def test_sweep_idle_stops_a_stale_slot(self):
        clock = [1000.0]
        atk, cfg, ex = make_attack()
        atk.clock = lambda: clock[0]
        cfg.attack_idle_seconds = 60
        atk.start("student01", "ctf-1")
        atk.process_one()
        clock[0] += 61
        atk.sweep_idle()
        self.assertEqual(atk.status("student01")["state"], "stopped")
        self.assertNotIn(cfg.attack_slot_name("student01"), ex.containers)

    def test_catalog_lists_target_ids(self):
        atk, _, _ = make_attack()
        self.assertEqual([t["id"] for t in atk.catalog()], ["ctf-1", "ctf-2"])


class TestHTTP(unittest.TestCase):
    GATEWAY_TOKEN = "gw-secret"
    FACILITATOR = "admin"

    def setUp(self):
        self.ctl, self.cfg, self.ex = make_controller(count=1)
        self.cfg.gateway_token = self.GATEWAY_TOKEN
        self.cfg.facilitator = self.FACILITATOR
        self.cfg.attack_targets = {"ctf-1": "registry.ctf.internal/ctf-1:base"}
        self.ex.images.add("registry.ctf.internal/ctf-1:base")
        self.ctl.tick()  # populate snapshot + last_ok
        self.atk = c.AttackManager(self.cfg, self.ex)
        self.srv = c.Server(("127.0.0.1", 0), c.make_handler(self.ctl, self.atk))
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def _req(self, method, path, token=None, body=None, gw_user=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {}
        if token:
            headers["Authorization"] = "Bearer " + token
        if gw_user:
            headers["X-Gateway-Token"] = self.GATEWAY_TOKEN
            headers["X-Auth-User"] = gw_user
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

    def _raw_get(self, path):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp.status, body

    def test_page_shell_served_with_no_auth(self):
        status, body = self._raw_get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"Attack Range", body)
        # No inline <style> or style="": the shared CSP (style-src 'self', no
        # unsafe-inline) silently drops both, which is what left this page
        # completely unstyled before 2026-10-06's fix.
        self.assertNotIn(b"<style", body)
        self.assertNotIn(b'style="', body)
        self.assertIn(b'<link rel="stylesheet" href="app.css">', body)
        status, body = self._raw_get("/app.js")
        self.assertEqual(status, 200)
        self.assertIn(b"attack/status", body)
        status, body = self._raw_get("/app.css")
        self.assertEqual(status, 200)
        self.assertIn(b"--accent", body)
        # Landing-page per-target cards: the script and its external
        # stylesheet are same-origin and must stay same-origin so the
        # allocator's strict CSP (script-src 'self', style-src 'self')
        # accepts both when attack-cards.js is injected into the landing.
        status, body = self._raw_get("/attack-cards.js")
        self.assertEqual(status, 200)
        self.assertIn(b"data-surface", body)
        self.assertIn(b"portal", body)
        status, body = self._raw_get("/attack-cards.css")
        self.assertEqual(status, 200)
        self.assertIn(b".attack-card", body)

    def test_attack_status_requires_gateway_token(self):
        self.assertEqual(self._req("GET", "/attack/status")[0], 403)
        status, doc = self._req("GET", "/attack/status", gw_user="student01")
        self.assertEqual(status, 200)
        self.assertFalse(doc["facilitator"])
        self.assertEqual(doc["slot"]["state"], "stopped")
        self.assertEqual([t["id"] for t in doc["targets"]], ["ctf-1"])

    def test_attack_status_for_facilitator_has_no_slot(self):
        status, doc = self._req("GET", "/attack/status", gw_user=self.FACILITATOR)
        self.assertEqual(status, 200)
        self.assertTrue(doc["facilitator"])
        self.assertIsNone(doc["slot"])

    def test_attack_status_echoes_scan_target(self):
        # The landing page's attack-range header reads doc.net for the
        # fallback scan hint, and each target in doc.targets carries its
        # own student-reserved IP (addr) that the per-card UI shows. A
        # change to either shape would strand the landing page.
        self.cfg.net_subnet = "10.42.0.0/24"
        self.cfg.net_host_addr = "10.42.0.2"
        self.cfg.attack_subnet_prefix = "10.42.0"
        _, doc = self._req("GET", "/attack/status", gw_user="student01")
        self.assertEqual(doc["net"], {"host": "ctf-host", "subnet": "10.42.0.0/24", "addr": "10.42.0.2"})
        self.assertEqual(doc["targets"], [{"id": "ctf-1", "addr": "10.42.0.100"}])
        # Facilitator view carries the net block (same JS) but no per-
        # target addrs (no slot, no student IP block).
        _, doc = self._req("GET", "/attack/status", gw_user=self.FACILITATOR)
        self.assertEqual(doc["net"]["subnet"], "10.42.0.0/24")
        self.assertEqual(doc["targets"], [{"id": "ctf-1"}])

    def test_attack_start_stop_via_http(self):
        self.assertEqual(self._req("POST", "/attack/start",
                                   body={"target": "ctf-1"})[0], 403)  # no gateway token
        status, doc = self._req("POST", "/attack/start", gw_user="student01", body={"target": "ctf-1"})
        self.assertEqual(status, 200)
        self.assertTrue(doc["ok"])
        self.assertTrue(self.atk.process_one())
        _, doc = self._req("GET", "/attack/status", gw_user="student01")
        self.assertEqual(doc["slot"]["state"], "live")
        status, doc = self._req("POST", "/attack/stop", gw_user="student01", body={})
        self.assertEqual(status, 200)
        self.assertTrue(doc["ok"])
        self.assertEqual(self.atk.status("student01")["state"], "stopped")

    def test_attack_start_refused_for_facilitator(self):
        status, doc = self._req("POST", "/attack/start", gw_user=self.FACILITATOR, body={"target": "ctf-1"})
        self.assertEqual(status, 403)
        self.assertFalse(doc["ok"] if "ok" in doc else False)


if __name__ == "__main__":
    unittest.main()
