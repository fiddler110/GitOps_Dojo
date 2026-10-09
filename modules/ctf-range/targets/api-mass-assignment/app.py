"""api-mass-assignment — CTF target 12 (plan docs/CTF-WORKSHOP-PLAN.md
§7.3, CTF-2 "Server-side trust and APIs", API-only — OWASP API Security
Top 10 API3:2023 Broken Object Property Level Authorization). A JSON
`PATCH /users/me` binds the WHOLE request body onto the user object, so a
field the client should never be able to set (`role`) gets set right along
with the one it should (`bio`).

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


# -- Scenario theme ("Kestrel Accounts API"): static CSS served at /assets/theme.css, linked
# with a relative root path so it works through the Target Viewer proxy.
_CSS = """
:root{--bg:#f4f1fa;--card:#fff;--ink:#241b3a;--mute:#6d6490;--acc:#7e22ce;--line:#ddd3ef}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,Segoe UI,sans-serif;background:var(--bg);color:var(--ink)}
header{background:linear-gradient(90deg,#3b0764,#7e22ce);color:#fff;padding:.9rem 1.5rem;display:flex;align-items:center;gap:.7rem}
.logo{background:#fff;color:#7e22ce;font-weight:800;border-radius:6px;padding:.1rem .5rem}.brand{font-weight:600;letter-spacing:.02em}
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
        '<header><span class="logo">K</span><span class="brand">Kestrel Accounts API</span></header>'
        f"<main>{inner}</main></body></html>"
    )


@app.get("/")
def index():
    return _shell('Kestrel Accounts API', '<h1>Kestrel Accounts API</h1><p>JSON API for Kestrel account holders. Authenticate with <code>POST /login</code>, then use <code>/users/me</code> to read or update your profile.</p>')

FLAG = os.environ.get("CTF_FLAG", "flag{api-mass-assignment-dev0000000000}")
STUDENT_USER = os.environ.get("CTF_STUDENT", "student07")
STUDENT_PASS = "changeme123"

_TOKENS = {}  # token -> username
_USERS = {STUDENT_USER: {"username": STUDENT_USER, "role": "student", "bio": ""}}


@app.post("/login")
def login():
    body = request.get_json(silent=True) or {}
    if body.get("username") == STUDENT_USER and body.get("password") == STUDENT_PASS:
        token = secrets.token_hex(16)
        _TOKENS[token] = STUDENT_USER
        return jsonify({"token": token})
    return jsonify({"error": "invalid credentials"}), 401


def _auth():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return _TOKENS.get(header[len("Bearer "):])


@app.get("/users/me")
def get_me():
    username = _auth()
    if not username:
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(_USERS[username])


@app.patch("/users/me")
def patch_me():
    username = _auth()
    if not username:
        return jsonify({"error": "unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    # THE BUG: every key in the client's JSON body is written straight onto
    # the user record, `role` included. The fix is an explicit allow-list,
    # e.g.:
    #   for key in ("bio",):
    #       if key in body:
    #           _USERS[username][key] = body[key]
    _USERS[username].update(body)
    return jsonify(_USERS[username])


@app.get("/admin/report")
def admin_report():
    username = _auth()
    if not username:
        return jsonify({"error": "unauthorized"}), 401
    if _USERS[username]["role"] != "admin":
        return jsonify({"error": "forbidden"}), 403
    return jsonify({"flag": FLAG})


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
