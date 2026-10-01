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
import identity  # noqa: E402
import server  # noqa: E402
import webhook  # noqa: E402
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
        self.assertEqual(me["completion"]["needed"], 18)
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

    # -- activity ----------------------------------------------------------------------
    def test_shell_event_unlocks_once(self):
        self.assertEqual(self.s.shell("a", {"cmd": "git clone http://x/y.git", "exit": 0}), {"unlocked": 1})
        self.assertEqual(self.s.shell("a", {"cmd": "git clone http://x/y.git", "exit": 0}), {"unlocked": 0})
        self.assertEqual(self.s.me("a")["score"], 10)
        with self.assertRaises(Denied):
            self.s.shell("a", {"cmd": "git clone"})

    def test_shell_burst_is_dropped_without_the_masher(self):
        self.mk(shell_rate=(3, 10))
        for _ in range(3):
            self.s.shell("a", {"cmd": "ls", "exit": 0})
        with self.assertRaises(Denied) as cm:
            self.s.shell("a", {"cmd": "git clone x", "exit": 0})
        self.assertEqual(cm.exception.code, 429)
        self.assertEqual(self.s.ledger.unlocked_ids("a"), set())

    def test_shell_is_for_students_only(self):
        with self.assertRaises(Denied):
            self.s.shell("boss", {"cmd": "git clone x", "exit": 0})

    def test_activity_counts_failures_and_progress_without_the_command_text(self):
        self.s.shell("a", {"cmd": "git clone http://x/y.git", "exit": 0})
        self.clock.t += 120
        for _ in range(3):
            self.s.shell("a", {"cmd": "secret-looking command", "exit": 1})
        self.clock.t += 30
        a = self.s.activity_snapshot()["a"]
        self.assertEqual((a["streak"], a["cmds"], a["fails"]), (3, 4, 3))
        self.assertEqual((a["since_cmd"], a["since_progress"]), (30, 150))
        self.assertNotIn("secret", repr(self.s.activity_snapshot()))
        self.s.shell("a", {"cmd": "ls", "exit": 0})
        self.assertEqual(self.s.activity_snapshot()["a"]["streak"], 0)
        self.assertNotIn("boss", self.s.activity_snapshot())

    def test_activity_forgets_old_commands(self):
        self.s.shell("a", {"cmd": "ls", "exit": 1})
        self.clock.t += 700
        self.s.shell("a", {"cmd": "ls", "exit": 0})
        self.assertEqual(self.s.activity_snapshot()["a"]["fails"], 0)

    def test_progress_lists_core_milestones_by_lab(self):
        self.s.shell("a", {"cmd": "git clone http://x/y.git", "exit": 0})
        p = self.s.progress("a")
        rows = [m for lab in p["labs"] for m in lab["milestones"]]
        self.assertTrue(any(m["done"] for m in rows) and any(not m["done"] for m in rows))
        self.assertEqual(p["done"], sum(m["done"] for m in rows))
        self.assertNotIn("challenges", p)

    def test_forgejo_event_credits_the_user_and_skips_staff(self):
        self.mk(ignore=("forge-admin",))
        pr = lambda who: {"source": "forgejo", "event": "pull_request", "action": "opened", "user": who,
                          "actor": who, "repo": "r/r", "branch": "main", "tag": None, "ref_type": None}
        self.assertEqual(self.s.forgejo(pr("a")), {"unlocked": 1})
        self.assertIn("l1-pr", self.s.ledger.unlocked_ids("a"))
        for staff in ("boss", "forge-admin", None):
            self.assertEqual(self.s.forgejo(pr(staff)), {"unlocked": 0})
        self.assertEqual(set(self.s.ledger.users), {"a"})

    def test_reload_rebuilds_the_matcher(self):
        c = load()
        for m in c["labs"][0]["milestones"]:
            if m["id"] == "l1-clone":
                m["match"] = {"source": "shell", "cmd": "git init", "exit": 0}
        self.s.reload(c)
        self.s.shell("a", {"cmd": "git clone x", "exit": 0})
        self.assertNotIn("l1-clone", self.s.ledger.unlocked_ids("a"))
        self.s.shell("a", {"cmd": "git init", "exit": 0})
        self.assertIn("l1-clone", self.s.ledger.unlocked_ids("a"))

    def test_switched_off_items_are_hidden_from_student_views(self):
        self.s.shell("a", {"cmd": "git clone x", "exit": 0})
        c = load()
        c["labs"][0]["milestones"][0]["enabled"] = False     # l1-clone
        c["challenges"][0]["enabled"] = False
        self.s.reload(c)
        me = self.s.me("a")
        self.assertEqual(me["score"], 0)
        self.assertNotIn("l1-clone", [r["id"] for r in me["recent"]])
        self.assertNotIn(c["challenges"][0]["id"], [r["id"] for r in me["challenges"]])
        self.assertEqual(self.s.admin_state()["students"][0]["unlocks"], 0)
        self.assertEqual(self.s.shell("a", {"cmd": "git clone y", "exit": 0}), {"unlocked": 0})


