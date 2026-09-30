"""Tests for the achievement catalog loader, validator and markdown generator. No containers."""

import copy
import json
import os
import shutil
import tempfile
import unittest

import catalog as cat
import render_md

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.join(HERE, "shared.json")


def item(iid, core=True, **extra):
    d = {"id": iid, "title": iid.title(), "joke": "j", "when": "shell: x", "match": {"source": "shell", "cmd": "x"}}
    if core is not None:
        d["core"] = core
    d.update(extra)
    return d


def challenge(cid="c1", **extra):
    d = {"id": cid, "title": "T", "space": "own repo `{user}/x`", "goal": "g", "verify_text": "v",
         "hints": ["h1", "h2"], "answer": "a", "seed": "s", "isolation": "i",
         "verify": [{"verb": "branch_exists", "branch": "b-{user}"}]}
    d.update(extra)
    return d


class Workshop:
    """A throwaway workshop folder holding a valid catalog that a test can then break."""

    def __init__(self, name="demo"):
        self.tmp = tempfile.mkdtemp()
        self.dir = os.path.join(self.tmp, name)
        self.base = os.path.join(self.dir, "achievements")
        self.write("catalog.json", {"workshop": name, "title": "Demo", "labs": [{"id": "lab1", "title": "One"}]})
        self.write("labs/lab1.json", {"milestones": [item("m1"), item("m2"), item("m3", core=False)]})
        self.write("funny.json", {"unlocks": [item("f1", core=None)]})
        self.write("challenges/c1.json", challenge())
        self.write("capstone.json", challenge("capstone", badge_tier="capstone"))
        # A shared catalog of its own, so these tests don't depend on the real one's warnings.
        self.shared = os.path.join(self.tmp, "shared.json")
        with open(self.shared, "w", encoding="utf-8") as fh:
            json.dump({"cheats": [item("cheat-x", core=None, points=-1)], "unlocks": []}, fh)

    def write(self, rel, obj):
        path = os.path.join(self.base, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)

    def read(self, rel):
        with open(os.path.join(self.base, rel), encoding="utf-8") as fh:
            return json.load(fh)

    def load(self, **kw):
        return cat.load(self.dir, self.shared, **kw)

    def problems(self, **kw):
        try:
            self.load(**kw)
        except cat.CatalogError as exc:
            return exc.problems
        return []

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class ValidCatalog(unittest.TestCase):
    def setUp(self):
        self.w = Workshop()
        self.addCleanup(self.w.cleanup)

    def test_loads(self):
        c, warnings = self.w.load()
        self.assertEqual(c["workshop"], "demo")
        self.assertEqual([m["id"] for m in cat.milestones(c)], ["m1", "m2", "m3"])
        self.assertEqual([m["id"] for m in cat.core_milestones(c)], ["m1", "m2"])
        self.assertEqual(warnings, [])

    def test_points_default_and_override(self):
        c, _ = self.w.load()
        self.assertEqual(cat.points_of(c["labs"][0]["milestones"][0], "milestone"), 10)
        self.assertEqual(cat.points_of({"points": 3}, "milestone"), 3)
        self.assertEqual(cat.points_of({}, "capstone"), 300)
        self.assertEqual(cat.points_of({"points": 0}, "milestone"), 0)  # zero is a real value

    def test_retired_items_are_kept_but_not_counted(self):
        self.w.write("labs/lab1.json", {"milestones": [item("m1"), item("m2", retired=True, match={})]})
        c, warnings = self.w.load()
        self.assertEqual([m["id"] for m in cat.milestones(c)], ["m1"])
        self.assertEqual(warnings, [])  # a retired item needs no match

    def test_shared_ids_may_not_collide_with_workshop_ids(self):
        self.w.write("funny.json", {"unlocks": [item("cheat-x", core=None)]})
        self.assertTrue(any("duplicate id" in p for p in self.w.problems()))


