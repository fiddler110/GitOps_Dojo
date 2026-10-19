"""/status without forks (REVIEW.md 2.3): one /proc pass for "active", a
socket probe for "watchable".

Run: cd engine/web-terminal && python3 -B -m unittest discover -s tests
"""
import importlib.util
import io
import json
import os
import pathlib
import socket
import tempfile
import threading
import unittest
import urllib.request
from unittest import mock

SRC = pathlib.Path(__file__).resolve().parents[1] / "workspace-control.py"
spec = importlib.util.spec_from_file_location("workspace_control_status", SRC)
wc = importlib.util.module_from_spec(spec)
with mock.patch.dict("os.environ", {"CONTROL_TOKEN": "test"}):
    spec.loader.exec_module(wc)


def status(uid):
    return f"Name:\tx\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\nGid:\t0\n"


PROC = {"/proc/1/status": status(0), "/proc/50/status": status(1001), "/proc/51/status": status(1001),
        "/proc/60/status": status(1002)}


def fake_open(path, *a, **k):
    if path in PROC:
        return io.StringIO(PROC[path])
    raise FileNotFoundError(path)


def pw(uids):
    def _get(name):
        if name not in uids:
            raise KeyError(name)
        return mock.Mock(pw_uid=uids[name])
    return _get


class Active(unittest.TestCase):
    def setUp(self):
        p = [mock.patch.object(wc.os, "listdir", return_value=["1", "50", "51", "60", "77", "self", "net"]),
             mock.patch("builtins.open", fake_open),
             mock.patch.object(wc.pwd, "getpwnam", pw({"student01": 1001, "student02": 1002, "student03": 1003}))]
        for x in p:
            x.start()
            self.addCleanup(x.stop)
        self.addCleanup(wc.holders.clear)

    def test_one_pass_maps_pids_to_effective_uid(self):
        self.assertEqual(wc._proc_euids(), {1: 0, 50: 1001, 51: 1001, 60: 1002})  # 77 exited mid-scan

    def test_is_alive_ignores_the_namespace_holder(self):
        euids = wc._proc_euids()
        self.assertTrue(wc.is_alive("student01", euids))
        self.assertFalse(wc.is_alive("student03", euids))
        self.assertFalse(wc.is_alive("nobody99", euids))
        wc.holders["student02"] = (None, 60, 61)
        self.assertFalse(wc.is_alive("student02", euids))  # only its holder is left
        wc.holders["student01"] = (None, 50, 52)
        self.assertTrue(wc.is_alive("student01", euids))   # pid 51 is real work

    def test_no_subprocess(self):
        with mock.patch.object(wc.subprocess, "run", side_effect=AssertionError("forked")):
            self.assertTrue(wc.is_alive("student01"))


class Watchable(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = mock.patch.object(wc.pwd, "getpwnam", pw({"student01": 1001}))
        p.start()
        self.addCleanup(p.stop)

    def listen(self, path):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.bind(path)
        s.listen(4)
        self.addCleanup(s.close)
        return s

    def stale(self, path):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.bind(path)
        s.close()  # file left behind, nothing accepting

    def test_socket_listening(self):
        live, dead = os.path.join(self.tmp.name, "live"), os.path.join(self.tmp.name, "dead")
        self.listen(live)
        self.stale(dead)
        self.assertTrue(wc._socket_listening(live))
        self.assertFalse(wc._socket_listening(dead))
        self.assertFalse(wc._socket_listening(os.path.join(self.tmp.name, "missing")))

    def test_tmux_socket_per_uid(self):
        os.mkdir(os.path.join(self.tmp.name, "tmux-1001"))
        tmpl = os.path.join(self.tmp.name, "tmux-{uid}", "default")
        with mock.patch.object(wc, "ZELLIJ", False), mock.patch.object(wc, "TMUX_SOCKET", tmpl), \
                mock.patch.object(wc.subprocess, "run", side_effect=AssertionError("forked")):
            self.assertFalse(wc.has_terminal_session("student01"))  # never opened a terminal
            self.stale(tmpl.format(uid=1001))
            self.assertFalse(wc.has_terminal_session("student01"))  # server killed, socket left
            os.unlink(tmpl.format(uid=1001))
            self.listen(tmpl.format(uid=1001))
            self.assertTrue(wc.has_terminal_session("student01"))
            self.assertFalse(wc.has_terminal_session("nobody99"))

    def test_zellij_any_live_session_socket(self):
        top = os.path.join(self.tmp.name, "zellij-{uid}")
        ver = os.path.join(top.format(uid=1001), "contract_version_1")
        os.makedirs(ver)
        with mock.patch.object(wc, "ZELLIJ", True), \
                mock.patch.object(wc, "ZELLIJ_SOCKET_DIRS", (os.path.join(self.tmp.name, "none-{uid}"), top)):
            self.assertFalse(wc.has_terminal_session("student01"))
            self.stale(os.path.join(ver, "old"))
            self.assertFalse(wc.has_terminal_session("student01"))
            self.listen(os.path.join(ver, "main"))
            self.assertTrue(wc.has_terminal_session("student01"))


class StatusEndpoint(unittest.TestCase):
    def test_same_shape_one_proc_pass(self):
        httpd = http_server()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        alive = {"student01": True, "student02": False}
        with mock.patch.object(wc, "_proc_euids", return_value={}) as scan, \
                mock.patch.object(wc, "is_alive", side_effect=lambda u, e=None: alive[u]), \
                mock.patch.object(wc, "has_terminal_session", side_effect=lambda u: u == "student02"):
            req = urllib.request.Request(f"http://127.0.0.1:{httpd.server_address[1]}/status?users=student01,student02,bad$",
                                         headers={"X-Control-Token": wc.CONTROL_TOKEN})
            with urllib.request.urlopen(req, timeout=5) as r:
                body = json.loads(r.read())
        self.assertEqual(body, {"student01": {"active": True, "watchable": False},
                                "student02": {"active": False, "watchable": True}})
        self.assertEqual(scan.call_count, 1)


def http_server():
    return wc.http.server.ThreadingHTTPServer(("127.0.0.1", 0), wc.Handler)

if __name__ == "__main__":
    unittest.main()
