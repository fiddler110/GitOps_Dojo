"""Dojo Cloud Policy: a data-driven rule engine with an Azure-Policy-like grammar.

Pure functions, stdlib only, no I/O (so it is unit-tested in test_policy_engine.py).

Shapes
  resource    {id, type, name, location, tags, properties}   (build one with resource_view)
  definition  {id, name, properties: {displayName, policyType, mode, parameters, policyRule: {if, then}}}
  set         {id, name, properties: {displayName, parameters, policyDefinitions: [...]}}
  assignment  {id, name, properties: {policyDefinitionId, scope, notScopes, parameters, enforcementMode,
              nonComplianceMessage | nonComplianceMessages, displayName}}
  exemption   {id, name, properties: {policyAssignmentId, scope, policyDefinitionReferenceIds, expiresOn}}
  lookup(id)  -> definition or set dict, or None

Conditions: field + one operator (equals notEquals in notIn like notLike contains notContains exists less
lessOrEquals greater greaterOrEquals), or allOf / anyOf / not. Strings compare case-insensitively.
Dojo extensions (not in the real product): operator isBlank, operator inExact (case-sensitive in), and the
alias .../containers[*].environmentVariableCount (there is no `count` expression).

`[*]` arrays: a condition on an array alias is true only if it holds for EVERY element. An empty or missing
array has no elements, so it is vacuously true (wrap in `not` to deny on "some element fails").
Template expressions: "[parameters('name')]", whole string only.
Effects: deny, audit, modify (tags only), append (tags only), disabled. Modify and append run first, then
deny and audit see the changed resource.
"""
import copy
import datetime
import re
from dataclasses import dataclass, field as dc_field

CG = "Microsoft.ContainerInstance/containerGroups"
RG = "Microsoft.Resources/resourceGroups"
EFFECTS = ("deny", "audit", "modify", "append", "disabled")
MODES = ("All", "Indexed")
COMPARISON_OPS = ("equals", "notEquals", "in", "notIn", "like", "notLike", "contains", "notContains",
                  "exists", "less", "lessOrEquals", "greater", "greaterOrEquals", "isBlank", "inExact")
PARAM_TYPES = ("String", "Array", "Integer", "Float", "Boolean", "Object")

_P = CG + "/"
_ALIASES = {  # lower-cased alias -> path into the resource; "*" flattens an array; "#envcount" is computed
    _P + "containers[*].name": ("properties", "containers", "*", "name"),
    _P + "containers[*].image": ("properties", "containers", "*", "properties", "image"),
    _P + "containers[*].resources.requests.cpu":
        ("properties", "containers", "*", "properties", "resources", "requests", "cpu"),
    _P + "containers[*].resources.requests.memoryinGB".lower():
        ("properties", "containers", "*", "properties", "resources", "requests", "memoryInGB"),
    _P + "containers[*].ports[*].port": ("properties", "containers", "*", "properties", "ports", "*", "port"),
    _P + "containers[*].environmentvariablecount": ("properties", "containers", "*", "#envcount"),
    _P + "ipaddress.dnsnamelabel": ("properties", "ipAddress", "dnsNameLabel"),
    _P + "ipaddress.type": ("properties", "ipAddress", "type"),
    _P + "ipaddress.ports[*].port": ("properties", "ipAddress", "ports", "*", "port"),
    _P + "ostype": ("properties", "osType"),
}
_ALIASES = {k.lower(): v for k, v in _ALIASES.items()}
ALIAS_NAMES = tuple(sorted(a for a in (
    _P + "containers[*].name", _P + "containers[*].image", _P + "containers[*].resources.requests.cpu",
    _P + "containers[*].resources.requests.memoryInGB", _P + "containers[*].ports[*].port",
    _P + "containers[*].environmentVariableCount", _P + "ipAddress.dnsNameLabel", _P + "ipAddress.type",
    _P + "ipAddress.ports[*].port", _P + "osType")))
