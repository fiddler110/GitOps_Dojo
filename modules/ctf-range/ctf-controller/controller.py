"""ctf-controller — the single, unprivileged client of the boxed ctf-host dind
(decision CTF-D21, spike S14). It is the only thing in the range that can start
or replace a target slot, and students can never reach it (it sits on the
internal `ctf_ops` network).

Two jobs:

  * Reconcile (CTF-5 model, §4 "Exception: CTF-5"): keep one always-on
    customer-portal slot running per student, created from the base image, each
    seeded for that student and handed that student's flag value (§5). A slot
    already running a patched image is left alone — reconcile never rolls a fix
    back.

  * Redeploy in place (the live tail of the S6 loop that defend-main.yml
    calls): on merge to main the pipeline pushes the student's rebuilt image to
    the in-lab registry and POSTs here; the controller pulls that tag and
    recreates the slot UNDER THE SAME NAME AND ADDRESS, so the attacker bot's
    next probe hits the patched app without anything being redirected. The
    wall-of-shame entry then flips LIVE → DISCONNECTED (§8.12).

The controller never builds an image and never sees a Dockerfile; its whole
reach into ctf-host is docker_api.Executor (pull / create / start / stop / rm).
"""
import hmac
import http.server
import json
import os
import re
import signal
import socketserver
import sys
import threading
import time

import docker_api
import flags

TICK = 10          # reconcile loop period, seconds
# Per-slot published port inside ctf-host: BASE + index. Overridable
# (CTF_HOST_PORT_BASE) because the web-terminal firewall hook
# (modules/ctf-range/terminal/start.d/50-ctf-range.sh) computes the same
# address from the same roster/index and must agree with this value - see
# that hook's header comment.
HOST_PORT_BASE = 15000


def _mem_bytes(text, default=128 * 1024 ** 2):
    """Parse a compose-style size ('128m', '1g', '536870912') to bytes."""
    m = re.fullmatch(r"\s*(\d+)\s*([kmg]?)\s*", (text or "").lower())
    if not m:
        return default
    n = int(m.group(1))
    return n * {"": 1, "k": 1024, "m": 1024 ** 2, "g": 1024 ** 3}[m.group(2)]


def roster(env):
    """The students who get an always-on slot. Matches the engine's padding
    exactly (allocator STUDENT_IDS, `{n:02d}`), as cloud-api's roster() does."""
    prefix = env.get("STUDENT_PREFIX", "student")
    try:
        count = int(env.get("STUDENT_COUNT", "0") or 0)
    except ValueError:
        count = 0
    return [f"{prefix}{n:02d}" for n in range(1, count + 1)]


class Config:
    def __init__(self, env=os.environ):
        self.socket = env.get("CTF_SOCKET", "/run/ctf/docker.sock")
        self.control_token = env.get("CTF_CONTROL_TOKEN", "")
        self.registry = env.get("CTF_REGISTRY", "").rstrip("/")
        self.base_image = env.get("CTF_BASE_IMAGE", "ctf-customer-portal:base")
        self.container_port = int(env.get("CTF_TARGET_PORT", "5000"))
        self.mem_bytes = _mem_bytes(env.get("CTF_TARGET_MEM_LIMIT", "128m"))
        self.pids = int(env.get("CTF_TARGET_PIDS_LIMIT", "256"))
        self.seed = env.get("STUDENT_PASSWORD_SEED", "")
        self.host_port_base = int(env.get("CTF_HOST_PORT_BASE", "") or HOST_PORT_BASE)
        self.users = roster(env)
        # Stable per-user index → container name and published port, so a
        # recreate keeps the same address (§4 "Stable slot address").
        self.index = {u: i for i, u in enumerate(self.users)}

    def slot_name(self, user):
        return f"ctf-{flags.CHALLENGE}-{user}"

    def host_port(self, user):
        return self.host_port_base + self.index.get(user, 0)


