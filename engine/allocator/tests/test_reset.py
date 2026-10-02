"""Student reset (reset.py and its wiring in server.py). Run from
engine/allocator:

  python3 -B -m unittest discover -s tests -v
"""

import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
for _k, _v in {"FORGEJO_ADMIN_USER": "admin", "FORGEJO_ADMIN_PASSWORD": "x",
               "CONTROL_TOKEN": "control-test", "GATEWAY_TOKEN": "gateway-test",
               "EXTENSIONS_FILE": os.path.join(HERE, "no-such-file.json")}.items():
    os.environ.setdefault(_k, _v)
import reset  # noqa: E402
import server  # noqa: E402


class FakeForgejo:
    """Just enough of the admin API, in memory. `calls` records every write."""

    def __init__(self, users=("student01", "student02"), pulls=(), branches=()):
        self.users = set(users)
        self.pulls = [dict(p) for p in pulls]
        self.branches = [dict(b) for b in branches]
        self.calls = []

    def call(self, method, path, body=None):
        bare = path.split("?")[0]
        if method != "GET":
            self.calls.append((method, bare, body))
        if bare == "/orgs/training/repos":
            return 200, [{"name": "repo", "default_branch": "main"}] if "page=1" in path else []
        if bare == "/repos/training/repo/pulls":
            return 200, [p for p in self.pulls if p["state"] == "open"] if "page=1" in path else []
        if bare == "/repos/training/repo/branches":
            return 200, list(self.branches) if "page=1" in path else []
        if bare == "/orgs/training/teams":
            return 200, [{"id": 7, "name": "students"}] if "page=1" in path else []
        if method == "PATCH" and bare.startswith("/repos/training/repo/pulls/"):
            n = int(bare.rsplit("/", 1)[1])
            for p in self.pulls:
                if p["number"] == n:
                    p["state"] = "closed"
            return 201, {}
        if method == "DELETE" and bare.startswith("/repos/training/repo/branches/"):
            name = bare[len("/repos/training/repo/branches/"):]
            before = len(self.branches)
            self.branches = [b for b in self.branches if b["name"] != name]
            return (204 if len(self.branches) < before else 404), None
        if bare.startswith("/admin/users/") and method == "DELETE":
            user = bare.rsplit("/", 1)[1]
            if user in self.users:
                self.users.discard(user)
                return 204, None
            return 404, None
        if bare.startswith("/users/") and method == "GET":
            return (200, {}) if bare.rsplit("/", 1)[1] in self.users else (404, None)
        if bare == "/admin/users" and method == "POST":
            self.users.add(body["username"])
            return 201, {}
        if bare.startswith("/admin/users/") and method == "PATCH":
            return 200, {}
        if method == "PUT" and bare.startswith("/teams/7/members/"):
            return 204, None
        return 500, {"message": f"unexpected {method} {path}"}

    expect = reset.Forgejo.expect
    pages = reset.Forgejo.pages


def pr(number, login, ref, repo="training/repo"):
    return {"number": number, "state": "open", "user": {"login": login},
            "head": {"ref": ref, "repo": {"full_name": repo}}}


def branch(name, author, protected=False):
    return {"name": name, "protected": protected,
            "commit": {"author": {"username": "", "email": f"{author}@example.com"}, "committer": {}}}


class ForgejoStepsTest(unittest.TestCase):
    def setUp(self):
        self.fj = FakeForgejo(
            pulls=[pr(1, "student01", "student01/fix"), pr(2, "student02", "shared"),
                   pr(3, "student01", "main", repo="student01/repo")],
            branches=[branch("main", "student01"), branch("student01/fix", "student01"),
                      branch("student01/old", "student01"), branch("shared", "student01"),
                      branch("guarded", "student01", protected=True), branch("student02/x", "student02")])

    def test_teardown_closes_prs_and_deletes_only_their_branches(self):
        detail = reset.forgejo_teardown(self.fj, "training", "student01")
        self.assertEqual(detail, "2 PR(s) closed, 2 branch(es) deleted, account deleted")
        self.assertEqual({p["number"] for p in self.fj.pulls if p["state"] == "closed"}, {1, 3})
        # main (default), shared (another student's open PR), guarded (protected) and
        # student02's branch all stay.
        self.assertEqual([b["name"] for b in self.fj.branches], ["main", "shared", "guarded", "student02/x"])
        self.assertNotIn("student01", self.fj.users)
        self.assertIn(("DELETE", "/admin/users/student01", None), self.fj.calls)

    def test_teardown_is_idempotent(self):
        reset.forgejo_teardown(self.fj, "training", "student01")
        self.assertEqual(reset.forgejo_teardown(self.fj, "training", "student01"),
                         "0 PR(s) closed, 0 branch(es) deleted, no account")

    def test_provision_creates_then_keeps(self):
        self.fj.users.discard("student01")
        self.assertEqual(reset.forgejo_provision(self.fj, "training", "student01", "pw"),
                         "account created, in team 'students'")
        self.assertIn(("POST", "/admin/users", {"username": "student01", "password": "pw",
                                                "email": "student01@example.com",
                                                "must_change_password": False}), self.fj.calls)
        self.assertEqual(reset.forgejo_provision(self.fj, "training", "student01", "pw"),
                         "account kept, in team 'students'")
        self.assertIn(("PUT", "/teams/7/members/student01", None), self.fj.calls)

    def test_forgejo_error_is_a_reset_error(self):
        self.fj.call = lambda *a, **k: (500, {"message": "boom"})
        with self.assertRaisesRegex(reset.ResetError, "HTTP 500 boom"):
            reset.forgejo_teardown(self.fj, "training", "student01")


