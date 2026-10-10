"""Tests for the store and the HTTP layer: identity, signed events, cheats, persistence, admin."""

import http.client
import http.server
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from unittest import mock

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

    def test_refused_user_keeps_its_nonce(self):
        with self.assertRaises(Denied):
            self.s.event(None, self.ev(self.s.facilitator, "l1-clone", "n5"))
        self.s.event(None, self.ev("a", "l1-clone", "n5"))      # the same nonce, now for a student
        self.assertIn("l1-clone", self.s.ledger.unlocked_ids("a"))

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

    def test_wall_of_shame_tracks_live_then_disconnected_then_ages_off(self):
        self.s.adapter({"source": "ctf", "event": "dump_success", "user": "alice", "challenge": "customer-portal"})
        rows = self.s.wall_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["challenge"], rows[0]["state"]), ("customer-portal", "LIVE"))
        self.assertNotIn("alice", json.dumps(rows))  # anonymous by default, like the board
        self.clock.t += self.s.WALL_LIVE_WINDOW + 1
        self.assertEqual(self.s.wall_rows()[0]["state"], "DISCONNECTED")
        self.clock.t += self.s.WALL_MAX_AGE
        self.assertEqual(self.s.wall_rows(), [])

    def test_wall_of_shame_is_not_anonymous_when_the_board_is_not(self):
        self.mk(anonymous=False)
        self.s.adapter({"source": "ctf", "event": "dump_success", "user": "alice", "challenge": "c"})
        self.assertEqual(self.s.wall_rows()[0]["user"], "alice")

    def test_soc_alerts_land_on_the_student_and_room_feeds(self):
        self.s.adapter({"source": "soc", "event": "probe", "user": "alice", "challenge": "c",
                        "persona": "alice", "origin": "RU"})
        self.assertEqual(len(self.s.soc_rows("alice")), 1)
        self.assertEqual(self.s.soc_rows("alice")[0]["severity"], "WARN")
        self.assertEqual(self.s.soc_rows("bob"), [])          # not alice's own feed
        self.assertEqual(len(self.s.admin_soc_rows()), 1)     # but it IS on the room-wide one

    def test_soc_severity_is_derived_not_trusted(self):
        self.s.adapter({"source": "soc", "event": "exploit_attempt", "user": "alice",
                        "severity": "INFO"})   # a poster can't downgrade its own severity
        self.assertEqual(self.s.soc_rows("alice")[0]["severity"], "CRITICAL")

    def test_soc_timer_waits_until_the_facilitator_starts_it(self):
        self.mk(soc_dwell_seconds=100, soc_ramp_seconds=200)
        self.assertEqual(self.s.soc_timer(), {"phase": "waiting", "seconds_remaining": None, "started_at": None})
        self.clock.t += 99999   # waiting forever doesn't advance anything on its own
        self.assertEqual(self.s.soc_timer()["phase"], "waiting")

    def test_admin_soc_start_is_idempotent(self):
        self.mk(soc_dwell_seconds=100, soc_ramp_seconds=200)
        first = self.s.admin_soc_start()
        self.clock.t += 50
        second = self.s.admin_soc_start()    # a second click doesn't reset the clock
        self.assertEqual(first, second)

    def test_soc_timer_green_then_yellow_then_red_once_started(self):
        self.mk(soc_dwell_seconds=100, soc_ramp_seconds=200)
        start = self.s.admin_soc_start()["started_at"]
        self.assertEqual(self.s.soc_timer(), {"phase": "green", "seconds_remaining": 300, "started_at": start})
        self.clock.t += 101
        self.assertEqual(self.s.soc_timer()["phase"], "yellow")
        self.clock.t += 200
        self.assertEqual(self.s.soc_timer(), {"phase": "red", "seconds_remaining": 0, "started_at": start})
        self.clock.t += 99999
        self.assertEqual(self.s.soc_timer(), {"phase": "red", "seconds_remaining": 0, "started_at": start})

    def test_admin_soc_reset_rearms_the_countdown(self):
        self.mk(soc_dwell_seconds=100, soc_ramp_seconds=200)
        self.s.admin_soc_start()
        self.clock.t += 150
        self.assertEqual(self.s.soc_timer()["phase"], "yellow")
        self.s.admin_soc_reset()
        self.assertEqual(self.s.soc_timer()["phase"], "waiting")
        restarted = self.s.admin_soc_start()["started_at"]
        self.assertEqual(restarted, self.clock.t)   # a fresh clock, not the old one

    def test_target_status_green_until_breached(self):
        self.assertEqual(self.s.target_statuses(), [])

    def test_target_status_turns_red_on_breach_then_yellow_once_contained(self):
        self.s.adapter({"source": "ctf", "event": "dump_success", "user": "alice", "challenge": "c"})
        rows = self.s.target_statuses()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "red")
        self.assertIsNone(rows[0]["mttp"])
        self.clock.t += 30
        self.s.adapter({"source": "soc", "event": "contained", "user": "alice", "challenge": "c"})
        rows = self.s.target_statuses()
        self.assertEqual(rows[0]["status"], "yellow")
        self.assertEqual(rows[0]["mttp"], 30)

    def test_target_status_never_goes_back_to_red_once_yellow(self):
        self.s.adapter({"source": "ctf", "event": "dump_success", "user": "alice", "challenge": "c"})
        self.s.adapter({"source": "soc", "event": "contained", "user": "alice", "challenge": "c"})
        self.s.adapter({"source": "ctf", "event": "dump_success", "user": "alice", "challenge": "c"})
        rows = self.s.target_statuses()
        self.assertEqual(rows[0]["status"], "yellow")
        self.assertEqual(rows[0]["retries"], 1)

    def test_a_fix_on_a_never_breached_target_is_a_no_op(self):
        self.s.adapter({"source": "soc", "event": "contained", "user": "alice", "challenge": "c"})
        self.assertEqual(self.s.target_statuses(), [])

    def test_mttp_summary_only_counts_fixed_targets(self):
        self.s.adapter({"source": "ctf", "event": "dump_success", "user": "alice", "challenge": "c"})
        self.assertEqual(self.s.mttp_summary(), [])      # still red: no time yet
        self.clock.t += 40
        self.s.adapter({"source": "soc", "event": "contained", "user": "alice", "challenge": "c"})
        self.assertEqual(self.s.mttp_summary(), [{"user": self.s._label("alice"), "mttp": 40}])

    def test_map_data_has_arcs_top_and_breaches(self):
        self.s.adapter({"source": "soc", "event": "probe", "user": "alice", "challenge": "c",
                        "persona": "alice", "origin": "RU"})
        self.s.adapter({"source": "ctf", "event": "dump_success", "user": "alice", "challenge": "c"})
        data = self.s.map_data()
        self.assertEqual([a["event"] for a in data["arcs"]], ["probe", "dump_success"])  # breaches are feed rows too
        self.assertEqual(data["top"], [{"user": self.s._label("alice"), "challenge": "c", "hits": 2}])
        self.assertEqual(len(data["breaches"]), 1)
        self.assertEqual(data["breaches"][0]["status"], "red")
        self.assertIn("timer", data)

    def test_map_breach_stays_listed_while_red_but_stops_being_recent(self):
        self.s.adapter({"source": "ctf", "event": "dump_success", "user": "alice", "challenge": "c"})
        self.assertTrue(self.s.map_data()["breaches"][0]["recent"])
        self.clock.t += self.s.MAP_WINDOW + 1
        b = self.s.map_data()["breaches"]
        self.assertEqual((len(b), b[0]["recent"]), (1, False))
        self.s.adapter({"source": "soc", "event": "contained", "user": "alice", "challenge": "c"})
        self.clock.t += self.s.MAP_WINDOW + 1
        self.assertEqual(self.s.map_data()["breaches"], [])      # patched and old: gone

    def test_dump_success_streams_into_the_feed_throttled_and_counts_for_siege(self):
        ev = {"source": "ctf", "event": "dump_success", "user": "alice", "challenge": "c", "origin": "CN"}
        for _ in range(10):
            self.s.adapter(ev)
            self.clock.t += 2
        rows = self.s.admin_soc_rows()
        self.assertEqual([r["severity"] for r in rows], ["BREACH"] * len(rows))
        self.assertTrue(0 < len(rows) < 10)
        self.assertEqual(self.s.map_data()["top"][0]["hits"], 10)    # every dump counts, rows or not

    def test_map_windows_follow_the_time_scale(self):
        self.s.time_scale = 0.1
        self.s.adapter({"source": "soc", "event": "probe", "user": "alice", "challenge": "c"})
        self.assertEqual(self.s.map_data()["window"], 12)
        self.clock.t += 13
        self.assertEqual(self.s.map_data()["top"], [])

    def test_map_shows_every_student_at_the_home_fallback(self):
        self.s.me("alice"); self.s.me("bob")
        self.s.regions["alice"] = {"lat": 1.0, "lon": 2.0, "place": "Somewhere", "src": "admin"}
        st = {r["user"]: r for r in self.s.map_data()["students"]}
        self.assertEqual(len(st), 2)
        self.assertEqual(st[self.s._label("alice")]["place"], "Somewhere")
        self.assertEqual(st[self.s._label("bob")]["src"], "default")
        self.assertNotIn("id", next(iter(st.values())))

    def test_incident_is_the_students_own_timeline_and_status(self):
        self.s.adapter({"source": "soc", "event": "probe", "user": "alice", "challenge": "c",
                        "persona": "alice", "origin": "RU"})
        self.s.adapter({"source": "ctf", "event": "dump_success", "user": "alice", "challenge": "c"})
        doc = self.s.incident("alice")
        self.assertEqual(doc["user"], self.s._label("alice"))
        self.assertEqual([r["event"] for r in doc["timeline"]], ["dump_success", "probe"])   # newest first
        self.assertEqual(doc["targets"][0]["status"], "red")

    def test_admin_incident_needs_a_known_student(self):
        with self.assertRaises(Denied) as e:
            self.s.admin_incident("nobody")
        self.assertEqual(e.exception.code, 404)
        self.s.me("alice")
        self.assertEqual(self.s.admin_incident("alice")["targets"], [])

    def test_admin_soc_inject_and_hint_need_a_known_student(self):
        with self.assertRaises(Denied) as e:
            self.s.admin_soc_inject("nobody")
        self.assertEqual(e.exception.code, 404)
        self.s.me("alice")
        self.s.admin_soc_inject("alice")
        self.s.admin_soc_hint("all")
        self.assertEqual(self.s.soc_control()["commands"],
                         [{"type": "inject", "user": "alice"}, {"type": "hint", "user": None}])

    def test_soc_control_pops_commands_at_most_once(self):
        self.s.me("alice")
        self.s.admin_soc_inject("alice")
        self.assertEqual(len(self.s.soc_control()["commands"]), 1)
        self.assertEqual(self.s.soc_control()["commands"], [])

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

    def test_activity_survives_a_restart(self):
        self.s.shell("a", {"cmd": "git clone http://x/y.git", "exit": 0})    # unlocks: saved
        self.clock.t += 5
        self.s.shell("a", {"cmd": "ls", "exit": 1})                         # within 30 s: not saved yet
        self.clock.t += 40
        self.s.shell("a", {"cmd": "ls", "exit": 1})                         # 30 s on: saved
        self.mk()
        a = self.s.activity_snapshot()["a"]
        self.assertEqual((a["streak"], a["cmds"], a["fails"], a["since_cmd"]), (2, 3, 2, 0))

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


