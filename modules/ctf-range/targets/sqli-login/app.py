"""sqli-login — CTF target 0 (plan docs/CTF-WORKSHOP-PLAN.md §7.3, CTF-1
"Access and identity"). The warm-up: a login form whose query is built by
plain string formatting, so the classic auth-bypass payload
(`' OR '1'='1' -- `) logs in as `admin` without knowing the password.
Two stages, like a HackTheBox box: the login bypass is the foothold; behind
it the portal links three log files that leak service accounts; one logs into the box
over SSH (sshshell.py, an emulated shell) where flag.txt holds the flag.

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
import random
import socket
import sqlite3
import threading

import sshshell
from flask import Flask, Response, redirect, render_template_string, request, session

app = Flask(__name__)
app.config.update(SESSION_COOKIE_NAME="meridian", SESSION_COOKIE_HTTPONLY=True)

FLAG = os.environ.get("CTF_FLAG", "flag{sqli-login-dev0000000000}")
STUDENT = os.environ.get("CTF_STUDENT", "student07")
app.secret_key = "meridian:" + FLAG

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

# Three accounts turn up in the operations logs behind the login; only the first logs into the box
# over SSH. The other two are stale service accounts the SSH server has never heard of.
_rnd = random.Random(FLAG)
SSH_USER = "svc-print"
SSH_PASSWORD = "Print-" + os.urandom(4).hex()
_CREDS = [
    (SSH_USER, SSH_PASSWORD),
    ("svc-backup", "Bk-%08x" % _rnd.getrandbits(32)),
    ("helpdesk", "Help-%08x" % _rnd.getrandbits(32)),
]

LOGS = [
    ("print-queue.log", "Print queue service log"),
    ("maintenance.log", "Nightly maintenance jobs"),
    ("helpdesk-sync.log", "Helpdesk ticket sync"),
]


def _cred_line(kind, n, user, pw):
    """One log line that leaks a credential, in the style of the service that wrote it."""
    if n == 0:
        return f"auth: login failed user={user} password={pw} src=10.0.4.{_rnd.randint(10, 90)} reason=bad-gateway-token"
    if n == 1:
        return f"/usr/local/bin/sync-queue.sh: sshpass -p '{pw}' ssh {user}@print01 'lpstat -o'"
    return f"debug: connecting to print01 with credentials {user} / {pw}"


_NOISE = {
    "print-queue.log": ["job {n} queued on floor2-laser by dpatel", "job {n} completed, 3 pages",
                        "printer floor3-color: toner low (12%)", "spooler: cleaned {n} stale jobs",
                        "job {n} cancelled by owner", "printer floor2-laser: paper jam cleared"],
    "maintenance.log": ["logrotate: rotated /var/log/cups/access_log", "backup: snapshot {n} ok, 412 MB",
                        "apt: 0 upgraded, 0 newly installed", "cron: job nightly-cleanup finished in {n}s",
                        "ntp: clock offset 0.0{n}s", "disk: /var at 41% used"],
    "helpdesk-sync.log": ["ticket INC-{n} synced (status=resolved)", "ticket INC-{n} synced (status=open)",
                          "sync: 14 tickets in, 0 conflicts", "sync: waiting for next interval",
                          "ticket INC-{n} assigned to it-desk", "webhook: 200 OK from servicedesk"],
}


def _build_logs():
    counts = [1, 2, 0]
    _rnd.shuffle(counts)
    creds = list(_CREDS)
    _rnd.shuffle(creds)
    logs, i = {}, 0
    for (name, _title), count in zip(LOGS, counts):
        lines = [_rnd.choice(_NOISE[name]).format(n=_rnd.randint(100, 9999)) for _ in range(28)]
        for _ in range(count):
            user, pw = creds[i]
            lines.insert(_rnd.randint(3, len(lines) - 3), _cred_line(name, i % 3, user, pw))
            i += 1
        t, out = 8 * 3600 + _rnd.randint(0, 600), []
        for line in lines:
            t += _rnd.randint(7, 340)
            out.append(f"2026-10-17 {t // 3600 % 24:02d}:{t // 60 % 60:02d}:{t % 60:02d} {name.split('.')[0]}[{_rnd.randint(200, 900)}]: {line}")
        logs[name] = "\n".join(out) + "\n"
    return logs


_LOG_TEXT = _build_logs()

PAGE = """
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Employee Sign-in &middot; Meridian Intranet</title>
<link rel="icon" href="/assets/logo.svg" type="image/svg+xml"><link rel="stylesheet" href="/assets/theme.css"><script src="/assets/show.js" defer></script></head>
<body>
<div class="shell">
<aside class="brandpanel">
  <img class="mark" src="/assets/logo.svg" alt="Meridian Corp" width="132" height="132">
  <div class="name">Meridian<span>Corp</span></div>
  <p class="tag">One network. Every office. Always on.</p>
  <ul class="facts"><li>Employee directory</li><li>Payroll and benefits</li><li>IT service desk</li></ul>
