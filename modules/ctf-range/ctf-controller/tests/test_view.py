import os, sys, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, ".."), os.path.join(HERE, "..", "..", "..", "_shared")]
import view
from controller import Config


def cfg():
    return Config({"STUDENT_COUNT": "3", "CTF_ATTACK_TARGETS": "a=x:1,b=y:2", "CTF_NET_SUBNET": "10.42.0.0/24",
                   "FACILITATOR_USERNAME": "admin"})


class ResolveTest(unittest.TestCase):
    def test_student_own(self):
        self.assertEqual(view.resolve(cfg(), "student02", False, "/b/login"),
                         ("student02", "b", "/ctf-view/b", "/login", False))

    def test_redirect_needs_slash(self):
        self.assertTrue(view.resolve(cfg(), "student01", False, "/a")[4])
        self.assertFalse(view.resolve(cfg(), "student01", False, "/a/")[4])

    def test_student_cannot_name_other(self):
        self.assertIsNone(view.resolve(cfg(), "student01", False, "/student02/a/")[0])

    def test_facilitator_names_student(self):
        r = view.resolve(cfg(), "admin", True, "/student03/a/x/y")
        self.assertEqual(r[:4], ("student03", "a", "/ctf-view/student03/a", "/x/y"))
        self.assertIsNone(view.resolve(cfg(), "admin", True, "/a/")[0])

    def test_unknown_target(self):
        self.assertIsNone(view.resolve(cfg(), "student01", False, "/zzz/")[0])

    def test_cookie_path(self):
        self.assertEqual(view.rewrite_cookie("s=1; Path=/x; HttpOnly"), "s=1; HttpOnly; Path=/")



class IndexTest(unittest.TestCase):
    def test_student_lists_targets(self):
        p = view.index_page(cfg(), "student01", False, "/")
        self.assertIn(b'class="box off"', p)
        self.assertIsNone(view.index_page(cfg(), "student01", False, "/student02/"))

    def test_facilitator_lists_students_then_targets(self):
        self.assertIn(b'href="/ctf-view/student02/"', view.index_page(cfg(), "admin", True, "/"))
        self.assertIn(b"10.42.0.105", view.index_page(cfg(), "admin", True, "/student02/"))
        self.assertIsNone(view.index_page(cfg(), "admin", True, "/a/"))

    def test_only_live_box_is_a_link(self):
        orig = view._live
        view._live = lambda ip, port: ip.endswith(".101")
        try:
            p = view.index_page(cfg(), "student01", False, "/")
        finally:
            view._live = orig
        self.assertEqual(p.count(b'class="box live"'), 1)
        self.assertIn(b'href="/ctf-view/b/"', p)
        self.assertEqual(p.count(b'class="box off"'), 1)


if __name__ == "__main__":
    unittest.main()
