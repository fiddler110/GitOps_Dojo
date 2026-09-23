#!/usr/bin/env python3
"""Dojo Cloud credential broker (runs as root inside the terminal container).

A student's shell asks this daemon (over a unix socket) for its Dojo Cloud
credentials. The kernel tells us WHO is asking (SO_PEERCRED gives the caller's
real uid), so a student can only ever obtain their OWN service-principal
values — they cannot ask for someone else's, and the signing key that derives
them is in a root-only file they cannot read.

Derivations (uuid namespace, HMAC scheme) MUST match cloud-api/auth.py;
compose/test_parity.py checks that.
"""
import hashlib
import hmac
import json
import os
import pwd
import socket
import struct
import sys
import time
import uuid

NAMESPACE = uuid.UUID("6f0d4a1e-5b1c-4d55-9a3e-0d0a0c10a1b1")
TENANT_ID = "5f2c1a40-7d3e-4b6a-9c11-3a7e2d9b8f10"
SOCKET_PATH = "/run/dojo-broker/broker.sock"
KEY_PATH = "/run/cloud-secrets/signing.key"
CA_BUNDLE = "/etc/dojo/ca-bundle.pem"


def app_id(username):
    return str(uuid.uuid5(NAMESPACE, "app:" + username))


def subscription_id(username):
    return str(uuid.uuid5(NAMESPACE, "sub:" + username))


def client_secret(key, username):
    return "dojo~" + hmac.new(key, ("client-secret:" + username).encode(), hashlib.sha256).hexdigest()[:40]


def roster(env):
    # Same names the engine creates (kept in step with cloud-api's auth.roster, see
    # test_parity.py): students are zero-padded (student01), demo bots are not (testuser1).
    users = []
    for prefix_var, count_var, default_prefix, pad in (("STUDENT_PREFIX", "STUDENT_COUNT", "student", "02d"),
                                                       ("BOT_PREFIX", "BOT_COUNT", "testuser", "d")):
        prefix = env.get(prefix_var, default_prefix)
        try:
            count = int(env.get(count_var, "0") or 0)
        except ValueError:
            count = 0
        users += [f"{prefix}{n:{pad}}" for n in range(1, count + 1)]
    if env.get("FACILITATOR_USERNAME", "root"):
        users.append(env.get("FACILITATOR_USERNAME", "root"))
    return users


def credentials_for(username, key, env):
    base = env.get("PUBLIC_BASE_URL", "").rstrip("/")
    creds = {
        "ARM_METADATA_HOSTNAME": "management.dojo.cloud",
        "ARM_TENANT_ID": TENANT_ID,
        "ARM_SUBSCRIPTION_ID": subscription_id(username),
        "ARM_CLIENT_ID": app_id(username),
        "ARM_CLIENT_SECRET": client_secret(key, username),
        "ARM_USE_CLI": "false",
        "ARM_RESOURCE_PROVIDER_REGISTRATIONS": "none",
        "TF_VAR_owner": username,
        "TF_VAR_portal_base_url": f"{base}/cloud",
    }
    if os.path.exists(CA_BUNDLE):
        creds["SSL_CERT_FILE"] = CA_BUNDLE
        creds["CURL_CA_BUNDLE"] = CA_BUNDLE  # so plain `curl https://management.dojo.cloud/...` works too
    return creds


def serve():
    users = set(roster(os.environ))
    key = None
    while key is None:  # cloud-api creates the key; Track A works without it
        try:
            with open(KEY_PATH, "rb") as f:
                key = f.read().strip() or None
        except OSError:
            key = None
        if key is None:
            time.sleep(2)

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
            # Nothing until the wrapper has written the CA bundle: a shell holding ARM_* credentials
            # but no way to trust the cloud is worse than a shell without them (Lab 4: open a new tab).
            ready = name in users and os.path.exists(CA_BUNDLE)
            payload = credentials_for(name, key, os.environ) if ready else {}
            conn.sendall(json.dumps(payload).encode())
        except OSError:
            pass
        finally:
            conn.close()


if __name__ == "__main__":
    sys.exit(serve())
