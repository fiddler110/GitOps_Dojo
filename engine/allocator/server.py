#!/usr/bin/env python3
"""Student self-service login + facilitator dashboard for the workshop engine.

One thread per connection (http.server.ThreadingHTTPServer, remediation
T3.4). It used to be single-threaded so that slot claiming needed no lock,
but then one idle or slow client stalled /auth-check -- and with it every
student's VS Code and terminal -- for the whole 3 s socket timeout, once per
idle connection. Now an idle socket only times out in its own thread.

Locking rules (keep them when touching shared state):
- `_state_lock` guards `slots` and `token_index`. Claiming a slot
  (claim_slot) finds the first free studentNN and writes it in one critical
  section, so two concurrent /assign requests can never get the same slot.
- Never hold a lock across I/O: no control_request, forgejo_login_request,
  probe or socket write inside one. Handlers copy what they need under the
  lock (slot_snapshot, held_slots), release it, then do the I/O.
- A release first records the slot's token, stops the workspace without the
  lock, then clears the slot only if the token is unchanged, so a slow
  release never frees a slot someone else has claimed in the meantime.
- AssignLimit, audit() and audit_check() each have their own small lock.

All state is in-memory and reset on container restart, matching this
project's ephemeral-by-design stack (see engine/docker-compose.yml).

Besides the request threads there is one background daemon that probes the
lab's services (Forgejo, terminals, slides, plus whatever a workshop lists
in STATUS_CHECKS) every few seconds for the facilitator's status strip
(/admin/api/status). It never touches `slots`, `token_index` or anything
else a request handler mutates: its only output is one status snapshot that
it replaces wholesale (a single reference assignment, atomic in CPython),
and request handlers only ever read that snapshot. All upstream I/O for
status happens in that thread; no request handler waits on a probe.
"""
import base64
import datetime
import hashlib
import hmac
import html
import http.client
import http.server
import json
import os
import re
import secrets
import socket
import ssl
import threading
import time
import urllib.parse

from dojo_secret import forgejo_password

PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost")
# Marks the session cookie Secure whenever the public deployment actually
# terminates TLS (see gateway/README's Deployment scenarios) -- the browser
# then refuses to ever send it over a plain-HTTP connection, e.g. to a
# spoofed same-name host on an open network. No effect (and no downside)
# on the plain-HTTP localhost path, since that's never HTTPS to begin with.
COOKIE_SECURE = PUBLIC_BASE_URL.startswith("https://")
# The gateway's own address when another proxy terminates TLS in front of it
# (e.g. http://:8080); empty means the gateway serves PUBLIC_BASE_URL itself.
GATEWAY_LISTEN = os.environ.get("GATEWAY_LISTEN", "")

STUDENT_COUNT = int(os.environ.get("STUDENT_COUNT", "30"))
STUDENT_PREFIX = os.environ.get("STUDENT_PREFIX", "student")
# Demo/test bots (--test, see engine/run.sh and README.md's "Demo bots"
# section): unlike real students, these never go through /assign -- they're
# always shown in the roster (see handle_sessions_api) so a facilitator can
# watch/Release them without any browser having "joined" as them. 0 (the
# default) disables this feature entirely.
BOT_COUNT = int(os.environ.get("BOT_COUNT", "0"))
BOT_PREFIX = os.environ.get("BOT_PREFIX", "testuser")
WORKSHOP_NAME = os.environ.get("WORKSHOP_NAME", "Workshop Lab")
# Must match web-terminal's actual facilitator Linux account -- entrypoint.sh
# and docker-compose.yml both default this to "root", not "facilitator", so
# it has to come from the same env var, never be hardcoded here.
FACILITATOR_USERNAME = os.environ.get("FACILITATOR_USERNAME", "root")


_audit_lock = threading.Lock()


def audit(event, **fields):
    """One JSON line on stdout per identity or control-plane decision
    (remediation T1.4, FIND-13): who, what, on which target, with what
    result. Never a secret: no tokens, passwords or cookies. Student names
    are student-typed; json.dumps escapes them."""
    rec = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds"),
           "event": event}
    rec.update(fields)
    line = json.dumps(rec, separators=(",", ":"))
    with _audit_lock:  # one whole line at a time from concurrent handlers
        print(line, flush=True)


# /auth-check runs once per request VS Code or ttyd makes (every asset), so
# logging each 200 would flood the log. Log every non-200, and a 200 only
# when it's the first for that (event, account, tool) or follows a non-200.
_last_check = {}
_last_check_lock = threading.Lock()


def audit_check(event, account, tool, status, **fields):
    key = (event, account, tool)
    with _last_check_lock:
        log = status != 200 or _last_check.get(key) != 200
        _last_check[key] = status
    if log:
        audit(event, account=account, tool=tool, result=status, **fields)


TTYD_USERNAME = os.environ.get("TTYD_USERNAME", "")
TTYD_PASSWORD = os.environ.get("TTYD_PASSWORD", "")
FACILITATOR_PASSWORD = os.environ.get("FACILITATOR_PASSWORD", "")
WORKSHOP_DESCRIPTION = os.environ.get("WORKSHOP_DESCRIPTION", "").strip()
# Deep-links the landing page's Forgejo button straight at the seeded
# workshop repo -- must match bootstrap.sh's FORGEJO_ORG/FORGEJO_REPO
# defaults (see docker-compose.yml's bootstrap service), not hardcoded here.
FORGEJO_ORG = os.environ.get("FORGEJO_ORG", "training")
FORGEJO_REPO = os.environ.get("FORGEJO_REPO", "sample-training-repo")
# SSO into Forgejo (see /forgejo-login below) signs a student in with their
# own password, forgejo_password(sid) from dojo_secret.py: the same one
# bootstrap.sh created the account with (remediation T2.1b, D13).
FORGEJO_ADMIN_USER = os.environ["FORGEJO_ADMIN_USER"]
FORGEJO_ADMIN_PASSWORD = os.environ["FORGEJO_ADMIN_PASSWORD"]
# Shared secret sent on every call to web-terminal's control API (see
# control_request() below) -- proves these calls actually come from the
# allocator, not some other container on the internal workshop_lab network.
# Must match web-terminal's own CONTROL_TOKEN (workspace-control.py).
CONTROL_TOKEN = os.environ["CONTROL_TOKEN"]
# Shared secret gateway/Caddyfile sends (via header_up X-Gateway-Token) on
# EVERY request it proxies to this process -- proves the request actually
# came through Caddy, not directly from some other container on the shared
# workshop_lab network (allocator must share that network with web-terminal
# and git-server for its own legitimate outbound calls -- see
# control_request()/forgejo_login_request() below -- and Docker/Podman
# bridge networks are not directional, so anything reachable BY allocator
# can equally reach allocator back). Without this check, resolve_identity()
# below trusting X-Auth-User would be forgeable by any process inside
# web-terminal (e.g. a student's own shell) simply by sending its own
# X-Auth-User: root header straight to http://allocator:8080/. Required, no
# default -- same fail-fast pattern as CONTROL_TOKEN above. Must match
# gateway's own GATEWAY_TOKEN (gateway/Caddyfile).
GATEWAY_TOKEN = os.environ["GATEWAY_TOKEN"]

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
    return account if account in (TTYD_USERNAME, FACILITATOR_USERNAME) else None


def check_login(username, password):
    """The account this username/password opens, or None. Both accounts are
    always compared, so timing says nothing about which one was close. An
    empty password never matches, whatever is configured."""
    if not username or not password:
        return None
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

# Workshop/module extensions (engine/MODULES-PLAN.md §3): cards, /admin tabs,
# route gates and status checks, already checked by render_extensions.py
# (run.sh, before start) and mounted read-only. Missing means none.
EXTENSIONS_FILE = os.environ.get("EXTENSIONS_FILE", "/etc/dojo/extensions/extensions.json")


def load_extensions(path=EXTENSIONS_FILE):
    empty = {"cards": [], "admin_tabs": [], "routes": [], "status_checks": []}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return empty
    return {k: list(data.get(k, [])) for k in empty}


EXTENSIONS = load_extensions()
EXT_ROUTES = {r["id"]: r for r in EXTENSIONS["routes"]}
# {user} in a route's host template stands for a whole DNS label.
DNS_LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")

WEB_TERMINAL_HOST = "web-terminal"
CONTROL_PORT = 7682
CONTROL_TIMEOUT = 3.0

GIT_SERVER_HOST = "git-server"
GIT_SERVER_PORT = 3000

IDE_PORT_BASE = 9000
TERM_PORT_BASE = 9500
FACILITATOR_IDE_PORT = 9099
FACILITATOR_TERM_PORT = 9599
# Facilitator's read-only mirror of a student's term session -- must match
# WATCH_PORT_BASE in web-terminal/workspace-control.py, which actually
# spawns the ttyd process on this port.
WATCH_PORT_BASE = 9600
# Same, for demo bots -- must match BOT_WATCH_PORT_BASE in
# web-terminal/workspace-control.py.
BOT_WATCH_PORT_BASE = 9800
# Same collision fix as watch_port() below, mirrored here for ide_port()/
# term_port() -- must match BOT_IDE_PORT_BASE/BOT_TERM_PORT_BASE in
# web-terminal/workspace-control.py. Not currently reachable (resolve_identity()
# never returns a bot id as `username` -- only a real student id or the
# facilitator), but kept symmetric per this file's own "must match" comments.
BOT_IDE_PORT_BASE = 9700
BOT_TERM_PORT_BASE = 9750

COOKIE_NAME = "dojo_session"

STUDENT_IDS = [f"{STUDENT_PREFIX}{n:02d}" for n in range(1, STUDENT_COUNT + 1)]
BOT_IDS = [f"{BOT_PREFIX}{n}" for n in range(1, BOT_COUNT + 1)]

# studentId -> {name, ip, token, tool, assigned_at}
slots = {sid: {"name": None, "ip": None, "token": None, "tool": None, "assigned_at": None} for sid in STUDENT_IDS}
token_index = {}  # token -> studentId
# Guards slots and token_index (see the locking rules at the top).
_state_lock = threading.Lock()


def _env_int(name, default):
    try:
        return max(1, int(os.environ.get(name) or default))
    except ValueError:
        return default


