"""Port-squat helpers of workspace-control.py (REVIEW.md P4).

Run: cd engine/web-terminal && python3 -B -m unittest discover -s tests
"""
import importlib.util
import io
import pathlib
import unittest
from unittest import mock

SRC = pathlib.Path(__file__).resolve().parents[1] / "workspace-control.py"
spec = importlib.util.spec_from_file_location("workspace_control", SRC)
wc = importlib.util.module_from_spec(spec)
with mock.patch.dict("os.environ", {"CONTROL_TOKEN": "test"}):
    spec.loader.exec_module(wc)  # only defines things; servers start in main()

HEADER = "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnmt   uid  timeout inode\n"


def row(port, state, uid, inode):
    return (f"   0: 0100007F:{port:04X} 00000000:0000 {state} 00000000:00000000 "
            f"00:00000000 00000000  {uid}        0 {inode} 1 0000000000000000 100 0 0 10 0\n")


TCP = HEADER + row(9101 - 100, "0A", 1001, 111) + row(9500, "01", 1002, 222) + row(9300, "0A", 0, 333)
TCP6 = HEADER + row(9300, "0A", 1003, 444)


def fake_open(files):
    def _open(path, *a, **k):
        if path in files:
            return io.StringIO(files[path])
        raise FileNotFoundError(path)
    return _open


class Listeners(unittest.TestCase):
    def test_parses_listen_rows_from_both_files(self):
        with mock.patch("builtins.open", fake_open({"/proc/net/tcp": TCP, "/proc/net/tcp6": TCP6})):
            got = wc._listeners()
        self.assertEqual(got, {9001: [(1001, "111")], 9300: [(0, "333"), (1003, "444")]})

    def test_missing_files_give_empty(self):
        with mock.patch("builtins.open", fake_open({})):
            self.assertEqual(wc._listeners(), {})

    def test_garbage_is_skipped(self):
        with mock.patch("builtins.open", fake_open({"/proc/net/tcp": HEADER + "short 0A\n"})):
            self.assertEqual(wc._listeners(), {})


class Owner(unittest.TestCase):
    def setUp(self):
        self.users = {1001: "student01", 1002: "student02"}

    def allowed(self, port, uid):
        def getpwuid(u):
            if u not in self.users:
                raise KeyError(u)
            return mock.Mock(pw_name=self.users[u])
        with mock.patch.object(wc.pwd, "getpwuid", getpwuid):
            return wc._owner_allowed(port, uid)

    def test_root_allowed(self):
        self.assertTrue(self.allowed(wc.port_for("ide", "student01"), 0))

    def test_owner_allowed(self):
        self.assertTrue(self.allowed(wc.port_for("ide", "student01"), 1001))

    def test_other_uid_refused(self):
        self.assertFalse(self.allowed(wc.port_for("ide", "student01"), 1002))

    def test_unknown_uid_refused(self):
        self.assertFalse(self.allowed(wc.port_for("ide", "student01"), 4242))

    def test_account_without_number_refused(self):
        self.users[1003] = "nonumber"
        self.assertFalse(self.allowed(wc.port_for("ide", "student01"), 1003))


class PortOpen(unittest.TestCase):
    def setUp(self):
        self.port = wc.port_for("ide", "student01")
        p = mock.patch.object(wc, "_evict")
        self.evict = p.start()
        self.addCleanup(p.stop)
        p = mock.patch.object(wc.pwd, "getpwuid",
                              lambda u: mock.Mock(pw_name={1001: "student01"}.get(u) or (_ for _ in ()).throw(KeyError(u))))
        p.start()
        self.addCleanup(p.stop)

    def test_nothing_listening(self):
        self.assertFalse(wc.port_open(self.port, {}))
        self.evict.assert_not_called()

    def test_right_owner_is_ready(self):
        self.assertTrue(wc.port_open(self.port, {self.port: [(1001, "1")]}))
        self.evict.assert_not_called()

    def test_root_ttyd_is_ready(self):
        self.assertTrue(wc.port_open(self.port, {self.port: [(0, "1")]}))

    def test_squatter_is_evicted_and_not_ready(self):
        sq = (1002, "9")
        self.assertFalse(wc.port_open(self.port, {self.port: [(1001, "1"), sq]}))
        self.evict.assert_called_once_with(self.port, [sq])


if __name__ == "__main__":
    unittest.main()
