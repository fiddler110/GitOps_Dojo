import os
import shutil
import subprocess
import tempfile
import unittest

import bot
import roster

BASE = "# Team\n\n- name: Alice\n  role: Eng\n- name: Bob\n  role: Ops\n"
REPO = "training/sample"


def git(cwd, *a, check=True):
    r = subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True,
                       env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                                GIT_COMMITTER_EMAIL="t@t"))
    if check and r.returncode:
        raise AssertionError(r.stderr)
    return r.stdout.strip()


class FakeForgejo:
    """Just enough Forgejo over a real bare repo, plus a record of comments."""

    def __init__(self, root):
        self.root = root
        self.bare = os.path.join(root, REPO + ".git")
        os.makedirs(os.path.dirname(self.bare))
        git(root, "init", "-q", "--bare", "-b", "main", self.bare)
        self.prs, self.comments, self.next = {}, [], 1
        self.workclone("main", {"roster/team.yaml": BASE, "README.md": "hi\n"}, "seed", fresh=True)

    def workclone(self, branch, files, msg, fresh=False, start="main"):
        w = tempfile.mkdtemp(dir=self.root)
        if fresh:
            git(w, "init", "-q", "-b", "main")
            git(w, "remote", "add", "origin", self.bare)
        else:
            git(w, "clone", "-q", self.bare, ".")
            git(w, "checkout", "-q", "-B", branch, f"origin/{start}")
        for p, text in files.items():
            os.makedirs(os.path.dirname(os.path.join(w, p)) or w, exist_ok=True)
            with open(os.path.join(w, p), "w") as f:
                f.write(text)
        git(w, "add", "-A")
        git(w, "commit", "-q", "-m", msg)
        git(w, "push", "-q", "origin", f"HEAD:refs/heads/{branch}")
        sha = git(w, "rev-parse", "HEAD")
        shutil.rmtree(w)
        return sha

    def open_pr(self, user, branch, files, title="Add me"):
        self.workclone(branch, files, title)
        n = self.next
        self.next += 1
        self.prs[n] = {"number": n, "title": title, "user": {"login": user}, "head_ref": branch, "state": "open",
                       "merged": False}
        return n

    def show(self, ref, path):
        r = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=self.bare, capture_output=True, text=True)
        return r.stdout if r.returncode == 0 else None

    def sha(self, ref):
        return git(self.bare, "rev-parse", ref)

    def pull(self, n):
        p = self.prs[n]
        if p["state"] == "open":
            head = self.sha(f"refs/heads/{p['head_ref']}")
        else:
            head = p["head_sha"]
        return {"number": n, "title": p["title"], "user": p["user"], "state": p["state"], "merged": p["merged"],
                "draft": False, "merge_base": git(self.bare, "merge-base", "main", head) if p["state"] == "open" else "",
                "base": {"ref": "main"}, "head": {"ref": p["head_ref"], "sha": head, "repo": {"full_name": REPO}}}

    def __call__(self, method, path, body=None, raw=False):
        path = path.split("?")[0]
        pre = f"/repos/{REPO}"
        if method == "GET" and path == pre + "/pulls":
            return 200, [self.pull(n) for n, p in self.prs.items() if p["state"] == "open"]
        if path.startswith(pre + "/pulls/"):
            rest = path[len(pre + "/pulls/"):].split("/")
            n = int(rest[0])
            if n not in self.prs:
                return 404, None
            if len(rest) == 1:
                return 200, self.pull(n)
            if rest[1] == "files":
                out = git(self.bare, "diff", "--name-only", f"main...refs/heads/{self.prs[n]['head_ref']}").split()
                return 200, [{"filename": f} for f in out]
            if rest[1] == "merge":
                return self.merge(n)
        if path.startswith(pre + "/raw/"):
            ref, _, file = path[len(pre + "/raw/"):].partition("/")
            text = self.show(ref, file)
            return (200, text) if text is not None else (404, None)
        if method == "POST" and path.startswith(pre + "/issues/") and path.endswith("/comments"):
            self.comments.append((int(path.split("/")[-2]), body["body"]))
            return 201, {}
        return 500, None

    def merge(self, n):
        p = self.prs[n]
        w = tempfile.mkdtemp(dir=self.root)
        try:
            git(w, "clone", "-q", self.bare, ".")
            git(w, "checkout", "-q", "main")
            r = subprocess.run(["git", "merge", "--no-ff", "-m", "merge", f"origin/{p['head_ref']}"], cwd=w,
                               capture_output=True, text=True,
                               env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
                                        GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t"))
            if r.returncode:
                return 405, None
            p["head_sha"] = self.sha(f"refs/heads/{p['head_ref']}")
            git(w, "push", "-q", "origin", "main")
            git(w, "push", "-q", "origin", f":refs/heads/{p['head_ref']}")
            p["state"], p["merged"] = "closed", True
            return 200, {}
        finally:
            shutil.rmtree(w)


class SenseiTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.fj = FakeForgejo(self.root)
        self.s = bot.Sensei({"repo": REPO}, self.fj, "file://" + self.root, sleep=lambda s: None)

    def tearDown(self):
        shutil.rmtree(self.root)

    def entry(self, name, role="Dev"):
        return {"roster/team.yaml": BASE + f"- name: {name}\n  role: {role}\n"}

    def test_three_students_all_append_and_all_merge(self):
        nums = [self.fj.open_pr(f"s{i}", f"add-s{i}", self.entry(f"Student {i}")) for i in range(3)]
        self.assertEqual(self.s.tick(), nums)
        self.assertEqual([self.s.prs[n]["status"] for n in nums], ["merged"] * 3)
        entries, problems = roster.parse(self.fj.show("main", "roster/team.yaml"))
        self.assertEqual(problems, [])
        self.assertEqual([e[0] for e in entries], ["Alice", "Bob", "Student 0", "Student 1", "Student 2"])
        # the first merged cleanly, the others had their branch brought up to date first
        mentions = [t for _, t in self.fj.comments if "brought" in t or "behind" in t]
        self.assertEqual(len(mentions), 2)

    def test_students_own_commit_stays_in_history(self):
        a = self.fj.open_pr("s0", "add-s0", self.entry("Student 0"))
        b = self.fj.open_pr("s1", "add-s1", self.entry("Student 1"))
        tip_b = self.fj.sha("refs/heads/add-s1")
        self.s.tick()
        r = subprocess.run(["git", "merge-base", "--is-ancestor", tip_b, "main"], cwd=self.fj.bare)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.s.prs[a]["status"], "merged")

    def test_bad_pr_gets_one_comment_and_no_merge(self):
        files = dict(self.entry("Cy"), **{"README.md": "changed\n"})
        n = self.fj.open_pr("cy", "add-cy", files)
        self.s.tick()
        self.s.tick()
        self.assertEqual(self.s.prs[n]["status"], "needs-review")
        self.assertIn("README.md", self.s.prs[n]["reason"])
        self.assertEqual(len(self.fj.comments), 1)
        self.assertNotIn("Cy", self.fj.show("main", "roster/team.yaml"))

    def test_fixing_the_pr_gets_it_merged(self):
        n = self.fj.open_pr("cy", "add-cy", {"roster/team.yaml": BASE + "\n"})
        self.s.tick()
        self.assertEqual(self.s.prs[n]["status"], "needs-review")       # no new entry
        self.fj.workclone("add-cy", self.entry("Cy", "SRE"), "fix", start="add-cy")
        self.s.tick()
        self.assertEqual(self.s.prs[n]["status"], "merged")
        self.assertIn("Cy", self.fj.show("main", "roster/team.yaml"))

    def test_bad_pr_is_flagged_for_the_facilitator_first_in_the_list(self):
        good = self.fj.open_pr("s0", "add-s0", self.entry("Student 0"))
        bad = self.fj.open_pr("cy", "add-cy", dict(self.entry("Cy"), **{"README.md": "x\n"}))
        self.s.tick()
        self.assertEqual(self.s.attention(), 1)
        self.assertEqual([r["number"] for r in self.s.snapshot()], [bad, good])
        self.assertIn("flagged it for the facilitator", self.fj.comments[-1][1])
        self.assertIn("Rubber-stamped", [t for n, t in self.fj.comments if n == good][0])

    def test_outside_the_confined_repo_or_branch_is_never_approved(self):
        n = self.fj.open_pr("s0", "add-s0", self.entry("Student 0"))
        real = self.fj.pull
        self.fj.pull = lambda k: dict(real(k), base={"ref": "release"})
        self.assertEqual(self.s.handle(n), "error")
        self.assertEqual(self.s.attention(), 1)
        self.assertNotIn("Student 0", self.fj.show("main", "roster/team.yaml"))

    def test_merge_anyway_and_disabled(self):
        files = dict(self.entry("Cy"), **{"README.md": "changed\n"})
        n = self.fj.open_pr("cy", "add-cy", files)
        self.s.enabled = False
        self.assertEqual(self.s.tick(), [])
        self.s.enabled = True
        self.s.tick()
        self.assertEqual(self.s.handle(n, force=True), "merged")
        self.assertEqual(self.s.prs[n]["reason"], "merged anyway")

    def test_state_survives_a_restart(self):
        path = os.path.join(self.root, "state.json")
        s = bot.Sensei({"repo": REPO}, self.fj, "file://" + self.root, state_path=path, sleep=lambda s: None)
        self.fj.open_pr("s0", "add-s0", self.entry("Student 0"))
        s.tick()
        s2 = bot.Sensei({"repo": REPO}, self.fj, "file://" + self.root, state_path=path)
        self.assertEqual(s2.prs[1]["status"], "merged")

    def test_forgejo_down_is_not_a_verdict(self):
        s = bot.Sensei({"repo": REPO}, lambda *a, **k: (0, None), "file://" + self.root)
        self.assertEqual(s.tick(), [])
        self.assertEqual(s.prs, {})


if __name__ == "__main__":
    unittest.main()
