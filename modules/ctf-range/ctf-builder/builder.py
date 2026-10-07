"""ctf-builder — the ONLY thing allowed to ask ctf-host to build (spike S6).

Reachable only from the Forgejo runner pool's network (`runner_net`), never
from `ctf_ops` where ctf-controller and ctf-host live — see compose.yml and
README.md's "Why a separate service, and runner_net only" for the choice.
Narrow by design, the same way docker_api.py / controller.py narrow
ctf-controller, just along a different axis:

  * It builds exactly ONE thing per call: the student's OWN repo, at a ref
    the caller names, cloned by ctf-builder ITSELF from git-server — never a
    build context, tarball or Dockerfile the caller hands it directly.
  * It can tag and push exactly ONE name per call: the slot's own name under
    the approved registry prefix (docker_build.image_tag_for) — never a name
    the caller chooses.
  * It never creates, starts, stops or removes a container. That whole
    capability belongs to ctf-controller alone; ctf-builder shares ctf-host's
    socket only for POST /build and POST /images/*/push.

A compromised build (a malicious Dockerfile in the student's own repo — low
stakes, it is their own target) can do damage only inside that one image
build, which runs inside the already-boxed, privileged ctf-host dind
(CTF-D21) with no route out of `ctf_ops`/`ctf_net`. It can never reach another
student's repo (the repo path is derived from a validated `user`, never taken
from the caller) and ctf-builder itself never sees a Dockerfile or tar from
the caller at all.
"""
import hmac
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import tarfile
import tempfile
import threading
import time
from io import BytesIO

import docker_build
import gitref

MAX_BODY = 1024          # the request is just {"user": "...", "ref": "..."}
CLONE_TIMEOUT = 60
BUILD_TIMEOUT = 180
PUSH_TIMEOUT = 120


class Config:
    def __init__(self, env=os.environ):
        self.socket = env.get("CTF_SOCKET", "/run/ctf/docker.sock")
        # Deliberately its OWN token, not ctf-controller's CTF_CONTROL_TOKEN:
        # a leaked build-trigger credential should never also grant
        # /redeploy, and vice versa (narrower blast radius per service).
        self.control_token = env.get("CTF_BUILD_TOKEN", "")
        self.registry = env.get("CTF_REGISTRY", "").rstrip("/")
        self.git_server = env.get("CTF_GIT_SERVER", "git-server:3000")
        self.repo_name = env.get("CTF_REPO_NAME", "customer-portal")
        self.image = env.get("CTF_IMAGE", docker_build.IMAGE_NAME)


def _audit(action, result):
    print(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                      "event": "ctf-builder", "action": action, "result": result},
                     separators=(",", ":")), flush=True)


def _tar_bytes(src_dir):
    """Tar the clone ctf-builder just made (minus .git) as the build
    context. In memory: target repos are one small Flask app."""
    buf = BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name in sorted(os.listdir(src_dir)):
            if name == ".git":
                continue
            tf.add(os.path.join(src_dir, name), arcname=name)
    return buf.getvalue()


def do_build(cfg, ex, user, ref):
    """Clone `user`'s own repo at `ref`, tar it, build+push under the slot's
    own tag. Returns (ok, tag_or_error). Validation happens here, before any
    subprocess or daemon call, so a bad request never touches git or
    ctf-host."""
    if not cfg.registry:
        return False, "registry not configured"
    if not gitref.safe_user(user):
        return False, "bad user"
    if not gitref.safe_ref(ref):
        return False, "bad ref"
    repo_url = gitref.repo_url_for(user, cfg.git_server, cfg.repo_name)
    workdir = tempfile.mkdtemp(prefix="ctf-build-")
    try:
        dest = os.path.join(workdir, "repo")
        subprocess.run(gitref.clone_argv(repo_url, dest), check=True,
                       timeout=CLONE_TIMEOUT, capture_output=True)
        subprocess.run(gitref.checkout_argv(dest, ref), check=True,
                       timeout=CLONE_TIMEOUT, capture_output=True)
        tag = docker_build.image_tag_for(user, cfg.registry, cfg.image)
        tar_bytes = _tar_bytes(dest)
        ex.build(tar_bytes, tag, timeout=BUILD_TIMEOUT)
        ex.push(user, cfg.registry, cfg.image, timeout=PUSH_TIMEOUT)
        return True, tag
    except subprocess.TimeoutExpired:
        return False, "git clone/checkout timed out"
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or b"")[:200]
        return False, f"git failed: {detail!r}"
    except docker_build.DockerError as exc:
        return False, str(exc)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def make_handler(cfg, ex, build_lock):
    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "ctf-builder"
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
            want = cfg.control_token
            if not want:
                return False  # fail closed: no token configured = no access
            given = self.headers.get("Authorization", "")
            if given.startswith("Bearer "):
                given = given[len("Bearer "):]
            return hmac.compare_digest(given.encode(), want.encode())

        def _path(self):
            return self.path.split("?", 1)[0] or "/"

        def do_GET(self):
            if self._path() == "/healthz":
                ok = ex.ping()
                self._json(200 if ok else 503, {"ok": ok})
                return
            self._json(404, {"error": "not found"})

        do_HEAD = do_GET

        def do_POST(self):
            if self._path() != "/build":
                self._json(404, {"error": "not found"})
                return
            if not self._authed():
                self._json(403, {"error": "control token required"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length <= 0 or length > MAX_BODY:
                    raise ValueError
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError
            except ValueError:
                self._json(400, {"error": "bad request"})
                return
            user = str(body.get("user") or "")
            ref = str(body.get("ref") or "")
            with build_lock:  # one build at a time against the shared dind
                ok, msg = do_build(cfg, ex, user, ref)
            _audit(f"build {user} {ref}", msg if ok else msg)
            doc = {"ok": ok}
            doc["tag" if ok else "error"] = msg
            self._json(200 if ok else 400, doc)

    return Handler


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    cfg = Config()
    ex = docker_build.Executor(cfg.socket)
    build_lock = threading.Lock()
    print(f"[ctf-builder] registry {cfg.registry or '(none)'}, "
          f"git-server {cfg.git_server}", flush=True)
    Server(("0.0.0.0", 9100), make_handler(cfg, ex, build_lock)).serve_forever()


if __name__ == "__main__":
    main()
