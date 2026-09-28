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
import datetime
import hmac
import http.server
import json
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

# V8 flags for every node process a student's code-server runs. They are
# passed on node's command line, not through NODE_OPTIONS, because
# code-server strips NODE_OPTIONS from the environment of its extension
# host, pty host and file watcher, but forks all three (and its own wrapper
# forks the server) with the parent's execArgv. Verified via
# /proc/<pid>/cmdline: the extension host, the largest process per
# student, inherits them. Language servers are forked by extensions with
# their own execArgv, so they only get MALLOC_ARENA_MAX from the
# environment.
#
#   --max-old-space-size: caps each process's heap, a safety net under the
#     container-wide mem_limit backstop (docker-compose.yml), not a
#     replacement for it. Per process, so a student's worst case is several
#     times this; see scripts/capacity-calc.sh's CEILING_PER_STUDENT_MB.
#   --max-semi-space-size=2, --optimize-for-size, MALLOC_ARENA_MAX=2: a
#     smaller young generation, V8 preferring memory over speed, and fewer
#     glibc malloc arenas. Measured together on one student (PSS, README +
#     preview, a .yaml, a .tf and the terminal open): 350 -> 316 MB for
#     --optimize-for-size on top of the other two, with every capped
#     process smaller. Costs a little CPU, which lab-sized files don't
#     notice.
#
# Override the cap via env if a workshop's files/extensions genuinely need
# more headroom.
CODE_SERVER_MAX_HEAP_MB = os.environ.get("CODE_SERVER_MAX_HEAP_MB", "384")
if not (CODE_SERVER_MAX_HEAP_MB.isascii() and CODE_SERVER_MAX_HEAP_MB.isdigit()):
    # Interpolated into a shell command below, same as _seconds_env's values.
    raise SystemExit(f"CODE_SERVER_MAX_HEAP_MB must be a whole number of MB, got {CODE_SERVER_MAX_HEAP_MB!r}")
CODE_SERVER_NODE_FLAGS = (
    f"--max-old-space-size={CODE_SERVER_MAX_HEAP_MB} --max-semi-space-size=2 --optimize-for-size"
)


def _seconds_env(name, default, floor=None):
    """Non-negative integer seconds from the environment. Interpolated into
    a shell command below, so anything but plain digits fails fast at
    startup instead of being passed through. With `floor`, a non-zero value
    must also be greater than it (0 still means "off")."""
    raw = os.environ.get(name, default)
    if not (raw.isascii() and raw.isdigit()):
        raise SystemExit(f"{name} must be a non-negative integer number of seconds, got {raw!r}")
    value = int(raw)
    if floor is not None and 0 < value <= floor:
        raise SystemExit(f"{name} must be 0 (off) or greater than {floor} seconds, got {value}")
    return value


# What a code-server keeps holding once its browser tab is gone. Measured
# with both bundled language servers active, one student is ~550 MB (PSS)
# before f977209's extension trim and node flags, ~260 MB after, and by
# default a disconnected client's extension host and language servers
# linger for 3 HOURS (VS Code's own reconnection grace time), so a closed
# tab quietly keeps most of that (~330 MB before, ~200 MB after) until then. Two independent
# timers, both counted from the tab closing (an open tab keeps both from
# firing, however idle the student is):
#
#   - RECONNECTION_GRACE: after this long disconnected, the extension host,
#     language servers, and pty host are killed (~200 MB back per student).
#     The code-server process itself stays. A client reconnecting after
#     this is told to reload its window instead of resuming in place.
#   - IDLE_TIMEOUT: after this long with no client at all, the whole
#     code-server exits (code-server judges "no client" from a heartbeat
#     that can be up to ~1 minute stale, so expect up to that much extra). Nothing is lost by it: the next /ide request goes
#     through the allocator's forward_auth -> POST /start/ide/<user> ->
#     start_workspace() below, which sees the dead process and starts a
#     fresh one, and terminals are tmux sessions owned by the student's own
#     uid, so they outlive it.
#
# Keep GRACE below IDLE_TIMEOUT or the idle exit fires first and the
# shorter grace is moot. 0 turns a timer off (VS Code's 3 h grace / no idle
# exit). Neither changes memory while students are actually connected --
# that's what CODE_SERVER_MAX_HEAP_MB and the container limit are for.
# code-server itself refuses --idle-timeout-seconds of 60 or less and would exit at once, with its output discarded
# (start_workspace below), so a too-small value is rejected here at startup instead of failing every /ide.
CODE_SERVER_IDLE_TIMEOUT_SECONDS = _seconds_env("CODE_SERVER_IDLE_TIMEOUT_SECONDS", "900", floor=60)
CODE_SERVER_RECONNECTION_GRACE_SECONDS = _seconds_env("CODE_SERVER_RECONNECTION_GRACE_SECONDS", "300")


def code_server_lifecycle_flags():
    flags = []
    if CODE_SERVER_RECONNECTION_GRACE_SECONDS:
        flags.append(f"--reconnection-grace-time {CODE_SERVER_RECONNECTION_GRACE_SECONDS}")
    if CODE_SERVER_IDLE_TIMEOUT_SECONDS:
        flags.append(f"--idle-timeout-seconds {CODE_SERVER_IDLE_TIMEOUT_SECONDS}")
    return " ".join(flags)


running = {}  # (tool, username) -> subprocess.Popen
running_lock = threading.Lock()
watch_target = {}  # username -> tmux session name the running watch ttyd is attached to
holders = {}  # username -> (Popen of su, unshare's pid, the namespace's init pid)