class PokingTests(unittest.TestCase):
    """The "poking a neighbour" ladder: 1 strike bumped (0), 3 curious (0), 8 persistent (-1)."""
    tearDown, mk = StoreTests.tearDown, StoreTests.mk

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.clock = Clock()
        self.mk()
        for u in ("student01", "student02", "student10"):
            self.s.me(u)

    def sh(self, user, cmd):
        self.clock.t += 1
        return self.s.shell(user, {"cmd": cmd, "exit": 0})

    def ids(self, user="student01"):
        return self.s.ledger.unlocked_ids(user)

    def test_ladder_over_shell_commands(self):
        self.sh("student01", "ls /home/student02")
        self.assertIn("cheat-bump", self.ids())
        self.assertNotIn("cheat-curious", self.ids())
        self.sh("student01", "cat student02/notes")
        self.assertNotIn("cheat-curious", self.ids())
        self.sh("student01", "git clone http://forgejo/student02/challenge-repo")
        self.assertIn("cheat-curious", self.ids())
        self.assertEqual(self.s.me("student01")["score"], 10)     # only the clone milestone
        for _ in range(4):
            self.sh("student01", "ls student02")
        self.assertNotIn("cheat-persistent", self.ids())
        self.sh("student01", "ls student02")
        self.assertIn("cheat-persistent", self.ids())
        self.assertEqual(self.s.me("student01")["score"], 9)
        self.sh("student01", "ls student02")      # each tier fires once
        self.assertEqual(self.s.me("student01")["score"], 9)
        self.assertEqual(self.ids("student02"), set())

    def test_own_name_and_lookalikes_are_not_pokes(self):
        for cmd in ("ls /home/student01", "echo student1", "ls student100", "ls my-student02", "git status"):
            self.sh("student01", cmd)
        self.assertNotIn("cheat-bump", self.ids())
        self.sh("student01", "ls /home/student10")
        self.assertIn("cheat-bump", self.ids())

    def test_forgejo_write_in_a_classmates_repo(self):
        own = {"source": "forgejo", "event": "push", "user": "student01", "repo": "student01/challenge-repo"}
        org = dict(own, repo="training/sample-training-repo")
        self.s.forgejo(own); self.s.forgejo(org)
        self.assertNotIn("cheat-bump", self.ids())
        self.s.forgejo(dict(own, repo="student02/challenge-repo"))
        self.assertIn("cheat-bump", self.ids())

    def test_facilitator_in_a_students_repo_is_fine(self):
        self.s.forgejo({"source": "forgejo", "event": "push", "user": "boss", "repo": "student02/challenge-repo"})
        self.assertEqual(self.ids("student02"), set())
        self.assertEqual(self.s.ledger.users["boss"]["strikes"] if "boss" in self.s.ledger.users else 0, 0)

    def test_check_request_naming_a_neighbour_is_refused(self):
        self.s.probe("student01", {"challenge": "c1"})            # nothing named: fine
        self.s.probe("student01", {"challenge": "c1", "user": "student01"})
        self.assertNotIn("cheat-bump", self.ids())
        with self.assertRaises(Denied) as e:
            self.s.probe("student01", {"challenge": "c1", "repo": "student02/challenge-repo"})
        self.assertEqual(e.exception.code, 403)
        self.assertIn("cheat-bump", self.ids())

    def test_strikes_survive_a_restart(self):
        for _ in range(3):
            self.sh("student01", "ls student02")
        self.mk()
        self.assertIn("cheat-curious", self.ids())
        self.sh("student01", "ls student02")
        self.assertEqual(self.s.ledger.users["student01"]["strikes"], 4)


