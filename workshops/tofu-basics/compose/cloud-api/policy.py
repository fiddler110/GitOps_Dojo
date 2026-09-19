"""Dojo Cloud's "Azure Policy": rules every request is checked against.

Each rule is a teaching moment (PLAN.md §6.3). A violation becomes an
ARM-shaped error the student has to read and fix in their HCL. Pure functions,
no I/O, so they are unit-tested in test_policy.py.
"""
import re

# Canadian regions only (a data-residency style policy); the default is the first.
ALLOWED_LOCATIONS = ("canadacentral", "canadaeast")
ALLOWED_IMAGES = ("dojo/hello:1.0", "dojo/hello:2.0")
REQUIRED_TAGS = ("owner", "env")
MAX_CPU = 0.25
MAX_MEMORY_GB = 0.125
MAX_CONTAINER_GROUPS = 2
ALLOWED_PORTS = (80,)
MAX_ENV_VARS = 10
RG_NAME = re.compile(r"^rg-[a-z0-9][a-z0-9-]{1,56}$")
CG_NAME = re.compile(r"^ci-[a-z0-9][a-z0-9-]{1,56}$")
DNS_LABEL = re.compile(r"^[a-z][a-z0-9-]{2,40}$")
ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
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


def _disallowed(name, policy, detail):
    return PolicyError(
        403, "RequestDisallowedByPolicy",
        f"Resource '{name}' was disallowed by policy. Policy: '{policy}'. {detail}",
        target=name, policy=policy)


def _check_location(name, location):
    if location not in ALLOWED_LOCATIONS:
        raise _disallowed(name, "Allowed locations",
                          f"Location '{location}' is not allowed; use one of: "
                          f"{', '.join(ALLOWED_LOCATIONS)}.")


def check_tags(name, tags):
    tags = tags or {}
    for tag in REQUIRED_TAGS:
        if not str(tags.get(tag, "")).strip():
            raise _disallowed(name, f"Require tag '{tag}'",
                              f"The resource is missing the required tag '{tag}'.")


def check_resource_group(name, location, tags):
    if not RG_NAME.match(name or ""):
        raise PolicyError(400, "InvalidResourceGroupName",
                          f"Resource group name '{name}' is invalid: it must start with 'rg-' and "
                          "use only lowercase letters, digits and hyphens (for example "
                          "'rg-hello-dev-uks').", target=name)
    _check_location(name, location)
    check_tags(name, tags)


def check_container_group(name, location, tags, props, other_groups, dns_taken):
    """other_groups = number of the caller's OTHER container groups;
    dns_taken(label) -> True if another group already owns the label."""
    if not CG_NAME.match(name or ""):
        raise PolicyError(400, "InvalidContainerGroupName",
                          f"Container group name '{name}' is invalid: it must start with 'ci-' and "
                          "use only lowercase letters, digits and hyphens (for example "
                          "'ci-hello-dev').", target=name)
    _check_location(name, location)
    check_tags(name, tags)

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

    image = cp.get("image", "")
    if image not in ALLOWED_IMAGES:
        raise PolicyError(400, "InvalidImage",
                          f"Image '{image}' is not in the approved image list: "
                          f"{', '.join(ALLOWED_IMAGES)}.", target=name)

    if cp.get("command"):
        raise PolicyError(400, "InvalidRequestContent",
                          "Overriding the container command is not allowed.", target=name)

    req = (cp.get("resources") or {}).get("requests") or {}
    cpu, mem = float(req.get("cpu", 0) or 0), float(req.get("memoryInGB", 0) or 0)
    if cpu <= 0 or mem <= 0:
        raise PolicyError(400, "InvalidRequestContent",
                          "Container resource requests (cpu and memory) are required.", target=name)
    if cpu > MAX_CPU or mem > MAX_MEMORY_GB:
        raise PolicyError(400, "InvalidResourceRequest",
                          f"Requested {cpu} vCPU / {mem} GB exceeds the per-container limit of "
                          f"{MAX_CPU} vCPU / {MAX_MEMORY_GB} GB.", target=name)

    ports = [p.get("port") for p in (cp.get("ports") or [])]
    ports += [p.get("port") for p in ((props.get("ipAddress") or {}).get("ports") or [])]
    if not ports:
        raise PolicyError(400, "InvalidRequestContent",
                          "The container must expose a port (this environment allows port 80).",
                          target=name)
    for port in ports:
        if port not in ALLOWED_PORTS:
            raise PolicyError(400, "InvalidRequestContent",
                              f"Port {port} is not allowed; the hello image serves on "
                              f"{', '.join(map(str, ALLOWED_PORTS))}.", target=name)

    env = cp.get("environmentVariables") or []
    if len(env) > MAX_ENV_VARS:
        raise PolicyError(400, "InvalidRequestContent",
                          f"At most {MAX_ENV_VARS} environment variables are allowed.", target=name)
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
