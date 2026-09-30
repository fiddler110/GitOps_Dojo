"""The Forgejo system webhook: its shared secret, its signature check and its registration.

Forgejo sends every push, branch or tag create/delete, pull request and review in the whole
instance to POST /api/forgejo on this service, signed with HMAC-SHA256 of the raw body under a
shared secret (header X-Forgejo-Signature, hex; X-Gitea-Signature carries the same value).
The lab network can reach this service directly, so an unsigned or wrongly signed delivery is
refused.

The service registers the hook itself at start (no engine change, no terminal hook): it asks
Forgejo's admin API, as FORGEJO_ADMIN_USER, for the system hooks, removes any that point at
this service, and creates one with the current secret. Forgejo must also be allowed to deliver
to this host: the module's compose.yml adds `achievements` to git-server's
[webhook] ALLOWED_HOST_LIST.
"""

import base64
import hashlib
import hmac
import json
import threading
import time
import urllib.error
import urllib.request

EVENTS = ["push", "create", "delete", "pull_request", "pull_request_review"]


def secret_from(gateway_token):
    """A per-run secret derived from the service's gateway token, so a restart keeps it."""
    if not gateway_token:
        return None
    return hmac.new(gateway_token.encode(), b"achievements forgejo webhook", hashlib.sha256).hexdigest()


def signature(secret, body):
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify(secret, body, headers):
    """True when the delivery carries a valid signature for `body` (bytes)."""
    if not secret:
        return False
    sent = headers.get("X-Forgejo-Signature") or headers.get("X-Gitea-Signature") or ""
    return hmac.compare_digest(signature(secret, body).encode(), sent.strip().lower().encode())


def event_kind(headers):
    return headers.get("X-Forgejo-Event") or headers.get("X-Gitea-Event") or ""


def hook_body(url, secret):
    return {"type": "forgejo", "active": True, "events": EVENTS, "branch_filter": "*",
            "config": {"url": url, "content_type": "json", "secret": secret}}


def ensure(api, url, secret):
    """Make exactly one system hook point at `url`, with `secret`.

    `api(method, path, body=None) -> (status, parsed JSON or None)`, paths under /api/v1.
    Returns True when the hook is in place."""
    status, hooks = api("GET", "/admin/hooks?limit=50")
    if status != 200 or not isinstance(hooks, list):
        return False
    for h in hooks:
        cfg = h.get("config") if isinstance(h, dict) else None
        if isinstance(cfg, dict) and cfg.get("url") == url and h.get("id") is not None:
            api("DELETE", f"/admin/hooks/{h['id']}")
    status, _ = api("POST", "/admin/hooks", hook_body(url, secret))
    return status == 201


def forgejo_api(base_url, user, password):
    """An `api` for `ensure` that talks to Forgejo with basic auth."""
    auth = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()

    def api(method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(base_url.rstrip("/") + "/api/v1" + path, data=data, method=method,
                                     headers={"Authorization": auth, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                raw = r.read()
                return r.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            return e.code, None
        except (urllib.error.URLError, OSError, ValueError):
            return 0, None
    return api


def register_in_background(api, url, secret, log, sleep=time.sleep, tries=120, delay=5):
    """Keep trying `ensure` until it works (Forgejo and its admin come up after this service)."""
    def run():
        for n in range(tries):
            try:
                if ensure(api, url, secret):
                    log(f"forgejo webhook registered -> {url}")
                    return
            except Exception as exc:    # a bad answer must not kill the thread
                log(f"forgejo webhook: {exc!r}")
            sleep(delay if n < 60 else delay * 6)
        log("forgejo webhook: gave up registering; Forgejo events will not score")
    t = threading.Thread(target=run, name="forgejo-webhook", daemon=True)
    t.start()
    return t
