#!/usr/bin/env python3
"""runner-controller: registers single-use runners, scales them, and serves
the Runners panel (VAULT-FUNDAMENTALS-PLAN.md §6.3, §6.4).

Every few seconds it reads Forgejo's runner list and waiting jobs (admin
API) and the pool supervisor's /spool/state.json, then:

- removes registrations whose runner is gone (Forgejo keeps showing a dead
  runner as idle for a while, so the supervisor's view wins, §6.3);
- in Auto, keeps RUNNER_MIN_IDLE runners ready plus one per waiting job, up
  to the max, and removes an idle runner above that after
  RUNNER_IDLE_TIMEOUT seconds. A busy runner is never removed;
- in Manual, does nothing by itself: the panel's - / + do it.

To start a runner it registers an ephemeral one through the API and drops its
config in /spool/start/<name>.yaml; to remove an idle one it drops
/spool/stop/<name>. The supervisor does the rest (../pool/supervise.py).

HTTP (behind the gateway's facilitator gate, /runners stripped): the panel
page and its API, for the facilitator only, checked here too because
workshop_lab can reach this port directly: X-Gateway-Token must match and
X-Auth-User must be FACILITATOR_USERNAME. POSTs also need
`X-Requested-With: dojo-runners`, which a cross-site form can't send.
Requests are answered from the snapshot the loop keeps, never with a
Forgejo call of their own. /healthz needs no token.
"""
import base64
import collections
import hmac
import http.server
import json
import math
import os
import re
import secrets
import signal
import socketserver
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
# dojo_http: modules/_shared/ in the source tree, ./_shared/ once ./run.sh has copied it (SHARED= in module.env).
sys.path[:0] = [os.path.join(HERE, "..", "..", "_shared"), os.path.join(HERE, "_shared")]
import dojo_http  # noqa: E402

PREFIX = "pool-"
ALIVE = ("starting", "idle", "busy")
FINISHED = ("done", "removed", "failed")
# A registration with no runner in the spool is left alone this long after
# we made it (the supervisor may not have picked it up yet).
GRACE = 30
# Forgejo reporting a live runner offline for this long turns it red.
OFFLINE_AFTER = 30
# This many failed starts within FAIL_WINDOW pause Auto's starts for FAIL_WINDOW.
FAIL_LIMIT = 3
FAIL_WINDOW = 60
TICK = 3
# The panel can raise the max this far (or to RUNNER_MAX, if that is higher):
# every runner shares the pool's RUNNER_POOL_MEM_LIMIT.
MAX_CEILING = 24


def env_int(name, default, env=os.environ):
    value = (env.get(name) or "").strip()
    return int(value) if value else default


class Config:
    def __init__(self, env=os.environ):
        self.min_idle = env_int("RUNNER_MIN_IDLE", 2, env)
        students = env_int("STUDENT_COUNT", 30, env)
        # §6.3: ceil(students / 3), at least 2, at most 12, unless set.
        self.max = env_int("RUNNER_MAX", min(12, max(2, math.ceil(students / 3))), env)
        self.min_idle = max(0, min(self.min_idle, self.max))
        self.idle_timeout = env_int("RUNNER_IDLE_TIMEOUT", 120, env)
        self.job_timeout = env_int("RUNNER_JOB_TIMEOUT", 900, env)
        self.labels = [l.strip() for l in (env.get("RUNNER_LABELS") or "host:host").split(",") if l.strip()]
        self.gateway_token = env.get("GATEWAY_TOKEN", "")
        self.facilitator = env.get("FACILITATOR_USERNAME") or "root"
        self.forgejo_url = env.get("FORGEJO_URL") or "http://git-server:3000"
        self.forgejo_user = env.get("FORGEJO_ADMIN_USER", "")
        self.forgejo_password = env.get("FORGEJO_ADMIN_PASSWORD", "")
        # T5.2c: a scoped token minted by the runner-token-init service, read
        # from this file on every call; the password is only the fallback.
        self.forgejo_token_file = env.get("FORGEJO_TOKEN_FILE", "")
        self.spool = env.get("SPOOL_DIR") or "/spool"
        # The engine's student reset hook (extensions.json `resets`) carries this.
        self.reset_token = env.get("RESET_TOKEN", "")


