"""customer-portal — CTF target 14 (CTF-5 app-code defend target, CTF-D25).

A deliberately vulnerable customer lookup portal over a SQLite DB.
This is the source the STUDENT edits in CTF-5: the graded flaw is a SQL
injection in the search field, and the fix is to parameterize the query.

  THE FLAW (search):   the WHERE clause is built with string formatting, so a
                       crafted `q` escapes the quoted literal and dumps the
                       whole customers table — including the service account
                       whose password is the flag.
  THE FIX:             use a parameterized query (the `?` placeholder and a
                       params tuple) so input can never change the SQL. See the
                       SAFE example right below the vulnerable line.

The exploit re-run (exploit/dump.py) is the CTF-D19 gate: once the query is
parameterized the dump returns no flag, and the target goes green.

Nothing here is a secret the student shouldn't see — it's their own target's
source. The only secret is the flag, which lives in the DB, not the code.
"""

import os
import sqlite3

from flask import Flask, request, jsonify

app = Flask(__name__)
DB_PATH = os.environ.get("CTF_DB_PATH", "/data/portal.db")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/healthz")
def healthz():
    return "ok", 200


@app.get("/")
def index():
    # A minimal search form — no template engine, just enough to drive the
    # endpoint from a browser. The interesting surface is /search.
    return (
        "<h1>Customer Portal</h1>"
        '<form action="/search" method="get">'
        '<input name="q" placeholder="search customers by name">'
        '<button type="submit">Search</button>'
        "</form>",
        200,
    )


@app.get("/search")
def search():
    """Look up customers whose name matches `q`.

    VULNERABLE: `q` is interpolated straight into the SQL string, so
    `%' OR '1'='1' -- ` (or a UNION) returns every row.
    """
    q = request.args.get("q", "")

    conn = _connect()
    try:
        # The query returns the whole row (password column included), so a
        # successful injection dumps that column and the service account's flag,
        # not just names.
        # --- VULNERABLE (remove this) -------------------------------------
        sql = "SELECT id, name, email, password, account_id, tier FROM customers " \
              "WHERE name LIKE '%" + q + "%'"
        rows = conn.execute(sql).fetchall()
        # --- SAFE (use this instead) --------------------------------------
        # sql = ("SELECT id, name, email, password, account_id, tier FROM customers "
        #        "WHERE name LIKE ?")
        # rows = conn.execute(sql, (f"%{q}%",)).fetchall()
        # ------------------------------------------------------------------
    except sqlite3.Error as exc:
        # A broken injection payload shouldn't 500 the whole app.
        return jsonify(error=str(exc)), 400
    finally:
        conn.close()

    return jsonify(results=[dict(r) for r in rows]), 200


@app.post("/login")
def login():
    """Password login. Also string-built, so `' OR '1'='1' -- ` bypasses it.

    The graded, gated flaw is the /search dump; this endpoint shares the same
    root cause and the same fix (parameterize), and is here so the SQLi lesson
    reads as a portal, not a single query.
    """
    email = request.form.get("email", "")
    password = request.form.get("password", "")

    conn = _connect()
    try:
        # --- VULNERABLE (remove this) -------------------------------------
        sql = ("SELECT name FROM customers "
               f"WHERE email = '{email}' AND password = '{password}'")
        row = conn.execute(sql).fetchone()
        # --- SAFE (use this instead) --------------------------------------
        # sql = "SELECT name FROM customers WHERE email = ? AND password = ?"
        # row = conn.execute(sql, (email, password)).fetchone()
        # ------------------------------------------------------------------
    except sqlite3.Error as exc:
        return jsonify(error=str(exc)), 400
    finally:
        conn.close()

    if row is None:
        return jsonify(ok=False), 401
    return jsonify(ok=True, name=row["name"]), 200


if __name__ == "__main__":
    # Flask's dev server is fine here: one lightweight process per slot, on an
    # internal network with no route out (§4, §6).
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
