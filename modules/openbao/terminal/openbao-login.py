#!/usr/bin/env python3
"""Signs the calling user in to OpenBao with no password: a JWT from the
root-owned broker (openbao-broker), traded at OpenBao's `jwt` auth method
for a token, written to ~/.vault-token (which bao, sops and hvac all read).

Run from /etc/zsh/zshenv with --quiet on every shell start, so it does nothing
while the token it wrote last is still good for an hour or more, and never
replaces a token the user got some other way (`bao login ...`) unless asked
with --force. Run it by hand to sign in again, e.g. in a shell opened before
OpenBao was ready.
"""
import json
import os
import socket
import sys
import time
import urllib.request

TOKEN = os.path.expanduser("~/.vault-token")
STATE = os.path.expanduser("~/.cache/openbao-login")  # "<token> <expiry epoch>" of the last token we wrote
MARGIN = 3600  # seconds


def read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def needed(force):
    if force:
        return True
    token = read(TOKEN)
    ours, _, expiry = read(STATE).partition(" ")
    if token and token != ours:
        return False  # the user signed in some other way: leave it
    return not token or not expiry.isdigit() or int(expiry) < time.time() + MARGIN


def broker_jwt():
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(3)
    s.connect("/run/openbao-broker/broker.sock")
    data = b""
    while chunk := s.recv(65536):
        data += chunk
    return data.decode().strip()


def login():
    jwt = broker_jwt()
    if not jwt:
        raise RuntimeError("the broker has no JWT for this account")
    addr = os.environ.get("BAO_ADDR") or os.environ.get("VAULT_ADDR") or "http://openbao:8200"
    req = urllib.request.Request(f"{addr.rstrip('/')}/v1/auth/jwt/login", method="POST",
                                 data=json.dumps({"role": "terminal", "jwt": jwt}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        auth = json.load(r)["auth"]
    write(TOKEN, auth["client_token"])
    write(STATE, f"{auth['client_token']} {int(time.time()) + int(auth['lease_duration'])}")
    return auth


def main(args):
    quiet = "--quiet" in args
    if not needed("--force" in args):
        return 0
    try:
        auth = login()
    except Exception as e:  # noqa: BLE001 - a shell start must never fail over this
        if not quiet:
            print(f"openbao-login: could not sign in to OpenBao: {e}", file=sys.stderr)
        return 0 if quiet else 1
    if not quiet:
        print(f"Signed in to OpenBao as {auth['metadata'].get('sub', '?')} "
              f"(policies: {', '.join(auth.get('identity_policies') or []) or 'none'}).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
