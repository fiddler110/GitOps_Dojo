"""policy-bypass — CTF target 9 (plan docs/CTF-WORKSHOP-PLAN.md §7.3, CTF-4
"Trusting the wrong thing", ties `cloud-policy-as-code`). A12/A04-style
"insecure design": there is no bug to find in how the rule is evaluated —
`policy_engine.py` (vendored verbatim from `modules/dojo-cloud/cloud-api/`,
see its own header) runs the condition exactly as written, and the condition
itself passes every syntax/shape check a real `opa test` analogue would run.
The flaw is what the rule's author chose to check.

"CloudGuard" fronts one resource group, `rg-vault-gateway`, with a custom
deny policy meant to restrict writes there to the security team. The
assignment's `if` condition denies a containerGroup write UNLESS the
REQUEST's own `tags['provisioned-by']` already reads `security-team` --
i.e. it trusts a label the requester attaches to their own request as proof
of who they are, the same category of mistake as trusting an unsigned
`X-Auth-User` header (see CLAUDE.md's trust-model rule) or an attacker-
controlled JSON field (`api-mass-assignment`, target 12) -- just one layer
up, in a policy rule instead of application code. Nothing here verifies the
caller is really the security team; a requester need only assert it.

The policy and the resource it guards are both fully inspectable
(`GET /api/policy`) -- same "the rule has no syntax error, it's just the
wrong rule" lesson the plan's A04 row names. Fixing it (not required to
solve, but the inline comment says how) means checking something the
requester cannot set about themselves, e.g. a caller identity the gateway
itself attaches server-side, never a field inside the request body.

Env:
  CTF_FLAG      this slot's flag value (plan §5).
  PORT          listen port (default 5000).
"""
import os
import threading
import socket

from flask import Flask, jsonify, request
from flask import Response as _Response

import policy_engine as engine

app = Flask(__name__)


# -- Scenario theme ("CloudGuard Policy"): static CSS served at /assets/theme.css, linked
# with a relative root path so it works through the Target Viewer proxy.
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
    # `inner` is static markup written in this file (never request data).
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

# --- the vulnerable policy, as data -- this IS the target, not a toy -------
# `policy_engine.py` is the real evaluator (vendored, unmodified); only this
# definition/assignment pair is specific to this challenge.
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
            # THE BUG: the second clause checks a tag on the REQUEST ITSELF,
            # not anything about who is making it. A requester can always
            # set their own request's tags, so this never actually restricts
            # anyone. A correct version would deny unless a caller-identity
            # field the gateway attaches server-side (never present in the
            # request body a student can shape) says security-team -- the
            # same "check who's asking, not what they claim" fix api-bfla's
            # README spells out for a function-level check.
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


_PROVISIONED = []  # flavor-only audit trail, shown back on /api/resources


@app.get("/")
def index():
    return _shell(
        "CloudGuard Policy",
        "<h1>CloudGuard</h1>"
        "<p>Policy-as-code guardrails for Dojo Cloud. One resource group, "
        f"<code>{PROTECTED_RG}</code>, is restricted to the security team.</p>"
        '<ul><li><a href="/api/policy">GET /api/policy</a> — the active policy, in full</li>'
        '<li><a href="/api/resources">GET /api/resources</a> — what has been provisioned</li>'
        "<li>POST /api/provision — request a new resource</li></ul>"
    )


@app.get("/api/policy")
def get_policy():
    # Deliberately no auth on this route: a real policy-as-code tool shows
    # its rules openly (`opa test` is public too) -- the gap is in the rule,
    # never in keeping it secret.
    return jsonify({"definitions": [DEFINITION], "assignments": [ASSIGNMENT]})


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
                                   "message": "name and a known resourceGroup are required."}}), 400

    resource = engine.resource_view("containerGroup", name, LOCATION, tags, props, SUB, rg)
    assignments = [ASSIGNMENT] if rg == PROTECTED_RG else []
    outcome = engine.evaluate_write(resource, assignments, _lookup)
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


# -- Decoy listener (plan §7.3's nmap primer, same shape every other target
# in this ladder uses -- see weak-auth-portal/app.py's identical comment for
# why this can never be a real sshd under this range's CapDrop ALL.)
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
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), threaded=False)
