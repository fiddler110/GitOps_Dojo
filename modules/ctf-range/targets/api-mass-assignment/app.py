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

from flask import Flask, jsonify, request

app = Flask(__name__)

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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), threaded=False)
