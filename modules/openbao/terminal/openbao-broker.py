#!/usr/bin/env python3
"""OpenBao identity broker (runs as root inside the terminal container).

A shell asks this daemon, over a unix socket, for a JWT that says who it is.
The kernel tells us WHO is asking (SO_PEERCRED gives the caller's real uid),
so a student only ever gets a JWT for their OWN account; the signing key is
in a root-only file they can't read. OpenBao's `jwt` auth method trusts the
matching public key (openbao-setup reads it from the shared volume) and maps
`sub` to the account's identity entity, the same one the web UI's SSO uses.

The JWT lives two minutes: it is only traded for an OpenBao token
(openbao-login does that), never stored.
"""
import base64
import json
import os
import pwd
import socket
import struct
import subprocess
import sys
import time

SOCKET_PATH = "/run/openbao-broker/broker.sock"
KEY_PATH = "/var/lib/openbao-broker/key.pem"
ISSUER = "dojo-terminal"
AUDIENCE = "openbao"
LIFETIME = 120  # seconds


def roster(env):
    # The accounts openbao-setup gives an entity: every student and the facilitator.
    prefix = env.get("STUDENT_PREFIX", "student")
    try:
        count = int(env.get("STUDENT_COUNT", "0") or 0)
    except ValueError:
        count = 0
    return {f"{prefix}{n:02d}" for n in range(1, count + 1)} | {env.get("FACILITATOR_USERNAME", "root")}


def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=")


def jwt_for(username):
    now = int(time.time())
    header = b64url(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claims = b64url(json.dumps({"iss": ISSUER, "aud": AUDIENCE, "sub": username,
                                "iat": now, "nbf": now - 5, "exp": now + LIFETIME}).encode())
    signing_input = header + b"." + claims
    sig = subprocess.run(["openssl", "dgst", "-sha256", "-sign", KEY_PATH], input=signing_input,
                         capture_output=True, check=True).stdout
    return (signing_input + b"." + b64url(sig)).decode()


def serve():
    users = roster(os.environ)
    os.makedirs(os.path.dirname(SOCKET_PATH), mode=0o755, exist_ok=True)
    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(SOCKET_PATH)
    os.chmod(SOCKET_PATH, 0o666)
    srv.listen(64)
    while True:
        conn, _ = srv.accept()
        try:
            conn.settimeout(3)
            _pid, uid, _gid = struct.unpack("3i", conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED,
                                                                 struct.calcsize("3i")))
            try:
                name = pwd.getpwuid(uid).pw_name
            except KeyError:
                name = ""
            conn.sendall((jwt_for(name) if name in users else "").encode())
        except (OSError, subprocess.CalledProcessError):
            pass
        finally:
            conn.close()


if __name__ == "__main__":
    sys.exit(serve())
