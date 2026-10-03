#!/usr/bin/env python3
"""openbao-reset: the student-reset hook for OpenBao (docs/archive/STUDENT-RESET-PLAN.md
R9, §4.4), a relay with no vault token of its own.

The allocator POSTs /_dojo/reset/<user>?phase=teardown|provision with
X-Dojo-Reset-Token. The work itself needs the bao CLI, the workshop's
openbao-setup.d hooks and the narrow reset token, which all live in
openbao-setup (setup/setup.sh mints the token into that container's tmpfs and
never writes it to disk). So this service queues the job, and openbao-setup's
reset worker long-polls GET /_dojo/work, runs the hooks for that one user with
the reset token, and posts the result to /_dojo/work/<id>; the hook call
answers with it. The reset token never crosses the network.

Both sides prove themselves with RESET_TOKEN (RESET_TOKEN_OPENBAO_RESET, the
allocator's token for this service): the hook so no student can wipe another,
the worker so no student can take a job and answer it. Empty RESET_TOKEN:
everything is refused. Stdlib only, on the allocator image.
"""
import collections
import hmac
import http.server
import json
import os
import re
import secrets
import sys
import threading
import time
import urllib.parse

RESET_TOKEN = os.environ.get("RESET_TOKEN", "")
# How long a hook call waits for the worker; under the manifest's timeout, so
# the allocator gets this service's answer rather than its own timeout.
JOB_TIMEOUT = float(os.environ.get("RESET_JOB_TIMEOUT") or 110)
POLL_WAIT = float(os.environ.get("RESET_POLL_WAIT") or 25)
USER_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}")
PHASES = ("teardown", "provision")
MAX_RESULT = 4096


def log(msg):
    print(f"openbao-reset: {msg}", flush=True)


class Relay:
    """Jobs for a worker that can't take HTTP calls itself. run() queues one
    and waits for its result; the worker take()s it and finish()es it."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.cond = threading.Condition()
        self.pending = collections.deque()
        self.jobs = {}  # id -> job, while its run() waits

    def _wait(self, until, done):
        while not done():
            left = until - self.clock()
            if left <= 0:
                return False
            self.cond.wait(left)
        return True

    def run(self, phase, user, timeout):
        """(ok, detail) once the worker answers, or (False, why) after timeout seconds."""
        job = {"id": secrets.token_hex(8), "phase": phase, "user": user,
               "taken": False, "done": False, "ok": False, "detail": ""}
        with self.cond:
            self.jobs[job["id"]] = job
            self.pending.append(job)
            self.cond.notify_all()
            self._wait(self.clock() + timeout, lambda: job["done"])
            self.jobs.pop(job["id"], None)
            if job in self.pending:
                self.pending.remove(job)
        if job["done"]:
            return job["ok"], job["detail"]
        if job["taken"]:
            return False, f"openbao-setup's reset worker did not finish within {timeout:g}s"
        return False, "openbao-setup's reset worker is not running (is openbao-setup up and ready?)"

    def take(self, wait):
        """The oldest queued job, or None after wait seconds."""
        with self.cond:
            if not self._wait(self.clock() + wait, lambda: bool(self.pending)):
                return None
            job = self.pending.popleft()
            job["taken"] = True
            return job

    def finish(self, job_id, ok, detail):
        """False when no run() is waiting for that job any more."""
        with self.cond:
            job = self.jobs.get(job_id)
            if job is None or job["done"]:
                return False
            job.update(done=True, ok=bool(ok), detail=detail)
            self.cond.notify_all()
            return True


def parse_result(body):
    """The worker's answer: first line `ok` or `fail`, then the detail."""
    text = body.decode("utf-8", "replace")[:MAX_RESULT]
    first, _, rest = text.partition("\n")
    detail = " ".join(rest.split())[-300:]
    return first.strip() == "ok", detail


def make_handler(relay, token, job_timeout=JOB_TIMEOUT, poll_wait=POLL_WAIT):
    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "openbao-reset"
        sys_version = ""
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            pass

        def _send(self, code, body, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code, doc):
            self._send(code, json.dumps(doc).encode())

        def _authorised(self):
            given = self.headers.get("X-Dojo-Reset-Token") or ""
            return bool(token) and hmac.compare_digest(given.encode(), token.encode())

        def do_GET(self):
            path = urllib.parse.urlsplit(self.path).path
            if path == "/healthz":
                return self._json(200, {"ok": True, "armed": bool(token)})
            if path == "/_dojo/work":
                if not self._authorised():
                    return self._json(403, {"error": "reset token required"})
                job = relay.take(poll_wait)
                line = f"{job['id']} {job['phase']} {job['user']}\n" if job else ""
                return self._send(200, line.encode(), "text/plain; charset=utf-8")
            self._json(404, {"error": "not found"})

        def do_POST(self):
            parts = urllib.parse.urlsplit(self.path)
            segs = parts.path.split("/")  # ["", "_dojo", "reset"|"work", x]
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            body = self.rfile.read(min(max(length, 0), MAX_RESULT)) if length else b""
            if len(segs) != 4 or segs[1] != "_dojo" or segs[2] not in ("reset", "work"):
                return self._json(404, {"error": "not found"})
            if not self._authorised():
                return self._json(403, {"error": "reset token required"})
            if segs[2] == "work":
                ok, detail = parse_result(body)
                if not relay.finish(segs[3], ok, detail):
                    return self._json(404, {"error": "no such job (it timed out?)"})
                return self._json(200, {"ok": True})
            phase = (urllib.parse.parse_qs(parts.query).get("phase") or [""])[0]
            user = urllib.parse.unquote(segs[3])
            if phase not in PHASES:
                return self._json(404, {"error": "phase is teardown or provision"})
            if not USER_RE.fullmatch(user):
                return self._json(400, {"ok": False, "detail": "no such student"})
            started = time.monotonic()
            ok, detail = relay.run(phase, user, job_timeout)
            log(f"{phase} {user}: {'ok' if ok else 'FAILED'} in {time.monotonic() - started:.1f}s: {detail}")
            self._json(200 if ok else 502, {"ok": ok, "detail": detail or ("done" if ok else "failed")})

    return Handler


def main():
    if not RESET_TOKEN:
        log("RESET_TOKEN is empty: every reset call will be refused")
    server = http.server.ThreadingHTTPServer(("0.0.0.0", 8080), make_handler(Relay(), RESET_TOKEN))
    server.daemon_threads = True
    log("listening on :8080")
    server.serve_forever()


if __name__ == "__main__":
    sys.exit(main())
