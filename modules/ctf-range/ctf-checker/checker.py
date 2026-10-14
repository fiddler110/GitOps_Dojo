"""ctf-checker: runs a target's check.py and returns a verdict.

  POST /check  {"user": "student01"}  -> {"results": [{target, verdict, note, at}]}
      Student-facing (via `dojo-check`). Identity is the caller's $USER, as for
      dojo-flag; the worst a spoofed name does is check someone else's slot,
      which only reveals a verdict word. One run per user per RATE_S seconds.
  POST /gate   Bearer CTF_BUILD_TOKEN, {"user","target","ref"}
      Clones the student's repo at ref itself, runs the candidate app.py
      locally (seed files from the image, only app.py comes from the repo),
      runs check.py and returns {verdict, note, pass}.

check.py interface: `check.py --url URL [--expect-flag F] [--legit-key K]`
prints {"verdict","note"}; exit 0 exploitable, 1 contained, 3 broke-normal-use,
2 unreachable.
"""
import hmac
import http.server
import json
import os
import shutil
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
import time

import gitref

MAX_BODY = 1024
RATE_S = 3.0
CHECK_TIMEOUT = 40
CLONE_TIMEOUT = 60
VERDICTS = ("exploitable", "contained", "broke-normal-use", "unreachable")
EXIT_VERDICT = {0: "exploitable", 1: "contained", 3: "broke-normal-use", 2: "unreachable"}
TARGETS_DIR = os.environ.get("CTF_TARGETS_DIR", "/targets")
GATE_METRICS_PASS = "gate-metrics-pass"
DEFAULT_TARGETS = "customer-portal policy-bypass leaky-config"


def roster(env):
    prefix = env.get("STUDENT_PREFIX", "student")
    try:
        count = int(env.get("STUDENT_COUNT", "0") or 0)
    except ValueError:
        count = 0
    return [f"{prefix}{n:02d}" for n in range(1, count + 1)]


class Config:
    def __init__(self, env=os.environ):
        self.targets = (env.get("CTF_DEFEND_TARGETS") or DEFAULT_TARGETS).split()
        self.stride = int(env.get("CTF_PORT_STRIDE", "") or 100)
        self.host = env.get("CTF_HOST", "ctf-host")
        self.port_base = int(env.get("CTF_HOST_PORT_BASE", "") or 15000)
        self.users = roster(env)
        self.index = {u: i for i, u in enumerate(self.users)}
        self.build_token = env.get("CTF_BUILD_TOKEN", "")
        self.seed = env.get("STUDENT_PASSWORD_SEED", "")
        self.git_server = env.get("CTF_GIT_SERVER", "git-server:3000")

    def slot_port(self, user, target):
        return (self.port_base + self.targets.index(target) * self.stride
                + self.index[user])


def parse_check_output(stdout, rc):
    """Map a check.py run to (verdict, note). The exit code is authoritative;
    the JSON verdict is only used if it agrees or the code is unknown."""
    note = ""
    doc_verdict = None
    for line in reversed((stdout or "").strip().splitlines()):
        try:
            doc = json.loads(line)
        except ValueError:
            continue
        if isinstance(doc, dict):
            doc_verdict = doc.get("verdict")
            note = str(doc.get("note") or "")[:200]
            break
    verdict = EXIT_VERDICT.get(rc)
    if verdict is None:
        verdict = doc_verdict if doc_verdict in VERDICTS else "unreachable"
        if not note:
            note = "the check did not finish cleanly"
    return verdict, note


class RateLimiter:
    def __init__(self, interval=RATE_S, clock=time.monotonic):
        self.interval, self.clock, self.last, self.lock = interval, clock, {}, threading.Lock()

    def allow(self, key):
        now = self.clock()
        with self.lock:
            prev = self.last.get(key)
            if prev is not None and now - prev < self.interval:
                return False
            self.last[key] = now
            return True


def validate_check(body, cfg):
    """-> (user, error). Roster membership is required so a made-up name
    cannot probe arbitrary ports."""
    user = str((body or {}).get("user") or "")
    if not gitref.safe_user(user):
        return None, "bad user"
    if cfg.users and user not in cfg.index:
        return None, "unknown user"
    if not cfg.users:
        return None, "no roster configured"
    return user, None