class AssignLimit:
    """How fast new slots go out (remediation T3.4, FIND-07): a token bucket,
    ASSIGN_BURST at once, then ASSIGN_PER_MINUTE. It counts only new
    assignments (a cookie-less POST /assign that would take a slot), so a
    class arriving together gets in within a minute or so while a script
    can't empty every slot in one go. The facilitator, bots, returning
    browsers and /auth-check never touch it. In memory, behind its own lock
    (requests run in parallel threads)."""

    def __init__(self, burst, per_minute, clock=time.monotonic):
        self.burst, self.rate, self.clock = float(burst), per_minute / 60.0, clock
        self.tokens, self.last = float(burst), clock()
        self.lock = threading.Lock()

    def take(self):
        """0 if a slot may go out now, else seconds until one may."""
        with self.lock:
            return self._take()

    def _take(self):
        now = self.clock()
        self.tokens = min(self.burst, self.tokens + (now - self.last) * self.rate)
        self.last = now
        if self.tokens >= 1:
            self.tokens -= 1
            return 0
        return max(1, int((1 - self.tokens) / self.rate + 0.999))


ASSIGN_LIMIT = AssignLimit(_env_int("ASSIGN_BURST", 10), _env_int("ASSIGN_PER_MINUTE", 20))
# "Release unused" frees a slot taken at least this long ago with no IDE or
# terminal running.
UNUSED_AFTER_SECONDS = 120


def release_slot(sid, result="released", token=None):
    """Stop a student's workspace and free their slot. Returns the name that
    held it, or None if the slot was already free or has changed hands.
    `token` is the holder the caller decided to release (default: whoever
    holds it now); the stop runs without the lock, and the slot is cleared
    only if that same holder still has it."""
    with _state_lock:
        if token is None:
            token = slots[sid]["token"]
        if token is None or slots[sid]["token"] != token:
            return None
    control_request("POST", f"/stop/{sid}")
    with _state_lock:
        if slots[sid]["token"] != token:
            return None  # someone else released it while we were stopping
        token_index.pop(token, None)
        name = slots[sid]["name"]
        slots[sid].update(name=None, ip=None, token=None, tool=None, assigned_at=None)
    audit("release", target=sid, name=name, result=result)
    return name


def claim_slot(name, ip):
    """Give the first free studentNN to `name`: (sid, token), or (None, None)
    when the lab is full. One critical section, so no two callers can get
    the same slot."""
    token = secrets.token_urlsafe(32)
    with _state_lock:
        sid = find_free_slot()
        if sid is None:
            return None, None
        slots[sid].update(name=name, ip=ip, token=token, assigned_at=time.time())
        token_index[token] = sid
    return sid, token


def slot_snapshot(sid):
    """A copy of one slot, taken under the lock."""
    with _state_lock:
        return dict(slots[sid])


def held_slots():
    """{sid: copy of slot} for every held student slot, in roster order."""
    with _state_lock:
        return {sid: dict(slots[sid]) for sid in STUDENT_IDS if slots[sid]["name"] is not None}


def student_number(student_id):
    return int(student_id[len(STUDENT_PREFIX):])


def bot_number(bot_id):
    return int(bot_id[len(BOT_PREFIX):])


def ide_port(username):
    if username == FACILITATOR_USERNAME:
        return FACILITATOR_IDE_PORT
    if username in BOT_IDS:
        return BOT_IDE_PORT_BASE + bot_number(username)
    return IDE_PORT_BASE + student_number(username)


def term_port(username):
    if username == FACILITATOR_USERNAME:
        return FACILITATOR_TERM_PORT
    if username in BOT_IDS:
        return BOT_TERM_PORT_BASE + bot_number(username)
    return TERM_PORT_BASE + student_number(username)


def watch_port(sid):
    if sid in BOT_IDS:
        return BOT_WATCH_PORT_BASE + bot_number(sid)
    return WATCH_PORT_BASE + student_number(sid)


def find_free_slot():
    """Caller holds _state_lock (claim_slot)."""
    for sid in STUDENT_IDS:
        if slots[sid]["name"] is None:
            return sid
    return None


def control_request(method, path):
    """Best-effort call to workspace-control.py inside web-terminal. Never
    raises -- returns None on any failure so a flaky internal call degrades
    gracefully instead of blocking the single-threaded allocator."""
    try:
        conn = http.client.HTTPConnection(WEB_TERMINAL_HOST, CONTROL_PORT, timeout=CONTROL_TIMEOUT)
        conn.request(method, path, headers={"X-Control-Token": CONTROL_TOKEN})
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        if resp.status != 200:
            return None
        return body
    except (OSError, socket.timeout, http.client.HTTPException):
        return None


def local_path(value):
    """`value` if it is a path on this site (for /forgejo-login?next=), else
    None: one leading '/', no backslash (browsers read "/\\host" as
    "//host"), printable ASCII only."""
    if (value.startswith("/") and not value.startswith("//") and "\\" not in value
            and all("!" <= c <= "~" for c in value)):
        return value
    return None


def forgejo_login_request(username, password):
    """POST straight to Forgejo's own login form over the internal network
    and return the raw Set-Cookie header values from its response, in
    order, for /forgejo-login to relay verbatim onto the browser's
    response. Relaying them in the same order Forgejo sent them reproduces
    the exact session a real browser login would end up with (Forgejo's
    login POST needs no CSRF token -- verified against the running
    instance), without this process ever needing to hold a live session of
    its own. Best-effort: an empty list just means no cookies get set, so
    the browser lands on Forgejo's normal login page instead of an error."""
    try:
        conn = http.client.HTTPConnection(GIT_SERVER_HOST, GIT_SERVER_PORT, timeout=CONTROL_TIMEOUT)
        body = urllib.parse.urlencode({"user_name": username, "password": password, "remember": ""})
        conn.request("POST", "/user/login", body=body, headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Content-Length": str(len(body)),
        })
        resp = conn.getresponse()
        cookies = resp.msg.get_all("Set-Cookie") or []
        resp.read()
        conn.close()
        return cookies
    except (OSError, socket.timeout, http.client.HTTPException):
        return []


# -- Facilitator service status (see the module docstring) -----------------
# One daemon thread (status_probe_loop, started by main()) probes each
# service in turn and republishes _status_snapshot; request handlers only
# read it. Nothing below is called from a request handler except
# handle_status_api, which does a plain read.
GATEWAY_HOST = "gateway"
STATUS_PROBE_TIMEOUT = 2.0
STATUS_DETAIL_MAX = 200


def _env_seconds(name, default, minimum):
    try:
        return max(minimum, float(os.environ.get(name, default)))
    except ValueError:
        return float(default)


# The three timings can be shortened for a test; the defaults suit a real class.
STATUS_INTERVAL = _env_seconds("STATUS_INTERVAL_SECONDS", 5, 0.2)
STATUS_STARTUP_GRACE = _env_seconds("STATUS_STARTUP_GRACE_SECONDS", 300, 0)
STATUS_LOSS_GRACE = _env_seconds("STATUS_LOSS_GRACE_SECONDS", 30, 0)
# Workshop-specific extras, "Label=URL" items separated by ";" (a workshop's
# compose overlay sets it, e.g. tofu-basics' Dojo Cloud). OK means HTTP 200.
STATUS_CHECKS = os.environ.get("STATUS_CHECKS", "")


