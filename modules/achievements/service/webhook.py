"""The Forgejo system webhook: its shared secret, its signature check and its registration.

Forgejo sends every push, branch or tag create/delete, pull request and review in the whole
instance to POST /api/forgejo on this service, signed with HMAC-SHA256 of the raw body under a
shared secret (header X-Forgejo-Signature, hex; X-Gitea-Signature carries the same value).
The lab network can reach this service directly, so an unsigned or wrongly signed delivery is
refused.

The service registers the hook itself at start (no engine change, no terminal hook): it asks
Forgejo's admin API, as FORGEJO_ADMIN_USER, for the system hooks, removes any that point at
this service, and creates one with the current secret through the admin web form (the API
can only make a default hook, see `forgejo_web_create`). Forgejo must also be allowed to deliver
to this host: the module's compose.yml adds `achievements` to git-server's
[webhook] ALLOWED_HOST_LIST.
"""

import base64
import hashlib
import hmac
import json
import re
import threading
import time
import urllib.error
import urllib.parse
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
    """The event name. Prefer X-Forgejo-Event-Type: Forgejo 16 sends a review as
    X-Forgejo-Event: pull_request_approved but X-Forgejo-Event-Type: pull_request_review_approved."""
    return (headers.get("X-Forgejo-Event-Type") or headers.get("X-Gitea-Event-Type")
            or headers.get("X-Forgejo-Event") or headers.get("X-Gitea-Event") or "")


def ensure(api, create, url, secret):
    """Make exactly one system hook point at `url`, with `secret`.

    `api(method, path, body=None) -> (status, parsed JSON or None)`, paths under /api/v1;
    `create(url, secret) -> bool` makes the system hook (see `forgejo_web_create`).
    GET /admin/hooks lists system hooks, so the check after `create` proves it is one.
    Returns True when the hook is in place."""
    status, hooks = api("GET", "/admin/hooks?limit=50")
    if status != 200 or not isinstance(hooks, list):
        return False
    for h in hooks:
        cfg = h.get("config") if isinstance(h, dict) else None
        if isinstance(cfg, dict) and cfg.get("url") == url and h.get("id") is not None:
            api("DELETE", f"/admin/hooks/{h['id']}")
    if not create(url, secret):
        return False
    status, hooks = api("GET", "/admin/hooks?limit=50")
    return status == 200 and isinstance(hooks, list) and any(
        isinstance(h, dict) and isinstance(h.get("config"), dict) and h["config"].get("url") == url for h in hooks)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def forgejo_web_create(base_url, user, password):
    """A `create` for `ensure` that makes a real *system* hook through Forgejo's admin web form.

    Why the web form: on Forgejo 16 `POST /api/v1/admin/hooks` makes a *default* hook (a
    template copied only into repos created after it, and not listed by GET /admin/hooks, so
    every restart would add another), and the API has no way to ask for a system hook. The
    session cookie is kept by hand: Forgejo scopes it to ROOT_URL's /git/ path, which is not
    the path this service talks to, and redirects (to /git/...) are not followed."""
    base = base_url.rstrip("/")
    opener = urllib.request.build_opener(_NoRedirect)

    def create(url, secret):
        jar = {}

        def req(path, form=None):
            data = urllib.parse.urlencode(form).encode() if form is not None else None
            r = urllib.request.Request(base + path, data,
                                       headers={"Cookie": "; ".join(f"{k}={v}" for k, v in jar.items())})
            try:
                resp = opener.open(r, timeout=10)
                code, body, hdrs = resp.status, resp.read().decode(errors="replace"), resp.headers
            except urllib.error.HTTPError as e:
                code, body, hdrs = e.code, e.read().decode(errors="replace"), e.headers
            for c in hdrs.get_all("Set-Cookie") or []:
                k, _, v = c.split(";")[0].partition("=")
                jar[k.strip()] = v
            return code, body

        def csrf(html):
            # Forgejo 16 has no _csrf token (it checks the request's origin instead); older
            # releases put it in a form field or the page's JS config. Send it when there is one.
            m = re.search(r'name="_csrf" value="([^"]+)"', html) or re.search(r"csrfToken: '([^']+)'", html)
            return {"_csrf": m.group(1)} if m else {}

        code, page = req("/user/login")
        if code != 200:
            return False
        code, _ = req("/user/login", {**csrf(page), "user_name": user, "password": password})
        if code not in (302, 303):
            return False
        code, page = req("/admin/system-hooks/forgejo/new")
        if code != 200:
            return False
        form = {**csrf(page), "payload_url": url, "http_method": "POST", "content_type": "1",
                "secret": secret, "events": "choose_events", "branch_filter": "*", "active": "on"}
        form.update({e: "on" for e in EVENTS})
        code, _ = req("/admin/system-hooks/forgejo/new", form)
        return code in (302, 303)
    return create


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


def register_in_background(api, create, url, secret, log, sleep=time.sleep, tries=120, delay=5):
    """Keep trying `ensure` until it works (Forgejo and its admin come up after this service)."""
    def run():
        for n in range(tries):
            try:
                if ensure(api, create, url, secret):
                    log(f"forgejo webhook registered -> {url}")
                    return
            except Exception as exc:    # a bad answer must not kill the thread
                log(f"forgejo webhook: {exc!r}")
            sleep(delay if n < 60 else delay * 6)
        log("forgejo webhook: gave up registering; Forgejo events will not score")
    t = threading.Thread(target=run, name="forgejo-webhook", daemon=True)
    t.start()
    return t
