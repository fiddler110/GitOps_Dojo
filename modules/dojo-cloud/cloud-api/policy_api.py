"""Dojo Cloud's fake Azure Policy API (the azurerm provider's policy resources) and its compliance state.

Everything lives in the subscription's state: State.data["policy"][sub] = {"definitions", "sets", "assignments",
"exemptions", "remediations": {key: ARM object}, "states": [...], "evaluatedAt": ...}. It is saved with the rest of the
state and removed by Portal._purge (so a student reset clears it). Rules are judged by policy_engine; this module is
the wire shape, the fail-closed checks on every write, and the stored compliance.

Locking: every function here that touches state takes State.lock (an RLock) itself; nothing here calls Docker.
"""
import copy
import datetime
import json
import re
import uuid

import auth
import policy
import policy_engine as engine

QUOTA = 50  # objects of each kind per subscription
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._()-]{0,63}\Z")
AUTHZ, INSIGHTS = "microsoft.authorization", "microsoft.policyinsights"
BUCKETS = ("definitions", "sets", "assignments", "exemptions", "remediations")
# ARM answers a PUT of these with 201 on update too, and azurerm 5.6.0 accepts only 201 for them (a 200 fails the
# apply with "unexpected status 200"). Exemptions and remediations answer 200 on update, like the real API.
ALWAYS_201 = ("definitions", "sets", "assignments")
# URL segment (lower case) -> (bucket, ARM type, label for the activity log, error code when missing)
KINDS = {
    "policydefinitions": ("definitions", "Microsoft.Authorization/policyDefinitions", "policy definition",
                          "PolicyDefinitionNotFound"),
    "policysetdefinitions": ("sets", "Microsoft.Authorization/policySetDefinitions", "policy set definition",
                             "PolicySetDefinitionNotFound"),
    "policyassignments": ("assignments", "Microsoft.Authorization/policyAssignments", "policy assignment",
                          "PolicyAssignmentNotFound"),
    "policyexemptions": ("exemptions", "Microsoft.Authorization/policyExemptions", "policy exemption",
                         "PolicyExemptionNotFound"),
    "remediations": ("remediations", "Microsoft.PolicyInsights/remediations", "policy remediation",
                     "ResourceNotFound"),
}
_BUILTIN = {k.lower(): v for k, v in policy.BUILTIN_DEFINITIONS.items()}


def _err(status, code, message, details=None):
    err = {"code": code, "message": message}
    if details:
        err["details"] = [{"code": code, "message": d} for d in details]
    return status, {"error": err}


