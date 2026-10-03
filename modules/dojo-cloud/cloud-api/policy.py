"""Dojo Cloud's "Azure Policy": rules every request is checked against.

Each rule is a teaching moment (TOFU-BASICS-PLAN.md §6.3). A violation becomes an
ARM-shaped error the student has to read and fix in their HCL. Pure functions,
no I/O, so they are unit-tested in test_policy.py.
"""
import functools
import math
import re

import policy_engine as engine

# Canadian regions only (a data-residency style policy); the default is the first.
ALLOWED_LOCATIONS = ("canadacentral", "canadaeast")
ALLOWED_IMAGES = ("dojo/hello:1.0", "dojo/hello:2.0")
REQUIRED_TAGS = ("owner", "env")
MAX_CPU = 0.25
MAX_MEMORY_GB = 0.125
# A floor as well: a request that rounds to 0 becomes "unlimited" in Docker, and below these values the runtime
# refuses the container anyway (1 ms CPU quota, 6 MB memory).
MIN_CPU = 0.05
MIN_MEMORY_GB = 0.03125
MAX_CONTAINER_GROUPS = 2
ALLOWED_PORTS = (80,)
MAX_ENV_VARS = 10
RG_NAME = re.compile(r"^rg-[a-z0-9][a-z0-9-]{1,56}\Z")
CG_NAME = re.compile(r"^ci-[a-z0-9][a-z0-9-]{1,56}\Z")
DNS_LABEL = re.compile(r"^[a-z][a-z0-9-]{2,40}\Z")
ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}\Z")
RESERVED_ENV = ("PATH", "HOSTNAME", "HELLO_VERSION", "HOME")


class PolicyError(Exception):
    def __init__(self, status, code, message, target=None, policy=None):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
        self.target, self.policy = target, policy

    def body(self):
        err = {"code": self.code, "message": self.message}
        if self.target:
            err["target"] = self.target
        if self.policy:
            err["additionalInfo"] = [{"type": "PolicyViolation", "info": {
                "policyDefinitionDisplayName": self.policy}}]
        return {"error": err}


def _shape_guarded(check):
    """A body the checks cannot even walk (a list where an object belongs, a string where a number belongs) is a
    malformed request: answer 400, never let the surprise escape as a 500."""
    @functools.wraps(check)
    def guarded(*args, **kwargs):
        try:
            return check(*args, **kwargs)
        except (AttributeError, TypeError, ValueError, KeyError, IndexError, OverflowError):
            raise PolicyError(400, "InvalidRequestContent",
                              "The request body has an unexpected structure or an invalid value.") from None
    return guarded


def _disallowed(name, policy, detail):
    return PolicyError(
        403, "RequestDisallowedByPolicy",
        f"Resource '{name}' was disallowed by policy. Policy: '{policy}'. {detail}",
        target=name, policy=policy)


# ---- built-in definitions: the real guardrails, expressed as data and judged by policy_engine ----
_DEF_PREFIX = "/providers/Microsoft.Authorization/policyDefinitions/"


def _builtin(slug, display, rule, parameters):
    return {"id": _DEF_PREFIX + slug, "name": slug, "properties": {
        "displayName": display, "policyType": "BuiltIn", "mode": "All", "parameters": parameters,
        "policyRule": {"if": rule, "then": {"effect": "deny"}}}}


def _param(ptype):
    return {"type": ptype}


