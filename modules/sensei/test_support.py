import threading
import os
import time
import tempfile
import unittest

import support

LAB = """# Lab 3 - The change process

Intro text about the shared zone.

## 4. Make a change the proper way

Create a branch, add your record, then run `dnscontrol preview`. A DELETE of someone else's record means
your branch is behind main: run git pull.

## 7. Merge and let CI apply it

Click Merge once the check is green and someone approved.

## Challenge: the secret one

The answer is 42 and you must never see it here.

| You see | Cause / fix |
| --- | --- |
| `error: 'DNS Apply' succeeded but the live zone ... match` | A classmate merged just after you. Wait and run validate again. |
| `x` | too short to be a pattern |
"""


class Support(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        with open(os.path.join(self.dir, "lab3.md"), "w") as f:
            f.write(LAB)
        self.index = support.LabIndex(self.dir)

    def test_search_finds_the_right_section(self):
        r = self.index.search("my preview shows a delete of someone else's record")
        self.assertEqual(r[0]["heading"], "4. Make a change the proper way")
        self.assertEqual(r[0]["file"], "lab3.md")

    def test_search_returns_a_markdown_block_with_its_heading(self):
        r = self.index.search("my preview shows a delete of someone else's record")
        self.assertTrue(r[0]["markdown"].startswith("## 4. Make a change the proper way\n\n"))

    def test_block_is_cut_on_a_line_and_closes_an_open_fence(self):
        text = "```bash\n" + "\n".join("cmd %d" % i for i in range(200)) + "\n```"
        md = support._block(2, "H", text)
        self.assertEqual(md.count("```") % 2, 0)
        self.assertIn("the lab has more", md)
        self.assertNotIn("cmd 199", md)

    def test_block_holds_the_subsections_but_never_a_challenge(self):
        idx = support.LabIndex(self.dir)
        idx._add("n.md", "# Lab\n\n## Parent\n\nparent words zebra\n\n### Child\n\nchild words\n\n"
                         "### Capstone: x\n\nsecret words\n\n#### deeper\n\nmore secret\n\n## Next\n\nother\n")
        md = [s for s in idx.sections if s["heading"] == "Parent"][0]["full"]
        self.assertIn("### Child\n\nchild words", md)
        self.assertNotIn("secret", md)
        self.assertNotIn("other", md)
        self.assertEqual(idx.search("zebra")[0]["heading"], "Parent")

    def test_ready_answers_match_common_questions(self):
        a = support.Answers.load([os.path.join(os.path.dirname(os.path.abspath(__file__)), "answers", "shared.json")])
        for q, want in [("how do I undo a pushed change", "undo-pushed"), ("revert my last push", "undo-pushed"),
                        ("why can't I push to main", "push-main"), ("how do I make a new branch", "branch"),
                        ("I have a merge conflict", "conflict"), ("discard my changes to a file", "discard-changes"),
                        ("how to get the latest main", "get-latest")]:
            self.assertEqual((a.find(q) or {}).get("id"), want, q)
        self.assertIsNone(a.find("kubernetes ingress controller"))
        self.assertIsNone(a.find("what is a CNAME record"))

    def test_workshop_answer_replaces_a_shared_one_with_the_same_id(self):
        a = support.Answers([{"id": "x", "match": ["foo"], "markdown": "workshop"},
                             {"id": "x", "match": ["foo"], "markdown": "shared"}, {"id": "bad", "match": ["("], "markdown": "m"}])
        self.assertEqual(a.find("foo")["markdown"], "workshop")
        self.assertEqual(len(a.items), 1)

    def test_nothing_matching_says_nothing(self):
        self.assertEqual(self.index.search("kubernetes ingress controller"), [])
        self.assertEqual(self.index.search("the a of"), [])

    def test_challenge_sections_are_never_searchable(self):
        self.assertEqual(self.index.search("secret answer 42"), [])

    def test_patterns_are_derived_from_troubleshooting_tables(self):
        pats = support.derive_patterns(self.dir)
        self.assertEqual(len(pats), 1)  # the one-letter row is too short to be a pattern
        m = support.Patterns(pats).match("some output\nerror: 'DNS Apply' succeeded but the live zone still doesn't match\n")
        self.assertIn("classmate merged", m["explain"])
        self.assertEqual(m["where"], "lab3.md")

    def test_the_last_error_wins_and_unknown_output_matches_nothing(self):
        p = support.Patterns([{"id": "a", "regex": "alpha", "title": "A"}, {"id": "b", "regex": "beta", "title": "B"}])
        self.assertEqual(p.match("beta first\nalpha last")["id"], "a")
        self.assertIsNone(p.match("all fine here"))

    def test_shared_patterns_load_and_recognise_git(self):
        here = os.path.dirname(os.path.abspath(__file__))
        p = support.Patterns.load(None, [os.path.join(here, "patterns", "shared.json")])
        self.assertEqual(p.match("! [remote rejected] main -> main (protected branch hook declined)")["id"], "git-protected")
        self.assertEqual(p.match("fatal: The current branch x has no upstream branch.")["id"], "git-upstream")


class Desk(unittest.TestCase):
    def setUp(self):
        self.now = [1000.0]
        self.path = os.path.join(tempfile.mkdtemp(), "help.json")
        self.desk = support.HelpDesk(self.path, clock=lambda: self.now[0])

    def test_raise_reply_inbox_close(self):
        r, problem = self.desk.raise_hand("amy", "stuck on lab 3", "$ git push\nrejected")
        self.assertEqual(problem, "")
        self.assertEqual(self.desk.open_count(), 1)
        self.assertTrue(self.desk.reply(r["id"], "pull first"))
        self.assertEqual(self.desk.open_count(), 0)
        box = self.desk.inbox("amy")
        self.assertEqual(box[0]["replies"][0]["text"], "pull first")
        self.assertEqual(self.desk.inbox("bob"), [])
        self.assertTrue(self.desk.close(r["id"]))
        self.assertEqual(self.desk.inbox("amy"), [])

    def test_notify_reports_each_facilitator_reply_once(self):
        r, _ = self.desk.raise_hand("amy", "stuck")
        self.assertEqual(self.desk.notify("amy"), [])
        self.desk.reply(r["id"], "pull first")
        self.assertEqual(self.desk.notify("bob"), [])
        self.assertEqual(self.desk.notify("amy"), [{"id": r["id"], "text": "pull first"}])
        self.assertEqual(self.desk.notify("amy"), [])
        self.assertFalse(self.desk.inbox("amy", mark_seen=False)[0]["replies"][0]["seen"])
        self.desk.reply(r["id"], "then push")
        self.assertEqual([x["text"] for x in self.desk.notify("amy")], ["then push"])

    def test_notify_is_per_surface_and_long_polls(self):
        r, _ = self.desk.raise_hand("amy", "stuck")
        self.desk.reply(r["id"], "pull first")
        self.assertEqual(len(self.desk.notify("amy", "vscode")), 1)
        self.assertEqual(self.desk.notify("amy", "vscode"), [])
        self.assertEqual(len(self.desk.notify("amy", "terminal")), 1)
        got = []
        t = threading.Thread(target=lambda: got.extend(self.desk.notify("amy", "vscode", wait=5)))
        t.start()
        time.sleep(0.2)
        self.desk.reply(r["id"], "then push")
        t.join(3)
        self.assertEqual([x["text"] for x in got], ["then push"])
        self.assertEqual(self.desk.notify("amy", "zellij", wait=0.1)[0]["text"], "pull first")

    def test_student_reply_returns_request_to_the_queue(self):
        r, _ = self.desk.raise_hand("amy", "stuck")
        self.desk.reply(r["id"], "try pull")
        self.assertEqual(self.desk.open_count(), 0)
        self.assertFalse(self.desk.reply(r["id"], "not mine", who="bob"))
        self.now[0] += 60
        self.assertTrue(self.desk.reply(r["id"], "still rejected", who="amy"))
        self.assertEqual(self.desk.open_count(), 1)
        self.assertEqual([x["from"] for x in self.desk.snapshot()[0]["replies"]], ["facilitator", "amy"])
        self.desk.close(r["id"])
        self.assertFalse(self.desk.reply(r["id"], "late", who="amy"))

    def test_empty_message_is_refused_and_flooding_is_limited(self):
        self.assertIsNone(self.desk.raise_hand("amy", "  ")[0])
        self.assertIsNotNone(self.desk.raise_hand("amy", "one")[0])
        self.assertIsNone(self.desk.raise_hand("amy", "two")[0])  # too soon
        for i in range(2):
            self.now[0] += 30
            self.assertIsNotNone(self.desk.raise_hand("amy", "more %d" % i)[0])
        self.now[0] += 30
        self.assertIsNone(self.desk.raise_hand("amy", "fourth")[0])  # three open is the cap

    def test_survives_a_restart(self):
        r, _ = self.desk.raise_hand("amy", "stuck")
        self.desk.reply(r["id"], "ok")
        again = support.HelpDesk(self.path, clock=lambda: self.now[0])
        self.assertEqual(again.inbox("amy")[0]["replies"][0]["text"], "ok")
        self.assertEqual(again.raise_hand("bob", "me too")[0]["id"], 2)


def act(**kw):
    a = {"since_cmd": 30, "since_progress": 60, "since_first": 900, "streak": 0, "cmds": 5, "fails": 0,
         "percent": 20, "complete": False}
    a.update(kw)
    return a


class RadarTests(unittest.TestCase):
    def test_flags_failing_stalled_and_quiet_worst_first(self):
        got = support.stuck({
            "ok": act(),
            "quiet1": act(since_cmd=20 * 60, since_progress=40 * 60),
            "stall1": act(since_progress=12 * 60),
            "fail1": act(streak=6),
        })
        self.assertEqual([(r["user"], r["level"]) for r in got],
                         [("fail1", "failing"), ("stall1", "stalled"), ("quiet1", "quiet")])
        self.assertIn("6 failed commands in a row", got[0]["why"][0])

    def test_mostly_failing_window_counts(self):
        got = support.stuck({"a": act(cmds=10, fails=8)})
        self.assertEqual(got[0]["level"], "failing")
        self.assertEqual(support.stuck({"a": act(cmds=10, fails=5)}), [])

    def test_leaves_out_finished_absent_and_long_gone(self):
        got = support.stuck({"done": act(streak=9, complete=True), "new": act(since_cmd=None, streak=9),
                             "gone": act(since_cmd=2 * 3600)})
        self.assertEqual(got, [])

    def test_never_progressed_counts_from_first_command(self):
        got = support.stuck({"a": act(since_progress=None, since_first=11 * 60)})
        self.assertEqual(got[0]["level"], "stalled")

    def test_marks_a_raised_hand(self):
        got = support.stuck({"a": act(streak=5)}, helping={"a"})
        self.assertTrue(got[0]["hand"])

    def test_busy_but_recent_progress_is_fine(self):
        self.assertEqual(support.stuck({"a": act(since_progress=60, streak=2)}), [])


class AchievementsClientTests(unittest.TestCase):
    def test_off_without_url_or_key(self):
        self.assertIsNone(support.Achievements("", "k").activity())
        self.assertIsNone(support.Achievements("http://a", "").progress("x"))

    def test_caches_and_quotes_the_user(self):
        calls = []
        t = [0]
        c = support.Achievements("http://a", "k", ttl=10, clock=lambda: t[0],
                                 opener=lambda p: calls.append(p) or {"students": {"x": 1}})
        self.assertEqual(c.activity(), {"x": 1})
        c.activity()
        self.assertEqual(len(calls), 1)
        t[0] = 11
        c.activity()
        self.assertEqual(len(calls), 2)
        c.progress("a b/c")
        self.assertEqual(calls[-1], "/api/sensei/progress?user=a%20b%2Fc")

    def test_unreachable_is_none(self):
        c = support.Achievements("http://a", "k", opener=lambda p: None)
        self.assertIsNone(c.activity())
        self.assertIsNone(c.progress("x"))


class CurrentLabTests(unittest.TestCase):
    def test_first_unfinished_lab_and_what_is_missing(self):
        m = lambda i, d: {"id": i, "title": "T" + i, "when": "w" + i, "done": d}
        prog = {"labs": [{"id": "l1", "title": "One", "milestones": [m("a", True)]},
                         {"id": "l2", "title": "Two", "milestones": [m("b", True), m("c", False)]}],
                "done": 2, "total": 3, "percent": 66, "complete": False}
        r = support.current_lab(prog)
        self.assertEqual(r["current"]["title"], "Two")
        self.assertEqual(r["current"]["missing"], [{"title": "Tc", "when": "wc"}])
        self.assertEqual(r["current"]["done"], ["Tb"])
        self.assertEqual(r["labs"][0], {"title": "One", "done": 1, "total": 1})

    def test_all_done_has_no_current(self):
        prog = {"labs": [{"id": "l1", "title": "One", "milestones": [{"id": "a", "title": "A", "when": "", "done": True}]}],
                "done": 1, "total": 1, "percent": 100, "complete": True}
        self.assertIsNone(support.current_lab(prog)["current"])


if __name__ == "__main__":
    unittest.main()