_PARAM_REF = re.compile(r"\[parameters\('([^']+)'\)\]")
_PARAM_WHOLE = re.compile(r"^\[parameters\('([^']+)'\)\]\Z")
_TAG_BRACKET = re.compile(r"""^tags\[(['"])(.+)\1\]\Z""", re.I)
_TAG_DOT = re.compile(r"^tags\.([^.\[\]]+)\Z", re.I)


class PolicyDefinitionError(ValueError):
    """A definition, set or assignment that cannot be evaluated (bad parameter value, bad reference)."""


@dataclass
class Violation:
    assignmentId: str
    assignmentName: str
    assignmentDisplayName: str
    definitionId: str
    definitionName: str
    displayName: str
    referenceId: object
    effect: str
    reason: str
    message: str = ""
    enforced: bool = True


@dataclass
class Outcome:
    denied: list = dc_field(default_factory=list)
    audited: list = dc_field(default_factory=list)
    resource: dict = None
    modified: list = dc_field(default_factory=list)


# ---------------------------------------------------------------- resources

def resource_view(kind, name, location, tags, props, sub, rg):
    """Builds the ARM-shaped resource the engine evaluates. kind: 'resourceGroup' or 'containerGroup'."""
    if tags is None:
        tags = {}
    if not isinstance(tags, dict):
        raise TypeError("tags must be an object")
    if kind == "resourceGroup":
        rid, rtype = f"/subscriptions/{sub}/resourceGroups/{name}", RG
    elif kind == "containerGroup":
        rid, rtype = f"/subscriptions/{sub}/resourceGroups/{rg}/providers/{CG}/{name}", CG
    else:
        raise ValueError(f"unknown resource kind {kind!r}")
    return {"id": rid, "type": rtype, "name": name, "location": location, "tags": dict(tags),
            "properties": props if props is not None else {}}


def _props(d):
    p = d.get("properties") if isinstance(d, dict) else None
    return p if isinstance(p, dict) else (d if isinstance(d, dict) else {})


def _tag_name(fld):
    m = _TAG_BRACKET.match(fld) or _TAG_DOT.match(fld)
    return m.group(2 if m.re is _TAG_BRACKET else 1) if m else None


def _field_kind(fld):
    """('basic', key) | ('tags',) | ('tag', name) | ('alias', path) | None when unknown."""
    if not isinstance(fld, str):
        return None
    low = fld.strip().lower()
    if low in ("type", "name", "location", "id", "kind"):
        return ("basic", low)
    if low == "tags":
        return ("tags",)
    t = _tag_name(fld.strip())
    if t is not None:
        return ("tag", t)
    if low in _ALIASES:
        return ("alias", _ALIASES[low])
    return None


def _tag_lookup(tags, name):
    if not isinstance(tags, dict):
        return False, None
    for k, v in tags.items():
        if str(k).lower() == name.lower():
            return True, v
    return False, None


def _resolve(res, fld):
    """-> (values, is_array, present). Missing scalars give [None]."""
    kind = _field_kind(fld)
    if kind is None:
        raise PolicyDefinitionError(f"unknown field alias '{fld}'")
    if kind[0] == "basic":
        v = res.get(kind[1])
        return [v], False, v is not None
    if kind[0] == "tags":
        v = res.get("tags")
        return [v], False, bool(v)
    if kind[0] == "tag":
        present, v = _tag_lookup(res.get("tags"), kind[1])
        return [v], False, present
    cur, is_arr = [res], False
    for tok in kind[1]:
        if tok == "*":
            is_arr = True
            cur = [e for v in cur if isinstance(v, list) for e in v]
        elif tok == "#envcount":
            cur = [len(((v.get("properties") or {}).get("environmentVariables") or []))
                   if isinstance(v, dict) else 0 for v in cur]
        else:
            cur = [v.get(tok) if isinstance(v, dict) else None for v in cur]
    if not is_arr and not cur:
        cur = [None]
    return cur, is_arr, any(v is not None for v in cur)


# ---------------------------------------------------------------- expressions and parameters

