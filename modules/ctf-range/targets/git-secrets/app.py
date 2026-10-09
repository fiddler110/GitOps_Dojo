"""git-secrets — CTF target 8 (plan docs/CTF-WORKSHOP-PLAN.md §7.3, CTF-3
"Secrets and misconfiguration", ties `git-fundamentals`). Unlike every other
attack-ladder target, there is NO bug in this app at all -- the token check
below is correct. The whole foothold lives outside `ctf_net` entirely, in a
Forgejo repo's git history: a deploy token that was committed, then "cleaned
up" in a later commit (the file no longer contains it on the default
branch), but git never actually forgets a blob a later commit stops
referencing. `git log -p` (or Forgejo's own commit/diff view) still shows it.

This target is the second half of the lesson (plan §7.3 row 8's
"escalation"): present the token you recovered from history and this
service hands you the flag. No brute force is possible or intended -- the
token space is large; the only path in is reading it off the leaked commit.

Env (all rendered by ctf-controller's AttackManager, generic over every
attack-ladder target -- see controller.py's `_env_for`):
  CTF_FLAG          this slot's flag value.
  CTF_TARGET_TOKEN  the exact value planted in this student's git history
                     (modules/ctf-range/terminal/start.d/55-git-secrets.sh
                     computes the identical value independently -- same
                     two-copies idiom as CTF_FLAG itself).
  PORT              listen port (default 5000).
"""
import os
import socket
import threading

from flask import Flask, request
from flask import Response as _Response

app = Flask(__name__)


# -- Scenario theme ("Forgeline Deploy"): static CSS served at /assets/theme.css, linked
# with a relative root path so it works through the Target Viewer proxy.
_CSS = """
:root{--bg:#fbf3ea;--card:#fff;--ink:#2b1a0c;--mute:#8a6a4d;--acc:#c2410c;--line:#ecd9c6}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,Segoe UI,sans-serif;background:var(--bg);color:var(--ink)}
header{background:linear-gradient(90deg,#7c2d12,#ea580c);color:#fff;padding:.9rem 1.5rem;display:flex;align-items:center;gap:.7rem}
.logo{background:#fff;color:#ea580c;font-weight:800;border-radius:6px;padding:.1rem .5rem}.brand{font-weight:600;letter-spacing:.02em}
main{max-width:640px;margin:2.5rem auto;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:2rem;box-shadow:0 8px 30px #0002}
h1{margin:0 0 .6rem;font-size:1.4rem}h1 small{color:var(--mute);font-weight:400;font-size:.8em}h2{font-size:1.1rem}a{color:var(--acc)}
label{display:block;font-weight:600;font-size:.85rem;margin:.8rem 0 .25rem}
input{width:100%;padding:.6rem .7rem;border:1px solid var(--line);border-radius:8px;font:inherit;background:var(--bg);color:var(--ink)}
input:focus{outline:2px solid var(--acc)}
button{margin-top:1rem;padding:.6rem 1.2rem;border:0;border-radius:8px;background:var(--acc);color:#fff;font:600 1rem system-ui;cursor:pointer}
code,pre{background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:.05rem .35rem;font-size:.9em}
pre{padding:.7rem;white-space:pre-wrap;word-break:break-all}
"""


@app.get("/assets/theme.css")
def theme_css():
    return _Response(_CSS, mimetype="text/css")


def _shell(title, inner):
    # `inner` is static markup written in this file (never request data).
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{title}</title>"
        '<link rel="stylesheet" href="/assets/theme.css"></head><body>'
        '<header><span class="logo">F</span><span class="brand">Forgeline Deploy</span></header>'
        f"<main>{inner}</main></body></html>"
    )

FLAG = os.environ.get("CTF_FLAG", "flag{git-secrets-dev0000000000}")
DEPLOY_TOKEN = os.environ.get("CTF_TARGET_TOKEN", "flag{git-secrets-token-dev0000000000}")


@app.get("/")
def index():
    return _shell("Deploy Trigger - Forgeline", 
        "<h1>Internal Deploy Trigger</h1>"
        "<p>Deploys are kicked off by POSTing the service's own deploy token "
        "to <code>/deploy/trigger</code>. If you don't have it, you're not "
        "supposed to be here.</p>"
    )


@app.get("/status")
def status():
    return "<p>idle, waiting for a deploy</p>"


@app.post("/deploy/trigger")
def deploy_trigger():
    # No bug here: a correct, constant-time comparison of a correct check.
    # The only way in is already having the token.
    token = request.form.get("token") or request.headers.get("X-Deploy-Token") or ""
    if not token or not _const_eq(token, DEPLOY_TOKEN):
        return "<p>Rejected: bad or missing deploy token.</p>", 403
    return f"<p>Deploy triggered.</p><p>{FLAG}</p>"


def _const_eq(a, b):
    import hmac
    return hmac.compare_digest(a.encode(), b.encode())


# -- Decoy listener (plan §7.3's nmap primer) --------------------------------
# NOT a real sshd -- see weak-auth-portal/app.py's identical comment for why
# a genuine one is impossible under this range's hardening.
def _decoy_ssh_handler(conn):
    try:
        conn.sendall(b"SSH-2.0-OpenSSH_9.7p1 Debian-7\r\n")
        conn.recv(256)
    except OSError:
        pass
    finally:
        conn.close()


def _start_decoy(port, handler):
    def _accept_loop():
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", port))
        srv.listen(16)
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                continue
            threading.Thread(target=handler, args=(conn,), daemon=True).start()
    threading.Thread(target=_accept_loop, daemon=True).start()


_start_decoy(2222, _decoy_ssh_handler)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), threaded=False)
