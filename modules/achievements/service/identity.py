"""Who is asking, when the request carries a Forgejo token instead of gateway headers.

The student's terminal talks to the service directly and holds only its own Forgejo token
(~/.git-credentials). The service asks Forgejo whose token it is, so nothing new is stored in
the terminal and a student can't claim to be anyone else. Answers are cached briefly so a
prompt hook doesn't hit Forgejo on every keystroke. Pure: `fetch` and `clock` are injected.
"""

import json
import time
import urllib.error
import urllib.request

TTL = 60
NEGATIVE_TTL = 10
MAX_CACHE = 500


def forgejo_fetch(base_url):
    """A `fetch(token) -> login or None` that asks Forgejo's API."""
    def fetch(token):
        req = urllib.request.Request(base_url.rstrip("/") + "/api/v1/user",
                                     headers={"Authorization": "token " + token})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return json.load(r).get("login") or None
        except (urllib.error.URLError, OSError, ValueError):
            return None
    return fetch


class Resolver:
    def __init__(self, fetch, clock=time.time, ttl=TTL, negative_ttl=NEGATIVE_TTL):
        self.fetch = fetch
        self.clock = clock
        self.ttl = ttl
        self.negative_ttl = negative_ttl
        self._cache = {}    # token -> (user or None, expires)

    @staticmethod
    def token_of(header):
        """The token in an `Authorization: token X` (or Bearer) header, else None."""
        if not isinstance(header, str):
            return None
        kind, _, value = header.strip().partition(" ")
        value = value.strip()
        if kind.lower() in ("token", "bearer") and 0 < len(value) <= 200 and value.isalnum():
            return value
        return None

    def resolve(self, header):
        token = self.token_of(header)
        if not token:
            return None
        now = self.clock()
        hit = self._cache.get(token)
        if hit and hit[1] > now:
            return hit[0]
        user = self.fetch(token)
        if len(self._cache) >= MAX_CACHE:
            self._cache = {k: v for k, v in self._cache.items() if v[1] > now}
            if len(self._cache) >= MAX_CACHE:
                self._cache.clear()
        self._cache[token] = (user, now + (self.ttl if user else self.negative_ttl))
        return user