class _SniHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS to one address while asking for another name (SNI), and without
    verifying the certificate. Only used by status probes, which send no
    credential and only look at the status code."""

    def __init__(self, host, port, sni=None, **kw):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        super().__init__(host, port, context=ctx, **kw)
        self._probe_ctx = ctx
        self._probe_sni = sni

    def connect(self):
        http.client.HTTPConnection.connect(self)
        self.sock = self._probe_ctx.wrap_socket(self.sock, server_hostname=self._probe_sni or self.host)


def _short(text):
    text = " ".join(str(text).split())
    return text[:STATUS_DETAIL_MAX] or "check failed"


def _describe_error(exc):
    if isinstance(exc, socket.timeout):
        return f"no answer within {STATUS_PROBE_TIMEOUT:g} s"
    if isinstance(exc, ConnectionRefusedError):
        return "connection refused"
    if isinstance(exc, socket.gaierror):
        return "name not found"
    if isinstance(exc, ssl.SSLError):
        return "TLS error: " + str(exc)
    return f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__


def probe_http(host, port, path, tls=False, sni=None, host_header=None, headers=None, require_body=False):
    """One GET with a short timeout. Returns (ok, detail); never raises.
    ok is True only for HTTP 200 (a redirect is NOT ok: it means we asked the
    wrong address). On a non-200, detail is a JSON body's "detail" when
    there is one (cloud-api's /readyz sends that), else "HTTP <status>".
    require_body also demands a non-empty 200 body: Caddy answers an empty
    200 for a Host it has no site for, which would look healthy."""
    conn = None
    try:
        if tls:
            conn = _SniHTTPSConnection(host, port, sni=sni, timeout=STATUS_PROBE_TIMEOUT)
        else:
            conn = http.client.HTTPConnection(host, port, timeout=STATUS_PROBE_TIMEOUT)
        hdrs = dict(headers or {})
        if host_header:
            hdrs["Host"] = host_header
        conn.request("GET", path, headers=hdrs)
        resp = conn.getresponse()
        if resp.status == 200:
            # Read the whole body (capped): closing with unread data makes the kernel reset the
            # connection, and the server then logs a ConnectionResetError traceback on every probe.
            body = resp.read(1 << 20)
            if require_body and not body:
                return False, "empty response (gateway has no site for this Host?)"
            return True, None
        detail = f"HTTP {resp.status}"
        try:
            parsed = json.loads(resp.read(4096))
            if isinstance(parsed, dict) and isinstance(parsed.get("detail"), str) and parsed["detail"].strip():
                detail = parsed["detail"]
        except ValueError:
            pass
        return False, _short(detail)
    except (OSError, http.client.HTTPException) as exc:  # socket.timeout and ssl errors are OSErrors
        return False, _short(_describe_error(exc))
    finally:
        if conn is not None:
            conn.close()


def probe_forgejo():
    return probe_http(GIT_SERVER_HOST, GIT_SERVER_PORT, "/api/healthz")


def probe_terminals():
    # Same call control_request("GET", "/status") makes, but through
    # probe_http so a failure has a reason and a 2 s timeout.
    return probe_http(WEB_TERMINAL_HOST, CONTROL_PORT, "/status", headers={"X-Control-Token": CONTROL_TOKEN})


def probe_slides():
    """The presentation container is on web_lab, which the allocator is not
    on, so go through the gateway (on both networks) exactly as a browser
    would: same scheme, port and Host as PUBLIC_BASE_URL. Not http://gateway:80:
    Caddy answers an empty 200 for Host "gateway" when the site is
    http://localhost, and a 308 redirect (or a TLS failure on 443) when the
    site is an https hostname, so neither would say anything about slides.
    Behind another proxy, GATEWAY_LISTEN is the address to call; with no
    host in it (http://:8080) Caddy takes any Host, so send the public one.
    /slides is behind the class login, so send a session for it: without one
    the probe would only see the login redirect."""
    public = urllib.parse.urlsplit(PUBLIC_BASE_URL)
    base = urllib.parse.urlsplit(GATEWAY_LISTEN) if GATEWAY_LISTEN else public
    tls = base.scheme == "https"
    host = base.hostname or public.hostname
    return probe_http(GATEWAY_HOST, base.port or (443 if tls else 80), "/slides/",
                      tls=tls, sni=host, host_header=base.netloc if base.hostname else public.netloc,
                      headers={"Cookie": f"{SESSION_COOKIE}={make_session(TTYD_USERNAME)}"}, require_body=True)


def _extra_probe(url):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return lambda: (False, "STATUS_CHECKS: not an http(s) URL")
    tls = parts.scheme == "https"
    target = (parts.path or "/") + (("?" + parts.query) if parts.query else "")
    return lambda: probe_http(parts.hostname, parts.port or (443 if tls else 80), target, tls=tls)


def build_status_services():
    """[{name, probe, ok, last_ok, detail}] in display order. Only the probe
    thread writes ok/last_ok/detail after this."""
    probes = [("Forgejo", probe_forgejo), ("Terminals", probe_terminals), ("Slides", probe_slides)]
    for item in STATUS_CHECKS.split(";"):
        label, sep, url = item.partition("=")
        label, url = label.strip()[:40], url.strip()
        if sep and label and url:
            probes.append((label, _extra_probe(url)))
    for check in EXTENSIONS["status_checks"]:
        probes.append((check["label"], _extra_probe(check["url"])))
    return [{"name": n, "probe": p, "ok": None, "last_ok": None, "detail": None} for n, p in probes]


_status_started = time.monotonic()
_status_services = build_status_services()


def classify_status(ok, last_ok, now, started=None):
    """green / yellow / red for one service; the allocator decides, not the
    service. Yellow = not OK but either never OK yet and still inside the
    startup grace, or OK within the loss grace (a blip or a restart)."""
    if ok:
        return "green"
    if last_ok is None:
        return "yellow" if now - (_status_started if started is None else started) < STATUS_STARTUP_GRACE else "red"
    return "yellow" if now - last_ok < STATUS_LOSS_GRACE else "red"


def _build_snapshot(now):
    services = []
    for svc in _status_services:
        if svc["ok"] is None:
            services.append({"name": svc["name"], "state": "yellow", "detail": "waiting for first check"})
            continue
        state = classify_status(svc["ok"], svc["last_ok"], now)
        services.append({"name": svc["name"], "state": state,
                         "detail": None if state == "green" else (svc["detail"] or "check failed")})
    return {"generatedAt": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "services": services}


# Replaced wholesale by the probe thread, read by handle_status_api.
_status_snapshot = _build_snapshot(time.monotonic())


def status_probe_loop():
    global _status_snapshot
    while True:
        for svc in _status_services:
            try:
                ok, detail = svc["probe"]()
            except Exception as exc:  # a bad probe must not kill the thread
                ok, detail = False, _short(f"probe error: {type(exc).__name__}")
            now = time.monotonic()
            svc["ok"], svc["detail"] = ok, detail
            if ok:
                svc["last_ok"] = now
            _status_snapshot = _build_snapshot(now)
        time.sleep(STATUS_INTERVAL)


# Inline, self-contained SVGs for the confirmation page's tool cards (see
# render_confirmation) -- feather-style, 24x24, stroke=currentColor so each
# one automatically picks up its card's icon color (including the primary
# card's white-on-blue) with no extra markup or external icon font/CDN
# request. This runs entirely inside a student's own browser, which this
# project makes no assumption has internet access beyond the workshop
# origin itself (see engine/README.md's Troubleshooting section on the
# terminal container's own lack of one) -- so nothing on this page ever
# depends on a third-party asset loading.
_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{}</svg>'
ICON_CODE = _SVG.format('<polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline>')
ICON_TERMINAL = _SVG.format('<polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line>')
ICON_GIT = _SVG.format('<line x1="6" y1="3" x2="6" y2="15"></line><circle cx="18" cy="6" r="3"></circle>'
                        '<circle cx="6" cy="18" r="3"></circle><path d="M18 9a9 9 0 0 1-9 9"></path>')
ICON_SLIDES = _SVG.format('<rect x="2" y="4" width="20" height="14" rx="2"></rect>'
                           '<line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="18" x2="12" y2="21"></line>')
ICON_ROCKET = _SVG.format('<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"></path>'
                           '<path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"></path>'
                           '<path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"></path>'
                           '<path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"></path>')
ICON_CLOUD = _SVG.format('<path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"></path>')
ICON_KEY = _SVG.format('<circle cx="7.5" cy="15.5" r="5.5"></circle><path d="M21 2l-9.6 9.6"></path>'
                        '<path d="M15.5 7.5l3 3L22 7l-3-3"></path>')
ICON_DNS = _SVG.format('<circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line>'
                        '<path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>')
# Names an extensions.json card may use (render_extensions.py ICONS).
ICONS_BY_NAME = {"code": ICON_CODE, "terminal": ICON_TERMINAL, "git": ICON_GIT, "slides": ICON_SLIDES,
                 "rocket": ICON_ROCKET, "cloud": ICON_CLOUD, "key": ICON_KEY, "dns": ICON_DNS}
ICON_ARROW ='<svg class="card-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' \
             'stroke-linecap="round" stroke-linejoin="round"><line x1="7" y1="17" x2="17" y2="7"></line>' \
             '<polyline points="7 7 17 7 17 17"></polyline></svg>'


# -- page assets (remediation T4.2, FIND-14) ------------------------------
# Every allocator page is served under a strict Content-Security-Policy (see
# CSP below): no inline script, no style attributes. The facilitator page's
# script and stylesheet are served from memory at /admin/admin.js and
# /admin/admin.css (behind the same facilitator gate as /admin). The student
# pages keep one inline <style> each, allowed by its sha256 hash, computed
# here from the exact text so the header can't drift from the page.
LANDING_CSS = """
  :root { color-scheme: light dark; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          max-width: 30rem; margin: 8vh auto; padding: 0 1.25rem; color: #1a1a1a; background: #fafafa; }
  @media (prefers-color-scheme: dark) { body { color: #eee; background: #171717; } }
  h1 { font-size: 1.4rem; margin-bottom: 0.25rem; }
  .sub { opacity: 0.7; margin-bottom: 2rem; }
  input[type=text] { width: 100%; padding: 0.6rem 0.8rem; font-size: 1rem; border-radius: 0.5rem;
          border: 1px solid #ccc; box-sizing: border-box; margin-bottom: 1rem; }
  button, .btn { display: inline-block; padding: 0.6rem 1.2rem; font-size: 1rem; border-radius: 0.5rem;
          border: none; background: #2563eb; color: white; cursor: pointer; text-decoration: none;
          margin-right: 0.5rem; margin-bottom: 0.5rem; }
  button:disabled { opacity: 0.6; cursor: default; }
  .btn.secondary { background: #6b7280; }
  .badge { display: inline-block; background: #eef2ff; color: #3730a3; border-radius: 999px;
          padding: 0.15rem 0.7rem; font-weight: 600; font-size: 0.9rem; }
  @media (prefers-color-scheme: dark) { .badge { background: #1e2352; color: #c7d2fe; } }
"""

CONFIRM_CSS = """
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          max-width: 40rem; margin: 6vh auto; padding: 0 1.25rem 3rem; color: #1a1a1a; background: #fafafa; }
  @media (prefers-color-scheme: dark) { body { color: #eee; background: #171717; } }
  .hero { text-align: center; margin-bottom: 2rem; }
  .hero-badge { display: inline-block; background: #eef2ff; color: #3730a3; border-radius: 999px;
          padding: 0.2rem 0.85rem; font-weight: 600; font-size: 0.85rem; letter-spacing: 0.02em;
          margin-bottom: 0.9rem; }
  @media (prefers-color-scheme: dark) { .hero-badge { background: #1e2352; color: #c7d2fe; } }
  .hero h1 { font-size: 1.6rem; margin: 0 0 0.4rem; }
  .hero .sub { opacity: 0.7; margin: 0; }
  .cards { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
  @media (max-width: 30rem) { .cards { grid-template-columns: 1fr; } }
  .card { display: flex; align-items: center; gap: 0.85rem; padding: 0.9rem 1rem; border-radius: 0.75rem;
          border: 1px solid #e2e2e2; background: #fff; text-decoration: none; color: inherit;
          transition: border-color 0.15s, transform 0.15s, box-shadow 0.15s; }
  @media (prefers-color-scheme: dark) { .card { border-color: #333; background: #1f1f1f; } }
  .card:hover, .card:focus-visible { border-color: #2563eb; transform: translateY(-1px);
          box-shadow: 0 4px 14px rgba(37, 99, 235, 0.15); }
  .card.primary { grid-column: 1 / -1; border-color: #2563eb; background: #eff6ff; }
  @media (prefers-color-scheme: dark) { .card.primary { background: #172554; } }
  .card-icon { flex-shrink: 0; width: 2.25rem; height: 2.25rem; border-radius: 0.6rem; background: #eef2ff;
          color: #2563eb; display: flex; align-items: center; justify-content: center; }
  @media (prefers-color-scheme: dark) { .card-icon { background: #1e2352; } }
  .card.primary .card-icon { background: #2563eb; color: #fff; }
  .card-icon svg { width: 1.25rem; height: 1.25rem; }
  .card-text { display: flex; flex-direction: column; gap: 0.1rem; min-width: 0; flex: 1; }
  .card-title { font-weight: 600; font-size: 0.98rem; }
  .card-desc { font-size: 0.82rem; opacity: 0.65; line-height: 1.3; }
  .card-arrow { flex-shrink: 0; opacity: 0.35; width: 1rem; height: 1rem; }
  .card:hover .card-arrow, .card:focus-visible .card-arrow { opacity: 0.7; }
  .secret { margin-top: 1.25rem; padding: 0.85rem 1rem; border-radius: 0.75rem; border: 1px solid #e2e2e2;
          background: #fff; text-align: center; display: flex; flex-direction: column; align-items: center; gap: 0.4rem; }
  @media (prefers-color-scheme: dark) { .secret { border-color: #333; background: #1f1f1f; } }
  .secret-label { font-weight: 600; font-size: 0.85rem; letter-spacing: 0.02em; }
  .secret code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; background: #eef2ff;
          color: #3730a3; border-radius: 0.4rem; padding: 0.1rem 0.5rem; }
  @media (prefers-color-scheme: dark) { .secret code { background: #1e2352; color: #c7d2fe; } }
  .secret-hint code { font-size: 0.75rem; padding: 0.05rem 0.3rem; }
  .secret-table { border-collapse: collapse; margin: 0.15rem 0; }
  .secret-table th, .secret-table td { padding: 0.35rem 0.75rem; border-bottom: 1px solid #e2e2e2; }
  @media (prefers-color-scheme: dark) { .secret-table th, .secret-table td { border-color: #333; } }
  .secret-table tr:last-child th, .secret-table tr:last-child td { border-bottom: none; }
  .secret-table th { text-align: right; font-weight: 500; font-size: 0.85rem; opacity: 0.7; }
  .secret-table td { text-align: left; }
  .secret-value { font-size: 1.05rem; font-weight: 600; user-select: all; overflow-wrap: anywhere; }
  .secret-hint { font-size: 0.8rem; opacity: 0.65; line-height: 1.35; }
  .footnote { margin-top: 1.75rem; text-align: center; font-size: 0.8rem; opacity: 0.55; }
"""

ADMIN_CSS = """
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          margin: 0; height: 100vh; display: flex; overflow: hidden;
          color: #1a1a1a; background: #fafafa; }
  @media (prefers-color-scheme: dark) { body { color: #eee; background: #171717; } }
  #side { flex: none; width: 13.5rem; display: flex; flex-direction: column; gap: 1.1rem;
           padding: 1.1rem 0.75rem; overflow-y: auto; border-right: 1px solid #ddd; background: #f3f3f3; }
  @media (prefers-color-scheme: dark) { #side { border-right-color: #333; background: #121212; } }
  #main { flex: 1; min-width: 0; overflow: auto; padding: 0.75rem; }
  h1 { font-size: 1.3rem; margin: 0 0 0.15rem; }
  .sub { opacity: 0.7; }
  #bar .sub { margin: 0.25rem 0 0; font-size: 0.9rem; }
  #status { display: flex; flex-direction: column; align-items: flex-start; gap: 0.35rem; margin-top: auto; }
  #status.stale { opacity: 0.45; }
  .svc { display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.2rem 0.65rem; border-radius: 999px;
          border: 1px solid #ddd; background: #fff; font-size: 0.8rem; max-width: 100%; cursor: default; }
  @media (prefers-color-scheme: dark) { .svc { border-color: #333; background: #1f1f1f; } }
  .svc-dot { width: 0.65rem; height: 0.65rem; border-radius: 50%; flex: none; background: #6b7280; }
  .svc.green .svc-dot { background: #16a34a; }
  .svc.yellow .svc-dot { background: #d97706; }
  .svc.red .svc-dot { background: #dc2626; }
  @media (prefers-color-scheme: dark) {
    .svc.green .svc-dot { background: #22c55e; }
    .svc.yellow .svc-dot { background: #f59e0b; }
    .svc.red .svc-dot { background: #f87171; }
  }
  .svc-name { font-weight: 600; }
  .svc-word { opacity: 0.75; }
  .svc.yellow .svc-word, .svc.red .svc-word { opacity: 1; font-weight: 600; }
  .badge { display: inline-block; background: #eef2ff; color: #3730a3; border-radius: 999px;
          padding: 0.15rem 0.7rem; font-weight: 600; font-size: 0.9rem; }
  @media (prefers-color-scheme: dark) { .badge { background: #1e2352; color: #c7d2fe; } }
  button { font: inherit; }
  .tabs { display: flex; flex-direction: column; gap: 0.15rem; }
  .tab { padding: 0.55rem 0.8rem; font-size: 0.95rem; border: none; background: none; cursor: pointer; text-align: left;
          color: inherit; opacity: 0.65; border-left: 3px solid transparent; border-radius: 0 0.35rem 0.35rem 0; }
  .tab:hover { opacity: 0.9; background: rgba(127, 127, 127, 0.12); }
  .tab.active { opacity: 1; border-left-color: #2563eb; background: rgba(37, 99, 235, 0.1); font-weight: 600; }
  .panel { display: none; }
  .panel.active { display: block; }
  .panel iframe { display: block; width: 100%; height: calc(100vh - 1.5rem); min-height: 400px; border: 0; border-radius: 0.5rem; }
  @media (max-width: 700px) {
    body { flex-direction: column; height: auto; overflow: visible; }
    #side { width: auto; border-right: none; border-bottom: 1px solid #ddd; }
    .tabs { flex-direction: row; flex-wrap: wrap; }
    #status { flex-direction: row; flex-wrap: wrap; margin-top: 0; }
    #main { overflow: visible; }
  }
  #grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 0.75rem; }
  .tile { border: 1px solid #333; border-radius: 0.5rem; overflow: hidden; background: #000;
           display: flex; flex-direction: column; height: 280px; }
  .tile-head { display: flex; flex-direction: column; gap: 0.2rem; padding: 0.3rem 0.6rem 0.4rem;
                font-size: 0.8rem; background: #111; color: #ccc; flex-shrink: 0; }
  .tile-title { display: flex; align-items: center; justify-content: space-between; }
  .tile-label { cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 600; }
  .tile-reload { background: none; border: none; color: #ccc; cursor: pointer; font-size: 0.95rem; padding: 0 0.2rem; flex-shrink: 0; }
  .tile-reload:hover { color: #fff; }
  .tile-meta { display: flex; align-items: center; gap: 0.6rem; font-size: 0.72rem; opacity: 0.85; }
  .tile-ip { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .tile-status { white-space: nowrap; }
  .tile-status.st-on { color: #16a34a; }
  .tile-status.st-off { color: #dc2626; }
  .tile-release, .tile-pw-btn { padding: 0.15rem 0.55rem; font-size: 0.72rem; border-radius: 0.35rem;
          border: none; background: #6b7280; color: white; cursor: pointer; flex-shrink: 0; }
  .tile-pw { margin-left: auto; font-size: 0.72rem; user-select: all; }
  .tile-pw:empty { display: none; }
  .tile-pw:empty + .tile-pw-btn, .tile-pw:empty + .tile-release { margin-left: auto; }
  .tile-release:hover, .tile-pw-btn:hover { background: #7c8494; }
  .tile-release:disabled { opacity: 0.6; cursor: default; }
  #roster-bar { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem; }
  #release-unused { padding: 0.3rem 0.8rem; font-size: 0.8rem; border-radius: 0.35rem; border: 0;
    background: #64748b; color: #fff; cursor: pointer; }
  #release-unused:hover { background: #7c8494; }
  #release-unused:disabled { opacity: 0.6; cursor: default; }
  /* The iframe is laid out at a fixed, generous pixel size (see
     FRAME_W/H below), then CSS-transformed to fill whatever size the
     tile wrapper actually is, enlarged or not -- see that comment and
     updateScale's for why. */
  .tile-frame-wrap { position: relative; flex: 1; overflow: hidden; background: #000; }
  .tile-waiting { position: absolute; inset: 0; display: flex; align-items: center;
          justify-content: center; text-align: center; padding: 1rem;
          font-size: 0.78rem; color: #888; }
  .tile.watching .tile-waiting { display: none; }
  .tile iframe { position: absolute; top: 0; left: 0; border: 0; border-radius: 0;
          background: #000; transform-origin: top left; }
  #grid.has-enlarged .tile { display: none; }
  #grid.has-enlarged .tile.enlarged { display: flex; grid-column: 1 / -1; height: calc(100vh - 1.5rem); }
"""

ADMIN_JS = """
// -- tabs ---------------------------------------------------------------
const tabs = Array.from(document.querySelectorAll('.tab'));
const panels = {};
document.querySelectorAll('.panel').forEach(p => { panels[p.id.slice('panel-'.length)] = p; });

function activateTab(name) {
  tabs.forEach(t => t.classList.toggle('active', t.dataset.tab === name));
  Object.entries(panels).forEach(([key, el]) => el.classList.toggle('active', key === name));
  const frame = panels[name] && panels[name].querySelector('iframe[data-src]');
  if (frame) { frame.src = frame.dataset.src; frame.removeAttribute('data-src'); }
}
tabs.forEach(t => t.onclick = () => activateTab(t.dataset.tab));

// -- roster grid ------------------------------------------------------
const grid = document.getElementById('grid');
const tiles = {};
let enlarged = null;

// The watch iframe is laid out at one fixed, generous pixel size -- not
// the tile's actual (usually much smaller) visible size -- then shrunk
// (or, enlarged, grown) to fit with a CSS transform (see updateScale).
// xterm.js inside sizes its terminal from that *unscaled* layout box, so
// tmux always sees a client at least as big as most real single-terminal
// panes; a client smaller than the real pane is what makes tmux clip to
// that corner instead of reflowing (see tmux.conf's window-size comment).
//
// This view is read-only and just for a facilitator's at-a-glance check,
// not a pixel-perfect mirror, so it deliberately does NOT track each
// student's actual pane size to match it exactly -- an earlier version
// did, but a session nobody else ever attaches to (every demo bot, always
// -- see tmux.conf) has nothing real to anchor that size against, so this
// page's own size guess fed back into itself every 5s poll and grew
// without bound. One fixed reference size, comfortably bigger than almost
// any single terminal pane, sidesteps that whole problem.
//
// A smaller per-tile-only reference (more legible text, less content
// visible) was tried and reverted -- shrinking a small tile's *content*,
// not just its text, isn't the tradeoff wanted here; a small tile should
// show as much of the real pane as an enlarged one does, just smaller.
const FRAME_W = 1120;
const FRAME_H = 800;

function initFrameSize(frame) {
  frame.dataset.w = FRAME_W;
  frame.dataset.h = FRAME_H;
  frame.style.width = FRAME_W + 'px';
  frame.style.height = FRAME_H + 'px';
}

// A floor on how far a tile will shrink the frame to fit -- without one,
// a tile still mid-layout (0 width/height for a tick after being added)
// or an unusually large real pane would render text at an illegibly tiny
// scale. Below this floor .tile-frame-wrap's overflow: hidden just crops
// to whatever corner fits, same as tmux would show a too-small client
// anyway (see above) -- a legible fraction beats all of it unreadable.
const MIN_SCALE = 0.3;

function updateScale(wrap) {
  const frame = wrap.querySelector('iframe');
  if (!frame || !frame.dataset.w) return;
  const rect = wrap.getBoundingClientRect();
  const scale = Math.min(rect.width / frame.dataset.w, rect.height / frame.dataset.h);
  frame.style.transform = `scale(${Math.max(scale, MIN_SCALE)})`;
}

const frameObserver = new ResizeObserver(entries => {
  for (const entry of entries) updateScale(entry.target);
});

// Builds one element; any text goes in via textContent (student names and
// the like are data, never markup).
function make(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function setStatus(el, active) {
  el.textContent = active ? '\\u25CF active' : '\\u25CF inactive';
  el.classList.toggle('st-on', !!active);
  el.classList.toggle('st-off', !active);
}

// Connects a tile's iframe to its watch endpoint the first time the
// student becomes watchable (see updateRoster) -- a no-op if already
// connected, so it's safe to call on every poll.
function activateWatch(tile, sid) {
  const frame = tile.querySelector('iframe');
  if (frame.src) return;
  frame.src = '/admin/watch/' + encodeURIComponent(sid) + '/';
  tile.classList.add('watching');
}

function reloadTile(sid) {
  const frame = tiles[sid].querySelector('iframe');
  if (!frame.src) return;  // not watchable yet -- nothing to reload
  const src = frame.src;
  frame.src = 'about:blank';
  frame.src = src;
}

function releaseTile(sid, btn) {
  btn.disabled = true;
  fetch('/admin/release/' + encodeURIComponent(sid), {
    method: 'POST',
    headers: { 'X-Requested-With': 'dojo-admin' },
  }).then(refresh);
}

// Roster "Release unused": free every slot taken a while ago whose student
// never started VS Code or a terminal (e.g. slots a script grabbed).
function releaseUnused(btn, out) {
  if (!confirm('Release every slot taken over 2 minutes ago with no VS Code or terminal running?')) return;
  btn.disabled = true;
  fetch('/admin/release-unused', {
    method: 'POST',
    headers: { 'X-Requested-With': 'dojo-admin' },
  }).then(r => r.ok ? r.json() : Promise.reject(r.status))
    .then(d => { out.textContent = d.released.length ? 'Released: ' + d.released.join(', ') : 'Nothing to release'; })
    .catch(() => { out.textContent = 'Release failed'; })
    .finally(() => { btn.disabled = false; refresh(); });
}
document.getElementById('release-unused').onclick = (e) =>
  releaseUnused(e.currentTarget, document.getElementById('release-unused-out'));

// Roster "Password": fetch one student's Forgejo password on demand and show
// it in the tile (textContent only); a second click hides it again.
function togglePassword(sid, btn, out) {
  if (out.textContent) { out.textContent = ''; btn.textContent = 'Password'; return; }
  fetch('/admin/api/forgejo-password/' + encodeURIComponent(sid), {
    headers: { 'X-Requested-With': 'dojo-admin' },
  }).then(r => r.ok ? r.json() : Promise.reject(r.status))
    .then(d => { out.textContent = d.password; btn.textContent = 'Hide'; })
    .catch(() => { out.textContent = 'unavailable'; });
}

function toggleEnlarge(sid) {
  if (enlarged === sid) { closeEnlarge(); return; }
  if (enlarged && tiles[enlarged]) tiles[enlarged].classList.remove('enlarged');
  tiles[sid].classList.add('enlarged');
  grid.classList.add('has-enlarged');
  enlarged = sid;
}

function closeEnlarge() {
  if (enlarged && tiles[enlarged]) tiles[enlarged].classList.remove('enlarged');
  grid.classList.remove('has-enlarged');
  enlarged = null;
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeEnlarge(); });

function buildTile(r) {
  const tile = document.createElement('div');
  tile.className = 'tile';
  const head = document.createElement('div');
  head.className = 'tile-head';
  const title = make('div', 'tile-title');
  const label = make('span', 'tile-label', String(r.studentId) + ' \\u2014 ' + String(r.name));
  const reload = make('button', 'tile-reload', '\\u21BB');
  reload.title = 'Reload (follow current terminal)';
  title.append(label, reload);
  const meta = make('div', 'tile-meta');
  const status = make('span', 'tile-status');
  setStatus(status, r.active);
  const pw = make('code', 'tile-pw');
  const pwBtn = make('button', 'tile-pw-btn', 'Password');
  const release = make('button', 'tile-release', 'Release');
  meta.append(make('span', 'tile-ip', String(r.ip)), status, pw, pwBtn, release);
  head.append(title, meta);
  label.onclick = () => toggleEnlarge(r.studentId);
  reload.onclick = (e) => { e.stopPropagation(); reloadTile(r.studentId); };
  release.onclick = (e) => { e.stopPropagation(); releaseTile(r.studentId, e.currentTarget); };
  // Bots sign in with BOT_PASSWORD, not a derived one: no button.
  if (r.ip === 'bot') pwBtn.remove();
  else pwBtn.onclick = (e) => { e.stopPropagation(); togglePassword(r.studentId, e.currentTarget, pw); };
  const wrap = document.createElement('div');
  wrap.className = 'tile-frame-wrap';
  const waiting = document.createElement('div');
  waiting.className = 'tile-waiting';
  waiting.textContent = 'Waiting for a terminal session to watch…';
  const frame = document.createElement('iframe');
  frame.loading = 'lazy';
  wrap.appendChild(waiting);
  wrap.appendChild(frame);
  initFrameSize(frame);
  tile.appendChild(head);
  tile.appendChild(wrap);
  frameObserver.observe(wrap);
  if (r.watchable) activateWatch(tile, r.studentId);
  return tile;
}

function updateRoster(rows) {
  const seen = new Set();
  for (const r of rows) {
    seen.add(r.studentId);
    if (tiles[r.studentId]) {
      setStatus(tiles[r.studentId].querySelector('.tile-status'), r.active);
      if (r.watchable) activateWatch(tiles[r.studentId], r.studentId);
      continue;
    }
    const tile = buildTile(r);
    grid.appendChild(tile);
    tiles[r.studentId] = tile;
  }
  for (const sid of Object.keys(tiles)) {
    if (seen.has(sid)) continue;
    frameObserver.unobserve(tiles[sid].querySelector('.tile-frame-wrap'));
    tiles[sid].remove();
    delete tiles[sid];
    if (enlarged === sid) enlarged = null;
  }
  document.getElementById('empty').style.display = rows.length ? 'none' : 'block';
}

// -- service status strip ---------------------------------------------
// One chip per service: coloured dot + name + a word, so colour is never
// the only signal. Chips are updated in place (never rebuilt) and all text
// goes in via textContent/title -- names and details are data.
const statusEl = document.getElementById('status');
const svcChips = [];
const STATE_WORD = { green: 'Ready', yellow: 'Starting', red: 'Down' };

function buildChip() {
  const el = document.createElement('span');
  const dot = document.createElement('span');
  dot.className = 'svc-dot';
  dot.setAttribute('aria-hidden', 'true');
  const name = document.createElement('span');
  name.className = 'svc-name';
  const word = document.createElement('span');
  word.className = 'svc-word';
  el.append(dot, name, word);
  return el;
}

function updateStatus(data) {
  const services = Array.isArray(data.services) ? data.services : [];
  services.forEach((s, i) => {
    if (!svcChips[i]) {
      svcChips[i] = buildChip();
      statusEl.appendChild(svcChips[i]);
    }
    const el = svcChips[i];
    const state = STATE_WORD[s.state] ? s.state : 'red';
    el.className = 'svc ' + state;
    el.querySelector('.svc-name').textContent = String(s.name);
    el.querySelector('.svc-word').textContent = STATE_WORD[state];
    el.title = s.detail ? String(s.name) + ': ' + String(s.detail) : String(s.name) + ': ' + STATE_WORD[state];
  });
  while (svcChips.length > services.length) svcChips.pop().remove();
  statusEl.classList.remove('stale');
}

async function refreshStatus() {
  try {
    updateStatus(await (await fetch('/admin/api/status')).json());
  } catch {
    statusEl.classList.add('stale');  // keep the last known chips, greyed out
  }
}

async function refresh() {
  refreshStatus();
  let rows;
  try {
    rows = await (await fetch('/admin/api/sessions')).json();
  } catch {
    return;  // transient fetch failure -- try again next poll, don't tear down tiles
  }
  updateRoster(rows);
}
refresh();
setInterval(refresh, 5000);
"""


def _style_hash(text):
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode() + "'"


CSP = ("default-src 'self'; script-src 'self'; "
       f"style-src 'self' {_style_hash(LANDING_CSS)} {_style_hash(CONFIRM_CSS)}; "
       "img-src 'self' data:; object-src 'none'; base-uri 'none'; "
       "form-action 'self'; frame-ancestors 'self'")

ADMIN_ASSETS = {
    "/admin/admin.js": ("text/javascript; charset=utf-8", ADMIN_JS),
    "/admin/admin.css": ("text/css; charset=utf-8", ADMIN_CSS),
}


def page(title, body):
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{LANDING_CSS}</style></head>
<body>{body}</body></html>"""


# The landing page shows the student's Forgejo password, so nothing between
# here and the browser (or the browser's own back/forward cache) may keep a copy.
NO_STORE_HEADERS = [("Cache-Control", "no-store"), ("Pragma", "no-cache")]


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "AllocatorHTTP/1.0"
    # Per-connection socket timeout. Each connection has its own thread
    # (AllocatorServer), so a client that connects and then sends slowly or
    # not at all only holds its own thread, for at most this long per read,
    # and never delays anyone else. 3 s is plenty for any legitimate request
    # (all local; control_request/forgejo_login_request have their own
    # CONTROL_TIMEOUT).
    timeout = 3

    def log_message(self, fmt, *args):
        pass  # keep container logs quiet; nothing sensitive is worth logging by default

    # -- helpers ---------------------------------------------------------
    def send_html(self, body, status=200, headers=None):
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Content-Security-Policy", CSP)
        for k, v in (headers or {}):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(encoded)

    def send_asset(self, content_type, body):
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)

    def send_json(self, data, status=200, headers=None):
        encoded = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        for k, v in (headers or {}):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(encoded)

    def gateway_authorized(self):
        """True only if this request carries the shared secret Caddy alone
        knows (see GATEWAY_TOKEN above) -- mirrors workspace-control.py's
        own authorized()/CONTROL_TOKEN check byte for byte. Checked first,
        in do_GET/do_POST, before any path parsing or resolve_identity()
        call: resolve_identity() trusts X-Auth-User, and this is the only
        thing standing between that trust and any other container on the
        shared workshop_lab network forging it."""
        token = self.headers.get("X-Gateway-Token", "")
        return hmac.compare_digest(token, GATEWAY_TOKEN)

    def get_cookie(self):
        cookie_header = self.headers.get("Cookie", "")
        for part in cookie_header.split(";"):
            part = part.strip()
            if part.startswith(f"{COOKIE_NAME}="):
                return part[len(COOKIE_NAME) + 1:]
        return None

    def resolve_identity(self):
        """Return (username_for_control_plane, student_id_or_None) for the
        current request, or (None, None) if it isn't valid.

        Facilitator identity comes from X-Auth-User, set by
        gateway/Caddyfile's basic_auth + header_up on every request (this
        always overwrites any client-supplied value, so it can't be
        spoofed by a browser/curl -- only Caddy, on the internal-only
        network, can set it) to whichever account actually satisfied the
        shared or /admin basic_auth challenge. Caddy authenticates every
        request before it ever reaches this process, so this header is
        always present and correct -- typing the facilitator credential
        once, anywhere, is immediately enough; no cookie needed. A student
        identity, by contrast, only ever comes from the dojo_session
        cookie minted when they claim a slot via /assign.
        """
        if self.headers.get("X-Auth-User") == FACILITATOR_USERNAME:
            return FACILITATOR_USERNAME, None
        token = self.get_cookie()
        if token is None:
            return None, None
        with _state_lock:
            sid = token_index.get(token)
            if sid is not None and slots[sid]["token"] == token and slots[sid]["name"] is not None:
                return sid, sid
        return None, None

    def client_ip(self):
        # gateway/Caddyfile has no trusted_proxies configured, so Caddy's
        # reverse_proxy APPENDS the address it actually saw to whatever
        # X-Forwarded-For value the client already sent, rather than
        # replacing it -- the same header a curl/browser client is free to
        # set to anything. That means the FIRST entry can be attacker-
        # supplied, but the LAST entry is always the address Caddy itself
        # observed on the connection, since gateway is the sole public
        # entry point with nothing in front of it to have appended anything
        # earlier. Only that last hop is safe to trust (this is only ever
        # used for the facilitator roster display, not an auth decision).
        forwarded = self.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[-1].strip()
        return self.client_address[0]

    # Real form bodies here are tiny (a name, capped at 60 chars, is the
    # only field any form on this service ever submits) -- capping well
    # above that but far below "attacker-declared Content-Length" stops a
    # client from making this single-threaded process (see class docstring)
    # allocate or block on reading an enormous declared body.
    MAX_BODY_BYTES = 4096

    def read_form_body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            length = 0
        length = max(0, min(length, self.MAX_BODY_BYTES))
        raw = self.rfile.read(length) if length else b""
        parsed = urllib.parse.parse_qs(raw.decode("utf-8", errors="replace"))
        return {k: v[0] for k, v in parsed.items()}

    # -- pages -------------------------------------------------------------
    def render_name_form(self):
        body = f"""
<h1>{html.escape(WORKSHOP_NAME)}</h1>
<p class="sub">Enter your name to get started.</p>
<form method="post" action="/assign">
  <input type="text" name="name" placeholder="Your name" required autofocus maxlength="60">
  <button type="submit">Join workshop</button>
</form>"""
        return page(WORKSHOP_NAME, body)

    def render_full(self):
        body = f"""
<h1>{html.escape(WORKSHOP_NAME)}</h1>
<p class="sub">All workshop seats are currently taken. Please ask your facilitator for help.</p>"""
        return page(WORKSHOP_NAME, body)

    def render_busy(self, wait):
        body = f"""
<h1>{html.escape(WORKSHOP_NAME)}</h1>
<p class="sub">A lot of people are joining at once. Please try again in {int(wait)} seconds.</p>
<p><a href="/">Try again</a></p>"""
        return page(WORKSHOP_NAME, body)

    def render_confirmation(self, sid):
        """The landing page a student sees on every visit after /assign has
        claimed them a slot (including refresh/back-button -- see
        handle_assign). Deliberately its own full HTML document, like
        render_facilitator_workspace, rather than page() -- page()'s
        narrow single-column layout is tuned for the two short forms
        (name entry, "lab full"), not a set of tool choices that benefits
        from room to show what each one actually does."""
        slot = slot_snapshot(sid)
        tools = [
            {
                "href": "/ide/", "label": "VS Code", "icon": ICON_CODE, "primary": True,
                "desc": "Your editor, already open in your lab folder.",
            },
            {
                "href": "/term/", "label": "Terminal", "icon": ICON_TERMINAL,
                "desc": "A plain shell, same account, if you'd rather type.",
            },
            {
                "href": "/forgejo-login", "label": "Forgejo", "icon": ICON_GIT,
                "desc": "Your repo -- branches, commits, pull requests.",
            },
            {
                "href": "/slides/", "label": "Slides", "icon": ICON_SLIDES,
                "desc": "Today's material, for reference as you go.",
            },
        ]
        for card in EXTENSIONS["cards"]:
            tools.append({
                "href": card["href"], "label": card["label"], "desc": card["desc"],
                "icon": ICONS_BY_NAME.get(card["icon"], ICON_ARROW),
            })

        cards = "\n".join(
            f"""<a class="card{' primary' if t.get('primary') else ''}" href="{t['href']}" target="_blank" rel="noopener">
  <span class="card-icon">{t['icon']}</span>
  <span class="card-text">
    <span class="card-title">{html.escape(t['label'])}</span>
    <span class="card-desc">{html.escape(t['desc'])}</span>
  </span>
  {ICON_ARROW}
</a>"""
            for t in tools
        )

        body = f"""
<div class="hero">
  <span class="hero-badge">{html.escape(sid)}</span>
  <h1>You're in, {html.escape(slot['name'])}</h1>
  <p class="sub">Pick a tool to get started -- each one opens in a new tab.</p>
</div>
<div class="cards">
{cards}
</div>
<div class="secret">
  <span class="secret-label">Your Forgejo account</span>
  <table class="secret-table">
    <tr><th scope="row">Username</th><td><code class="secret-value">{html.escape(sid)}</code></td></tr>
    <tr><th scope="row">Password</th><td><code class="secret-value">{html.escape(forgejo_password(sid))}</code></td></tr>
  </table>
  <span class="secret-hint">Yours alone, for signing in to Forgejo by hand. Git in your terminal and VS Code is already signed in (a token in <code>~/.git-credentials</code>), and the Forgejo card signs you in to the web page.</span>
</div>
<p class="footnote">Reload this page any time -- it always brings you straight back here as <strong>{html.escape(sid)}</strong>, with nothing lost.</p>
<p class="footnote"><a href="/logout">Sign out</a></p>"""

        return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(WORKSHOP_NAME)}</title>
<style>{CONFIRM_CSS}</style></head>
<body>{body}</body></html>"""

    def render_facilitator_workspace(self):
        """The facilitator's one-stop page at /admin: a roster of live
        terminal tiles (one per held slot -- account/name/IP/status/Release
        in the tile header, an iframe onto /admin/watch/<sid>/ underneath),
        plus their own VS Code/Terminal/Forgejo/Slides as further tabs, all
        on one wide page -- no dependency on the shared student gate either
        (see gateway/Caddyfile: /admin has its own basic_auth, which is
        also now accepted at the shared gate, so a facilitator never needs
        the student credential at all).

        Deliberately its own full HTML document rather than page() (which
        is tuned for the narrow single-column student flow) -- this page
        needs real width for the tool iframes and the roster grid.

        The VS Code/Terminal/Forgejo/Slides tabs are plain iframes onto the
        same /ide/, /term/, /forgejo-login, /slides/ routes the old
        separate-tab links used -- nothing new for Caddy or the allocator
        to authorize, since the facilitator's browser already carries
        whatever those routes need (the shared-gate basic_auth realm is
        reused automatically once /admin's has been satisfied -- see the
        Caddyfile comment above the shared block -- and neither ttyd nor
        code-server nor Forgejo send X-Frame-Options/frame-ancestors, the
        same fact that already makes the watch tiles embeddable). Each
        iframe's src is set lazily, on that tab's first click, so opening
        /admin doesn't eagerly spin up the facilitator's own VS
        Code/terminal/Forgejo session -- and once set it's never torn
        down, just hidden via CSS when another tab is active, so switching
        tabs doesn't lose editor/terminal state.

        The roster tab itself, unlike those, is the page's default (active)
        tab, so it builds its tiles -- and connects each one's watch
        websocket -- as soon as /admin loads, not lazily. It's kept in sync
        by polling /admin/api/sessions: client-side Set-diffing against the
        existing `tiles` object so a join/leave only ever adds/removes the
        one tile involved, never a wholesale replace (that would tear down
        and reconnect every iframe's websocket every poll). An existing
        tile's status dot does get refreshed in place on every poll, since
        "active" genuinely changes over a session -- just without touching
        that tile's iframe."""
        body = """
<nav id="side">
  <div id="bar">
    <h1>Facilitator</h1>
    <p class="sub">Signed in as <span class="badge">FACILITATOR_USERNAME_PLACEHOLDER</span></p>
    <p class="sub"><a href="/logout" target="_top">Sign out</a></p>
  </div>
  <div class="tabs" role="tablist" aria-orientation="vertical">
  <button class="tab active" data-tab="roster">Roster</button>
  <button class="tab" data-tab="ide">VS Code</button>
  <button class="tab" data-tab="term">Terminal</button>
  <button class="tab" data-tab="forgejo">Forgejo</button>
  <button class="tab" data-tab="slides">Slides</button>
EXT_TABS_PLACEHOLDER  </div>
  <div id="status" role="group" aria-label="Service status"></div>
</nav>

<main id="main">
<div class="panel active" id="panel-roster">
  <div id="roster-bar">
    <button id="release-unused" type="button" title="Frees every slot taken over 2 minutes ago with no VS Code or terminal running">Release unused</button>
    <span id="release-unused-out" class="sub"></span>
  </div>
  <p id="empty" class="sub">No students connected yet.</p>
  <div id="grid"></div>
</div>

<div class="panel" id="panel-ide"><iframe data-src="/ide/"></iframe></div>
<div class="panel" id="panel-term"><iframe data-src="/term/"></iframe></div>
<div class="panel" id="panel-forgejo"><iframe data-src="/forgejo-login"></iframe></div>
<div class="panel" id="panel-slides"><iframe data-src="/slides/"></iframe></div>
EXT_PANELS_PLACEHOLDER</main>
<script src="/admin/admin.js"></script>"""
        body = body.replace("FACILITATOR_USERNAME_PLACEHOLDER", html.escape(FACILITATOR_USERNAME))
        # The facilitator gets every tool a student has: every tab a workshop
        # or module declares next to its cards (extensions.json).
        # Ids are [a-z0-9-] and src a checked same-origin path; escaped anyway.
        body = body.replace(
            "EXT_TABS_PLACEHOLDER",
            "".join(f'  <button class="tab" data-tab="{html.escape(t["id"])}">{html.escape(t["label"])}</button>\n'
                    for t in EXTENSIONS["admin_tabs"]),
        ).replace(
            "EXT_PANELS_PLACEHOLDER",
            "".join(f'<div class="panel" id="panel-{html.escape(t["id"])}">'
                    f'<iframe data-src="{html.escape(t["src"])}"></iframe></div>\n'
                    for t in EXTENSIONS["admin_tabs"]),
        )
        return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(WORKSHOP_NAME)} — Facilitator</title>
<link rel="stylesheet" href="/admin/admin.css">
</head>
<body>{body}</body></html>"""

    # -- GET routes ----------------------------------------------------
    def do_GET(self):
        if not self.gateway_authorized():
            self.send_response(403)
            self.end_headers()
            return
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path

        if path == "/session-check":
            self.handle_session_check(parsed)
            return

        if path == "/login":
            nxt = self.login_next(urllib.parse.parse_qs(parsed.query).get("next", [""])[0])
            if self.session_account():
                self.redirect(nxt)
            else:
                self.send_html(self.render_login(nxt=nxt), headers=NO_STORE_HEADERS)
            return

        if path.startswith("/login/assets/"):
            asset = LOGIN_ASSETS.get(path[len("/login/assets/"):])
            if asset is None:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", asset[0])
            self.send_header("Content-Length", str(len(asset[1])))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(asset[1])
            return

        if path == "/logout":
            self.redirect("/login", cookies=[self.session_cookie("", 0)])
            return

        if path == "/":
            username, sid = self.resolve_identity()
            if username == FACILITATOR_USERNAME:
                # /admin is the facilitator's one canonical page (own tool
                # links + roster) -- send them there instead of rendering
                # student-shaped content at "/".
                self.send_response(303)
                self.send_header("Location", "/admin")
                self.send_header("Content-Length", "0")
                self.end_headers()
            elif sid is not None:
                self.send_html(self.render_confirmation(sid), headers=NO_STORE_HEADERS)
            else:
                self.send_html(self.render_name_form())
            return

        if path == "/forgejo-login":
            # Deliberately NOT under /git/* -- Caddy's @git matcher is a
            # raw prefix match ("/git*"), so a path starting with "/git"
            # here would be routed straight to Forgejo instead of us.
            username, sid = self.resolve_identity()
            if username is None:
                self.send_response(303)
                self.send_header("Location", "/")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if username == FACILITATOR_USERNAME:
                forgejo_user, password = FORGEJO_ADMIN_USER, FORGEJO_ADMIN_PASSWORD
            else:
                forgejo_user, password = sid, forgejo_password(sid)
            cookies = forgejo_login_request(forgejo_user, password)
            audit("forgejo-login", account=username, target=forgejo_user,
                  result="ok" if cookies else "failed")
            # ?next=<path>: signed in to Forgejo, go on to another page on
            # this site (a module's OIDC sign-in, say). Anything else: the repo.
            nxt = urllib.parse.parse_qs(parsed.query).get("next", [""])[0]
            self.send_response(303)
            self.send_header("Location", local_path(nxt) or f"/git/{FORGEJO_ORG}/{FORGEJO_REPO}")
            for cookie in cookies:
                self.send_header("Set-Cookie", cookie)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        if path == "/whoami":
            # The browser's own student ID, for pages that personalise
            # themselves (the lab reader swaps it in for "studentXX").
            # null for the facilitator and for a browser holding no slot.
            _, sid = self.resolve_identity()
            self.send_json({"user": sid}, headers=NO_STORE_HEADERS)
            return

        if path == "/auth-check":
            self.handle_auth_check(parsed)
            return

        if path == "/auth-check-watch":
            self.handle_auth_check_watch(parsed)
            return

        if path in ("/admin", "/admin/"):
            # Reaching this route at all means Caddy's own facilitator-only
            # basic_auth (see gateway/Caddyfile's @admin block) already
            # passed -- no separate cookie/login step needed.
            self.send_html(self.render_facilitator_workspace())
            return

        if path in ADMIN_ASSETS:
            # The /admin page's own script and stylesheet (see ADMIN_JS):
            # same facilitator gate as /admin itself.
            self.send_asset(*ADMIN_ASSETS[path])
            return

        if path == "/admin/api/sessions":
            self.handle_sessions_api()
            return

        if path == "/admin/api/status":
            self.handle_status_api()
            return

        if path.startswith("/admin/api/forgejo-password/"):
            self.handle_forgejo_password(path[len("/admin/api/forgejo-password/"):])
            return

        self.send_response(404)
        self.end_headers()

    def handle_auth_check(self, parsed):
        qs = urllib.parse.parse_qs(parsed.query)
        if "route" in qs:
            self.handle_route_check((qs.get("route") or [""])[0])
            return
        tool = (qs.get("tool") or [""])[0]
        if tool not in ("ide", "term"):
            self.send_response(400)
            self.end_headers()
            return

        # The page or asset the browser asked for (gateway/Caddyfile sends
        # it), without the query string, to tell a page load from an asset.
        uri = self.headers.get("X-Forwarded-Uri", "").split("?", 1)[0][:200]
        username, _sid = self.resolve_identity()
        if username is None:
            audit_check("auth-check", None, tool, 303, uri=uri)
            self.send_response(303)
            self.send_header("Location", "/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        port = ide_port(username) if tool == "ide" else term_port(username)
        started = time.monotonic()
        resp = control_request("POST", f"/start/{tool}/{username}")
        ready = False
        if resp is not None:
            try:
                ready = bool(json.loads(resp).get("ready"))
            except (ValueError, AttributeError):
                ready = False
        audit_check("auth-check", username, tool, 200 if ready else 202, uri=uri,
                    ms=round((time.monotonic() - started) * 1000))

        if ready:
            self.send_response(200)
            self.send_header("X-Upstream-Port", str(port))
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            # code-server/ttyd was just spawned (or web-terminal itself is
            # briefly unreachable) and isn't listening yet -- 202 tells
            # Caddy (see gateway/Caddyfile's @ide/@term handle_response) to
            # serve the self-refreshing starting page instead of proxying
            # to a port nothing is listening on yet.
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def handle_route_check(self, route_id):
        """forward_auth for an extension route's identity/facilitator gate
        (render_extensions.py's Caddy template). 200 hands Caddy the caller's
        name as X-Dojo-User, and X-Dojo-Host when the route has a host
        template; Caddy strips any client-sent copies first and passes them
        upstream next to X-Gateway-Token. No session: 303 to "/" like the
        other tools. Unknown or shared route: 404, so nothing reaches an
        upstream this workshop didn't declare."""
        route = EXT_ROUTES.get(route_id)
        username, _sid = self.resolve_identity()
        denied = None
        if route is None or route["gate"] not in ("identity", "facilitator"):
            denied = 404
        elif username is None:
            denied = 303
        elif route["gate"] == "facilitator" and username != FACILITATOR_USERNAME:
            denied = 403
        elif "host" in route and not DNS_LABEL_RE.match(username.lower()):
            denied = 403
        audit_check("route-check", username, route_id, denied or 200)
        if route is None or route["gate"] not in ("identity", "facilitator"):
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if username is None:
            self.send_response(303)
            self.send_header("Location", "/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if route["gate"] == "facilitator" and username != FACILITATOR_USERNAME:
            self.send_response(403)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        host = None
        if "host" in route:
            label = username.lower()
            if not DNS_LABEL_RE.match(label):
                self.send_response(403)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            host = route["host"].replace("{user}", label)
        self.send_response(200)
        self.send_header("X-Dojo-User", username)
        if host is not None:
            self.send_header("X-Dojo-Host", host)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def handle_auth_check_watch(self, parsed):
        """Gates /admin/watch/<studentId> (see gateway/Caddyfile). Reached
        only after Caddy's own facilitator-only basic_auth on /admin*, but
        re-checked here too -- this process shouldn't trust routing alone
        to keep a student out of another student's terminal."""
        username, _sid = self.resolve_identity()
        sid = (urllib.parse.parse_qs(parsed.query).get("student") or [""])[0][:40]
        if username != FACILITATOR_USERNAME:
            audit_check("watch", username, sid, 403)
            self.send_response(403)
            self.end_headers()
            return

        # A demo bot has no "held slot" concept -- see BOT_IDS above -- it's
        # always watchable as long as --test provisioned it.
        if sid not in BOT_IDS and (sid not in slots or slot_snapshot(sid)["name"] is None):
            audit_check("watch", username, sid, 404)
            self.send_response(404)  # not a currently held slot
            self.end_headers()
            return

        body = control_request("POST", f"/start/watch/{sid}")
        audit_check("watch", username, sid, 409 if body is None else 200)
        if body is None:
            self.send_response(409)  # student has no term session to watch yet
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("X-Upstream-Port", str(watch_port(sid)))
        self.send_header("Content-Length", "0")
        self.end_headers()

    def handle_status_api(self):
        """Facilitator service status: authorised exactly like
        /admin/api/sessions (do_GET's gateway_authorized() ran first; Caddy's
        /admin* basic_auth is the facilitator gate). Reads the snapshot the
        probe thread publishes -- no upstream I/O here."""
        self.send_json(_status_snapshot)

    def handle_forgejo_password(self, sid):
        """The Roster's "Password" button (remediation T2.1d): one student's
        own Forgejo password, for when the facilitator helps at a desk.
        Behind /admin's facilitator gate like the other /admin/api routes;
        also needs the roster JS's X-Requested-With header, as Release does,
        so no other page can have a browser fetch it. Logged."""
        if self.headers.get("X-Requested-With") != "dojo-admin":
            self.send_response(403)
            self.end_headers()
            return
        if sid not in STUDENT_IDS:
            self.send_response(404)
            self.end_headers()
            return
        audit("forgejo-password-shown", target=sid)
        self.send_json({"studentId": sid, "password": forgejo_password(sid)}, headers=NO_STORE_HEADERS)

    def handle_sessions_api(self):
        held = held_slots()  # copies; the status call below runs without the lock
        all_ids = list(held) + BOT_IDS
        status = {}
        if all_ids:
            body = control_request("GET", "/status?users=" + ",".join(all_ids))
            if body:
                try:
                    status = json.loads(body)
                except json.JSONDecodeError:
                    status = {}
        rows = []
        for sid, slot in held.items():
            s = status.get(sid) or {}
            rows.append({
                "studentId": sid,
                "name": slot["name"],
                "ip": slot["ip"],
                "assignedAt": slot["assigned_at"],
                "active": bool(s.get("active", False)),
                # Whether this student has a terminal session to watch yet
                # -- see workspace-control.py's /status. The roster JS uses
                # this to connect a tile's watch iframe itself the moment
                # it turns true, instead of only on the next manual reload.
                "watchable": bool(s.get("watchable", False)),
            })
        # Demo bots are always listed (no /assign step -- see BOT_IDS above),
        # right after real students, so a facilitator can watch/Release them
        # the same way. bot-runner.sh's own narration prints which persona
        # (expert/intermediate/novice) each one is playing.
        for sid in BOT_IDS:
            s = status.get(sid) or {}
            rows.append({
                "studentId": sid,
                "name": f"Demo bot ({sid})",
                "ip": "bot",
                "assignedAt": None,
                "active": bool(s.get("active", False)),
                "watchable": bool(s.get("watchable", False)),
            })
        self.send_json(rows)

    # -- POST routes -----------------------------------------------------
    def do_POST(self):
        if not self.gateway_authorized():
            self.send_response(403)
            self.end_headers()
            return
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path

        if path == "/login":
            self.handle_login()
            return

        if path == "/assign":
            self.handle_assign()
            return

        if path.startswith("/admin/release/"):
            # HTTP Basic Auth (unlike a cookie) carries no SameSite
            # protection of its own -- a browser that's already satisfied
            # /admin's basic_auth reattaches those credentials to ANY
            # same-origin request, including one triggered by a hidden form
            # on a page a facilitator merely has open in another tab. A
            # plain cross-site <form method=post> can't set a custom
            # header, and a cross-site fetch() that tries to would first
            # need this server to answer its CORS preflight (it doesn't) --
            # so requiring this header on the actual roster JS's own fetch
            # call (see render_facilitator_workspace's releaseTile) blocks
            # both of those forgery paths while costing the real UI nothing.
            if self.headers.get("X-Requested-With") != "dojo-admin":
                self.send_response(403)
                self.end_headers()
                return
            sid = path[len("/admin/release/"):]
            self.handle_release(sid)
            return

        if path == "/admin/release-unused":
            if self.headers.get("X-Requested-With") != "dojo-admin":
                self.send_response(403)
                self.end_headers()
                return
            self.handle_release_unused()
            return

        self.send_response(404)
        self.end_headers()

    # -- front door (/login) ---------------------------------------------
    def session_cookie(self, value, max_age):
        cookie = f"{SESSION_COOKIE}={value}; HttpOnly; Path=/; SameSite=Lax; Max-Age={max_age}"
        return cookie + "; Secure" if COOKIE_SECURE else cookie

    def session_account(self):
        """The account the browser's login cookie was issued to, or None."""
        for part in self.headers.get("Cookie", "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == SESSION_COOKIE:
                return read_session(value)
        return None

    @staticmethod
    def login_next(value):
        """Where to go after signing in: a path on this site, never the login
        page itself, else the front page."""
        value = local_path(value or "")
        return value if value and not value.startswith("/login") else "/"

    def redirect(self, location, cookies=()):
        self.send_response(303)
        self.send_header("Location", location)
        for cookie in cookies:
            self.send_header("Set-Cookie", cookie)
        for k, v in NO_STORE_HEADERS:
            self.send_header(k, v)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def render_login(self, error=None, username="", nxt="/"):
        esc = html.escape
        alert = ""
        if error:
            alert = ('<p class="alert" role="alert"><svg viewBox="0 0 24 24" aria-hidden="true">'
                     '<circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>'
                     f'{esc(error)}</p>')
        lede = esc(WORKSHOP_DESCRIPTION) if WORKSHOP_DESCRIPTION else "Sign in with the class login to reach your lab."
        return (LOGIN_HTML.replace("{{WORKSHOP}}", esc(WORKSHOP_NAME))
                .replace("{{LEDE}}", lede)
                .replace("{{ERROR}}", alert)
                .replace("{{CARD_CLASS}}", " shake" if error else "")
                .replace("{{USERNAME}}", esc(username, quote=True))
                .replace("{{NEXT}}", esc(nxt, quote=True)))

    def handle_session_check(self, parsed):
        """Caddy's forward_auth target for every gated request. 200 plus
        X-Session-User (Caddy copies it to X-Auth-User upstream) when the
        cookie is a live session; otherwise a browser page load is sent to
        /login and anything else (a poll, an API call) gets 401. ?role=
        facilitator is /admin: the class login is refused there."""
        account = self.session_account()
        role = urllib.parse.parse_qs(parsed.query).get("role", [""])[0]
        if account is None:
            wants_page = (self.headers.get("X-Forwarded-Method", "GET") == "GET"
                          and "text/html" in self.headers.get("Accept", ""))
            if wants_page:
                target = local_path(self.headers.get("X-Forwarded-Uri", ""))
                self.redirect("/login" if not target or target == "/"
                              else "/login?next=" + urllib.parse.quote(target, safe=""))
            else:
                self.send_response(401)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", "0")
                self.end_headers()
            return
        if role == "facilitator" and account != FACILITATOR_USERNAME:
            self.send_html(page("Facilitator only", (
                "<h1>Facilitator only</h1><p>This page is for the facilitator's login.</p>"
                '<p><a href="/logout">Sign in as someone else</a></p>')), status=403,
                headers=NO_STORE_HEADERS)
            return
        self.send_response(200)
        self.send_header("X-Session-User", account)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def handle_login(self):
        form = self.read_form_body()
        username = (form.get("username") or "").strip()
        password = form.get("password") or ""
        nxt = self.login_next(form.get("next"))
        ip = self.client_ip()
        account = check_login(username, password)
        if account is None:
            # A right password still gets in during someone else's guessing
            # spree from the same address (a class behind one NAT).
            if LOGIN_GUARD.blocked(ip):
                audit("login", ip=ip, result="rate-limited")
                self.send_html(self.render_login("Too many wrong guesses. Wait a minute and try again.",
                                                 username, nxt),
                               status=429, headers=[("Retry-After", "60")] + NO_STORE_HEADERS)
                return
            LOGIN_GUARD.fail(ip)
            audit("login", ip=ip, result="failed")
            self.send_html(self.render_login("That username and password don't match. Try again.",
                                             username, nxt),
                           status=401, headers=NO_STORE_HEADERS)
            return
        audit("login", account=account, ip=ip, result="ok")
        self.redirect(nxt, cookies=[self.session_cookie(make_session(account), SESSION_SECONDS)])

    def handle_assign(self):
        # Idempotent: a valid existing cookie just re-renders the confirmation
        # instead of claiming a second slot (handles refresh/back-button).
        # A facilitator identity in particular must never fall through to
        # the student-slot logic below -- that would silently demote them
        # to a random studentNN account (this is exactly how a facilitator
        # who typed admin:admin at "/" used to end up assigned student01).
        username, sid = self.resolve_identity()
        if username == FACILITATOR_USERNAME:
            self.read_form_body()  # drain body regardless
            self.send_html(self.render_facilitator_workspace())
            return
        if sid is not None:
            self.read_form_body()  # drain body regardless
            self.send_html(self.render_confirmation(sid), headers=NO_STORE_HEADERS)
            return

        form = self.read_form_body()
        name = (form.get("name") or "").strip()[:60]
        if not name:
            self.send_html(self.render_name_form(), status=400)
            return

        wait = ASSIGN_LIMIT.take()
        if wait:
            audit("assign", name=name, ip=self.client_ip(), result="rate-limited")
            self.send_html(self.render_busy(wait), status=429,
                           headers=[("Retry-After", str(wait))] + NO_STORE_HEADERS)
            return

        sid, token = claim_slot(name, self.client_ip())
        if sid is None:
            audit("assign", name=name, ip=self.client_ip(), result="full")
            self.send_html(self.render_full())
            return

        audit("assign", account=sid, name=name, ip=self.client_ip(), result="assigned")

        cookie = f"{COOKIE_NAME}={token}; HttpOnly; Path=/; SameSite=Lax"
        if COOKIE_SECURE:
            cookie += "; Secure"

        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def handle_release(self, sid):
        if sid in BOT_IDS:
            # No slot bookkeeping for a bot -- it isn't "assigned" in the
            # first place (see BOT_IDS above). This just kills its process;
            # bot-supervisor.sh (in web-terminal) notices within its poll
            # interval and restarts it, and bot-runner.sh resumes from its
            # own persisted (round, step) state -- see engine/README.md's
            # "Demo bots (--test)" section.
            control_request("POST", f"/stop/{sid}")
            audit("release", target=sid, result="bot-restarted")
            self.send_json({"released": sid})
            return
        if sid not in slots:
            self.send_response(404)
            self.end_headers()
            return
        release_slot(sid)
        self.send_json({"released": sid})

    def handle_release_unused(self):
        """The Roster's "Release unused" (remediation T3.4): frees every slot
        taken at least UNUSED_AFTER_SECONDS ago with no IDE or terminal
        running, e.g. slots a script grabbed. One status call for all."""
        now = time.time()
        # sid -> the token holding it now: a slot released and re-claimed
        # while the status call below runs is left alone (release_slot).
        held = {sid: slot["token"] for sid, slot in held_slots().items()
                if now - (slot["assigned_at"] or now) >= UNUSED_AFTER_SECONDS}
        status = {}
        if held:
            body = control_request("GET", "/status?users=" + ",".join(held))
            if not body:
                self.send_json({"error": "workspace status unavailable"}, status=503)
                return
            try:
                status = json.loads(body)
            except json.JSONDecodeError:
                self.send_json({"error": "workspace status unavailable"}, status=503)
                return
        released = []
        for sid, token in held.items():
            s = status.get(sid) or {}
            if not s.get("active") and not s.get("watchable"):
                if release_slot(sid, result="released-unused", token=token) is not None:
                    released.append(sid)
        self.send_json({"released": released})


class AllocatorServer(http.server.ThreadingHTTPServer):
    """One daemon thread per connection, so a slow or idle client only ties
    up its own thread (for at most Handler.timeout) and never the class."""
    daemon_threads = True
    request_queue_size = 128  # a whole class arriving at once (default 5)


def make_server(addr):
    return AllocatorServer(addr, Handler)


def main():
    threading.Thread(target=status_probe_loop, name="status-probe", daemon=True).start()
    server = make_server(("0.0.0.0", 8080))
    server.serve_forever()


if __name__ == "__main__":
    main()
