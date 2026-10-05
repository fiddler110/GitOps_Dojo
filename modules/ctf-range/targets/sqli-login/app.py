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
import sqlite3

from flask import Flask, render_template_string, request

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
<head><meta charset="utf-8"><title>Internal Portal</title></head>
<body>
<h1>Internal Portal</h1>
{% if error %}<p style="color:#b33">{{ error }}</p>{% endif %}
{% if welcome %}<p>Welcome, {{ welcome }}! {{ flag }}</p>{% endif %}
<form method="post" action="/login">
  <label>Username <input name="username"></label><br>
  <label>Password <input name="password" type="password"></label><br>
  <button type="submit">Log in</button>
</form>
</body>
</html>
"""


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), threaded=False)