def _subst(value, params):
    if isinstance(value, str):
        m = _PARAM_WHOLE.match(value)
        if m:
            if m.group(1) not in params:
                raise PolicyDefinitionError(f"parameter '{m.group(1)}' is not defined")
            return params[m.group(1)]
        return value
    if isinstance(value, list):
        return [_subst(v, params) for v in value]
    if isinstance(value, dict):
        return {k: _subst(v, params) for k, v in value.items()}
    return value


def _type_ok(ptype, v):
    if ptype == "String":
        return isinstance(v, str)
    if ptype == "Array":
        return isinstance(v, list)
    if ptype == "Integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if ptype == "Float":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if ptype == "Boolean":
        return isinstance(v, bool)
    if ptype == "Object":
        return isinstance(v, dict)
    return False


def resolve_parameters(declared, supplied):
    """declared {name: {type, defaultValue, allowedValues}}, supplied {name: {value}|value}
    -> (values, errors). Checks type, allowedValues, unknown and missing parameters."""
    declared, supplied = declared or {}, supplied or {}
    values, errors = {}, []
    for name in supplied:
        if name not in declared:
            errors.append(f"parameter '{name}' is not defined")
    for name, spec in declared.items():
        spec = spec if isinstance(spec, dict) else {}
        if name in supplied:
            s = supplied[name]
            v = s["value"] if isinstance(s, dict) and "value" in s else s
        elif "defaultValue" in spec:
            v = spec["defaultValue"]
        else:
            errors.append(f"parameter '{name}' has no value and no defaultValue")
            continue
        ptype = spec.get("type", "String")
        if not _type_ok(ptype, v):
            errors.append(f"parameter '{name}' must be of type {ptype}")
            continue
        allowed = spec.get("allowedValues")
        if allowed is not None and not any(_eq(v, a) for a in allowed):
            errors.append(f"parameter '{name}' value {v!r} is not one of the allowed values "
                          f"[{', '.join(map(str, allowed))}]")
            continue
        values[name] = v
    return values, errors


# ---------------------------------------------------------------- comparison

def _eq(a, b):
    if isinstance(a, str) and isinstance(b, str):
        return a.lower() == b.lower()
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    return a == b


def _num(v):
    if isinstance(v, bool) or v is None:
        raise ValueError
    return float(v)


def _like(v, pattern):
    if not isinstance(v, str) or not isinstance(pattern, str):
        return False
    rx = ".*".join(re.escape(p) for p in pattern.split("*"))
    return re.fullmatch(rx, v, re.I | re.S) is not None


def _order(op, v, o):
    try:
        a, b = _num(v), _num(o)
    except (ValueError, TypeError):
        if not (isinstance(v, str) and isinstance(o, str)):
            return False
        a, b = v.lower(), o.lower()
    return {"less": a < b, "lessOrEquals": a <= b, "greater": a > b, "greaterOrEquals": a >= b}[op]


def _cmp(op, v, o):
    if op == "equals":
        return _eq(v, o)
    if op == "notEquals":
        return not _eq(v, o)
    if op in ("in", "notIn", "inExact"):
        if not isinstance(o, list):
            raise PolicyDefinitionError(f"operator '{op}' needs an array")
        if op == "inExact":
            hit = any(v == x and isinstance(v, bool) == isinstance(x, bool) for x in o)
        else:
            hit = any(_eq(v, x) for x in o)
        return not hit if op == "notIn" else hit
    if op in ("like", "notLike"):
        return _like(v, o) != (op == "notLike")
    if op in ("contains", "notContains"):
        if isinstance(v, str) and isinstance(o, str):
            hit = o.lower() in v.lower()
        elif isinstance(v, (list, tuple)):
            hit = any(_eq(x, o) for x in v)
        elif isinstance(v, dict):
            hit = any(_eq(k, o) for k in v)
        else:
            hit = False
        return hit != (op == "notContains")
    if op == "isBlank":
        return (v is None or str(v).strip() == "") == _truthy(o)
    return _order(op, v, o)


def _truthy(x):
    return x.lower() == "true" if isinstance(x, str) else bool(x)


