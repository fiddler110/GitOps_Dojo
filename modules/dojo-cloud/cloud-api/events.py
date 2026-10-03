"""Tells the achievements service what a student did in Dojo Cloud (optional, best effort).

Off unless ACHIEVEMENTS_ADAPTER_URL and ACHIEVEMENTS_ADAPTER_SECRET are both set. Each event is posted as
{"source": "cloud", "event", "user", "reason"?}, signed with the shared secret (HMAC-SHA256 of the raw body,
header X-Adapter-Signature) through the shared adapter_client (one bounded queue, one worker that swallows
every error): reporting must never slow down or break an ARM or portal request. Stdlib only.

Events: portal_request, site_request, policy_denied (reason tag | region | size | image | assignment), quota_denied,
container_created, container_updated, container_deleted, container_replaced, policy_written. For updated,
deleted and replaced, `reason` says how it was done: "portal" (the Dojo Portal) or "arm" (the API, so tofu).
policy_denied "assignment" is a refusal by one of the student's own policy assignments (not a platform
guardrail). policy_written is a successful create or update of one of the student's own Dojo Cloud Policy
objects, `reason` its kind: definition | set | assignment | exemption | remediation, or "portal" for an
enforcement-mode change made by hand on the portal's Policy blade.
"""
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# adapter_client: modules/_shared/ in the source tree, ./_shared/ once ./run.sh has copied it (SHARED= in module.env).
sys.path[:0] = [os.path.join(HERE, "..", "..", "_shared"), os.path.join(HERE, "_shared")]
from adapter_client import AdapterClient  # noqa: E402

REPLACE_WINDOW = 120.0  # a create of a group this user deleted within this many seconds is a replace


def denial(exc):
    """(event, reason) for a policy.PolicyError worth reporting, else None."""
    code, pol = getattr(exc, "code", ""), getattr(exc, "policy", None) or ""
    if code == "RequestDisallowedByPolicy" and getattr(exc, "assignment", None):
        return "policy_denied", "assignment"   # the student's own assignment (policy_api.refusal marks it)
    if code == "QuotaExceeded":
        return "quota_denied", None
    if code == "RequestDisallowedByPolicy":
        if pol.startswith("Require tag"):
            return "policy_denied", "tag"
        if pol == "Allowed locations":
            return "policy_denied", "region"
    if code == "InvalidResourceRequest":
        return "policy_denied", "size"
    if code == "InvalidImage":
        return "policy_denied", "image"
    return None


class Reporter:
    def __init__(self, url, secret, timeout=2, send=None, clock=time.monotonic):
        self.client = AdapterClient(url, secret, "cloud", timeout=timeout, send=send)
        self.enabled, self.clock = self.client.enabled, clock
        self.lock = threading.Lock()
        self.last = {}          # (user, event) -> when it was last sent, for `every`
        self.deleted = {}       # (user, group key) -> when it was deleted

    def emit(self, event, user, reason=None, every=0):
        """Post one event. `every`: send at most one such event per user per this many seconds."""
        if not self.enabled or not user:
            return
        now = self.clock()
        with self.lock:
            if every and now - self.last.get((user, event), -1e9) < every:
                return
            self.last[(user, event)] = now
        doc = {"event": event, "user": user}
        if reason:
            doc["reason"] = reason
        self.client.post(doc)

    def refused(self, user, exc):
        """Report a policy refusal if it is one of the teaching ones (tag, region, size, quota)."""
        found = denial(exc)
        if found:
            self.emit(found[0], user, found[1])

    def deleted_group(self, user, key, via):
        with self.lock:
            self.deleted[(user, key)] = self.clock()
        self.emit("container_deleted", user, via or "arm")

    def written_group(self, user, key, created, changed):
        """A successful create or update of a container group. A create right after this user deleted the
        same group, or an update that had to swap the container, is a replace (tofu's `-/+`)."""
        with self.lock:
            gone = self.deleted.pop((user, key), None)
            recent = gone is not None and self.clock() - gone <= REPLACE_WINDOW
        if created and not recent:
            self.emit("container_created", user)
        elif created or changed:
            self.emit("container_replaced", user)
        else:
            self.emit("container_updated", user, "arm")


def from_env(env):
    return Reporter(env.get("ACHIEVEMENTS_ADAPTER_URL"), env.get("ACHIEVEMENTS_ADAPTER_SECRET"))
