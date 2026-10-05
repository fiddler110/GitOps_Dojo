"""The allocator's HTTP handlers over real HTTP (RV15): /auth-check, /assign,
/admin/release, /admin/release-unused, /admin/api/sessions and
/session-check, with web-terminal's control API faked. Run from
engine/allocator:

  python3 -B -m unittest discover -s tests -v
"""

import json
import os
import select
import socket
import sys
import threading
import time
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
import accounts  # noqa: E402
import allocation  # noqa: E402
import config  # noqa: E402
import server  # noqa: E402

FAC = config.FACILITATOR_USERNAME
ADMIN = {"X-Auth-User": FAC, "X-Requested-With": "dojo-admin"}


class FakeControl:
    """web-terminal's workspace-control API: records every call and answers
    from `answers` (path prefix -> body), else None (unreachable)."""

    def __init__(self):
        self.calls = []
        self.answers = {}

    def __call__(self, method, path, timeout=None):
        self.calls.append((method, path))
        for prefix, body in self.answers.items():
            if path.startswith(prefix):
                return body
        return None


class HandlerTest(unittest.TestCase):
    def setUp(self):
        self.control = FakeControl()
        self.patches = [mock.patch.object(allocation, "control_request", self.control),
                        mock.patch.object(allocation, "READY_CACHE", allocation.TTLCache(2.0)),
                        mock.patch.object(allocation, "STATUS_CACHE", allocation.TTLCache(3.0)),
                        mock.patch.object(allocation, "ASSIGN_LIMIT", allocation.AssignLimit(100, 100)),
                        mock.patch.object(allocation, "STATE_FILE", ""),
                        mock.patch.object(config, "audit")]
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
        with allocation._state_lock:
            allocation.token_index.clear()
            for slot in allocation.slots.values():
                slot.update(name=None, ip=None, token=None, tool=None, assigned_at=None)

    def request(self, method, path, body=None, headers=None, gateway=True):
        """(status, headers, body) without following redirects."""
        h = {"X-Gateway-Token": config.GATEWAY_TOKEN} if gateway else {}
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
            with resp:
                return resp.status, resp.headers, resp.read()
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.headers, e.read()

    def student(self, name="Ada"):
        sid, token = allocation.claim_slot(name, "10.0.0.1")
        return sid, {"Cookie": f"{config.COOKIE_NAME}={token}"}

    def held(self, sid):
        return allocation.slot_snapshot(sid)["name"] is not None


class GatewayToken(HandlerTest):
    def test_every_route_needs_the_gateway_token(self):
        for method, path in (("GET", "/auth-check?tool=ide"), ("GET", "/session-check"),
                             ("GET", "/admin/api/sessions"), ("POST", "/assign"),
                             ("POST", "/admin/release-unused")):
            status = self.request(method, path, "" if method == "POST" else None,
                                  {"X-Auth-User": FAC, "X-Requested-With": "dojo-admin"}, gateway=False)[0]
            self.assertEqual(status, 403, f"{method} {path}")
        self.assertEqual(self.request("GET", "/auth-check?tool=ide", headers={"X-Gateway-Token": "wrong"},
                                      gateway=False)[0], 403)
        self.assertEqual(self.control.calls, [])


class PostBody(HandlerTest):
    """A rejected POST is answered only after its body is read. Every reply
    closes the connection, and closing over unread bytes sends RST, so the
    client could get ConnectionResetError instead of the status (it made
    test_reset's 403 checks flaky under load). Raw sockets, so the body can be
    held back: a reply that comes first was sent without reading it."""

    def test_rejections_wait_for_the_body(self):
        body = b"confirm=student01"
        gw = {"X-Gateway-Token": config.GATEWAY_TOKEN}
        for path, headers, status in (
                ("/admin/reset/student01", {}, 403),                                       # no gateway token
                ("/admin/reset/student01", {**gw, "X-Auth-User": FAC}, 403),               # no X-Requested-With
                ("/admin/reset/student01", {**gw, "X-Requested-With": "dojo-admin"}, 403),  # not the facilitator
                ("/admin/reset/root", {**gw, "X-Auth-User": FAC, "X-Requested-With": "dojo-admin"}, 404),
                ("/no-such-route", gw, 404)):
            with self.subTest(path=path, headers=sorted(headers)):
                head = f"POST {path} HTTP/1.1\r\nHost: x\r\nContent-Length: {len(body)}\r\n"
                head += "".join(f"{k}: {v}\r\n" for k, v in headers.items()) + "\r\n"
                with socket.create_connection(("127.0.0.1", self.port), timeout=5) as s:
                    s.sendall(head.encode())
                    self.assertFalse(select.select([s], [], [], 0.3)[0], "replied before reading the body")
                    s.sendall(body)
                    reply = s.recv(4096)
                self.assertTrue(reply.startswith(f"HTTP/1.0 {status} ".encode()), reply[:40])


