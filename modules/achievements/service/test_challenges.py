"""Phase 4: the verifier runner, the seed builder and the git-fundamentals challenges c1 and c2,
against an in-memory Forgejo (fake_forgejo.py). No containers."""

import os
import sys
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "catalog"))
import catalog as cat  # noqa: E402
import challenges  # noqa: E402
import ledger as lg  # noqa: E402
from fake_forgejo import FakeForgejo  # noqa: E402
from store import Denied, Store  # noqa: E402

ROOT = os.path.join(HERE, "..", "..", "..")
WORKSHOP = os.path.join(ROOT, "workshops", "git-fundamentals")
PLUGINS = challenges.load_plugins([os.path.join(HERE, "..", "achievements")])
CATALOG, _ = cat.load(WORKSHOP, os.path.join(HERE, "..", "catalog", "shared.json"),
                      known_verbs=set(PLUGINS["verbs"]))
REPO = "{}/challenge-repo"
STUDENTS = ("amy", "ben", "cat", "dan")


def challenge(cid):
    if cid == "capstone":
        return CATALOG["capstone"]
    return next(c for c in CATALOG["challenges"] if c["id"] == cid)


class Clock:
    def __init__(self):
        self.t = 1_790_000_000.0

    def __call__(self):
        self.t += 1
        return self.t


class Base(unittest.TestCase):
    def setUp(self):
        self.fj = FakeForgejo(STUDENTS)
        self.clock = Clock()
        self.runner = challenges.Runner(PLUGINS, os.path.join(WORKSHOP, "achievements", "seeds"), self.fj, self.clock)
        self.store = Store(CATALOG, lg.Config(), None, "s" * 32, facilitator="boss", clock=self.clock,
                           rate=(1000, 10))
        self.errs = self.runner.errors()

    # the store calls the way server.py does
    def start(self, user, cid="c1", action="start"):
        return self.store.challenge_space(user, cid, action, self.runner, self.errs)

    def check(self, user, cid):
        return self.store.check(user, cid, self.runner, self.errs)

    def vals(self, user, cid="c1"):
        return self.runner.values(challenge(cid), user)

    # the student's side of c1 and c2
    def solve_c1(self, user, title="hotfix: my role", role=None, extra=None):
        repo = REPO.format(user)
        roster = self.fj.file(repo, "main", "roster/team.yaml")
        vals = self.vals(user)
        role = role or vals["role"]
        mine = f"- name: {user}\n  role: {vals['role_typo']}"
        self.assertIn(mine, roster)
        files = {"roster/team.yaml": roster.replace(mine, f"- name: {user}\n  role: {role}")}
        files.update(extra or {})
        self.fj.commit(repo, f"hotfix-{user}", files, user, start="main")
        return self.fj.open_pr(repo, f"hotfix-{user}", "main", title)

    def other_role(self, user):
        mine = self.vals(user)["role"]
        return next(r for r in self.runner.plan(challenge("c1"))["values"]["role"] if r != mine)

    def culprit(self, user):
        repo = self.fj.repos[REPO.format(user)]
        target = self.vals(user, "c2")["target_line"]
        for sha, c in repo["commits"].items():
            parent = repo["commits"][c["parents"][0]]["tree"] if c["parents"] else {}
            if target in c["tree"].get("config/settings.yaml", "") and target not in parent.get("config/settings.yaml", ""):
                return sha, c["author"]["name"]
        raise AssertionError("no planted commit")

    def solve_c2(self, user, text=None):
        sha, author = self.culprit(user)
        self.fj.commit(REPO.format(user), f"case-{user}", {"answer.txt": text or f"{sha[:7]} {author}\n"}, user,
                       start="main")