def validate_gate(body, cfg):
    """-> ((user, target, ref), error)."""
    body = body or {}
    user, err = validate_check(body, cfg)
    if err:
        return None, err
    target = str(body.get("target") or "")
    if target not in cfg.targets or os.sep in target:
        return None, "unknown target"
    ref = str(body.get("ref") or "")
    if not gitref.safe_ref(ref):
        return None, "bad ref"
    return (user, target, ref), None


def script_path(target, targets_dir=TARGETS_DIR):
    return os.path.join(targets_dir, target, "exploit", "check.py")


def run_check(target, url, expect_flag="", legit_key="", targets_dir=TARGETS_DIR, runner=subprocess.run):
    argv = [sys.executable, script_path(target, targets_dir), "--url", url]
    if expect_flag:
        argv += ["--expect-flag", expect_flag]
    if legit_key:
        argv += ["--legit-key", legit_key]
    try:
        p = runner(argv, capture_output=True, text=True, timeout=CHECK_TIMEOUT)
    except (subprocess.TimeoutExpired, OSError):
        return "unreachable", "the check timed out"
    return parse_check_output(p.stdout, p.returncode)


def _derive(cfg, user, challenge):
    try:
        import flags
        return flags.render(user, cfg.seed, challenge=challenge)
    except Exception:
        return ""


def secteam_key(cfg, user, target):
    return _derive(cfg, user, f"{target}-secteam")


def proxy_token(cfg, user, target):
    return _derive(cfg, user, f"{target}-proxy")


def legit_key_for(cfg, user, target, local=False):
    """--legit-key per target. leaky-config's metrics password is derived per
    user (the controller sets the slot's CTF_METRICS_PASS the same way); the
    local gate run uses a fixed value the checker sets itself."""
    if target == "policy-bypass":
        return secteam_key(cfg, user, target)
    if target == "leaky-config":
        return "metrics-agent:" + (GATE_METRICS_PASS if local
                                   else _derive(cfg, user, "leaky-config-metrics"))
    return ""


def _flag_for(cfg, user, target):
    """The slot's flag is derived exactly as the controller does; flags.py is
    optional here (check scripts only use it as a hint)."""
    try:
        import flags  # noqa: shipped beside the controller, not required
        return flags.render(user, cfg.seed, challenge=target)
    except Exception:
        return ""


