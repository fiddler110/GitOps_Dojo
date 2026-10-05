"""ctf-flags — the one thing in the range a student's terminal talks to
directly over `workshop_lab` (plan §5). It does exactly one job: verify a
submitted flag and, if it checks out, credit the achievement.

    POST /submit  {"user": "student07", "challenge": "sqli-login", "flag": "flag{...}"}
                  -> {"ok": true}   (verified; a signed `ctf`/`flag_solved` event was
                                     queued for achievements — best effort, never blocks)
                  -> {"ok": false}  (wrong flag, or a malformed body)

`user` is self-asserted (the CLI sends `id -un`'s own account), the same trust
level as a terminal's other self-reported identity (dojo-check's shell hook,
for one). That is deliberately not a security boundary here: the actual
secret is the flag VALUE (plan.render, the per-slot HMAC keyed on a seed the
student never sees), not who claims to hold it. Lying about `user` only lets
a student credit themselves with a flag they already had — not a privilege
a classmate's identity would grant them, and not worth the complexity of a
stronger identity check in an ephemeral lab (see CLAUDE.md "don't
overengineer" convention for this kind of residual risk).

A wrong flag never raises or errors the CLI (plan §5) — this always answers
200 with {"ok": bool}, even on a bad body.

Stdlib only. No capability beyond an outbound POST to achievements (best
effort, via AdapterClient) and reading STUDENT_PASSWORD_SEED from its own
environment, same trust tier as ctf-controller.
"""
import hmac
import http.server
import json
import os
import socketserver
import sys

sys.path[:0] = [os.path.join(os.path.dirname(__file__), "..", "..", "_shared"),
                os.path.join(os.path.dirname(__file__), "_shared")]
from adapter_client import AdapterClient  # noqa: E402

import flags

MAX_BODY = 2048
MAX_FIELD = 200


class Config:
    def __init__(self, env=os.environ):
        self.seed = env.get("STUDENT_PASSWORD_SEED", "")
        self.adapter_url = env.get("ACHIEVEMENTS_ADAPTER_URL", "")
        self.adapter_secret = env.get("ACHIEVEMENTS_ADAPTER_SECRET", "")


def verify(cfg, user, challenge, flag):
    """True if `flag` is the real value for (user, challenge). Constant-time
    compare so a submission can't be brute-forced by response timing."""
    want = flags.render(user, cfg.seed, challenge)
    return hmac.compare_digest(flag.encode(), want.encode())


def _valid_field(v):
    return isinstance(v, str) and 0 < len(v) <= MAX_FIELD


def make_handler(cfg, adapter):
    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "ctf-flags"
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

        def do_GET(self):
            if self.path.split("?", 1)[0] == "/healthz":
                self._json(200, {"ok": True})
                return
            self._json(404, {"error": "not found"})

        do_HEAD = do_GET

        def do_POST(self):
            if self.path.split("?", 1)[0] != "/submit":
                self._json(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length > MAX_BODY:
                    raise ValueError
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict):
                    raise ValueError
            except ValueError:
                self._json(200, {"ok": False})
                return
            user, challenge, flag = body.get("user"), body.get("challenge"), body.get("flag")
            if not all(_valid_field(v) for v in (user, challenge, flag)):
                self._json(200, {"ok": False})
                return
            ok = verify(cfg, user, challenge, flag)
            if ok:
                adapter.post({"source": "ctf", "event": "flag_solved", "user": user, "challenge": challenge})
            self._json(200, {"ok": ok})

    return Handler


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    cfg = Config()
    adapter = AdapterClient(cfg.adapter_url, cfg.adapter_secret, "ctf")
    print(f"[ctf-flags] ready, achievements adapter {'on' if adapter.enabled else 'off'}", flush=True)
    Server(("0.0.0.0", 8080), make_handler(cfg, adapter)).serve_forever()


if __name__ == "__main__":
    main()
