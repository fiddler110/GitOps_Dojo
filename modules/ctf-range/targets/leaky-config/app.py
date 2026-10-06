"""leaky-config — CTF target 5 (plan docs/CTF-WORKSHOP-PLAN.md §7.3, CTF-3
"Secrets and misconfiguration", OWASP A05 Security Misconfiguration). An
"ops dashboard" whose static-file route was wired to serve a whole
directory, including files nobody meant to publish: a verbose debug log and
a config backup. The log's own verbosity is the gating flaw — a service
account's Basic Auth credentials end up in plaintext in a line nobody
scrubbed. The backup is flavor/noise (a believable, unrelated DB
connection string) so a student has to tell "a leaked secret" apart from
"a secret-shaped string that happens to be sitting here too" — the same
read a real misconfigured-share incident needs.

Env:
  CTF_FLAG      this slot's flag value (plan §5).
  PORT          listen port (default 5000).

No bug in the Basic Auth check itself — the escalation is plain credential
reuse: the leaked metrics-agent password, read verbatim off the log, is the
real password for `/internal/metrics`.
"""
import base64
import os
import secrets
import socket
import threading

from flask import Flask, Response, request

app = Flask(__name__)

FLAG = os.environ.get("CTF_FLAG", "flag{leaky-config-dev0000000000}")

# THE SECRET: generated once per process start, never logged anywhere else,
# never sent to a client directly -- only ever readable off the leaked log
# line below. A real incident: a service account retries, fails once against
# a stricter auth check that was rolled out after the account's password was
# set, and the failure handler logs the attempted credentials "for
# debugging" instead of redacting them.
METRICS_USER = "metrics-agent"
METRICS_PASS = secrets.token_hex(8)

# Flavor-only noise: a DB connection string that LOOKS like a leaked secret
# but unlocks nothing here -- the actual gating credential is the metrics
# password above, read off app.log, not this file. Distinguishing "a secret
# that happens to be reachable" from "the secret that matters" is the point.
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
    # THE LEAK: the failed-auth handler logs the attempted credentials
    # "for debugging" instead of redacting the password. This is the one
    # line a student actually needs.
    f"2026-10-05 09:31:47 WARN  basic auth failed for /internal/metrics:"
    f" user={METRICS_USER} pass={METRICS_PASS}",
    "2026-10-05 09:31:48 ERROR metrics-agent giving up after 1 attempt, will retry in 300s",
    "2026-10-05 09:36:48 INFO  metrics-agent polled /internal/metrics (200)",
]


@app.get("/")
def index():
    return (
        "<h1>Ops Dashboard</h1>"
        '<p><a href="/status">Status</a></p>'
    )


@app.get("/status")
def status():
    return "<p>All systems nominal.</p>"


# THE BUG: this directory was meant to be reachable only from the office
# VPN's own reverse proxy, which added the auth check. Here (no reverse
# proxy, no auth) it is wired straight into the app with none at all --
# a classic "the control lived in infrastructure that got removed/never
# ported" misconfiguration, not a code-level bug in Flask's routing. The
# fix (inline comment below) is to require auth here too.
_ADMIN_FILES = {
    "app.log": "\n".join(_LOG_LINES) + "\n",
    "ops-dashboard.conf.bak": _DB_BACKUP,
}


@app.get("/admin/logs")
def admin_logs():
    # FIX: add the same auth check /internal/metrics already has, e.g.
    #   if not _check_auth(request): return _unauthorized()
    # before listing or serving anything under here.
    listing = "".join(f'<li><a href="/admin/logs/{name}">{name}</a></li>' for name in _ADMIN_FILES)
    return f"<h1>Logs</h1><ul>{listing}</ul>"


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
    # Correctly checked -- the bug is never here. The escalation is pure
    # credential reuse: the only way to produce a valid Authorization
    # header is to have read METRICS_PASS off the leaked log line above.
    if not _check_auth(request):
        return _unauthorized()
    return f"<p>uptime_seconds=118203 requests_total=48217</p><p>{FLAG}</p>"


# -- Decoy listener (plan §7.3's nmap primer) --------------------------------
# NOT a real sshd -- see weak-auth-portal/app.py's identical comment for why
# a genuine one is impossible under this range's hardening. Speaks just
# enough of the banner to fingerprint under `nmap -sV`, then closes.
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
