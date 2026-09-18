#!/usr/bin/env python3
"""Internal-only control plane for per-student code-server/ttyd processes.

Runs as root (same trust model this container already had when it ran
`exec ttyd ... login` continuously -- see entrypoint.sh) inside the
web-terminal container, listening on the workshop_lab-internal network only
(never published through the gateway). The allocator service is the only
caller, deciding *who* gets a workspace; this process only manages the OS
processes that back it, so no docker.sock or cross-container privilege is
ever needed (see workshops/dns-as-code/compose/runner/Dockerfile for why
that's a hard constraint in this stack).

Uses ThreadingHTTPServer deliberately (unlike the allocator): the only
shared mutable state here is `running`, guarded by a lock, and each
handler's real work is a short-lived subprocess/pgrep call -- serializing
those on one thread would make Release feel laggy for no benefit.
"""
import hmac
import http.server
import os
import re
import socket
import subprocess
import threading
import time
import urllib.parse

IDE_PORT_BASE = 9000
TERM_PORT_BASE = 9500
FACILITATOR_IDE_PORT = 9099
FACILITATOR_TERM_PORT = 9599

# Facilitator "watch" mirror of a student's terminal -- a second, read-only
# ttyd attached to the same tmux session as their TERM_PORT_BASE one (see
# start_watch below). Not offered for the facilitator's own account, so no
# FACILITATOR_WATCH_PORT constant.
WATCH_PORT_BASE = 9600

# Separate watch port range for demo/test bots (see BOT_PREFIX above) --
# student_number() below extracts the trailing digits from a username
# regardless of its prefix, so testuser1 and student01 would otherwise both
# resolve to WATCH_PORT_BASE + 1 and collide. STUDENT_COUNT is capped at 99
# (see entrypoint.sh), so WATCH_PORT_BASE's range never reaches here.
BOT_WATCH_PORT_BASE = 9800

# Same collision, same fix, for port_for()'s IDE/term ports -- without
# these, a bot (e.g. testuser1) and a same-numbered student (student01)
# would resolve to the exact same IDE_PORT_BASE/TERM_PORT_BASE port.
BOT_IDE_PORT_BASE = 9700
BOT_TERM_PORT_BASE = 9750

# tmux session name every `term` ttyd process runs inside. Fixed and shared
# across accounts on purpose: tmux sessions are namespaced per-uid (each
# account gets its own socket under /tmp/tmux-<uid>/), so this never
# collides between students.
TMUX_SESSION = "main"

# Must match the allocator's view of these same values -- entrypoint.sh and
# docker-compose.yml default FACILITATOR_USERNAME to "root", not
# "facilitator", and STUDENT_PREFIX/BOT_PREFIX are configurable too, so none
# of these can be hardcoded here.
FACILITATOR_USERNAME = os.environ.get("FACILITATOR_USERNAME", "root")
STUDENT_PREFIX = os.environ.get("STUDENT_PREFIX", "student")
# Demo/test bot accounts (--test, see entrypoint.sh and README.md's "Demo
# bots" section) -- a second account namespace, same numbering scheme as
# students but never competing with them for a slot. Included here so
# start/stop/status calls for a botN account validate the same way a
# studentNN one does.
BOT_PREFIX = os.environ.get("BOT_PREFIX", "testuser")

# Shared secret proving a request actually came from the allocator, not some
# other container reachable on the internal workshop_lab network (e.g. a
# workshop's own Forgejo Actions runner executing student-authored CI --
# see docker-compose.yml). Required, no default -- fail fast at startup if
# unset, same pattern as allocator/server.py's own required secrets.
CONTROL_TOKEN = os.environ["CONTROL_TOKEN"]

USERNAME_RE = re.compile(
    rf"^({re.escape(FACILITATOR_USERNAME)}|{re.escape(STUDENT_PREFIX)}\d+|{re.escape(BOT_PREFIX)}\d+)$"
)

# Shared, read-only, preinstalled-at-build-time extension set (see
# web-terminal/Dockerfile) -- no per-user copy, no runtime Marketplace
# access (this container has no route to the internet at all once the
# stack is up; see docker-compose.yml's workshop_lab network).
CODE_SERVER_EXTENSIONS_DIR = "/opt/code-server-extensions"