class ResetManagerTest(unittest.TestCase):
    def manager(self, fail_at=None, seen=None):
        log = []

        def steps_for(sid):
            def step(name):
                def run():
                    if seen is not None:
                        seen.append((name, mgr.fenced(sid)))
                    if name == fail_at:
                        raise reset.ResetError(f"{name} broke")
                    return f"{name} ok"
                return run
            return [(n, n.title(), step(n)) for n in ("a", "b", "c")]

        mgr = reset.ResetManager(steps_for, lambda event, **f: log.append((event, f)), clock=lambda: 5.0)
        mgr.log = log
        return mgr

    def test_runs_in_order_and_fences_while_running(self):
        seen = []
        mgr = self.manager(seen=seen)
        self.assertTrue(mgr.request("student01"))
        self.assertTrue(mgr.fenced("student01"))
        self.assertFalse(mgr.request("student01"))  # already queued
        mgr.run_one(mgr.queue.get_nowait())
        self.assertEqual(seen, [("a", True), ("b", True), ("c", True)])
        snap = mgr.snapshot("student01")
        self.assertEqual(snap["state"], "done")
        self.assertEqual([s["status"] for s in snap["steps"]], ["done"] * 3)
        self.assertFalse(mgr.fenced("student01"))
        self.assertIn(("reset", {"target": "student01", "result": "done"}), mgr.log)

    def test_stops_at_first_failure_and_can_retry(self):
        mgr = self.manager(fail_at="b")
        mgr.request("student01")
        mgr.run_one(mgr.queue.get_nowait())
        snap = mgr.snapshot("student01")
        self.assertEqual(snap["state"], "failed")
        self.assertEqual([(s["status"], s["detail"]) for s in snap["steps"]],
                         [("done", "a ok"), ("failed", "b broke"), ("pending", "")])
        self.assertFalse(mgr.fenced("student01"))
        self.assertTrue(mgr.request("student01"))  # Retry

    def test_snapshot_is_a_copy_and_none_when_never_reset(self):
        mgr = self.manager()
        self.assertIsNone(mgr.snapshot("student02"))
        mgr.request("student01")
        mgr.snapshot("student01")["steps"][0]["status"] = "tampered"
        self.assertEqual(mgr.snapshot("student01")["steps"][0]["status"], "pending")

    def test_long_detail_is_cut(self):
        mgr = reset.ResetManager(lambda sid: [("x", "X", lambda: "y" * 500)], lambda *a, **k: None)
        mgr.request("student01")
        mgr.run_one(mgr.queue.get_nowait())
        self.assertEqual(len(mgr.snapshot("student01")["steps"][0]["detail"]), reset.DETAIL_MAX)


