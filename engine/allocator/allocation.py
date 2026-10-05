"""The slot table (who holds which studentNN), its state file, per-student ports, the
workspace-control client and the student reset steps. Locking rules are in server.py.
"""
import http.client
import json
import os
import re
import secrets
import socket
import threading
import time
import urllib.parse

from config import (
    BOT_IDE_PORT_BASE, BOT_PASSWORD, BOT_PREFIX, BOT_TERM_PORT_BASE, BOT_WATCH_PORT_BASE, CONTROL_PORT,
    CONTROL_TIMEOUT, CONTROL_TOKEN, EXTENSIONS, FACILITATOR_IDE_PORT, FACILITATOR_TERM_PORT, FACILITATOR_USERNAME,
    FORGEJO_ADMIN_PASSWORD, FORGEJO_ADMIN_USER, FORGEJO_ORG, GATEWAY_TOKEN, GIT_SERVER_HOST, GIT_SERVER_PORT,
    IDE_PORT_BASE, _short, STUDENT_IDS, STUDENT_PREFIX, TERM_PORT_BASE, WATCH_PORT_BASE, WEB_TERMINAL_HOST,
)
import config
from dojo_secret import forgejo_password
import reset

# studentId -> {name, ip, token, tool, assigned_at}
slots = {sid: {"name": None, "ip": None, "token": None, "tool": None, "assigned_at": None} for sid in STUDENT_IDS}
token_index = {}  # token -> studentId
# Guards slots and token_index (see the locking rules at the top).
_state_lock = threading.Lock()
# Where the slot table is saved; empty means not saved (unit tests).
STATE_FILE = os.environ.get("ALLOCATOR_STATE_FILE", "")
SLOT_FIELDS = ("name", "ip", "token", "tool", "assigned_at")
_slots_version = 0  # bumped under _state_lock on every change
_saved_version = 0  # guarded by _save_lock
_save_lock = threading.Lock()


def save_slots():
    """Write the held slots to STATE_FILE (temp file + rename). Called
    after a claim or release, never under _state_lock."""
    global _saved_version
    if not STATE_FILE:
        return
    with _state_lock:
        held = {sid: dict(slot) for sid, slot in slots.items() if slot["name"] is not None}
        version = _slots_version
    with _save_lock:
        if version <= _saved_version:
            return  # a newer snapshot is already on disk
        tmp = STATE_FILE + ".tmp"
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                json.dump({"slots": held}, f)
            os.replace(tmp, STATE_FILE)
            _saved_version = version
        except OSError as exc:
            config.audit("state-save", result="failed", detail=str(exc))


def load_slots():
    """Read STATE_FILE back at start-up: slots for students that still
    exist (STUDENT_COUNT may have shrunk), and the token index."""
    if not STATE_FILE:
        return 0
    try:
        with open(STATE_FILE) as f:
            held = json.load(f).get("slots", {})
    except FileNotFoundError:
        return 0
    except (OSError, ValueError, AttributeError) as exc:
        config.audit("state-load", result="failed", detail=str(exc))
        return 0
    restored = 0
    with _state_lock:
        for sid, slot in held.items():
            if sid not in slots or not isinstance(slot, dict) or not slot.get("name") or not slot.get("token"):
                continue
            slots[sid].update({k: slot.get(k) for k in SLOT_FIELDS})
            token_index[slot["token"]] = sid
            restored += 1
    config.audit("state-load", result="ok", restored=restored)
    return restored


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
        _bump_version()
    save_slots()
    config.audit("release", target=sid, name=name, result=result)
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
        _bump_version()
    save_slots()
    return sid, token


def _bump_version():
    """Caller holds _state_lock."""
    global _slots_version
    _slots_version += 1


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
    if username in config.BOT_IDS:
        return BOT_IDE_PORT_BASE + bot_number(username)
    return IDE_PORT_BASE + student_number(username)


def term_port(username):
    if username == FACILITATOR_USERNAME:
        return FACILITATOR_TERM_PORT
    if username in config.BOT_IDS:
        return BOT_TERM_PORT_BASE + bot_number(username)
    return TERM_PORT_BASE + student_number(username)


def watch_port(sid):
    if sid in config.BOT_IDS:
        return BOT_WATCH_PORT_BASE + bot_number(sid)
    return WATCH_PORT_BASE + student_number(sid)


def find_free_slot():
    """Caller holds _state_lock (claim_slot)."""
    for sid in STUDENT_IDS:
        if slots[sid]["name"] is None:
            return sid
    return None