class ForgejoError(Exception):
    pass


class Forgejo:
    """The few admin API calls the controller needs (T0.7)."""

    def __init__(self, base, user, password, timeout=5, token_file=""):
        self.base = base.rstrip("/") + "/api/v1"
        self.basic = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
        self.token_file = token_file
        self.has_password = bool(password)
        self.timeout = timeout
        self.repo_names = {}

    @property
    def auth(self):
        """The scoped token if the file holds one (re-read each call, so a
        re-minted token is picked up), else the admin password login."""
        if self.token_file:
            try:
                with open(self.token_file) as f:
                    tok = f.read().strip()
            except OSError:
                tok = ""
            if tok:
                return "token " + tok
            if self.has_password:
                return self.basic
            raise ForgejoError("waiting for the runner-token-init token")
        return self.basic

    def _call(self, method, path, body=None, ok=(200, 201, 204)):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Authorization": self.auth, "Content-Type": "application/json",
                                              "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                status = resp.status
        except urllib.error.HTTPError as e:
            raw, status = e.read(), e.code
        except (urllib.error.URLError, OSError) as e:
            raise ForgejoError(f"{method} {path}: {e}") from None
        if status not in ok:
            raise ForgejoError(f"{method} {path}: HTTP {status}")
        return json.loads(raw) if raw.strip() else None

    def runners(self):
        d = self._call("GET", "/admin/actions/runners?limit=100")
        d = d.get("runners", d) if isinstance(d, dict) else d
        return d or []

    def waiting_jobs(self, labels):
        names = ",".join(l.split(":", 1)[0] for l in labels)
        jobs = self._call("GET", f"/admin/actions/runners/jobs?labels={names}") or []
        return [j for j in jobs if j.get("status", "waiting") == "waiting"]

    def register(self, name):
        d = self._call("POST", "/admin/actions/runners",
                       {"name": name, "ephemeral": True, "description": "runner-pool, one job"})
        return d["uuid"], d["token"]

    def delete_runner(self, runner_id):
        self._call("DELETE", f"/admin/actions/runners/{int(runner_id)}", ok=(200, 204, 404))

    def repo_name(self, repo_id):
        if repo_id not in self.repo_names:
            try:
                self.repo_names[repo_id] = self._call("GET", f"/repositories/{int(repo_id)}")["full_name"]
            except (ForgejoError, KeyError, TypeError, ValueError):
                return f"repo {repo_id}"
        return self.repo_names[repo_id]


class Spool:
    """The files shared with the supervisor."""

    def __init__(self, root):
        self.root = root
        self.start_dir = os.path.join(root, "start")
        self.stop_dir = os.path.join(root, "stop")
        self.kill_dir = os.path.join(root, "kill")
        for d in (root, self.start_dir, self.stop_dir, self.kill_dir):
            os.makedirs(d, exist_ok=True)
            os.chmod(d, 0o700)

    def read_state(self):
        try:
            with open(os.path.join(self.root, "state.json")) as f:
                doc = json.load(f)
        except (OSError, ValueError):
            return {}
        return doc if isinstance(doc, dict) else {}

    def _write(self, path, text):
        tmp = os.path.join(os.path.dirname(path), "." + os.path.basename(path) + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp, path)

    def write_start(self, name, config):
        self._write(os.path.join(self.start_dir, name + ".yaml"), config)

    def write_stop(self, name):
        self._write(os.path.join(self.stop_dir, name), "")

    def write_kill(self, name):
        self._write(os.path.join(self.kill_dir, name), "")

    def pending(self):
        try:
            return {e[:-5] for e in os.listdir(self.start_dir) if e.endswith(".yaml")}
        except OSError:
            return set()


def runner_config(uuid, token, labels, job_timeout):
    # JSON is valid YAML, and it quotes every value for us.
    return json.dumps({
        "log": {"level": "info", "job_level": "info"},
        "runner": {"capacity": 1, "labels": labels, "timeout": f"{job_timeout}s"},
        "cache": {"enabled": False},
        "container": {"docker_host": "-"},
        "server": {"connections": {"dojo": {"url": "http://git-server:3000/", "uuid": uuid, "token": token}}},
    }, indent=2) + "\n"