_CGT = {"field": "type", "equals": engine.CG}
_C = engine.CG + "/containers[*]."
BUILTIN_DEFINITIONS = {d["id"]: d for d in (
    _builtin("dojo-allowed-locations", "Allowed locations",
             {"not": {"field": "location", "inExact": "[parameters('listOfAllowedLocations')]"}},
             {"listOfAllowedLocations": _param("Array")}),
    *(_builtin(f"dojo-require-tag-{t}", f"Require tag '{t}'",
               {"anyOf": [{"field": f"tags['{t}']", "exists": "false"},
                          {"field": f"tags['{t}']", "isBlank": "true"}]}, {})
      for t in REQUIRED_TAGS),
    _builtin("dojo-allowed-images", "Allowed container images",
             {"allOf": [_CGT, {"not": {"field": _C + "image", "inExact": "[parameters('listOfAllowedImages')]"}}]},
             {"listOfAllowedImages": _param("Array")}),
    _builtin("dojo-max-cpu", "Maximum container CPU",
             {"allOf": [_CGT, {"not": {"field": _C + "resources.requests.cpu",
                                       "lessOrEquals": "[parameters('maxCpu')]"}}]},
             {"maxCpu": _param("Float")}),
    _builtin("dojo-max-memory", "Maximum container memory",
             {"allOf": [_CGT, {"not": {"field": _C + "resources.requests.memoryInGB",
                                       "lessOrEquals": "[parameters('maxMemoryGB')]"}}]},
             {"maxMemoryGB": _param("Float")}),
    _builtin("dojo-allowed-ports", "Allowed container ports",
             {"allOf": [_CGT, {"not": {"allOf": [
                 {"field": _C + "ports[*].port", "inExact": "[parameters('listOfAllowedPorts')]"},
                 {"field": engine.CG + "/ipAddress.ports[*].port",
                  "inExact": "[parameters('listOfAllowedPorts')]"}]}}]},
             {"listOfAllowedPorts": _param("Array")}),
    _builtin("dojo-max-env-vars", "Maximum environment variables",
             {"allOf": [_CGT, {"not": {"field": _C + "environmentVariableCount",
                                       "lessOrEquals": "[parameters('maxEnvVars')]"}}]},
             {"maxEnvVars": _param("Integer")}),
)}


def _platform(slug, display, params, message):
    return {"id": f"/providers/Microsoft.Authorization/policyAssignments/platform-{slug}",
            "name": f"platform-{slug}", "properties": {
                "displayName": display, "scope": "/", "policyDefinitionId": _DEF_PREFIX + slug,
                "parameters": {k: {"value": v} for k, v in params.items()},
                "enforcementMode": "Default", "nonComplianceMessage": message}}


PLATFORM_ASSIGNMENTS = [
    _platform("dojo-allowed-locations", "Allowed locations", {"listOfAllowedLocations": list(ALLOWED_LOCATIONS)},
              "Use one of the allowed Canadian regions."),
    *(_platform(f"dojo-require-tag-{t}", f"Require tag '{t}'", {}, f"Add the required tag '{t}'.")
      for t in REQUIRED_TAGS),
    _platform("dojo-allowed-images", "Allowed container images", {"listOfAllowedImages": list(ALLOWED_IMAGES)},
              "Use an approved image."),
    _platform("dojo-max-cpu", "Maximum container CPU", {"maxCpu": MAX_CPU}, "Request less CPU."),
    _platform("dojo-max-memory", "Maximum container memory", {"maxMemoryGB": MAX_MEMORY_GB},
              "Request less memory."),
    _platform("dojo-allowed-ports", "Allowed container ports", {"listOfAllowedPorts": list(ALLOWED_PORTS)},
              "Expose only allowed ports."),
    _platform("dojo-max-env-vars", "Maximum environment variables", {"maxEnvVars": MAX_ENV_VARS},
              "Use fewer environment variables."),
]
_PLATFORM = {a["name"][len("platform-"):]: a for a in PLATFORM_ASSIGNMENTS}


def builtin_lookup(definition_id):
    return BUILTIN_DEFINITIONS.get(definition_id)


def _ports(props, cp):
    ports = [p.get("port") for p in (cp.get("ports") or [])]
    return ports + [p.get("port") for p in ((props.get("ipAddress") or {}).get("ports") or [])]


