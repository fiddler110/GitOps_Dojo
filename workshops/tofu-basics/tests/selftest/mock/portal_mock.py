#!/usr/bin/env python3
"""A tiny stand-in for cloud-api's portal API, for tests/selftest only. It knows just enough to let lib.sh,
e2e.sh and load.sh run their control flow without a stack: /readyz, /cloud/api/me, overview, activity, progress and
admin/purge. Resource state is read from files "<state dir>/<user>" containing "<resource groups> <container groups>",
which the fake terraform writes. It checks X-Auth-User and X-Gateway-Token like the real one.

    portal_mock.py PORT STATE_DIR
"""
import json
import os
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT, STATE = int(sys.argv[1]), sys.argv[2]
TOKEN = "mocktoken"
FAC = "admin"
NS = uuid.UUID("6f0d4a1e-5b1c-4d55-9a3e-0d0a0c10a1b1")
USERS = [f"student{n:02d}" for n in range(1, 21)] + [FAC]
SUB = {u: str(uuid.uuid5(NS, "sub:" + u)) for u in USERS}
BY_SUB = {v: k for k, v in SUB.items()}


def counts(user):
    try:
        rg, cg = open(os.path.join(STATE, user)).read().split()
        return int(rg), int(cg)
    except (OSError, ValueError):
        return 0, 0


def view(only=None):
    rgs, cgs = [], []
    for u in USERS:
        if only and u != only:
            continue
        rg, cg = counts(u)
        rgs += [{"name": f"rg-{i}", "owner": u, "subscriptionId": SUB[u]} for i in range(rg)]
        cgs += [{"name": f"ci-{i}", "owner": u, "subscriptionId": SUB[u], "state": "Running"} for i in range(cg)]
    return {"resourceGroups": rgs, "containerGroups": cgs}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, status, obj):
        raw = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def handle_any(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}") if n else {}
        if u.path == "/readyz":
            return self.send(200, {"ready": True, "state": "ready", "detail": ""})
        user = self.headers.get("X-Auth-User", "")
        if self.headers.get("X-Gateway-Token") != TOKEN or user not in USERS:
            return self.send(401, {"error": {"code": "Unauthenticated", "message": "no"}})
        if u.path == "/cloud/api/me":
            rg, cg = counts(user)
            return self.send(200, {"user": user, "subscriptionId": SUB[user], "isFacilitator": user == FAC,
                                   "quota": {"containerGroups": {"used": cg, "limit": 2}}})
        if u.path == "/cloud/api/overview":
            scope = (q.get("scope") or ["mine"])[0]
            return self.send(200, view(None if scope == "class" else user))
        if u.path == "/cloud/api/activity":
            return self.send(200, {"events": []})
        if u.path == "/cloud/api/admin/progress":
            return self.send(200, {"summary": {}, "students": []}) if user == FAC else self.send(403, {})
        if u.path == "/cloud/api/admin/purge" and self.command == "POST":
            target = BY_SUB.get(str(body.get("subscriptionId", "")).lower())
            if user != FAC or not target:
                return self.send(404, {"error": {"code": "SubscriptionNotFound"}})
            rg, cg = counts(target)
            open(os.path.join(STATE, target), "w").write("0 0")
            return self.send(200, {"removed": {"containerGroups": cg, "resourceGroups": rg}})
        return self.send(404, {"error": {"code": "NotFound", "message": u.path}})

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = handle_any


if __name__ == "__main__":
    os.makedirs(STATE, exist_ok=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