class Controller:
    def __init__(self, cfg, forgejo, spool, clock=time.time):
        self.cfg = cfg
        self.forgejo = forgejo
        self.spool = spool
        self.clock = clock
        self.mode = "auto"  # every class starts in Auto (S15)
        self.min_idle = cfg.min_idle
        self.max = cfg.max  # the facilitator's call from the panel; starts at RUNNER_MAX
        self.ceiling = max(MAX_CEILING, cfg.max)
        # RV6: guards the fields below, in memory only, never across a Forgejo call. Readers (/api/state,
        # /healthz) take no lock at all: `snapshot` is replaced whole, never changed in place.
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.created = {}  # name -> when we registered it
        self.offline_since = {}
        self.seen_failed = set()
        self.fail_times = collections.deque()
        self.problems = collections.deque(maxlen=20)
        self.last_ok = 0.0
        self.error = ""
        self.sup = {}
        self.regs = {}
        self.waiting = []
        self.pending = set()
        self.shim_ca = ""
        self.repo_names = {}  # repo id -> name, for the waiting jobs (looked up before the lock)
        self.snapshot = {}

    # -- reading the world -------------------------------------------------

    def _fetch(self):
        """Everything a tick reads from the spool and Forgejo. No lock held."""
        state = self.spool.read_state()
        regs = self.forgejo.runners()
        waiting = self.forgejo.waiting_jobs(self.cfg.labels)
        names = {j.get("repo_id"): self.forgejo.repo_name(j.get("repo_id")) for j in waiting[:50]}
        return state, regs, waiting, names, self.spool.pending()

    def _refresh(self, seen):
        """Take in what _fetch read (under the lock, memory only). Returns the ids of registrations to delete."""
        state, regs, waiting, names, pending = seen
        now = self.clock()
        sup = state.get("runners") if isinstance(state.get("runners"), dict) else {}
        self.sup = {n: s for n, s in sup.items() if isinstance(s, dict) and n.startswith(PREFIX)}
        self.shim_ca = state.get("shim_ca", "")
        self.regs = {r["name"]: r for r in regs
                     if isinstance(r, dict) and str(r.get("name", "")).startswith(PREFIX)}
        self.waiting, self.repo_names = waiting, names
        # Registrations whose runner is gone. One the supervisor hasn't picked
        # up yet (still pending, or just made) is left alone.
        stale = []
        for name, reg in list(self.regs.items()):
            s = self.sup.get(name)
            if s is None:
                gone = name not in pending and now - self.created.get(name, 0) > GRACE
            else:
                gone = s.get("state") in FINISHED
            if gone:
                stale.append(reg["id"])
                del self.regs[name]
                self.created.pop(name, None)
        for name, s in self.sup.items():
            if s.get("state") == "failed" and name not in self.seen_failed:
                self.seen_failed.add(name)
                self.fail_times.append(now)
                self._problem(name, s.get("detail") or "failed")
        while self.fail_times and now - self.fail_times[0] > FAIL_WINDOW:
            self.fail_times.popleft()
        # The supervisor takes a start file a moment before its state.json lists
        # the runner: one we registered counts as starting until it shows up.
        self.pending = {n for n in pending if n not in self.sup}
        self.pending |= {n for n, t in self.created.items() if n not in self.sup and now - t <= GRACE}
        for name, reg in self.regs.items():
            if reg.get("status") == "offline" and self.sup.get(name, {}).get("state") in ALIVE:
                self.offline_since.setdefault(name, now)
            else:
                self.offline_since.pop(name, None)
        return stale

    def _problem(self, name, detail):
        self.problems.appendleft({"time": self.clock(), "runner": name, "detail": str(detail)[:300]})

    def _alive(self):
        """name -> state for every runner that is, or is about to be, up."""
        alive = {n: s.get("state") for n, s in self.sup.items() if s.get("state") in ALIVE}
        for n in self.pending:
            alive.setdefault(n, "starting")
        return alive

    # -- acting ------------------------------------------------------------

    def _reserve(self):
        """Count a new runner as starting before it exists (under the lock), so no other tick or click
        starts one past the max while it registers."""
        name = PREFIX + secrets.token_hex(3)
        self.created[name] = self.clock()
        self.pending.add(name)
        return name

    def _unreserve(self, names):
        with self.lock:
            for name in names:
                self.created.pop(name, None)
                self.pending.discard(name)

    def _start(self, names):
        """Register reserved runners and hand them to the supervisor. Forgejo and the spool; no lock held."""
        for i, name in enumerate(names):
            try:
                uuid, token = self.forgejo.register(name)
            except ForgejoError:
                self._unreserve(names[i:])
                raise
            try:
                self.spool.write_start(name, runner_config(uuid, token, self.cfg.labels, self.cfg.job_timeout))
            except OSError:
                self._unreserve(names[i:])
                self.forgejo.delete_runner(self._reg_id(name))
                raise

    def _reg_id(self, name):
        for r in self.forgejo.runners():
            if r.get("name") == name:
                return r["id"]
        return 0

    def _idle_oldest_first(self, min_age=0):
        now = self.clock()
        idle = [(s.get("since") or 0, n) for n, s in self.sup.items()
                if s.get("state") == "idle" and now - (s.get("since") or now) >= min_age]
        return [n for _, n in sorted(idle)]

    def _stop(self, name):
        self.spool.write_stop(name)
        # Counted as gone at once, so the next decision doesn't pick it again.
        self.sup[name] = dict(self.sup[name], state="stopping")

    def _autoscale(self):
        """Decide (under the lock): stop files are written now; returns the names reserved to start."""
        alive = self._alive()
        busy = sum(1 for s in alive.values() if s == "busy")
        ready = len(alive) - busy
        want_ready = self.min_idle + len(self.waiting)
        want_total = min(self.max, busy + want_ready)
        if len(alive) > self.max:  # the facilitator lowered the max: idle ones above it go now
            for name in self._idle_oldest_first()[:len(alive) - self.max]:
                self._stop(name)
            return []
        if len(alive) < want_total:
            if len(self.fail_times) >= FAIL_LIMIT:
                return []
            return [self._reserve() for _ in range(want_total - len(alive))]
        if ready > want_ready:
            for name in self._idle_oldest_first(self.cfg.idle_timeout)[:ready - want_ready]:
                self._stop(name)
        return []

    def tick(self):
        """Read, decide, act. Forgejo and the spool are called with no lock held; the lock covers only the
        decision and the snapshot swap, so the panel and /healthz never wait on a slow Forgejo."""
        try:
            seen = self._fetch()
            with self.lock:
                stale = self._refresh(seen)
            for reg_id in stale:
                self.forgejo.delete_runner(reg_id)
            with self.lock:
                start = self._autoscale() if self.mode == "auto" else []
            self._start(start)
            self.error = ""
            self.last_ok = self.clock()
        except ForgejoError as e:
            self.error = f"Forgejo: {e}"
        except OSError as e:
            self.error = f"spool: {e}"
        with self.lock:
            self._snapshot()

    def _room(self):
        """Make room for one more runner: at the max, + raises the max too (the facilitator's call), up to the
        ceiling. Returns a note for the message, or None if the ceiling is reached."""
        if len(self._alive()) < self.max:
            return ""
        if self.max >= self.ceiling:
            return None
        self.max += 1
        return f" (max raised to {self.max})"

    def scale(self, delta):
        """The panel's - / +. Returns (ok, message)."""
        with self.lock:
            if self.mode == "auto":
                note = ""
                if delta > 0:
                    note = self._room()
                    if note is None:
                        return False, f"Already at the most the pool allows ({self.ceiling})"
                self.min_idle = max(0, min(self.max, self.min_idle + delta))
                self.wake.set()
                self._snapshot()
                return True, f"Warm pool: {self.min_idle} idle{note}"
            if delta < 0:
                idle = self._idle_oldest_first()
                if not idle:
                    return False, "No idle runner to remove (a busy one is never removed)"
                self._stop(idle[0])
                self._snapshot()
                return True, f"Removing {idle[0]}"
            note = self._room()
            if note is None:
                return False, f"Already at the most the pool allows ({self.ceiling})"
            name = self._reserve()
            self._snapshot()  # shown as starting while it registers
        try:
            self._start([name])
        except ForgejoError as e:
            return False, f"Forgejo: {e}"
        with self.lock:
            self._snapshot()
        return True, f"Starting {name}{note}"

    def set_max(self, delta):
        """The panel's Max - / +: the facilitator's call on how many runners Auto may run at once."""
        with self.lock:
            new = max(1, min(self.ceiling, self.max + delta))
            if new == self.max:
                return False, (f"Max is already the most the pool allows ({self.ceiling})" if delta > 0
                               else "Max can't go below 1")
            self.max = new
            self.min_idle = min(self.min_idle, new)
            over = len(self._alive()) - new
            self.wake.set()
            self._snapshot()
        msg = f"Max: {new} runners"
        if over > 0:
            msg += (" (idle runners above it are being removed; busy ones finish their job first)" if self.mode == "auto"
                    else " (Manual removes nothing by itself: use − to remove idle runners)")
        return True, msg

    def set_mode(self, mode):
        with self.lock:
            self.mode = mode
            self.wake.set()
            self._snapshot()
        return True, f"Mode: {mode}"

    # -- what the panel shows ----------------------------------------------

    def _light(self, name, s):
        now = self.clock()
        state = s.get("state")
        if state == "failed":
            return "red", s.get("detail") or "failed"
        if state == "busy":
            if now - (s.get("since") or now) > self.cfg.job_timeout:
                return "red", "stuck: running one job for too long"
            return "yellow", "running a job"
        if name in self.offline_since and now - self.offline_since[name] > OFFLINE_AFTER:
            return "red", "Forgejo sees it offline"
        if state == "idle" and name not in self.regs and now - self.created.get(name, 0) > GRACE:
            return "red", "not registered in Forgejo"
        if state == "starting":
            return "green", "starting"
        if state == "stopping":
            return "green", "being removed"
        return "green", "ready for a job"

    def _snapshot(self):
        now = self.clock()
        rows = []
        for name, s in sorted(self.sup.items(), key=lambda kv: kv[1].get("started") or 0):
            state = s.get("state")
            if state in ("done", "removed") or (state == "failed" and now - (s.get("since") or 0) > 300):
                continue
            light, detail = self._light(name, s)
            rows.append({"name": name, "light": light, "state": state, "detail": detail,
                         "repo": s.get("repo") or "", "since": s.get("since")})
        for name in sorted(self.pending):
            rows.append({"name": name, "light": "green", "state": "starting", "detail": "starting",
                         "repo": "", "since": self.created.get(name)})
        alive = self._alive()
        waiting = [{"repo": self.repo_names.get(j.get("repo_id")) or f"repo {j.get('repo_id')}",
                    "job": str(j.get("name") or "")}
                   for j in self.waiting[:50]]
        self.snapshot = {
            "mode": self.mode, "min_idle": self.min_idle, "max": self.max, "ceiling": self.ceiling,
            "runners": rows, "alive": len(alive),
            "busy": sum(1 for s in alive.values() if s == "busy"),
            "waiting": waiting, "problems": list(self.problems)[:10],
            "paused": len(self.fail_times) >= FAIL_LIMIT,
            "error": self.error or ("Waiting for the shim's CA" if self.shim_ca == "waiting" else ""),
            "updated": now,
        }

    def reset_user(self, user):
        """Student reset teardown: stop every runner busy with a job of one of the student's own repos
        (their forks; the engine deletes the repos next, which drops their waiting jobs). A job they started
        in a shared repo runs on: nothing ties it to them but the push. Returns a short detail."""
        runners = (self.spool.read_state().get("runners") or {})
        mine = sorted(n for n, s in runners.items() if isinstance(s, dict) and s.get("state") == "busy"
                      and str(s.get("repo") or "").startswith(user + "/"))
        for name in mine:
            self.spool.write_kill(name)
        return f"stopped {len(mine)} runner(s) busy with their jobs"

    def healthy(self):
        return self.clock() - self.last_ok < 20

    def loop(self):
        while True:
            self.tick()
            self.wake.wait(TICK)
            self.wake.clear()