def audit(event, **fields):
    """One JSON line on stdout (the container log) per workspace decision,
    same shape as the allocator's (remediation T1.4, FIND-13). No secrets."""
    rec = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds"),
           "event": event}
    rec.update(fields)
    print(json.dumps(rec, separators=(",", ":")), flush=True)


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
    """Any of this account's processes running, not counting its PID
    namespace holder (which runs for as long as the account is in use)."""
    out = subprocess.run(["pgrep", "-u", username], capture_output=True, text=True).stdout.split()
    holder = holders.get(username)
    skip = {str(holder[1]), str(holder[2])} if holder else set()
    return any(pid not in skip for pid in out)


# -- A PID namespace per student (remediation T2.3b, FIND-10) -------------------
# Every account shares this container's PID namespace, so `ps` shows every
# student's command lines (tokens and passwords typed as arguments included).
# Each student's IDE and terminal instead run in a PID namespace of their own,
# with /proc remounted for it, so `ps` shows only their own processes.
#
# Root can't make one here (rootless podman gives no CAP_SYS_ADMIN), but the
# student can, inside a user namespace mapping only their own uid: the
# pattern runner-pool and AppHost already use. The kernel uid is unchanged, so
# DOJO_ISOLATION, file ownership and the SO_PEERCRED brokers see the student.
# A PID namespace ends when its first process does, so one long-lived holder
# per student keeps it (and the tmux server inside it) alive across
# connections; code-server and ttyd's shell join it with nsenter. The
# facilitator and demo bots stay outside. setuid tools (su, sudo, ping) don't
# work inside; no lab uses them. If a namespace can't be made, the workspace
# starts without one and a pidns-unavailable line is logged.

def uses_pid_namespace(username):
    return username != FACILITATOR_USERNAME and not username.startswith(BOT_PREFIX)


def _children(pid):
    kids = []
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            with open(f"/proc/{d}/stat") as f:
                ppid = int(f.read().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            continue
        if ppid == pid:
            kids.append(int(d))
    return kids


def _is_ns_init(pid):
    """True while pid is the first process of a PID namespace below ours
    (its NSpid line has our pid and 1)."""
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("NSpid:"):
                    return line.split()[1:] == [str(pid), "1"]
    except OSError:
        pass
    return False


def ensure_holder(username):
    """The init pid of this student's PID namespace, starting its holder
    first if needed; None if one can't be made. Called with running_lock held."""
    held = holders.get(username)
    if held and held[0].poll() is None and _is_ns_init(held[2]):
        return held[2]
    proc = subprocess.Popen(
        ["su", "-", username, "-c",
         "exec unshare -U --map-current-user -p -f --mount-proc --kill-child sleep infinity"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        for unshare_pid in _children(proc.pid):
            for init_pid in _children(unshare_pid):
                if _is_ns_init(init_pid):
                    holders[username] = (proc, unshare_pid, init_pid)
                    audit("pidns-start", account=username, holder=init_pid)
                    return init_pid
        if proc.poll() is not None:
            break
        time.sleep(0.1)
    proc.kill()
    holders.pop(username, None)
    audit("pidns-unavailable", account=username)
    return None


def ns_prefix(username):
    """`nsenter ... -- ` for this student's namespace, or "" (no namespace:
    the facilitator, a bot, or one couldn't be made). Called with running_lock held."""
    if not uses_pid_namespace(username):
        return ""
    init_pid = ensure_holder(username)
    if init_pid is None:
        return ""
    return f"nsenter -t {init_pid} -U -p -m --preserve-credentials -- "


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
        ns = ns_prefix(username)
        if tool == "ide":
            cmd = [
                "su", "-", username, "-c",
                f"export MALLOC_ARENA_MAX=2; "
                f"exec {ns}/usr/lib/code-server/lib/node {CODE_SERVER_NODE_FLAGS} /usr/lib/code-server "
                f"--bind-addr 0.0.0.0:{port} --auth none "
                f"--disable-telemetry --disable-update-check --disable-workspace-trust "
                f"{code_server_lifecycle_flags()} "
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
            # Inside the student's PID namespace, like the IDE (whose VS Code
            # terminals start tmux there too), so the tmux server lives there.
            cmd = ["ttyd", "-p", str(port), "-W", "-t", "fontSize=16", "su", "-", username,
                   "-c", f"exec {ns}tmux new-session -A -s {TMUX_SESSION}"]

        running[key] = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    audit("workspace-start", account=username, tool=tool, port=port)
    # Doesn't wait for the port to open -- the caller (do_POST's /start
    # handler) reports actual readiness back via port_open() right after
    # this returns, and the allocator's /auth-check uses that to decide
    # whether to proxy or show a starting page, so nothing here needs to
    # block on the spawn finishing.


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
    audit("watch-start", target=username, session=session, port=port)

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
        holders.pop(username, None)  # pkill below ends it; the next start makes a new one
    subprocess.run(["pkill", "-KILL", "-u", username], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    audit("workspace-stop", account=username)


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
                self.send_json_ok()
            else:
                start_workspace(tool, username)
                # Reported straight back to the allocator's /auth-check,
                # which proxies once this is true and shows a starting page
                # (that reloads itself) otherwise -- see server.py's
                # handle_auth_check. Checked fresh every call (not just
                # right after a spawn) since this same endpoint is hit on
                # every /ide or /term request, not only the first.
                self.send_json_ok({"ready": port_open(port_for(tool, username))})
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
