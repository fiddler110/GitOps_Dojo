"""Control-plane state: resource groups, container groups, ports, activity log.

Kept in memory and mirrored to one small JSON file on a volume after every
change, so a cloud-api restart doesn't forget what students deployed.

Next to the (capped) activity log, log() keeps a tiny per-subscription summary --
the latest event plus the times of recent Failed events -- so the class progress
board doesn't lose a student's failures when someone else's noise pushes them out
of the log. It is derived data: rebuilt from the persisted log when state loads.

State.lock is never held across a Docker call (PLAN.md 5.8). A write that must talk to Docker first reserves
what it needs under the lock (pending / deleting_rgs), lets go of the lock for the call, then commits under the
lock again and releases. Reservations live in memory only: a restart mid-operation is what reconcile() handles.
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
BUSY_MESSAGE = "Another operation on this container group is in progress. Wait for it to finish, then try again."


class Busy(Exception):
    """The container group (or its resource group) has an operation in flight; nothing was changed."""

    def __init__(self):
        super().__init__(BUSY_MESSAGE)


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
        # Operations in flight (memory only). Both are read and written under the lock.
        self.pending = {}  # cg key -> {"sub", "port", "dnsLabel"}: a PUT, a DELETE, or a child of an rg being deleted
        self.deleting_rgs = set()  # rg keys with a DELETE in flight

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
        with self.lock:  # dumps the whole document: nothing may change it meanwhile
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
        """Lowest port that no container group has, recorded or reserved."""
        with self.lock:
            used = {rec["port"] for rec in self.cgs.values()} | {p["port"] for p in self.pending.values()}
            for port in range(low, high + 1):
                if port not in used:
                    return port
            return None

    def dns_owner(self, label):
        """Key of the recorded container group that owns `label` (reservations are not looked at: see dns_taken)."""
        with self.lock:
            for key, rec in self.cgs.items():
                if rec.get("dnsLabel") == label:
                    return key
            return None

    def dns_taken(self, label, key):
        """True if a container group other than `key` owns `label` or has reserved it."""
        with self.lock:
            holder = self.dns_owner(label)
            if holder is not None and holder != key:
                return True
            return any(k != key and p["dnsLabel"] == label for k, p in self.pending.items())

    def other_groups(self, sub, key):
        """How many container groups `sub` holds besides `key`: recorded ones and reserved ones, each counted once."""
        with self.lock:
            keys = {k for k in self.cgs if k.startswith(sub + "/")}
            keys |= {k for k, p in self.pending.items() if p["sub"] == sub}
            keys.discard(key)
            return len(keys)

    # ---- reservations (callers that change the pending sets hold the lock; release() takes it itself) ----------
    def busy(self, key):
        """True if `key` has an operation in flight, or its resource group is being deleted."""
        with self.lock:
            return key in self.pending or key.rsplit("/", 1)[0] in self.deleting_rgs

    def reserve(self, key, sub, port, label):
        with self.lock:
            self.pending[key] = {"sub": sub, "port": port, "dnsLabel": label}

    def claim_rg(self, rg_key):
        """Reserve a resource group and every container group in it, for a DELETE. -> the child keys, or None
        (and nothing is claimed) if the group is already being deleted or a child has an operation in flight,
        including one that is still creating it."""
        with self.lock:
            prefix = rg_key + "/"
            if rg_key in self.deleting_rgs or any(k.startswith(prefix) for k in self.pending):
                return None
            children = [k for k in self.cgs if k.startswith(prefix)]
            self.deleting_rgs.add(rg_key)
            for k in children:
                self.reserve(k, k.split("/", 1)[0], self.cgs[k]["port"], self.cgs[k].get("dnsLabel"))
            return children

    def release(self, *keys, rg=None):
        """Drop reservations (safe to call for one that is already gone)."""
        with self.lock:
            for key in keys:
                self.pending.pop(key, None)
            if rg is not None:
                self.deleting_rgs.discard(rg)
