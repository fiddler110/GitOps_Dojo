"""Tells the achievements service what a student did in the vault (optional, best effort).

Off unless ACHIEVEMENTS_ADAPTER_URL and ACHIEVEMENTS_ADAPTER_SECRET are both set. `Reporter.entry`
takes one audit response entry (the raw JSON object OpenBao wrote) and, when it is something a
student did, posts {source: "bao", event, user, ...} signed with the shared secret (HMAC-SHA256
of the raw body, header X-Adapter-Signature), the same contract as the dns-gate module. Posts go
through the shared adapter_client (one bounded queue, one worker thread that swallows every
error): reporting must never slow down or break the audit tail, and a full queue just drops events.

What each field is derived from (the audit log HMACs every request/response *string value* in
`data`, so a role name or a secret ID is never readable here; paths, operations, policies and
display names are not hashed):
  user    namespace `students/<name>` of the entry; for the root namespace (the OIDC and terminal
          logins, the shared secret/), the caller's display_name `oidc-<name>` / `jwt-<name>`
          (token display names, set by the login). Anything else is skipped.
  event   login    path `auth/<mount>/login` (and the OIDC `callback`);   mount = <mount>
          wrapping path `sys/wrapping/*`
          request  any other request by a student, except UI and housekeeping reads
          (`sealed` is never sent: a sealed OpenBao is not unsealed enough to audit.)
  ok      false when the entry carries an error
  status  403 for "permission denied", 404 for a read that answered nothing (no data, no auth,
          no wrap info: how a missing KV path looks), 400 for any other error, else 200
  root    the calling token's policies include `root`
  op      the request operation (read, create, update, delete, list)
  path    the request path inside the namespace
  role    the first policy that is not `default`: the token's policy when it made the request,
          the policy the login handed out when it succeeded. (OpenBao hashes the *role name* in a
          login, so the policy stands in for it: `ci-read` for Lab 9's jobs, `app-read` for the
          app, `app-deliver` for the pipeline, `nightly-report` for the leaked token.)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# adapter_client: modules/_shared/ in the source tree, ./_shared/ once ./run.sh has copied it (SHARED= in module.env).
sys.path[:0] = [os.path.join(HERE, "..", "..", "_shared"), os.path.join(HERE, "_shared")]
from adapter_client import AdapterClient  # noqa: E402

STUDENTS = "students/"
SKIP_PREFIXES = ("sys/internal/", "sys/capabilities-self", "sys/health", "sys/seal-status", "sys/leader",
                 "sys/mounts", "sys/auth", "auth/token/lookup-self", "auth/token/renew-self")
SKIP_EXACT = ("sys/capabilities", "sys/policies/acl")
PREFIX_USERS = ("oidc-", "jwt-")


def _policies(auth):
    out = []
    for key in ("policies", "token_policies"):
        for p in auth.get(key) or []:
            if isinstance(p, str) and p not in out:
                out.append(p)
    return out


def _user(ns, auth):
    if ns.startswith(STUDENTS):
        name = ns[len(STUDENTS):].split("/")[0]
        return name or None
    if ns == "":
        shown = auth.get("display_name") or ""
        for prefix in PREFIX_USERS:
            if shown.startswith(prefix) and len(shown) > len(prefix):
                return shown[len(prefix):]
    return None


def classify(entry):
    """The event to post for one audit entry, or None."""
    if not isinstance(entry, dict) or entry.get("type") != "response":
        return None
    req = entry.get("request") or {}
    resp = entry.get("response") or {}
    ns = ((req.get("namespace") or {}).get("path") or "").strip("/")
    path = (req.get("path") or "").strip("/")
    op = req.get("operation")
    if not path or not isinstance(op, str):
        return None
    # A refused request has a top-level `error`, except a logical error (HTTP 400, e.g. a JWT login whose claims don't
    # match a role), which OpenBao logs with only `response.data.error`, HMAC'd like every other value.
    data = resp.get("data")
    failed = bool(entry.get("error")) or (isinstance(data, dict) and set(data) == {"error"})
    # A successful login's response carries the *new* token's auth block (policies, display name);
    # a failed one has none, and every other request is judged by the caller's own auth block.
    is_login = path.startswith("auth/") and (path.endswith("/login") or path.endswith("/callback"))
    auth = (resp.get("auth") if is_login else None) or entry.get("auth") or {}
    user = _user(ns, auth) or _user(ns, entry.get("auth") or {})
    if not user:
        return None
    parts = path.split("/")
    if len(parts) >= 3 and parts[0] == "auth" and parts[-1] in ("login", "callback"):
        mount = "/".join(parts[1:-1]) if parts[-1] == "login" else parts[1]
        event = "login"
    elif path.startswith("sys/wrapping/"):
        mount, event = None, "wrapping"
    else:
        if path.startswith(SKIP_PREFIXES) or path in SKIP_EXACT or op == "help":
            return None
        mount, event = None, "request"
    caller = entry.get("auth") or {}
    policies = _policies(auth if event == "login" and not failed else caller)
    role = next((p for p in policies if p != "default"), None)
    err = str(entry.get("error") or "")
    if not failed:
        empty = not (resp.get("data") or resp.get("auth") or resp.get("wrap_info"))
        status = 404 if event == "request" and op == "read" and empty else 200
    elif "permission denied" in err:
        status = 403
    else:
        status = 400
    ev = {"source": "bao", "event": event, "user": user, "ok": not failed, "status": status,
          "root": "root" in _policies(caller), "op": op, "path": path}
    if mount:
        ev["mount"] = mount
    if role:
        ev["role"] = role
    return ev


class Reporter:
    def __init__(self, url, secret, timeout=2, send=None, size=500):
        self.client = AdapterClient(url, secret, "bao", timeout=timeout, send=send, size=size)
        self.enabled = self.client.enabled
        self.live = False       # off while the first pass reads what was logged before we started

    def entry(self, entry):
        """Report one audit entry if it is a student's doing. Never raises, never blocks."""
        if not (self.enabled and self.live):
            return
        try:
            ev = classify(entry)
            if ev:
                self.client.post(ev)
        except Exception:  # noqa: BLE001
            pass
