"""Tests for the matcher: command-line parsing, Forgejo normalisation and the git-fundamentals
catalog replayed against recorded event sequences (testdata/)."""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "catalog"))
import catalog  # noqa: E402
import ledger as lg  # noqa: E402
import matcher as mt  # noqa: E402

WORKSHOP = os.path.join(HERE, "..", "..", "..", "workshops", "git-fundamentals")
SHARED = os.path.join(HERE, "..", "catalog", "shared.json")
with open(os.path.join(HERE, "testdata", "git-fundamentals-sequences.json")) as _f:
    SEQUENCES = json.load(_f)


def load():
    return catalog.load(WORKSHOP, SHARED)[0]


def shell(cmd, exit=0, **kw):
    return mt.shell_event(dict(cmd=cmd, exit=exit, **kw))


class Segments(unittest.TestCase):
    def words(self, line):
        return [s["words"] for s in mt.segments(line)]

    def test_control_operators_split_commands(self):
        self.assertEqual(self.words('git add . && git commit -m "a && b"; git push | cat'),
                         [["git", "add", "."], ["git", "commit", "-m", "a && b"], ["git", "push"], ["cat"]])

    def test_redirects_leave_words_but_stay_in_text(self):
        seg = mt.segments('echo "*.log" >> .gitignore')[0]
        self.assertEqual(seg["words"], ["echo", "*.log"])
        self.assertEqual(seg["text"], "echo *.log >> .gitignore")

    def test_env_wrappers_and_git_global_options_dropped(self):
        self.assertEqual(self.words("GIT_PAGER=cat command git -C repo -c a=b --no-pager log -1"),
                         [["git", "log", "-1"]])

    def test_newlines_and_heredocs(self):
        self.assertEqual(self.words("git status\ngit diff")[:2], [["git", "status"], ["git", "diff"]])
        self.assertEqual(self.words("cat >> f <<'EOF'\n- a\nEOF")[0], ["cat"])

    def test_unbalanced_quote_falls_back(self):
        self.assertEqual(self.words('git commit -m "oops')[0][:2], ["git", "commit"])

    def test_flags(self):
        self.assertTrue(mt._has_flag(["-fu", "origin"], "-f"))
        self.assertTrue(mt._has_flag(["--force-with-lease=main"], "--force-with-lease"))
        self.assertFalse(mt._has_flag(["-m", "fix -f"], "-f"))
        self.assertFalse(mt._has_flag(["--", "-f"], "-f"))
        self.assertFalse(mt._has_flag(["-D"], "-d"))


class ShellEvents(unittest.TestCase):
    def test_body_validation(self):
        self.assertIsNone(mt.shell_event({"cmd": "", "exit": 0}))
        self.assertIsNone(mt.shell_event({"cmd": "ls", "exit": "x"}))
        self.assertIsNone(mt.shell_event({"cmd": "ls", "exit": True}))
        ev = mt.shell_event({"cmd": "ls" * 5000, "exit": "2", "merging": "1", "branch": 5})
        self.assertEqual((len(ev["cmd"]), ev["exit"], ev["merging"], ev["branch"]), (mt.MAX_CMD, 2, True, None))

    def test_exit_variants(self):
        m = mt.Matcher({"a": {"kind": "funny", "cheat": False,
                              "item": {"match": {"source": "shell", "cmd": "x", "exit": "nonzero"}}},
                        "b": {"kind": "funny", "cheat": False,
                              "item": {"match": {"source": "shell", "cmd": "x", "exit": [1, 2]}}},
                        "c": {"kind": "funny", "cheat": False, "item": {"match": {"source": "shell", "cmd": "x"}}}})
        self.assertEqual(m.match(shell("x", 0)), ["c"])
        self.assertEqual(m.match(shell("x", 2)), ["a", "b", "c"])
        self.assertEqual(m.match(shell("x", 3)), ["a", "c"])

    def test_cheats_and_other_sources_are_not_matched(self):
        idx = lg.build_index(load(), lg.Config())
        ids = {iid for iid, _ in mt.Matcher(idx).rules}
        self.assertFalse(any(i.startswith("cheat") for i in ids))
        self.assertNotIn("c1", ids)


