#!/usr/bin/env python3
"""Dojo Cloud control plane ("cloud-api").

Speaks just enough Azure Resource Manager for the real `azurerm` provider
(TOFU-BASICS-PLAN.md §5.5): a metadata document, an OAuth client-credentials token
endpoint, and resource groups + container groups. Requests are authenticated
(token -> student), authorised (path subscription must be the caller's), checked
against policy, and executed on cloud-host by a fixed template. Also serves
student sites at /cloud/site/<label>/ (reverse proxy to cloud-host).

Stdlib only, single file per concern, same spirit as engine/allocator.
"""
import copy
import hmac
import http.client
import json
import os
import re
import secrets
import signal
import ssl
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

import auth
import docker_api
import events
import pki
import policy
import portal_api
import state as state_mod

ENV = os.environ
DATA_DIR = ENV.get("CLOUD_DATA_DIR", "/data")
SHARED_PKI = ENV.get("CLOUD_PKI_DIR", "/pki")
SECRETS_DIR = ENV.get("CLOUD_SECRETS_DIR", "/secrets")
DOCKER_SOCKET = ENV.get("CLOUD_DOCKER_SOCKET", "/run/cloud/docker.sock")
CLOUD_HOST = ENV.get("CLOUD_HOST", "cloud-host")
MGMT = "https://management.dojo.cloud"
LOGIN = "https://login.dojo.cloud"
GRAPH = "https://graph.dojo.cloud"
ARM_TYPE_RG = "Microsoft.Resources/resourceGroups"
ARM_TYPE_CG = "Microsoft.ContainerInstance/containerGroups"
SITE_RE = re.compile(r"^/cloud/site/([a-z][a-z0-9-]{2,40})(/.*)?$")
CLIENT_GONE = (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)  # peer hung up mid-exchange
KEEP_TAGS = object()  # update_container_group_tags(): leave the current tag set as it is
READY_INTERVAL = 3.0  # seconds between readiness checks (the only thing that asks cloud-host about it)
RECONCILE_RETRY = 2.0  # seconds between start-up attempts while cloud-host is not answering
HOST_DOWN = "The cloud host is not answering; try again shortly."
# The status ARM refusals use while Dojo Cloud cannot do a write. Not 503: the azurerm provider retries 503 with
# exponential backoff (`plan` sat silent ~4 min, `apply` up to ~10 min before printing the error). A status the provider
# does not retry makes it print the message at once. The ONE place this number lives (tests import it); /readyz and
# the portal API keep their own 503, since neither is called by the provider.
NOT_READY_STATUS = 409
RETRY_HINT = "Wait a minute and run the command again, or tell your facilitator."
# What a container group reads as when cloud-host cannot be asked whether it is running (see Handler.cg_views).
ASSUME_RUNNING = True
# Fixed strings for /readyz (and the refusals a write gets): a reason, never a raw error.
REASONS = {"first": "the first readiness check has not finished",
           "host": "the cloud host is not answering",
           "images": "the cloud host is still loading its app images",
           "reconcile": "the control plane is still syncing with the cloud host"}


def log(msg):
    print(msg, flush=True)


class RateLimit:
    """A token bucket per authenticated identity: a tripwire against a runaway
    loop, far above what a lab does, not a budget (0 = off). Never keyed by
    source IP (all students share one address). The lock covers arithmetic
    only, no I/O."""

    def __init__(self, burst, per_sec, clock=time.monotonic):
        self.burst, self.rate, self.clock = float(burst), float(per_sec), clock
        self.buckets = {}  # key -> [tokens, last]
        self.lock = threading.Lock()

    def take(self, key, scale=1):
        """0 if the request may go now, else seconds until one may. `scale`
        widens the bucket for shared identities (CI, the read key)."""
        if self.burst <= 0 or self.rate <= 0:
            return 0
        burst, rate = self.burst * scale, self.rate * scale
        with self.lock:
            now = self.clock()
            tokens, last = self.buckets.get(key, (burst, now))
            tokens = min(burst, tokens + (now - last) * rate)
            if tokens >= 1:
                self.buckets[key] = (tokens - 1, now)
                return 0
            self.buckets[key] = (tokens, now)
            return max(1, int((1 - tokens) / rate + 0.999))


def _rate(name, default):
    try:
        return float(ENV.get(name, default))
    except ValueError:
        return float(default)


# Per-student ARM request tripwire (CLOUD_API_RATE_*, module.env; 0 = off).
LIMIT = RateLimit(_rate("CLOUD_API_RATE_BURST", 200), _rate("CLOUD_API_RATE_PER_SEC", 20))


def load_signing_key():
    os.makedirs(SECRETS_DIR, exist_ok=True)
    path = f"{SECRETS_DIR}/signing.key"
    if not os.path.exists(path):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_hex(32))
    with open(path, "rb") as f:
        return f.read().strip()


