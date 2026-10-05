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

app = Flask(__name__)

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