class AuthCheck(HandlerTest):
    def test_unknown_tool_is_400(self):
        self.assertEqual(self.request("GET", "/auth-check?tool=shell")[0], 400)
        self.assertEqual(self.request("GET", "/auth-check")[0], 400)

    def test_no_identity_goes_to_the_front_page(self):
        status, headers, _ = self.request("GET", "/auth-check?tool=ide")
        self.assertEqual((status, headers["Location"]), (303, "/"))
        forged = {"Cookie": f"{config.COOKIE_NAME}=not-a-real-token"}
        self.assertEqual(self.request("GET", "/auth-check?tool=ide", headers=forged)[0], 303)
        self.assertEqual(self.control.calls, [])

    def test_ready_workspace_gets_its_own_port_and_is_cached(self):
        sid, cookie = self.student()
        self.control.answers["/start/"] = b'{"ready": true}'
        status, headers, _ = self.request("GET", "/auth-check?tool=ide", headers=cookie)
        self.assertEqual((status, headers["X-Upstream-Port"]), (200, str(allocation.ide_port(sid))))
        status, headers, _ = self.request("GET", "/auth-check?tool=term", headers=cookie)
        self.assertEqual((status, headers["X-Upstream-Port"]), (200, str(allocation.term_port(sid))))
        self.request("GET", "/auth-check?tool=ide", headers=cookie)
        self.assertEqual(self.control.calls, [("POST", f"/start/ide/{sid}"), ("POST", f"/start/term/{sid}")])

    def test_not_ready_or_unreachable_is_the_starting_page_and_not_cached(self):
        sid, cookie = self.student()
        self.control.answers["/start/"] = b'{"ready": false}'
        self.assertEqual(self.request("GET", "/auth-check?tool=ide", headers=cookie)[0], 202)
        del self.control.answers["/start/"]
        self.assertEqual(self.request("GET", "/auth-check?tool=ide", headers=cookie)[0], 202)
        self.control.answers["/start/"] = b"not json"
        self.assertEqual(self.request("GET", "/auth-check?tool=ide", headers=cookie)[0], 202)
        self.assertEqual(len(self.control.calls), 3)

    def test_facilitator_gets_their_own_workspace(self):
        self.control.answers["/start/"] = b'{"ready": true}'
        status, headers, _ = self.request("GET", "/auth-check?tool=ide", headers={"X-Auth-User": FAC})
        self.assertEqual((status, headers["X-Upstream-Port"]), (200, str(allocation.ide_port(FAC))))
        self.assertEqual(self.control.calls, [("POST", f"/start/ide/{FAC}")])

    def test_released_cookie_stops_working(self):
        sid, cookie = self.student()
        allocation.release_slot(sid)
        self.assertEqual(self.request("GET", "/auth-check?tool=ide", headers=cookie)[0], 303)