class Plugins(Base):
    def test_loaded_and_catalog_verbs_known(self):
        self.assertEqual(PLUGINS["problems"], [])
        self.assertIn("forgejo-repo", PLUGINS["builders"])
        self.assertEqual(self.runner.unknown_verbs(CATALOG), [])

    def test_values_are_stable_and_per_student(self):
        self.assertEqual(self.vals("amy"), self.vals("amy"))
        roles = {self.vals(u)["role"] for u in ("amy", "ben", "cat", "dan", "eve", "fay")}
        self.assertGreater(len(roles), 1)

    def test_linked_values_stay_a_pair(self):
        plan = self.runner.plan(challenge("c1"))
        pairs = dict(zip(plan["values"]["role"], plan["values"]["role_typo"]))
        for u in ("amy", "ben", "cat", "dan", "eve", "fay", "gus", "hal"):
            v = self.vals(u)
            self.assertEqual(pairs[v["role"]], v["role_typo"], u)
            self.assertNotEqual(v["role"], v["role_typo"])

    def test_regex_values_are_escaped(self):
        args = challenges.fill_args({"regex": "role: {v}", "text": "{v}"}, {"v": "a.b"})
        self.assertEqual(args, {"regex": r"role: a\.b", "text": "a.b"})

    def test_rendered_goal_names_the_students_values(self):
        c2 = challenge("c2")
        self.assertIn(self.vals("amy", "c2")["target_line"], self.runner.render(c2, "amy", c2["goal"]))
        self.assertIn("case-amy", self.runner.render(c2, "amy", c2["goal"]))


class Seeding(Base):
    def test_start_builds_the_students_own_repo(self):
        res = self.start("amy")
        self.assertEqual((res["repo"], res["created"]), ("amy/challenge-repo", True))
        repo = self.fj.repos["amy/challenge-repo"]
        self.assertEqual(len(repo["commits"]), 11)
        self.assertIn("amy", self.fj.file("amy/challenge-repo", "main", "README.md"))
        roster = self.fj.file("amy/challenge-repo", "main", "roster/team.yaml")
        self.assertIn(f"- name: amy\n  role: {self.vals('amy')['role_typo']}\n", roster)
        self.assertNotIn(self.vals("amy")["role"], roster)
        self.assertIn(self.vals("amy", "c2")["target_line"], self.fj.file("amy/challenge-repo", "main", "config/settings.yaml"))
        self.assertEqual(self.store.seeds["amy"]["challenge-repo.json"]["resets"], 0)

    def test_start_is_idempotent(self):
        self.start("amy")
        head = self.fj.repos["amy/challenge-repo"]["branches"]["main"]
        self.assertFalse(self.start("amy")["created"])
        self.assertFalse(self.start("amy", "c2")["created"])     # one repo serves every challenge
        self.assertEqual(self.fj.repos["amy/challenge-repo"]["branches"]["main"], head)

    def test_reset_recreates_any_number_of_times(self):
        self.start("amy")
        self.solve_c1("amy")
        for i in range(3):
            self.assertTrue(self.start("amy", action="reset")["created"])
        repo = self.fj.repos["amy/challenge-repo"]
        self.assertEqual(set(repo["branches"]), {"main", "feature-a", "feature-b"})   # the student's branch is gone
        self.assertEqual(repo["pulls"], [])
        self.assertEqual(self.store.seeds["amy"]["challenge-repo.json"]["resets"], 3)

    def test_reset_without_start_just_builds(self):
        self.assertTrue(self.start("amy", action="reset")["created"])

    def test_seeding_touches_only_the_students_repo(self):
        self.start("ben")
        before = dict(self.fj.repos["ben/challenge-repo"]["branches"])
        self.fj.writes.clear()
        self.start("amy")
        self.start("amy", action="reset")
        self.assertTrue(self.fj.writes)
        for method, path in self.fj.writes:
            self.assertTrue("/amy/" in path or path.endswith("/amy/repos"), path)
        self.assertEqual(self.fj.repos["ben/challenge-repo"]["branches"], before)

    def test_plan_outside_the_students_space_is_refused(self):
        bad = dict(challenge("c1"), seed_plan="../catalog.json")
        with self.assertRaises(challenges.NotCheckable):
            self.runner.seed(bad, "amy")

    def test_same_student_twice_at_once_is_refused(self):
        self.store.busy.add("amy")
        with self.assertRaises(Denied) as cm:
            self.start("amy")
        self.assertEqual(cm.exception.code, 409)

    def test_forgejo_down_is_try_again(self):
        self.fj.down = True
        with self.assertRaises(Denied) as cm:
            self.start("amy")
        self.assertEqual(cm.exception.code, 503)
        self.assertNotIn("amy", self.store.busy)

    def test_hints_stay_used_across_reset(self):
        self.start("amy")
        self.store.hint("amy", "c1")
        self.start("amy", action="reset")
        self.assertEqual(self.store.ledger.hints_used("amy", "c1"), 1)


