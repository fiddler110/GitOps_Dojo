#!/usr/bin/env python3
"""Dojo Cloud ARM facade — SPIKE VERSION (P2, PLAN.md T2.2).

A tiny, stdlib-only HTTPS server that speaks just enough of Azure Resource
Manager's REST shape (metadata document, OAuth token, resource groups,
container groups) for the real `azurerm` provider to run
init / plan / apply / destroy against it. Every request is logged so the
spike can record exactly which endpoints the provider needs.

Not a security boundary yet: no student identity, no policy, no cloud-host.
Those arrive in P3. State lives in memory.
"""
import base64
import json
import os
import ssl
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HOST = os.environ.get("CLOUD_HOSTNAME", "dojo-cloud")
PORT = int(os.environ.get("CLOUD_PORT", "443"))
TENANT = os.environ.get("CLOUD_TENANT_ID", "11111111-1111-1111-1111-111111111111")
ENV_NAME = os.environ.get("CLOUD_ENV_NAME", "dojocloud")
BASE = f"https://{HOST}" + ("" if PORT == 443 else f":{PORT}")

LOCK = threading.Lock()
STORE = {}  # lower-cased resource path -> resource dict


def b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def fake_jwt(client_id, audience):
    now = int(time.time())
    claims = {
        "aud": audience, "iss": f"{BASE}/{TENANT}/", "iat": now, "nbf": now,
        "exp": now + 3600, "tid": TENANT, "oid": client_id, "appid": client_id,
        "sub": client_id, "idtyp": "app",
    }
    head = b64(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    return f"{head}.{b64(json.dumps(claims).encode())}.sig"


def metadata():
    return {
        "name": ENV_NAME,
        "authentication": {
            "loginEndpoint": f"{BASE}/",
            "audiences": [f"{BASE}/"],
            # azurerm treats any environment whose identity provider is not
            # "AAD" with tenant "common" as Azure Stack and refuses it
            # (go-azure-sdk environments.IsAzureStack) — so we must say so.
            "tenant": "common",
            "identityProvider": "AAD",
        },
        "resourceManager": f"{BASE}/",
        "microsoftGraphResourceId": f"{BASE}/graph/",
        "graph": f"{BASE}/graph/",
        "portal": f"{BASE}/portal",
        "suffixes": {
            "acrLoginServer": "azurecr.dojo.test",
            "storage": "core.dojo.test",
            "keyVaultDns": "vault.dojo.test",
            "mhsmDns": "managedhsm.dojo.test",
        },
    }


def arm_error(code, message):
    return {"error": {"code": code, "message": message}}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "DojoCloud/0.1"

    def log_message(self, fmt, *args):  # replaced by explicit logging below
        pass

    def _read(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

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
        print(f"   -> {status}", flush=True)

    def _handle(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        body = self._read()
        print(f"{self.command} {self.path}", flush=True)
        if body:
            print(f"   body: {body[:1500].decode(errors='replace')}", flush=True)

        low = path.lower()

        # --- discovery + auth ---------------------------------------------
        if low == "/metadata/endpoints":
            return self._send(200, metadata())
        if low.endswith("/.well-known/openid-configuration"):
            return self._send(200, {
                "token_endpoint": f"{BASE}/{TENANT}/oauth2/v2.0/token",
                "authorization_endpoint": f"{BASE}/{TENANT}/oauth2/v2.0/authorize",
                "issuer": f"{BASE}/{TENANT}/v2.0",
            })
        if low.endswith("/oauth2/v2.0/token") or low.endswith("/oauth2/token"):
            form = parse_qs(body.decode()) if body else {}
            cid = (form.get("client_id") or ["dojo-student"])[0]
            scope = (form.get("scope") or form.get("resource") or [f"{BASE}/"])[0]
            aud = scope.replace("/.default", "")
            return self._send(200, {
                "token_type": "Bearer", "expires_in": 3600, "ext_expires_in": 3600,
                "access_token": fake_jwt(cid, aud),
            })

        # --- ARM ----------------------------------------------------------
        with LOCK:
            return self._arm(low, path, body)

    def _arm(self, low, path, body):
        parts = [p for p in low.split("/") if p]

        if len(parts) == 2 and parts[0] == "subscriptions":
            return self._send(200, {
                "id": f"/subscriptions/{parts[1]}", "subscriptionId": parts[1],
                "tenantId": TENANT, "displayName": "Dojo Student Subscription",
                "state": "Enabled",
            })
        if low == "/subscriptions":
            return self._send(200, {"value": []})
        if low.startswith("/providers/") or (len(parts) >= 3 and parts[2] == "providers" and len(parts) == 3):
            return self._send(200, {"value": []})

        if self.command == "PUT":
            res = json.loads(body or b"{}")
            res["id"] = path
            res["name"] = path.rsplit("/", 1)[-1]
            res.setdefault("properties", {})["provisioningState"] = "Succeeded"
            if "resourcegroups" in parts and len(parts) == 4:
                res["type"] = "Microsoft.Resources/resourceGroups"
            elif "containergroups" in parts:
                res["type"] = "Microsoft.ContainerInstance/containerGroups"
                res["properties"]["ipAddress"] = dict(res["properties"].get("ipAddress") or {},
                                                      ip="10.20.0.5", fqdn=f"{res['name']}.dojo.test")
            existed = low in STORE
            STORE[low] = res
            return self._send(200 if existed else 201, res)

        if self.command == "GET":
            if low in STORE:
                return self._send(200, STORE[low])
            # list under a prefix (…/containerGroups)
            prefix = low + "/"
            kids = [v for k, v in STORE.items() if k.startswith(prefix) and "/" not in k[len(prefix):]]
            last = parts[-1] if parts else ""
            if last in ("containergroups", "resourcegroups", "resources"):
                return self._send(200, {"value": kids})
            code = "ResourceGroupNotFound" if "resourcegroups" in parts and len(parts) == 4 else "ResourceNotFound"
            return self._send(404, arm_error(code, f"The resource '{path}' was not found."))

        if self.command == "DELETE":
            existed = STORE.pop(low, None) is not None
            for k in [k for k in STORE if k.startswith(low + "/")]:
                del STORE[k]
            return self._send(200 if existed else 204, {} if existed else None)

        return self._send(405, arm_error("MethodNotAllowed", self.command))

    do_GET = do_PUT = do_POST = do_DELETE = do_PATCH = do_HEAD = _handle


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    cert, key = os.environ.get("CLOUD_TLS_CERT"), os.environ.get("CLOUD_TLS_KEY")
    if cert and key:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
    print(f"Dojo Cloud facade listening on {BASE} (tls={'on' if cert else 'off'})", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    sys.exit(main())
