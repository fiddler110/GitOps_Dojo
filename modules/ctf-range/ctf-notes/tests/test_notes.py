import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(HERE, ".."), os.path.join(HERE, "..", "..", "..", "_shared")]
import notes  # noqa: E402


class NotesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        os.mkdir(os.path.join(self.root, "student01"))

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, *parts):
        return os.path.join(self.root, "student01", *parts)

    def test_first_read_creates_the_template(self):
        text, _ = notes.read_notes("student01", self.root)
        self.assertEqual(text, notes.TEMPLATE)
        self.assertTrue(os.path.isfile(self.path("lab", "notes.md")))

    def test_mtime_is_exact_in_javascript(self):
        _, m = notes.read_notes("student01", self.root)
        self.assertLess(m, 2 ** 53)

    def test_save_then_read_back(self):
        _, m = notes.read_notes("student01", self.root)
        ok, m2 = notes.write_notes("student01", "creds: a/b\n", m, self.root)
        self.assertTrue(ok)
        self.assertEqual(notes.read_notes("student01", self.root), ("creds: a/b\n", m2))
        with open(self.path("lab", "notes.md")) as f:
            self.assertEqual(f.read(), "creds: a/b\n")

    def test_shrinking_save_truncates(self):
        _, m = notes.read_notes("student01", self.root)
        ok, m = notes.write_notes("student01", "x" * 500, m, self.root)
        ok, m = notes.write_notes("student01", "short", m, self.root)
        self.assertEqual(notes.read_notes("student01", self.root)[0], "short")

    def test_terminal_edit_is_a_conflict(self):
        _, m = notes.read_notes("student01", self.root)
        with open(self.path("lab", "notes.md"), "w") as f:
            f.write("edited in the terminal\n")
        ok, _ = notes.write_notes("student01", "mine", m, self.root)
        self.assertFalse(ok)
        self.assertEqual(notes.read_notes("student01", self.root)[0], "edited in the terminal\n")

    def test_force_overwrites(self):
        notes.read_notes("student01", self.root)
        with open(self.path("lab", "notes.md"), "w") as f:
            f.write("theirs\n")
        ok, _ = notes.write_notes("student01", "mine", None, self.root)
        self.assertTrue(ok)

    def test_symlinked_notes_file_refused(self):
        os.mkdir(self.path("lab"))
        target = os.path.join(self.root, "secret")
        with open(target, "w") as f:
            f.write("do not touch\n")
        os.symlink(target, self.path("lab", "notes.md"))
        with self.assertRaises(notes.NotesError):
            notes.write_notes("student01", "pwned", None, self.root)
        with open(target) as f:
            self.assertEqual(f.read(), "do not touch\n")

    def test_symlinked_lab_dir_refused(self):
        elsewhere = os.path.join(self.root, "other")
        os.mkdir(elsewhere)
        os.symlink(elsewhere, self.path("lab"))
        with self.assertRaises(notes.NotesError):
            notes.read_notes("student01", self.root)
        self.assertEqual(os.listdir(elsewhere), [])

    def test_hard_linked_file_refused(self):
        notes.read_notes("student01", self.root)
        os.link(self.path("lab", "notes.md"), os.path.join(self.root, "alias"))
        with self.assertRaises(notes.NotesError):
            notes.read_notes("student01", self.root)

    def test_bad_account_names(self):
        for bad in ("", "../etc", "a/b", "Student", None):
            with self.assertRaises(notes.NotesError):
                notes.read_notes(bad, self.root)

    def test_missing_home(self):
        with self.assertRaises(notes.NotesError):
            notes.read_notes("nobody", self.root)

    def test_size_cap(self):
        with self.assertRaises(notes.NotesError):
            notes.write_notes("student01", "x" * (notes.MAX_BYTES + 1), None, self.root)


    def test_read_only_view_creates_nothing(self):
        with self.assertRaises(notes.NotesError):
            notes.read_notes("student01", self.root, create=False)
        self.assertFalse(os.path.exists(self.path("lab")))
        notes.write_notes("student01", "hi\n", None, self.root)
        self.assertEqual(notes.read_notes("student01", self.root, create=False)[0], "hi\n")

    def test_students_listed_without_the_facilitator(self):
        os.mkdir(os.path.join(self.root, "admin"))
        os.mkdir(os.path.join(self.root, "student02"))
        os.symlink(os.path.join(self.root, "student02"), os.path.join(self.root, "student03"))
        self.assertEqual(notes.list_students(self.root, "admin"), ["student01", "student02"])


class FacilitatorViewTest(unittest.TestCase):
    """Over HTTP: only the facilitator lists students or reads a student's notes."""

    setUp_home, tearDown_home, path = NotesTest.setUp, NotesTest.tearDown, NotesTest.path

    def setUp(self):
        self.setUp_home()
        import threading
        self.saved = (notes.TOKEN, notes.FACILITATOR, notes.HOME_ROOT)
        notes.TOKEN, notes.FACILITATOR, notes.HOME_ROOT = "gw", "admin", self.root
        os.mkdir(os.path.join(self.root, "student02"))
        notes.write_notes("student02", "secret plan\n", None, self.root)
        self.srv = notes.http.server.ThreadingHTTPServer(("127.0.0.1", 0), notes.make_handler())
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        notes.TOKEN, notes.FACILITATOR, notes.HOME_ROOT = self.saved
        self.tearDown_home()

    def get(self, path, user):
        import http.client
        import json
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1], timeout=5)
        c.request("GET", path, headers={"X-Gateway-Token": "gw", "X-Auth-User": user})
        r = c.getresponse()
        return r.status, json.loads(r.read() or b"{}")

    def test_only_the_facilitator_lists_and_reads_others(self):
        self.assertEqual(self.get("/api/students", "student01")[0], 403)
        self.assertEqual(self.get("/api/notes?user=student02", "student01")[0], 403)
        status, doc = self.get("/api/students", "admin")
        self.assertEqual((status, doc["students"]), (200, ["student01", "student02"]))
        status, doc = self.get("/api/notes?user=student02", "admin")
        self.assertEqual((status, doc["text"]), (200, "secret plan\n"))
        self.assertEqual(self.get("/api/notes?user=student01", "admin")[0], 409)   # no notes yet: nothing created
        self.assertFalse(os.path.exists(self.path("lab")))


if __name__ == "__main__":
    unittest.main()
