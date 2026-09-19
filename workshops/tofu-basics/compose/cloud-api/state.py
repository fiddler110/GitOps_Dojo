"""Control-plane state: resource groups, container groups, ports, activity log.

Kept in memory and mirrored to one small JSON file on a volume after every
change, so a cloud-api restart doesn't forget what students deployed.

Next to the (capped) activity log, log() keeps a tiny per-subscription summary --
the latest event plus the times of recent Failed events -- so the class progress
board doesn't lose a student's failures when someone else's noise pushes them out
of the log. It is derived data: rebuilt from the persisted log when state loads.
"""
import calendar
import collections
import json
import os
import threading
import time

ACTIVITY_MAX = 2000
FAILURES_KEPT = 100  # Failed-event times remembered per subscription (memory bound)
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def event_epoch(event):
    """Seconds since the epoch of an event's UTC ISO 'time' (calendar.timegm, so no local-timezone
    skew); -inf if it cannot be parsed, i.e. too old to count as recent."""
    try:
        return calendar.timegm(time.strptime(event.get("time"), TIME_FORMAT))
    except (TypeError, ValueError):
        return float("-inf")


class State:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.data = {"rgs": {}, "cgs": {}, "activity": []}
        if path and os.path.exists(path):
            try:
                with open(path) as f:
                    self.data.update(json.load(f))
            except (OSError, ValueError):
                pass
        self._summary = {}  # sub -> {"last": newest event, "failed": deque of epoch times}
        self.rebuild_summary()

    # rgs are keyed "<sub>/<rg lowercase>", cgs "<sub>/<rg>/<cg>" (lowercase)
    @property
    def rgs(self):
        return self.data["rgs"]

    @property
    def cgs(self):
        return self.data["cgs"]

    def save(self):
        if not self.path:
            return
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.data, f)
        os.replace(tmp, self.path)

    def log(self, sub, user, operation, resource_id, status, message=""):
        now = time.time()
        with self.lock:
            event = {
                "time": time.strftime(TIME_FORMAT, time.gmtime(now)),
                "subscription": sub, "caller": user, "operation": operation,
                "resourceId": resource_id, "status": status, "message": message,
            }
            self.data["activity"].append(event)
            del self.data["activity"][:-ACTIVITY_MAX]
            self._note(event, int(now))

    def _note(self, event, epoch):
        """Fold one event into the per-subscription summary. Caller holds the lock."""
        sub = event.get("subscription")
        if not isinstance(sub, str):
            return
        entry = self._summary.setdefault(sub, {"last": None, "failed": collections.deque(maxlen=FAILURES_KEPT)})
        entry["last"] = event  # entries are never mutated after they are logged
        if event.get("status") == "Failed" and epoch != float("-inf"):
            entry["failed"].append(epoch)

    def rebuild_summary(self):
        """Recompute the summary from the activity list: on load, so a restart keeps whatever the
        log still holds (and for tests that edit the list directly)."""
        with self.lock:
            self._summary = {}
            for event in self.data["activity"]:
                if isinstance(event, dict):
                    self._note(event, event_epoch(event))

    def activity_summary(self, since):
        """-> {sub: (latest event, number of Failed events at or after epoch `since`)}. Drops older
        failure times as it goes (for good: use one window per State), so the deques only ever
        hold what is still recent."""
        with self.lock:
            out = {}
            for sub, entry in self._summary.items():
                failed = entry["failed"]
                while failed and failed[0] < since:
                    failed.popleft()
                out[sub] = (entry["last"], sum(1 for t in failed if t >= since))
            return out

    def free_port(self, low=20000, high=20999):
        used = {rec["port"] for rec in self.cgs.values()}
        for port in range(low, high + 1):
            if port not in used:
                return port
        return None

    def dns_owner(self, label):
        for key, rec in self.cgs.items():
            if rec.get("dnsLabel") == label:
                return key
        return None
