"""Every workshop's challenges, started for two students against the fake Forgejo: each repo is the
student's own, one per seed plan, and nothing the student sees (files on every branch, commit messages,
the goal) still holds an unfilled {placeholder}. A challenge with no seed plan starts with no repo.
Run: python3 -B -m unittest test_all_seeds
"""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(HERE, "..", "catalog"))
import catalog as cat  # noqa: E402
import challenges  # noqa: E402
import ledger as lg  # noqa: E402
from fake_forgejo import FakeForgejo  # noqa: E402
from store import Store  # noqa: E402

PACKS = ("git-fundamentals", "dns-as-code", "cert-autorenewal", "tofu-basics", "vault-fundamentals")
PLUGINS = challenges.load_plugins([os.path.join(HERE, "..", "achievements")])
SHARED = os.path.join(HERE, "..", "catalog", "shared.json")
STUDENTS = ("amy", "bob")


class Clock:
    t = 1_000_000.0

    def __call__(self):
        self.t += 1
        return self.t


class AllSeeds(unittest.TestCase):
    def pack(self, name):
        path = os.path.join(ROOT, "workshops", name)
        catalog, _ = cat.load(path, SHARED)
        fj, clock = FakeForgejo(STUDENTS), Clock()
        runner = challenges.Runner(PLUGINS, os.path.join(path, "achievements", "seeds"), fj, clock)
        store = Store(catalog, lg.Config(), None, "s" * 32, facilitator="boss", clock=clock, rate=(1000, 10))
        return catalog, fj, runner, store

    def test_every_challenge_starts_for_every_student(self):
        for name in PACKS:
            catalog, fj, runner, store = self.pack(name)
            items = catalog["challenges"] + ([catalog["capstone"]] if catalog.get("capstone") else [])
            repo_of_plan = {}
            for ch in items:
                for user in STUDENTS:
                    with self.subTest(pack=name, challenge=ch["id"], user=user):
                        doc = store.challenge_space(user, ch["id"], "start", runner, runner.errors())
                        vals = runner.values(ch, user)
                        left = re.compile(r"\{(%s)\}" % "|".join(map(re.escape, sorted(vals))))
                        self.assertNotRegex(runner.render(ch, user, ch["goal"]), left)
                        if not ch.get("seed_plan"):
                            self.assertIsNone(doc["repo"])
                            continue
                        repo = doc["repo"]
                        self.assertTrue(repo.startswith(user + "/"), repo)
                        self.assertEqual(repo_of_plan.setdefault((ch["seed_plan"], user), repo), repo)
                        r = fj.repos[repo]
                        self.assertIn("main", r["branches"])
                        for sha in set(r["branches"].values()):
                            c = r["commits"][sha]
                            self.assertNotRegex(c["message"], left)
                            for path, text in c["tree"].items():
                                self.assertNotRegex(text if isinstance(text, str) else "", left,
                                                    f"{repo}:{path}")
            # Different plans never share a repo: start leaves an existing repo alone.
            for user in STUDENTS:
                repos = [r for (plan, u), r in repo_of_plan.items() if u == user]
                self.assertEqual(len(repos), len(set(repos)), (name, repos))


if __name__ == "__main__":
    unittest.main()