class SaveTests(unittest.TestCase):
    """RV2: polls don't write, a burst of changes is one write off the request path, and
    flush() (SIGTERM) writes whatever the writer hasn't yet."""
    tearDown, mk = StoreTests.tearDown, StoreTests.mk
    ev = StoreTests.ev

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.clock = Clock()

    def count_writes(self):
        writes = []
        real = self.s._write
        self.s._write = lambda text: (writes.append(text), real(text))
        return writes

    def saved_score(self, user):
        return Store(load(), lg.Config(), self.dir, "secret", facilitator="boss", clock=self.clock).me(user)["score"]

    def test_polls_write_only_when_they_register_someone(self):
        self.mk()
        writes = self.count_writes()
        self.s.me("a")
        self.s.board("b")
        self.assertEqual(len(writes), 2)        # each registered a new student
        for _ in range(50):
            self.s.me("a")
            self.s.board("a")
        self.assertEqual(len(writes), 2)

    def test_a_burst_is_one_write_soon_after(self):
        self.mk(save_delay=0.3)
        time.sleep(0.4)                          # the start-up write
        writes = self.count_writes()
        self.s.event(None, self.ev("a", "l1-clone"))
        for n in range(20):
            self.s.me(f"s{n}")                   # each registers someone: a change
            self.s.me("a")
        self.assertEqual(writes, [])             # nothing written on the request path
        deadline = time.monotonic() + 3
        while not writes and time.monotonic() < deadline:
            time.sleep(0.05)
        time.sleep(0.4)
        self.assertEqual(len(writes), 1)
        self.assertEqual(self.saved_score("a"), 10)

    def test_flush_writes_what_is_pending(self):
        self.mk(save_delay=60)
        time.sleep(0.2)                          # the start-up write; the next one would wait 60 s
        self.s.event(None, self.ev("a", "l1-clone"))
        self.assertEqual(self.saved_score("a"), 0)
        self.assertTrue(self.s.flush())
        self.assertFalse(self.s.flush())         # nothing new
        self.assertEqual(self.saved_score("a"), 10)

    def test_flush_keeps_the_last_commands_activity(self):
        self.mk(save_delay=60)
        time.sleep(0.2)
        fail = {"cmd": "git push origin nope", "exit": 1}  # unlocks nothing
        self.s.shell("a", fail)                  # registers "a": a change of its own
        self.s.flush()
        for _ in range(4):                       # the stuck radar's "failing" needs 5 in a row
            self.s.shell("a", fail)
        self.s.flush()
        again = Store(load(), lg.Config(), self.dir, "secret", facilitator="boss", clock=self.clock)
        self.assertEqual(again.activity_snapshot()["a"]["streak"], 5)

    def test_failed_write_stays_dirty(self):
        self.mk(save_delay=60)
        time.sleep(0.2)
        self.s.me("a")
        self.s._write = mock.Mock(side_effect=OSError("disk full"))
        with self.assertRaises(OSError):
            self.s.flush()
        del self.s._write
        self.assertTrue(self.s.flush())

    def test_sigterm_flushes_the_running_service(self):
        """The real server process: a change, then SIGTERM well before the writer's next turn."""
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        env = dict(os.environ, DATA_DIR=self.dir, PORT=str(port), WORKSHOP_DIR=WORKSHOP,
                   GATEWAY_TOKEN="gw-test", FORGEJO_ADMIN_USER="", FORGEJO_ADMIN_PASSWORD="")
        proc = subprocess.Popen([sys.executable, "-B", "-c", "import server; server.SAVE_DELAY = 60; server.main()"],
                                cwd=HERE, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(proc.kill)
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/me",
                                     headers={"X-Gateway-Token": "gw-test", "X-Auth-User": "student07"})
        deadline = time.monotonic() + 10
        while True:
            try:
                urllib.request.urlopen(req, timeout=2).read()
                break
            except OSError:
                if time.monotonic() > deadline:
                    self.fail("the service never answered")
                time.sleep(0.1)
        with open(os.path.join(self.dir, "state.json")) as f:
            self.assertNotIn("student07", f.read())     # the writer waits 60 s
        proc.send_signal(signal.SIGTERM)
        self.assertEqual(proc.wait(timeout=10), 0)
        with open(os.path.join(self.dir, "state.json")) as f:
            self.assertIn("student07", json.load(f)["ledger"]["users"])


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

    def test_soc_control_poll_needs_the_shared_secret_too(self):
        import hashlib
        import hmac
        server.ADAPTER_SECRET = "adapt"
        try:
            raw = b"{}"

            def poll(sig):
                c = http.client.HTTPConnection("127.0.0.1", self.port)
                c.request("POST", "/api/soc/control", body=raw, headers={"X-Adapter-Signature": sig})
                r = c.getresponse()
                out = (r.status, json.loads(r.read()))
                c.close()
                return out
            self.assertEqual(poll("0" * 64)[0], 403)
            status, doc = poll(hmac.new(b"adapt", raw, hashlib.sha256).hexdigest())
            self.assertEqual((status, doc["phase"]), (200, "waiting"))   # nothing started it yet
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
            self.assertIn("hotfix", doc["constraints"])
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

    def test_student_reset_hooks(self):
        st = server.store
        st.ledger.unlock("rita", "l1-clone", 5)
        st.seeds["rita"] = {"x.json": {"repo": "rita/x"}}
        st.stepped["rita"] = {"capstone": 5.0}
        hdr = {"X-Dojo-Reset-Token": "rt"}
        server.RESET_TOKEN = "rt"
        try:
            self.assertEqual(self.call("POST", "/_dojo/reset/progress/rita?phase=teardown")[0], 403)
            self.assertEqual(self.call("POST", "/_dojo/reset/progress/rita?phase=teardown",
                                       extra={"X-Dojo-Reset-Token": "nope"})[0], 403)
            self.assertEqual(self.call("POST", "/_dojo/reset/other/rita?phase=teardown", extra=hdr)[0], 404)
            self.assertEqual(self.call("POST", "/_dojo/reset/progress/rita?phase=x", extra=hdr)[0], 404)
            self.assertEqual(self.call("POST", "/_dojo/reset/progress/boss?phase=teardown", extra=hdr)[0], 400)
            code, doc, _ = self.call("POST", "/_dojo/reset/progress/rita?phase=teardown", extra=hdr)
            self.assertEqual((code, doc["ok"]), (200, True))
            self.assertNotIn("rita", st.seeds)
            self.assertNotIn("rita", st.stepped)
            self.assertIn("l1-clone", st.ledger.unlocked_ids("rita"))           # score kept unless asked
            self.assertEqual(self.call("POST", "/_dojo/reset/score/rita?phase=provision", extra=hdr)[0], 200)
            self.assertIn("l1-clone", st.ledger.unlocked_ids("rita"))           # provision does nothing
            code, doc, _ = self.call("POST", "/_dojo/reset/score/rita?phase=teardown", extra=hdr)
            self.assertEqual(doc["detail"], "achievements and score cleared")
            self.assertNotIn("l1-clone", st.ledger.unlocked_ids("rita"))
            self.assertEqual(self.call("POST", "/_dojo/reset/score/rita?phase=teardown", extra=hdr)[1]["detail"],
                             "no achievements to clear")                      # runs again safely
        finally:
            server.RESET_TOKEN = ""
        self.assertEqual(self.call("POST", "/_dojo/reset/score/rita?phase=teardown", extra=hdr)[0], 403)  # unset: off

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

    def test_soc_start_and_reset_need_the_facilitator(self):
        hdr = {"X-Requested-With": "dojo-admin"}
        self.assertEqual(self.call("GET", "/api/soc", user="alice")[1]["timer"]["phase"], "waiting")
        self.assertEqual(self.call("POST", "/achievements-admin/api/soc/start", user="alice", extra=hdr)[0], 403)
        self.assertEqual(self.call("POST", "/achievements-admin/api/soc/start", user="boss")[0], 403)   # no header
        st, doc, _ = self.call("POST", "/achievements-admin/api/soc/start", user="boss", extra=hdr)
        self.assertEqual(st, 200)
        self.assertIsNotNone(doc["started_at"])
        self.assertEqual(self.call("GET", "/api/soc", user="alice")[1]["timer"]["phase"], "green")
        # idempotent: a second click doesn't reset the clock
        st, doc2, _ = self.call("POST", "/achievements-admin/api/soc/start", user="boss", extra=hdr)
        self.assertEqual(doc2["started_at"], doc["started_at"])
        self.assertEqual(self.call("POST", "/achievements-admin/api/soc/reset", user="alice", extra=hdr)[0], 403)
        self.assertEqual(self.call("POST", "/achievements-admin/api/soc/reset", user="boss", extra=hdr)[0], 200)
        self.assertEqual(self.call("GET", "/api/soc", user="alice")[1]["timer"]["phase"], "waiting")

    def test_soc_inject_and_hint_need_the_facilitator_and_a_known_student(self):
        hdr = {"X-Requested-With": "dojo-admin"}
        self.call("GET", "/api/me", user="dana")     # registers dana
        self.assertEqual(self.call("POST", "/achievements-admin/api/soc/inject",
                                   user="dana", extra=hdr, body={"user": "dana"})[0], 403)
        self.assertEqual(self.call("POST", "/achievements-admin/api/soc/inject",
                                   user="boss", body={"user": "dana"})[0], 403)   # no header
        self.assertEqual(self.call("POST", "/achievements-admin/api/soc/inject",
                                   user="boss", extra=hdr, body={"user": "nobody"})[0], 404)
        self.assertEqual(self.call("POST", "/achievements-admin/api/soc/inject",
                                   user="boss", extra=hdr, body={"user": "dana"})[0], 200)
        self.assertEqual(self.call("POST", "/achievements-admin/api/soc/hint",
                                   user="boss", extra=hdr, body={"user": "all"})[0], 200)

    def test_map_and_incident_routes(self):
        self.call("GET", "/api/me", user="erin")
        self.assertEqual(self.call("GET", "/api/map", user="erin")[1]["top"], [])
        st, doc, _ = self.call("GET", "/api/incident", user="erin")
        self.assertEqual((st, doc["targets"]), (200, []))
        st, doc, _ = self.call("GET", "/api/incident", user="boss")      # facilitator on the student page
        self.assertEqual((st, doc["targets"], doc["timeline"]), (200, [], []))
        self.assertEqual(self.call("GET", "/achievements-admin/api/incident?user=nobody", user="boss")[0], 404)
        self.assertEqual(self.call("GET", "/achievements-admin/api/incident?user=erin", user="boss")[0], 200)
        self.assertEqual(self.call("GET", "/achievements-admin/api/map", user="boss")[0], 200)

    def test_old_map_and_incident_pages_redirect_to_the_one_page_soc(self):
        for path, user, want in (("/map", "erin", "soc"), ("/incident", "erin", "soc"),
                                 ("/achievements-admin/map", "boss", "soc"),
                                 ("/achievements-admin/incident?user=erin", "boss", "soc?user=erin")):
            st, _, r = self.call("GET", path, user=user)
            self.assertEqual((st, r.getheader("Location")), (302, want), path)
        self.assertEqual(self.call("GET", "/soc", user="erin")[0], 200)
        self.assertEqual(self.call("GET", "/achievements-admin/soc", user="boss")[0], 200)
        for asset in ("/map.js", "/mapdata.js", "/dash.css", "/soc.js"):
            self.assertEqual(self.call("GET", asset, user="erin")[0], 200, asset)

    def test_student_region_comes_from_the_forwarded_address_only_behind_the_gateway_token(self):
        import test_geo
        import geo
        server.store.locator = geo.Locator(reader=geo.Reader(test_geo.DB), home="toronto")
        ip = "24.80.10.5"
        # no gateway token: identity headers are someone else's name, and no address is read
        self.call("GET", "/api/map", user="mallory", token="wrong", extra={"X-Forwarded-For": ip})
        self.assertNotIn("mallory", server.store.regions)
        # with the token, the right-most public address picks the region; a forged left entry does not
        self.call("GET", "/api/me", user="vera", extra={"X-Forwarded-For": "99.250.10.1, " + ip + ", 172.19.0.2"})
        self.assertEqual(server.store.regions["vera"]["place"], "Vancouver, CA")
        # a private-only address (WSL, a LAN) uses the home region
        self.call("GET", "/api/me", user="wes", extra={"X-Forwarded-For": "172.19.0.4"})
        self.assertEqual((server.store.regions["wes"]["src"], server.store.regions["wes"]["place"]), ("default", "Toronto, ON"))
        # the facilitator has no map point
        self.call("GET", "/api/me", user="boss", extra={"X-Forwarded-For": ip})
        self.assertNotIn("boss", server.store.regions)
        # the address appears nowhere a student, the facilitator or the disk can read it
        server.store.flush()
        with open(os.path.join(self.dir, "state.json")) as f:
            on_disk = f.read()
        pages = [json.dumps(self.call("GET", "/api/map", user="vera")[1]),
                 json.dumps(self.call("GET", "/achievements-admin/api/map", user="boss")[1]),
                 json.dumps(self.call("GET", "/achievements-admin/api/state", user="boss")[1]), on_disk]
        for text in pages:
            for frag in (ip, "99.250.10", "172.19.0"):
                self.assertNotIn(frag, text)
        mp = self.call("GET", "/api/map", user="vera")[1]["students"]
        self.assertTrue(all(set(s) == {"user", "lat", "lon", "place", "src"} for s in mp))
        server.store.locator = None

    def test_admin_region_override(self):
        import geo
        server.store.locator = geo.Locator(home="toronto")
        hdr = {"X-Requested-With": "dojo-admin"}
        self.call("GET", "/api/me", user="xena", extra={"X-Forwarded-For": "172.19.0.4"})
        path = "/achievements-admin/api/region"
        self.assertEqual(self.call("POST", path, user="xena", extra=hdr, body={"user": "xena", "region": "Vancouver"})[0], 403)
        self.assertEqual(self.call("POST", path, user="boss", extra=hdr, body={"user": "nobody", "region": "Vancouver"})[0], 404)
        self.assertEqual(self.call("POST", path, user="boss", extra=hdr, body={"user": "xena", "region": "Atlantis"})[0], 400)
        self.assertEqual(self.call("POST", path, user="boss", extra=hdr, body={"user": "xena", "region": "Vancouver"})[0], 200)
        self.call("GET", "/api/map", user="xena", extra={"X-Forwarded-For": "172.19.0.4"})
        self.assertEqual(server.store.regions["xena"]["place"], "Vancouver, BC")      # not replaced by a later lookup
        admin = [s for s in self.call("GET", "/achievements-admin/api/map", user="boss")[1]["students"] if s["id"] == "xena"]
        self.assertEqual(admin[0]["place"], "Vancouver, BC")
        self.assertEqual(self.call("POST", path, user="boss", extra=hdr, body={"user": "xena", "region": ""})[0], 200)
        self.assertNotIn("xena", server.store.regions)
        server.store.locator = None

    def test_time_scale(self):
        self.assertEqual(server.time_scale({}), 1.0)
        self.assertEqual(server.time_scale({"CTF_TIME_SCALE": "0.1"}), 0.1)
        for bad in ("x", "0", "-2", "500"):
            self.assertEqual(server.time_scale({"CTF_TIME_SCALE": bad}), 1.0)

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
