"""OpenTofu `http` state backend on the fake ARM host: /_dojo/tfstate/<name>.

A student's terminal and their Forgejo Actions jobs share one state per name. Auth is HTTP Basic with the student's
ARM client id and secret (the same check as the client_credentials token flow); the state belongs to that
client's subscription and hangs off State.data["tfstate"][sub] = {"states": {name: text}, "locks": {name: info}}.
A lock lasts until UNLOCK (no expiry): `tofu force-unlock` is the escape hatch. State content is never logged.
"""
import base64
import binascii
import json
import re
from urllib.parse import parse_qs

import auth

PREFIX = "/_dojo/tfstate/"
NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
MAX_BYTES = 2 * 1024 * 1024
MAX_STATES = 10
REALM = 'Basic realm="dojo-tfstate"'


def _reply(status, body=None, headers=None):
    if isinstance(body, (dict, list)):
        return status, json.dumps(body).encode(), {"Content-Type": "application/json", **(headers or {})}
    return status, body or b"", {"Content-Type": "application/json", **(headers or {})}


def _err(status, code, message, headers=None):
    return _reply(status, {"error": {"code": code, "message": message}}, headers)


def _doc(st, sub):
    """The subscription's tfstate document, created on first write. Caller holds the lock."""
    d = st.data.setdefault("tfstate", {}).setdefault(sub, {})
    d.setdefault("states", {})
    d.setdefault("locks", {})
    return d


def purge(st, sub):
    """Forget the subscription's states and locks (caller holds the lock) -> how many states there were."""
    d = (st.data.get("tfstate") or {}).pop(sub, None)
    return len(d["states"]) if d else 0


def credentials(header):
    try:
        raw = base64.b64decode(header.split(None, 1)[1], validate=True).decode()
        cid, _, secret = raw.partition(":")
        return cid, secret
    except (IndexError, ValueError, binascii.Error):
        return None


def handle(app, limiter, method, path, query, auth_header, read_body):
    """-> (status, bytes, headers). `read_body(limit)` returns up to limit bytes; handle only calls it once the
    caller is authenticated, so an unauthenticated client cannot make us read megabytes."""
    challenge = {"WWW-Authenticate": REALM}
    creds = credentials(auth_header or "")
    user = app.auth.authenticate_client(*creds) if creds else None
    if user is None:
        return _err(401, "Unauthorized", "Use your ARM client id and secret as the HTTP Basic username and password.",
                    challenge)
    name = path[len(PREFIX):]
    if not NAME.match(name):
        return _err(400, "InvalidName", "State names are 1-40 characters of a-z, 0-9 and '-', starting with a letter or digit.")
    wait = limiter.take(user)
    if wait:
        return _err(429, "TooManyRequests", "Too many requests: slow down and retry.", {"Retry-After": str(wait)})
    q = parse_qs(query or "")
    sub = auth.subscription_id(user)
    other = (q.get("subscription") or [""])[0].lower()
    if other and other != sub:
        if method != "GET" or not app.auth.is_facilitator(user) or other not in app.auth.by_subscription:
            return _err(403, "Forbidden", "Only the facilitator may read another subscription's state.")
        sub = other
    body = b""
    if method in ("POST", "LOCK", "UNLOCK"):
        body = read_body(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            return _err(413, "StateTooLarge", f"State is limited to {MAX_BYTES // 1024} KiB.")
    st = app.state
    body_id = ""
    if method in ("LOCK", "UNLOCK") and body.strip():
        try:
            info = json.loads(body)
            body_id = str(info.get("ID") or "") if isinstance(info, dict) else ""
        except ValueError:
            if method == "LOCK":
                return _err(400, "InvalidBody", "Lock info must be JSON.")
    lock_id = (q.get("ID") or [""])[0] or body_id
    with st.lock:
        if method == "GET":
            text = (st.data.get("tfstate") or {}).get(sub, {}).get("states", {}).get(name)
            if text is None:
                return _err(404, "StateNotFound", f"No state named '{name}'.")
            return _reply(200, text.encode())
        d = _doc(st, sub)
        held = d["locks"].get(name)
        if method == "LOCK":
            if held:
                return _reply(423, held)
            try:
                info = json.loads(body) if body.strip() else {}
            except ValueError:
                info = {}
            if not isinstance(info, dict):
                return _err(400, "InvalidBody", "Lock info must be a JSON object.")
            info.setdefault("ID", lock_id or "unknown")
            d["locks"][name] = info
            st.save()
            return _reply(200, info)
        if method == "UNLOCK":
            if held and lock_id and held.get("ID") != lock_id:
                return _reply(409, held)
            d["locks"].pop(name, None)  # no ID = force unlock; nothing held = still fine
            st.save()
            return _reply(200, {})
        if method in ("POST", "DELETE"):
            if held and held.get("ID") != lock_id:
                return _reply(409, held)
            if method == "DELETE":
                existed = d["states"].pop(name, None) is not None
                if existed:
                    st.log(sub, user, f"Delete state {name}", f"/_dojo/tfstate/{name}", "Succeeded")
                st.save()
                return _reply(200, {})
            try:
                text = body.decode()
            except UnicodeDecodeError:
                return _err(400, "InvalidBody", "State must be UTF-8 JSON.")
            if name not in d["states"] and len(d["states"]) >= MAX_STATES:
                return _err(507, "QuotaExceeded", f"At most {MAX_STATES} states per subscription; delete one first.")
            d["states"][name] = text
            st.log(sub, user, f"Save state {name}", f"/_dojo/tfstate/{name}", "Succeeded")
            st.save()
            return _reply(200, {})
    return _err(405, "MethodNotAllowed", f"{method} is not supported.", {"Allow": "GET, POST, DELETE, LOCK, UNLOCK"})
