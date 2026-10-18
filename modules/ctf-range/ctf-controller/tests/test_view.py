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
                         ("student02", "b", "/ctf-view/b", "/login", False, None))

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
        self.assertEqual(view.rewrite_cookie("s=1; Path=/x; Domain=lab.example; HttpOnly", "/ctf-view/a"),
                         "s=1; HttpOnly; Path=/ctf-view/a/")

    def test_target_cannot_set_dojo_cookie(self):
        for name in ("dojo_login", "dojo_session", "DOJO_gate"):
            self.assertIsNone(view.rewrite_cookie(f"{name}=x; Path=/", "/ctf-view/a"))

    def test_no_dojo_cookie_reaches_target(self):
        self.assertEqual(view.target_cookies("dojo_login=a; s=1; dojo_session=b;dojo_gate=c; t=2"), "s=1; t=2")
        self.assertIsNone(view.target_cookies("dojo_login=a; dojo_session=b"))
        self.assertIsNone(view.target_cookies(None))


class IsolationTest(unittest.TestCase):
    """A target is attacker-controlled script on the dojo origin: it must not reach
    a same-origin window (frame, framed by, opened) or a worker."""

    def test_csp_blocks_frames_and_workers(self):
        csp = view.SANDBOX["Content-Security-Policy"]
        for directive in ("connect-src 'none'", "frame-src 'none'", "worker-src 'none'", "frame-ancestors 'none'"):
            self.assertIn(directive, csp)
        self.assertEqual(view.SANDBOX["X-Frame-Options"], "DENY")
        self.assertEqual(view.SANDBOX["Cross-Origin-Opener-Policy"], "same-origin")

    def test_origin_wide_headers_dropped(self):
        for h in ("Service-Worker-Allowed", "Clear-Site-Data", "Strict-Transport-Security", "Refresh",
                  "Access-Control-Allow-Origin", "Cross-Origin-Opener-Policy", "Content-Security-Policy"):
            self.assertTrue(view.drop_response_header(h), h)
        for h in ("Content-Type", "Content-Disposition", "WWW-Authenticate", "X-Debug-Token"):
            self.assertFalse(view.drop_response_header(h), h)



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


class PortTest(unittest.TestCase):
    def test_port_suffix_is_parsed(self):
        r = view.resolve(cfg(), "student01", False, "/a:8514/login")
        self.assertEqual((r[1], r[2], r[3], r[5]), ("a", "/ctf-view/a:8514", "/login", 8514))

    def test_no_port_is_none(self):
        self.assertIsNone(view.resolve(cfg(), "student01", False, "/a/")[5])

    def test_bad_port_refused(self):
        for bad in ("/a:0/", "/a:70000/", "/a:x/"):
            self.assertIsNone(view.resolve(cfg(), "student01", False, bad)[0], bad)


class IndexTest(unittest.TestCase):
    def test_index_csp_allows_its_own_form_only(self):
        self.assertIn("form-action 'self'", view.INDEX_CSP["Content-Security-Policy"])
        self.assertNotIn("form-action 'none'", view.INDEX_CSP["Content-Security-Policy"])