class App:
    def __init__(self, auth_=None, state=None, executor=None):  # arguments: for unit tests
        self.auth = auth_ or auth.Auth(load_signing_key(), auth.roster(ENV), ENV.get("FACILITATOR_USERNAME", "root"),
                                       f"{LOGIN}/{auth.TENANT_ID}/v2.0")
        self.state = state if state is not None else state_mod.State(f"{DATA_DIR}/state.json")
        self.executor = executor or docker_api.Executor(DOCKER_SOCKET)
        self.reconciled = threading.Event()  # set once the start-up reconcile has worked
        self.events = events.from_env(ENV)  # what students did, for the achievements service (off by default)
        self.readiness = Readiness(self)
        self.portal = portal_api.Portal(self, ENV)

    # ---- helpers ---------------------------------------------------------
    @staticmethod
    def rg_key(sub, rg):
        return f"{sub}/{rg.lower()}"

    @staticmethod
    def cg_key(sub, rg, cg):
        return f"{sub}/{rg.lower()}/{cg.lower()}"

    def container_name(self, sub, rg, cg):
        return f"dojo-{self.auth.by_subscription.get(sub, 'x')}-{rg.lower()}-{cg.lower()}"[:120]

    def reconcile(self):
        """Forget container groups whose container vanished; remove orphans.
        Returns False (and can simply be retried) if cloud-host could not be asked or told."""
        st = self.state
        try:
            live = set(self.executor.list_managed())
        except docker_api.DockerError as exc:
            log(f"reconcile skipped: {exc}")
            return False
        with st.lock:
            known = {rec["container"] for rec in st.cgs.values()}
            for key in [k for k, rec in st.cgs.items() if rec["container"] not in live]:
                del st.cgs[key]
            orphans = live - known
            st.save()
        try:
            for orphan in orphans:  # Docker only after the lock is released
                self.executor.remove(orphan)
        except docker_api.DockerError as exc:
            log(f"reconcile skipped: {exc}")
            return False
        log(f"reconciled: {len(st.cgs)} container group(s), {len(st.rgs)} resource group(s)")
        return True

    def start_up(self, stop, retry=RECONCILE_RETRY):
        """Background thread: wait for cloud-host, then reconcile; retries until that has worked
        once, then marks the control plane reconciled. Requests are served (and writes refused,
        see Readiness) all the while."""
        warned = False
        while not stop.is_set():
            try:
                if self.executor.ping() and self.reconcile():
                    self.reconciled.set()
                    return
            except Exception as exc:  # a bug here must not leave the control plane "starting" forever, silently
                log(f"start-up error: {exc!r}")
            if not warned:
                log("cloud-host is not ready yet; will keep trying")
                warned = True
            stop.wait(retry)

    # ---- container-group changes shared by ARM and the portal --------------
    # One implementation, so policy, activity log and executor behave identically
    # whoever asks. `via` ("portal") is appended to the logged operation name.
    # The executor is called with the state lock released: the group is reserved (State.pending) under the lock,
    # Docker is called, then the result is recorded under the lock again and the reservation released (TOFU-BASICS-PLAN.md 5.8).
    @staticmethod
    def op_name(base, via):
        return f"{base} ({via})" if via else base

    def delete_container_group(self, sub, rg, cg, user, via=""):
        """Returns False if there was no such container group; raises state.Busy (nothing changed) if it has an
        operation in flight or its resource group is being deleted."""
        st, key = self.state, self.cg_key(sub, rg, cg)
        rid = f"/subscriptions/{sub}/resourceGroups/{rg}/providers/{ARM_TYPE_CG}/{cg}"
        op = self.op_name("Delete container group", via)
        with st.lock:
            if st.busy(key):
                raise state_mod.Busy()
            rec = st.cgs.get(key)
            if rec is None:
                return False
            st.reserve(key, sub, rec["port"], rec.get("dnsLabel"))
        try:
            try:  # the record stays until the container is really gone: a failed delete changes nothing
                self.executor.remove(rec["container"])
            except docker_api.DockerError:
                with st.lock:
                    st.log(sub, user, op, rid, "Failed", "executor")
                    st.save()
                raise
            with st.lock:
                if st.cgs.pop(key, None) is None:  # the record went another way (a purge)
                    return False
                st.log(sub, user, op, rid, "Succeeded")
                st.save()
            self.report_delete(user, key, via)
            return True
        finally:
            st.release(key)

    def report_refusal(self, user, exc):
        if not self.auth.is_facilitator(user):
            self.events.refused(user, exc)

    def report_delete(self, user, key, via):
        if not self.auth.is_facilitator(user):
            self.events.deleted_group(user, key, via)

    def update_container_group_tags(self, sub, rg, cg, user, tags=KEEP_TAGS, via=""):
        """Replaces the tag set (policy-checked). Returns a snapshot copy of the record;
        raises LookupError if missing, policy.PolicyError on a violation."""
        st, key = self.state, self.cg_key(sub, rg, cg)
        rid = f"/subscriptions/{sub}/resourceGroups/{rg}/providers/{ARM_TYPE_CG}/{cg}"
        op = self.op_name("Update container group tags", via)
        with st.lock:
            rec = st.cgs.get(key)
            if rec is None:
                raise LookupError(key)
            if tags is KEEP_TAGS:
                tags = rec.get("tags") or {}
            try:
                policy.check_tags(cg, tags)
            except policy.PolicyError as exc:
                st.log(sub, user, op, rid, "Failed", f"{exc.code}: {exc.message}")
                if not self.auth.is_facilitator(user):
                    self.events.refused(user, exc)
                raise
            rec["tags"] = tags
            rec["body"]["tags"] = tags
            st.log(sub, user, op, rid, "Succeeded")
            st.save()
            if not self.auth.is_facilitator(user):
                self.events.emit("container_updated", user, via or "arm")
            return copy.deepcopy(rec)

    # ---- ARM representations --------------------------------------------
    @staticmethod
    def cg_endpoint(rec):
        """(ip, fqdn) the way ARM and the portal both present them."""
        return (f"10.20.{rec['port'] // 256}.{rec['port'] % 256}",
                f"{rec['dnsLabel']}.{rec['location']}.dojo-cloud.test")

    def rg_body(self, sub, rec):
        return {"id": f"/subscriptions/{sub}/resourceGroups/{rec['name']}", "name": rec["name"],
                "type": ARM_TYPE_RG, "location": rec["location"], "tags": rec.get("tags") or {},
                "properties": {"provisioningState": "Succeeded"}}

    def cg_body(self, sub, rec, running):
        """The ARM JSON of a stored container group. `running` is the one value Docker provides."""
        body = copy.deepcopy(rec["body"])
        body.update({"id": f"/subscriptions/{sub}/resourceGroups/{rec['rg']}/providers/{ARM_TYPE_CG}/{rec['name']}",
                     "name": rec["name"], "type": ARM_TYPE_CG, "location": rec["location"],
                     "tags": rec.get("tags") or {}})
        props = body.setdefault("properties", {})
        props["provisioningState"] = "Succeeded"
        ip = props.setdefault("ipAddress", {})
        ip["ip"], ip["fqdn"] = self.cg_endpoint(rec)
        state = "Running" if running else "Terminated"
        props["instanceView"] = {"state": state}
        for c in props.get("containers", []):
            cp = c.setdefault("properties", {})
            cp["instanceView"] = {"currentState": {"state": state}}
            for var in cp.get("environmentVariables") or []:
                var.pop("secureValue", None)
        return body