def _operator(cond):
    ops = [k for k in cond if k in COMPARISON_OPS]
    return ops[0] if len(ops) == 1 else None


def _eval(cond, res, params):
    if "allOf" in cond:
        return all(_eval(c, res, params) for c in cond["allOf"])
    if "anyOf" in cond:
        return any(_eval(c, res, params) for c in cond["anyOf"])
    if "not" in cond:
        return not _eval(cond["not"], res, params)
    values, is_arr, present = _resolve(res, cond["field"])
    op = _operator(cond)
    operand = _subst(cond[op], params)
    if op == "exists":
        return present == _truthy(operand)
    return all(_cmp(op, v, operand) for v in values)


# ---------------------------------------------------------------- reasons

_WORDS = {"equals": ("is", "is not"), "notEquals": ("is not", "is"), "in": ("is in", "is not in"),
          "inExact": ("is in", "is not in"), "notIn": ("is not in", "is in"),
          "like": ("matches", "does not match"), "notLike": ("does not match", "matches"),
          "contains": ("contains", "does not contain"), "notContains": ("does not contain", "contains"),
          "less": ("is less than", "is not less than"),
          "lessOrEquals": ("is at most", "is more than"),
          "greater": ("is greater than", "is not greater than"),
          "greaterOrEquals": ("is at least", "is less than")}


def _fmt(x):
    return "[" + ", ".join(map(str, x)) + "]" if isinstance(x, list) else str(x)


def _describe(cond, res, params, neg=False):
    if "allOf" in cond or "anyOf" in cond:
        key = "allOf" if "allOf" in cond else "anyOf"
        join = " and " if (key == "allOf") != neg else " or "
        return "(" + join.join(_describe(c, res, params, neg) for c in cond[key]) + ")"
    if "not" in cond:
        return _describe(cond["not"], res, params, not neg)
    fld, op = cond["field"], _operator(cond)
    values, is_arr, present = _resolve(res, fld)
    shown = ", ".join(map(str, values)) if is_arr else values[0]
    name = _tag_name(fld) and f"tag '{_tag_name(fld)}'" or fld.rsplit("/", 1)[-1]
    operand = _subst(cond[op], params)
    if op == "exists":
        want = _truthy(operand) != neg
        return f"{name} {'exists' if want else 'does not exist'}"
    if op == "isBlank":
        return f"{name} {'is blank' if _truthy(operand) != neg else 'is not blank'}"
    word = _WORDS[op][1 if neg else 0]
    return f"{name} '{shown}' {word} {_fmt(operand)}"


# ---------------------------------------------------------------- validation

def _walk_strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, list):
        for i in x:
            yield from _walk_strings(i)
    elif isinstance(x, dict):
        for v in x.values():
            yield from _walk_strings(v)


def _check_cond(cond, errors, path="if"):
    if not isinstance(cond, dict):
        errors.append(f"{path}: a condition must be an object")
        return
    logical = [k for k in ("allOf", "anyOf", "not") if k in cond]
    if logical:
        if len(logical) > 1 or len(cond) > 1:
            errors.append(f"{path}: {logical[0]} cannot be combined with other keys")
            return
        k = logical[0]
        if k == "not":
            _check_cond(cond["not"], errors, path + ".not")
        elif not isinstance(cond[k], list) or not cond[k]:
            errors.append(f"{path}.{k}: must be a non-empty array of conditions")
        else:
            for i, c in enumerate(cond[k]):
                _check_cond(c, errors, f"{path}.{k}[{i}]")
        return
    if "field" not in cond:
        errors.append(f"{path}: condition needs a 'field' (or allOf/anyOf/not)")
        return
    if _field_kind(cond["field"]) is None:
        errors.append(f"{path}: unknown field alias '{cond['field']}'")
    others = [k for k in cond if k != "field"]
    ops = [k for k in others if k in COMPARISON_OPS]
    for k in others:
        if k not in COMPARISON_OPS:
            errors.append(f"{path}: unknown operator '{k}'")
    if not others:
        errors.append(f"{path}: condition on '{cond['field']}' has no operator")
    elif len(ops) > 1:
        errors.append(f"{path}: use exactly one operator, found {', '.join(ops)}")


