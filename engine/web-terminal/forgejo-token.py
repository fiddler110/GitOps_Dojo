#!/usr/bin/env python3
"""Signs each student's git in to Forgejo with their own token (remediation
T2.1c, D3), so no lab asks for a password.

    forgejo-token.py [--wait SECONDS] <user>...

For each student: sign in to Forgejo's API with their own password
(dojo_secret.forgejo_password), create a token named "dojo-git" (SCOPES
below), and write it to

  ~/.git-credentials  git's `store` helper (credential.helper set in
                      ~/.gitconfig), for clone/push over http://git-server:3000
  ~/.netrc            for the labs' `curl --netrc` calls to the Forgejo API

both 0600 and owned by the student. Idempotent: a token that still works is
kept; otherwise the old "dojo-git" token is deleted and a new one made (the
value is only shown once, at creation). A student reset runs this again.

The entrypoint runs it in the background for every student, with --wait:
Forgejo and its bootstrap may still be starting, so a user whose password
isn't accepted yet is retried until SECONDS have passed. Root only; nothing
here puts a password or token in an argv.
"""
import base64
import json
import os
import pwd
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, "/usr/local/lib/dojo")
from dojo_secret import forgejo_password  # noqa: E402

HOST = "git-server:3000"
API = f"http://{HOST}/api/v1"
TOKEN_NAME = "dojo-git"
# Repositories (clone, push, forks, pull requests, actions secrets), issues
# (pull request comments: dnsctl in dns-as-code reads them), and the
# token's own account (the "still works?" check). No admin, no settings.
SCOPES = ["write:repository", "write:issue", "read:user"]


def call(method, path, auth, body=None):
    """(status, parsed JSON or None). auth is a full Authorization value."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method,
                                 headers={"Authorization": auth, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, None


def basic(user, password):
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


def current_token(home):
    """The token in ~/.git-credentials, if this script wrote one."""
    try:
        with open(os.path.join(home, ".git-credentials")) as f:
            for line in f:
                line = line.strip()
                if line.startswith("http://") and line.endswith("@" + HOST):
                    return line[len("http://"):-len("@" + HOST)].split(":", 1)[1]
    except (OSError, IndexError):
        pass
    return None


def write_private(path, text, uid, gid):
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chown(tmp, uid, gid)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def provision(user):
    """'kept', 'created', or raises RuntimeError('retry: ...') / RuntimeError."""
    pw = pwd.getpwnam(user)
    home = pw.pw_dir
    token = current_token(home)
    if token:
        status, me = call("GET", "/user", "token " + token)
        if status == 200 and me and me.get("login") == user:
            return "kept"

    auth = basic(user, forgejo_password(user))
    status, _ = call("GET", "/user", auth)
    if status != 200:
        raise RuntimeError(f"retry: Forgejo sign-in as {user}: HTTP {status}")
    call("DELETE", f"/users/{user}/tokens/{TOKEN_NAME}", auth)
    status, made = call("POST", f"/users/{user}/tokens", auth, {"name": TOKEN_NAME, "scopes": SCOPES})
    if status != 201 or not made or not made.get("sha1"):
        raise RuntimeError(f"token for {user}: HTTP {status}")
    token = made["sha1"]

    write_private(os.path.join(home, ".git-credentials"), f"http://{user}:{token}@{HOST}\n",
                  pw.pw_uid, pw.pw_gid)
    write_private(os.path.join(home, ".netrc"), f"machine git-server login {user} password {token}\n",
                  pw.pw_uid, pw.pw_gid)
    gitconfig = os.path.join(home, ".gitconfig")
    subprocess.run(["git", "config", "--file", gitconfig, "credential.helper", "store"], check=True)
    os.chown(gitconfig, pw.pw_uid, pw.pw_gid)
    return "created"


def main(argv):
    wait = 0
    if argv[:1] == ["--wait"]:
        wait, argv = int(argv[1]), argv[2:]
    if not argv:
        sys.exit("usage: forgejo-token.py [--wait SECONDS] <user>...")
    deadline = time.monotonic() + wait
    pending, results = list(argv), {}
    while True:
        retry = []
        for user in pending:
            try:
                results[user] = provision(user)
            except (RuntimeError, OSError) as e:
                # Not signed in yet, or Forgejo not up (URLError is an OSError).
                if isinstance(e, OSError) or str(e).startswith("retry:"):
                    retry.append(user)
                results[user] = f"failed ({e})"
        pending = retry
        if not pending or time.monotonic() >= deadline:
            break
        time.sleep(5)
    failed = {u: r for u, r in results.items() if r not in ("kept", "created")}
    summary = ", ".join(f"{sum(r == k for r in results.values())} {k}" for k in ("created", "kept"))
    print(f"forgejo-token: {summary}, {len(failed)} failed", flush=True)
    for user, r in failed.items():
        print(f"forgejo-token: {user}: {r}", file=sys.stderr, flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
