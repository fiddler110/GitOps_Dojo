"""Tests for the store and the HTTP layer: identity, signed events, cheats, persistence, admin."""

import http.client
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["GATEWAY_TOKEN"] = "t" * 64
os.environ["FACILITATOR_USERNAME"] = "boss"
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "catalog"))
import catalog  # noqa: E402  (server puts ../catalog on the path)
import guards  # noqa: E402
import ledger as lg  # noqa: E402
import server  # noqa: E402
from store import Denied, Store  # noqa: E402

WORKSHOP = os.path.join(HERE, "..", "..", "..", "workshops", "git-fundamentals")
TOKEN = os.environ["GATEWAY_TOKEN"]


def load():
    return catalog.load(WORKSHOP, os.path.join(HERE, "..", "catalog", "shared.json"))[0]


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.clock = Clock()
        self.mk()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def mk(self, **kw):
        self.s = Store(load(), lg.Config(), self.dir, "secret", facilitator="boss", clock=self.clock, **kw)

    def ev(self, user, item, nonce="n", **over):
        body = {"user": user, "event": item, "ts": int(self.clock()), "nonce": nonce}
        body["sig"] = guards.sign("secret", user, item, body["ts"], nonce)
        body.update(over)
        return body

    def test_signed_event_scores_and_toasts(self):
        self.assertEqual(self.s.event("a", self.ev("a", "l1-clone")), {"awarded": True, "points": 10})
        self.assertEqual(self.s.event(None, self.ev("a", "l1-branch", "n2"))["points"], 10)
        self.assertEqual(self.s.me("a")["score"], 20)
        self.assertEqual(len(self.s.toasts("a", "portal")), 2)
        self.assertEqual(self.s.toasts("a", "portal"), [])

    def test_repeat_event_awards_nothing(self):
        self.s.event(None, self.ev("a", "l1-clone"))
        self.assertFalse(self.s.event(None, self.ev("a", "l1-clone", "n2"))["awarded"])

    def test_forged_event_charges_the_identified_caller(self):
        with self.assertRaises(Denied) as e:
            self.s.event("a", self.ev("a", "l1-clone", sig="0" * 64))
        self.assertEqual(e.exception.code, 403)
        me = self.s.me("a")
        self.assertEqual(me["score"], 0)     # -1 floors at zero
        self.assertIn("cheat-forged", self.s.ledger.unlocked_ids("a"))
        self.assertEqual(self.s.toasts("a", "portal")[0]["title"], "Nice Try, Hackerman")

    def test_forged_event_from_the_network_is_never_charged_to_the_named_user(self):
        with self.assertRaises(Denied):
            self.s.event(None, self.ev("victim", "l1-clone", sig="0" * 64))
        self.assertNotIn("victim", self.s.ledger.users)
        self.assertEqual(len(self.s.forged), 1)

    def test_posting_as_someone_else_is_forged_for_the_caller(self):
        with self.assertRaises(Denied):
            self.s.event("mallory", self.ev("victim", "l1-clone"))
        self.assertIn("cheat-forged", self.s.ledger.unlocked_ids("mallory"))
        self.assertNotIn("victim", self.s.ledger.users)

    def test_malformed_and_replay_and_stale(self):
        with self.assertRaises(Denied):
            self.s.event(None, {"user": "a"})
        self.s.event(None, self.ev("a", "l1-clone"))
        with self.assertRaises(Denied) as e:
            self.s.event(None, self.ev("a", "l1-branch"))     # same nonce
        self.assertEqual(e.exception.code, 409)
        old = self.ev("a", "l1-diff", "n9")
        self.clock.t += 1000
        with self.assertRaises(Denied) as e:
            self.s.event(None, old)
        self.assertEqual(e.exception.code, 400)

    def test_unknown_item(self):
        with self.assertRaises(Denied) as e:
            self.s.event(None, self.ev("a", "no-such"))
        self.assertEqual(e.exception.code, 404)

    def test_masher_gets_the_zero_point_cheat_and_a_429(self):
        for i in range(20):
            self.s.hint("a", "c1")
        with self.assertRaises(Denied) as e:
            self.s.hint("a", "c1")
        self.assertEqual(e.exception.code, 429)
        self.assertIn("cheat-masher", self.s.ledger.unlocked_ids("a"))
        self.assertEqual(self.s.me("a")["score"], 0)

    def test_facilitator_is_not_a_student(self):
        with self.assertRaises(Denied) as e:
            self.s.me("boss")
        self.assertEqual(e.exception.code, 403)
        self.assertNotIn("boss", self.s.ledger.users)

    def test_hints_and_reveal(self):
        self.assertEqual(self.s.hint("a", "c1")["cost"], 25)
        with self.assertRaises(Denied) as e:
            self.s.reveal("a", "c1")
        self.assertEqual(e.exception.code, 409)
        h = self.s.hint("a", "c1")
        self.assertEqual(h["n"], 2)
        self.assertTrue(h["text"])
        self.assertIn("answer", self.s.reveal("a", "c1"))
        self.assertEqual(self.s.event(None, self.ev("a", "c1", "x"))["points"], 0)
        with self.assertRaises(Denied):
            self.s.hint("a", "nope")

    def test_board_is_anonymous_and_marks_you(self):
        self.s.event(None, self.ev("alice", "l1-clone"))
        self.s.me("bob")
        rows = self.s.board("bob")
        self.assertEqual(len(rows), 2)
        self.assertNotIn("alice", json.dumps(rows))
        self.assertEqual([r["you"] for r in rows], [False, True])
        self.mk(anonymous=False)
        self.assertEqual({r["name"] for r in self.s.board("bob")}, {"alice", "bob"})

    def test_me_has_moments_and_completion(self):
        self.s.event(None, self.ev("a", "f-wrongdir"))
        me = self.s.me("a")
        self.assertEqual([m["id"] for m in me["moments"]], ["f-wrongdir"])
        self.assertEqual(me["completion"]["percent"], 0)
        self.assertEqual(me["completion"]["needed"], 17)
        self.assertEqual(me["score"], 0)

    def test_state_survives_a_restart(self):
        self.s.event(None, self.ev("a", "l1-clone"))
        name = self.s.me("a")["name"]
        self.mk()
        self.assertEqual(self.s.me("a")["score"], 10)
        self.assertEqual(self.s.me("a")["name"], name)

    def test_corrupt_state_starts_fresh(self):
        with open(os.path.join(self.dir, "state.json"), "w") as f:
            f.write("{not json")
        self.mk()
        self.assertEqual(self.s.me("a")["score"], 0)

    def test_admin(self):
        self.s.event(None, self.ev("a", "l1-clone"))
        self.s.admin_award("a", 5, "helped out")
        self.assertEqual(self.s.me("a")["score"], 15)
        with self.assertRaises(Denied):
            self.s.admin_award("ghost", 1, "")
        with self.assertRaises(Denied):
            self.s.admin_award("a", "lots", "")
        st = self.s.admin_state()
        self.assertEqual(st["students"][0]["user"], "a")
        self.assertTrue(st["students"][0]["name"])
        self.s.admin_reset("a")
        self.assertEqual(self.s.admin_state()["students"], [])
        self.assertEqual([e["action"] for e in self.s.admin_state()["log"]], ["award", "reset"])

    def test_reload_keeps_unlocks(self):
        self.s.event(None, self.ev("a", "l1-clone"))
        self.s.reload(load())
        self.assertEqual(self.s.me("a")["score"], 10)


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        server.store = Store(load(), lg.Config(), cls.dir, TOKEN, facilitator="boss")
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        shutil.rmtree(cls.dir)

    def call(self, method, path, user=None, token=TOKEN, body=None, extra=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port)
        h = dict(extra or {})
        if user:
            h["X-Auth-User"] = user
            if token:
                h["X-Gateway-Token"] = token
        data = json.dumps(body).encode() if body is not None else None
        c.request(method, path, body=data, headers=h)
        r = c.getresponse()
        raw = r.read()
        c.close()
        try:
            doc = json.loads(raw)
        except ValueError:
            doc = raw
        return r.status, doc, r

    def test_pages_and_headers(self):
        for path in ("/", "/widget", "/toast.js", "/widget.js", "/board.js", "/style.css"):
            st, _, r = self.call("GET", path)
            self.assertEqual(st, 200, path)
            self.assertIn("script-src 'self'", r.getheader("Content-Security-Policy"))
            self.assertEqual(r.getheader("X-Frame-Options"), "SAMEORIGIN")
        self.assertEqual(self.call("GET", "/healthz")[0], 200)

    def test_pages_have_no_inline_script_or_style(self):
        import re
        for name in os.listdir(os.path.join(HERE, "static")):
            if name.endswith(".html"):
                with open(os.path.join(HERE, "static", name)) as f:
                    text = f.read()
                self.assertIsNone(re.search(r"<script(?![^>]*\bsrc=)", text), name)
                self.assertNotIn("<style", text, name)
                self.assertNotIn(" style=", text, name)
                self.assertNotIn(" onclick=", text, name)

    def test_identity_needs_the_gateway_token(self):
        self.assertEqual(self.call("GET", "/api/me")[0], 403)
        self.assertEqual(self.call("GET", "/api/me", user="alice", token="wrong")[0], 403)
        st, doc, _ = self.call("GET", "/api/me", user="ivy")
        self.assertEqual((st, doc["score"]), (200, 0))

    def test_toasts_endpoint_and_terminal_surface(self):
        body = {"user": "tina", "event": "f-wrongdir", "ts": int(__import__("time").time()), "nonce": "h1"}
        body["sig"] = guards.sign(TOKEN, "tina", "f-wrongdir", body["ts"], "h1")
        st, doc, _ = self.call("POST", "/api/event", body=body)
        self.assertEqual((st, doc["awarded"]), (200, True))
        self.assertEqual(len(self.call("GET", "/api/toasts?surface=terminal", user="tina")[1]["toasts"]), 1)
        t = self.call("GET", "/api/toasts?surface=widget", user="tina")[1]["toasts"]
        self.assertEqual((len(t), t[0]["kind"], t[0]["points"]), (1, "funny", 0))
        self.assertEqual(self.call("GET", "/api/toasts?surface=widget", user="tina")[1]["toasts"], [])

    def test_forged_post_through_the_gateway_is_charged(self):
        st, _, _ = self.call("POST", "/api/event", user="fred",
                             body={"user": "fred", "event": "l1-clone", "ts": 1, "nonce": "x", "sig": "no"})
        self.assertEqual(st, 403)
        self.assertEqual(self.call("GET", "/api/me", user="fred")[1]["score"], 0)
        self.assertIn("cheat-forged", server.store.ledger.unlocked_ids("fred"))

    def test_bad_bodies(self):
        c = http.client.HTTPConnection("127.0.0.1", self.port)
        c.request("POST", "/api/event", body=b"not json")
        self.assertEqual(c.getresponse().status, 400)
        c.close()
        self.assertEqual(self.call("POST", "/api/hint", user="a", body={})[0], 400)
        self.assertEqual(self.call("POST", "/api/hint", body={"challenge": "c1"})[0], 403)

    def test_hint_over_http(self):
        st, doc, _ = self.call("POST", "/api/hint", user="hank", body={"challenge": "c1"})
        self.assertEqual((st, doc["n"], doc["cost"]), (200, 1, 25))

    def test_admin_is_facilitator_only(self):
        self.assertEqual(self.call("GET", "/achievements-admin/api/state", user="alice")[0], 403)
        self.assertEqual(self.call("GET", "/achievements-admin/")[0], 403)
        self.assertEqual(self.call("GET", "/achievements-admin/", user="boss")[0], 200)
        st, doc, _ = self.call("GET", "/achievements-admin/api/state", user="boss")
        self.assertEqual(st, 200)
        self.assertIn("students", doc)

    def test_admin_post_needs_header_and_facilitator(self):
        path = "/achievements-admin/api/award"
        body = {"user": "alice", "points": 3, "reason": "x"}
        self.call("GET", "/api/me", user="alice")
        self.assertEqual(self.call("POST", path, user="alice", body=body, extra={"X-Requested-With": "dojo-admin"})[0], 403)
        self.assertEqual(self.call("POST", path, user="boss", body=body)[0], 403)
        self.assertEqual(self.call("POST", path, user="boss", body=body, extra={"X-Requested-With": "dojo-admin"})[0], 200)
        self.assertEqual(self.call("GET", "/api/me", user="alice")[1]["score"], 3)

    def test_unknown_paths(self):
        self.assertEqual(self.call("GET", "/nope")[0], 404)
        self.assertEqual(self.call("POST", "/nope", user="a", body={})[0], 404)


if __name__ == "__main__":
    unittest.main()