def _tag_field_ok(fld):
    return isinstance(fld, str) and _tag_name(fld.strip()) is not None


def validate_definition(defn):
    """-> list of human error strings (empty when the definition is usable)."""
    errors = []
    if not isinstance(defn, dict):
        return ["definition must be an object"]
    p = _props(defn)
    if p.get("mode", "All") not in MODES:
        errors.append(f"mode '{p.get('mode')}' is not one of {', '.join(MODES)}")
    declared = p.get("parameters") or {}
    if not isinstance(declared, dict):
        errors.append("parameters must be an object")
        declared = {}
    for n, spec in declared.items():
        if not isinstance(spec, dict) or spec.get("type", "String") not in PARAM_TYPES:
            errors.append(f"parameter '{n}' needs a type of {', '.join(PARAM_TYPES)}")
    rule = p.get("policyRule")
    if not isinstance(rule, dict) or "if" not in rule:
        errors.append("policyRule.if is missing")
        return errors
    _check_cond(rule["if"], errors)
    then = rule.get("then")
    if not isinstance(then, dict) or "effect" not in then:
        errors.append("policyRule.then.effect is missing")
        return errors
    for s in _walk_strings(rule):
        for name in _PARAM_REF.findall(s):
            if name not in declared:
                errors.append(f"parameters('{name}') is used but not declared")
    effect = then["effect"]
    names = [effect]
    m = _PARAM_WHOLE.match(effect) if isinstance(effect, str) else None
    if m and m.group(1) in declared:
        spec = declared[m.group(1)]
        names = list(spec.get("allowedValues") or []) + (
            [spec["defaultValue"]] if "defaultValue" in spec else [])
    elif m:
        names = []
    for e in names:
        if not isinstance(e, str) or e.lower() not in EFFECTS:
            errors.append(f"unknown effect '{e}' (use {', '.join(EFFECTS)})")
    lowered = {str(e).lower() for e in names} | ({"modify", "append"} if m and not names else set())
    details = then.get("details")
    if "modify" in lowered:
        ops = details.get("operations") if isinstance(details, dict) else None
        if not ops or not isinstance(ops, list):
            errors.append("modify needs then.details.operations")
        else:
            for o in ops:
                if not isinstance(o, dict) or str(o.get("operation", "")).lower() not in (
                        "addorreplace", "add", "remove"):
                    errors.append("modify operation must be addOrReplace, add or remove")
                elif not _tag_field_ok(o.get("field")):
                    errors.append(f"modify can only change tags, not '{o.get('field')}'")
                elif str(o["operation"]).lower() != "remove" and "value" not in o:
                    errors.append(f"modify operation on '{o['field']}' needs a value")
    if "append" in lowered:
        if not isinstance(details, list) or not details:
            errors.append("append needs then.details as a list of {field, value}")
        else:
            for d in details:
                if not isinstance(d, dict) or "value" not in d:
                    errors.append("append detail needs a field and a value")
                elif not _tag_field_ok(d.get("field")):
                    errors.append(f"append can only add tags, not '{d.get('field')}'")
    return errors


# ---------------------------------------------------------------- scopes, sets, exemptions

def _under(scope, rid):
    if not isinstance(scope, str) or not isinstance(rid, str):
        return False
    s, r = scope.rstrip("/").lower(), rid.lower()
    return s == "" or r == s or r.startswith(s + "/")


def _in_scope(assignment, rid):
    p = _props(assignment)
    if not _under(p.get("scope", "/"), rid):
        return False
    return not any(_under(ns, rid) for ns in (p.get("notScopes") or []))


def _is_set(d):
    return "policyDefinitions" in _props(d)