class Controller:
    def __init__(self, cfg, executor, clock=time.time):
        self.cfg = cfg
        self.ex = executor
        self.clock = clock
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.last_ok = 0
        self.error = ""
        self.snapshot = {"ready": False, "slots": [], "error": "starting", "updated": 0}

    # -- slot operations ---------------------------------------------------

    def _env_for(self, user):
        return [
            ("CTF_STUDENT", user),
            ("CTF_FLAG", flags.render(user, self.cfg.seed)),
            ("PORT", str(self.cfg.container_port)),
        ]

    def _create_slot(self, user, image):
        """Create (replacing any existing) one slot for `user` from `image`."""
        name = self.cfg.slot_name(user)
        self.ex.remove(name)
        self.ex.create(
            name=name,
            image=image,
            env_pairs=self._env_for(user),
            container_port=self.cfg.container_port,
            host_port=self.cfg.host_port(user),
            memory_bytes=self.cfg.mem_bytes,
            pids_limit=self.cfg.pids,
            labels={docker_api.LABEL_SLOT: user, docker_api.LABEL_USER: user},
        )

    def redeploy(self, user, image=None):
        """The S6 live tail. Pull (if a registry tag) and recreate the user's
        slot in place from `image` (default: the base image). Returns (ok, msg)."""
        if user not in self.cfg.index:
            return False, f"unknown slot {user!r}"
        image = image or self.cfg.base_image
        with self.lock:
            try:
                if image != self.cfg.base_image:
                    # A registry tag: pull it first (base is already imported).
                    self.ex.pull(image)
                elif not self.ex.image_present(image):
                    return False, f"base image {image!r} not present on ctf-host"
                self._create_slot(user, image)
            except docker_api.DockerError as exc:
                return False, str(exc)
        return True, f"redeployed {self.cfg.slot_name(user)} <- {image}"

    def reconcile(self):
        """Ensure every student has a running slot. A slot already running a
        (patched) image is left as-is — reconcile never downgrades a fix."""
        try:
            present = set(self.ex.list_managed())
        except docker_api.DockerError as exc:
            self.error = str(exc)
            return
        for user in self.cfg.users:
            name = self.cfg.slot_name(user)
            try:
                state = self.ex.state(name) if name in present else None
                if state is None:
                    self._create_slot(user, self.cfg.base_image)
                elif state != "running":
                    # Recreate from whatever image it already carries, so a
                    # patched slot that stopped comes back patched.
                    self._create_slot(user, self.ex.image_of(name) or self.cfg.base_image)
            except docker_api.DockerError as exc:
                self.error = f"{name}: {exc}"

    # -- state for callers / readiness -------------------------------------

    def ready(self):
        return self.ex.ping() and self.error == ""

    def healthy(self):
        return self.clock() - self.last_ok < 3 * TICK

    def _snapshot(self):
        rows = []
        try:
            for user in self.cfg.users:
                name = self.cfg.slot_name(user)
                rows.append({
                    "user": user, "name": name,
                    "state": self.ex.state(name) or "absent",
                    "image": self.ex.image_of(name) or "",
                    "port": self.cfg.host_port(user),
                })
        except docker_api.DockerError as exc:
            self.error = str(exc)
        with self.lock:
            self.snapshot = {
                "ready": self.ex.ping(),
                "slots": rows,
                "error": self.error,
                "updated": int(self.clock()),
            }

    def tick(self):
        if self.ex.ping():
            self.error = ""
            self.reconcile()
            self.last_ok = self.clock()
        else:
            self.error = "ctf-host unreachable"
        self._snapshot()

    def loop(self):
        while True:
            self.tick()
            self.wake.wait(TICK)
            self.wake.clear()


# -- HTTP control API ------------------------------------------------------
# Reachable only by the allocator / the defend pipeline on ctf_ops. Mutating
# routes need the control token; /healthz is open for compose's healthcheck.

def make_handler(ctl):
    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "ctf-controller"
        sys_version = ""

        def log_message(self, fmt, *args):  # quiet
            pass

        def _json(self, status, doc):
            body = json.dumps(doc).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _authed(self):
            want = ctl.cfg.control_token
            if not want:
                return False  # fail closed: no token configured = no access
            given = self.headers.get("Authorization", "")
            if given.startswith("Bearer "):
                given = given[len("Bearer "):]
            return hmac.compare_digest(given.encode(), want.encode())

        def _path(self):
            return self.path.split("?", 1)[0] or "/"

        def do_GET(self):
            path = self._path()
            if path == "/healthz":
                self._json(200 if ctl.healthy() else 503,
                           {"ok": ctl.healthy(), "ready": ctl.ready(), "error": ctl.error})
                return
            if not self._authed():
                self._json(403, {"error": "control token required"})
                return
            if path == "/slots":
                self._json(200, ctl.snapshot)
                return
            self._json(404, {"error": "not found"})

        do_HEAD = do_GET

        def _audit(self, action, result):
            print(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                              "event": "ctf-controller", "action": action, "result": result},
                             separators=(",", ":")), flush=True)

        def do_POST(self):
            path = self._path()
            if not self._authed():
                self._json(403, {"error": "control token required"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length > 2048:
                    raise ValueError
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError
            except ValueError:
                self._json(400, {"error": "bad request"})
                return
            if path == "/redeploy":
                user = str(body.get("user") or "")
                image = body.get("image")
                if image is not None and not isinstance(image, str):
                    self._json(400, {"error": "bad image"})
                    return
                ok, msg = ctl.redeploy(user, image)
                self._audit(f"redeploy {user} {image or '(base)'}", "ok" if ok else msg)
                self._json(200 if ok else 409, {"ok": ok, "message": msg})
                return
            if path == "/reconcile":
                ctl.wake.set()
                self._json(200, {"ok": True, "message": "reconcile scheduled"})
                return
            self._json(404, {"error": "not found"})

    return Handler


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    cfg = Config()
    ex = docker_api.Executor(cfg.socket, registry_prefix=cfg.registry)
    ctl = Controller(cfg, ex)
    threading.Thread(target=ctl.loop, daemon=True).start()
    print(f"[ctf-controller] {len(cfg.users)} slot(s), base {cfg.base_image}, "
          f"registry {cfg.registry or '(none)'}", flush=True)
    Server(("0.0.0.0", 9000), make_handler(ctl)).serve_forever()


if __name__ == "__main__":
    main()