def _json(body):
    try:
        data = json.loads(body or b"{}")
        return data if isinstance(data, dict) else None
    except (ValueError, RecursionError):
        return None


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _stamp(t=None):
    return (t or _now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pol(st, sub):
    """The subscription's policy document, created on first write. Caller holds the lock."""
    pol = st.data.setdefault("policy", {}).setdefault(sub, {})
    for b in BUCKETS:
        pol.setdefault(b, {})
    pol.setdefault("states", [])
    return pol


def _peek(st, sub):
    return (st.data.get("policy") or {}).get(sub)


def make_lookup(pol, override=None):
    """lookup(id) -> custom definition or set of this subscription, or a built-in definition; case-insensitive."""
    table = {o["id"].lower(): o for b in ("definitions", "sets") for o in pol[b].values()}
    if override is not None:
        table[override["id"].lower()] = override

    def lookup(i):
        if not isinstance(i, str):
            return None
        return table.get(i.lower()) or _BUILTIN.get(i.lower())
    return lookup


def _builtin_view(d):
    out = copy.deepcopy(d)
    out["type"] = KINDS["policydefinitions"][1]
    return out


# ---------------------------------------------------------------- enforcement and compliance (used by server.py)

def active(st, sub):
    """True if the subscription has any student policy assignment: the only case in which the write paths do more
    than they always did."""
    with st.lock:
        pol = _peek(st, sub)
        return bool(pol and pol["assignments"])


def enforce(st, sub, resource):
    """Judges a resource write against built-ins plus the subscription's assignments and exemptions -> Outcome."""
    with st.lock:
        pol = _pol(st, sub)
        return policy.check_with_assignments(resource, list(pol["assignments"].values()), make_lookup(pol),
                                             list(pol["exemptions"].values()))


def refusal(outcome, name):
    """The 403 for the first denial, in the shape every built-in refusal has (naming assignment and definition)."""
    v = outcome.denied[0]
    detail = (f"Assignment '{v.assignmentName}', definition '{v.displayName}': {v.reason}."
              + (f" {v.message}" if v.message else ""))
    exc = policy._disallowed(name, v.assignmentDisplayName, detail)
    exc.assignment = v.assignmentName  # a student's own assignment, not a platform guardrail (events.denial)
    return exc


def _view(sub, kind, rec):
    if kind == "rg":
        return engine.resource_view("resourceGroup", rec["name"], rec.get("location"), rec.get("tags"), {}, sub, "-")
    props = (rec.get("body") or {}).get("properties") or {}
    return engine.resource_view("containerGroup", rec["name"], rec.get("location"), rec.get("tags"), props, sub,
                                rec["rg"])


def _views(st, sub):
    out = []
    for k, rec in st.rgs.items():
        if k.startswith(sub + "/"):
            out.append(("rg", rec))
    for k, rec in st.cgs.items():
        if k.startswith(sub + "/"):
            out.append(("cg", rec))
    views = []
    for kind, rec in out:
        try:
            views.append(_view(sub, kind, rec))
        except (TypeError, ValueError, KeyError):
            continue  # a record the engine cannot read is simply not evaluated
    return views


def recompute(st, sub, now=None):
    """Recompute the subscription's stored compliance. Called after every write of a policy object or a resource,
    never on a read. A subscription that never had policy objects costs nothing."""
    with st.lock:
        pol = _peek(st, sub)
        if not pol:
            return
        now = now or _now()
        rows = []
        if pol["assignments"]:
            rows = engine.compliance(_views(st, sub), list(pol["assignments"].values()), make_lookup(pol),
                                     list(pol["exemptions"].values()), now)
        ts = _stamp(now)
        pol["states"] = [{"resourceId": r["resourceId"], "policyAssignmentId": r["assignmentId"],
                          "policyDefinitionId": r["definitionId"], "policyDefinitionReferenceId": r["referenceId"],
                          "complianceState": r["state"], "reason": r["reason"], "timestamp": ts} for r in rows]
        pol["evaluatedAt"] = ts


def purge(st, sub):
    """Forget the subscription's policy objects (caller holds the lock) -> how many objects there were."""
    pol = (st.data.get("policy") or {}).pop(sub, None)
    return sum(len(pol[b]) for b in BUCKETS) if pol else 0


# ---------------------------------------------------------------- the ARM routes

def _rid(sub, rg, typ, name):
    base = f"/subscriptions/{sub}" + (f"/resourceGroups/{rg}" if rg else "")
    return f"{base}/providers/{typ}/{name}"


def route(app, method, sub, user, parts, body, mgmt):
    """Handles the policy paths below /subscriptions/{sub}; None if the path is not one of them (the caller then
    answers its usual 404). The subscription was already authorised by arm()."""
    low = [p.lower() for p in parts]
    rg, off = None, 2
    if len(parts) > 3 and low[2] == "resourcegroups":
        rg, off = parts[3], 4
    if len(parts) < off + 3 or low[off] != "providers":
        return None
    ns, typ = low[off + 1], low[off + 2]
    name = parts[off + 3] if len(parts) > off + 3 else None
    extra = low[off + 4:]
    if ns == AUTHZ and typ in KINDS and typ != "remediations" and not (rg and typ in
                                                                         ("policydefinitions", "policysetdefinitions")):
        if name is None:
            return _list(app, method, sub, rg, typ) if len(parts) == off + 3 else None
        return _object(app, method, sub, user, rg, typ, name, body) if not extra else None
    if ns == INSIGHTS and typ == "remediations" and rg:
        if name is None:
            return _list(app, method, sub, rg, typ)
        return _object(app, method, sub, user, rg, typ, name, body) if not extra else None
    if ns == INSIGHTS and typ == "policystates" and rg is None and len(parts) == off + 5 and low[off + 3] == "latest":
        if extra[0] == "queryresults" and method in ("GET", "POST"):
            return _query(app, sub)
        if extra[0] == "triggerevaluation" and method == "POST":
            return _trigger(app, sub, user, mgmt)
    if ns == INSIGHTS and typ == "asyncoperationresults" and method == "GET" and name:
        return 200, {"status": "Succeeded"}
    return None


def global_route(method, parts):
    """The built-in definitions' own path, /providers/Microsoft.Authorization/policyDefinitions/{name}: parts are
    the path segments. 200 for a built-in, 404 for anything else."""
    low = [p.lower() for p in parts]
    if len(low) < 3 or low[:2] != ["providers", AUTHZ] or low[2] not in ("policydefinitions",
                                                                         "policysetdefinitions"):
        return None
    if method != "GET":
        return _err(405, "MethodNotAllowed", method)
    if low[2] == "policysetdefinitions":
        return _err(404, "PolicySetDefinitionNotFound", "There are no built-in policy set definitions here.") \
            if len(low) == 4 else (200, {"value": []})
    if len(low) == 3:
        return 200, {"value": [_builtin_view(d) for d in policy.BUILTIN_DEFINITIONS.values()]}
    d = _BUILTIN.get(f"{policy._DEF_PREFIX}{low[3]}".lower())
    if d is None or len(low) != 4:
        return _err(404, "PolicyDefinitionNotFound", f"The policy definition '{parts[3]}' could not be found.")
    return 200, _builtin_view(d)


def _list(app, method, sub, rg, typ):
    if method != "GET":
        return _err(405, "MethodNotAllowed", method)
    st, bucket = app.state, KINDS[typ][0]
    with st.lock:
        pol = _peek(st, sub)
        objs = [copy.deepcopy(o) for o in (pol[bucket].values() if pol else ())]
    if rg:
        prefix = f"/subscriptions/{sub}/resourcegroups/{rg}/".lower()
        objs = [o for o in objs if o["id"].lower().startswith(prefix)]
    if typ == "policydefinitions" and not rg:
        objs += [_builtin_view(d) for d in policy.BUILTIN_DEFINITIONS.values()]
    return 200, {"value": objs}


def _object(app, method, sub, user, rg, typ, name, body):
    bucket, atype, label, missing = KINDS[typ]
    st = app.state
    if not NAME.match(name):
        return _err(400, "InvalidName", f"The name '{name}' is invalid: use letters, digits, '.', '_', '-' "
                    "(at most 64 characters).")
    rid = _rid(sub, rg, atype, name)
    key = name.lower() if bucket in ("definitions", "sets") else rid.lower()
    if method in ("GET", "HEAD"):
        with st.lock:
            pol = _peek(st, sub)
            obj = copy.deepcopy(pol[bucket].get(key)) if pol else None
        if obj is None:
            return _err(404, missing, f"The {label} '{name}' could not be found.")
        return 200, obj
    if method == "DELETE":
        return _delete(app, sub, user, bucket, label, key, rid)
    if method != "PUT":
        return _err(405, "MethodNotAllowed", method)
    data = _json(body)
    props = data.get("properties") if data is not None else None
    if not isinstance(props, dict):
        return _err(400, "InvalidRequestContent", "The request body must be a JSON object with 'properties'.")
    op = f"Create/Update {label}"
    with st.lock:
        if rg and f"{sub}/{rg.lower()}" not in st.rgs:
            return _err(404, "ResourceGroupNotFound", f"Resource group '{rg}' could not be found.")
        pol = _pol(st, sub)
        existing = pol[bucket].get(key)
        if existing is None and len(pol[bucket]) >= QUOTA:
            result = _err(400, "QuotaExceeded", f"At most {QUOTA} {label}s are allowed in a subscription.")
        else:
            result = BUILDERS[bucket](st, sub, pol, rid, name, rg, data, props, existing)
        if isinstance(result[0], int):  # (status, error body)
            st.log(sub, user, op, rid, "Failed", f"{result[1]['error']['code']}: {result[1]['error']['message']}"[:300])
            return result
        obj = result[0]
        if bucket in ("definitions", "sets"):
            broken = _breaks(pol, make_lookup(pol, obj)) if existing is not None else None
            if broken:
                st.log(sub, user, op, rid, "Failed", f"InvalidPolicyParameters: {broken}"[:300])
                return _err(400, "InvalidPolicyParameters",
                            f"The change would break an assignment that uses it: {broken}")
        pol[bucket][key] = obj
        recompute(st, sub)
        st.log(sub, user, op, rid, "Succeeded")
        st.save()
        out = copy.deepcopy(obj)
    _report(app, user, bucket)
    return (200 if existing is not None and bucket not in ALWAYS_201 else 201), out


KIND_EVENT = {"definitions": "definition", "sets": "set", "assignments": "assignment", "exemptions": "exemption",
              "remediations": "remediation"}


def _report(app, user, what):
    """Tell the achievements service (events.py) a student wrote a policy object; never the facilitator."""
    reporter, auth_ = getattr(app, "events", None), getattr(app, "auth", None)
    if reporter is None or (auth_ is not None and auth_.is_facilitator(user)):
        return
    reporter.emit("policy_written", user, KIND_EVENT.get(what, what))


def _breaks(pol, lookup):
    for a in pol["assignments"].values():
        try:
            engine.expand_assignment(a, lookup)
        except engine.PolicyDefinitionError as exc:
            return f"assignment '{a['name']}': {exc}"
    return None


def _uses(pol, obj):
    """Why `obj` (a definition or set) cannot be deleted, or None."""
    oid = obj["id"].lower()
    for a in pol["assignments"].values():
        if str(a["properties"].get("policyDefinitionId", "")).lower() == oid:
            return f"it is used by policy assignment '{a['name']}'"
    for s in pol["sets"].values():
        if any(str(r.get("policyDefinitionId", "")).lower() == oid for r in s["properties"]["policyDefinitions"]):
            return f"it is included in policy set definition '{s['name']}'"
    return None


def _delete(app, sub, user, bucket, label, key, rid):
    st = app.state
    with st.lock:
        pol = _peek(st, sub)
        obj = pol[bucket].get(key) if pol else None
        if obj is None:
            return 204, None
        if bucket in ("definitions", "sets"):
            why = _uses(pol, obj)
            if why:
                msg = f"The {label} '{obj['name']}' cannot be deleted because {why}."
                st.log(sub, user, f"Delete {label}", rid, "Failed", f"PolicyDefinitionInUse: {msg}"[:300])
                return _err(400, "PolicyDefinitionInUse", msg)
        del pol[bucket][key]
        if bucket == "assignments":  # what hangs off an assignment goes with it
            for b in ("exemptions", "remediations"):
                for k in [k for k, o in pol[b].items()
                          if str(o["properties"].get("policyAssignmentId", "")).lower() == obj["id"].lower()]:
                    del pol[b][k]
        recompute(st, sub)
        st.log(sub, user, f"Delete {label}", rid, "Succeeded")
        st.save()
        return 200, obj


# ---------------------------------------------------------------- builders: validate, and make the stored object
# Each returns (object, None) or an error pair (status, body); the object is a dict.

def _make(rid, atype, name, props, **extra):
    props = dict(props)
    props["provisioningState"] = "Succeeded"
    return {"id": rid, "name": name, "type": atype, **extra, "properties": props}


def _scope_error(sub, scope):
    return _err(403, "AuthorizationFailed", f"The client does not have authorization to perform action over "
                f"scope '{scope}' or the scope is invalid. Policy objects must be in your own subscription "
                f"'/subscriptions/{sub}'.")


def _in_sub(sub, scope):
    s = str(scope).rstrip("/").lower()
    root = f"/subscriptions/{sub}".lower()
    return s == root or s.startswith(root + "/")


def _build_definition(st, sub, pol, rid, name, rg, data, props, existing):
    if not isinstance(props.get("policyRule"), dict):
        return _err(400, "InvalidPolicyRule", "policyRule must be an object.")
    errors = engine.validate_definition({"properties": props})
    if errors:
        return _err(400, "InvalidPolicyRule", "The policy rule is invalid: " + "; ".join(errors), errors)
    out = {k: props[k] for k in ("displayName", "description", "metadata", "version") if k in props}
    out.update({"displayName": props.get("displayName") or name, "mode": props.get("mode") or "All",
                "policyType": "Custom", "policyRule": props["policyRule"], "parameters": props.get("parameters") or {}})
    return _make(rid, KINDS["policydefinitions"][1], name, out), None


def _build_set(st, sub, pol, rid, name, rg, data, props, existing):
    members = props.get("policyDefinitions")
    if not isinstance(members, list) or not members or len(members) > QUOTA:
        return _err(400, "InvalidPolicySetDefinition", f"policyDefinitions must list 1 to {QUOTA} definitions.")
    lookup, seen, clean = make_lookup(pol), set(), []
    for m in members:
        d = lookup(m.get("policyDefinitionId")) if isinstance(m, dict) else None
        if d is None:
            return _err(404, "PolicyDefinitionNotFound", "The policy definition "
                        f"'{m.get('policyDefinitionId') if isinstance(m, dict) else m}' could not be found.")
        if engine._is_set(d):
            return _err(400, "InvalidPolicySetDefinition", "A policy set cannot include another policy set.")
        ref = str(m.get("policyDefinitionReferenceId") or d["name"])
        if ref.lower() in seen:
            return _err(400, "InvalidPolicySetDefinition", f"policyDefinitionReferenceId '{ref}' is used twice.")
        seen.add(ref.lower())
        clean.append({"policyDefinitionId": m["policyDefinitionId"], "policyDefinitionReferenceId": ref,
                      "groupNames": m.get("groupNames") or [], "parameters": m.get("parameters") or {}})
    params = props.get("parameters") or {}
    if not isinstance(params, dict) or any(not isinstance(s, dict) or s.get("type", "String") not in
                                           engine.PARAM_TYPES for s in params.values()):
        return _err(400, "InvalidPolicySetDefinition", "parameters must declare a type for each parameter.")
    out = {k: props[k] for k in ("displayName", "description", "metadata", "policyDefinitionGroups") if k in props}
    out.update({"displayName": props.get("displayName") or name, "policyType": "Custom", "parameters": params,
                "policyDefinitions": clean})
    return _make(rid, KINDS["policysetdefinitions"][1], name, out), None


def _build_assignment(st, sub, pol, rid, name, rg, data, props, existing):
    did = props.get("policyDefinitionId")
    if not isinstance(did, str) or not did:
        return _err(400, "InvalidRequestContent", "policyDefinitionId is required.")
    scope = f"/subscriptions/{sub}" + (f"/resourceGroups/{rg}" if rg else "")
    if props.get("scope") is not None and not _in_sub(sub, props["scope"]):
        return _scope_error(sub, props["scope"])
    not_scopes = props.get("notScopes") or []
    if not isinstance(not_scopes, list) or not all(isinstance(s, str) for s in not_scopes):
        return _err(400, "InvalidRequestContent", "notScopes must be a list of scope ids.")
    for s in not_scopes:
        if not _in_sub(sub, s):
            return _scope_error(sub, s)
    mode = props.get("enforcementMode") or "Default"
    if mode not in ("Default", "DoNotEnforce"):
        return _err(400, "InvalidRequestContent", "enforcementMode must be Default or DoNotEnforce.")
    params = props.get("parameters") or {}
    if not isinstance(params, dict):
        return _err(400, "InvalidPolicyParameters", "parameters must be an object.")
    msgs = props.get("nonComplianceMessages") or []
    if not isinstance(msgs, list) or not all(isinstance(m, dict) for m in msgs):
        return _err(400, "InvalidRequestContent", "nonComplianceMessages must be a list of {message}.")
    lookup = make_lookup(pol)
    target = lookup(did)
    if target is None:
        return _err(404, "PolicyDefinitionNotFound", f"The policy definition '{did}' could not be found.")
    out = {k: props[k] for k in ("description", "metadata", "nonComplianceMessage") if k in props}
    out.update({"displayName": props.get("displayName") or name, "enforcementMode": mode, "policyDefinitionId": did,
                "scope": scope, "notScopes": not_scopes, "parameters": params, "nonComplianceMessages": msgs})
    candidate = {"id": rid, "name": name, "properties": out}
    try:
        engine.expand_assignment(candidate, lookup)
    except engine.PolicyDefinitionError as exc:
        return _err(400, "InvalidPolicyParameters", f"The assignment's parameters are invalid: {exc}")
    extra = {}
    ident = data.get("identity")
    if isinstance(ident, dict) and ident.get("type") in ("SystemAssigned", "UserAssigned"):
        extra["identity"] = {"type": ident["type"]}
        if ident["type"] == "SystemAssigned":
            extra["identity"].update({"principalId": str(uuid.uuid5(auth.NAMESPACE, "policy-principal:" + rid.lower())),
                                      "tenantId": auth.TENANT_ID})
    if data.get("location"):
        extra["location"] = data["location"]
    return _make(rid, KINDS["policyassignments"][1], name, out, **extra), None


def _find_assignment(pol, aid):
    return next((a for a in pol["assignments"].values() if a["id"].lower() == str(aid).lower()), None)


def _build_exemption(st, sub, pol, rid, name, rg, data, props, existing):
    aid = props.get("policyAssignmentId")
    if _find_assignment(pol, aid) is None:
        return _err(404, "PolicyAssignmentNotFound", f"The policy assignment '{aid}' could not be found.")
    cat = props.get("exemptionCategory")
    if cat not in ("Waiver", "Mitigated"):
        return _err(400, "InvalidRequestContent", "exemptionCategory must be Waiver or Mitigated.")
    if props.get("expiresOn") is not None and engine._parse_time(props["expiresOn"]) is None:
        return _err(400, "InvalidRequestContent", "expiresOn must be an ISO 8601 date-time.")
    refs = props.get("policyDefinitionReferenceIds") or []
    if not isinstance(refs, list) or not all(isinstance(r, str) for r in refs):
        return _err(400, "InvalidRequestContent", "policyDefinitionReferenceIds must be a list of strings.")
    out = {k: props[k] for k in ("displayName", "description", "metadata", "expiresOn") if k in props}
    out.update({"policyAssignmentId": aid, "policyDefinitionReferenceIds": refs, "exemptionCategory": cat})
    return _make(rid, KINDS["policyexemptions"][1], name, out), None


def _build_remediation(st, sub, pol, rid, name, rg, data, props, existing):
    """The PUT runs it: the assignment's modify or append effect is applied to the group's existing resources
    (the resource group itself and its container groups), then the counts are answered."""
    assignment = _find_assignment(pol, props.get("policyAssignmentId"))
    if assignment is None:
        return _err(404, "PolicyAssignmentNotFound",
                    f"The policy assignment '{props.get('policyAssignmentId')}' could not be found.")
    lookup, exemptions = make_lookup(pol), list(pol["exemptions"].values())
    prefix = f"{sub}/{rg.lower()}"
    targets = [("rg", st.rgs[prefix])] + [("cg", r) for k, r in st.cgs.items() if k.startswith(prefix + "/")]
    total = 0
    for kind, rec in targets:
        try:
            out = engine.evaluate_write(_view(sub, kind, rec), [assignment], lookup, exemptions)
        except (TypeError, ValueError, KeyError):
            continue
        if out.modified:
            total += 1
            rec["tags"] = out.resource["tags"]
            if kind == "cg" and isinstance(rec.get("body"), dict):
                rec["body"]["tags"] = rec["tags"]
    now = _stamp()
    out = {k: props[k] for k in ("failureThreshold", "resourceCount", "parallelDeployments", "filters") if k in props}
    out.update({"policyAssignmentId": assignment["id"], "policyDefinitionReferenceId":
                props.get("policyDefinitionReferenceId"), "resourceDiscoveryMode":
                props.get("resourceDiscoveryMode") or "ExistingNonCompliant",
                "createdOn": (existing or {}).get("properties", {}).get("createdOn", now), "lastUpdatedOn": now,
                "deploymentStatus": {"totalDeployments": total, "successfulDeployments": total,
                                     "failedDeployments": 0}})
    return _make(rid, KINDS["remediations"][1], name, out), None


BUILDERS = {"definitions": _build_definition, "sets": _build_set, "assignments": _build_assignment,
            "exemptions": _build_exemption, "remediations": _build_remediation}


# ---------------------------------------------------------------- compliance endpoints

def _rows(sub, pol):
    out = []
    for s in pol["states"] if pol else ():
        parts = s["resourceId"].split("/")
        out.append({"resourceId": s["resourceId"], "policyAssignmentId": s["policyAssignmentId"],
                    "policyDefinitionId": s["policyDefinitionId"],
                    "policyDefinitionReferenceId": s["policyDefinitionReferenceId"] or "",
                    "complianceState": s["complianceState"], "isCompliant": s["complianceState"] == "Compliant",
                    "timestamp": s["timestamp"], "subscriptionId": sub,
                    "resourceType": "/".join(parts[-3:-1]) if "providers" in parts else "Microsoft.Resources/resourceGroups",
                    "resourceGroup": parts[4] if len(parts) > 4 else ""})
    return out


def _query(app, sub):
    """Reads the stored states: a poll never computes anything."""
    with app.state.lock:
        return 200, {"value": _rows(sub, _peek(app.state, sub))}


def _trigger(app, sub, user, mgmt):
    """The evaluation is synchronous (it is a few rule checks), so the operation Location already says Succeeded."""
    st = app.state
    with st.lock:
        recompute(st, sub)
        st.save()
    return 202, None, {"Location": f"{mgmt}/subscriptions/{sub}/providers/Microsoft.PolicyInsights/"
                                   "asyncOperationResults/evaluation?api-version=2019-10-01",
                       "Retry-After": "1"}


# ---------------------------------------------------------------- the portal's Policy blade

def portal_section(st, sub):
    """Plain data for GET /cloud/api/policy: assignments with compliance counts and the resources that fail,
    exemptions, custom definitions and sets, and the built-ins (read-only). Never computes: it reads the stored
    states. Strings here may be student-written: the front end must render them with textContent."""
    now = _now()
    with st.lock:
        pol = copy.deepcopy(_peek(st, sub)) or {b: {} for b in BUCKETS} | {"states": []}
    by_a = {}
    for s in pol["states"]:
        by_a.setdefault(s["policyAssignmentId"].lower(), []).append(s)
    lookup = make_lookup({b: pol[b] for b in BUCKETS})
    assignments = []
    for a in pol["assignments"].values():
        ap, rows = a["properties"], by_a.get(a["id"].lower(), [])
        target = lookup(ap.get("policyDefinitionId")) or {}
        assignments.append({
            "id": a["id"], "name": a["name"], "displayName": ap.get("displayName"), "scope": ap.get("scope"),
            "enforcementMode": ap.get("enforcementMode"), "policyDefinitionId": ap.get("policyDefinitionId"),
            "definitionName": (target.get("properties") or {}).get("displayName") or target.get("name"),
            "isSet": engine._is_set(target) if target else False,
            "effect": ((target.get("properties") or {}).get("policyRule") or {}).get("then", {}).get("effect", ""),
            "compliant": sum(1 for r in rows if r["complianceState"] == "Compliant"),
            "nonCompliant": sum(1 for r in rows if r["complianceState"] == "NonCompliant"),
            "exempt": sum(1 for r in rows if r["complianceState"] == "Exempt"),
            "resources": [{"resourceId": r["resourceId"], "name": r["resourceId"].rsplit("/", 1)[-1],
                           "definitionReferenceId": r["policyDefinitionReferenceId"], "reason": r["reason"]}
                          for r in rows if r["complianceState"] == "NonCompliant"]})
    exemptions = []
    for e in pol["exemptions"].values():
        ep = e["properties"]
        t = engine._parse_time(ep.get("expiresOn")) if ep.get("expiresOn") else None
        exemptions.append({"id": e["id"], "name": e["name"], "displayName": ep.get("displayName"),
                           "policyAssignmentId": ep.get("policyAssignmentId"),
                           "category": ep.get("exemptionCategory"), "expiresOn": ep.get("expiresOn"),
                           "expired": bool(t and t <= now)})
    slim = lambda o: {"id": o["id"], "name": o["name"], "displayName": o["properties"].get("displayName"),
                      "description": o["properties"].get("description"),
                      "rule": o["properties"].get("policyRule") or o["properties"].get("policyDefinitions"),
                      "parameters": o["properties"].get("parameters") or {}}
    builtins = []
    for a in policy.PLATFORM_ASSIGNMENTS:
        d = policy.BUILTIN_DEFINITIONS[a["properties"]["policyDefinitionId"]]
        builtins.append({"id": d["id"], "name": d["name"], "displayName": d["properties"]["displayName"],
                         "effect": d["properties"]["policyRule"]["then"]["effect"],
                         "rule": d["properties"]["policyRule"], "parameters": d["properties"].get("parameters") or {},
                         "message": a["properties"].get("nonComplianceMessage", ""), "readOnly": True})
    return {"assignments": assignments, "exemptions": exemptions,
            "definitions": [slim(o) for o in pol["definitions"].values()],
            "sets": [slim(o) for o in pol["sets"].values()], "builtIns": builtins,
            "evaluatedAt": pol.get("evaluatedAt", "")}


def portal_write(st, sub, user, action, name="", mode=""):
    """The portal's hand-made drift for the Policy blade: set a subscription-scope assignment's enforcementMode,
    delete it, or recompute compliance. Same stored objects and the same recompute as the ARM routes. -> (status, body)."""
    if action == "evaluate":
        with st.lock:
            recompute(st, sub)
            st.log(sub, user, "Evaluate policy compliance", f"/subscriptions/{sub}", "Succeeded", "portal")
            st.save()
        return 200, {"evaluated": True}
    if not NAME.match(name or ""):
        return _err(400, "InvalidName", f"The name '{name}' is invalid.")
    rid = _rid(sub, None, "Microsoft.Authorization/policyAssignments", name)
    if action == "delete":
        with st.lock:
            pol = _peek(st, sub)
            if not pol or rid.lower() not in pol["assignments"]:
                return _err(404, "PolicyAssignmentNotFound", f"The policy assignment '{name}' could not be found.")
        status, out = _delete(_AppState(st), sub, user, "assignments", "policy assignment", rid.lower(), rid)
        return (200, {"deleted": True}) if status in (200, 204) else (status, out)
    if mode not in ("Default", "DoNotEnforce"):
        return _err(400, "InvalidRequestContent", 'The body must be {"mode": "Default"|"DoNotEnforce"}.')
    with st.lock:
        pol = _peek(st, sub)
        obj = pol["assignments"].get(rid.lower()) if pol else None
        if obj is None:
            return _err(404, "PolicyAssignmentNotFound", f"The policy assignment '{name}' could not be found.")
        obj["properties"]["enforcementMode"] = mode
        recompute(st, sub)
        st.log(sub, user, "Create/Update policy assignment", rid, "Succeeded", f"enforcementMode={mode} (portal)")
        st.save()
    return 200, {"name": obj["name"], "enforcementMode": mode}


class _AppState:
    """_delete only needs app.state."""
    def __init__(self, st):
        self.state = st