class ForgejoEvents(unittest.TestCase):
    REPO = {"full_name": "amy/challenge-repo"}

    def test_push_branch_and_tag(self):
        ev = mt.forgejo_event("push", {"ref": "refs/heads/feat", "pusher": {"login": "amy"}, "repository": self.REPO})
        self.assertEqual((ev["event"], ev["branch"], ev["user"], ev["repo"]), ("push", "feat", "amy", "amy/challenge-repo"))
        ev = mt.forgejo_event("push", {"ref": "refs/tags/v1", "pusher": {"username": "amy"}})
        self.assertEqual((ev["tag"], ev["branch"], ev["ref_type"]), ("v1", None, "tag"))

    def test_create_delete(self):
        ev = mt.forgejo_event("create", {"ref": "v2", "ref_type": "tag", "sender": {"login": "amy"}})
        self.assertEqual((ev["event"], ev["tag"], ev["ref_type"]), ("create", "v2", "tag"))
        ev = mt.forgejo_event("delete", {"ref": "old", "ref_type": "branch", "sender": {"login": "amy"}})
        self.assertEqual((ev["event"], ev["branch"]), ("delete", "old"))

    def test_merge_credits_the_author_not_the_merger(self):
        ev = mt.forgejo_event("pull_request", {"action": "closed", "sender": {"login": "boss"},
                                               "pull_request": {"merged": True, "user": {"login": "amy"},
                                                                "base": {"ref": "main"}}})
        self.assertEqual((ev["action"], ev["user"], ev["actor"], ev["branch"]), ("merged", "amy", "boss", "main"))
        ev = mt.forgejo_event("pull_request", {"action": "closed", "sender": {"login": "amy"},
                                               "pull_request": {"merged": False, "user": {"login": "amy"}}})
        self.assertEqual(ev["action"], "closed")

    def test_review_credits_the_reviewer(self):
        ev = mt.forgejo_event("pull_request_review_rejected", {"sender": {"login": "ben"},
                                                               "pull_request": {"user": {"login": "amy"}}})
        self.assertEqual((ev["event"], ev["action"], ev["user"]), ("pull_request_review", "rejected", "ben"))

    def test_recorded_forgejo16_deliveries(self):
        """Real deliveries from Forgejo 16.0.4 (testdata/forgejo16-deliveries.json), headers as sent."""
        import webhook
        with open(os.path.join(HERE, "testdata", "forgejo16-deliveries.json")) as f:
            rec = json.load(f)["deliveries"]
        got = []
        for d in rec:
            ev = mt.forgejo_event(webhook.event_kind(d["headers"]), d["payload"])
            got.append((ev["event"], ev["action"], ev["user"], ev["branch"]) if ev else None)
        self.assertEqual(got, [
            ("create", None, "workshop-admin", "main"),
            ("push", None, "workshop-admin", "main"),
            ("pull_request", "opened", "testuser1", "main"),
            ("pull_request_review", "approved", "workshop-admin", None),
            ("pull_request", "merged", "testuser1", "main"),
            ("pull_request_review", "rejected", "workshop-admin", None),
        ])
        # The short X-Forgejo-Event alone (no -Type header) still reads as a review.
        ev = mt.forgejo_event(rec[3]["headers"]["X-Forgejo-Event"], rec[3]["payload"])
        self.assertEqual((ev["event"], ev["action"]), ("pull_request_review", "approved"))
        m = mt.Matcher(lg.Ledger(load(), lg.Config()).index)
        self.assertEqual(m.match(mt.forgejo_event("pull_request", rec[2]["payload"])), ["l1-pr"])
        self.assertEqual(m.match(mt.forgejo_event("pull_request", rec[4]["payload"])), ["l1-merged"])

    def test_unknown_or_anonymous_events_are_dropped(self):
        self.assertIsNone(mt.forgejo_event("issues", {"sender": {"login": "amy"}}))
        self.assertIsNone(mt.forgejo_event("push", {"ref": "refs/heads/x"}))
        self.assertIsNone(mt.forgejo_event("push", "not a dict"))

    def test_repo_template_and_not_fields(self):
        idx = {"own": {"kind": "funny", "cheat": False,
                       "item": {"match": {"source": "forgejo", "event": "push", "repo": "{user}/challenge-repo",
                                          "branch_not": ["main"]}}}}
        m = mt.Matcher(idx)
        push = lambda who, ref, repo: mt.forgejo_event("push", {"ref": ref, "pusher": {"login": who},
                                                               "repository": {"full_name": repo}})
        self.assertEqual(m.match(push("amy", "refs/heads/x", "amy/challenge-repo")), ["own"])
        self.assertEqual(m.match(push("ben", "refs/heads/x", "amy/challenge-repo")), [])
        self.assertEqual(m.match(push("amy", "refs/heads/main", "amy/challenge-repo")), [])
        self.assertEqual(m.match(push("amy", "refs/tags/v1", "amy/challenge-repo")), [])