# Caps each code-server process's V8 heap so one student can't quietly
# balloon past the container-wide mem_limit backstop (docker-compose.yml)
# on their own -- a safety net under that ceiling, not a replacement for
# it. Override via env if a workshop's files/extensions genuinely need
# more headroom.
CODE_SERVER_MAX_HEAP_MB = os.environ.get("CODE_SERVER_MAX_HEAP_MB", "384")

running = {}  # (tool, username) -> subprocess.Popen
running_lock = threading.Lock()
watch_target = {}  # username -> tmux session name the running watch ttyd is attached to


def valid_username(username):
    return bool(USERNAME_RE.match(username))


def student_number(username):
    return int(re.search(r"\d+", username).group())


def port_for(tool, username):
    if username == FACILITATOR_USERNAME:
        return FACILITATOR_IDE_PORT if tool == "ide" else FACILITATOR_TERM_PORT
    if username.startswith(BOT_PREFIX):
        return (BOT_IDE_PORT_BASE if tool == "ide" else BOT_TERM_PORT_BASE) + student_number(username)
    n = student_number(username)
    return (IDE_PORT_BASE if tool == "ide" else TERM_PORT_BASE) + n


def watch_port(username):
    if username.startswith(BOT_PREFIX):
        return BOT_WATCH_PORT_BASE + student_number(username)
    return WATCH_PORT_BASE + student_number(username)