</aside>
<main>
<h1>Internal Portal</h1>
<p class="sub">Sign in with your employee account.</p>
{% if error %}<p class="err">{{ error }}</p>{% endif %}
{% if welcome %}<p class="ok">Welcome, {{ welcome }}.</p>
<div class="note"><b>Operations logs</b>
<p>Service logs for the print server and its helpers. Internal use only.</p>
<ul>{% for name, title in logs %}<li><a href="logs/{{ name }}">{{ title }}</a> <code>{{ name }}</code></li>{% endfor %}</ul></div>
{% else %}<form method="post" action="/login">
  <label>Username <input name="username" autocomplete="off" placeholder="firstname.lastname"></label>
  <label>Password <input id="pw" name="password" type="password" autocomplete="off" spellcheck="false"></label>
  <label class="show"><input id="show" type="checkbox"> Show password</label>
  <button type="submit">Log in</button>
</form>{% endif %}
<footer>Authorized personnel only. Activity is logged.</footer>
</main>
</div>
</body>
</html>
"""


_CSS = """
:root{--bg:#0b1b3a;--card:#fff;--ink:#1e293b;--mute:#64748b;--acc:#1d4ed8;--line:#d7dee9}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;font:15px/1.5 system-ui,Segoe UI,sans-serif;color:var(--ink);display:flex;align-items:center;justify-content:center;
background:radial-gradient(circle at 20% 15%,#1d4ed8 0,#0f2a5c 38%,#0b1b3a 80%);padding:1.5rem}
.shell{display:flex;width:100%;max-width:820px;border-radius:16px;overflow:hidden;box-shadow:0 30px 80px #0008}
.brandpanel{flex:1 1 44%;padding:2.4rem 2rem;color:#e8efff;background:linear-gradient(160deg,#0f2a5c,#1740a8);display:flex;flex-direction:column;gap:.6rem}
.mark{display:block;background:#fff;border-radius:50%;padding:10px;box-shadow:0 10px 30px #0006;margin-bottom:.8rem}
.name{font-size:1.7rem;font-weight:700;letter-spacing:.01em}.name span{font-weight:300;margin-left:.35rem;color:#9db8ff}
.tag{margin:0;color:#b8cbff}
.facts{list-style:none;margin:1.4rem 0 0;padding:0;color:#c9d8ff;font-size:.9rem}
.facts li{padding:.25rem 0 .25rem 1.1rem;position:relative}
.facts li:before{content:"";position:absolute;left:0;top:.8rem;width:6px;height:6px;border-radius:50%;background:#6f9bff}
main{flex:1 1 56%;background:var(--card);padding:2.4rem 2rem}
h1{margin:0 0 .3rem;font-size:1.5rem}.sub{color:var(--mute);margin:0 0 1.2rem}
label.show{font-weight:400;display:flex;gap:.4rem;align-items:center}
label.show input{width:auto}
label{display:block;font-weight:600;font-size:.85rem;margin:.8rem 0 .25rem}
input{width:100%;padding:.65rem .75rem;border:1px solid var(--line);border-radius:8px;font:inherit}
input:focus{outline:2px solid #93b4ff;border-color:var(--acc)}
button{margin-top:1.2rem;width:100%;padding:.7rem;border:0;border-radius:8px;background:var(--acc);color:#fff;font:600 1rem system-ui;cursor:pointer}
button:hover{background:#1e40af}
.err{background:#fef2f2;color:#b91c1c;border:1px solid #fecaca;border-radius:8px;padding:.5rem .7rem}
.ok{background:#f0fdf4;color:#166534;border:1px solid #bbf7d0;border-radius:8px;padding:.6rem .7rem;word-break:break-all}
.note{margin-top:.8rem;border:1px solid var(--line);border-radius:8px;padding:.6rem .8rem;background:#f8fafc;font-size:.9rem}.note p{margin:.3rem 0}.note ul{margin:.4rem 0 0;padding-left:1.1rem}.note a{color:var(--acc)}.note code{background:#e8efff;padding:.05rem .35rem;border-radius:4px;word-break:break-all}
footer{text-align:center;color:var(--mute);font-size:.75rem;margin-top:1.4rem}
@media (max-width:640px){.shell{flex-direction:column}.brandpanel{padding:1.4rem}.facts{display:none}}
"""


@app.get("/assets/theme.css")
def theme_css():
    return Response(_CSS, mimetype="text/css")


_LOGO = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "Meridian_Logo.svg"), "rb").read()


@app.get("/assets/logo.svg")
def logo_svg():
    return Response(_LOGO, mimetype="image/svg+xml")


@app.get("/assets/show.js")
def show_js():
    return Response('document.getElementById("show").addEventListener("change", function (e) {\n'
                    '  document.getElementById("pw").type = e.target.checked ? "text" : "password";\n});\n',
                    mimetype="text/javascript")


@app.get("/")
def index():
    return render_template_string(PAGE, error=None, welcome=None)


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
        session["user"] = row[0]
        return redirect("portal")
    return render_template_string(PAGE, error="Invalid credentials", welcome=None)


def _user():
    return session.get("user")


@app.get("/portal")
def portal():
    if not _user():
        return redirect("./")
    return render_template_string(PAGE, error=None, welcome=_user(), logs=LOGS)


@app.get("/logs/<name>")
def log_file(name):
    if not _user():
        return redirect("../")
    if name not in _LOG_TEXT:
        return Response("not found\n", 404, mimetype="text/plain")
    return Response(_LOG_TEXT[name], mimetype="text/plain")


# -- Decoy listener (plan §7.3's nmap primer: a student scans their box and
# finds more than the one port they'll actually use, same as a HackTheBox
# box) -----------------------------------------------------------------
# The SSH service on 2222 (the host publishes it as 22) is the second stage:
# a real SSH server with an emulated shell, see sshshell.py. The service
# account's password is shown only on the portal page behind the login.


def _decoy_ftp_handler(conn):
    try:
        conn.sendall(b"220 ProFTPD 1.3.7e Server (Meridian File Transfer) [10.0.0.14]\r\n")
        while True:
            line = conn.recv(256)
            if not line:
                break
            verb = line.strip().split(b" ")[0].upper()
            if verb == b"QUIT":
                conn.sendall(b"221 Goodbye.\r\n")
                break
            if verb == b"USER":
                conn.sendall(b"331 Password required\r\n")
            else:
                conn.sendall(b"530 Login incorrect.\r\n")
    except OSError:
        pass
    finally:
        conn.close()


# A second web listener that looks like an admin console and answers 401 to
# everything; nothing behind it. With the real port it is two HTTP services
# to tell apart, which `nmap -sV` and a curl each do.
def _decoy_http_handler(conn):
    try:
        conn.recv(2048)
        conn.sendall(b"HTTP/1.1 401 Unauthorized\r\nServer: Apache/2.4.58 (Debian)\r\n"
                     b"WWW-Authenticate: Basic realm=\"Meridian Print Server\"\r\n"
                     b"Content-Length: 0\r\nConnection: close\r\n\r\n")
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


sshshell.start(2222, SSH_USER, SSH_PASSWORD, FLAG, FLAG)
_start_decoy(2121, _decoy_ftp_handler)
_start_decoy(8081, _decoy_http_handler)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), threaded=False)
