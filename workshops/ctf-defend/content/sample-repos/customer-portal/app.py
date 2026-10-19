import os
import sqlite3

from flask import Flask, request, jsonify
from flask import Response as _Response

app = Flask(__name__)


_CSS = """
:root{--bg:#eef6f5;--card:#fff;--ink:#16302e;--mute:#5b7471;--acc:#0f766e;--line:#cfe3e0}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,Segoe UI,sans-serif;background:var(--bg);color:var(--ink)}
header{background:linear-gradient(90deg,#064e4a,#0f766e);color:#fff;padding:.9rem 1.5rem;display:flex;align-items:center;gap:.7rem}
.logo{background:#fff;color:#0f766e;font-weight:800;border-radius:6px;padding:.1rem .5rem}.brand{font-weight:600;letter-spacing:.02em}
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
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{title}</title>"
        '<link rel="stylesheet" href="/assets/theme.css"></head><body>'
        '<header><span class="logo">L</span><span class="brand">Larkspur Credit Union</span></header>'
        f"<main>{inner}</main></body></html>"
    )
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
    return _shell(
        "Customer Portal - Larkspur Credit Union",
        "<h1>Customer Portal</h1>"
        '<form action="/search" method="get">'
        '<input name="q" placeholder="search customers by name">'
        '<button type="submit">Search</button>'
        "</form>",
    ), 200


@app.get("/search")
def search():
    q = request.args.get("q", "")

    conn = _connect()
    try:
        sql = "SELECT id, name, email, password, account_id, tier FROM customers " \
              "WHERE name LIKE '%" + q + "%'"
        rows = conn.execute(sql).fetchall()
    except sqlite3.Error as exc:
        return jsonify(error=str(exc)), 400
    finally:
        conn.close()

    return jsonify(results=[dict(r) for r in rows]), 200


@app.post("/login")
def login():
    email = request.form.get("email", "")
    password = request.form.get("password", "")

    conn = _connect()
    try:
        sql = ("SELECT name FROM customers "
               f"WHERE email = '{email}' AND password = '{password}'")
        row = conn.execute(sql).fetchone()
    except sqlite3.Error as exc:
        return jsonify(error=str(exc)), 400
    finally:
        conn.close()

    if row is None:
        return jsonify(ok=False), 401
    return jsonify(ok=True, name=row["name"]), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
