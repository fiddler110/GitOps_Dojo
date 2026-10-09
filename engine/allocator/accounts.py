"""The class login: signed session cookies, password checks, the login rate guard and the /login page assets.
"""
import base64
import hashlib
import hmac
import os
import re
import threading
import time

from config import (
    BOT_COUNT, BOT_PASSWORD, BOT_PREFIX, FACILITATOR_PASSWORD, FACILITATOR_USERNAME, GATEWAY_TOKEN, TTYD_PASSWORD,
    TTYD_USERNAME,
)

# The front door (/login): a signed cookie replaces HTTP Basic Auth. The
# cookie names the account that signed in (the class login or the
# facilitator's); gateway/Caddyfile asks /session-check about it on every
# request and passes the answer upstream as X-Auth-User, exactly as
# basic_auth's user id used to be. Signed with a key derived from
# GATEWAY_TOKEN and both passwords, so changing either password signs
# everyone out. Stateless: nothing to store, survives allocator restarts.
SESSION_COOKIE = "dojo_login"
SESSION_SECONDS = 12 * 3600
_SESSION_KEY = hmac.new(GATEWAY_TOKEN.encode(),
                        f"dojo-login|{TTYD_PASSWORD}|{FACILITATOR_PASSWORD}".encode(),
                        hashlib.sha256).digest()


def _session_sig(body):
    return hmac.new(_SESSION_KEY, body.encode(), hashlib.sha256).hexdigest()


def make_session(account, now=None):
    exp = int((time.time() if now is None else now) + SESSION_SECONDS)
    body = base64.urlsafe_b64encode(account.encode()).decode().rstrip("=") + "." + str(exp)
    return body + "." + _session_sig(body)


def read_session(token, now=None):
    """The account a session cookie was issued to, or None."""
    try:
        name, exp, sig = token.split(".")
        body = f"{name}.{exp}"
        if not hmac.compare_digest(sig, _session_sig(body)):
            return None
        if int(exp) < (time.time() if now is None else now):
            return None
        account = base64.urlsafe_b64decode(name + "=" * (-len(name) % 4)).decode()
    except (ValueError, UnicodeDecodeError):
        return None
    return account if account in (TTYD_USERNAME, FACILITATOR_USERNAME) or is_bot_id(account) else None


def is_bot_id(name):
    """True for testuser1..testuserN while demo bots run (BOT_COUNT > 0)."""
    m = re.fullmatch(re.escape(BOT_PREFIX) + r"([1-9][0-9]*)", name or "")
    return bool(m) and BOT_COUNT > 0 and int(m.group(1)) <= BOT_COUNT


def check_login(username, password):
    """The account this username/password opens, or None. Both accounts are
    always compared, so timing says nothing about which one was close. An
    empty password never matches, whatever is configured. While bots run, a
    bot also signs in as itself with its Forgejo password (BOT_PASSWORD), so
    it can use identity-gated extension routes (a portal) as a student does:
    see handle_route_check; nothing else treats a bot session as a student."""
    if not username or not password:
        return None
    if is_bot_id(username):
        return username if hmac.compare_digest(password.encode(), BOT_PASSWORD.encode()) else None
    ok_class = hmac.compare_digest(username.encode(), TTYD_USERNAME.encode()) & \
        hmac.compare_digest(password.encode(), TTYD_PASSWORD.encode())
    ok_fac = hmac.compare_digest(username.encode(), FACILITATOR_USERNAME.encode()) & \
        hmac.compare_digest(password.encode(), FACILITATOR_PASSWORD.encode())
    return FACILITATOR_USERNAME if ok_fac else TTYD_USERNAME if ok_class else None


class LoginGuard:
    """Brute-force limit (remediation T1.1c, FIND-01): at most `limit` wrong
    guesses per client address per `window` seconds; past it the answer is
    429 before any password is compared. Only failures count, so a class
    behind one NAT address signing in correctly is never limited."""

    def __init__(self, limit=30, window=60, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self.fails = {}
        self.lock = threading.Lock()

    def _recent(self, ip):
        cutoff = self.clock() - self.window
        recent = [t for t in self.fails.get(ip, ()) if t > cutoff]
        if recent:
            self.fails[ip] = recent
        else:
            self.fails.pop(ip, None)
        return recent

    def blocked(self, ip):
        with self.lock:
            return len(self._recent(ip)) >= self.limit

    def fail(self, ip):
        with self.lock:
            if len(self.fails) > 2000:  # a spray from many addresses
                for other in list(self.fails):
                    self._recent(other)
            self.fails.setdefault(ip, []).append(self.clock())


LOGIN_GUARD = LoginGuard()
# Wrong access-code cookies seen by the gateway (--pass): 10 a minute per address.
GATE_GUARD = LoginGuard(limit=10)

LOGIN_DIR = os.environ.get("LOGIN_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "login")
LOGIN_ASSET_TYPES = {".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                     ".png": "image/png"}


def _load_login_assets():
    assets = {}
    for name in os.listdir(LOGIN_DIR):
        ext = os.path.splitext(name)[1]
        if ext in LOGIN_ASSET_TYPES:
            with open(os.path.join(LOGIN_DIR, name), "rb") as f:
                assets[name] = (LOGIN_ASSET_TYPES[ext], f.read())
    return assets


LOGIN_ASSETS = _load_login_assets()
with open(os.path.join(LOGIN_DIR, "login.html"), encoding="utf-8") as _f:
    LOGIN_HTML = _f.read()