STATIC = {"/": ("panel.html", "text/html; charset=utf-8"),
          "/panel.js": ("panel.js", "text/javascript; charset=utf-8"),
          "/panel.css": ("panel.css", "text/css; charset=utf-8")}


def make_handler(ctl, static_dir=HERE):
    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "runner-controller"
        sys_version = ""

        def log_message(self, fmt, *args):  # quiet: the panel polls every few seconds
            pass

        def _send(self, status, body=b"", ctype="application/json"):
            dojo_http.send(self, status, body, ctype)

        def _json(self, status, doc):
            dojo_http.send_json(self, status, doc)

        def _facilitator(self):
            return dojo_http.is_facilitator(self.headers, ctl.cfg.gateway_token, ctl.cfg.facilitator)

        def _path(self):
            return self.path.split("?", 1)[0] or "/"

        def do_GET(self):
            path = self._path()
            if path == "/healthz":
                ok = ctl.healthy()
                self._json(200 if ok else 503, {"ok": ok, "error": ctl.error})
                return
            if not self._facilitator():
                self._json(403, {"error": "facilitator only"})
                return
            if path == "/api/state":
                self._json(200, ctl.snapshot)
                return
            if path in STATIC:
                fname, ctype = STATIC[path]
                with open(os.path.join(static_dir, fname), "rb") as f:
                    self._send(200, f.read(), ctype)
                return
            self._json(404, {"error": "not found"})

        do_HEAD = do_GET

        def _audit(self, action, result):
            # One JSON line per panel action (remediation T1.4, FIND-13).
            print(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                              "event": "runners", "account": self.headers.get("X-Auth-User"),
                              "action": action, "result": result}, separators=(",", ":")), flush=True)

        def _student_reset(self, path):
            given = self.headers.get("X-Dojo-Reset-Token", "")
            want = ctl.cfg.reset_token
            if not want or not hmac.compare_digest(given.encode(), want.encode()):
                self._json(403, {"error": "reset token required"})
                return
            user = urllib.parse.unquote(path[len("/_dojo/reset/"):])
            phase = urllib.parse.parse_qs(self.path.partition("?")[2]).get("phase", [""])[0]
            if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", user) or phase not in ("teardown", "provision"):
                self._json(404, {"error": "not found"})
                return
            detail = ctl.reset_user(user) if phase == "teardown" else "nothing to set up"
            self._audit(f"reset {user} {phase}", 200)
            self._json(200, {"ok": True, "detail": detail})

        def do_POST(self):
            path = self._path()
            if path.startswith("/_dojo/reset/"):
                self._student_reset(path)
                return
            if not self._facilitator():
                self._audit(path, 403)
                self._json(403, {"error": "facilitator only"})
                return
            if self.headers.get("X-Requested-With") != "dojo-runners":
                self._json(403, {"error": "missing X-Requested-With"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length > 1024:
                    raise ValueError
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError
            except ValueError:
                self._json(400, {"error": "bad request"})
                return
            if path == "/api/scale" and body.get("delta") in (1, -1):
                ok, msg = ctl.scale(body["delta"])
            elif path == "/api/max" and body.get("delta") in (1, -1):
                ok, msg = ctl.set_max(body["delta"])
            elif path == "/api/mode" and body.get("mode") in ("auto", "manual"):
                ok, msg = ctl.set_mode(body["mode"])
            else:
                self._json(400, {"error": "bad request"})
                return
            self._audit(f"{path} {body.get('delta', body.get('mode'))}", 200 if ok else 409)
            self._json(200 if ok else 409, {"ok": ok, "message": msg, "state": ctl.snapshot})

    return Handler


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    # As PID 1, Python ignores SIGTERM unless it has a handler.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    cfg = Config()
    ctl = Controller(cfg, Forgejo(cfg.forgejo_url, cfg.forgejo_user, cfg.forgejo_password,
                                     token_file=cfg.forgejo_token_file), Spool(cfg.spool))
    threading.Thread(target=ctl.loop, daemon=True).start()
    print(f"[runner-controller] min idle {cfg.min_idle}, max {cfg.max}, labels {cfg.labels}", flush=True)
    Server(("0.0.0.0", 8080), make_handler(ctl)).serve_forever()


if __name__ == "__main__":
    main()
