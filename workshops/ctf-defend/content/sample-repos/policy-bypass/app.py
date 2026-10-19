import hmac
import json
import os
import sys
import threading
import socket

from flask import Flask, jsonify, request
from flask import Response as _Response

import policy_engine as engine

app = Flask(__name__)


_CSS = """
:root{--bg:#f1f0fb;--card:#fff;--ink:#1f1b3a;--mute:#6b6890;--acc:#4f46e5;--line:#d9d6f2}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,Segoe UI,sans-serif;background:var(--bg);color:var(--ink)}
header{background:linear-gradient(90deg,#1e1b4b,#4f46e5);color:#fff;padding:.9rem 1.5rem;display:flex;align-items:center;gap:.7rem}
.logo{background:#fff;color:#4f46e5;font-weight:800;border-radius:6px;padding:.1rem .5rem}.brand{font-weight:600;letter-spacing:.02em}
main{max-width:640px;margin:2.5rem auto;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:2rem;box-shadow:0 8px 30px #0002}
h1{margin:0 0 .6rem;font-size:1.4rem}h1 small{color:var(--mute);font-weight:400;font-size:.8em}h2{font-size:1.1rem}a{color:var(--acc)}
label{display:block;font-weight:600;font-size:.85rem;margin:.8rem 0 .25rem}
input{width:100%;padding:.6rem .7rem;border:1px solid var(--line);border-radius:8px;font:inherit;background:var(--bg);color:var(--ink)}
input:focus{outline:2px solid var(--acc)}
button{margin-top:1rem;padding:.6rem 1.2rem;border:0;border-radius:8px;background:var(--acc);color:#fff;font:600 1rem system-ui;cursor:pointer}
code,pre{background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:.05rem .35rem;font-size:.9em}
pre{padding:.7rem;white-space:pre-wrap;word-break:break-all}
"""


@app.get("/assets/theme.css")
def theme_css():
    return _Response(_CSS, mimetype="text/css")


def _shell(title, inner):
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{title}</title>"
        '<link rel="stylesheet" href="/assets/theme.css"></head><body>'
        '<header><span class="logo">C</span><span class="brand">CloudGuard Policy</span></header>'
        f"<main>{inner}</main></body></html>"
    )

FLAG = os.environ.get("CTF_FLAG", "flag{policy-bypass-dev0000000000}")
SUB = "ctf-lab"
LOCATION = "canadacentral"
PROTECTED_RG = "rg-vault-gateway"
SANDBOX_RG = "rg-sandbox"

DEFINITION_ID = "/providers/Microsoft.Authorization/policyDefinitions/deny-vault-gateway-writes"
DEFINITION = {
    "id": DEFINITION_ID,
    "name": "deny-vault-gateway-writes",
    "properties": {
        "displayName": "Restrict container writes to the security team",
        "policyType": "Custom",
        "mode": "All",
        "parameters": {},
        "policyRule": {
            "if": {"allOf": [
                {"field": "type", "equals": engine.CG},
                {"not": {"field": "tags['provisioned-by']", "equals": "security-team"}},
            ]},
            "then": {"effect": "deny"},
        },
    },
}
ASSIGNMENT = {
    "id": "/providers/Microsoft.Authorization/policyAssignments/protect-vault-gateway",
    "name": "protect-vault-gateway",
    "properties": {
        "displayName": "Protect rg-vault-gateway",
        "scope": f"/subscriptions/{SUB}/resourceGroups/{PROTECTED_RG}",
        "policyDefinitionId": DEFINITION_ID,
        "parameters": {},
        "enforcementMode": "Default",
        "nonComplianceMessage": "Only the security team may provision resources in rg-vault-gateway.",
    },
}


def _lookup(definition_id):
    return DEFINITION if definition_id == DEFINITION_ID else None


def _caller_role():
    expected = os.environ.get("CTF_PROXY_TOKEN", "")
    got = request.headers.get("X-Gateway-Token", "")
    if expected and hmac.compare_digest(got, expected):
        return request.headers.get("X-Caller-Role", "unknown")
    return "unknown"


_PROVISIONED = []


@app.get("/")
def index():
    return _shell(
        "CloudGuard Policy",
        "<h1>CloudGuard</h1>"
        "<p>Policy-as-code guardrails for Dojo Cloud. One resource group, "
        f"<code>{PROTECTED_RG}</code>, is restricted to the security team.</p>"
        '<ul><li><a href="/api/policy">GET /api/policy</a> — the active policy, in full</li>'
        '<li><a href="/api/resources">GET /api/resources</a> — what has been provisioned</li>'
        '<li><a href="/spec">GET /spec</a> — API reference: routes, request/response shapes</li>'
        "<li>POST /api/provision — request a new resource</li></ul>"
    )