class Assign(HandlerTest):
    def test_no_name_shows_the_form_again(self):
        self.assertEqual(self.request("POST", "/assign", "name=++")[0], 400)
        self.assertEqual(allocation.held_slots(), {})

    def test_claims_a_slot_and_sets_the_cookie(self):
        status, headers, _ = self.request("POST", "/assign", "name=Ada")
        self.assertEqual((status, headers["Location"]), (303, "/"))
        cookie = headers["Set-Cookie"]
        self.assertTrue(cookie.startswith(f"{config.COOKIE_NAME}="))
        self.assertIn("HttpOnly", cookie)
        held = allocation.held_slots()
        self.assertEqual([s["name"] for s in held.values()], ["Ada"])
        sid = next(iter(held))
        body = self.request("GET", "/whoami", headers={"Cookie": cookie.split(";")[0]})[2]
        self.assertEqual(json.loads(body), {"user": sid})

    def test_name_is_capped(self):
        self.request("POST", "/assign", "name=" + "x" * 200)
        self.assertEqual([len(s["name"]) for s in allocation.held_slots().values()], [60])

    def test_returning_browser_keeps_its_slot(self):
        sid, cookie = self.student()
        status, _, body = self.request("POST", "/assign", "name=Someone+else", cookie)
        self.assertEqual(status, 200)
        self.assertIn(sid.encode(), body)
        self.assertEqual(list(allocation.held_slots()), [sid])

    def test_facilitator_never_takes_a_slot(self):
        status, _, _ = self.request("POST", "/assign", "name=Boss", {"X-Auth-User": FAC})
        self.assertEqual(status, 200)
        self.assertEqual(allocation.held_slots(), {})

    def test_rate_limited(self):
        with mock.patch.object(allocation, "ASSIGN_LIMIT", allocation.AssignLimit(1, 1)):
            self.assertEqual(self.request("POST", "/assign", "name=A")[0], 303)
            status, headers, _ = self.request("POST", "/assign", "name=B")
        self.assertEqual(status, 429)
        self.assertGreaterEqual(int(headers["Retry-After"]), 1)
        self.assertEqual(len(allocation.held_slots()), 1)

    def test_full_lab(self):
        with mock.patch.object(allocation, "find_free_slot", return_value=None):
            status, headers, body = self.request("POST", "/assign", "name=Late")
        self.assertEqual(status, 200)
        self.assertIsNone(headers["Set-Cookie"])
        self.assertEqual(allocation.held_slots(), {})


class Release(HandlerTest):
    def test_needs_the_admin_header(self):
        sid, _ = self.student()
        self.assertEqual(self.request("POST", f"/admin/release/{sid}", "", {"X-Auth-User": FAC})[0], 403)
        self.assertTrue(self.held(sid))
        self.assertEqual(self.control.calls, [])

    def test_frees_the_slot_and_stops_the_workspace(self):
        sid, cookie = self.student()
        status, _, body = self.request("POST", f"/admin/release/{sid}", "", ADMIN)
        self.assertEqual((status, json.loads(body)), (200, {"released": sid}))
        self.assertFalse(self.held(sid))
        self.assertIn(("POST", f"/stop/{sid}"), self.control.calls)
        self.assertEqual(self.request("GET", "/whoami", headers=cookie)[2], b'{"user": null}')

    def test_free_slot_is_a_no_op_and_unknown_is_404(self):
        sid = config.STUDENT_IDS[0]
        self.assertEqual(self.request("POST", f"/admin/release/{sid}", "", ADMIN)[0], 200)
        self.assertEqual(self.control.calls, [])
        self.assertEqual(self.request("POST", "/admin/release/nobody", "", ADMIN)[0], 404)

    def test_bot_is_restarted(self):
        with mock.patch.object(config, "BOT_IDS", ["testuser1"]):
            status, _, body = self.request("POST", "/admin/release/testuser1", "", ADMIN)
        self.assertEqual((status, json.loads(body)), (200, {"released": "testuser1"}))
        self.assertEqual(self.control.calls, [("POST", "/stop/testuser1")])


class ReleaseUnused(HandlerTest):
    def age(self, sid, seconds):
        with allocation._state_lock:
            allocation.slots[sid]["assigned_at"] = time.time() - seconds

    def test_needs_the_admin_header(self):
        self.assertEqual(self.request("POST", "/admin/release-unused", "", {"X-Auth-User": FAC})[0], 403)

    def test_frees_only_old_idle_slots(self):
        idle, _ = self.student("Idle")
        busy, _ = self.student("Busy")
        watched, _ = self.student("Watched")
        new, _ = self.student("New")
        for sid in (idle, busy, watched):
            self.age(sid, allocation.UNUSED_AFTER_SECONDS + 5)
        self.control.answers["/status"] = json.dumps(
            {busy: {"active": True}, watched: {"watchable": True}}).encode()
        status, _, body = self.request("POST", "/admin/release-unused", "", ADMIN)
        self.assertEqual((status, json.loads(body)), (200, {"released": [idle]}))
        self.assertEqual([self.held(s) for s in (idle, busy, watched, new)], [False, True, True, True])
        query = next(p for m, p in self.control.calls if p.startswith("/status"))
        self.assertNotIn(new, query)

    def test_nothing_old_makes_no_status_call(self):
        self.student()
        self.assertEqual(json.loads(self.request("POST", "/admin/release-unused", "", ADMIN)[2]),
                         {"released": []})
        self.assertEqual(self.control.calls, [])

    def test_status_unavailable_releases_nothing(self):
        sid, _ = self.student()
        self.age(sid, allocation.UNUSED_AFTER_SECONDS + 5)
        self.assertEqual(self.request("POST", "/admin/release-unused", "", ADMIN)[0], 503)
        self.control.answers["/status"] = b"not json"
        self.assertEqual(self.request("POST", "/admin/release-unused", "", ADMIN)[0], 503)
        self.assertTrue(self.held(sid))