class CertificateTests(unittest.TestCase):
    tearDown, mk = StoreTests.tearDown, StoreTests.mk

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.clock = Clock()
        self.mk()

    def test_not_complete_has_no_tier_and_override_completes(self):
        self.s.me("a")
        doc = self.s.certificate("a")
        self.assertIsNone(doc["tier"])
        self.assertFalse(doc["completion"]["complete"])
        self.s.admin_complete("a", True)
        self.assertEqual(self.s.certificate("a")["tier"], "complete")
        self.assertTrue(self.s.admin_state()["students"][0]["override"])
        self.s.admin_complete("a", False)
        self.assertIsNone(self.s.certificate("a")["tier"])
        with self.assertRaises(Denied):
            self.s.admin_complete("nobody", True)

    def test_summary_lists_unlocks_and_cheats_but_not_the_name(self):
        self.s.signature, self.s.class_date = "Ada", "1 Jan"
        self.s.me("a")
        self.s.tamper("a")
        self.s.event(None, {"user": "a", "event": "l1-clone", "ts": int(self.clock()), "nonce": "n",
                            "sig": guards.sign("secret", "a", "l1-clone", int(self.clock()), "n")})
        doc = self.s.certificate("a")
        self.assertEqual([u["id"] for u in doc["unlocks"]], ["l1-clone"])
        self.assertEqual(len(doc["cheats"]), 1)
        self.assertEqual((doc["signature"], doc["class_date"]), ("Ada", "1 Jan"))
        self.assertNotIn("name", doc)


class ResolverTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.clock = Clock()
        self.r = identity.Resolver(self.fetch, self.clock)

    def fetch(self, token):
        self.calls.append(token)
        return {"good1": "alice"}.get(token)

    def test_token_parsing(self):
        t = identity.Resolver.token_of
        self.assertEqual(t("token abc123"), "abc123")
        self.assertEqual(t("Bearer abc123"), "abc123")
        for bad in (None, "", "token", "Basic abc", "token a b", "token ../x", "token " + "a" * 300):
            self.assertIsNone(t(bad), bad)

    def test_resolves_and_caches(self):
        self.assertEqual(self.r.resolve("token good1"), "alice")
        self.assertEqual(self.r.resolve("token good1"), "alice")
        self.assertEqual(self.calls, ["good1"])
        self.clock.t += 61
        self.r.resolve("token good1")
        self.assertEqual(len(self.calls), 2)

    def test_unknown_token_is_cached_briefly(self):
        self.assertIsNone(self.r.resolve("token nope"))
        self.assertIsNone(self.r.resolve("token nope"))
        self.assertEqual(len(self.calls), 1)
        self.clock.t += 11
        self.r.resolve("token nope")
        self.assertEqual(len(self.calls), 2)

    def test_malformed_never_calls_forgejo(self):
        self.r.resolve("nonsense")
        self.assertEqual(self.calls, [])