def expand_assignment(assignment, lookup):
    """-> [(definition, resolved_params, referenceId)]. Raises PolicyDefinitionError on bad references or values."""
    ap = _props(assignment)
    target = lookup(ap.get("policyDefinitionId"))
    if target is None:
        raise PolicyDefinitionError(f"policy '{ap.get('policyDefinitionId')}' was not found")
    tp = _props(target)
    values, errors = resolve_parameters(tp.get("parameters"), ap.get("parameters"))
    if errors:
        raise PolicyDefinitionError("; ".join(errors))
    if not _is_set(target):
        return [(target, values, None)]
    out = []
    for ref in tp["policyDefinitions"]:
        d = lookup(ref.get("policyDefinitionId"))
        if d is None:
            raise PolicyDefinitionError(f"policy '{ref.get('policyDefinitionId')}' was not found")
        supplied = {k: {"value": _subst(v["value"] if isinstance(v, dict) and "value" in v else v, values)}
                    for k, v in (ref.get("parameters") or {}).items()}
        vals, errs = resolve_parameters(_props(d).get("parameters"), supplied)
        if errs:
            raise PolicyDefinitionError("; ".join(errs))
        out.append((d, vals, ref.get("policyDefinitionReferenceId") or d.get("name")))
    return out


def _parse_time(s):
    try:
        t = datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=datetime.timezone.utc)


def _exempt(exemptions, assignment, ref, rid, now):
    for ex in exemptions or ():
        ep = _props(ex)
        aid = ep.get("policyAssignmentId")
        if not aid or str(aid).lower() != str(assignment.get("id", "")).lower():
            continue
        scope = ep.get("scope")
        if scope is None:
            eid = str(ex.get("id", ""))
            scope = re.split(r"/providers/Microsoft\.Authorization/policyExemptions/", eid, flags=re.I)[0]
        if not _under(scope, rid):
            continue
        refs = ep.get("policyDefinitionReferenceIds")
        if refs and (ref is None or ref.lower() not in [str(r).lower() for r in refs]):
            continue
        if ep.get("expiresOn"):
            t = _parse_time(ep["expiresOn"])
            if t is not None and t <= now:
                continue
        return True
    return False


def _indexed_ok(defn, res):
    if _props(defn).get("mode", "All") != "Indexed":
        return True
    return res.get("type") != RG and "location" in res and "tags" in res


def _effect(defn, params):
    e = _subst(_props(defn)["policyRule"]["then"]["effect"], params)
    return str(e).lower()


def _message(assignment, ref):
    ap = _props(assignment)
    for m in ap.get("nonComplianceMessages") or []:
        if isinstance(m, dict) and m.get("message") and m.get("policyDefinitionReferenceId") in (None, ref):
            return m["message"]
    return ap.get("nonComplianceMessage") or ""


def _tag_changes(defn, params, res):
    """Planned tag edits [(label, tag, op, value)] that would actually change res for modify/append."""
    then = _props(defn)["policyRule"]["then"]
    effect = _effect(defn, params)
    out = []
    if effect == "modify":
        for o in _subst(then["details"]["operations"], params):
            op, tag = str(o["operation"]).lower(), _tag_name(o["field"].strip())
            present, cur = _tag_lookup(res.get("tags"), tag)
            if op == "remove" and present:
                out.append((f"remove tags['{tag}']", tag, "remove", None))
            elif op == "add" and not present:
                out.append((f"add tags['{tag}']", tag, "set", o["value"]))
            elif op == "addorreplace" and (not present or not _eq(cur, o["value"])):
                out.append((f"addOrReplace tags['{tag}']", tag, "set", o["value"]))
    elif effect == "append":
        for d in _subst(then["details"], params):
            tag = _tag_name(d["field"].strip())
            if not _tag_lookup(res.get("tags"), tag)[0]:
                out.append((f"append tags['{tag}']", tag, "set", d["value"]))
    return out


def _apply(res, changes):
    tags = res.setdefault("tags", {})
    for _label, tag, op, value in changes:
        key = next((k for k in tags if str(k).lower() == tag.lower()), tag)
        if op == "remove":
            tags.pop(key, None)
        else:
            tags[key] = value