class SessionsApi(HandlerTest):
    def test_rows_for_students_then_bots_with_one_cached_status_call(self):
        a, _ = self.student("Ada")
        b, _ = self.student("Bo")
        self.control.answers["/status"] = json.dumps(
            {a: {"active": True, "watchable": True}, "testuser1": {"active": True}}).encode()
        with mock.patch.object(config, "BOT_IDS", ["testuser1"]):
            rows = json.loads(self.request("GET", "/admin/api/sessions", headers={"X-Auth-User": FAC})[2])
            self.request("GET", "/admin/api/sessions", headers={"X-Auth-User": FAC})
        self.assertEqual([(r["studentId"], r["name"], r["active"], r["watchable"]) for r in rows],
                         [(a, "Ada", True, True), (b, "Bo", False, False),
                          ("testuser1", "Demo bot (testuser1)", True, False)])
        self.assertEqual(rows[0]["ip"], "10.0.0.1")
        self.assertEqual(len([c for c in self.control.calls if c[1].startswith("/status")]), 1)

    def test_status_down_still_lists_everyone(self):
        a, _ = self.student()
        rows = json.loads(self.request("GET", "/admin/api/sessions", headers={"X-Auth-User": FAC})[2])
        self.assertEqual([(r["studentId"], r["active"]) for r in rows], [(a, False)])

    def test_empty_class_makes_no_call(self):
        with mock.patch.object(config, "BOT_IDS", []):
            self.assertEqual(json.loads(self.request("GET", "/admin/api/sessions")[2]), [])
        self.assertEqual(self.control.calls, [])


class LoginPage(HandlerTest):
    def test_login_form_is_served(self):
        status, _, body = self.request("GET", "/login")
        self.assertEqual(status, 200)
        self.assertIn(b'name="username"', body)


class SessionCheck(HandlerTest):
    def login(self, account):
        return {"Cookie": f"{accounts.SESSION_COOKIE}={accounts.make_session(account)}"}

    def test_page_load_without_a_session_goes_to_login_with_next(self):
        page = {"Accept": "text/html,application/xhtml+xml", "X-Forwarded-Uri": "/slides/talk.md"}
        status, headers, _ = self.request("GET", "/session-check", headers=page)
        self.assertEqual((status, headers["Location"]), (303, "/login?next=%2Fslides%2Ftalk.md"))
        page["X-Forwarded-Uri"] = "/"
        self.assertEqual(self.request("GET", "/session-check", headers=page)[1]["Location"], "/login")

    def test_poll_without_a_session_is_401(self):
        self.assertEqual(self.request("GET", "/session-check", headers={"Accept": "application/json"})[0], 401)
        post = {"Accept": "text/html", "X-Forwarded-Method": "POST"}
        self.assertEqual(self.request("GET", "/session-check", headers=post)[0], 401)

    def test_tampered_session_is_401(self):
        cookie = self.login(config.TTYD_USERNAME)
        cookie["Cookie"] = cookie["Cookie"][:-2] + "00"
        self.assertEqual(self.request("GET", "/session-check", headers=cookie)[0], 401)

    def test_class_login_passes_but_not_for_the_facilitator_role(self):
        cls = self.login(config.TTYD_USERNAME)
        status, headers, _ = self.request("GET", "/session-check", headers=cls)
        self.assertEqual((status, headers["X-Session-User"]), (200, config.TTYD_USERNAME))
        self.assertEqual(self.request("GET", "/session-check?role=facilitator", headers=cls)[0], 403)
        status, headers, _ = self.request("GET", "/session-check?role=facilitator", headers=self.login(FAC))
        self.assertEqual((status, headers["X-Session-User"]), (200, FAC))


if __name__ == "__main__":
    unittest.main()