class Readiness:
    """Can Dojo Cloud take work? ONE background thread asks (every READY_INTERVAL); requests only
    read the cached answer, so a poll never costs a Docker call and never touches State.lock.

    Ready = cloud-host's Docker answers AND both allow-listed images are there AND the start-up
    reconcile has finished. `starting` = never ready since this process began; `unavailable` =
    was ready, is not now."""

    def __init__(self, app):
        self.app = app
        self._lock = threading.Lock()  # guards the fields below ONLY: never held across I/O
        self._seen_ready = False
        self._result = (False, "starting", self._detail("starting", "first"))

    @staticmethod
    def _detail(state, reason):
        if state == "ready":
            return "Dojo Cloud is ready."
        # "not ready", not "still starting": after the allocator's start-up grace the facilitator's chip is red,
        # and a red chip must not say "starting" (it would if the host never came up since this process began).
        return f"Dojo Cloud is {'not ready' if state == 'starting' else 'unavailable'}: {REASONS[reason]}."

    def _probe(self):
        """-> None when ready, else the key of the first reason in REASONS that is not met."""
        ex = self.app.executor
        try:
            if not ex.ping():
                return "host"
            if not all(ex.image_present(image) for image in policy.ALLOWED_IMAGES):
                return "images"
        except docker_api.DockerError:
            return "host"
        return None if self.app.reconciled.is_set() else "reconcile"

    def refresh(self):
        """One check, then publish the result. The Docker calls happen before the lock is taken."""
        reason = self._probe()
        with self._lock:
            self._seen_ready = self._seen_ready or reason is None
            state = "ready" if reason is None else ("unavailable" if self._seen_ready else "starting")
            self._result = (reason is None, state, self._detail(state, reason))

    def snapshot(self):
        """-> (ready, state, detail), from the cache."""
        with self._lock:
            return self._result

    def refusal(self):
        """None when ready, else the detail string a write is refused with."""
        ready, _, detail = self.snapshot()
        return None if ready else detail

    def run(self, stop, interval=READY_INTERVAL):
        while not stop.is_set():
            try:
                self.refresh()
            except Exception as exc:  # keep checking; the cached answer stays as it was
                log(f"readiness check error: {exc!r}")
            stop.wait(interval)


APP = None


def arm_error(status, code, message, target=None):
    err = {"code": code, "message": message}
    if target:
        err["target"] = target
    return status, {"error": err}


def busy_reply():
    """The 409 for a write that meets an operation in flight on the same container group (nothing was changed)."""
    return arm_error(409, "Conflict", state_mod.BUSY_MESSAGE)