class C1Hotfix(Base):
    def setUp(self):
        super().setUp()
        self.start("amy")

    def test_not_started(self):
        r = self.check("ben", "c1")
        self.assertFalse(r["passed"])

    def test_pass_scores_and_first_blood(self):
        self.solve_c1("amy")
        r = self.check("amy", "c1")
        self.assertTrue(r["passed"], r)
        self.assertEqual(r["points"], 100)
        self.assertEqual(self.store.ledger.score("amy"), 125)       # + first blood

    def test_merged_pr_with_deleted_branch_still_passes(self):
        n = self.solve_c1("amy")
        self.fj.merge_pr("amy/challenge-repo", n, "amy", delete_branch=True)
        self.assertTrue(self.check("amy", "c1")["passed"])

    def test_wrong_answers_cost_nothing(self):
        cases = [
            dict(title="fix Alice"),                                   # no hotfix: prefix
            dict(role="Chief Typo Officer"),                           # not this student's value
            dict(role=self.other_role("amy")),                         # a neighbour's right role
            dict(extra={"README.md": "changed too\n"}),                # touches another file
        ]
        for i, kw in enumerate(cases):
            self.start("amy", action="reset")
            self.solve_c1("amy", **kw)
            r = self.check("amy", "c1")
            self.assertFalse(r["passed"], kw)
            self.assertTrue(r["message"])
        self.assertEqual(self.store.ledger.score("amy"), 0)
        self.assertNotIn("c1", self.store.ledger.unlocked_ids("amy"))
        self.assertEqual(len([c for c in self.store.checks if not c["passed"]]), 4)
        # and a right answer afterwards still gets full points
        self.start("amy", action="reset")
        self.solve_c1("amy")
        self.assertEqual(self.check("amy", "c1")["points"], 100)

    def test_direct_push_to_main_fails(self):
        self.solve_c1("amy")
        self.fj.commit("amy/challenge-repo", "main", {"roster/team.yaml": "oops\n"}, "amy")
        r = self.check("amy", "c1")
        self.assertFalse(r["passed"])
        self.assertIn("pull request", r["message"])

    def test_closed_unmerged_pr_does_not_count(self):
        n = self.solve_c1("amy")
        self.fj.repos["amy/challenge-repo"]["pulls"][n - 1]["state"] = "closed"
        self.assertIn("closed without merging", self.check("amy", "c1")["message"])

    def test_hint_then_pass(self):
        self.store.hint("amy", "c1")
        self.solve_c1("amy")
        self.assertEqual(self.check("amy", "c1")["points"], 75)

    def test_reveal_then_pass_scores_zero_but_counts(self):
        self.store.hint("amy", "c1")
        self.store.hint("amy", "c1")
        self.store.reveal("amy", "c1")
        self.solve_c1("amy")
        r = self.check("amy", "c1")
        self.assertEqual((r["passed"], r["points"]), (True, 0))
        self.assertIn("c1", self.store.ledger.unlocked_ids("amy"))
        self.assertEqual(self.store.ledger.score("amy"), 0)          # no first blood after a reveal

    def test_pass_is_never_undone_and_pays_once(self):
        self.solve_c1("amy")
        self.check("amy", "c1")
        self.start("amy", action="reset")                            # the PR is gone now
        r = self.check("amy", "c1")
        self.assertTrue(r["already"])
        self.assertIn("c1", self.store.ledger.unlocked_ids("amy"))
        self.assertEqual(self.store.ledger.score("amy"), 125)

    def test_another_students_pass_does_not_help(self):
        self.solve_c1("amy")
        self.start("ben")
        self.assertTrue(self.check("amy", "c1")["passed"])
        self.assertFalse(self.check("ben", "c1")["passed"])

    def test_assertion_on_someone_elses_repo_is_refused(self):
        bad = dict(challenge("c1"), verify=[{"verb": "repo_exists", "repo": "ben/challenge-repo"}])
        with self.assertRaises(challenges.NotCheckable):
            self.runner.verify(bad, "amy")

    def test_forgejo_down_is_not_a_wrong_answer(self):
        self.solve_c1("amy")
        self.fj.down = True
        with self.assertRaises(Denied) as cm:
            self.check("amy", "c1")
        self.assertEqual(cm.exception.code, 503)
        self.assertEqual(self.store.checks, [])