@app.get("/api/policy")
def get_policy():
    return jsonify({"definitions": [DEFINITION], "assignments": [ASSIGNMENT]})


@app.get("/spec")
def spec():
    return jsonify({
        "openapi": "3.0.0",
        "info": {"title": "CloudGuard Policy API", "version": "1.0"},
        "paths": {
            "/api/policy": {
                "get": {
                    "summary": "The deployed policy definitions and assignments, in full.",
                    "responses": {"200": {"description": "definitions[] and assignments[]"}},
                },
            },
            "/api/resources": {
                "get": {
                    "summary": "Resources provisioned so far in this slot.",
                    "responses": {"200": {"description": "provisioned[]"}},
                },
            },
            "/api/provision": {
                "post": {
                    "summary": "Provision a resource into a resource group.",
                    "requestBody": {
                        "required": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "required": True,
                                          "description": "resource name"},
                                "resourceGroup": {"type": "string", "required": True,
                                                   "enum": [SANDBOX_RG, PROTECTED_RG],
                                                   "description": "must be a known resource group"},
                                "tags": {"type": "object", "required": False,
                                         "description": "free-form key/value tags attached to the resource",
                                         "additionalProperties": {"type": "string"}},
                                "properties": {"type": "object", "required": False,
                                                "description": "free-form resource properties"},
                            },
                        },
                    },
                    "responses": {
                        "201": {"description": "Succeeded; includes 'flag' when the target resource "
                                                "group was the protected one and the policy allowed it.",
                                "schema": {"status": "Succeeded", "resourceGroup": "string",
                                           "name": "string", "flag": "string (only if granted)"}},
                        "400": {"description": "name and a known resourceGroup are required, and "
                                                "tags (if present) must be an object.",
                                "schema": {"error": {"code": "InvalidRequestContent", "message": "string"}}},
                        "403": {"description": "Denied by policy evaluation.",
                                "schema": {"error": {"code": "RequestDisallowedByPolicy", "message": "string"}}},
                    },
                },
            },
        },
    })


@app.get("/api/resources")
def get_resources():
    return jsonify({"provisioned": _PROVISIONED})


@app.post("/api/provision")
def provision():
    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    rg = str(body.get("resourceGroup", "")).strip()
    tags = body.get("tags") or {}
    props = body.get("properties") or {}
    if not name or rg not in (PROTECTED_RG, SANDBOX_RG) or not isinstance(tags, dict):
        return jsonify({"error": {"code": "InvalidRequestContent",
                                   "message": f"'name' (string, required), 'resourceGroup' (string, "
                                              f"required, one of {SANDBOX_RG!r}/{PROTECTED_RG!r}) and "
                                              f"'tags' (object, if present) are required."}}), 400

    resource = engine.resource_view("containerGroup", name, LOCATION, tags, props, SUB, rg)
    assignments = [ASSIGNMENT] if rg == PROTECTED_RG else []
    outcome = engine.evaluate_write(resource, assignments, _lookup)
    print(json.dumps({"audit": True, "method": "POST", "path": "/api/provision", "caller": _caller_role(),
                      "resource_group": rg, "asserted_tag": str(tags.get("provisioned-by", "")),
                      "outcome": "denied" if outcome.denied else "allowed"}), file=sys.stderr, flush=True)
    if outcome.denied:
        v = outcome.denied[0]
        return jsonify({"error": {
            "code": "RequestDisallowedByPolicy",
            "message": f"Resource '{name}' was disallowed by policy. "
                       f"Policy: '{v.assignmentDisplayName}'. {v.reason}. {v.message}",
            "target": name,
            "additionalInfo": [{"type": "PolicyViolation",
                                "info": {"policyDefinitionDisplayName": v.displayName}}],
        }}), 403

    entry = {"name": name, "resourceGroup": rg, "tags": tags}
    _PROVISIONED.append(entry)
    resp = {"status": "Succeeded", "resourceGroup": rg, "name": name}
    if rg == PROTECTED_RG:
        resp["flag"] = FLAG
    return jsonify(resp), 201


def _decoy_ssh_handler(conn):
    try:
        conn.sendall(b"SSH-2.0-OpenSSH_9.7p1 Debian-7\r\n")
        conn.recv(256)
    except OSError:
        pass
    finally:
        conn.close()


def _start_decoy(port, handler):
    def _accept_loop():
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", port))
        srv.listen(16)
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                continue
            threading.Thread(target=handler, args=(conn,), daemon=True).start()
    threading.Thread(target=_accept_loop, daemon=True).start()


_start_decoy(2222, _decoy_ssh_handler)

if __name__ == "__main__":
    if os.environ.get("CTF_DEFEND_PROXY") == "1":
        app.run(host="127.0.0.1", port=5001, threaded=False)
    else:
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), threaded=False)
