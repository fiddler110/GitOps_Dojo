#!/usr/bin/env python3
"""Dojo Cloud control plane ("cloud-api").

Speaks just enough Azure Resource Manager for the real `azurerm` provider
(PLAN.md §5.5): a metadata document, an OAuth client-credentials token
endpoint, and resource groups + container groups. Requests are authenticated
(token -> student), authorised (path subscription must be the caller's), checked
against policy, and executed on cloud-host by a fixed template. Also serves
student sites at /cloud/site/<label>/ (reverse proxy to cloud-host).

Stdlib only, single file per concern, same spirit as engine/allocator.
"""
import copy
import http.client
import json
import os
import re
import secrets
import ssl
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import auth
import docker_api
import pki
import policy
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


def log(msg):
    print(msg, flush=True)


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
    def __init__(self):
        self.auth = auth.Auth(load_signing_key(), auth.roster(ENV), ENV.get("FACILITATOR_USERNAME", "root"),
                              f"{LOGIN}/{auth.TENANT_ID}/v2.0")
        self.state = state_mod.State(f"{DATA_DIR}/state.json")
        self.executor = docker_api.Executor(DOCKER_SOCKET)

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
        """Forget container groups whose container vanished; remove orphans."""
        st = self.state
        try:
            live = set(self.executor.list_managed())
        except docker_api.DockerError as exc:
            log(f"reconcile skipped: {exc}")
            return
        with st.lock:
            known = {rec["container"] for rec in st.cgs.values()}
            for key in [k for k, rec in st.cgs.items() if rec["container"] not in live]:
                del st.cgs[key]
            for orphan in live - known:
                self.executor.remove(orphan)
            st.save()
        log(f"reconciled: {len(st.cgs)} container group(s), {len(st.rgs)} resource group(s)")

    # ---- ARM representations --------------------------------------------
    def rg_body(self, sub, rec):
        return {"id": f"/subscriptions/{sub}/resourceGroups/{rec['name']}", "name": rec["name"],
                "type": ARM_TYPE_RG, "location": rec["location"], "tags": rec.get("tags") or {},
                "properties": {"provisioningState": "Succeeded"}}

    def cg_body(self, sub, rec, running):
        body = copy.deepcopy(rec["body"])
        body.update({"id": f"/subscriptions/{sub}/resourceGroups/{rec['rg']}/providers/{ARM_TYPE_CG}/{rec['name']}",
                     "name": rec["name"], "type": ARM_TYPE_CG, "location": rec["location"],
                     "tags": rec.get("tags") or {}})
        props = body.setdefault("properties", {})
        props["provisioningState"] = "Succeeded"
        ip = props.setdefault("ipAddress", {})
        ip["ip"] = f"10.20.{rec['port'] // 256}.{rec['port'] % 256}"
        ip["fqdn"] = f"{rec['dnsLabel']}.{rec['location']}.dojo-cloud.test"
        state = "Running" if running else "Terminated"
        props["instanceView"] = {"state": state}
        for c in props.get("containers", []):
            cp = c.setdefault("properties", {})
            cp["instanceView"] = {"currentState": {"state": state}}
            for var in cp.get("environmentVariables") or []:
                var.pop("secureValue", None)
        return body


APP = None


