import unittest

import dnsrules

BASE = 'D("dojo.test", REG,\n\tA("www", "203.0.113.10"),\n\tA("mail", "203.0.113.20"),\n);\n'


def head(*lines):
    return BASE.replace('\tA("mail"', "".join("\t%s,\n" % l for l in lines) + '\tA("mail"')


class DnsRules(unittest.TestCase):
    def ok(self, text, **kw):
        return dnsrules.review(BASE, text, kw.get("author", "testuser1"), kw.get("files", ["dnsconfig.js"]))

    def test_one_own_record_is_fine(self):
        v = self.ok(head('A("testuser1-app", "203.0.113.30")'))
        self.assertTrue(v["ok"], v)
        self.assertEqual(v["added"], ["testuser1-app"])

    def test_removing_own_record_is_fine(self):
        v = dnsrules.review(head('A("testuser1-app", "203.0.113.30")'), BASE, "testuser1", ["dnsconfig.js"])
        self.assertTrue(v["ok"], v)
        self.assertEqual(v["removed"], ["testuser1-app"])

    def test_someone_elses_record_is_refused(self):
        self.assertFalse(self.ok(head('A("testuser2-app", "203.0.113.30")'))["ok"])
        self.assertFalse(self.ok(head('A("testuser10-app", "203.0.113.30")'), author="testuser1")["ok"])

    def test_editing_an_existing_record_is_refused(self):
        self.assertFalse(self.ok(BASE.replace("203.0.113.10", "203.0.113.99"))["ok"])

    def test_other_files_and_non_records_are_refused(self):
        self.assertFalse(self.ok(head('A("testuser1-app", "1.2.3.4")'), files=["dnsconfig.js", "x"])["ok"])
        self.assertFalse(self.ok(head('var x = 1'))["ok"])

    def test_no_change_and_too_many(self):
        self.assertFalse(self.ok(BASE)["ok"])
        many = head(*['A("testuser1-%d", "1.2.3.4")' % i for i in range(5)])
        self.assertFalse(self.ok(many)["ok"])


class CrissCross(unittest.TestCase):
    def test_lines_the_branch_took_from_main_are_not_its_change(self):
        mine = 'A("testuser2-app", "203.0.113.31")'
        theirs = 'A("testuser1-app", "203.0.113.30")'
        main = head(theirs)
        branch = head(theirs, mine)  # merged main in, then added its own record; the merge base is older
        v = dnsrules.review(BASE, branch, "testuser2", ["dnsconfig.js"], main_text=main)
        self.assertTrue(v["ok"], v)
        self.assertEqual(v["added"], ["testuser2-app"])
        # without main's text the same PR looks like it adds testuser1's record too
        self.assertFalse(dnsrules.review(BASE, branch, "testuser2", ["dnsconfig.js"])["ok"])

    def test_a_removal_main_already_made_is_not_its_change(self):
        gone = 'A("testuser1-app", "203.0.113.30")'
        v = dnsrules.review(head(gone), BASE, "testuser2", ["dnsconfig.js"], main_text=BASE)
        self.assertFalse(v["ok"])  # nothing left to change at all
        self.assertEqual(v["problems"], ["There is no change to dnsconfig.js."])

    def test_a_real_foreign_record_in_the_branch_is_still_refused(self):
        v = dnsrules.review(BASE, head('A("testuser1-app", "1.2.3.4")'), "testuser2", ["dnsconfig.js"], main_text=BASE)
        self.assertFalse(v["ok"])


if __name__ == "__main__":
    unittest.main()