def host_stopped_message(left):
    """For a write that lost cloud-host part-way. `left`: what state the record was left in (one sentence)."""
    return ("The cloud host stopped answering while this request was running. " + left + " Wait a minute, run "
            "`terraform plan` to see where things stand, then run the command again, or tell your facilitator.")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    # Headers and body are separate send() calls; with keep-alive, Nagle plus
    # the peer's delayed ACK stalls every second small response by ~40 ms
    # (measured through the gateway: /cloud/api/me p50 47 ms -> 5 ms).
    disable_nagle_algorithm = True
    server_version = "DojoCloud/1.0"

    def log_message(self, fmt, *args):
        # A request line that cannot be parsed is answered with an error before command/path exist.
        path = getattr(self, "path", "").split("?")[0]
        log(f"{self.client_address[0]} {getattr(self, 'command', None)} {path} -> {args[1] if len(args) > 1 else ''}")

    def send_error(self, code, message=None, explain=None):
        """Requests that cannot be parsed (bad request line, oversized header) get the same JSON error as the rest."""
        self.close_connection = True
        self.request_version = "HTTP/1.1"  # a line that did not parse counts as HTTP/0.9, which gets no status line
        self._send(code, arm_error(code, "BadRequest", message or "The request could not be understood.")[1])

    # ---- plumbing --------------------------------------------------------
    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:  # not a number: treated as no body
            n = 0
            self.close_connection = True
        if n > 1_000_000:  # the rest stays unread: on a kept-alive connection it would be parsed as the next request
            self.close_connection = True
        return self.rfile.read(min(n, 1_000_000)) if n > 0 else b""

    def _send(self, status, body=None, headers=None):
        raw = b"" if body is None else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(raw)

    def _send_pair(self, pair):
        self._send(*pair)

    def portal(self, path, body):
        query = parse_qs(urlparse(self.path).query)
        status, headers, raw = APP.portal.dispatch(self.command, path, query, self.headers, body)
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(raw)

    def handle_any(self):
        try:
            self.route()
        except CLIENT_GONE:  # the client dropped mid-response: nobody to answer, nothing worth a traceback
            self.close_connection = True
        except docker_api.DockerError as exc:  # cloud-host went away mid-request: retryable, not a bug
            log(f"cloud-host error: {exc}")
            try:
                self._send(*self.host_stopped_reply(
                    "What was recorded for your resources was left as it was; the container behind it may have changed."))
            except CLIENT_GONE:
                self.close_connection = True
        except Exception as exc:  # never leak a traceback to a student
            log(f"internal error: {exc!r}")
            try:
                self._send(*arm_error(500, "InternalServerError", "The control plane hit an unexpected error."))
            except CLIENT_GONE:
                self.close_connection = True

    def host_stopped_reply(self, left):
        """The reply when cloud-host stops answering mid-request. An ARM write gets NOT_READY_STATUS and says what
        state it left things in (`left`); anything else (the ARM logs read, the portal API) keeps a plain 503."""
        if self.command in ("PUT", "PATCH", "DELETE") and urlparse(self.path).path.lower().startswith("/subscriptions"):
            return arm_error(NOT_READY_STATUS, "ServiceUnavailable", host_stopped_message(left))
        return arm_error(503, "ServiceUnavailable", HOST_DOWN)

    def route(self):
        path = urlparse(self.path).path
        low = path.lower().rstrip("/") or "/"
        body = self._body()
        if low == "/healthz":
            return self._send(200, {"status": "ok", "cloudHost": APP.executor.ping()})
        if low == "/readyz":  # from the cache; 200 only when Dojo Cloud can take work
            ready, state, detail = APP.readiness.snapshot()
            return self._send(200 if ready else 503, {"ready": ready, "state": state, "detail": detail},
                              {"Cache-Control": "no-store"})
        if low == "/metadata/endpoints":
            return self._send(200, self.metadata())
        if low.endswith("/oauth2/v2.0/token") or low.endswith("/oauth2/token"):
            return self._send_pair(self.token(body))
        if low.endswith("/.well-known/openid-configuration"):
            return self._send(200, {"token_endpoint": f"{LOGIN}/{auth.TENANT_ID}/oauth2/v2.0/token",
                                    "issuer": f"{LOGIN}/{auth.TENANT_ID}/v2.0"})
        if low.startswith("/_dojo/reset/"):
            return self.student_reset(path)
        if low.startswith("/subscriptions"):
            return self._send_pair(self.arm(low, path, body))
        if low.startswith("/cloud/site/") or low == "/cloud/site":
            return self.site(path)
        if low == "/cloud" or low.startswith("/cloud/"):  # Dojo Portal: SPA + /cloud/api/*
            return self.portal(path, body)
        return self._send(*arm_error(404, "NotFound", f"No route for '{path}'."))

    do_GET = do_PUT = do_POST = do_DELETE = do_PATCH = do_HEAD = handle_any

    def student_reset(self, path):
        """POST /_dojo/reset/<user>?phase=teardown|provision from the engine's student reset, with the
        service's own X-Dojo-Reset-Token (students can reach this port, so nothing works without it)."""
        want = ENV.get("RESET_TOKEN", "")
        given = self.headers.get("X-Dojo-Reset-Token", "")
        if self.command != "POST" or not want or not hmac.compare_digest(given.encode(), want.encode()):
            return self._send(403, {"error": "reset token required"})
        user = unquote(path[len("/_dojo/reset/"):])
        phase = (parse_qs(urlparse(self.path).query).get("phase") or [""])[0]
        if not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", user) or phase not in ("teardown", "provision"):
            return self._send(404, {"error": "not found"})
        try:
            detail = APP.portal.student_reset(user, phase)
        except (RuntimeError, docker_api.DockerError) as exc:
            return self._send(500, {"ok": False, "detail": str(exc)[:200]})
        return self._send(200, {"ok": True, "detail": detail})

    # ---- discovery + auth -------------------------------------------------
    def metadata(self):
        return {
            "name": "dojocloud",
            "resourceManager": f"{MGMT}/",
            "microsoftGraphResourceId": f"{GRAPH}/",
            "graph": f"{GRAPH}/",
            "portal": f"{ENV.get('PUBLIC_BASE_URL', '')}/cloud/",
            "authentication": {
                "loginEndpoint": f"{LOGIN}/",
                "audiences": [f"{MGMT}/"],
                # azurerm treats anything other than AAD + "common" as Azure Stack
                # and refuses it (TOFU-BASICS-PLAN.md §5.5).
                "tenant": "common",
                "identityProvider": "AAD",
            },
            "suffixes": {"acrLoginServer": "azurecr.dojo.test", "storage": "core.dojo.test",
                         "keyVaultDns": "vault.dojo.test", "mhsmDns": "managedhsm.dojo.test"},
        }

    def token(self, body):
        form = parse_qs(body.decode(errors="replace")) if body else {}
        cid = (form.get("client_id") or [""])[0]
        secret = (form.get("client_secret") or [""])[0]
        scope = (form.get("scope") or form.get("resource") or [MGMT + "/"])[0]
        if cid not in APP.auth.by_app_id:
            return 401, {"error": "unauthorized_client", "error_description":
                         f"AADSTS700016: Application with identifier '{cid}' was not found in the directory "
                         "'Dojo Cloud'. Check ARM_CLIENT_ID."}
        user = APP.auth.authenticate_client(cid, secret)
        if user is None:
            return 401, {"error": "invalid_client", "error_description":
                         "AADSTS7000215: Invalid client secret provided. Check ARM_CLIENT_SECRET."}
        return 200, {"token_type": "Bearer", "expires_in": auth.TOKEN_TTL, "ext_expires_in": auth.TOKEN_TTL,
                     "access_token": APP.auth.issue_token(user, scope.replace("/.default", ""))}

    def caller(self):
        header = self.headers.get("Authorization", "")
        if not header.lower().startswith("bearer "):
            return None
        return APP.auth.verify_token(header[7:].strip())

    # ---- ARM --------------------------------------------------------------
    def arm(self, low, path, body):
        user = self.caller()
        if user is None:
            return 401, {"error": {"code": "InvalidAuthenticationToken",
                                   "message": "The access token is missing, invalid or expired."}}
        wait = LIMIT.take(user)
        if wait:
            log(f"rate limit: {user} {self.command} {path[:120]} -> 429 (retry in {wait}s)")
            return (429, arm_error(429, "TooManyRequests", "Too many requests: slow down and retry.")[1],
                    {"Retry-After": str(wait)})
        parts = [p for p in path.split("/") if p]
        lparts = [p.lower() for p in parts]
        if len(parts) == 1:  # GET /subscriptions
            sub = auth.subscription_id(user)
            return 200, {"value": [self.subscription_body(sub, user)]}
        sub = lparts[1]
        allowed = APP.auth.is_facilitator(user) or sub == auth.subscription_id(user)
        if not allowed:
            return arm_error(403, "AuthorizationFailed",
                             f"The client '{auth.app_id(user)}' with object id '{auth.app_id(user)}' does not "
                             f"have authorization to perform action over scope '/subscriptions/{sub}' or the "
                             "scope is invalid. If access was recently granted, please refresh your credentials.")
        if sub not in APP.auth.by_subscription:
            return arm_error(404, "SubscriptionNotFound", f"The subscription '{sub}' could not be found.")
        owner = APP.auth.by_subscription[sub]
        method = self.command
        if len(parts) == 2:
            return 200, self.subscription_body(sub, owner)
        if lparts[2] == "resourcegroups":
            if len(parts) == 3:
                with APP.state.lock:  # rg_body does no I/O; the dict must not change under the iteration
                    return 200, {"value": [APP.rg_body(sub, r) for k, r in APP.state.rgs.items()
                                           if k.startswith(sub + "/")]}
            rg = parts[3]
            if len(parts) == 4:
                return self.resource_group(method, sub, owner, user, rg, body)
            if len(parts) >= 6 and lparts[4] == "providers" and lparts[5] == "microsoft.containerinstance":
                if len(parts) == 7 and lparts[6] == "containergroups":
                    return 200, {"value": self.cg_list(sub, f"{sub}/{rg.lower()}/")}
                if len(parts) == 8 and lparts[6] == "containergroups":
                    return self.container_group(method, sub, owner, user, rg, parts[7], body)
                if len(parts) == 9 and lparts[6] == "containergroups" and lparts[8] == "logs":
                    return self.cg_logs(sub, rg, parts[7])
        if lparts[2] == "providers" and len(parts) == 5 and lparts[3] == "microsoft.containerinstance" \
                and lparts[4] == "containergroups":
            return 200, {"value": self.cg_list(sub, sub + "/")}
        return arm_error(404, "InvalidResourceType", f"No handler for '{path}'.")

    def subscription_body(self, sub, owner):
        return {"id": f"/subscriptions/{sub}", "subscriptionId": sub, "tenantId": auth.TENANT_ID,
                "displayName": f"Dojo Subscription - {owner}", "state": "Enabled"}

    def cg_views(self, sub, recs):
        """ARM JSON of stored container groups. A read never fails because cloud-host is down: if Docker cannot say
        whether a container runs, the stored record is answered with ASSUME_RUNNING, and the rest of the list does
        not ask again (a hung host would cost a timeout per item). Never called with State.lock held.

        Why Running: the record was created as Running, and a deployment nobody touched read as Running the last time
        the provider looked (and will again once the host is back and dockerd has restarted the container, see
        docker_api.build_create_request). The same JSON then comes back, so the provider plans "No changes" instead
        of retrying an error; "Terminated" would be a state it never saw for a healthy deployment. The portal says
        "Unknown" instead: it is for people, and this is for a program that cannot be told "unknown"."""
        views, asked = [], True
        for rec in recs:
            running = ASSUME_RUNNING
            if asked:
                try:
                    running = APP.executor.state(rec["container"]) == "Running"
                except docker_api.DockerError as exc:
                    log(f"cloud-host error (read answered from the stored record): {exc}")
                    asked = False
            views.append(APP.cg_body(sub, rec, running))
        return views

    def cg_view(self, sub, rec):
        return self.cg_views(sub, [rec])[0]

    def cg_list(self, sub, prefix):
        with APP.state.lock:  # a snapshot: Docker is asked only after the lock is released
            recs = [copy.deepcopy(r) for k, r in APP.state.cgs.items() if k.startswith(prefix)]
        return self.cg_views(sub, recs)

    @staticmethod
    def not_ready():
        """ARM NOT_READY_STATUS while Dojo Cloud cannot take work (checked BEFORE anything is changed), else None."""
        detail = APP.readiness.refusal()
        return None if detail is None else arm_error(NOT_READY_STATUS, "ServiceUnavailable",
                                                     f"{detail} Nothing was changed. {RETRY_HINT}")

    def body_json(self, body):
        try:
            data = json.loads(body or b"{}")
            return data if isinstance(data, dict) else None
        except (ValueError, RecursionError):  # RecursionError: absurdly deeply nested JSON
            return None

    def resource_group(self, method, sub, owner, user, rg, body):
        # Every write is refused while Dojo Cloud is not ready, resource groups too: `apply` sends the resource
        # group first, so refusing it here fails the whole run before anything is changed (an update that reached
        # the group but not its container group would leave the two half-applied).
        if method in ("PUT", "PATCH", "DELETE") and (refused := self.not_ready()):
            return refused
        st, key = APP.state, App.rg_key(sub, rg)
        rid = f"/subscriptions/{sub}/resourceGroups/{rg}"
        if method == "DELETE":  # talks to Docker, so it does not run under the lock below
            return self.delete_resource_group(sub, user, rg, key, rid)
        with st.lock:
            if method in ("GET", "HEAD"):
                rec = st.rgs.get(key)
                if rec is None:
                    return arm_error(404, "ResourceGroupNotFound", f"Resource group '{rg}' could not be found.")
                return 200, APP.rg_body(sub, rec)
            if method == "PUT":
                data = self.body_json(body)
                if data is None:
                    return arm_error(400, "InvalidRequestContent", "The request body is not valid JSON.")
                try:
                    policy.check_resource_group(rg, data.get("location"), data.get("tags"))
                except policy.PolicyError as exc:
                    st.log(sub, user, "Create/Update resource group", rid, "Failed", f"{exc.code}: {exc.message}")
                    APP.report_refusal(user, exc)
                    return exc.status, exc.body()
                existed = key in st.rgs
                st.rgs[key] = {"name": rg, "location": data["location"], "tags": data.get("tags") or {}}
                st.log(sub, user, "Create/Update resource group", rid, "Succeeded")
                st.save()
                return (200 if existed else 201), APP.rg_body(sub, st.rgs[key])
            if method == "PATCH":  # tags-only update (what the provider sends for `~` on tags)
                rec = st.rgs.get(key)
                if rec is None:
                    return arm_error(404, "ResourceGroupNotFound", f"Resource group '{rg}' could not be found.")
                data = self.body_json(body)
                if data is None:
                    return arm_error(400, "InvalidRequestContent", "The request body is not valid JSON.")
                tags = data.get("tags", rec.get("tags") or {})
                try:
                    policy.check_resource_group(rg, rec["location"], tags)
                except policy.PolicyError as exc:
                    st.log(sub, user, "Update resource group tags", rid, "Failed", f"{exc.code}: {exc.message}")
                    APP.report_refusal(user, exc)
                    return exc.status, exc.body()
                rec["tags"] = tags
                st.log(sub, user, "Update resource group tags", rid, "Succeeded")
                st.save()
                return 200, APP.rg_body(sub, rec)
        return arm_error(405, "MethodNotAllowed", method)

    def delete_resource_group(self, sub, user, rg, key, rid):
        """Reserve the group and everything in it, remove the containers with the lock released, then record (5.8)."""
        st = APP.state
        with st.lock:
            if key not in st.rgs:
                return 204, None
            children = st.claim_rg(key)
            if children is None:
                return busy_reply()
            containers = {ck: st.cgs[ck]["container"] for ck in children}
        try:
            removed, failure = [], None
            for ck, container in containers.items():  # container first, then its record: the two stay in step
                try:
                    APP.executor.remove(container)
                except docker_api.DockerError as exc:
                    log(f"executor error: {exc}")
                    failure = exc
                    break
                removed.append(ck)
            with st.lock:
                for ck in removed:
                    st.cgs.pop(ck, None)
                if failure is not None:
                    st.log(sub, user, "Delete resource group", rid, "Failed", "executor")
                    st.save()
                    return arm_error(NOT_READY_STATUS, "ServiceUnavailable", host_stopped_message(
                        "Container groups already deleted are gone; the rest and the resource group were left in place."))
                st.rgs.pop(key, None)
                st.log(sub, user, "Delete resource group", rid, "Succeeded")
                st.save()
                return 200, {}
        finally:
            st.release(*children, rg=key)

    def container_group(self, method, sub, owner, user, rg, cg, body):
        if method in ("PUT", "PATCH", "DELETE") and (refused := self.not_ready()):
            return refused  # reads below keep working
        if method == "DELETE":  # shared with the portal; talks to Docker outside the lock
            try:
                return (200, {}) if APP.delete_container_group(sub, rg, cg, user) else (204, None)
            except state_mod.Busy:
                return busy_reply()
        if method == "PATCH":  # tags-only update
            return self.patch_container_group(sub, user, rg, cg, body)
        st, key = APP.state, App.cg_key(sub, rg, cg)
        rid = f"/subscriptions/{sub}/resourceGroups/{rg}/providers/{ARM_TYPE_CG}/{cg}"
        if method == "GET":
            return self.get_container_group(sub, user, rg, cg, rid, key)
        if method == "PUT":  # takes the lock only to decide and to record, never across Docker
            return self.put_container_group(sub, owner, user, rg, cg, rid, key, body)
        return arm_error(405, "MethodNotAllowed", method)

    def get_container_group(self, sub, user, rg, cg, rid, key):
        """One Docker call, made with State.lock released. If cloud-host cannot be asked the stored record is
        answered (see cg_views): a host outage is not drift, and must not make the provider retry."""
        st = APP.state
        with st.lock:
            rec = copy.deepcopy(st.cgs.get(key))
        if rec is None:
            return self.cg_not_found(rg, cg)
        try:
            state = APP.executor.state(rec["container"])
        except docker_api.DockerError as exc:
            log(f"cloud-host error (read answered from the stored record): {exc}")
            return 200, APP.cg_body(sub, rec, ASSUME_RUNNING)
        if state is None:
            # Container vanished (deleted out-of-band): that IS drift. Forget it only if the record is still the
            # one we asked about and nothing is in flight on it: a replace or delete removes the old container
            # while its record still exists, and that is not drift.
            with st.lock:
                in_flight = key in st.pending
                if not in_flight and st.cgs.get(key) == rec:
                    del st.cgs[key]
                    st.log(sub, user, "Container disappeared outside IaC", rid, "Succeeded")
                    st.save()
                    return self.cg_not_found(rg, cg)
                current = copy.deepcopy(st.cgs.get(key))
            if current is None:
                return self.cg_not_found(rg, cg)
            if in_flight:  # Docker's answer is about the old container: say what is recorded, as when it cannot be asked
                return 200, APP.cg_body(sub, current, ASSUME_RUNNING)
            return 200, self.cg_view(sub, current)
        return 200, APP.cg_body(sub, rec, state == "Running")

    def cg_not_found(self, rg, cg):
        return arm_error(404, "ResourceNotFound", f"The Resource '{ARM_TYPE_CG}/{cg}' under "
                         f"resource group '{rg}' was not found.")

    def patch_container_group(self, sub, user, rg, cg, body):
        if APP.state.cgs.get(App.cg_key(sub, rg, cg)) is None:
            return self.cg_not_found(rg, cg)
        data = self.body_json(body)
        if data is None:
            return arm_error(400, "InvalidRequestContent", "The request body is not valid JSON.")
        try:
            rec = APP.update_container_group_tags(sub, rg, cg, user, data.get("tags", KEEP_TAGS))
        except policy.PolicyError as exc:
            return exc.status, exc.body()
        except LookupError:  # deleted between the check above and the update
            return self.cg_not_found(rg, cg)
        return 200, self.cg_view(sub, rec)

    def put_container_group(self, sub, owner, user, rg, cg, rid, key, body):
        """Reserve, then Docker, then commit (TOFU-BASICS-PLAN.md 5.8): State.lock covers the decision and the record, never a
        Docker call. Meanwhile the reservation (State.pending) keeps the key, port, DNS label and quota slot ours."""
        st = APP.state
        with st.lock:  # phase 1: decide and reserve
            if App.rg_key(sub, rg) not in st.rgs:
                return arm_error(404, "ResourceGroupNotFound", f"Resource group '{rg}' could not be found.")
            if st.busy(key):
                return busy_reply()
            data = self.body_json(body)
            if data is None:
                return arm_error(400, "InvalidRequestContent", "The request body is not valid JSON.")
            props, tags, location = data.get("properties") or {}, data.get("tags") or {}, data.get("location")
            existing = st.cgs.get(key)
            try:
                policy.check_container_group(cg, location, tags, props, st.other_groups(sub, key),
                                             lambda label: st.dns_taken(label, key))
            except policy.PolicyError as exc:
                st.log(sub, user, "Create/Update container group", rid, "Failed", f"{exc.code}: {exc.message}")
                APP.report_refusal(user, exc)
                return exc.status, exc.body()

            c = props["containers"][0]["properties"]
            env_pairs = [(v["name"], str(v.get("value", v.get("secureValue", "")) or ""))
                         for v in c.get("environmentVariables") or []]
            req = c["resources"]["requests"]
            spec = {"image": c["image"], "env": env_pairs, "cpu": float(req["cpu"]), "mem": float(req["memoryInGB"])}
            label = props["ipAddress"]["dnsNameLabel"]
            name = APP.container_name(sub, rg, cg)
            port = existing["port"] if existing else st.free_port()
            if port is None:
                return arm_error(503, "ServiceUnavailable", "No capacity is available right now.")
            if any(k != key and r["container"] == name for k, r in st.cgs.items()):
                return arm_error(409, "Conflict", "These resource group and container group names are too close to "
                                 "another of your container groups (the two would share one container name). "
                                 "Choose a different name.")
            changed = existing is None or existing["spec"] != spec or existing["dnsLabel"] != label
            st.reserve(key, sub, port, label)

        try:  # the reservation is released on every way out of here, an unexpected exception included
            if changed:  # phase 2: Docker, no lock
                if existing is not None:
                    try:
                        APP.executor.remove(existing["container"])
                    except docker_api.DockerError as exc:  # nothing has changed yet
                        log(f"executor error: {exc}")
                        with st.lock:
                            st.log(sub, user, "Create/Update container group", rid, "Failed", "executor")
                        return arm_error(NOT_READY_STATUS, "ServiceUnavailable", host_stopped_message(
                            "The container group's record was left as it was, and its old container may still be running."))
                try:
                    APP.executor.create(name, spec["image"], env_pairs, port, spec["cpu"], spec["mem"],
                                        {"dojo.owner": owner, "dojo.rg": rg, "dojo.name": cg})
                except docker_api.DockerError as exc:
                    log(f"executor error: {exc}")
                    with st.lock:
                        if existing is not None:  # the old container is already gone: forget it too
                            st.cgs.pop(key, None)
                        st.log(sub, user, "Create/Update container group", rid, "Failed", "executor")
                        st.save()
                    return arm_error(500, "InternalServerError", "The container could not be started.")
            created = existing is None
            with st.lock:  # phase 3: commit
                st.cgs[key] = {"name": cg, "rg": rg, "location": location, "tags": tags, "body": data, "spec": spec,
                               "port": port, "container": name, "dnsLabel": label, "owner": owner}
                st.log(sub, user, "Create/Update container group", rid, "Succeeded",
                       "" if created else ("replaced" if changed else "tags/metadata only"))
                st.save()
                stored = copy.deepcopy(st.cgs[key])
        finally:
            st.release(key)
        if not APP.auth.is_facilitator(user):
            APP.events.written_group(user, key, created, changed)
        return (201 if created else 200), self.cg_view(sub, stored)  # Docker is asked with the lock released

    def cg_logs(self, sub, rg, cg):
        rec = APP.state.cgs.get(App.cg_key(sub, rg, cg))
        if rec is None:
            return arm_error(404, "ResourceNotFound", "Container group not found.")
        return 200, {"content": APP.executor.logs(rec["container"]) or ""}

    # ---- student site ingress ----------------------------------------------
    def site(self, path):
        m = SITE_RE.match(path)
        if not m:
            return self._send(*arm_error(404, "NotFound", "No such site."))
        label, rest = m.group(1), m.group(2)
        if rest is None:
            self.send_response(301)
            self.send_header("Location", f"/cloud/site/{label}/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        with APP.state.lock:
            key = APP.state.dns_owner(label)
            port = None if key is None else APP.state.cgs[key]["port"]
            site_owner = None if key is None else APP.state.cgs[key].get("owner")
        if port is None:
            return self._send_text(404, "No site is deployed under that name (yet).")
        try:
            conn = http.client.HTTPConnection(CLOUD_HOST, port, timeout=5)
            conn.request("GET" if self.command != "HEAD" else "HEAD", rest or "/")
            resp = conn.getresponse()
            payload = resp.read(2_000_000)
            conn.close()
        except (UnicodeError, http.client.InvalidURL):  # a path that cannot be sent as a request line
            return self._send_text(400, "That path is not valid.")
        except OSError:
            return self._send_text(502, "The container is not answering.")
        if resp.status < 400 and site_owner and not APP.auth.is_facilitator(site_owner):
            # The ingress doesn't know who is looking: the site's owner is credited (a classmate's visit counts too).
            APP.events.emit("site_request", site_owner, every=30)
        self.send_response(resp.status)
        self.send_header("Content-Type", resp.getheader("Content-Type", "text/html"))
        self.send_header("Content-Length", str(len(payload)))
        # Student-controlled content: no scripts, unique origin.
        self.send_header("Content-Security-Policy", "sandbox; default-src 'none'; style-src 'unsafe-inline'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def _send_text(self, status, text):
        raw = text.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def serve(port, tls=None):
    """Starts one HTTP(S) server on a background thread and returns it (for shutdown())."""
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.daemon_threads = True
    if tls:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(*tls)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log(f"listening on :{port} ({'https' if tls else 'http'})")
    return server


def stop_on_signals():
    """Returns an Event that SIGTERM (docker stop; python is PID 1, so without a handler the
    signal is ignored and the container is SIGKILLed after 10 s) or SIGINT sets."""
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda _signum, _frame: stop.set())
    return stop


def shutdown(servers, state):
    """Stops accepting connections, then flushes state (it is saved after every change anyway;
    this covers a change in flight). Gives up on the lock after 5 s rather than hang the stop."""
    for srv in servers:
        srv.shutdown()
        srv.server_close()
    if state.lock.acquire(timeout=5):
        try:
            state.save()
        finally:
            state.lock.release()
    log("stopped")


def main():
    global APP
    stop = stop_on_signals()
    crt, key = pki.ensure(f"{DATA_DIR}/pki", SHARED_PKI)
    APP = App()
    servers = [serve(int(ENV.get("CLOUD_HTTPS_PORT", "443")), (crt, key)),
               serve(int(ENV.get("CLOUD_HTTP_PORT", "8080")))]
    # cloud-host may still be starting (or down for a while): listen anyway. ARM writes are refused (NOT_READY_STATUS)
    # until these say Dojo Cloud is ready. Daemon threads that stop on the same signal as the servers.
    for target, interval in ((APP.start_up, RECONCILE_RETRY), (APP.readiness.run, READY_INTERVAL)):
        threading.Thread(target=target, args=(stop, interval), daemon=True).start()
    stop.wait()
    shutdown(servers, APP.state)


if __name__ == "__main__":
    sys.exit(main())