def arm_error(status, code, message, target=None):
    err = {"code": code, "message": message}
    if target:
        err["target"] = target
    return status, {"error": err}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "DojoCloud/1.0"

    def log_message(self, fmt, *args):
        log(f"{self.client_address[0]} {self.command} {self.path.split('?')[0]} -> {args[1] if len(args) > 1 else ''}")

    # ---- plumbing --------------------------------------------------------
    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(min(n, 1_000_000)) if n else b""

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

    def handle_any(self):
        try:
            path = urlparse(self.path).path
            low = path.lower().rstrip("/") or "/"
            body = self._body()
            if low == "/healthz":
                return self._send(200, {"status": "ok", "cloudHost": APP.executor.ping()})
            if low == "/metadata/endpoints":
                return self._send(200, self.metadata())
            if low.endswith("/oauth2/v2.0/token") or low.endswith("/oauth2/token"):
                return self._send_pair(self.token(body))
            if low.endswith("/.well-known/openid-configuration"):
                return self._send(200, {"token_endpoint": f"{LOGIN}/{auth.TENANT_ID}/oauth2/v2.0/token",
                                        "issuer": f"{LOGIN}/{auth.TENANT_ID}/v2.0"})
            if low.startswith("/subscriptions"):
                return self._send_pair(self.arm(low, path, body))
            if low.startswith("/cloud/site/") or low == "/cloud/site":
                return self.site(path)
            return self._send(*arm_error(404, "NotFound", f"No route for '{path}'."))
        except Exception as exc:  # never leak a traceback to a student
            log(f"internal error: {exc!r}")
            self._send(*arm_error(500, "InternalServerError", "The control plane hit an unexpected error."))

    do_GET = do_PUT = do_POST = do_DELETE = do_PATCH = do_HEAD = handle_any

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
                # and refuses it (PLAN.md §5.5).
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
                return 200, {"value": [APP.rg_body(sub, r) for k, r in APP.state.rgs.items()
                                       if k.startswith(sub + "/")]}
            rg = parts[3]
            if len(parts) == 4:
                return self.resource_group(method, sub, owner, user, rg, body)
            if len(parts) >= 6 and lparts[4] == "providers" and lparts[5] == "microsoft.containerinstance":
                if len(parts) == 7 and lparts[6] == "containergroups":
                    return 200, {"value": [self.cg_view(sub, r) for k, r in APP.state.cgs.items()
                                           if k.startswith(f"{sub}/{rg.lower()}/")]}
                if len(parts) == 8 and lparts[6] == "containergroups":
                    return self.container_group(method, sub, owner, user, rg, parts[7], body)
                if len(parts) == 9 and lparts[6] == "containergroups" and lparts[8] == "logs":
                    return self.cg_logs(sub, rg, parts[7])
        if lparts[2] == "providers" and len(parts) == 5 and lparts[3] == "microsoft.containerinstance" \
                and lparts[4] == "containergroups":
            return 200, {"value": [self.cg_view(sub, r) for k, r in APP.state.cgs.items()
                                   if k.startswith(sub + "/")]}
        return arm_error(404, "InvalidResourceType", f"No handler for '{path}'.")

    def subscription_body(self, sub, owner):
        return {"id": f"/subscriptions/{sub}", "subscriptionId": sub, "tenantId": auth.TENANT_ID,
                "displayName": f"Dojo Subscription - {owner}", "state": "Enabled"}

    def cg_view(self, sub, rec):
        return APP.cg_body(sub, rec, APP.executor.state(rec["container"]) == "Running")

    def body_json(self, body):
        try:
            data = json.loads(body or b"{}")
            return data if isinstance(data, dict) else None
        except ValueError:
            return None

    def resource_group(self, method, sub, owner, user, rg, body):
        st, key = APP.state, App.rg_key(sub, rg)
        rid = f"/subscriptions/{sub}/resourceGroups/{rg}"
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
                    st.log(sub, user, "Create/Update resource group", rid, "Failed", exc.code)
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
                    st.log(sub, user, "Update resource group tags", rid, "Failed", exc.code)
                    return exc.status, exc.body()
                rec["tags"] = tags
                st.log(sub, user, "Update resource group tags", rid, "Succeeded")
                st.save()
                return 200, APP.rg_body(sub, rec)
            if method == "DELETE":
                if key not in st.rgs:
                    return 204, None
                for ck in [k for k in st.cgs if k.startswith(key + "/")]:
                    APP.executor.remove(st.cgs.pop(ck)["container"])
                del st.rgs[key]
                st.log(sub, user, "Delete resource group", rid, "Succeeded")
                st.save()
                return 200, {}
        return arm_error(405, "MethodNotAllowed", method)

    def container_group(self, method, sub, owner, user, rg, cg, body):
        st, key = APP.state, App.cg_key(sub, rg, cg)
        rid = f"/subscriptions/{sub}/resourceGroups/{rg}/providers/{ARM_TYPE_CG}/{cg}"
        with st.lock:
            if method == "GET":
                rec = st.cgs.get(key)
                if rec is not None and APP.executor.state(rec["container"]) is None:
                    # Container vanished (deleted out-of-band): that IS drift.
                    del st.cgs[key]
                    st.log(sub, user, "Container disappeared outside IaC", rid, "Succeeded")
                    st.save()
                    rec = None
                if rec is None:
                    return arm_error(404, "ResourceNotFound", f"The Resource '{ARM_TYPE_CG}/{cg}' under "
                                     f"resource group '{rg}' was not found.")
                return 200, self.cg_view(sub, rec)
            if method == "DELETE":
                rec = st.cgs.pop(key, None)
                if rec is None:
                    return 204, None
                APP.executor.remove(rec["container"])
                st.log(sub, user, "Delete container group", rid, "Succeeded")
                st.save()
                return 200, {}
            if method == "PATCH":  # tags-only update
                rec = st.cgs.get(key)
                if rec is None:
                    return arm_error(404, "ResourceNotFound", f"The Resource '{ARM_TYPE_CG}/{cg}' under "
                                     f"resource group '{rg}' was not found.")
                data = self.body_json(body)
                if data is None:
                    return arm_error(400, "InvalidRequestContent", "The request body is not valid JSON.")
                tags = data.get("tags", rec.get("tags") or {})
                try:
                    policy.check_tags(cg, tags)
                except policy.PolicyError as exc:
                    st.log(sub, user, "Update container group tags", rid, "Failed", exc.code)
                    return exc.status, exc.body()
                rec["tags"] = tags
                rec["body"]["tags"] = tags
                st.log(sub, user, "Update container group tags", rid, "Succeeded")
                st.save()
                return 200, self.cg_view(sub, rec)
            if method == "PUT":
                return self.put_container_group(sub, owner, user, rg, cg, rid, key, body)
        return arm_error(405, "MethodNotAllowed", method)

    def put_container_group(self, sub, owner, user, rg, cg, rid, key, body):
        st = APP.state
        if App.rg_key(sub, rg) not in st.rgs:
            return arm_error(404, "ResourceGroupNotFound", f"Resource group '{rg}' could not be found.")
        data = self.body_json(body)
        if data is None:
            return arm_error(400, "InvalidRequestContent", "The request body is not valid JSON.")
        props, tags, location = data.get("properties") or {}, data.get("tags") or {}, data.get("location")
        existing = st.cgs.get(key)
        others = sum(1 for k in st.cgs if k.startswith(sub + "/") and k != key)

        def dns_taken(label):
            holder = st.dns_owner(label)
            return holder is not None and holder != key

        try:
            policy.check_container_group(cg, location, tags, props, others, dns_taken)
        except policy.PolicyError as exc:
            st.log(sub, user, "Create/Update container group", rid, "Failed", exc.code)
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

        changed = existing is None or existing["spec"] != spec or existing["dnsLabel"] != label
        if changed:
            if existing is not None:
                APP.executor.remove(existing["container"])
            try:
                APP.executor.create(name, spec["image"], env_pairs, port, spec["cpu"], spec["mem"],
                                    {"dojo.owner": owner, "dojo.rg": rg, "dojo.name": cg})
            except docker_api.DockerError as exc:
                log(f"executor error: {exc}")
                st.log(sub, user, "Create/Update container group", rid, "Failed", "executor")
                return arm_error(500, "InternalServerError", "The container could not be started.")
        created = existing is None
        st.cgs[key] = {"name": cg, "rg": rg, "location": location, "tags": tags, "body": data, "spec": spec,
                       "port": port, "container": name, "dnsLabel": label, "owner": owner}
        st.log(sub, user, "Create/Update container group", rid, "Succeeded",
               "" if created else ("replaced" if changed else "tags/metadata only"))
        st.save()
        return (201 if created else 200), self.cg_view(sub, st.cgs[key])

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
        key = APP.state.dns_owner(label)
        if key is None:
            return self._send_text(404, "No site is deployed under that name (yet).")
        port = APP.state.cgs[key]["port"]
        try:
            conn = http.client.HTTPConnection(CLOUD_HOST, port, timeout=5)
            conn.request("GET" if self.command != "HEAD" else "HEAD", rest or "/")
            resp = conn.getresponse()
            payload = resp.read(2_000_000)
            conn.close()
        except OSError:
            return self._send_text(502, "The container is not answering.")
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
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.daemon_threads = True
    if tls:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(*tls)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log(f"listening on :{port} ({'https' if tls else 'http'})")


def main():
    global APP
    crt, key = pki.ensure(f"{DATA_DIR}/pki", SHARED_PKI)
    APP = App()
    for _ in range(60):  # cloud-host may still be starting
        if APP.executor.ping():
            break
        threading.Event().wait(1)
    APP.reconcile()
    serve(int(ENV.get("CLOUD_HTTPS_PORT", "443")), (crt, key))
    serve(int(ENV.get("CLOUD_HTTP_PORT", "8080")))
    threading.Event().wait()


if __name__ == "__main__":
    sys.exit(main())