class TerminalStepTest(unittest.TestCase):
    def test_failed_hook_fails_the_step(self):
        body = json.dumps({"ok": False, "steps": [{"id": "files", "ok": True, "detail": ""},
                                                  {"id": "reset.d/50-x.sh", "ok": False, "detail": "nope"}]})
        with mock.patch.object(server, "control_request", return_value=body.encode()):
            with self.assertRaisesRegex(reset.ResetError, r"reset.d/50-x.sh: nope"):
                server.reset_terminal("student01")

    def test_no_answer_fails_the_step(self):
        with mock.patch.object(server, "control_request", return_value=None):
            with self.assertRaises(reset.ResetError):
                server.reset_terminal("student01")

    def test_uses_the_long_timeout(self):
        body = json.dumps({"ok": True, "steps": [{"id": "files", "ok": True}]}).encode()
        with mock.patch.object(server, "control_request", return_value=body) as call:
            self.assertEqual(server.reset_terminal("student01"), "1 step(s) ok")
        call.assert_called_once_with("POST", "/reset/student01", timeout=server.RESET_TERMINAL_TIMEOUT)

    def test_bot_gets_the_bot_password(self):
        with mock.patch.object(server, "BOT_IDS", ["testuser1"]), \
                mock.patch.object(reset, "forgejo_provision", return_value="ok") as provision:
            steps = dict((i, fn) for i, _label, fn in server.reset_steps("testuser1"))
            steps["forgejo-provision"]()
        self.assertEqual(provision.call_args[0][3], server.BOT_PASSWORD)


class HttpTest(unittest.TestCase):
    """The admin endpoint, the fence and the sessions field over real HTTP."""

    def setUp(self):
        self.resets = reset.ResetManager(lambda sid: [("a", "A", lambda: "ok")], lambda *a, **k: None)
        self.patches = [mock.patch.object(server, "RESETS", self.resets),
                        mock.patch.object(server, "control_request", return_value=None)]
        for p in self.patches:
            p.start()
        self.httpd = server.make_server(("127.0.0.1", 0))
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        for p in self.patches:
            p.stop()
        with server._state_lock:
            server.token_index.clear()
            for slot in server.slots.values():
                slot.update(name=None, ip=None, token=None, tool=None, assigned_at=None)

    def request(self, method, path, body=None, headers=None):
        h = {"X-Gateway-Token": server.GATEWAY_TOKEN}
        h.update(headers or {})
        data = body.encode() if body is not None else None
        if data is not None:
            h["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, headers=h, method=method)

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None

        try:
            resp = urllib.request.build_opener(NoRedirect).open(req, timeout=5)
            return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.read()

    ADMIN = {"X-Auth-User": "root", "X-Requested-With": "dojo-admin"}

    def test_reset_needs_header_facilitator_and_typed_id(self):
        sid = server.STUDENT_IDS[0]
        self.assertEqual(self.request("POST", f"/admin/reset/{sid}", f"confirm={sid}",
                                      {"X-Auth-User": "root"})[0], 403)
        self.assertEqual(self.request("POST", f"/admin/reset/{sid}", f"confirm={sid}",
                                      {"X-Requested-With": "dojo-admin"})[0], 403)
        self.assertEqual(self.request("POST", f"/admin/reset/{sid}", "confirm=student99", self.ADMIN)[0], 400)
        self.assertEqual(self.request("POST", f"/admin/reset/{sid}", "", self.ADMIN)[0], 400)
        self.assertEqual(self.request("POST", "/admin/reset/root", "confirm=root", self.ADMIN)[0], 404)
        self.assertEqual(self.request("POST", "/admin/reset/..%2Fx", "confirm=../x", self.ADMIN)[0], 404)
        self.assertFalse(self.resets.fenced(sid))
        status, body = self.request("POST", f"/admin/reset/{sid}", f"confirm={sid}", self.ADMIN)
        self.assertEqual((status, json.loads(body)), (202, {"reset": sid, "state": "queued"}))
        self.assertEqual(self.request("POST", f"/admin/reset/{sid}", f"confirm={sid}", self.ADMIN)[0], 409)

    def test_fenced_student_gets_the_starting_page_and_progress_shows(self):
        sid, token = server.claim_slot("Ada", "10.0.0.1")
        cookie = {"Cookie": f"{server.COOKIE_NAME}={token}"}
        self.resets.request(sid)
        self.assertEqual(self.request("GET", "/auth-check?tool=ide", headers=cookie)[0], 202)
        self.assertEqual(self.request("GET", "/forgejo-login", headers=cookie)[0], 503)
        rows = json.loads(self.request("GET", "/admin/api/sessions", headers={"X-Auth-User": "root"})[1])
        row = next(r for r in rows if r["studentId"] == sid)
        self.assertEqual(row["reset"]["state"], "queued")
        self.resets.run_one(self.resets.queue.get_nowait())
        # Unfenced: back to asking web-terminal (patched to no answer, so 202 again,
        # but through control_request this time).
        with mock.patch.object(server, "control_request", return_value=b'{"ready": true}') as call:
            self.assertEqual(self.request("GET", "/auth-check?tool=ide", headers=cookie)[0], 200)
        call.assert_called_once()


if __name__ == "__main__":
    unittest.main()
