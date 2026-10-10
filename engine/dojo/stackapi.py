"""Helpers that talk to the running stack: find a service's container, and call a
service's HTTP API from inside its own container (so its gateway token is read
there and never appears on a host command line). Used by roster, reset-student
and export-results."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from . import state
from .envfiles import operator_env
from .runtime import READY, Container, Runtime, project_name

# Reads one JSON request on stdin, sends it with the container's own GATEWAY_TOKEN.
# "facilitator": also send the facilitator identity the gateway would (X-Auth-User)
# and the admin CSRF header; only valid because the token proves "the gateway" speaks.
_CALL = r'''
import json, os, sys, urllib.error, urllib.parse, urllib.request
r = json.load(sys.stdin)
h = {"X-Gateway-Token": os.environ["GATEWAY_TOKEN"]}
if r.get("facilitator"):
    h["X-Auth-User"] = os.environ.get("FACILITATOR_USERNAME", "root")
    h["X-Requested-With"] = "dojo-admin"
data = None
if r.get("form") is not None:
    data = urllib.parse.urlencode(r["form"]).encode()
    h["Content-Type"] = "application/x-www-form-urlencoded"
elif r.get("json") is not None:
    data = json.dumps(r["json"]).encode()
    h["Content-Type"] = "application/json"
req = urllib.request.Request("http://127.0.0.1:%s%s" % (r["port"], r["path"]), data=data, headers=h, method=r["method"])
try:
    resp = urllib.request.urlopen(req, timeout=15)
    code, body = resp.status, resp.read().decode()
except urllib.error.HTTPError as e:
    code, body = e.code, e.read().decode()
print(json.dumps({"status": code, "body": body}))
'''


class StackError(Exception):
    """The stack isn't in a state the command needs; the message says what to do."""


def project() -> str:
    cur = state.read_current()
    return project_name(operator_env(cur.env_name if cur else None))


def running(rt: Runtime) -> List[Container]:
    return rt.containers(project())


def find_container(rt: Runtime, service: str, need_ready: bool = True) -> Container:
    from .paths import PROG
    if not rt.available:
        raise StackError("No container engine found (podman with podman-compose, or docker).")
    found = [c for c in running(rt) if c.service == service]
    if not found:
        raise StackError(f"No '{service}' container is running ('{PROG} status' lists the services).")
    if need_ready and found[0].state not in READY:
        raise StackError(f"'{service}' is {found[0].state}, not ready yet ('{PROG} wait' blocks until it is).")
    return found[0]


def call(rt: Runtime, service: str, method: str, path: str, *, port: int = 8080, facilitator: bool = True,
         form: Optional[Dict[str, str]] = None, body: Any = None) -> Tuple[int, Any]:
    """(HTTP status, parsed JSON or raw text) of one request made from inside SERVICE's container."""
    import subprocess
    c = find_container(rt, service)
    req = json.dumps({"method": method, "path": path, "port": port, "facilitator": facilitator,
                      "form": form, "json": body})
    try:
        res = subprocess.run([rt.cli, "exec", "-i", c.name, "python3", "-c", _CALL],
                             input=req, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise StackError(f"Could not reach {service}: {exc}")
    if res.returncode != 0:
        raise StackError(f"Could not call {service} ({(res.stderr or res.stdout).strip()[-200:]})")
    try:
        out = json.loads(res.stdout)
    except ValueError:
        raise StackError(f"{service} gave an unreadable answer: {res.stdout.strip()[:200]}")
    try:
        return out["status"], json.loads(out["body"])
    except ValueError:
        return out["status"], out["body"]
