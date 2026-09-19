"""Control-plane state: resource groups, container groups, ports, activity log.

Kept in memory and mirrored to one small JSON file on a volume after every
change, so a cloud-api restart doesn't forget what students deployed.
"""
import json
import os
import threading
import time

ACTIVITY_MAX = 2000


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
        with self.lock:
            self.data["activity"].append({
                "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "subscription": sub, "caller": user, "operation": operation,
                "resourceId": resource_id, "status": status, "message": message,
            })
            del self.data["activity"][:-ACTIVITY_MAX]

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
