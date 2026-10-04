"""Per-slot flag values (plan §5).

A target's flag is deterministic in the student and the challenge:

    flag{<challenge>-<hex>}
    hex = HMAC-SHA256(STUDENT_PASSWORD_SEED, "ctf:<challenge>:<user>")[:16]

The seed is a range-wide secret that lives ONLY in the controller (and, when it
is built, the ctf-flags service). A target slot is handed the rendered flag
VALUE as an env var and never sees the seed, so dumping a target can never
yield another slot's flag. Because the value is a pure function of (seed,
challenge, user), it survives stop / start / recreate — a redeploy keeps the
same flag (§4 "Flags and state").

Without a seed (local dev, no §5 wiring) a clearly-marked dev flag is rendered
so the scaffold runs standalone; it is never used when a real seed is set.
"""
import hmac
import hashlib

CHALLENGE = "customer-portal"
_HEXLEN = 16


def render(user, seed, challenge=CHALLENGE):
    """The flag value for one (user, challenge). `seed` is bytes or str; empty
    seed → a dev flag that is obviously not real."""
    if not seed:
        return f"flag{{{challenge}-dev-{user}}}"
    if isinstance(seed, str):
        seed = seed.encode()
    msg = f"ctf:{challenge}:{user}".encode()
    hexd = hmac.new(seed, msg, hashlib.sha256).hexdigest()[:_HEXLEN]
    return f"flag{{{challenge}-{hexd}}}"
