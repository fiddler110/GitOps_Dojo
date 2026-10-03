"""The achievements event reporter, and the points in cloud-api where it fires. Run from this directory:
    python3 -B -m unittest test_events
"""
import hashlib
import hmac
import json
import unittest

import events
import policy
import server
import test_concurrency as tc

SUB, TAGS, USERS, FAC = tc.SUB, tc.TAGS, tc.USERS, tc.FAC


class Recorder(events.Reporter):
    def __init__(self, clock=None):
        super().__init__("http://x", "secret", send=self.record, **({"clock": clock} if clock else {}))
        self.sent = []

    def record(self, raw, sig):
        self.sent.append((json.loads(raw), sig, raw))

    def emit(self, *a, **kw):
        super().emit(*a, **kw)
        self.client.flush()

    def seen(self):
        return [(d["event"], d["user"], d.get("reason")) for d, _, _ in self.sent]


class ReporterTest(unittest.TestCase):
    def test_off_without_url_or_secret(self):
        for r in (events.Reporter("", "s"), events.Reporter("u", ""), events.from_env({})):
            self.assertFalse(r.enabled)
            r.emit("portal_request", "a")

    def test_signed_body(self):
        r = Recorder()
        r.emit("policy_denied", "amy", "tag")
        doc, sig, raw = r.sent[0]
        self.assertEqual(doc, {"source": "cloud", "event": "policy_denied", "user": "amy", "reason": "tag"})
        self.assertEqual(sig, hmac.new(b"secret", raw, hashlib.sha256).hexdigest())

    def test_every_limits_per_user_and_event(self):
        now = [0.0]
        r = Recorder(lambda: now[0])
        for _ in range(3):
            r.emit("portal_request", "amy", every=60)
        r.emit("portal_request", "bob", every=60)
        now[0] = 61
        r.emit("portal_request", "amy", every=60)
        self.assertEqual(len(r.sent), 3)

    def test_a_failing_send_never_raises(self):
        def boom(raw, sig):
            raise OSError("down")
        r = events.Reporter("u", "s", send=boom)
        r.emit("portal_request", "amy")
        r.client.flush()

    def test_denial_reasons(self):
        def err(code, pol=None):
            return policy.PolicyError(400, code, "m", policy=pol)
        self.assertEqual(events.denial(err("RequestDisallowedByPolicy", "Require tag 'env'")), ("policy_denied", "tag"))
        self.assertEqual(events.denial(err("RequestDisallowedByPolicy", "Allowed locations")), ("policy_denied", "region"))
        self.assertEqual(events.denial(err("InvalidResourceRequest")), ("policy_denied", "size"))
        self.assertEqual(events.denial(err("QuotaExceeded")), ("quota_denied", None))
        self.assertEqual(events.denial(err("InvalidImage")), ("policy_denied", "image"))
        self.assertIsNone(events.denial(err("InvalidRequestContent")))
        own = err("RequestDisallowedByPolicy", "Require tag 'env'")  # a student's assignment with a lookalike name
        own.assignment = "require-env"
        self.assertEqual(events.denial(own), ("policy_denied", "assignment"))

    def test_replace_after_delete_within_the_window(self):
        now = [0.0]
        r = Recorder(lambda: now[0])
        r.deleted_group("amy", "k", "arm")
        now[0] = 5
        r.written_group("amy", "k", created=True, changed=True)
        r.written_group("amy", "k2", created=True, changed=True)
        r.deleted_group("amy", "k3", "arm")
        now[0] = 500
        r.written_group("amy", "k3", created=True, changed=True)
        self.assertEqual([e for e, _, _ in r.seen()],
                         ["container_deleted", "container_replaced", "container_created", "container_deleted",
                          "container_created"])

    def test_update_in_place_and_swap(self):
        r = Recorder()
        r.written_group("amy", "k", created=False, changed=False)
        r.written_group("amy", "k", created=False, changed=True)
        self.assertEqual(r.seen(), [("container_updated", "amy", "arm"), ("container_replaced", "amy", None)])