class TokenHttpTests(unittest.TestCase):
    """The terminal's way in: its own Forgejo token, plus the client hash."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        server.store = Store(load(), lg.Config(), cls.dir, TOKEN, facilitator="boss")
        server.resolver = identity.Resolver(lambda t: {"tokA": "amy", "tokB": "ben", "tokC": "cat", "tokD": "dan"}.get(t))
        server.CLIENT_HASH = "h" * 64
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        server.resolver = None
        server.CLIENT_HASH = ""
        shutil.rmtree(cls.dir)

    def call(self, method, path, token=None, client="h" * 64, body=None, extra=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port)
        h = dict(extra or {})
        if token:
            h["Authorization"] = "token " + token
        if client:
            h["X-Dojo-Client"] = client
        c.request(method, path, body=json.dumps(body).encode() if body is not None else None, headers=h)
        r = c.getresponse()
        raw = r.read()
        c.close()
        return r.status, json.loads(raw)

    def cheats(self, user):
        return {i for i in server.store.ledger.unlocked_ids(user) if i.startswith("cheat")}

    def test_adapter_events_need_the_shared_secret(self):
        import hashlib
        import hmac
        server.ADAPTER_SECRET = "adapt"
        try:
            raw = json.dumps({"source": "dns", "event": "api_refused", "user": "amy", "zone": "z"}).encode()

            def post(sig):
                c = http.client.HTTPConnection("127.0.0.1", self.port)
                c.request("POST", "/api/adapter", body=raw, headers={"X-Adapter-Signature": sig})
                r = c.getresponse()
                out = (r.status, json.loads(r.read()))
                c.close()
                return out
            self.assertEqual(post("0" * 64)[0], 403)
            self.assertEqual(post(hmac.new(b"adapt", raw, hashlib.sha256).hexdigest()), (200, {"unlocked": 0}))
            server.ADAPTER_SECRET = None
            self.assertEqual(post(hmac.new(b"adapt", raw, hashlib.sha256).hexdigest())[0], 403)
        finally:
            server.ADAPTER_SECRET = None

    def test_sensei_reads_need_the_sensei_key(self):
        server.store.shell("amy", {"cmd": "ls", "exit": 1})
        try:
            for path in ("/api/sensei/activity", "/api/sensei/progress?user=amy"):
                self.assertEqual(self.call("GET", path, client=None)[0], 403)         # key unset: off
            server.SENSEI_KEY = "sk"
            for path in ("/api/sensei/activity", "/api/sensei/progress?user=amy"):
                self.assertEqual(self.call("GET", path, client=None)[0], 403)         # no key
                self.assertEqual(self.call("GET", path, client=None, extra={"X-Sensei-Key": "bad"})[0], 403)
                self.assertEqual(self.call("GET", path, token="tokA")[0], 403)        # a student's own token is no key
            ok = {"X-Sensei-Key": "sk"}
            st, doc = self.call("GET", "/api/sensei/activity", client=None, extra=ok)
            self.assertEqual((st, doc["students"]["amy"]["fails"]), (200, 1))
            st, doc = self.call("GET", "/api/sensei/progress?user=amy", client=None, extra=ok)
            self.assertEqual(st, 200)
            self.assertTrue(doc["labs"] and "total" in doc)
            self.assertEqual(self.call("GET", "/api/sensei/progress", client=None, extra=ok)[0], 400)
        finally:
            server.SENSEI_KEY = None

    def test_token_identifies_the_student(self):
        st, doc = self.call("GET", "/api/me", token="tokA")
        self.assertEqual((st, doc["user"]), (200, "amy"))

    def test_unknown_token_is_anonymous(self):
        self.assertEqual(self.call("GET", "/api/me", token="bogus")[0], 403)
        self.assertEqual(self.call("GET", "/api/me")[0], 403)

    def test_hint_with_the_shipped_client(self):
        st, doc = self.call("POST", "/api/hint", token="tokA", body={"challenge": "c1"})
        self.assertEqual((st, doc["n"]), (200, 1))

    def test_edited_client_is_charged_and_refused(self):
        st, _ = self.call("POST", "/api/hint", token="tokB", client="f" * 64, body={"challenge": "c1"})
        self.assertEqual(st, 403)
        self.assertEqual(self.cheats("ben"), {"cheat-client"})
        self.assertEqual(server.store.ledger.hints_used("ben", "c1"), 0)

    def test_no_client_on_a_mutating_call_counts_as_your_own_client(self):
        st, _ = self.call("POST", "/api/hint", token="tokC", client=None, body={"challenge": "c1"})
        self.assertEqual(st, 403)
        self.assertEqual(self.cheats("cat"), {"cheat-client"})

    def test_reading_without_a_client_is_fine(self):
        self.assertEqual(self.call("GET", "/api/me", token="tokD", client=None)[0], 200)
        self.assertEqual(self.cheats("dan"), set())

    def test_someone_elses_identity_header_is_a_cheat(self):
        self.call("GET", "/api/me", token="tokA", extra={"X-Auth-User": "ben"})
        self.assertIn("cheat-identity", server.store.ledger.unlocked_ids("amy"))
        self.assertNotIn("cheat-identity", server.store.ledger.unlocked_ids("ben"))

    def test_terminal_toasts_echo_once_and_stay_queued(self):
        server.store.ledger.unlock("eve", "f-main", 5)
        server.resolver.fetch = lambda t: {"tokE": "eve"}.get(t)
        st, doc = self.call("GET", "/api/toasts?surface=terminal&after=0", token="tokE")
        self.assertEqual(len(doc["toasts"]), 1)
        seq = doc["toasts"][0]["seq"]
        self.assertEqual(self.call("GET", f"/api/toasts?surface=terminal&after={seq}", token="tokE")[1]["toasts"], [])
        # the echo did not deliver it: the browser still gets its toast
        self.assertEqual(len(server.store.ledger.pending("eve")), 1)

    def test_check_without_a_runner_is_501(self):
        self.assertIsNone(server.runner)
        self.assertEqual(self.call("POST", "/api/check", token="tokA", body={"challenge": "c1"})[0], 501)

    def test_challenge_start_and_check_end_to_end(self):
        """dojo-challenge start, then dojo-check, over HTTP against the fake Forgejo."""
        import challenges
        from fake_forgejo import FakeForgejo
        fj = FakeForgejo(["dan"])
        plugins = challenges.load_plugins(server.PLUGIN_DIRS)
        server.runner = challenges.Runner(plugins, os.path.join(WORKSHOP, "achievements", "seeds"), fj, lambda: 1.79e9)
        try:
            st, doc = self.call("POST", "/api/challenge", token="tokD", body={"challenge": "c1", "action": "start"})
            self.assertEqual(st, 200, doc)
            self.assertEqual((doc["repo"], doc["created"]), ("dan/challenge-repo", True))
            self.assertEqual(doc["clone_url"], "http://git-server:3000/dan/challenge-repo.git")
            vals = server.runner.values(server.store.ledger.index["c1"]["item"], "dan")
            role = vals["role"]
            self.assertIn(role, doc["constraints"])
            self.assertNotIn("{", doc["constraints"])
            st, doc = self.call("POST", "/api/check", token="tokD", body={"challenge": "c1"})
            self.assertEqual((st, doc["passed"]), (200, False))
            roster = fj.file("dan/challenge-repo", "main", "roster/team.yaml").replace(vals["role_typo"], role)
            fj.commit("dan/challenge-repo", "hotfix-dan", {"roster/team.yaml": roster}, "dan", start="main")
            fj.open_pr("dan/challenge-repo", "hotfix-dan", "main", "hotfix: role")
            st, doc = self.call("POST", "/api/check", token="tokD", body={"challenge": "c1"})
            self.assertEqual((st, doc["passed"], doc["points"]), (200, True, 100))
            # the answer is rendered for the student once revealed (c2 here)
            self.call("POST", "/api/hint", token="tokD", body={"challenge": "c2"})
            self.call("POST", "/api/hint", token="tokD", body={"challenge": "c2"})
            st, doc = self.call("POST", "/api/reveal", token="tokD", body={"challenge": "c2"})
            self.assertIn("case-dan", doc["answer"])
            # the check and the seed routes need the shipped client like hint does
            st, _ = self.call("POST", "/api/challenge", token="tokC", client=None,
                              body={"challenge": "c1", "action": "reset"})
            self.assertEqual(st, 403)
        finally:
            server.runner = None

    def test_shell_event_from_the_terminal(self):
        server.resolver.fetch = lambda t: {"tokF": "fay"}.get(t)
        st, doc = self.call("POST", "/api/shell", token="tokF", body={"cmd": "git stash", "exit": 0})
        self.assertEqual((st, doc), (200, {"unlocked": 1}))
        self.assertIn("l3-stash", server.store.ledger.unlocked_ids("fay"))

    def test_shell_event_needs_the_shipped_client(self):
        server.resolver.fetch = lambda t: {"tokG": "gus"}.get(t)
        st, _ = self.call("POST", "/api/shell", token="tokG", client=None, body={"cmd": "git stash", "exit": 0})
        self.assertEqual(st, 403)
        self.assertEqual(server.store.ledger.unlocked_ids("gus"), {"cheat-client"})

    def test_shell_event_needs_a_token(self):
        self.assertEqual(self.call("POST", "/api/shell", body={"cmd": "git stash", "exit": 0})[0], 403)
        st, _ = self.call("POST", "/api/shell", body={"cmd": "git stash", "exit": 0},
                          extra={"X-Auth-User": "hal", "X-Gateway-Token": TOKEN})
        self.assertEqual(st, 403)       # the browser can't post shell events
        self.assertNotIn("hal", server.store.ledger.users)

    def test_forged_event_by_token_is_charged_to_the_token_owner(self):
        st, _ = self.call("POST", "/api/event", token="tokA",
                          body={"user": "amy", "event": "l1-clone", "ts": 1, "nonce": "q", "sig": "no"})
        self.assertEqual(st, 403)
        self.assertIn("cheat-forged", server.store.ledger.unlocked_ids("amy"))


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


class WebhookTests(unittest.TestCase):
    """POST /api/forgejo (signature, normalising, crediting) and the hook's registration."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        server.store = Store(load(), lg.Config(), cls.dir, TOKEN, facilitator="boss")
        cls.secret = webhook.secret_from(TOKEN)
        server.WEBHOOK_SECRET = cls.secret
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        shutil.rmtree(cls.dir)

    def post(self, kind, payload, sig=None, header="X-Forgejo-Signature"):
        raw = json.dumps(payload).encode()
        c = http.client.HTTPConnection("127.0.0.1", self.port)
        h = {"X-Forgejo-Event": kind, "Content-Type": "application/json"}
        h[header] = webhook.signature(self.secret, raw) if sig is None else sig
        c.request("POST", "/api/forgejo", body=raw, headers=h)
        r = c.getresponse()
        doc = json.loads(r.read())
        c.close()
        return r.status, doc

    PR = {"action": "opened", "sender": {"login": "ivy"}, "repository": {"full_name": "training/x"},
          "pull_request": {"user": {"login": "ivy"}, "merged": False, "base": {"ref": "main"}}}

    def test_signed_delivery_scores(self):
        self.assertEqual(self.post("pull_request", self.PR), (200, {"unlocked": 1}))
        self.assertIn("l1-pr", server.store.ledger.unlocked_ids("ivy"))

    def test_gitea_signature_header_also_works(self):
        pr = json.loads(json.dumps(self.PR))
        pr["sender"]["login"] = pr["pull_request"]["user"]["login"] = "jon"
        self.assertEqual(self.post("pull_request", pr, header="X-Gitea-Signature")[0], 200)

    def test_bad_or_missing_signature_is_refused(self):
        pr = json.loads(json.dumps(self.PR))
        pr["sender"]["login"] = pr["pull_request"]["user"]["login"] = "kim"
        self.assertEqual(self.post("pull_request", pr, sig="0" * 64)[0], 403)
        self.assertEqual(self.post("pull_request", pr, sig="")[0], 403)
        self.assertNotIn("kim", server.store.ledger.users)

    def test_unknown_event_is_ignored(self):
        self.assertEqual(self.post("issues", {"sender": {"login": "ivy"}}), (200, {"ignored": True}))

    def test_secret_is_stable_per_token(self):
        self.assertEqual(webhook.secret_from("abc"), webhook.secret_from("abc"))
        self.assertNotEqual(webhook.secret_from("abc"), webhook.secret_from("abd"))
        self.assertIsNone(webhook.secret_from(""))
        self.assertFalse(webhook.verify(None, b"{}", {"X-Forgejo-Signature": "x"}))

    def test_ensure_replaces_our_hook_and_keeps_others(self):
        calls = []
        hooks = [{"id": 1, "config": {"url": "http://achievements:8080/api/forgejo"}},
                 {"id": 2, "config": {"url": "http://elsewhere/"}}]

        def api(method, path, body=None):
            calls.append((method, path, body))
            if method == "GET":
                return 200, hooks
            if method == "DELETE":
                hooks[:] = [h for h in hooks if f"/{h['id']}" != path[-2:]]
            return 204, None

        def create(url, secret):
            calls.append(("CREATE", url, secret))
            hooks.append({"id": 3, "config": {"url": url}})
            return True
        self.assertTrue(webhook.ensure(api, create, "http://achievements:8080/api/forgejo", "s3"))
        self.assertEqual([(m, p) for m, p, _ in calls],
                         [("GET", "/admin/hooks?limit=50"), ("DELETE", "/admin/hooks/1"),
                          ("CREATE", "http://achievements:8080/api/forgejo"), ("GET", "/admin/hooks?limit=50")])
        self.assertEqual(calls[2][2], "s3")
        self.assertEqual([h["id"] for h in hooks], [2, 3])

    def test_ensure_fails_when_the_hook_is_not_a_system_hook(self):
        # the create "worked" but the hook doesn't show in the system list (e.g. a default hook)
        api = lambda method, path, body=None: (200, []) if method == "GET" else (204, None)
        self.assertFalse(webhook.ensure(api, lambda u, s: True, "u", "s"))
        self.assertFalse(webhook.ensure(api, lambda u, s: False, "u", "s"))

    def test_register_retries_until_forgejo_answers(self):
        answers = iter([(0, None), (401, None), (200, []), (200, [{"id": 1, "config": {"url": "u"}}])])
        logs = []
        t = webhook.register_in_background(lambda *a, **k: next(answers), lambda u, s: True, "u", "s", logs.append,
                                           sleep=lambda s: None, tries=5)
        t.join(2)
        self.assertEqual(logs, ["forgejo webhook registered -> u"])


if __name__ == "__main__":
    unittest.main()