def _legacy_error(slug, name, resource, v):
    """Turns a built-in violation into the PolicyError the hand-written checks always raised."""
    props = resource.get("properties") or {}
    cp = (props["containers"][0].get("properties") or {}) if props.get("containers") else {}
    if slug == "dojo-allowed-locations":
        return _disallowed(name, v.assignmentDisplayName,
                           f"Location '{resource.get('location')}' is not allowed; use one of: "
                           f"{', '.join(ALLOWED_LOCATIONS)}.")
    if slug.startswith("dojo-require-tag-"):
        return _disallowed(name, v.assignmentDisplayName,
                           f"The resource is missing the required tag '{slug[len('dojo-require-tag-'):]}'.")
    if slug == "dojo-allowed-images":
        return PolicyError(400, "InvalidImage", f"Image '{cp.get('image', '')}' is not in the approved image "
                           f"list: {', '.join(ALLOWED_IMAGES)}.", target=name)
    if slug in ("dojo-max-cpu", "dojo-max-memory"):
        req = (cp.get("resources") or {}).get("requests") or {}
        return PolicyError(400, "InvalidResourceRequest",
                           f"Requested {float(req.get('cpu', 0) or 0)} vCPU / "
                           f"{float(req.get('memoryInGB', 0) or 0)} GB exceeds the per-container limit of "
                           f"{MAX_CPU} vCPU / {MAX_MEMORY_GB} GB.", target=name)
    if slug == "dojo-allowed-ports":
        port = next(p for p in _ports(props, cp) if p not in ALLOWED_PORTS)
        return PolicyError(400, "InvalidRequestContent", f"Port {port} is not allowed; the hello image serves "
                           f"on {', '.join(map(str, ALLOWED_PORTS))}.", target=name)
    return PolicyError(400, "InvalidRequestContent",
                       f"At most {MAX_ENV_VARS} environment variables are allowed.", target=name)


def _enforce(slug, resource):
    out = engine.evaluate_write(resource, [_PLATFORM[slug]], builtin_lookup)
    if out.denied:
        raise _legacy_error(slug, resource["name"], resource, out.denied[0])


def check_with_assignments(resource, student_assignments, lookup, exemptions=(), now=None):
    """Built-in platform assignments first, then the student's. Returns the engine Outcome (built-in denials
    short-circuit); the caller decides how to refuse. Student modify/append edits apply to outcome.resource."""
    def both(rid):
        return builtin_lookup(rid) or lookup(rid)
    base = engine.evaluate_write(resource, PLATFORM_ASSIGNMENTS, both, (), now)
    if base.denied:
        return base
    out = engine.evaluate_write(base.resource, list(student_assignments), both, exemptions, now)
    out.audited = base.audited + out.audited
    out.modified = base.modified + out.modified
    return out


def _enforce_location_and_tags(res, location=True):
    if location:
        _enforce("dojo-allowed-locations", res)
    for t in REQUIRED_TAGS:
        _enforce(f"dojo-require-tag-{t}", res)


@_shape_guarded
def check_tags(name, tags):
    _enforce_location_and_tags(engine.resource_view("containerGroup", name, None, tags, {}, "-", "-"), False)


@_shape_guarded
def check_resource_group(name, location, tags):
    if not RG_NAME.match(name or ""):
        raise PolicyError(400, "InvalidResourceGroupName",
                          f"Resource group name '{name}' is invalid: it must start with 'rg-' and "
                          "use only lowercase letters, digits and hyphens (for example "
                          "'rg-hello-dev-cac').", target=name)
    _enforce_location_and_tags(engine.resource_view("resourceGroup", name, location, tags, {}, "-", "-"))