class Invalid(unittest.TestCase):
    def setUp(self):
        self.w = Workshop()
        self.addCleanup(self.w.cleanup)

    def has(self, text, **kw):
        probs = self.w.problems(**kw)
        self.assertTrue(any(text in p for p in probs), probs)

    def test_missing_catalog(self):
        os.remove(os.path.join(self.w.base, "catalog.json"))
        self.has("missing")

    def test_bad_json(self):
        with open(os.path.join(self.w.base, "funny.json"), "w") as fh:
            fh.write("{nope")
        self.assertTrue(self.w.problems())

    def test_unknown_field_is_a_typo(self):
        self.w.write("labs/lab1.json", {"milestones": [item("m1", pointz=3)]})
        self.has("unknown field 'pointz'")

    def test_duplicate_id_across_files(self):
        self.w.write("funny.json", {"unlocks": [item("m1", core=None)]})
        self.has("duplicate id")

    def test_bad_id(self):
        self.w.write("labs/lab1.json", {"milestones": [item("Bad_ID")]})
        self.has("must be lowercase")

    def test_core_only_on_milestones(self):
        self.w.write("funny.json", {"unlocks": [item("f1", core=True)]})
        self.has("'core' only applies to milestones")

    def test_milestone_needs_core(self):
        self.w.write("labs/lab1.json", {"milestones": [item("m1", core=None)]})
        self.has("need 'core'")

    def test_points_must_be_whole(self):
        self.w.write("labs/lab1.json", {"milestones": [item("m1", points="10")]})
        self.has("points must be a whole number")

    def test_unknown_match_source(self):
        self.w.write("labs/lab1.json", {"milestones": [item("m1", match={"source": "telepathy"})]})
        self.has("match.source")

    def test_lab_file_not_listed(self):
        self.w.write("labs/lab9.json", {"milestones": []})
        self.has("not listed in catalog.json")

    def test_listed_lab_without_file(self):
        os.remove(os.path.join(self.w.base, "labs", "lab1.json"))
        self.has("missing")

    def test_workshop_name_must_match_folder(self):
        c = self.w.read("catalog.json")
        c["workshop"] = "other"
        self.w.write("catalog.json", c)
        self.has("must match the workshop's folder")

    # Isolation rules (A20)
    def test_challenge_space_must_be_per_student(self):
        self.w.write("challenges/c1.json", challenge(space="the shared repo main"))
        self.has("must name the student's own space")

    def test_verify_must_read_the_students_own_state(self):
        self.w.write("challenges/c1.json", challenge(verify=[{"verb": "pr_merged", "repo": "shared/main"}]))
        self.has("reads shared state")

    def test_two_hints_exactly(self):
        self.w.write("challenges/c1.json", challenge(hints=["only one"]))
        self.has("exactly two")

    def test_challenge_id_matches_file(self):
        self.w.write("challenges/c2.json", challenge("c3"))
        self.has("id must match the file name")

    def test_capstone_badge_tier(self):
        self.w.write("capstone.json", challenge("capstone"))
        self.has("badge_tier")

    def test_unknown_verifier_verb(self):
        self.has("unknown verifier verb 'branch_exists'", known_verbs={"pr_merged"})

    def test_known_verbs_accept(self):
        self.assertEqual(self.w.problems(known_verbs={"branch_exists"}), [])


class FunnyUnlocks(unittest.TestCase):
    """Funny unlocks are worth 0: they call you out but never help the score."""

    def setUp(self):
        self.w = Workshop()
        self.addCleanup(self.w.cleanup)

    def test_default_is_zero(self):
        self.assertEqual(cat.DEFAULT_POINTS["funny"], 0)
        c, _ = self.w.load()
        self.assertEqual(cat.points_of(c["funny"][0], "funny"), 0)

    def test_a_bonus_is_refused(self):
        self.w.write("funny.json", {"unlocks": [item("f1", core=None, points=5)]})
        self.assertTrue(any("never a bonus" in p for p in self.w.problems()))

    def test_a_penalty_is_allowed(self):
        self.w.write("funny.json", {"unlocks": [item("f1", core=None, points=-1)]})
        self.assertEqual(self.w.problems(), [])

    def test_totals_count_no_funny_points(self):
        c, _ = self.w.load()
        text = render_md.render(c)
        self.assertIn("1 funny unlocks (0 points each)", text)
        self.assertIn("Everything:", text)

    def test_real_catalogs_have_no_positive_funny(self):
        for d in render_md.workshop_dirs():
            c, _ = cat.load(d, SHARED)
            for f in c["funny"] + c["shared"]["cheats"] + c["shared"]["unlocks"]:
                self.assertLessEqual(cat.points_of(f, "funny"), 0, f["id"])


