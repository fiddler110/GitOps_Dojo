"""Settings from the environment, extension manifests, port layout and audit logging for the allocator.
"""
import datetime
import json
import os
import re
import threading



PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost")
# Marks the session cookie Secure whenever the public deployment actually
# terminates TLS (see gateway/README's Deployment scenarios) -- the browser
# then refuses to ever send it over a plain-HTTP connection, e.g. to a
# spoofed same-name host on an open network. No effect (and no downside)
# on the plain-HTTP localhost path, since that's never HTTPS to begin with.
COOKIE_SECURE = PUBLIC_BASE_URL.startswith("https://")
# The gateway's own address when another proxy terminates TLS in front of it
# (e.g. http://:8080); empty means the gateway serves PUBLIC_BASE_URL itself.
GATEWAY_LISTEN = os.environ.get("GATEWAY_LISTEN", "")

STUDENT_COUNT = int(os.environ.get("STUDENT_COUNT", "30"))
STUDENT_PREFIX = os.environ.get("STUDENT_PREFIX", "student")
# Demo/test bots (--test, see engine/run.sh and README.md's "Demo bots"
# section): unlike real students, these never go through /assign -- they're
# always shown in the roster (see handle_sessions_api) so a facilitator can
# watch/Release them without any browser having "joined" as them. 0 (the
# default) disables this feature entirely.
BOT_COUNT = int(os.environ.get("BOT_COUNT", "0"))
BOT_PREFIX = os.environ.get("BOT_PREFIX", "testuser")
WORKSHOP_NAME = os.environ.get("WORKSHOP_NAME", "Workshop Lab")
# Must match web-terminal's actual facilitator Linux account -- entrypoint.sh
# and docker-compose.yml both default this to "root", not "facilitator", so
# it has to come from the same env var, never be hardcoded here.
FACILITATOR_USERNAME = os.environ.get("FACILITATOR_USERNAME", "root")

# "web" (VS Code in the browser plus a tmux terminal) or "zellij" (a Zellij terminal
# only). Must match web-terminal's own TERMINAL_FLAVOR (docker-compose.yml passes the
# same value to both). With "zellij" there is no IDE, so its tab, landing card and
# /ide route are not offered.
TERMINAL_FLAVOR = os.environ.get("TERMINAL_FLAVOR", "web")
HAS_IDE = TERMINAL_FLAVOR != "zellij"


_audit_lock = threading.Lock()


def audit(event, **fields):
    """One JSON line on stdout per identity or control-plane decision
    (remediation T1.4, FIND-13): who, what, on which target, with what
    result. Never a secret: no tokens, passwords or cookies. Student names
    are student-typed; json.dumps escapes them."""
    rec = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds"),
           "event": event}
    rec.update(fields)
    line = json.dumps(rec, separators=(",", ":"))
    with _audit_lock:  # one whole line at a time from concurrent handlers
        print(line, flush=True)


# /auth-check runs once per request VS Code or ttyd makes (every asset), so
# logging each 200 would flood the log. Log every non-200, and a 200 only
# when it's the first for that (event, account, tool) or follows a non-200.
_last_check = {}
_last_check_lock = threading.Lock()


def audit_check(event, account, tool, status, **fields):
    key = (event, account, tool)
    with _last_check_lock:
        log = status != 200 or _last_check.get(key) != 200
        _last_check[key] = status
    if log:
        audit(event, account=account, tool=tool, result=status, **fields)


