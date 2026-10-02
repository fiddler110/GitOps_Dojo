"""RV7: one student's slow Forgejo call must not hold up another student, the facilitator's PR tab or the bot."""
import http.server
import json
import os
import tempfile
import threading
import unittest
import urllib.request

import bot
import server
import support

REPO = "training/sample"


class SlowForgejo:
    """Answers enough of Forgejo for `student_status` / `handle`; a call made by a blocked login waits on `gate`."""

    def __init__(self):
        self.gate, self.entered = threading.Event(), threading.Event()
        self.block = None  # a path that waits until gate is set

    def __call__(self, method, path, body=None, raw=False):
        path = path.split("?")[0]
        if path == self.block:
            self.entered.set()
            self.gate.wait(10)
        if path == f"/repos/{REPO}/pulls":
            return 200, [{"number": 1, "title": "t", "user": {"login": "student01"}, "base": {"ref": "main"},
                          "head": {"sha": "abc", "ref": "b"}}]
        if path == f"/repos/{REPO}/pulls/1":
            return 200, {"number": 1, "state": "closed", "merged": True, "user": {"login": "student01"},
                         "head": {"sha": "abc"}}
        return 200, []


def sensei_with(api):
    s = bot.Sensei({"repo": REPO, "mode": "approve"}, api, "http://git-server:3000", sleep=lambda s: None)
    s.prs = {7: {"number": 7, "title": "x", "user": "student02", "sha": "s", "status": "needs-review", "reason": "",
                 "since": 0, "updated": 0, "commented": ""}}
    return s


class BotLockTests(unittest.TestCase):
    def test_slow_handle_blocks_only_its_own_pr(self):
        api = SlowForgejo()
        api.block = f"/repos/{REPO}/pulls/1"
        s = sensei_with(api)
        t = threading.Thread(target=s.handle, args=(1,))
        t.start()
        try:
            self.assertTrue(api.entered.wait(5))
            self.assertEqual(s.handle(1, wait=False), "busy")
            self.assertEqual([r["number"] for r in s.snapshot()], [7])  # the table is readable meanwhile
            self.assertEqual(s.attention(), 1)
            self.assertEqual(s.tick(), [])  # the loop leaves a PR someone else holds to the next pass
        finally:
            api.gate.set()
            t.join(5)
        self.assertEqual(s.prs[1]["status"], "merged")


class Resolver:
    def resolve(self, auth):
        return (auth or "").replace("token ", "") or None


class ServerLockTests(unittest.TestCase):
    def setUp(self):
        self.api = SlowForgejo()
        self.saved = (server.sensei, server.resolver, server.desk, server.GATEWAY_TOKEN, server.WATCHING)
        server.sensei = sensei_with(self.api)
        server.resolver = Resolver()
        server.desk = support.HelpDesk(os.path.join(tempfile.mkdtemp(), "help.json"))
        server.GATEWAY_TOKEN = "gw"
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]

    def tearDown(self):
        self.api.gate.set()
        self.httpd.shutdown()
        self.httpd.server_close()
        server.sensei, server.resolver, server.desk, server.GATEWAY_TOKEN, server.WATCHING = self.saved

    def get(self, path, headers, timeout=2):
        req = urllib.request.Request(self.base + path, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())

    def test_one_slow_student_blocks_nobody_else(self):
        # student01's `sensei status` is stuck in Forgejo (the reviewers lookup); hold it there.
        self.api.block = f"/repos/{REPO}/pulls"
        out = {}
        t = threading.Thread(target=lambda: out.update(self.get("/api/student/status", {"Authorization": "token student01"}, 10)))
        t.start()
        self.assertTrue(self.api.entered.wait(5))
        self.api.block = None  # only that first call is slow
        mine = self.get("/api/student/status", {"Authorization": "token student02"})
        self.assertEqual([r["number"] for r in mine["prs"]], [7])
        prs = self.get("/api/prs", {"X-Gateway-Token": "gw", "X-Auth-User": server.FACILITATOR})
        self.assertEqual(prs["attention"], 1)
        self.assertTrue(t.is_alive())  # student01 is still waiting the whole time
        self.api.gate.set()
        t.join(5)
        self.assertEqual(out["mode"], "approve")

    def test_same_student_calls_take_turns(self):
        self.assertIs(server.user_lock("student01"), server.user_lock("student01"))
        self.assertIsNot(server.user_lock("student01"), server.user_lock("student02"))


if __name__ == "__main__":
    unittest.main()