class Warnings(unittest.TestCase):
    def test_missing_match_and_answer_only_warn(self):
        w = Workshop()
        self.addCleanup(w.cleanup)
        w.write("labs/lab1.json", {"milestones": [item("m1", match={})]})
        ch = challenge()
        del ch["answer"], ch["verify"]
        w.write("challenges/c1.json", ch)
        _, warnings = w.load()
        text = "\n".join(warnings)
        self.assertIn("m1: no 'match'", text)
        self.assertIn("no 'answer'", text)
        self.assertIn("no structured 'verify'", text)


class Completion(unittest.TestCase):
    def setUp(self):
        self.w = Workshop()
        self.addCleanup(self.w.cleanup)
        ms = [item(f"m{i}") for i in range(1, 11)] + [item("bonus", core=False)]
        self.w.write("labs/lab1.json", {"milestones": ms})
        self.c, _ = self.w.load()

    def test_counts_only_core(self):
        done, total, pct, complete = cat.completion(self.c, {"m1", "bonus"})
        self.assertEqual((done, total, pct, complete), (1, 10, 10, False))

    def test_complete_at_eighty_percent(self):
        ids = {f"m{i}" for i in range(1, 9)}
        self.assertTrue(cat.completion(self.c, ids)[3])
        self.assertFalse(cat.completion(self.c, {f"m{i}" for i in range(1, 8)})[3])

    def test_percent_rounds_up(self):
        # 80% of 33 is 26.4, so 26 is not enough and 27 is.
        self.w.write("labs/lab1.json", {"milestones": [item(f"m{i}") for i in range(1, 34)]})
        c, _ = self.w.load()
        self.assertFalse(cat.completion(c, {f"m{i}" for i in range(1, 27)})[3])
        self.assertTrue(cat.completion(c, {f"m{i}" for i in range(1, 28)})[3])

    def test_custom_percent(self):
        self.assertTrue(cat.completion(self.c, {f"m{i}" for i in range(1, 6)}, percent=50)[3])

    def test_no_core_milestones_is_never_complete(self):
        self.w.write("labs/lab1.json", {"milestones": [item("m1", core=False)]})
        c, _ = self.w.load()
        self.assertFalse(cat.completion(c, {"m1"})[3])

    def test_unlocked_ids_from_a_retired_or_unknown_item_are_ignored(self):
        self.assertEqual(cat.completion(self.c, {"gone", "m1"})[0], 1)


class SharedCatalog(unittest.TestCase):
    def test_cheats_are_never_worth_more_than_minus_one(self):
        with open(SHARED, encoding="utf-8") as fh:
            shared = json.load(fh)
        self.assertTrue(shared["cheats"])
        for c in shared["cheats"]:
            self.assertLessEqual(c["points"], 0, c["id"])
            self.assertGreaterEqual(c["points"], -1, c["id"])


class Render(unittest.TestCase):
    def test_render_is_deterministic_and_lists_everything(self):
        w = Workshop()
        self.addCleanup(w.cleanup)
        c, _ = w.load()
        text = render_md.render(c)
        self.assertEqual(text, render_md.render(copy.deepcopy(c)))
        for needle in ("## Lab 1: One", "| m1 |", "| f1 |", "### C1: T", "## Capstone (300 points", "Totals (computed)"):
            self.assertIn(needle, text)

    def test_totals_follow_the_data(self):
        w = Workshop()
        self.addCleanup(w.cleanup)
        w.write("labs/lab1.json", {"milestones": [item("m1", points=20), item("m2")]})
        c, _ = w.load()
        self.assertIn("2 core milestones (30 points)", render_md.render(c))


class RealCatalogs(unittest.TestCase):
    """The committed catalogs: they load, follow the rules and match their generated markdown."""

    def test_every_workshop_catalog_loads(self):
        dirs = render_md.workshop_dirs()
        self.assertGreaterEqual(len(dirs), 5)
        for d in dirs:
            cat.load(d, SHARED)

    def test_generated_markdown_is_not_stale(self):
        self.assertEqual(render_md.main(["--all", "--check", "--quiet"]), 0)


if __name__ == "__main__":
    unittest.main()
