"""Tells the achievements service what a student did to their zone (optional, best effort).

Off unless ACHIEVEMENTS_ADAPTER_URL and ACHIEVEMENTS_ADAPTER_SECRET are both set. The gate calls
`Reporter.patched` after PowerDNS accepted a change made with an account's own key, and
`Reporter.refused` when the gate refused a write. Each is posted, signed with the shared secret
(HMAC-SHA256 of the raw body, header X-Adapter-Signature), from a short-lived thread that swallows
every error: reporting must never slow down or break a zone change. The gate keeps the last
records it saw per zone in memory to tell a new record from an edited one.
"""
import hashlib
import hmac
import json
import threading
import urllib.request


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
        self.url, self.secret, self.timeout = url, secret, timeout
        self.enabled = bool(url and secret)
        self.state, self.lock = {}, threading.Lock()
        self._send = send or self._post

    def _post(self, raw, sig):
        req = urllib.request.Request(self.url, data=raw, method="POST", headers={
            "Content-Type": "application/json", "X-Adapter-Signature": sig})
        urllib.request.urlopen(req, timeout=self.timeout).read()

    def _emit(self, doc, wait=False):
        raw = json.dumps(dict(doc, source="dns"), separators=(",", ":")).encode()
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

    def patched(self, user, zone, body, wait=False):
        if not self.enabled:
            return
        with self.lock:
            s = summarise(self.state, zone.lower().rstrip(".") + ".", body)
        if s:
            s["zone"] = s["zone"].rstrip(".")
            self._emit(dict(s, event="zone_patch", user=user), wait)

    def refused(self, user, zone, wait=False):
        if self.enabled:
            self._emit({"event": "api_refused", "user": user, "zone": (zone or "").rstrip(".")}, wait)