class HooksTest(unittest.TestCase):
    """Real ARM and portal requests against the fake executor; the reporter records instead of posting."""
    for _n in ("setUp", "request", "arm", "portal", "go", "cg_path", "rg_path", "put_body", "put", "seed_rg", "seed"):
        locals()[_n] = tc.Concurrency.__dict__[_n]

    def start(self):
        self.setUp()
        self.rec = Recorder()
        self.app.events = self.rec
        self.seed_rg()

    def wait_sent(self, n):
        import time
        for _ in range(100):
            if len(self.rec.sent) >= n:
                return
            time.sleep(0.02)

    def test_create_update_replace_delete(self):
        self.start()
        self.assertEqual(self.put()[0], 201)
        self.assertEqual(self.put()[0], 200)                      # same body: tags/metadata only
        self.assertEqual(self.put(image="dojo/hello:2.0")[0], 200)  # swap the container
        self.assertEqual(self.arm("DELETE", self.cg_path())[0], 200)
        self.assertEqual(self.put()[0], 201)                      # tofu's delete then create
        self.wait_sent(5)
        got = sorted(self.rec.seen())
        a = USERS[0]
        self.assertEqual(got, sorted([("container_created", a, None), ("container_updated", a, "arm"),
                                      ("container_replaced", a, None), ("container_deleted", a, "arm"),
                                      ("container_replaced", a, None)]))

    def test_denials(self):
        self.start()
        body = self.put_body()
        body["location"] = "westus"
        self.assertEqual(self.arm("PUT", self.cg_path(), body)[0], 403)
        body = self.put_body()
        body["tags"] = {}
        self.assertEqual(self.arm("PUT", self.cg_path(), body)[0], 403)
        body = self.put_body()
        body["properties"]["containers"][0]["properties"]["resources"]["requests"]["cpu"] = 4
        self.assertEqual(self.arm("PUT", self.cg_path(), body)[0], 400)
        for n in (1, 2):
            self.put(name=f"ci-q{n}", label=f"site-q{n}")
        self.assertEqual(self.put(name="ci-q3", label="site-q3")[0], 409)
        self.wait_sent(4 + 2)
        a = USERS[0]
        self.assertEqual([x for x in self.rec.seen() if x[0] in ("policy_denied", "quota_denied")],
                         [("policy_denied", a, "region"), ("policy_denied", a, "tag"), ("policy_denied", a, "size"),
                          ("quota_denied", a, None)])

    def test_portal_edit_and_delete_are_marked_portal(self):
        self.start()
        self.seed()
        a = USERS[0]
        url = f"/cloud/api/containers/{SUB[a]}/rg-a/ci-a1"
        h = {"X-Gateway-Token": tc.TOKEN, "X-Auth-User": a}
        self.assertEqual(self.request("PATCH", url, h, {"tags": {"owner": "x", "env": "y"}})[0], 200)
        self.assertEqual(self.request("PATCH", url, h, {"tags": {"owner": "x"}})[0], 403)
        self.assertEqual(self.request("DELETE", url, h)[0], 200)
        self.wait_sent(4)
        seen = self.rec.seen()
        self.assertIn(("container_updated", a, "portal"), seen)
        self.assertIn(("policy_denied", a, "tag"), seen)
        self.assertIn(("container_deleted", a, "portal"), seen)
        self.assertEqual(seen.count(("portal_request", a, None)), 1)    # three calls, one report

    def test_facilitator_is_not_reported(self):
        self.start()
        self.seed()
        self.assertEqual(self.portal("GET", "/cloud/api/overview", FAC)[0], 200)
        self.assertEqual(self.arm("DELETE", self.cg_path(), user=FAC)[0], 200)
        self.assertEqual(self.rec.sent, [])


if __name__ == "__main__":
    unittest.main()
