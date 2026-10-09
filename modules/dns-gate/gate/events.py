"""Tells the achievements service what a student did to their zone (optional, best effort).

Off unless ACHIEVEMENTS_ADAPTER_URL and ACHIEVEMENTS_ADAPTER_SECRET are both set. The gate calls
`Reporter.patched` after PowerDNS accepted a change made with an account's own key, and
`Reporter.refused` when the gate refused a write. Each is posted, signed with the shared secret
(HMAC-SHA256 of the raw body, header X-Adapter-Signature), through the shared adapter_client (one
bounded queue, one worker that swallows every error): reporting must never slow down or break a
zone change. The gate keeps the last
records it saw per zone in memory to tell a new record from an edited one.
"""
import json
import os
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
# adapter_client: modules/_shared/ in the source tree, ./_shared/ once ./dojo has copied it (SHARED= in module.env).
sys.path[:0] = [os.path.join(HERE, "..", "..", "_shared"), os.path.join(HERE, "_shared")]
from adapter_client import AdapterClient  # noqa: E402


def summarise(state, zone, body):
    """Fold one PATCH body into `state` ({zone: {(name, type): (ttl, records)}}).
    Returns {zone, first, created, changed, deleted, min_ttl} or None if the body isn't rrsets."""
    try:
        rrsets = json.loads(body).get("rrsets")
    except (ValueError, AttributeError):
        return None
    if not isinstance(rrsets, list):
        return None
    first = zone not in state
    known = state.setdefault(zone, {})
    created = changed = deleted = 0
    ttls = []
    for r in rrsets:
        if not isinstance(r, dict):
            continue
        key = (str(r.get("name", "")).lower(), str(r.get("type", "")))
        if r.get("changetype") == "DELETE":
            if known.pop(key, None) is not None:
                deleted += 1
            continue
        records = tuple(sorted(str(x.get("content", "")) for x in r.get("records") or [] if isinstance(x, dict)))
        ttl = r.get("ttl") if isinstance(r.get("ttl"), int) and not isinstance(r.get("ttl"), bool) else None
        if ttl is not None:
            ttls.append(ttl)
        if key not in known:
            created += 1
        elif known[key] != (ttl, records):
            changed += 1
        known[key] = (ttl, records)
    return {"zone": zone, "first": first, "created": created, "changed": changed, "deleted": deleted,
            "min_ttl": min(ttls) if ttls else None}


class Reporter:
    def __init__(self, url, secret, timeout=2, send=None):
        self.client = AdapterClient(url, secret, "dns", timeout=timeout, send=send)
        self.enabled = self.client.enabled
        self.state, self.lock = {}, threading.Lock()

    def patched(self, user, zone, body):
        if not self.enabled:
            return
        with self.lock:
            s = summarise(self.state, zone.lower().rstrip(".") + ".", body)
        if s:
            s["zone"] = s["zone"].rstrip(".")
            self.client.post(dict(s, event="zone_patch", user=user))

    def refused(self, user, zone):
        if self.enabled:
            self.client.post({"event": "api_refused", "user": user, "zone": (zone or "").rstrip(".")})