class TTLCache:
    """A few seconds' memory of an answer, so a burst of identical requests
    makes one control call instead of hundreds. Its own small lock; the
    caller does the I/O outside it."""

    def __init__(self, ttl):
        self.ttl = ttl
        self._lock = threading.Lock()
        self._items = {}  # key -> (expires, value)

    def get(self, key):
        with self._lock:
            hit = self._items.get(key)
            if hit is None or hit[0] <= time.monotonic():
                self._items.pop(key, None)
                return None
            return hit[1]

    def put(self, key, value):
        with self._lock:
            now = time.monotonic()
            if len(self._items) > 512:  # drop expired entries now and then
                self._items = {k: v for k, v in self._items.items() if v[0] > now}
            self._items[key] = (now + self.ttl, value)

    def forget_user(self, user):
        """Drop every (tool, user) key for this user."""
        with self._lock:
            for key in [k for k in self._items if isinstance(k, tuple) and k[-1] == user]:
                del self._items[key]


# A workspace that answered ready is trusted for this long, so the hundreds of
# asset requests behind one VS Code page load don't each make a control call
# (identity and the reset fence are still checked on every request). Any stop
# or reset of that user clears it (control_request below).
READY_CACHE = TTLCache(2.0)
# The roster's workspace status, shared by every open /admin tab.
STATUS_CACHE = TTLCache(3.0)
_FORGET_ON = re.compile(r"^/(?:stop|reset)/([A-Za-z0-9_-]+)")


def control_request(method, path, timeout=CONTROL_TIMEOUT):
    """Best-effort call to workspace-control.py inside web-terminal. Never
    raises -- returns None on any failure so a flaky internal call degrades
    gracefully instead of blocking a request thread."""
    stopping = _FORGET_ON.match(path) if method == "POST" else None
    if stopping:
        READY_CACHE.forget_user(stopping.group(1))
    try:
        return _control_call(method, path, timeout)
    finally:
        if stopping:  # again, in case an auth-check cached it mid-stop
            READY_CACHE.forget_user(stopping.group(1))


# Whether the last control call reached web-terminal, so the log shows the
# moment it went away and came back (not one line per failed call). A plain
# bool: a lost update only costs a duplicate or missing log line.
_control_reachable = True


def _control_call(method, path, timeout):
    global _control_reachable
    try:
        conn = http.client.HTTPConnection(WEB_TERMINAL_HOST, CONTROL_PORT, timeout=timeout)
        conn.request(method, path, headers={"X-Control-Token": CONTROL_TOKEN})
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
    except (OSError, socket.timeout, http.client.HTTPException) as exc:
        if _control_reachable:
            _control_reachable = False
            config.audit("control", result="unreachable", path=path.split("?", 1)[0], detail=_short(repr(exc)))
        return None
    if not _control_reachable:
        _control_reachable = True
        config.audit("control", result="reachable", path=path.split("?", 1)[0])
    if resp.status != 200:
        return None
    return body


# -- Student reset (reset.py has the steps and the worker) -----------------
# workspace-control.py's POST /reset/<user> waits for Forgejo (up to 60 s) and
# runs every hook, so it gets far longer than CONTROL_TIMEOUT.
RESET_TERMINAL_TIMEOUT = 300.0


def reset_terminal(sid):
    body = control_request("POST", f"/reset/{sid}", timeout=RESET_TERMINAL_TIMEOUT)
    if body is None:
        raise reset.ResetError("web-terminal did not answer (or a reset of this account is already running)")
    result = json.loads(body)
    failed = [s for s in result.get("steps", []) if not s.get("ok")]
    if failed:
        raise reset.ResetError("; ".join(f"{s.get('id')}: {s.get('detail') or 'failed'}" for s in failed))
    return f"{len(result.get('steps', []))} step(s) ok"


def reset_steps(sid, optional=frozenset()):
    """The steps of one reset, in order (reset.py's module docstring);
    `optional` names the optional hooks the facilitator ticked."""
    fj = reset.Forgejo(GIT_SERVER_HOST, GIT_SERVER_PORT, FORGEJO_ADMIN_USER, FORGEJO_ADMIN_PASSWORD)
    password = BOT_PASSWORD if sid in config.BOT_IDS else forgejo_password(sid)

    def stop():
        if control_request("POST", f"/stop/{sid}") is None:
            raise reset.ResetError("web-terminal did not answer")
        return "processes stopped"

    hooks = [h for h in EXTENSIONS["resets"] if not h.get("optional") or h["id"] in optional]
    return [
        ("stop", "Stop VS Code and terminal" if config.HAS_IDE else "Stop terminal", stop),
    ] + reset.hook_steps(hooks, sid, "teardown", GATEWAY_TOKEN) + [
        ("forgejo-teardown", "Forgejo: close pull requests, delete branches and the account",
         lambda: reset.forgejo_teardown(fj, FORGEJO_ORG, sid)),
        ("forgejo-provision", "Forgejo: recreate the account",
         lambda: reset.forgejo_provision(fj, FORGEJO_ORG, sid, password)),
        ("terminal", "Terminal: home, lab files and hooks", lambda: reset_terminal(sid)),
    ] + reset.hook_steps(hooks, sid, "provision", GATEWAY_TOKEN)


RESETS = reset.ResetManager(reset_steps, config.audit)


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
