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
import secrets
import signal
import socketserver
import sys
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
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
        for d in (root, self.start_dir, self.stop_dir):
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
        self.lock = threading.RLock()
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
        self.snapshot = {}

    # -- reading the world -------------------------------------------------

    def _refresh(self):
        now = self.clock()
        state = self.spool.read_state()
        sup = state.get("runners") if isinstance(state.get("runners"), dict) else {}
        self.sup = {n: s for n, s in sup.items() if isinstance(s, dict) and n.startswith(PREFIX)}
        self.shim_ca = state.get("shim_ca", "")
        self.regs = {r["name"]: r for r in self.forgejo.runners()
                     if isinstance(r, dict) and str(r.get("name", "")).startswith(PREFIX)}
        self.waiting = self.forgejo.waiting_jobs(self.cfg.labels)
        pending = self.spool.pending()
        # Registrations whose runner is gone. One the supervisor hasn't picked
        # up yet (still pending, or just made) is left alone.
        for name, reg in list(self.regs.items()):
            s = self.sup.get(name)
            if s is None:
                gone = name not in pending and now - self.created.get(name, 0) > GRACE
            else:
                gone = s.get("state") in FINISHED
            if gone:
                self.forgejo.delete_runner(reg["id"])
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

    def _problem(self, name, detail):
        self.problems.appendleft({"time": self.clock(), "runner": name, "detail": str(detail)[:300]})

    def _alive(self):
        """name -> state for every runner that is, or is about to be, up."""
        alive = {n: s.get("state") for n, s in self.sup.items() if s.get("state") in ALIVE}
        for n in self.pending:
            alive.setdefault(n, "starting")
        return alive

    # -- acting ------------------------------------------------------------

    def _start_one(self):
        name = PREFIX + secrets.token_hex(3)
        uuid, token = self.forgejo.register(name)
        self.created[name] = self.clock()
        try:
            self.spool.write_start(name, runner_config(uuid, token, self.cfg.labels, self.cfg.job_timeout))
        except OSError:
            self.forgejo.delete_runner(self._reg_id(name))
            raise
        self.pending.add(name)
        return name

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
        alive = self._alive()
        busy = sum(1 for s in alive.values() if s == "busy")
        ready = len(alive) - busy
        want_ready = self.min_idle + len(self.waiting)
        want_total = min(self.cfg.max, busy + want_ready)
        if len(alive) < want_total:
            if len(self.fail_times) >= FAIL_LIMIT:
                return
            for _ in range(want_total - len(alive)):
                self._start_one()
        elif ready > want_ready:
            for name in self._idle_oldest_first(self.cfg.idle_timeout)[:ready - want_ready]:
                self._stop(name)

    def tick(self):
        with self.lock:
            try:
                self._refresh()
                if self.mode == "auto":
                    self._autoscale()
                self.error = ""
                self.last_ok = self.clock()
            except ForgejoError as e:
                self.error = f"Forgejo: {e}"
            except OSError as e:
                self.error = f"spool: {e}"
            self._snapshot()

    def scale(self, delta):
        """The panel's - / +. Returns (ok, message)."""
        with self.lock:
            if self.mode == "auto":
                self.min_idle = max(0, min(self.cfg.max, self.min_idle + delta))
                self.wake.set()
                self._snapshot()
                return True, f"Warm pool: {self.min_idle} idle"
            try:
                if delta > 0:
                    if len(self._alive()) >= self.cfg.max:
                        return False, f"Already at the max ({self.cfg.max})"
                    name = self._start_one()
                    msg = f"Starting {name}"
                else:
                    idle = self._idle_oldest_first()
                    if not idle:
                        return False, "No idle runner to remove (a busy one is never removed)"
                    self._stop(idle[0])
                    msg = f"Removing {idle[0]}"
            except ForgejoError as e:
                return False, f"Forgejo: {e}"
            self._snapshot()
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
        waiting = [{"repo": self.forgejo.repo_name(j.get("repo_id")), "job": str(j.get("name") or "")}
                   for j in self.waiting[:50]]
        self.snapshot = {
            "mode": self.mode, "min_idle": self.min_idle, "max": self.cfg.max,
            "runners": rows, "alive": len(alive),
            "busy": sum(1 for s in alive.values() if s == "busy"),
            "waiting": waiting, "problems": list(self.problems)[:10],
            "paused": len(self.fail_times) >= FAIL_LIMIT,
            "error": self.error or ("Waiting for the shim's CA" if self.shim_ca == "waiting" else ""),
            "updated": now,
        }

    def healthy(self):
        return self.clock() - self.last_ok < 20

    def loop(self):
        while True:
            self.tick()
            self.wake.wait(TICK)
            self.wake.clear()


SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
                               "img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'",
    "X-Frame-Options": "SAMEORIGIN",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}
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
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in SECURITY_HEADERS.items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status, doc):
            self._send(status, json.dumps(doc).encode())

        def _facilitator(self):
            token = ctl.cfg.gateway_token
            given = self.headers.get("X-Gateway-Token") or ""
            if not token or not hmac.compare_digest(given.encode(), token.encode()):
                return False
            return self.headers.get("X-Auth-User") == ctl.cfg.facilitator

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
                with ctl.lock:
                    doc = ctl.snapshot
                self._json(200, doc)
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

        def do_POST(self):
            path = self._path()
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
            elif path == "/api/mode" and body.get("mode") in ("auto", "manual"):
                ok, msg = ctl.set_mode(body["mode"])
            else:
                self._json(400, {"error": "bad request"})
                return
            self._audit(f"{path} {body.get('delta', body.get('mode'))}", 200 if ok else 409)
            with ctl.lock:
                doc = ctl.snapshot
            self._json(200 if ok else 409, {"ok": ok, "message": msg, "state": doc})

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
