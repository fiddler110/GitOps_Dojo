"""Tells the achievements service what a student did in Dojo Cloud (optional, best effort).

Off unless ACHIEVEMENTS_ADAPTER_URL and ACHIEVEMENTS_ADAPTER_SECRET are both set. Each event is posted as
{"source": "cloud", "event", "user", "reason"?}, signed with the shared secret (HMAC-SHA256 of the raw body,
header X-Adapter-Signature), from a short-lived thread that swallows every error: reporting must never slow
down or break an ARM or portal request. Stdlib only.

Events: portal_request, site_request, policy_denied (reason tag | region | size), quota_denied,
container_created, container_updated, container_deleted, container_replaced. For updated, deleted and
replaced, `reason` says how it was done: "portal" (the Dojo Portal) or "arm" (the API, so tofu).
"""
import hashlib
import hmac
import json
import threading
import time
import urllib.request

REPLACE_WINDOW = 120.0  # a create of a group this user deleted within this many seconds is a replace


def denial(exc):
    """(event, reason) for a policy.PolicyError worth reporting, else None."""
    code, pol = getattr(exc, "code", ""), getattr(exc, "policy", None) or ""
    if code == "QuotaExceeded":
        return "quota_denied", None
    if code == "RequestDisallowedByPolicy":
        if pol.startswith("Require tag"):
            return "policy_denied", "tag"
        if pol == "Allowed locations":
            return "policy_denied", "region"
    if code == "InvalidResourceRequest":
        return "policy_denied", "size"
    return None


class Reporter:
    def __init__(self, url, secret, timeout=2, send=None, clock=time.monotonic):
        self.url, self.secret, self.timeout, self.clock = url, secret, timeout, clock
        self.enabled = bool(url and secret)
        self._send = send or self._post
        self.lock = threading.Lock()
        self.last = {}          # (user, event) -> when it was last sent, for `every`
        self.deleted = {}       # (user, group key) -> when it was deleted

    def _post(self, raw, sig):
        req = urllib.request.Request(self.url, data=raw, method="POST", headers={
            "Content-Type": "application/json", "X-Adapter-Signature": sig})
        urllib.request.urlopen(req, timeout=self.timeout).read()

    def emit(self, event, user, reason=None, every=0, wait=False):
        """Post one event. `every`: send at most one such event per user per this many seconds."""
        if not self.enabled or not user:
            return
        now = self.clock()
        with self.lock:
            if every and now - self.last.get((user, event), -1e9) < every:
                return
            self.last[(user, event)] = now
        doc = {"source": "cloud", "event": event, "user": user}
        if reason:
            doc["reason"] = reason
        raw = json.dumps(doc, separators=(",", ":")).encode()
        sig = hmac.new(self.secret.encode(), raw, hashlib.sha256).hexdigest()

        def run():
            try:
                self._send(raw, sig)
            except Exception:  # noqa: BLE001 - reporting is best effort
                pass
        t = threading.Thread(target=run, daemon=True)
        t.start()
        if wait:
            t.join()

    def refused(self, user, exc, wait=False):
        """Report a policy refusal if it is one of the teaching ones (tag, region, size, quota)."""
        found = denial(exc)
        if found:
            self.emit(found[0], user, found[1], wait=wait)

    def deleted_group(self, user, key, via, wait=False):
        with self.lock:
            self.deleted[(user, key)] = self.clock()
        self.emit("container_deleted", user, via or "arm", wait=wait)

    def written_group(self, user, key, created, changed, wait=False):
        """A successful create or update of a container group. A create right after this user deleted the
        same group, or an update that had to swap the container, is a replace (tofu's `-/+`)."""
        with self.lock:
            gone = self.deleted.pop((user, key), None)
            recent = gone is not None and self.clock() - gone <= REPLACE_WINDOW
        if created and not recent:
            self.emit("container_created", user, wait=wait)
        elif created or changed:
            self.emit("container_replaced", user, wait=wait)
        else:
            self.emit("container_updated", user, "arm", wait=wait)


def from_env(env):
    return Reporter(env.get("ACHIEVEMENTS_ADAPTER_URL"), env.get("ACHIEVEMENTS_ADAPTER_SECRET"))