def check_all(cfg, user, only=None, runner=subprocess.run):
    out = []
    for t in cfg.targets:
        if only and t != only:
            continue
        url = f"http://{cfg.host}:{cfg.slot_port(user, t)}"
        v, n = run_check(t, url, _flag_for(cfg, user, t),
                         legit_key_for(cfg, user, t), runner=runner)
        out.append({"target": t, "verdict": v, "note": n,
                    "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    return out


def _free_wait(port, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def do_gate(cfg, user, target, ref, runner=subprocess.run):
    """Clone, run the candidate app locally, check. Callers hold gate_lock
    (fixed local ports 5000/5001)."""
    work = tempfile.mkdtemp(prefix="gate-")
    procs = []
    try:
        clone = os.path.join(work, "clone")
        url = gitref.repo_url_for(user, cfg.git_server, target)
        try:
            for argv in (gitref.clone_argv(url, clone), gitref.checkout_argv(clone, ref)):
                r = runner(argv, capture_output=True, text=True, timeout=CLONE_TIMEOUT)
                if r.returncode != 0:
                    return {"verdict": "unreachable", "note": "could not fetch that commit", "pass": False}
        except (subprocess.TimeoutExpired, OSError):
            return {"verdict": "unreachable", "note": "could not fetch that commit", "pass": False}
        cand = os.path.join(clone, "app.py")
        if not os.path.isfile(cand):
            return {"verdict": "broke-normal-use", "note": "the repo has no app.py", "pass": False}
        app = os.path.join(work, "app")
        shutil.copytree(os.path.join(TARGETS_DIR, target), app,
                        ignore=shutil.ignore_patterns("exploit", "sast", "__pycache__"))
        shutil.copy(cand, os.path.join(app, "app.py"))
        # Student-edited requirements are never installed; the image's Flask is used.
        flag = _flag_for(cfg, user, target) or "flag{gate-local}"
        env = {"PATH": os.environ.get("PATH", ""), "HOME": work, "CTF_FLAG": flag,
               "CTF_STUDENT": user, "CTF_DB_PATH": os.path.join(work, "portal.db"),
               "CTF_SECTEAM_KEY": secteam_key(cfg, user, target),
               "CTF_PROXY_TOKEN": proxy_token(cfg, user, target),
               "PYTHONDONTWRITEBYTECODE": "1", "CTF_DEFEND_PROXY": "1" if target == "policy-bypass" else "0",
               "CTF_METRICS_PASS": GATE_METRICS_PASS}
        seed = os.path.join(app, "seed.py")
        if os.path.isfile(seed):
            subprocess.run([sys.executable, seed], cwd=app, env=env, timeout=30,
                           capture_output=True)
        proxy = os.path.join(app, "proxy.py")
        has_proxy = os.path.isfile(proxy)
        procs.append(subprocess.Popen([sys.executable, os.path.join(app, "app.py")], cwd=app,
                                      env=dict(env, PORT="5001" if has_proxy else "5000"),
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        if has_proxy:
            procs.append(subprocess.Popen([sys.executable, proxy], cwd=app,
                                          env=dict(env, PORT="5000"),
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        if not _free_wait(5000) or (has_proxy and not _free_wait(5001)):
            return {"verdict": "broke-normal-use", "note": "the app did not start", "pass": False}
        v, n = run_check(target, "http://127.0.0.1:5000", flag,
                         legit_key_for(cfg, user, target, local=True), runner=runner)
        return {"verdict": v, "note": n, "pass": v == "contained"}
    finally:
        for p in procs:
            p.kill()
            try:
                p.wait(timeout=3)
            except Exception:
                pass
        shutil.rmtree(work, ignore_errors=True)


def _audit(action, result):
    print(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                      "event": "ctf-checker", "action": action, "result": result},
                     separators=(",", ":")), flush=True)


def make_handler(cfg, limiter, gate_lock):
    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "ctf-checker"

        def log_message(self, *a):
            pass

        def _json(self, code, doc):
            body = json.dumps(doc).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _body(self):
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0 or n > MAX_BODY:
                    return None
                doc = json.loads(self.rfile.read(n))
                return doc if isinstance(doc, dict) else None
            except ValueError:
                return None

        def _authed(self):
            want = cfg.build_token
            if not want:
                return False
            given = self.headers.get("Authorization", "")
            if given.startswith("Bearer "):
                given = given[7:]
            return hmac.compare_digest(given.encode(), want.encode())

        def do_GET(self):
            if self.path.split("?", 1)[0] == "/healthz":
                self._json(200, {"ok": True})
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            path = self.path.split("?", 1)[0]
            if path not in ("/check", "/gate"):
                return self._json(404, {"error": "not found"})
            if path == "/gate" and not self._authed():
                return self._json(403, {"error": "build token required"})
            body = self._body()
            if body is None:
                return self._json(400, {"error": "bad request"})
            if path == "/check":
                user, err = validate_check(body, cfg)
                if err:
                    return self._json(400, {"error": err})
                if not limiter.allow(user):
                    return self._json(429, {"error": "slow down: one check every few seconds"})
                only = body.get("target")
                if only is not None and only not in cfg.targets:
                    return self._json(400, {"error": "unknown target"})
                return self._json(200, {"results": check_all(cfg, user, only)})
            parsed, err = validate_gate(body, cfg)
            if err:
                return self._json(400, {"error": err})
            with gate_lock:
                res = do_gate(cfg, *parsed)
            _audit(f"gate {parsed[0]} {parsed[1]} {parsed[2]}", res["verdict"])
            self._json(200, res)

    return Handler


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    cfg = Config()
    print(f"[ctf-checker] targets {cfg.targets}, {len(cfg.users)} users", flush=True)
    Server(("0.0.0.0", 9200), make_handler(cfg, RateLimiter(), threading.Lock())).serve_forever()


if __name__ == "__main__":
    main()
