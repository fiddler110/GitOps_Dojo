"""weak-auth-portal — CTF target 2 (plan docs/CTF-WORKSHOP-PLAN.md §7.3,
CTF-1 "Access and identity"). A login portal with no attempt limiting
(flavor-only; nothing here brute-forces a password) and a password-reset
token that is deterministically derivable from PUBLIC information — the
real, gating flaw. No secret ever goes into it, so anyone who guesses the
*scheme* (not the token itself) can compute a valid one without ever
receiving it by email/SMS, for any account, including the higher-privileged
one that holds the flag.

Env:
  CTF_FLAG      this slot's flag value (plan §5).
  PORT          listen port (default 5000).

Accounts: `student` (known password, flavor only) and `ops-admin` (random,
unknown, unreachable except through the reset bug — it holds the flag).
"""
import hashlib
import os
import socket
import threading
import time

from flask import Flask, Response, request

app = Flask(__name__)

FLAG = os.environ.get("CTF_FLAG", "flag{weak-auth-portal-dev0000000000}")

# TOKEN_WINDOW/TOKEN_LEN together are the whole bug: a short, purely
# time-derived digest with NO secret key mixed in (contrast an HMAC with a
# server-side secret, which this is deliberately NOT). The fix is one line:
# mix in a server-side secret the attacker can never know, e.g.
#   hashlib.sha256((APP_SECRET + f"reset:{user}:{bucket}").encode()).hexdigest()[:TOKEN_LEN]
TOKEN_WINDOW = 60  # seconds per bucket
TOKEN_LEN = 6      # hex chars — small on purpose, but irrelevant: it's guessable
                    # with ZERO brute force since there's no secret to begin with.

_PASSWORDS = {"student": "changeme123", "ops-admin": os.urandom(16).hex()}


def _bucket(now):
    return int(now) // TOKEN_WINDOW


def _token_for(user, bucket):
    # THE BUG: derived only from `user` and the current time bucket — both
    # public/guessable, no secret anywhere in the inputs.
    return hashlib.sha256(f"reset:{user}:{bucket}".encode()).hexdigest()[:TOKEN_LEN]


# -- Presentation only (no behavior): each target wears the look of its own
# scenario. The stylesheet is a separate route so `curl` output stays readable.
_CSS = """
:root{--bg:#0b1220;--card:#111a2e;--ink:#e2e8f0;--mute:#8b9bb4;--acc:#14b8a6;--line:#22304a}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,Segoe UI,sans-serif;background:radial-gradient(circle at 20% 0,#12304a,var(--bg) 55%);color:var(--ink);min-height:100vh}
header{padding:.9rem 1.5rem;display:flex;align-items:center;gap:.7rem;border-bottom:1px solid var(--line)}
.logo{background:var(--acc);color:#04201c;font-weight:800;border-radius:6px;padding:.1rem .5rem}.brand{font-weight:600;letter-spacing:.04em;text-transform:uppercase;font-size:.85rem}
main{max-width:380px;margin:3rem auto;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:2rem}
form{display:flex;flex-direction:column;gap:.7rem;margin:0 0 .8rem}
input{padding:.65rem .75rem;border:1px solid var(--line);border-radius:8px;background:#0b1424;color:var(--ink);font:inherit}
input:focus{outline:2px solid #0f766e;border-color:var(--acc)}
button{padding:.65rem;border:0;border-radius:8px;background:var(--acc);color:#04201c;font:700 1rem system-ui;cursor:pointer}
button:hover{filter:brightness(1.1)}a{color:var(--acc)}p{margin:.4rem 0}
h1{font-size:1.25rem;margin:0 0 1rem}.note{color:var(--mute);font-size:.8rem;margin-top:1rem}
"""


@app.get("/assets/theme.css")
def theme_css():
    return Response(_CSS, mimetype="text/css")


def _page(title, body):
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{title} &middot; Northwind Ops Console</title>"
        '<link rel="stylesheet" href="/assets/theme.css"></head><body>'
        '<header><span class="logo">N</span><span class="brand">Northwind Ops Console</span></header>'
        f'<main>{body}</main></body></html>'
    )


@app.get("/")
def index():
    return _page("Sign in", (
        "<h1>Internal Portal</h1>"
        '<form method="post" action="/login">'
        '<input name="username" placeholder="username">'
        '<input name="password" type="password" placeholder="password">'
        "<button>Log in</button></form>"
        '<p><a href="/forgot-password">Forgot password?</a></p>'
        '<p class="note">Operations staff only. Infrastructure change window: Tue 02:00.</p>'
    ))


@app.post("/login")
def login():
    # No rate limit / lockout here at all — the ladder row's flavor flaw.
    # Not the gating path (password space is large), left in for fidelity.
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    if _PASSWORDS.get(username) == password:
        return _page("Portal", f"<p>Welcome, {username}.</p>")
    return _page("Portal", "<p>Invalid credentials.</p>"), 401


@app.get("/forgot-password")
def forgot_password_form():
    return _page("Reset password", (
        "<h1>Reset your password</h1>"
        '<form method="post" action="/forgot-password">'
        '<input name="username" placeholder="username"><button>Send reset link</button></form>'
    ))


@app.post("/forgot-password")
def forgot_password():
    # Realistic: never reveals the token itself (it would be emailed in a
    # real app). The vulnerability is that an attacker never needs to see
    # it — it's derivable from public inputs alone.
    user = request.form.get("username", "")
    if user in _PASSWORDS:
        return _page("Portal", "<p>If this account exists, a reset link has been sent.</p>")
    return _page("Portal", "<p>If this account exists, a reset link has been sent.</p>")


@app.post("/reset")
def reset():
    user = request.form.get("username", "")
    token = request.form.get("token", "")
    new_password = request.form.get("new_password", "")
    if user not in _PASSWORDS:
        return _page("Portal", "<p>Invalid request.</p>"), 400
    now = time.time()
    # Accept the current bucket and one on either side, same tolerance a
    # real deployment needs for clock skew / request latency — it changes
    # nothing about the bug (still zero secret involved).
    valid = {_token_for(user, _bucket(now) + delta) for delta in (-1, 0, 1)}
    if token not in valid:
        return _page("Portal", "<p>Invalid or expired token.</p>"), 403
    _PASSWORDS[user] = new_password
    if user == "ops-admin":
        return _page("Portal", f"<p>Password reset for {user}. {FLAG}</p>")
    return _page("Portal", f"<p>Password reset for {user}.</p>")


# -- Decoy listener (plan §7.3's nmap primer: a student scans their box and
# finds more than the one port they'll actually use, same as a HackTheBox
# box) -----------------------------------------------------------------
# NOT a real sshd: every slot container drops every Linux capability and
# runs read-only as a non-root user (docker_api.py's build_create_request()),
# which makes a genuine sshd impossible here at all (host keys, privilege
# separation and setuid-per-connection all need root). This speaks just
# enough of the real SSH-2.0 handshake to fingerprint correctly under
# `nmap -sV`, then closes — there is no key exchange and no account behind
# it. ctf-controller's AttackManager always reserves this port
# (DECOY_SSH_CONTAINER_PORT); it has nothing to do with this target's bug.
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
