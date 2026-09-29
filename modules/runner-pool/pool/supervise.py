#!/usr/bin/env python3
"""runner-pool supervisor: runs single-use Forgejo Actions runners.

The controller (../controller/controller.py) registers each runner with
Forgejo and drops its config in /spool/start/<name>.yaml. For each one this
starts `forgejo-runner one-job --wait` as a fresh Linux user of the same name,
inside its own user + PID namespace (VAULT-FUNDAMENTALS-PLAN.md §6.2, T0.8):
a home only it can read, umask 077, its own TMPDIR, prlimit caps, and a view
of its own processes only. When the job ends (or the controller asks for an
idle runner to go, with /spool/stop/<name>) it kills whatever the user left
running, deletes its files in the shared temp dirs and removes the user with
its home, so the next job starts from nothing.

It writes what it sees to /spool/state.json every second: per runner
`starting`, `idle`, `busy` (with the repo), then `done`, `removed` or
`failed`. It has no network listener, and never talks to Forgejo itself;
job output goes to Forgejo, not to this process's log.
"""
import collections
import json
import os
import pwd
import re
import shutil
import signal
import subprocess
import sys
import threading
import time

SPOOL = os.environ.get("SPOOL_DIR", "/spool")
START_DIR = os.path.join(SPOOL, "start")
STOP_DIR = os.path.join(SPOOL, "stop")
STATE_FILE = os.path.join(SPOOL, "state.json")
# Runner names come from the controller; they become Linux user names, so
# only this shape is accepted.
NAME_RE = re.compile(r"^pool-[a-z0-9]{1,16}$")
# forgejo-runner's line when it has claimed a job (T0.7).
TASK_RE = re.compile(r"task (\d+) repo is (\S+)")
# A runner still up this long after start, with no error, is waiting for a job.
IDLE_AFTER = 3
# Finished runners stay in state.json this long, for the panel's history.
KEEP_FINISHED = 600
SHIM_CA = "/shim/caddy/pki/authorities/local/root.crt"
SHIM_CA_INSTALLED = "/usr/local/share/ca-certificates/runner-pool-shim.crt"
TEMP_DIRS = ("/tmp", "/var/tmp", "/dev/shm")
CLEAN_ENV = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"}


def log(msg):
    print(f"[supervise] {msg}", flush=True)


def limits():
    """prlimit flags for every process of a runner (module.env)."""
    flags = [f"--nproc={int(os.environ.get('RUNNER_NPROC') or 256)}",
             f"--nofile={int(os.environ.get('RUNNER_NOFILE') or 1024)}"]
    if os.environ.get("RUNNER_AS"):
        flags.append(f"--as={int(os.environ['RUNNER_AS'])}")
    return " ".join(flags)


# useradd and userdel lock /etc/passwd: runners starting or finishing
# together must take turns (T0.8).
users_lock = threading.Lock()
# Guards `runners` and every Runner's fields.
lock = threading.Lock()


class Runner:
    def __init__(self, name):
        self.name = name
        self.state = "starting"
        self.repo = None
        self.task = None
        self.started = time.time()
        self.since = self.started
        self.exit = None
        self.detail = ""
        self.stop_requested = False
        self.proc = None
        self.tail = collections.deque(maxlen=20)

    def to_json(self):
        return {"state": self.state, "repo": self.repo, "task": self.task, "started": self.started,
                "since": self.since, "exit": self.exit, "detail": self.detail}


runners = {}


def run(args, **kw):
    return subprocess.run(args, env=CLEAN_ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kw)


def create_user(name, config):
    with users_lock:
        # UIDs well clear of any the image uses (its /data belonged to 1000).
        out = run(["useradd", "-m", "-K", "UMASK=077", "-K", "UID_MIN=20000", "-K", "UID_MAX=29999",
                   "-s", "/bin/sh", name])
    if out.returncode != 0:
        raise RuntimeError(f"useradd: {out.stdout.strip()[:200]}")
    pw = pwd.getpwnam(name)
    home = pw.pw_dir
    os.chmod(home, 0o700)
    path = os.path.join(home, "config.yaml")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(config)
    os.chown(path, pw.pw_uid, pw.pw_gid)
    tmp = os.path.join(home, "tmp")
    os.mkdir(tmp, 0o700)
    os.chown(tmp, pw.pw_uid, pw.pw_gid)


def remove_user(name):
    """Kill everything the user runs, delete its files outside its home, then
    the user and its home. Returns an error string, or "" when clean."""
    try:
        uid = pwd.getpwnam(name).pw_uid
    except KeyError:
        return ""
    run(["su", name, "-s", "/bin/sh", "-c", "kill -9 -1"])
    for top in TEMP_DIRS:
        try:
            entries = os.listdir(top)
        except OSError:
            continue
        for entry in entries:
            path = os.path.join(top, entry)
            try:
                if os.lstat(path).st_uid != uid:
                    continue
                if os.path.isdir(path) and not os.path.islink(path):
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    os.unlink(path)
            except OSError:
                pass
    with users_lock:
        out = run(["userdel", "-r", name])
    if out.returncode not in (0, 12):  # 12: home already gone
        return f"userdel: {out.stdout.strip()[:200]}"
    return ""


