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

import policy_engine as engine

app = Flask(__name__)

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
    return (
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