class C2Detective(Base):
    def setUp(self):
        super().setUp()
        self.start("amy", "c2")

    def test_pass(self):
        self.solve_c2("amy")
        r = self.check("amy", "c2")
        self.assertTrue(r["passed"], r)
        self.assertEqual(r["points"], 100)

    def test_long_hash_and_other_words_pass(self):
        sha, author = self.culprit("amy")
        self.solve_c2("amy", f"It was {author}!\ncommit {sha}\n")
        self.assertTrue(self.check("amy", "c2")["passed"])

    def test_wrong_answers(self):
        sha, author = self.culprit("amy")
        head = self.fj.repos["amy/challenge-repo"]["branches"]["main"]
        self.assertFalse(self.check("amy", "c2")["passed"])                         # no branch yet
        self.solve_c2("amy", f"{head[:7]} {author}\n")                              # wrong commit
        self.assertIn("hash", self.check("amy", "c2")["message"])
        self.fj.commit("amy/challenge-repo", "case-amy", {"answer.txt": f"{sha[:7]} Alice Engineer\n"}, "amy")
        self.assertIn("author", self.check("amy", "c2")["message"])
        self.assertEqual(self.store.ledger.score("amy"), 0)

    def test_neighbours_answer_does_not_work(self):
        self.start("ben", "c2")
        sha, author = self.culprit("ben")
        self.solve_c2("amy", f"{sha[:7]} {author}\n")
        self.assertFalse(self.check("amy", "c2")["passed"])

    def test_merging_later_keeps_the_answer_findable(self):
        n = self.solve_c1("amy")
        self.fj.merge_pr("amy/challenge-repo", n, "amy")
        self.solve_c2("amy")
        self.assertTrue(self.check("amy", "c2")["passed"])