def is_alive(username):
    return subprocess.run(["pgrep", "-u", username], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex(("127.0.0.1", port)) == 0


def start_workspace(tool, username):
    with running_lock:
        key = (tool, username)
        proc = running.get(key)
        if proc is not None and proc.poll() is None:
            return  # already running

        port = port_for(tool, username)
        home = f"/home/{username}"
        if tool == "ide":
            cmd = [
                "su", "-", username, "-c",
                f"export NODE_OPTIONS='--max-old-space-size={CODE_SERVER_MAX_HEAP_MB}'; "
                f"exec code-server --bind-addr 0.0.0.0:{port} --auth none "
                f"--disable-telemetry --disable-update-check --disable-workspace-trust "
                f"--extensions-dir {CODE_SERVER_EXTENSIONS_DIR} {home}/lab",
            ]
        else:
            # Wrapped in tmux, not a bare login shell: ttyd execs this
            # command fresh for every websocket connection, so without
            # tmux a second connection (e.g. a facilitator's watch tile)
            # would land in its own brand-new shell instead of seeing the
            # student's actual live session. `new-session -A` creates the
            # session on the first connect and reattaches on every one
            # after, including the student's own reconnects/extra tabs.
            cmd = ["ttyd", "-p", str(port), "-W", "su", "-", username,
                   "-c", f"tmux new-session -A -s {TMUX_SESSION}"]

        running[key] = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Give the process a moment to actually bind before Caddy's first proxy
    # attempt -- best-effort only, a reload fixes a still-cold start. Poll
    # the port itself, not is_alive(username): ttyd's listener runs as
    # root (only the per-connection `su - <username>` child it spawns once
    # a browser connects runs as the student), so pgrep -u would never
    # observe the listener itself as "up".
    for _ in range(50):
        if port_open(port):
            return
        time.sleep(0.1)


def list_sessions(username):
    """This student's tmux sessions as (name, last_activity_unix_ts) pairs
    -- `main` from the standalone Terminal tool, plus one `vscode-<pid>`
    per VS Code terminal (task, split, or extra tab; see
    tmux-terminal.sh). Empty if the account has never opened a terminal at
    all."""
    result = subprocess.run(
        ["su", "-", username, "-c", "tmux list-sessions -F '#{session_name} #{session_activity}'"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return []
    sessions = []
    for line in result.stdout.splitlines():
        name, _, activity = line.rpartition(" ")
        if name and activity.isdigit():
            sessions.append((name, int(activity)))
    return sessions


def most_active_session(username):
    """Whichever of this student's tmux sessions the student is actually
    using right now, regardless of which tool (VS Code or the standalone
    Terminal button) it came from -- gates and targets start_watch. None
    if the account has never opened a terminal (nothing to attach to)."""
    sessions = list_sessions(username)
    if not sessions:
        return None
    return max(sessions, key=lambda s: s[1])[0]


def start_watch(username):
    """Read-only mirror of whichever of the student's tmux sessions was
    most recently active, for a facilitator to watch live. Deliberately no
    -W (ttyd itself won't relay keystrokes) and `tmux attach -r` (tmux also
    marks this client read-only) -- belt and suspenders against a
    facilitator tile accidentally typing into a student's shell. Returns
    False if there's nothing to watch yet.

    Re-evaluates the most-active session on every call (i.e. every time a
    facilitator (re)opens the watch tile -- see allocator/server.py's
    /auth-check-watch) and restarts the mirror if the student has since
    switched to a different terminal. This does not follow a switch that
    happens while the tile is already open and connected -- reopen it to
    re-target."""
    session = most_active_session(username)
    if session is None:
        return False

    with running_lock:
        key = ("watch", username)
        proc = running.get(key)
        if proc is not None and proc.poll() is None and watch_target.get(username) == session:
            return True  # already watching the right session
        if proc is not None and proc.poll() is None:
            # Student switched terminals -- retarget. Wait for the old
            # ttyd to actually release the port before spawning its
            # replacement on the same one, or a request that lands in
            # between can hit a dead socket (502) while the old process
            # is still tearing down.
            proc.kill()
            proc.wait()

        port = watch_port(username)
        cmd = ["ttyd", "-p", str(port), "su", "-", username,
               "-c", f"tmux attach -t {session} -r"]
        running[key] = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        watch_target[username] = session

    for _ in range(50):
        if port_open(port):
            break
        time.sleep(0.1)
    return True


def stop_user(username):
    with running_lock:
        for key in list(running):
            if key[1] == username:
                del running[key]
        watch_target.pop(username, None)
    subprocess.run(["pkill", "-KILL", "-u", username], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def reap_children():
    """This process is the container's PID 1 (see entrypoint.sh); nothing
    else reaps the su/ttyd/code-server children we fork, so do it ourselves
    to avoid zombie accumulation over a long-running workshop."""
    while True:
        try:
            pid, _status = os.waitpid(-1, 0)
        except ChildProcessError:
            time.sleep(1)


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "WorkspaceControl/1.0"

    def log_message(self, fmt, *args):
        pass

    def send_json_ok(self, data=None):
        import json
        body = json.dumps(data or {}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        token = self.headers.get("X-Control-Token", "")
        return hmac.compare_digest(token, CONTROL_TOKEN)

    def do_GET(self):
        if not self.authorized():
            self.send_response(403)
            self.end_headers()
            return
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/status":
            qs = urllib.parse.parse_qs(parsed.query)
            users = (qs.get("users") or [""])[0].split(",")
            # "watchable" mirrors start_watch's own readiness check
            # (most_active_session != None) without the side effect of
            # actually spawning a watch ttyd -- the roster poll uses it to
            # know when a freshly-joined student's tile can connect its
            # iframe on its own, instead of waiting for a manual reload.
            result = {
                u: {"active": is_alive(u), "watchable": most_active_session(u) is not None}
                for u in users if u and valid_username(u)
            }
            self.send_json_ok(result)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if not self.authorized():
            self.send_response(403)
            self.end_headers()
            return
        parsed = urllib.parse.urlsplit(self.path)
        parts = parsed.path.strip("/").split("/")

        if len(parts) == 3 and parts[0] == "start":
            _, tool, username = parts
            if tool not in ("ide", "term", "watch") or not valid_username(username):
                self.send_response(400)
                self.end_headers()
                return
            if tool == "watch":
                # No facilitator self-watch -- watch_port()/student_number()
                # assume a studentNN account, and it wouldn't mean anything
                # anyway.
                if username == FACILITATOR_USERNAME:
                    self.send_response(400)
                    self.end_headers()
                    return
                if not start_watch(username):
                    self.send_response(409)  # no term session for this student yet
                    self.end_headers()
                    return
            else:
                start_workspace(tool, username)
            self.send_json_ok()
            return

        if len(parts) == 2 and parts[0] == "stop":
            username = parts[1]
            if not valid_username(username):
                self.send_response(400)
                self.end_headers()
                return
            stop_user(username)
            self.send_json_ok()
            return

        self.send_response(404)
        self.end_headers()


def main():
    threading.Thread(target=reap_children, daemon=True).start()
    server = http.server.ThreadingHTTPServer(("0.0.0.0", 7682), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