@_shape_guarded
def check_container_group(name, location, tags, props, other_groups, dns_taken):
    """other_groups = number of the caller's OTHER container groups;
    dns_taken(label) -> True if another group already owns the label."""
    if not CG_NAME.match(name or ""):
        raise PolicyError(400, "InvalidContainerGroupName",
                          f"Container group name '{name}' is invalid: it must start with 'ci-' and "
                          "use only lowercase letters, digits and hyphens (for example "
                          "'ci-hello-dev').", target=name)
    res = engine.resource_view("containerGroup", name, location, tags, props, "-", "-")
    _enforce_location_and_tags(res)

    if other_groups >= MAX_CONTAINER_GROUPS:
        raise PolicyError(409, "QuotaExceeded",
                          f"Subscription quota reached: at most {MAX_CONTAINER_GROUPS} container "
                          "groups are allowed. Destroy one before creating another.", target=name)

    if (props.get("osType") or "Linux") != "Linux":
        raise PolicyError(400, "InvalidRequestContent", "Only osType 'Linux' is supported.", target=name)

    containers = props.get("containers") or []
    if len(containers) != 1:
        raise PolicyError(400, "InvalidRequestContent",
                          "A container group must contain exactly one container in this environment.",
                          target=name)
    c = containers[0]
    cp = c.get("properties") or {}

    _enforce("dojo-allowed-images", res)

    if cp.get("command"):
        raise PolicyError(400, "InvalidRequestContent",
                          "Overriding the container command is not allowed.", target=name)

    req = (cp.get("resources") or {}).get("requests") or {}
    cpu, mem = float(req.get("cpu", 0) or 0), float(req.get("memoryInGB", 0) or 0)
    if not (math.isfinite(cpu) and math.isfinite(mem)):  # json.loads accepts NaN and Infinity
        raise PolicyError(400, "InvalidRequestContent",
                          "Container resource requests (cpu and memory) must be finite numbers.", target=name)
    if cpu <= 0 or mem <= 0:
        raise PolicyError(400, "InvalidRequestContent",
                          "Container resource requests (cpu and memory) are required.", target=name)
    _enforce("dojo-max-cpu", res)
    _enforce("dojo-max-memory", res)
    if cpu < MIN_CPU or mem < MIN_MEMORY_GB:
        raise PolicyError(400, "InvalidResourceRequest",
                          f"Requested {cpu} vCPU / {mem} GB is below the per-container minimum of "
                          f"{MIN_CPU} vCPU / {MIN_MEMORY_GB} GB.", target=name)

    ports = [p.get("port") for p in (cp.get("ports") or [])]
    ports += [p.get("port") for p in ((props.get("ipAddress") or {}).get("ports") or [])]
    if not ports:
        raise PolicyError(400, "InvalidRequestContent",
                          "The container must expose a port (this environment allows port 80).",
                          target=name)
    _enforce("dojo-allowed-ports", res)

    env = cp.get("environmentVariables") or []
    _enforce("dojo-max-env-vars", res)
    for item in env:
        var = item.get("name", "")
        value = item.get("value", item.get("secureValue", "")) or ""
        if not ENV_NAME.match(var) or var in RESERVED_ENV or var.startswith("LD_"):
            raise PolicyError(400, "InvalidRequestContent",
                              f"Environment variable name '{var}' is not allowed.", target=name)
        if len(str(value)) > 256 or "\x00" in str(value):
            raise PolicyError(400, "InvalidRequestContent",
                              f"Environment variable '{var}' has an invalid value (max 256 chars).",
                              target=name)

    label = (props.get("ipAddress") or {}).get("dnsNameLabel")
    if label:
        if not DNS_LABEL.match(label):
            raise PolicyError(400, "InvalidDnsNameLabel",
                              f"DNS name label '{label}' is invalid (3-41 chars: lowercase letters, "
                              "digits, hyphens; must start with a letter).", target=name)
        if dns_taken(label):
            raise PolicyError(409, "DnsNameLabelInUse",
                              f"The DNS name label '{label}' is already in use. Labels are unique "
                              "across the class - include your username.", target=name)
    else:
        raise PolicyError(400, "InvalidRequestContent",
                          "A dns_name_label is required so your site gets an address.", target=name)
