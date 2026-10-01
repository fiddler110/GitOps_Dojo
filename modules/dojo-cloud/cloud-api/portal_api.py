"""Dojo Portal backend: serves the SPA and the JSON API under /cloud/ (TOFU-BASICS-PLAN.md §5.6).

Trust: identity is taken from X-Auth-User ONLY when the request also carries
X-Gateway-Token equal to $GATEWAY_TOKEN (students can curl cloud-api directly, so a
bare header is forgeable). Students authorise on subscription ownership; the
facilitator can act on any. Everything sent to the SPA is student-controlled data:
JSON only, never HTML built here.

Talks to Docker only outside State.lock: data is snapshotted under the lock, the
lock is released, then the executor is called. Container status comes from ONE list
call per ~2 s for the whole class, not one inspect per container.
"""
import copy
import hmac
import json
import os
import threading
import time
from urllib.parse import unquote

import auth
import docker_api
import policy
import state as state_mod

PORTAL_DIR = "/app/portal"
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
       "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'")
# Fixed allow-list: request name -> (file in PORTAL_DIR, Content-Type). Nothing else is served,
# and the request never becomes part of a filesystem path.
STATIC = {
    "index.html": ("index.html", "text/html; charset=utf-8"),
    "app.js": ("app.js", "text/javascript; charset=utf-8"),
    "app.css": ("app.css", "text/css; charset=utf-8"),
    "favicon.svg": ("favicon.svg", "image/svg+xml"),
}
STATUS_TTL = 2.0       # seconds the "which containers are running" list is reused
STATUS_STALE_MAX = 10.0  # seconds after the last good list that a stale one may still be shown when cloud-host stops answering
DEFAULT_TAIL, MAX_TAIL = 200, 500
DEFAULT_EVENTS, MAX_EVENTS = 200, 500
MAX_LOG_CHARS = 64_000
FAILURE_WINDOW = 15 * 60  # seconds: how far back the class progress board counts Failed events
MAX_LAST_MESSAGE = 200
TIME_FORMAT = state_mod.TIME_FORMAT
MAX_TAGS, MAX_TAG_KEY, MAX_TAG_VALUE = 15, 512, 256