TTYD_USERNAME = os.environ.get("TTYD_USERNAME", "")
TTYD_PASSWORD = os.environ.get("TTYD_PASSWORD", "")
FACILITATOR_PASSWORD = os.environ.get("FACILITATOR_PASSWORD", "")
WORKSHOP_DESCRIPTION = os.environ.get("WORKSHOP_DESCRIPTION", "").strip()
# Deep-links the landing page's Forgejo button straight at the seeded
# workshop repo -- must match bootstrap.sh's FORGEJO_ORG/FORGEJO_REPO
# defaults (see docker-compose.yml's bootstrap service), not hardcoded here.
FORGEJO_ORG = os.environ.get("FORGEJO_ORG", "training")
FORGEJO_REPO = os.environ.get("FORGEJO_REPO", "sample-training-repo")
# SSO into Forgejo (see /forgejo-login below) signs a student in with their
# own password, forgejo_password(sid) from dojo_secret.py: the same one
# bootstrap.sh created the account with (remediation T2.1b, D13).
FORGEJO_ADMIN_USER = os.environ["FORGEJO_ADMIN_USER"]
FORGEJO_ADMIN_PASSWORD = os.environ["FORGEJO_ADMIN_PASSWORD"]
# Shared secret sent on every call to web-terminal's control API (see
# control_request() below) -- proves these calls actually come from the
# allocator, not some other container on the internal workshop_lab network.
# Must match web-terminal's own CONTROL_TOKEN (workspace-control.py).
CONTROL_TOKEN = os.environ["CONTROL_TOKEN"]
# Shared secret gateway/Caddyfile sends (via header_up X-Gateway-Token) on
# EVERY request it proxies to this process -- proves the request actually
# came through Caddy, not directly from some other container on the shared
# workshop_lab network (allocator must share that network with web-terminal
# and git-server for its own legitimate outbound calls -- see
# control_request()/forgejo_login_request() below -- and Docker/Podman
# bridge networks are not directional, so anything reachable BY allocator
# can equally reach allocator back). Without this check, resolve_identity()
# below trusting X-Auth-User would be forgeable by any process inside
# web-terminal (e.g. a student's own shell) simply by sending its own
# X-Auth-User: root header straight to http://allocator:8080/. Required, no
# default -- same fail-fast pattern as CONTROL_TOKEN above. Must match
# gateway's own GATEWAY_TOKEN (gateway/Caddyfile).
GATEWAY_TOKEN = os.environ["GATEWAY_TOKEN"]

# Workshop/module extensions (docs/archive/MODULES-PLAN.md §3): cards, /admin tabs,
# route gates and status checks, already checked by render_extensions.py
# (run.sh, before start) and mounted read-only. Missing means none.
EXTENSIONS_FILE = os.environ.get("EXTENSIONS_FILE", "/etc/dojo/extensions/extensions.json")


def load_extensions(path=EXTENSIONS_FILE):
    empty = {"cards": [], "admin_tabs": [], "widgets": [], "scripts": [], "routes": [], "status_checks": [],
             "resets": []}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return empty
    return {k: list(data.get(k, [])) for k in empty}


EXTENSIONS = load_extensions()
EXT_ROUTES = {r["id"]: r for r in EXTENSIONS["routes"]}
# {user} in a route's host template stands for a whole DNS label.
DNS_LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")

WEB_TERMINAL_HOST = "web-terminal"
CONTROL_PORT = 7682
CONTROL_TIMEOUT = 3.0

GIT_SERVER_HOST = "git-server"
GIT_SERVER_PORT = 3000

IDE_PORT_BASE = 9000
TERM_PORT_BASE = 9500
FACILITATOR_IDE_PORT = 9099
FACILITATOR_TERM_PORT = 9599
# Facilitator's read-only mirror of a student's term session -- must match
# WATCH_PORT_BASE in web-terminal/workspace-control.py, which actually
# spawns the ttyd process on this port.
WATCH_PORT_BASE = 9600
# Same, for demo bots -- must match BOT_WATCH_PORT_BASE in
# web-terminal/workspace-control.py.
BOT_WATCH_PORT_BASE = 9800
# Same collision fix as watch_port() below, mirrored here for ide_port()/
# term_port() -- must match BOT_IDE_PORT_BASE/BOT_TERM_PORT_BASE in
# web-terminal/workspace-control.py. Not currently reachable (resolve_identity()
# never returns a bot id as `username` -- only a real student id or the
# facilitator; a bot's own login counts only in handle_route_check), but kept
# symmetric per this file's own "must match" comments.
BOT_IDE_PORT_BASE = 9700
BOT_TERM_PORT_BASE = 9750

COOKIE_NAME = "dojo_session"

STUDENT_IDS = [f"{STUDENT_PREFIX}{n:02d}" for n in range(1, STUDENT_COUNT + 1)]
BOT_IDS = [f"{BOT_PREFIX}{n}" for n in range(1, BOT_COUNT + 1)]
# Demo bots' Forgejo password (bootstrap.sh and web-terminal use the same).
BOT_PASSWORD = os.environ.get("BOT_PASSWORD", "testuser123")
STATUS_DETAIL_MAX = 200


def _short(text):
    text = " ".join(str(text).split())
    return text[:STATUS_DETAIL_MAX] or "check failed"
