import unittest

import roster as r

BASE = "# Team\n\n- name: Alice\n  role: Eng\n- name: Bob\n  role: Ops\n"
ALLOWED = ["roster/team.yaml"]


class Parse(unittest.TestCase):
    def test_entries_and_comments(self):
        self.assertEqual(r.parse(BASE), ([("Alice", "Eng"), ("Bob", "Ops")], []))

    def test_quotes_and_trailing_space(self):
        self.assertEqual(r.parse('- name: "Al B"  \n  role: \'Dev\'\n')[0], [("Al B", "Dev")])

    def test_bad_shapes(self):
        for text in ("- name: A\n", "- name: A\n role: B\n", "name: A\nrole: B\n", "- name:\n  role: B\n",
                     "- name: A\n  role:\n", "- name: A\n- name: B\n  role: C\n", "- name: A\n  role: B\n  extra: 1\n"):
            self.assertTrue(r.parse(text)[1], text)


class Review(unittest.TestCase):
    def rev(self, head, main=None, files=ALLOWED, base=BASE):
        return r.review(base, head, main or base, ALLOWED, files)

    def test_good_pr(self):
        out = self.rev(BASE + "- name: Cy\n  role: SRE\n")
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["added"], [("Cy", "SRE")])

    def test_stale_branch_is_still_good(self):
        main = BASE + "- name: Dee\n  role: QA\n"
        self.assertTrue(self.rev(BASE + "- name: Cy\n  role: SRE\n", main)["ok"])

    def test_other_files(self):
        out = self.rev(BASE + "- name: Cy\n  role: SRE\n", files=["roster/team.yaml", "README.md"])
        self.assertFalse(out["ok"])
        self.assertIn("README.md", out["problems"][0])

    def test_deleted_or_edited_entry(self):
        self.assertFalse(self.rev("# Team\n- name: Alice\n  role: Eng\n- name: Cy\n  role: SRE\n")["ok"])
        self.assertFalse(self.rev(BASE.replace("Ops", "Boss") + "- name: Cy\n  role: SRE\n")["ok"])

    def test_no_new_entry_and_two_entries(self):
        self.assertFalse(self.rev(BASE)["ok"])
        self.assertFalse(self.rev(BASE + "- name: C\n  role: X\n- name: D\n  role: Y\n")["ok"])

    def test_already_on_main(self):
        main = BASE + "- name: Cy\n  role: SRE\n"
        self.assertFalse(self.rev(BASE + "- name: Cy\n  role: SRE\n", main)["ok"])

    def test_bad_yaml_and_missing_file(self):
        self.assertFalse(self.rev(BASE + "- Cy: SRE\n")["ok"])
        self.assertFalse(r.review(BASE, None, BASE, ALLOWED, ALLOWED)["ok"])


class Combine(unittest.TestCase):
    def test_appends_to_main(self):
        main = BASE + "- name: Dee\n  role: QA\n"
        out = r.combine(main, [("Cy", "SRE")])
        self.assertTrue(out.startswith(main))
        self.assertEqual(r.parse(out)[0][-2:], [("Dee", "QA"), ("Cy", "SRE")])

    def test_adds_missing_newline(self):
        self.assertEqual(r.parse(r.combine("- name: A\n  role: B", [("C", "D")]))[0], [("A", "B"), ("C", "D")])


if __name__ == "__main__":
    unittest.main()
