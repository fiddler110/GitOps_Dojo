import base64
import os
import secrets
import socket
import threading

from flask import Flask, Response, request
from flask import Response as _Response

app = Flask(__name__)


_CSS = """
:root{--bg:#14131f;--card:#1d1b2e;--ink:#e4e2f5;--mute:#9a97bd;--acc:#8b5cf6;--line:#34304f}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,Segoe UI,sans-serif;background:var(--bg);color:var(--ink)}
header{background:linear-gradient(90deg,#1e1b4b,#6d28d9);color:#fff;padding:.9rem 1.5rem;display:flex;align-items:center;gap:.7rem}
.logo{background:#fff;color:#6d28d9;font-weight:800;border-radius:6px;padding:.1rem .5rem}.brand{font-weight:600;letter-spacing:.02em}
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
        '<header><span class="logo">B</span><span class="brand">Brightwave Ops</span></header>'
        f"<main>{inner}</main></body></html>"
    )

FLAG = os.environ.get("CTF_FLAG", "flag{leaky-config-dev0000000000}")

METRICS_USER = "metrics-agent"
METRICS_PASS = os.environ.get("CTF_METRICS_PASS") or secrets.token_hex(8)

_DB_BACKUP = (
    "# ops-dashboard.conf -- nightly backup, superseded config\n"
    "db_host=internal-db.svc\n"
    "db_user=dashboard_ro\n"
    "db_password=CorrectHorseBatteryStaple!\n"
    "# rotated 2026-08-11, this file is stale -- kept only for the rollback runbook\n"
)

_LOG_LINES = [
    "2026-10-05 09:12:03 INFO  ops-dashboard starting up on :5000",
    "2026-10-05 09:12:04 INFO  health check registered at /status",
    "2026-10-05 09:14:21 INFO  metrics-agent polled /internal/metrics (200)",
    "2026-10-05 09:31:47 WARN  stricter auth rolled out on /internal/metrics;"
    " metrics-agent not yet updated",
    f"2026-10-05 09:31:47 WARN  basic auth failed for /internal/metrics:"
    f" user={METRICS_USER} pass={METRICS_PASS}",
    "2026-10-05 09:31:48 ERROR metrics-agent giving up after 1 attempt, will retry in 300s",
    "2026-10-05 09:36:48 INFO  metrics-agent polled /internal/metrics (200)",
]


@app.get("/")
def index():
    return _shell(
        "Ops Dashboard - Brightwave",
        "<h1>Ops Dashboard</h1>"
        '<p><a href="/status">Status</a></p>',
    )


@app.get("/status")
def status():
    return "<p>All systems nominal.</p>"


@app.get("/admin")
def admin_index():
    return _shell(
        "Admin - Brightwave",
        "<h1>Admin</h1><ul>"
        '<li><a href="/admin/logs">Logs</a></li>'
        "</ul>",
    )


@app.get("/internal")
def internal_index():
    return _shell(
        "Internal - Brightwave",
        "<h1>Internal</h1><ul>"
        '<li><a href="/internal/metrics">Metrics</a> (service accounts only)</li>'
        "</ul>",
    )


_ADMIN_FILES = {
    "app.log": "\n".join(_LOG_LINES) + "\n",
    "ops-dashboard.conf.bak": _DB_BACKUP,
}


@app.get("/admin/logs")
def admin_logs():
    listing = "".join(f'<li><a href="/admin/logs/{name}">{name}</a></li>' for name in _ADMIN_FILES)
    return _shell("Logs - Brightwave", f"<h1>Logs</h1><ul>{listing}</ul>")


@app.get("/admin/logs/<name>")
def admin_log_file(name):
    body = _ADMIN_FILES.get(name)
    if body is None:
        return "<p>Not found.</p>", 404
    return Response(body, mimetype="text/plain")


def _check_auth(req):
    header = req.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:]).decode("utf-8", "replace")
    except Exception:
        return False
    user, _, password = decoded.partition(":")
    return user == METRICS_USER and password == METRICS_PASS


def _unauthorized():
    return Response(
        "Unauthorized", 401, {"WWW-Authenticate": 'Basic realm="metrics"'}
    )


@app.get("/internal/metrics")
def internal_metrics():
    if not _check_auth(request):
        return _unauthorized()
    return f"<p>uptime_seconds=118203 requests_total=48217</p><p>{FLAG}</p>"


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
