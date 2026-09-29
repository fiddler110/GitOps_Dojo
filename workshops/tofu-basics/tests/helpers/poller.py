#!/usr/bin/env python3
"""Portal pollers for the load test. Runs INSIDE the cloud-api container (see cloud_http.py for why), for the
whole load run, as a background `podman exec`:

    podman exec workshop_cloud_api python3 -c "$(cat poller.py)" --duration 900 --stop-file /tmp/x --users student01,student02

It imitates what the class does to the control plane while it works: the portal SPA polls every ~3 s.
Threads, one each:
    overview   GET /cloud/api/overview?scope=class   as each user in --users, every --interval (default 3 s)
    progress   GET /cloud/api/admin/progress         as the facilitator, every --interval (the facilitator board)
    readyz     GET /readyz                           no identity, every --readyz-interval (default 2 s)

Output, on stdout, one CSV row per request (flushed at once):  epoch,kind,who,status,ms
status 0 = could not connect. The token is read from this container's environment and never printed.
It stops when --stop-file exists, after --duration seconds at the latest (so a crashed test cannot leave it
running), or when stdout is closed.
"""
import argparse
import os
import sys
import threading
import time
import urllib.error
import urllib.request

LOCK = threading.Lock()
STOP = threading.Event()


def request(path, user):
    port = os.environ.get("CLOUD_HTTP_PORT", "8080")
    headers = {}
    if user:
        headers = {"X-Auth-User": user, "X-Gateway-Token": os.environ.get("GATEWAY_TOKEN", "")}
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers=headers)
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:
        exc.read()
        status = exc.code
    except (urllib.error.URLError, OSError):
        status = 0
    return status, (time.monotonic() - started) * 1000


def emit(kind, who, status, ms):
    line = f"{time.time():.3f},{kind},{who},{status},{ms:.1f}\n"
    with LOCK:
        try:
            sys.stdout.write(line)
            sys.stdout.flush()
        except (BrokenPipeError, OSError, ValueError):
            STOP.set()


def poll(kind, path, user, who, interval, delay):
    if STOP.wait(delay):
        return
    while not STOP.is_set():
        status, ms = request(path, user)
        emit(kind, who, status, ms)
        if STOP.wait(interval):
            return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=900)
    ap.add_argument("--stop-file", default="")
    ap.add_argument("--users", default="student01")
    ap.add_argument("--interval", type=float, default=3.0)
    ap.add_argument("--readyz-interval", type=float, default=2.0)
    ap.add_argument("--no-progress", action="store_true")
    args = ap.parse_args()

    users = [u for u in args.users.split(",") if u]
    facilitator = os.environ.get("FACILITATOR_USERNAME", "root")
    sys.stdout.write("epoch,kind,who,status,ms\n")
    sys.stdout.flush()

    threads = []
    for i, user in enumerate(users):  # spread the pollers over the interval, like a class that did not click in sync
        threads.append(threading.Thread(target=poll, daemon=True, args=(
            "overview", "/cloud/api/overview?scope=class", user, user, args.interval,
            args.interval * i / max(len(users), 1))))
    if not args.no_progress:
        threads.append(threading.Thread(target=poll, daemon=True, args=(
            "progress", "/cloud/api/admin/progress", facilitator, "facilitator", args.interval, 0.5)))
    threads.append(threading.Thread(target=poll, daemon=True, args=(
        "readyz", "/readyz", "", "-", args.readyz_interval, 0.0)))
    for t in threads:
        t.start()

    deadline = time.monotonic() + args.duration
    while not STOP.is_set() and time.monotonic() < deadline:
        if args.stop_file and os.path.exists(args.stop_file):
            break
        time.sleep(0.5)
    STOP.set()
    for t in threads:
        t.join(timeout=35)
    return 0


if __name__ == "__main__":
    sys.exit(main())
