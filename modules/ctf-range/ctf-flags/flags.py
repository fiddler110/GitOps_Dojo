"""Per-slot flag values (plan §5).

Same derivation as `ctf-controller/flags.py`, kept as two small, independent
copies deliberately: ctf-flags verifies a submission and never talks to
ctf-host, while ctf-controller renders the value a slot runs with and never
takes a submission, so the two services share no code path worth a real
dependency (`check-tool-pins.sh` would catch the two copies drifting apart,
same as any other shared tool pin). If this ever grows past one function,
promote it to `modules/_shared/` instead of a third copy.

    flag{<challenge>-<hex>}
    hex = HMAC-SHA256(STUDENT_PASSWORD_SEED, "ctf:<challenge>:<user>")[:16]

The seed is a range-wide secret that lives only in ctf-controller and here.
A target slot is handed the rendered flag VALUE as an env var and never sees
the seed, so dumping a target can never yield another slot's flag.

Without a seed (local dev, no §5 wiring) a clearly-marked dev flag is
rendered so the scaffold runs standalone; it is never used when a real seed
is set.
"""
import hmac
import hashlib

_HEXLEN = 16


def render(user, seed, challenge):
    """The flag value for one (user, challenge). `seed` is bytes or str; empty
    seed → a dev flag that is obviously not real."""
    if not seed:
        return f"flag{{{challenge}-dev-{user}}}"
    if isinstance(seed, str):
        seed = seed.encode()
    msg = f"ctf:{challenge}:{user}".encode()
    hexd = hmac.new(seed, msg, hashlib.sha256).hexdigest()[:_HEXLEN]
    return f"flag{{{challenge}-{hexd}}}"


def user_key(user, seed):
    """A student's own key for the range's terminal-facing services (REVIEW §1.1):
    HMAC-SHA256(STUDENT_PASSWORD_SEED, "ctf-user:<user>"), 32 hex. Installed as
    ~/.config/dojo/ctf-key (0600) by terminal/start.d/57-ctf-key.sh; `dojo check`,
    `dojo reset` and `dojo flag` send it, so a request can only act as its own
    account. Same function in ctf-checker/checker.py, ctf-flags/flags.py and
    ctf-controller/flags.py. Empty seed -> "" (no key verifies)."""
    if not seed:
        return ""
    if isinstance(seed, str):
        seed = seed.encode()
    return hmac.new(seed, f"ctf-user:{user}".encode(), hashlib.sha256).hexdigest()[:32]


def key_ok(user, seed, key):
    """True if `key` is `user`'s own key (constant-time); never with an empty seed."""
    want = user_key(user, seed)
    return bool(want) and isinstance(key, str) and hmac.compare_digest(key.encode(), want.encode())