class Capstone(Base):
    """The Great Merge: two conflicting feature branches and a bad commit, per student."""
    BAD = "Make deploys faster"

    def setUp(self):
        super().setUp()
        self.start("amy", "capstone")

    def bad_sha(self, user="amy"):
        repo = self.fj.repos[REPO.format(user)]
        return next(s for s, c in repo["commits"].items() if c["message"] == self.BAD)

    def solve(self, user="amy", keep=("a", "b"), markers=False, revert="both", drop_bad=False,
              pr=True, merge=True, settings=None):
        """The student's side: merge-{user} off main, merge feature-a and feature-b (conflict
        resolved by hand), revert the bad commit, PR into main and merge it."""
        repo, v = REPO.format(user), self.vals(user, "capstone")
        branch = f"merge-{user}"
        base = self.fj.file(repo, "main", "CHANGELOG.md")
        self.fj.commit(repo, branch, {"CHANGELOG.md": base + f"- {v['feature_a']}\n"}, user, start="main",
                       message="Merge branch 'feature-a'", merge="feature-a")
        lines = "".join(f"- {v['feature_' + k]}\n" for k in keep)
        if markers:
            lines = f"<<<<<<< HEAD\n- {v['feature_a']}\n=======\n- {v['feature_b']}\n>>>>>>> feature-b\n"
        fb = self.fj.file(repo, "feature-b", "config/settings.yaml")
        files = {"CHANGELOG.md": base + lines}
        if drop_bad:        # took feature-b's line by hand, without its commits
            self.fj.commit(repo, branch, files, user, message="Add feature-b's line")
        else:
            files["config/settings.yaml"] = fb
            self.fj.commit(repo, branch, files, user, message="Merge branch 'feature-b'", merge="feature-b")
        if revert:
            sha = self.bad_sha(user)
            msg = {"both": f'Revert "{self.BAD}"\n\nThis reverts commit {sha}.',
                   "subject": f'Revert "{self.BAD}"', "body": f"Undo the timeout\n\nThis reverts commit {sha[:9]}.",
                   "edit": "Put the timeout back"}[revert]
            fixed = settings or fb.replace("timeout_seconds: 0", "timeout_seconds: 30")
            self.fj.commit(repo, branch, {"config/settings.yaml": fixed}, user, message=msg)
        if pr:
            n = self.fj.open_pr(repo, branch, "main", "The great merge")
            if merge:
                self.fj.merge_pr(repo, n, user)

    def test_seed_has_the_conflict_and_the_bad_commit(self):
        repo, v = "amy/challenge-repo", self.vals("amy", "capstone")
        self.assertIn("timeout_seconds: 30", self.fj.file(repo, "main", "config/settings.yaml"))
        self.assertIn("timeout_seconds: 0", self.fj.file(repo, "feature-b", "config/settings.yaml"))
        self.assertTrue(self.fj.file(repo, "feature-a", "CHANGELOG.md").endswith(f"- {v['feature_a']}\n"))
        self.assertTrue(self.fj.file(repo, "feature-b", "CHANGELOG.md").endswith(f"- {v['feature_b']}\n"))
        self.assertNotIn(v["feature_a"], self.fj.file(repo, "main", "CHANGELOG.md"))
        r = self.fj.repos[repo]
        self.assertNotIn(self.bad_sha(), self.fj._log(r, r["branches"]["main"]))
        self.assertIn(self.bad_sha(), self.fj._log(r, r["branches"]["feature-b"]))

    def test_values_are_per_student(self):
        a = self.vals("amy", "capstone")
        self.assertNotEqual(a["feature_a"], a["feature_b"])
        self.assertIn(a["feature_a"], self.runner.render(CATALOG["capstone"], "amy", CATALOG["capstone"]["answer"]))
        picks = {tuple(self.vals(u, "capstone")[k] for k in ("feature_a", "feature_b")) for u in STUDENTS}
        self.assertGreater(len(picks), 1)

    def test_pass_pays_300_and_first_blood(self):
        self.solve()
        r = self.check("amy", "capstone")
        self.assertTrue(r["passed"], r)
        self.assertEqual(r["points"], 300)
        self.assertEqual(self.store.ledger.score("amy"), 350)

    def test_either_revert_message_counts(self):
        for style in ("subject", "body"):
            with self.subTest(style=style):
                self.start("amy", "capstone", "reset")
                self.solve(revert=style)
                self.assertTrue(self.runner.verify(CATALOG["capstone"], "amy")["passed"])

    def test_wrong_answers(self):
        cases = [
            ({"pr": False}, "pull request"),
            ({"merge": False}, "merged pull request"),
            ({"markers": True}, "CHANGELOG.md"),
            ({"keep": ("a",)}, "CHANGELOG.md"),
            ({"revert": None}, self.BAD),
            ({"revert": "edit"}, "still in effect"),
            ({"drop_bad": True, "revert": None}, "history"),
            ({"settings": "timeout_seconds: 5\n"}, "settings.yaml"),
        ]
        for kw, want in cases:
            with self.subTest(kw=kw):
                self.start("amy", "capstone", "reset")
                self.solve(**kw)
                r = self.check("amy", "capstone")
                self.assertFalse(r["passed"], r)
                self.assertIn(want, r["message"])
        self.assertEqual(self.store.ledger.score("amy"), 0)

    def test_direct_push_to_main_fails(self):
        self.solve()
        self.fj.commit("amy/challenge-repo", "main", {"notes.txt": "x"}, "amy")
        self.assertIn("pull request", self.check("amy", "capstone")["message"])

    def test_neighbours_lines_do_not_pass(self):
        self.start("ben", "capstone")
        a, b = self.vals("amy", "capstone"), self.vals("ben", "capstone")
        if (a["feature_a"], a["feature_b"]) == (b["feature_a"], b["feature_b"]):
            self.skipTest("same picks")
        self.solve("ben")
        repo = "amy/challenge-repo"
        self.fj.commit(repo, "copy", {"CHANGELOG.md": self.fj.file("ben/challenge-repo", "main", "CHANGELOG.md")},
                       "amy", start="main")
        self.fj.merge_pr(repo, self.fj.open_pr(repo, "copy", "main", "copied"), "amy")
        self.assertFalse(self.check("amy", "capstone")["passed"])

    def test_c1_and_c2_still_pass_after_the_capstone(self):
        self.solve()
        self.assertTrue(self.check("amy", "capstone")["passed"])
        self.fj.merge_pr("amy/challenge-repo", self.solve_c1("amy"), "amy")
        self.assertTrue(self.check("amy", "c1")["passed"])
        self.solve_c2("amy")
        self.assertTrue(self.check("amy", "c2")["passed"])

    def test_reset_brings_the_branches_back(self):
        self.solve()
        self.start("amy", "capstone", "reset")
        repo = self.fj.repos["amy/challenge-repo"]
        self.assertEqual(sorted(repo["branches"]), ["feature-a", "feature-b", "main"])
        self.assertIn("timeout_seconds: 30", self.fj.file("amy/challenge-repo", "main", "config/settings.yaml"))


