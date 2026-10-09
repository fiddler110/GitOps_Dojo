"""The front door's session cookie and wrong-guess limit. Run from
engine/allocator:

  python3 -B -m unittest discover -s tests -v
"""

import base64
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
for _k, _v in {"FORGEJO_ADMIN_USER": "admin", "FORGEJO_ADMIN_PASSWORD": "x",
               "CONTROL_TOKEN": "control-test", "GATEWAY_TOKEN": "gateway-test",
               "EXTENSIONS_FILE": os.path.join(HERE, "no-such-file.json")}.items():
    os.environ.setdefault(_k, _v)
import accounts  # noqa: E402
import config  # noqa: E402
import handler  # noqa: E402


def setUpModule():
    # Another test module may have imported accounts first, without these.
    accounts.TTYD_USERNAME, accounts.TTYD_PASSWORD = "student", "class-pw"
    accounts.FACILITATOR_USERNAME, accounts.FACILITATOR_PASSWORD = "root", "fac-pw"
    accounts._SESSION_KEY = accounts.hmac.new(b"k", b"test", accounts.hashlib.sha256).digest()


class SessionTest(unittest.TestCase):
    def test_round_trip(self):
        for account in (accounts.TTYD_USERNAME, accounts.FACILITATOR_USERNAME):
            self.assertEqual(accounts.read_session(accounts.make_session(account)), account)

    def test_expired(self):
        token = accounts.make_session("student", now=1000)
        self.assertIsNone(accounts.read_session(token, now=1000 + accounts.SESSION_SECONDS + 1))
        self.assertEqual(accounts.read_session(token, now=1000 + 5), "student")

    def test_tampering(self):
        name, exp, sig = accounts.make_session("student").split(".")
        other = base64.urlsafe_b64encode(b"root").decode().rstrip("=")
        for bad in (f"{other}.{exp}.{sig}", f"{name}.{int(exp) + 999}.{sig}", f"{name}.{exp}.{'0' * 64}",
                    "", "a.b", "a.b.c.d", "!!!.1.2"):
            self.assertIsNone(accounts.read_session(bad), bad)

    def test_unknown_account_refused(self):
        self.assertIsNone(accounts.read_session(accounts.make_session("mallory")))


class CheckLoginTest(unittest.TestCase):
    def test_accounts(self):
        self.assertEqual(accounts.check_login("student", "class-pw"), "student")
        self.assertEqual(accounts.check_login("root", "fac-pw"), "root")

    def test_wrong(self):
        for user, pw in (("student", "fac-pw"), ("root", "class-pw"), ("student", ""), ("", ""),
                         ("Student", "class-pw"), ("student", "class-pw ")):
            self.assertIsNone(accounts.check_login(user, pw), (user, pw))


class BotLoginTest(unittest.TestCase):
    def setUp(self):
        self.saved = accounts.BOT_COUNT, accounts.BOT_PASSWORD
        accounts.BOT_COUNT, accounts.BOT_PASSWORD = 2, "bot-pw"

    def tearDown(self):
        accounts.BOT_COUNT, accounts.BOT_PASSWORD = self.saved

    def test_a_bot_signs_in_as_itself_while_bots_run(self):
        self.assertEqual(accounts.check_login("testuser2", "bot-pw"), "testuser2")
        self.assertEqual(accounts.read_session(accounts.make_session("testuser1")), "testuser1")

    def test_refused(self):
        for user, pw in (("testuser3", "bot-pw"), ("testuser0", "bot-pw"), ("testuser01", "bot-pw"),
                         ("testuser1", "class-pw"), ("testuser1", ""), ("student", "bot-pw")):
            self.assertIsNone(accounts.check_login(user, pw), (user, pw))

    def test_no_bots_no_bot_login(self):
        accounts.BOT_COUNT = 0
        self.assertIsNone(accounts.check_login("testuser1", "bot-pw"))
        self.assertIsNone(accounts.read_session(accounts.make_session("testuser1")))


class LoginGuardTest(unittest.TestCase):
    def test_blocks_after_limit_and_recovers(self):
        now = [0.0]
        guard = accounts.LoginGuard(limit=3, window=60, clock=lambda: now[0])
        for _ in range(3):
            self.assertFalse(guard.blocked("1.2.3.4"))
            guard.fail("1.2.3.4")
        self.assertTrue(guard.blocked("1.2.3.4"))
        self.assertFalse(guard.blocked("5.6.7.8"))
        now[0] = 61
        self.assertFalse(guard.blocked("1.2.3.4"))


class GateFailTest(unittest.TestCase):
    def test_ten_wrong_codes_then_429(self):
        import api
        codes = []

        class Fake:
            def client_ip(self): return "9.9.9.9"
            def send_response(self, c): codes.append(c)
            def send_header(self, *a): pass
            def end_headers(self): pass

        accounts.GATE_GUARD.fails.clear()
        for _ in range(12):
            api.Api.handle_gate_fail(Fake()) if hasattr(api, "Api") else handler.Handler.handle_gate_fail(Fake())
        self.assertEqual(codes, [401] * 10 + [429] * 2)
        accounts.GATE_GUARD.fails.clear()


class RedirectTargetTest(unittest.TestCase):
    def test_login_next(self):
        nxt = handler.Handler.login_next
        self.assertEqual(nxt("/slides/#3"), "/slides/#3")
        for bad in ("", None, "//evil.example", "https://evil.example", "/\\evil", "/login", "/login?next=/x"):
            self.assertEqual(nxt(bad), "/", bad)


if __name__ == "__main__":
    unittest.main()