def _items(res, assignments, lookup, exemptions, now):
    """Yields (assignment, defn, params, ref, effect, exempt, enforced) for every applicable definition."""
    for a in assignments:
        if not _in_scope(a, res.get("id", "")):
            continue
        try:
            expanded = expand_assignment(a, lookup)
        except PolicyDefinitionError:
            continue
        enforced = _props(a).get("enforcementMode", "Default") != "DoNotEnforce"
        for defn, params, ref in expanded:
            if validate_definition(defn) and not _props(defn).get("policyRule"):
                continue
            try:
                effect = _effect(defn, params)
            except PolicyDefinitionError:
                continue
            if effect == "disabled" or effect not in EFFECTS or not _indexed_ok(defn, res):
                continue
            yield a, defn, params, ref, effect, _exempt(exemptions, a, ref, res.get("id", ""), now), enforced


def _violation(a, defn, params, ref, effect, reason, enforced):
    ap, dp = _props(a), _props(defn)
    return Violation(
        assignmentId=a.get("id", ""), assignmentName=a.get("name", ""),
        assignmentDisplayName=ap.get("displayName") or dp.get("displayName") or a.get("name", ""),
        definitionId=defn.get("id", ""), definitionName=defn.get("name", ""),
        displayName=dp.get("displayName") or defn.get("name", ""), referenceId=ref, effect=effect,
        reason=reason, message=_message(a, ref), enforced=enforced)


def _now(now):
    return now or datetime.datetime.now(datetime.timezone.utc)


def evaluate_write(resource, assignments, lookup, exemptions=(), now=None):
    """Evaluates a create/update. Modify and append change a copy first, then deny and audit are judged on it.
    DoNotEnforce assignments are recorded in `audited` (enforced=False) and never block or change anything."""
    now = _now(now)
    out = Outcome(resource=copy.deepcopy(resource))
    items = list(_items(out.resource, assignments, lookup, exemptions, now))
    for a, defn, params, ref, effect, exempt, enforced in items:
        if exempt or effect not in ("modify", "append"):
            continue
        rule = _props(defn)["policyRule"]
        if not _eval(rule["if"], out.resource, params):
            continue
        changes = _tag_changes(defn, params, out.resource)
        if not changes:
            continue
        if enforced:
            _apply(out.resource, changes)
            out.modified += [c[0] for c in changes]
        else:
            out.audited.append(_violation(a, defn, params, ref, effect,
                                          "would " + ", ".join(c[0] for c in changes), False))
    for a, defn, params, ref, effect, exempt, enforced in items:
        if exempt or effect not in ("deny", "audit"):
            continue
        rule = _props(defn)["policyRule"]
        if not _eval(rule["if"], out.resource, params):
            continue
        v = _violation(a, defn, params, ref, effect, _describe(rule["if"], out.resource, params),
                       enforced and effect == "deny")
        if effect == "deny" and enforced:
            out.denied.append(v)
        else:
            out.audited.append(v)
    return out


def compliance(resources, assignments, lookup, exemptions=(), now=None):
    """-> [{assignmentId, definitionId, referenceId, resourceId, state, reason}] for deny/audit/modify/append."""
    now = _now(now)
    rows = []
    for res in resources:
        for a, defn, params, ref, effect, exempt, _enf in _items(res, assignments, lookup, exemptions, now):
            rule = _props(defn)["policyRule"]
            state, reason = "Compliant", ""
            if exempt:
                state, reason = "Exempt", "an exemption applies"
            elif _eval(rule["if"], res, params):
                if effect in ("modify", "append"):
                    changes = _tag_changes(defn, params, res)
                    if changes:
                        state, reason = "NonCompliant", "would " + ", ".join(c[0] for c in changes)
                else:
                    state, reason = "NonCompliant", _describe(rule["if"], res, params)
            rows.append({"assignmentId": a.get("id", ""), "definitionId": defn.get("id", ""),
                         "referenceId": ref, "resourceId": res.get("id", ""), "state": state,
                         "reason": reason})
    return rows
