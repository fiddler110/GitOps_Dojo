"""api-bfla — CTF target 13 (plan docs/CTF-WORKSHOP-PLAN.md §7.3, CTF-2
"Server-side trust and APIs", API-only — OWASP API Security Top 10
API5:2023 Broken Function Level Authorization). A valid, ordinary
student-scoped token can call `POST /admin/reset-all` because the route
checks only that the token is VALID, never that its role is `facilitator`.

**Deliberately non-destructive by default, matching the ladder row's own
note** ("the solve script treats this as 'exploit confirmed' without
actually running it against the live range"): without a
`X-Confirm-Reset: yes` header, the route proves the authz bug and returns
the flag without mutating any state ("dry run"); only a request that
explicitly opts in actually resets the in-memory roster. The reference
solve script never sends that header.

Env:
  CTF_FLAG      this slot's flag value (plan §5).
  CTF_STUDENT   this slot's student handle; seeds the one account.
  PORT          listen port (default 5000).

Pure JSON API, no HTML — meant to be hit with curl/httpie/jq, not a browser.
"""
import os
import secrets
import socket
import threading

from flask import Flask, jsonify, request
from flask import Response as _Response

app = Flask(__name__)


# -- Scenario theme ("Helix Ops API"): static CSS served at /assets/theme.css, linked
# with a relative root path so it works through the Target Viewer proxy.
_CSS = """
:root{--bg:#f0f7ee;--card:#fff;--ink:#1c2e18;--mute:#62785c;--acc:#4d7c0f;--line:#d3e3cc}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,Segoe UI,sans-serif;background:var(--bg);color:var(--ink)}
header{background:linear-gradient(90deg,#1a2e05,#4d7c0f);color:#fff;padding:.9rem 1.5rem;display:flex;align-items:center;gap:.7rem}
.logo{background:#fff;color:#4d7c0f;font-weight:800;border-radius:6px;padding:.1rem .5rem}.brand{font-weight:600;letter-spacing:.02em}
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
        '<header><span class="logo">H</span><span class="brand">Helix Ops API</span></header>'
        f"<main>{inner}</main></body></html>"
    )


@app.get("/")
def index():
    return _shell('Helix Ops API', '<h1>Helix Ops API</h1><p>JSON API for the Helix operations console. Authenticate with <code>POST /login</code>, then call <code>GET /me</code>. Administrative routes live under <code>/admin</code>.</p>')

FLAG = os.environ.get("CTF_FLAG", "flag{api-bfla-dev0000000000}")
STUDENT_USER = os.environ.get("CTF_STUDENT", "student07")
STUDENT_PASS = "changeme123"

_TOKENS = {}  # token -> (username, role)
_ROSTER = {STUDENT_USER: {"progress": 3}}


@app.post("/login")
def login():
    body = request.get_json(silent=True) or {}
    if body.get("username") == STUDENT_USER and body.get("password") == STUDENT_PASS:
        token = secrets.token_hex(16)
        # Every logged-in account gets a "student" role token — there is no
        # facilitator login here at all; the bug is what /admin/reset-all
        # does with ANY valid one.
        _TOKENS[token] = (STUDENT_USER, "student")
        return jsonify({"token": token})
    return jsonify({"error": "invalid credentials"}), 401


def _auth():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return _TOKENS.get(header[len("Bearer "):])


@app.get("/me")
def me():
    identity = _auth()
    if not identity:
        return jsonify({"error": "unauthorized"}), 401
    username, role = identity
    return jsonify({"username": username, "role": role})


@app.post("/admin/reset-all")
def reset_all():
    # THE BUG: checks the token is valid, never that its role is
    # "facilitator". The fix is one line: also require
    # `role == "facilitator"` (a role that, correctly, nothing here ever
    # issues) before doing anything.
    identity = _auth()
    if not identity:
        return jsonify({"error": "unauthorized"}), 401
    confirmed = request.headers.get("X-Confirm-Reset") == "yes"
    if confirmed:
        for record in _ROSTER.values():
            record["progress"] = 0
    return jsonify({"reset": confirmed, "accounts": len(_ROSTER), "flag": FLAG})


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
# (DECOY_SSH_CONTAINER_PORT); it has nothing to do with this target's API.
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
