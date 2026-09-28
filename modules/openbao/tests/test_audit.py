"""Unit tests for openbao-audit's facilitator tab (no stack needed):

    python3 -B -m unittest discover -s modules/openbao/tests -p 'test_*.py'

A temporary file stands in for OpenBao's audit log.
"""
import http.client
import http.server
import json
import os
import sys
import tempfile
import threading
import unittest

TOKEN = "gw-token"
LOG = tempfile.NamedTemporaryFile("w", suffix=".log", delete=False)
os.environ.update(AUDIT_FILE=LOG.name, GATEWAY_TOKEN=TOKEN, FACILITATOR_USERNAME="root")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "audit"))
import audit as a  # noqa: E402


def entry(ns, op, path, accessor, who, error=None, created=None):
    doc = {"type": "response", "time": "2026-09-25T12:00:00Z", "error": error,
           "request": {"namespace": {"path": ns + "/" if ns else ""}, "operation": op, "path": path},
           "auth": {"accessor": accessor, "display_name": who, "policies": ["default"]},
           "response": {}}
    if created:
        doc["response"]["auth"] = {"accessor": created}
    return json.dumps(doc)


class AuditPanel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        lines = [
            entry("students/student01", "read", "app/data/db", "acc1", "oidc-student01"),
            entry("students/student02", "read", "app/data/db", "acc2", "oidc-student02",
                  error="1 error occurred:\n\t* permission denied\n"),
            entry("", "update", "secret/data/students/student01/hello", "acc3", "oidc-student01"),
            entry("", "read", "secret/data/students/student02/x", "acc9", "<img src=x onerror=alert(1)>"),
            entry("students/student01", "update", "auth/token/create", "acc1", "oidc-student01", created="acc5"),
            '{"type": "request"}', "not json",
        ]
        LOG.write("\n".join(lines) + "\n")
        LOG.flush()
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), a.Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        LOG.close()
        os.unlink(LOG.name)

    def get(self, path, token=TOKEN, user="root"):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_port, timeout=5)
        headers = {}
        if token is not None:
            headers["X-Gateway-Token"] = token
        if user is not None:
            headers["X-Auth-User"] = user
        c.request("GET", path, headers=headers)
        r = c.getresponse()
        body = r.read()
        return r.status, r.getheader("Content-Security-Policy"), body

    def entries(self, query=""):
        status, _, body = self.get("/api/entries" + query)
        self.assertEqual(status, 200)
        return json.loads(body)

    def test_facilitator_only(self):
        for path in ("/", "/panel.js", "/panel.css", "/api/entries"):
            self.assertEqual(self.get(path, token=None)[0], 403, path)
            self.assertEqual(self.get(path, token="wrong")[0], 403, path)
            self.assertEqual(self.get(path, user="student01")[0], 403, path)
            self.assertEqual(self.get(path, user=None)[0], 403, path)
            status, csp, _ = self.get(path)
            self.assertEqual(status, 200, path)
            self.assertIn("script-src 'self'", csp)
            self.assertNotIn("unsafe-inline", csp)

    def test_healthz_open(self):
        self.assertEqual(self.get("/healthz", token=None, user=None)[0], 200)

    def test_newest_first_and_students(self):
        doc = self.entries()
        self.assertEqual(doc["total"], 5)
        self.assertEqual(doc["entries"][0]["path"], "auth/token/create")
        self.assertEqual(doc["students"], ["student01", "student02"])

    def test_student_includes_shared_folder(self):
        paths = [e["path"] for e in self.entries("?student=student01")["entries"]]
        self.assertEqual(paths, ["auth/token/create", "secret/data/students/student01/hello", "app/data/db"])
        paths = [e["path"] for e in self.entries("?student=student02")["entries"]]
        self.assertEqual(paths, ["secret/data/students/student02/x", "app/data/db"])

    def test_filters(self):
        self.assertEqual(len(self.entries("?accessor=acc5")["entries"]), 1)  # the entry that made it
        self.assertEqual(len(self.entries("?accessor=acc1")["entries"]), 2)
        self.assertEqual(len(self.entries("?op=update")["entries"]), 2)
        self.assertEqual(len(self.entries("?path=secret/")["entries"]), 2)
        errs = self.entries("?errors=1")["entries"]
        self.assertEqual([e["accessor"] for e in errs], ["acc2"])
        self.assertEqual(len(self.entries("?limit=2")["entries"]), 2)
        self.assertEqual(len(self.entries("?limit=bad")["entries"]), 5)

    def test_panel_uses_text_only(self):
        js = open(os.path.join(os.path.dirname(a.__file__), "panel.js")).read()
        self.assertNotIn("innerHTML", js)
        html = open(os.path.join(os.path.dirname(a.__file__), "panel.html")).read()
        self.assertNotIn("<style", html)
        self.assertNotIn("style=", html)
        self.assertNotIn("<script>", html)


if __name__ == "__main__":
    unittest.main()
