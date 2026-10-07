"""sqli-login — CTF target 0 (plan docs/CTF-WORKSHOP-PLAN.md §7.3, CTF-1
"Access and identity"). The warm-up: a login form whose query is built by
plain string formatting, so the classic auth-bypass payload
(`' OR '1'='1' -- `) logs in as `admin` without knowing the password. Single
flag, shown right on the welcome page — no second stage (the ladder's row for
this target: "none; single flag shown in the page").

Env:
  CTF_FLAG      this slot's flag value (rendered by ctf-controller's
                AttackManager, plan §5) — never read from anywhere else.
  CTF_STUDENT   this slot's student handle; seeds one decoy row so the DB
                isn't only `admin`, nothing security-relevant depends on it.
  PORT          listen port (default 5000).

The DB lives in-process (sqlite ':memory:'), never on disk: there is nothing
here worth a volume, and it keeps the container's whole root filesystem
read-only with no bind mount to manage at all (lighter than
targets/customer-portal's /data tmpfs, which this target doesn't need).
"""
import os
import socket
import sqlite3
import threading

from flask import Flask, Response, render_template_string, request

app = Flask(__name__)

FLAG = os.environ.get("CTF_FLAG", "flag{sqli-login-dev0000000000}")
STUDENT = os.environ.get("CTF_STUDENT", "student07")

# One connection for the process lifetime. The dev server below runs
# single-threaded (threaded=False), so this is never touched concurrently.
_DB = sqlite3.connect(":memory:", check_same_thread=False)
_DB.execute("CREATE TABLE users (username TEXT NOT NULL, password TEXT NOT NULL)")
# admin's real password is random and never revealed anywhere — the whole
# point is that the bypass never needs it. The second row is a decoy tied to
# this slot's handle so the DB isn't suspiciously single-purpose.
_DB.execute("INSERT INTO users VALUES (?, ?)", ("admin", os.urandom(16).hex()))
_DB.execute("INSERT INTO users VALUES (?, ?)", (STUDENT, "changeme123"))
_DB.commit()

PAGE = """
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Employee Sign-in &middot; Meridian Intranet</title>
<link rel="stylesheet" href="/assets/theme.css"></head>
<body>
<header><span class="logo">M</span><span class="brand">Meridian Corp Intranet</span></header>
<main>
<h1>Internal Portal</h1>
<p class="sub">Sign in with your employee account.</p>
{% if error %}<p class="err">{{ error }}</p>{% endif %}
{% if welcome %}<p class="ok">Welcome, {{ welcome }}! {{ flag }}</p>{% endif %}
<form method="post" action="/login">
  <label>Username <input name="username" autocomplete="off"></label>
  <label>Password <input name="password" type="password"></label>
  <button type="submit">Log in</button>
</form>
<footer>Authorized personnel only. Activity is logged.</footer>
</main>
</body>
</html>
"""


_CSS = """
:root{--bg:#eef2f7;--card:#fff;--ink:#1e293b;--mute:#64748b;--acc:#1d4ed8;--line:#d7dee9}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,Segoe UI,sans-serif;background:var(--bg);color:var(--ink)}
header{background:linear-gradient(90deg,#0f2a5c,#1d4ed8);color:#fff;padding:.9rem 1.5rem;display:flex;align-items:center;gap:.7rem}
.logo{background:#fff;color:#1d4ed8;font-weight:800;border-radius:6px;padding:.1rem .5rem}.brand{font-weight:600;letter-spacing:.02em}
main{max-width:380px;margin:3rem auto;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:2rem;box-shadow:0 8px 30px #0f2a5c14}
h1{margin:0 0 .3rem;font-size:1.4rem}.sub{color:var(--mute);margin:0 0 1.2rem}
label{display:block;font-weight:600;font-size:.85rem;margin:.8rem 0 .25rem}
input{width:100%;padding:.6rem .7rem;border:1px solid var(--line);border-radius:8px;font:inherit}
input:focus{outline:2px solid #93b4ff;border-color:var(--acc)}
button{margin-top:1.2rem;width:100%;padding:.65rem;border:0;border-radius:8px;background:var(--acc);color:#fff;font:600 1rem system-ui;cursor:pointer}
button:hover{background:#1e40af}.err{background:#fef2f2;color:#b91c1c;border:1px solid #fecaca;border-radius:8px;padding:.5rem .7rem}
.ok{background:#f0fdf4;color:#166534;border:1px solid #bbf7d0;border-radius:8px;padding:.6rem .7rem;word-break:break-all}
footer{text-align:center;color:var(--mute);font-size:.75rem;margin-top:1.2rem}
"""


@app.get("/assets/theme.css")
def theme_css():
    return Response(_CSS, mimetype="text/css")


@app.get("/")
def index():
    return render_template_string(PAGE, error=None, welcome=None, flag=None)


@app.post("/login")
def login():
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    # THE BUG: a string-built query, never parameterized. The fix is one
    # line — pass (username, password) as execute()'s second argument
    # instead of formatting them into the SQL text.
    query = (
        "SELECT username FROM users WHERE username = '"
        + username
        + "' AND password = '"
        + password
        + "'"
    )
    try:
        row = _DB.execute(query).fetchone()
    except sqlite3.Error:
        row = None
    if row:
        return render_template_string(PAGE, error=None, welcome=row[0], flag=FLAG)
    return render_template_string(PAGE, error="Invalid credentials", welcome=None, flag=None)


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
