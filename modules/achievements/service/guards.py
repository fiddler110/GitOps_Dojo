"""Event signing, replay protection and rate limiting. Pure: callers pass `now`.

An event reaches the service signed with a per-run secret, so a hand-posted one is rejected
(and the sender earns "Nice Try, Hackerman"). `verify` says why an event was refused so the
service can tell a forgery from an honest stale clock."""

import hashlib
import hmac

WINDOW = 300


def sign(secret, user, event, ts, nonce):
    msg = "\n".join((user, event, str(int(ts)), nonce)).encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


class Verifier:
    def __init__(self, secret, window=WINDOW):
        self.secret = secret
        self.window = window
        self._seen = {}     # nonce -> ts

    def verify(self, user, event, ts, nonce, signature, now):
        """(ok, reason): reason is None, 'forged', 'stale' or 'replay'. Order matters: a bad
        signature is reported as forged whatever else is wrong."""
        want = sign(self.secret, user, event, ts, nonce)
        if not isinstance(signature, str) or not hmac.compare_digest(want, signature):
            return False, "forged"
        if abs(now - int(ts)) > self.window:
            return False, "stale"
        self._seen = {n: t for n, t in self._seen.items() if now - t <= self.window}
        if nonce in self._seen:
            return False, "replay"
        self._seen[nonce] = int(ts)
        return True, None


class RateLimiter:
    """At most `limit` hits per `window` seconds per key: the button masher."""

    def __init__(self, limit=10, window=10):
        self.limit = limit
        self.window = window
        self._hits = {}

    def hit(self, key, now):
        """True when allowed, False when over the limit (the refused hit is not counted)."""
        recent = [t for t in self._hits.get(key, []) if now - t < self.window]
        if len(recent) >= self.limit:
            self._hits[key] = recent
            return False
        recent.append(now)
        self._hits[key] = recent
        return True