def _json(status, obj, headers=None):
    hdrs = {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff"}
    hdrs.update(headers or {})
    return status, hdrs, json.dumps(obj).encode()


def _err(status, code, message):
    return _json(status, {"error": {"code": code, "message": message}})


def _int_param(query, name, default, low, high):
    """Clamped integer query parameter; ValueError if present but not a number."""
    raw = (query.get(name) or [None])[0]
    if raw is None or raw == "":
        return default
    return max(low, min(high, int(raw)))


class Portal:
    def __init__(self, app, env=None, portal_dir=None):
        self.app = app
        self.env = os.environ if env is None else env
        self.dir = portal_dir or self.env.get("PORTAL_DIR", PORTAL_DIR)
        self._run_lock = threading.Lock()  # guards the status cache ONLY (not State.lock)
        self._run_set, self._run_at, self._run_ok = None, None, None  # _run_ok: when the list last succeeded

    # ---- entry point ---------------------------------------------------------
    def dispatch(self, method, path, query, headers, body):
        """-> (status, {header: value}, body bytes). `path` is the raw request path."""
        try:
            segs = [unquote(s) for s in path.split("/") if s]
            if [s.lower() for s in segs[:2]] == ["cloud", "api"]:
                return self._api(method, segs[2:], query, headers, body)
            return self._static(method, path)
        except docker_api.DockerError:
            return _err(502, "CloudHostUnavailable", "The cloud host is not answering; try again shortly.")

    # ---- static SPA ----------------------------------------------------------
    def _static(self, method, path):
        if method not in ("GET", "HEAD"):
            return _err(405, "MethodNotAllowed", method)
        if path == "/cloud":
            return 301, {"Location": "/cloud/"}, b""
        parts = unquote(path).split("/")  # exact: no empty/extra segments, no encoded slashes
        if [p.lower() for p in parts] == ["", "cloud", ""]:
            name = "index.html"
        elif len(parts) == 4 and parts[0] == "" and parts[1].lower() == "cloud" and parts[2] == "static" \
                and parts[3] in STATIC:
            name = parts[3]
        else:
            return _err(404, "NotFound", "No such file.")
        filename, ctype = STATIC[name]
        try:
            with open(os.path.join(self.dir, filename), "rb") as f:
                data = f.read()
        except OSError:
            return _err(404, "NotFound", "The portal front end is not installed in this image.")
        return 200, {"Content-Type": ctype, "Content-Security-Policy": CSP,
                     "X-Content-Type-Options": "nosniff", "Cache-Control": "no-cache"}, data

    # ---- identity ------------------------------------------------------------
    def _identity(self, headers):
        """-> (user, None) or (None, error response)."""
        expected = self.env.get("GATEWAY_TOKEN") or ""
        if not expected:
            return None, _err(503, "PortalNotConfigured", "The portal is not configured (GATEWAY_TOKEN is unset).")
        given = headers.get("X-Gateway-Token") or ""
        user = headers.get("X-Auth-User") or ""
        if not user or not hmac.compare_digest(given.encode(), expected.encode()):
            return None, _err(401, "Unauthenticated", "Sign in through the gateway.")
        if user not in self.app.auth.users:  # roster incl. the facilitator
            return None, _err(403, "Forbidden", "You are not part of this workshop.")
        return user, None

    def _is_fac(self, user):
        return self.app.auth.is_facilitator(user)

    def _own_or_fac(self, user, sub):
        """Subscription ownership (same rule as ARM). -> error response or None."""
        if not (self._is_fac(user) or sub == auth.subscription_id(user)):
            return _err(403, "AuthorizationFailed",
                        f"The signed-in user does not have authorization over subscription '{sub}'.")
        if sub not in self.app.auth.by_subscription:
            return _err(404, "SubscriptionNotFound", f"The subscription '{sub}' could not be found.")
        return None

    def write_actions(self):
        with self.app.state.lock:
            return bool(self.app.state.data.get("settings", {}).get("writeActions", True))

    # ---- router --------------------------------------------------------------
    def _check_read(self, method, segs, query, headers):
        """The achievements service's read-only credential (X-Check-Token, derived by module.env): it may
        only GET the caller's own overview, so it can't act as anyone or change anything.
        -> (user, response) when it applies, else None."""
        given, expected = headers.get("X-Check-Token") or "", self.env.get("CLOUD_CHECK_TOKEN") or ""
        if not given or not expected:
            return None
        user = headers.get("X-Auth-User") or ""
        if not hmac.compare_digest(given.encode(), expected.encode()) or user not in self.app.auth.users:
            return user, _err(401, "Unauthenticated", "The check token or account is not valid.")
        if method != "GET" or segs != ["overview"] or (query.get("scope") or ["mine"])[0] != "mine":
            return user, _err(403, "Forbidden", "The check token can only read an account's own overview.")
        return user, self._overview(user, query)

    def _api(self, method, segs, query, headers, body):
        checked = self._check_read(method, segs, query, headers)
        if checked:
            return checked[1]
        user, err = self._identity(headers)
        if err:
            return err
        if not self._is_fac(user):
            self.app.events.emit("portal_request", user, every=60)
        head = segs[0].lower() if segs else ""
        try:
            if head == "me" and len(segs) == 1:
                return self._only(method, "GET") or self._me(user)
            if head == "overview" and len(segs) == 1:
                return self._only(method, "GET") or self._overview(user, query)
            if head == "activity" and len(segs) == 1:
                return self._only(method, "GET") or self._activity(user, query)
            if head == "containers" and len(segs) in (4, 5):
                return self._container(method, user, segs, query, body)
            if head == "admin" and len(segs) == 2 and segs[1].lower() in ("settings", "purge", "progress"):
                return self._admin(method, user, segs[1].lower(), body)
        except ValueError:  # non-numeric limit/tail
            return _err(400, "InvalidQueryParameter", "A numeric query parameter was not a number.")
        return _err(404, "NotFound", f"No handler for '/cloud/api/{'/'.join(segs)}'.")

    @staticmethod
    def _only(method, *allowed):
        return None if method in allowed else _err(405, "MethodNotAllowed", method)

    @staticmethod
    def _json_body(body):
        try:
            data = json.loads(body or b"{}")
            return data if isinstance(data, dict) else None
        except (ValueError, RecursionError):  # RecursionError: absurdly deeply nested JSON
            return None

    # ---- snapshots (under the lock, no I/O) ------------------------------------
    @staticmethod
    def _tags(rec):
        tags = rec.get("tags")
        return {str(k): str(v) for k, v in tags.items()} if isinstance(tags, dict) else {}

    def _cg_summary(self, sub, rec, viewer_sub):
        ip, fqdn = self.app.cg_endpoint(rec)
        spec = rec.get("spec") or {}
        return {
            "id": f"/subscriptions/{sub}/resourceGroups/{rec['rg']}/providers/"
                  f"Microsoft.ContainerInstance/containerGroups/{rec['name']}",
            "name": rec["name"], "resourceGroup": rec["rg"], "subscriptionId": sub,
            "owner": rec.get("owner", ""), "location": rec["location"], "state": "Unknown",
            "fqdn": fqdn, "ip": ip, "image": spec.get("image", ""), "cpu": spec.get("cpu"),
            "memoryGb": spec.get("mem"), "tags": self._tags(rec), "dnsLabel": rec["dnsLabel"],
            "siteUrl": f"/cloud/site/{rec['dnsLabel']}/", "isMine": sub == viewer_sub,
        }

    def _snapshot(self, viewer_sub, only_sub=None):
        """-> (resource groups, [(container group summary, container name)])."""
        st, by_sub = self.app.state, self.app.auth.by_subscription
        rgs, cgs = [], []
        with st.lock:
            counts = {}  # containers per "<sub>/<rg>"
            for key in st.cgs:
                rg_key = key.rsplit("/", 1)[0]
                counts[rg_key] = counts.get(rg_key, 0) + 1
            for key, rec in st.rgs.items():
                sub = key.split("/", 1)[0]
                if only_sub is not None and sub != only_sub:
                    continue
                rgs.append({"id": f"/subscriptions/{sub}/resourceGroups/{rec['name']}", "name": rec["name"],
                            "subscriptionId": sub, "owner": by_sub.get(sub, ""), "location": rec["location"],
                            "tags": self._tags(rec), "containerCount": counts.get(key, 0),
                            "isMine": sub == viewer_sub})
            for key, rec in st.cgs.items():
                sub = key.split("/", 1)[0]
                if only_sub is not None and sub != only_sub:
                    continue
                cgs.append((self._cg_summary(sub, rec, viewer_sub), rec["container"]))
        rgs.sort(key=lambda r: (r["subscriptionId"], r["name"].lower()))
        cgs.sort(key=lambda c: (c[0]["subscriptionId"], c[0]["resourceGroup"].lower(), c[0]["name"].lower()))
        return rgs, cgs

    # ---- container status: one list call per ~2 s for everybody ------------------
    def _running(self):
        """Set of running container names, or None if cloud-host cannot be asked and nothing
        recent (STATUS_STALE_MAX) is cached. Never called with State.lock held."""
        with self._run_lock:
            now = time.monotonic()
            if self._run_at is not None and now - self._run_at < STATUS_TTL:
                return self._run_set
            try:
                self._run_set = set(self.app.executor.list_running())
                self._run_ok = now
            except docker_api.DockerError:
                # A blip keeps the last answer for a moment; a real outage must not keep saying "Running"
                # for a container nobody can see (the states then read "Unknown").
                if self._run_ok is None or now - self._run_ok > STATUS_STALE_MAX:
                    self._run_set = None
            self._run_at = now
            return self._run_set

    def _invalidate(self):
        with self._run_lock:
            self._run_at = None

    def _apply_state(self, cgs):
        running = self._running()
        out = []
        for summary, container in cgs:
            if running is not None:
                summary["state"] = "Running" if container in running else "Terminated"
            out.append(summary)
        return out

    # ---- endpoints ---------------------------------------------------------------
    def _me(self, user):
        sub = auth.subscription_id(user)
        with self.app.state.lock:
            used = sum(1 for k in self.app.state.cgs if k.startswith(sub + "/"))
        return _json(200, {"user": user, "subscriptionId": sub, "isFacilitator": self._is_fac(user),
                           "writeActions": self.write_actions(),
                           "quota": {"containerGroups": {"used": used, "limit": policy.MAX_CONTAINER_GROUPS}},
                           "publicBaseUrl": self.env.get("PUBLIC_BASE_URL", "")})

    def _overview(self, user, query):
        scope = (query.get("scope") or ["mine"])[0]
        if scope not in ("mine", "class"):
            return _err(400, "InvalidQueryParameter", "scope must be 'mine' or 'class'.")
        sub = auth.subscription_id(user)
        rgs, cgs = self._snapshot(sub, None if scope == "class" else sub)
        return _json(200, {"resourceGroups": rgs, "containerGroups": self._apply_state(cgs),
                           "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})

    def _activity(self, user, query):
        scope = (query.get("scope") or ["mine"])[0]
        if scope not in ("mine", "all"):
            return _err(400, "InvalidQueryParameter", "scope must be 'mine' or 'all'.")
        if scope == "all" and not self._is_fac(user):
            return _err(403, "Forbidden", "Only the facilitator can see the whole class's activity.")
        limit = _int_param(query, "limit", DEFAULT_EVENTS, 1, MAX_EVENTS)
        sub = auth.subscription_id(user)
        with self.app.state.lock:
            events = [dict(e) for e in self.app.state.data["activity"] if scope == "all" or e["subscription"] == sub]
        return _json(200, {"events": events[::-1][:limit]})

    def _container(self, method, user, segs, query, body):
        sub, rg, name = segs[1].lower(), segs[2], segs[3]
        is_logs = len(segs) == 5
        if is_logs and segs[4].lower() != "logs":
            return _err(404, "NotFound", "No such resource.")
        denied = self._own_or_fac(user, sub)
        if denied:
            return denied
        st, key = self.app.state, self.app.cg_key(sub, rg, name)
        if is_logs:
            return self._only(method, "GET") or self._logs(key, rg, name, query)
        if method == "GET":
            with st.lock:
                rec = st.cgs.get(key)
                snap = None if rec is None else (self._cg_summary(sub, rec, auth.subscription_id(user)),
                                                 copy.deepcopy(rec))
            if snap is None:
                return self._not_found(rg, name)
            summary, rec = snap
            (summary,) = self._apply_state([(summary, rec["container"])])
            running = summary["state"] == "Running"
            return _json(200, {"summary": summary, "arm": self.app.cg_body(sub, rec, running)})
        if method not in ("DELETE", "PATCH"):
            return _err(405, "MethodNotAllowed", method)
        if not self._is_fac(user) and not self.write_actions():
            return _err(403, "PortalWriteActionsDisabled", "The facilitator has switched off portal write actions.")
        refused = self.app.readiness.refusal()  # before anything is changed; reads above keep working
        if refused:
            return _err(503, "ServiceUnavailable", refused)
        if method == "DELETE":
            try:
                if not self.app.delete_container_group(sub, rg, name, user, via="portal"):
                    return self._not_found(rg, name)
            except state_mod.Busy as exc:  # an operation on it is in flight: same words as the ARM 409
                return _err(409, "Conflict", str(exc))
            self._invalidate()
            return _json(200, {"deleted": True})
        return self._patch(user, sub, rg, name, key, body)

    @staticmethod
    def _not_found(rg, name):
        return _err(404, "ResourceNotFound", f"The container group '{name}' under resource group '{rg}' was not found.")

    def _patch(self, user, sub, rg, name, key, body):
        data = self._json_body(body)
        tags = None if data is None else data.get("tags")
        if not isinstance(tags, dict) or len(tags) > MAX_TAGS or not all(
                isinstance(k, str) and isinstance(v, str) and len(k) <= MAX_TAG_KEY and len(v) <= MAX_TAG_VALUE
                for k, v in tags.items()):
            return _err(400, "InvalidRequestContent",
                        f"The body must be {{\"tags\": {{...}}}} with at most {MAX_TAGS} string-to-string tags.")
        try:
            rec = self.app.update_container_group_tags(sub, rg, name, user, tags, via="portal")
        except policy.PolicyError as exc:
            return _json(exc.status, exc.body())
        except LookupError:
            return self._not_found(rg, name)
        (summary,) = self._apply_state([(self._cg_summary(sub, rec, auth.subscription_id(user)), rec["container"])])
        return _json(200, {"summary": summary})

    def _logs(self, key, rg, name, query):
        tail = _int_param(query, "tail", DEFAULT_TAIL, 1, MAX_TAIL)
        with self.app.state.lock:
            rec = self.app.state.cgs.get(key)
            container = None if rec is None else rec["container"]
        if container is None:
            return self._not_found(rg, name)
        text = self.app.executor.logs(container, tail) or ""
        return _json(200, {"logs": text[-MAX_LOG_CHARS:]})

    # ---- facilitator ---------------------------------------------------------------
    def _admin(self, method, user, what, body):
        if not self._is_fac(user):
            return _err(403, "Forbidden", "Facilitator only.")
        st = self.app.state
        if what == "progress":
            return self._only(method, "GET") or self._progress(user)
        if what == "settings":
            if method == "GET":
                return _json(200, {"writeActions": self.write_actions()})
            if method != "PUT":
                return _err(405, "MethodNotAllowed", method)
            data = self._json_body(body)
            if data is None or not isinstance(data.get("writeActions"), bool):
                return _err(400, "InvalidRequestContent", 'The body must be {"writeActions": true|false}.')
            with st.lock:
                st.data.setdefault("settings", {})["writeActions"] = data["writeActions"]
                st.log(auth.subscription_id(user), user, "Change portal settings", "/dojo/portal/settings",
                       "Succeeded", f"writeActions={str(data['writeActions']).lower()}")
                st.save()
            return _json(200, {"writeActions": data["writeActions"]})
        if method != "POST":
            return _err(405, "MethodNotAllowed", method)
        data = self._json_body(body)
        sub = str((data or {}).get("subscriptionId") or "").lower()
        if sub not in self.app.auth.by_subscription:
            return _err(404, "SubscriptionNotFound", "Unknown subscriptionId.")
        return self._purge(user, sub)

    def _progress(self, user):
        """Class progress board (TOFU-BASICS-PLAN.md 5.6a): one row per roster user except the facilitator.
        `user` is the (already authorised) facilitator."""
        now, st = time.time(), self.app.state
        by_sub = {}  # sub -> {"rgs": n, "cgs": [(summary, container)]}
        with st.lock:  # snapshot only: no Docker, no per-student work
            for key in st.rgs:
                self._bucket(by_sub, key.split("/", 1)[0])["rgs"] += 1
            for key, rec in st.cgs.items():
                summary = {"name": rec["name"], "resourceGroup": rec["rg"], "state": "Unknown",
                           "siteUrl": f"/cloud/site/{rec['dnsLabel']}/"}
                self._bucket(by_sub, key.split("/", 1)[0])["cgs"].append((summary, rec["container"]))
            # Latest event + recent Failed count per subscription: kept by State.log(), so this does not
            # scan the activity log and a busy student cannot push another's failures out of view.
            # `failures` is capped at state_mod.FAILURES_KEPT (100) per student.
            recent = st.activity_summary(now - FAILURE_WINDOW)
        for b in by_sub.values():
            b["cgs"].sort(key=lambda c: (c[0]["resourceGroup"].lower(), c[0]["name"].lower()))
        # State for every container group in the class from ONE cached list call, outside the lock.
        self._apply_state([c for b in by_sub.values() for c in b["cgs"]])
        students, summary = [], {"total": 0, "notStarted": 0, "inProgress": 0, "running": 0, "attention": 0}
        for name in self.app.auth.users:
            if self._is_fac(name):
                continue
            sub = auth.subscription_id(name)
            b = by_sub.get(sub) or self._bucket({}, sub)
            last, failures = recent.get(sub, (None, 0))
            cgs = [c[0] for c in b["cgs"]]
            if (last and last.get("status") == "Failed") or any(c["state"] == "Terminated" for c in cgs):
                stage = "attention"
            elif cgs and all(c["state"] == "Running" for c in cgs):
                stage = "running"
            elif b["rgs"] or cgs or last:
                stage = "inProgress"
            else:
                stage = "notStarted"
            summary["total"] += 1
            summary[stage] += 1
            students.append({
                "user": name, "subscriptionId": sub, "stage": stage, "resourceGroups": b["rgs"],
                "containerGroups": [{k: c[k] for k in ("name", "resourceGroup", "state", "siteUrl")} for c in cgs],
                "lastEvent": None if not last else {
                    "time": last.get("time", ""), "operation": last.get("operation", ""),
                    "status": last.get("status", ""), "message": str(last.get("message") or "")[:MAX_LAST_MESSAGE]},
                "failures": failures})
        return _json(200, {"generatedAt": time.strftime(TIME_FORMAT, time.gmtime(now)),
                           "summary": summary, "students": students})

    @staticmethod
    def _bucket(by_sub, sub):
        return by_sub.setdefault(sub, {"rgs": 0, "cgs": []})

    def _purge(self, user, sub):
        st, prefix = self.app.state, sub + "/"
        with st.lock:
            containers = [st.cgs.pop(k)["container"] for k in [k for k in st.cgs if k.startswith(prefix)]]
            rg_keys = [k for k in st.rgs if k.startswith(prefix)]
            for k in rg_keys:
                del st.rgs[k]
            st.save()
        orphaned = 0
        for container in containers:  # Docker only after the lock is released
            try:
                orphaned += 0 if self.app.executor.remove(container) else 1
            except docker_api.DockerError:
                orphaned += 1
        self._invalidate()
        with st.lock:
            st.log(sub, user, "Purge subscription (portal)", f"/subscriptions/{sub}",
                   "Succeeded" if not orphaned else "Failed",
                   f"removed {len(containers)} container group(s), {len(rg_keys)} resource group(s)"
                   + (f"; {orphaned} container(s) could not be removed" if orphaned else ""))
            st.save()
        removed = {"containerGroups": len(containers), "resourceGroups": len(rg_keys)}
        return _json(200, {"removed": removed, **({"orphanedContainers": orphaned} if orphaned else {})})