class ClassWide(Base):
    def test_class_clear_and_concurrent_checks(self):
        for u in STUDENTS:
            self.start(u)
            self.solve_c1(u)
        results = {}

        def go(u):
            results[u] = self.check(u, "c1")
        threads = [threading.Thread(target=go, args=(u,)) for u in STUDENTS]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertTrue(all(r["passed"] and r["points"] == 100 for r in results.values()), results)
        self.assertEqual(len([u for u in STUDENTS if self.store.ledger.first_blood.get("c1") == u]), 1)
        self.assertIn("c1", self.store.ledger.class_cleared)
        for u in STUDENTS:
            bonus = 25 if self.store.ledger.first_blood["c1"] == u else 0
            self.assertEqual(self.store.ledger.score(u), 100 + bonus + 10)

    def test_no_seed_plan_and_no_verify(self):
        item = self.store.ledger.index["capstone"]["item"]
        saved = dict(item)
        self.addCleanup(item.update, saved)
        item.pop("verify")
        item.pop("seed_plan")
        with self.assertRaises(challenges.NotCheckable):
            self.check("amy", "capstone")
        with self.assertRaises(Denied) as cm:
            self.start("amy", "capstone")
        self.assertEqual(cm.exception.code, 501)
        with self.assertRaises(Denied):
            self.check("amy", "nope")


if __name__ == "__main__":
    unittest.main()