def watch(r):
    """Reader thread: follows the runner's output, then cleans up after it."""
    for line in r.proc.stdout:
        line = line.rstrip("\n")
        print(f"[{r.name}] {line}", flush=True)
        m = TASK_RE.search(line)
        with lock:
            r.tail.append(line)
            if m and r.task is None:
                r.task, r.repo = int(m.group(1)), m.group(2)
                r.state, r.since = "busy", time.time()
    rc = r.proc.wait()
    err = remove_user(r.name)
    with lock:
        r.exit = rc
        if r.task is not None:
            # A job was run. Exit codes after a cancelled job are not errors
            # (VAULT-FUNDAMENTALS-PLAN.md §14: the runner retries its log upload, then exits).
            r.state = "done"
        elif r.stop_requested:
            r.state = "removed"
        else:
            r.state = "failed"
            last = next((l for l in reversed(r.tail) if l.strip()), "")
            r.detail = f"exited ({rc}) before taking a job: {last[-160:]}"
        if err:
            r.state = "failed"
            r.detail = (r.detail + "; " if r.detail else "") + err
        r.since = time.time()
    log(f"{r.name} {r.state} (exit {rc})")


def start(name, config):
    r = Runner(name)
    with lock:
        runners[name] = r
    try:
        create_user(name, config)
        inner = ('umask 077; cd; export TMPDIR="$HOME/tmp"; '
                 f'exec prlimit {limits()} -- unshare -U --map-current-user -p -f --mount-proc '
                 'forgejo-runner one-job --config "$HOME/config.yaml" --wait')
        r.proc = subprocess.Popen(["su", name, "-s", "/bin/sh", "-c", inner], env=CLEAN_ENV,
                                  stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, errors="replace", start_new_session=True)
    except Exception as e:  # noqa: BLE001 - any failure is shown on the panel
        err = remove_user(name)
        with lock:
            r.state, r.since = "failed", time.time()
            r.detail = f"failed to start: {e}" + (f"; {err}" if err else "")
        log(f"{name} failed to start: {e}")
        return
    threading.Thread(target=watch, args=(r,), daemon=True).start()
    log(f"{name} started")


def stop(name):
    """Stop an idle runner. A busy one is never stopped: its job runs on."""
    with lock:
        r = runners.get(name)
        if r is None or r.state not in ("starting", "idle") or r.proc is None:
            return
        r.stop_requested = True
    run(["su", name, "-s", "/bin/sh", "-c", "kill -9 -1"])
    log(f"{name} stop requested")


def shim_ca_ready():
    """On an https:// name, jobs reach Forgejo through the shim, which serves
    with its own CA: trust it before starting any runner."""
    if not os.environ.get("PUBLIC_BASE_URL", "").startswith("https://"):
        return True
    if os.path.exists(SHIM_CA_INSTALLED):
        return True
    if not os.path.exists(SHIM_CA):
        return False
    shutil.copyfile(SHIM_CA, SHIM_CA_INSTALLED)
    out = run(["update-ca-certificates"])
    if out.returncode != 0:
        os.unlink(SHIM_CA_INSTALLED)
        log(f"update-ca-certificates failed: {out.stdout.strip()[:200]}")
        return False
    log("trusting the shim's CA")
    return True


def take_files(directory):
    """(name, path) for each well-named file in directory; others are removed."""
    try:
        entries = sorted(os.listdir(directory))
    except OSError:
        return []
    out = []
    for entry in entries:
        path = os.path.join(directory, entry)
        name = entry[:-5] if entry.endswith(".yaml") else entry
        if entry.startswith(".") or entry.endswith(".tmp"):
            continue  # being written
        if not NAME_RE.match(name):
            os.unlink(path)
            continue
        out.append((name, path))
    return out


def write_state(ca_ready):
    now = time.time()
    with lock:
        for name in [n for n, r in runners.items()
                     if r.state in ("done", "removed", "failed") and now - r.since > KEEP_FINISHED]:
            del runners[name]
        for r in runners.values():
            if r.state == "starting" and r.proc is not None and now - r.started >= IDLE_AFTER:
                r.state, r.since = "idle", now
        doc = {"updated": now, "shim_ca": "ready" if ca_ready else "waiting",
               "runners": {n: r.to_json() for n, r in runners.items()}}
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(doc, f)
    os.replace(tmp, STATE_FILE)


def clean_leftovers():
    """After a restart of this container its old runners are gone, but their
    users and files may not be."""
    for pw in pwd.getpwall():
        if NAME_RE.match(pw.pw_name):
            err = remove_user(pw.pw_name)
            log(f"removed leftover runner user {pw.pw_name}" + (f" ({err})" if err else ""))
    for _, path in take_files(STOP_DIR):
        os.unlink(path)


def main():
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    for d in (SPOOL, START_DIR, STOP_DIR):
        os.makedirs(d, exist_ok=True)
        os.chmod(d, 0o700)
    # The runner image's working directory belongs to uid 1000; a volume
    # every runner shares must not be writable by any of them.
    os.chown("/data", 0, 0)
    os.chmod("/data", 0o755)
    clean_leftovers()
    log("ready")
    while True:
        ca_ready = shim_ca_ready()
        if ca_ready:
            for name, path in take_files(START_DIR):
                with open(path) as f:
                    config = f.read()
                os.unlink(path)
                with lock:
                    known = name in runners
                if not known:
                    start(name, config)
        for name, path in take_files(STOP_DIR):
            os.unlink(path)
            stop(name)
        write_state(ca_ready)
        time.sleep(1)


if __name__ == "__main__":
    main()
