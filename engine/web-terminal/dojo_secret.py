"""Per-student secrets, derived instead of stored (remediation D13, FIND-03).

    derive(seed, label, name) = base32(HMAC-SHA256(seed, label + ":" + name))[:16]

forgejo_password(user) is each student's own Forgejo password: bootstrap.sh
creates the account with it, the allocator's Forgejo SSO signs in with it,
and the terminal uses it once to mint the student's git token. Students
never need to see it.

Identical copies live in engine/allocator/ and engine/web-terminal/ (one per
image); engine/git-server/dojo-secret.sh is the same function in shell for
the Forgejo image, which has no Python. engine/allocator/tests/
test_dojo_secret.py checks all three against one known answer, so they
can't drift.

Without STUDENT_PASSWORD_SEED (an engine/.env written before the seed
existed) every student falls back to the old shared STUDENT_PASSWORD.
"""
import base64
import hashlib
import hmac
import os
import sys

FALLBACK_PASSWORD = "student123"


def derive(seed, label, name, length=16):
    mac = hmac.new(seed.encode(), f"{label}:{name}".encode(), hashlib.sha256).digest()
    return base64.b32encode(mac).decode()[:length]


def forgejo_password(user, env=os.environ):
    seed = env.get("STUDENT_PASSWORD_SEED", "")
    if not seed:
        return env.get("STUDENT_PASSWORD") or FALLBACK_PASSWORD
    return derive(seed, "forgejo", user)


if __name__ == "__main__":
    # dojo_secret.py forgejo <user>: print that student's password (root
    # only in the terminal image; tests use it through `podman exec`).
    if len(sys.argv) != 3 or sys.argv[1] != "forgejo":
        sys.exit("usage: dojo_secret.py forgejo <user>")
    print(forgejo_password(sys.argv[2]))
