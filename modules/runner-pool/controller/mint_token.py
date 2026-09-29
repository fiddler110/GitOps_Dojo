#!/usr/bin/env python3
"""One-shot: mint the runner controller's scoped Forgejo token (T5.2c, FIND-16).

Signs in once with the admin login (this service alone holds it), deletes any
earlier "runner-controller" token, creates a new one with only the admin scope
the runner API needs, and writes it 0600 to $FORGEJO_TOKEN_FILE. The controller
then runs without FORGEJO_ADMIN_PASSWORD, so a leak of its environment or
memory gives a revocable token, not the admin login (web UI, SSO, every scope).
Waits for Forgejo's bootstrap to create the admin user. Nothing goes in argv.
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = (os.environ.get("FORGEJO_URL") or "http://git-server:3000").rstrip("/") + "/api/v1"
USER = os.environ["FORGEJO_ADMIN_USER"]
PASSWORD = os.environ["FORGEJO_ADMIN_PASSWORD"]
OUT = os.environ.get("FORGEJO_TOKEN_FILE") or "/token/forgejo-token"
NAME = "runner-controller"
SCOPES = ["write:admin"]
AUTH = "Basic " + base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Authorization": AUTH, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, None
    except (urllib.error.URLError, OSError):
        return 0, None


def main():
    deadline = time.time() + int(os.environ.get("MINT_WAIT", "300"))
    while True:
        status, _ = call("DELETE", f"/users/{USER}/tokens/{NAME}")
        if status in (204, 404):
            break
        if time.time() > deadline:
            print(f"[runner-token-init] Forgejo did not accept the admin login (last HTTP {status})", file=sys.stderr)
            return 1
        time.sleep(3)
    status, d = call("POST", f"/users/{USER}/tokens", {"name": NAME, "scopes": SCOPES})
    if status != 201 or not d or not d.get("sha1"):
        print(f"[runner-token-init] token create failed: HTTP {status}", file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(d["sha1"])
    os.replace(tmp, OUT)
    print("[runner-token-init] token written", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