class RecordedSequences(unittest.TestCase):
    """The recorded lab walkthroughs: each step unlocks exactly what it says, once."""

    def replay(self, steps, ledger=None, user="amy"):
        c = load()
        ledger = ledger or lg.Ledger(c, lg.Config())
        m = mt.Matcher(ledger.index)
        for n, step in enumerate(steps):
            if "shell" in step:
                ev = mt.shell_event(step["shell"])
                label = step["shell"]["cmd"]
            else:
                ev = mt.forgejo_event(*step["forgejo"])
                label = step["forgejo"][0]
            got = []
            # a Forgejo event credited to someone else (the facilitator merging) is not amy's
            if ev is not None and (ev["source"] == "shell" or ev["user"] == user):
                got = [i for i in m.match(ev) if ledger.unlock(user, i, n) is not None]
            self.assertEqual(got, step["expect"], f"step {n}: {label!r}")
        return ledger

    def test_labs_in_order_unlock_every_milestone(self):
        ledger = None
        for lab in ("lab1", "lab2", "lab3", "lab4", "lab5"):
            with self.subTest(lab=lab):
                ledger = self.replay(SEQUENCES[lab], ledger)
        all_milestones = {m["id"] for m in catalog.milestones(load())}
        self.assertEqual(all_milestones - ledger.unlocked_ids("amy"), set())
        # doing the labs as written is not funny
        self.assertFalse([i for i in ledger.unlocked_ids("amy") if i.startswith("f-")])
        self.assertTrue(ledger.completion("amy")[3])

    def test_funny_unlocks(self):
        ledger = self.replay(SEQUENCES["funny"])
        funny = {f["id"] for f in load()["funny"]}
        self.assertEqual(funny - ledger.unlocked_ids("amy"), set())



class Enabled(unittest.TestCase):
    def test_off_items_never_fire(self):
        c = load()
        on = mt.Matcher(lg.build_index(c, lg.Config()))
        self.assertIn("l1-clone", on.match(shell("git clone http://x/r.git")))
        c["labs"][0]["milestones"][0]["enabled"] = False
        self.assertEqual(c["labs"][0]["milestones"][0]["id"], "l1-clone")
        off = mt.Matcher(lg.build_index(c, lg.Config()))
        self.assertNotIn("l1-clone", off.match(shell("git clone http://x/r.git")))

if __name__ == "__main__":
    unittest.main()


class GenericFields(unittest.TestCase):
    """`requires`, `count` and forgejo `head_prefix`/`head` (shared by every pack)."""

    def matcher(self, *matches):
        index = {f"i{n}": {"kind": "milestone", "item": {"match": m}} for n, m in enumerate(matches)}
        return mt.Matcher(index)

    def pr(self, head, user="amy"):
        return mt.forgejo_event("pull_request", {
            "action": "opened", "sender": {"login": user}, "repository": {"full_name": "o/r"},
            "pull_request": {"user": {"login": user}, "base": {"ref": "main"}, "head": {"ref": head}}})

    def test_requires_needs_the_other_id_held(self):
        m = self.matcher({"source": "shell", "cmd": "git push", "requires": "a"})
        ev = shell("git push")
        self.assertEqual(m.match(ev), [])
        self.assertEqual(m.match(ev, {"a"}), ["i0"])

    def test_count_fires_from_the_nth_event(self):
        m = self.matcher({"source": "forgejo", "event": "pull_request", "action": "opened", "count": 3})
        seen = {}

        def bump(i):
            seen[i] = seen.get(i, 0) + 1
            return seen[i]
        got = [m.match(self.pr("x"), (), bump) for _ in range(4)]
        self.assertEqual(got, [[], [], ["i0"], ["i0"]])

    def test_head_prefix_and_head(self):
        m = self.matcher({"source": "forgejo", "event": "pull_request", "head_prefix": "rollback-"},
                         {"source": "forgejo", "event": "pull_request", "head": "hotfix-{user}"})
        self.assertEqual(m.match(self.pr("rollback-x")), ["i0"])
        self.assertEqual(m.match(self.pr("hotfix-amy")), ["i1"])
        self.assertEqual(m.match(self.pr("other")), [])

    def test_catalog_accepts_and_rejects(self):
        ok, _ = catalog.check_match({"source": "shell", "cmd": "x", "requires": ["a"], "count": 2}, "t")
        self.assertEqual(ok, [])
        bad, _ = catalog.check_match({"source": "shell", "cmd": "x", "count": 1}, "t")
        self.assertTrue(bad)
