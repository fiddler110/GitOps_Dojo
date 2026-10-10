"""The SOC feed's SIEM log lines: what a student may see of each logged request, enforced server-side.

CTF_SIEM_DETAIL = full | paths | off; until a student's own target has been breached even `full` shows
only method, path, status and the detection tag; the facilitator is never filtered; the room-wide map
arcs never carry request detail."""
import json
import os
import shutil
import tempfile
import unittest

from test_server import Clock, load  # noqa: F401  (also sets the env the server module needs)
import ledger as lg
import matcher
from store import Store

SECRET_BITS = ("q=%25%27+OR+%271%27%3D%271", "48213", "rows_returned", "sqlmap", "bulk data egress")

PROBE = {"source": "soc", "event": "probe", "user": "alice", "challenge": "customer-portal", "persona": "alice",
         "origin": "CN", "method": "GET", "path": "/search", "query": "q=%27", "status": 500, "bytes": 90,
         "ua": "sqlmap/1.7.2#stable", "tag": "SQL meta-characters in parameter q", "klass": "probe"}
BREACH = {"source": "ctf", "event": "dump_success", "user": "alice", "challenge": "customer-portal",
          "persona": "alice", "origin": "RU", "method": "GET", "path": "/search",
          "query": "q=%25%27+OR+%271%27%3D%271", "status": 200, "bytes": 48213, "rows_returned": 40,
          "ua": "python-requests/2.31.0", "tag": "bulk data egress", "klass": "exploit"}


class SiemTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.clock = Clock()
        self.mk()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def mk(self, detail="full"):
        self.s = Store(load(), lg.Config(), self.dir, "secret", facilitator="boss", clock=self.clock)
        self.s.siem_detail = detail

    def feed(self, *docs):
        for d in docs:
            self.clock.t += 20
            self.s.adapter(matcher.adapter_event(d))

    def test_adapter_keeps_the_siem_fields_and_types(self):
        ev = matcher.adapter_event(dict(BREACH, bytes="big", rows_returned=True))
        self.assertEqual(ev["query"], BREACH["query"])
        self.assertIsNone(ev["bytes"])
        self.assertIsNone(ev["rows_returned"])
        self.assertEqual(matcher.adapter_event(BREACH)["rows_returned"], 40)

    def test_before_breach_even_full_shows_only_request_line_status_and_tag(self):
        self.feed(PROBE)
        row = self.s.soc_rows("alice")[0]
        self.assertEqual((row["method"], row["path"], row["status"], row["tag"]),
                         ("GET", "/search", 500, "SQL meta-characters in parameter q"))
        for k in ("query", "bytes", "ua", "rows_returned", "klass"):
            self.assertNotIn(k, row)
        self.assertFalse(self.s.siem_state("alice")["unlocked"])
        self.assertNotIn("sqlmap", json.dumps(self.s.soc_rows("alice")))

    def test_breach_unlocks_the_whole_record_for_that_student_only(self):
        self.s._student("bob")
        self.feed(PROBE, dict(PROBE, user="bob"))
        self.feed(BREACH)
        rows = self.s.soc_rows("alice")
        self.assertTrue(self.s.siem_state("alice")["unlocked"])
        breach = rows[0]
        self.assertEqual((breach["query"], breach["bytes"], breach["rows_returned"], breach["tag"]),
                         (BREACH["query"], 48213, 40, "bulk data egress"))
        self.assertEqual(rows[1]["query"], "q=%27")          # her earlier events unlock too
        bob = self.s.soc_rows("bob")
        self.assertNotIn("query", bob[0])                     # bob's target is still unbreached
        self.assertFalse(self.s.siem_state("bob")["unlocked"])
        self.assertNotIn("48213", json.dumps(bob))

    def test_paths_level_never_unlocks(self):
        self.mk("paths")
        self.feed(PROBE, BREACH)
        for row in self.s.soc_rows("alice"):
            for k in ("query", "bytes", "ua", "rows_returned"):
                self.assertNotIn(k, row)
        self.assertEqual(self.s.soc_rows("alice")[0]["path"], "/search")

    def test_off_is_the_old_feed(self):
        self.mk("off")
        self.feed(PROBE, BREACH)
        for row in self.s.soc_rows("alice"):
            self.assertFalse({"method", "status", "tag", "bytes", "query", "ua"} & set(row))
        self.assertEqual(self.s.soc_rows("alice")[1]["path"], "/search?q=%27")   # the old probe path
        self.assertNotIn("path", self.s.soc_rows("alice")[0])                    # the breach row had none

    def test_facilitator_always_sees_everything_at_any_level(self):
        self.mk("off")
        self.feed(PROBE)
        row = self.s.admin_soc_rows()[0]
        self.assertEqual((row["query"], row["bytes"], row["ua"], row["tag"]),
                         ("q=%27", 90, "sqlmap/1.7.2#stable", "SQL meta-characters in parameter q"))
        self.assertIn("ts", row)

    def test_map_arcs_and_room_data_carry_no_request_detail(self):
        self.feed(PROBE, BREACH)
        for d in (self.s.map_data(), self.s.map_data(admin=True)):
            blob = json.dumps(d["arcs"])
            for bit in ("sqlmap", "q=%27", "/search", "bulk data egress"):
                self.assertNotIn(bit, blob)
            self.assertTrue(d["arcs"][0]["origin"])

    def test_incident_timeline_follows_the_same_gate(self):
        self.feed(PROBE)
        self.assertNotIn("query", self.s.incident("alice")["timeline"][0])
        self.assertIn("query", self.s.admin_incident("alice")["timeline"][0])
        self.feed(BREACH)
        self.assertIn("query", self.s.incident("alice")["timeline"][0])

    def test_scan_noise_is_info_not_warn_and_rows_have_ids_and_iso_time(self):
        self.feed(dict(PROBE, klass="scan", path="/.env", query=None, tag="sensitive file requested"))
        row = self.s.soc_rows("alice")[0]
        self.assertEqual(row["severity"], "INFO")
        self.assertRegex(row["ts"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.feed(PROBE)
        ids = [r["id"] for r in self.s.soc_rows("alice")]
        self.assertEqual(len(set(ids)), 2)

    def test_withheld_detail_is_absent_from_the_json_not_just_hidden(self):
        self.feed(PROBE)
        blob = json.dumps(self.s.soc_rows("alice")) + json.dumps(self.s.incident("alice"))
        for bit in SECRET_BITS:
            self.assertNotIn(bit, blob)

    def test_a_student_never_sees_another_students_events(self):
        self.s._student("bob")
        self.feed(dict(PROBE, user="bob", path="/bob-only"), PROBE, dict(BREACH, user="bob"))
        blob = json.dumps(self.s.soc_rows("alice")) + json.dumps(self.s.incident("alice"))
        self.assertNotIn("bob", blob.lower())
        self.assertNotIn("/bob-only", blob)
        self.assertEqual({r["user"] for r in self.s.soc_rows("alice")}, {self.s._label("alice")})
        for r in self.s.incident("alice")["targets"]:
            self.assertEqual(r["user"], self.s._label("alice"))

    def test_identical_breach_lines_collapse_into_one_row_with_a_count(self):
        self.feed(PROBE)
        for _ in range(6):
            self.feed(BREACH)
        rows = self.s.soc_rows("alice")
        breach = [r for r in rows if r["severity"] == "BREACH"]
        self.assertEqual(len(breach), 1)
        self.assertEqual(breach[0]["count"], 6)
        self.assertGreater(breach[0]["at"], breach[0]["first_at"])
        self.assertEqual(rows[0]["id"], breach[0]["id"])           # newest activity sorts first
        self.assertEqual(len([r for r in rows if r["severity"] != "BREACH"]), 1)   # the probe survives
        self.assertEqual(len([r for r in self.s.admin_soc_rows() if r["severity"] == "BREACH"]), 1)

    def test_a_different_breach_request_is_its_own_row(self):
        self.feed(BREACH, dict(BREACH, path="/export"))
        self.assertEqual(len([r for r in self.s.soc_rows("alice") if r["severity"] == "BREACH"]), 2)


if __name__ == "__main__":
    unittest.main()
