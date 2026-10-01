"""bao verifier verbs (see verifiers.json). Stdlib only. Every verb is `fn(api, args, ctx) -> (passed, message)`.
`api` is the Forgejo client the runner passes to every verb; these ignore it.

Own-space rule: the namespace is `students/<ctx user>`, built here, never taken from an argument, so a
check can only read the namespace of the student it is checking."""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./+*-]*$")
USER = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class Unavailable(Exception):
    """OpenBao couldn't be read (try again)."""


def _safe(*parts):
    for p in parts:
        if not isinstance(p, str) or not NAME.match(p) or ".." in p or "//" in p:
            raise ValueError(f"not an allowed name: {p!r}")


def _get(ns, path, listing=False):
    """GET <BAO_URL>/v1/<path> in namespace ns as the checker; the parsed `data`, or None when missing."""
    base, token = os.environ.get("BAO_URL", ""), os.environ.get("BAO_CHECK_TOKEN", "")
    if not base or not token:
        raise Unavailable("no BAO_URL / BAO_CHECK_TOKEN set")
    url = f"{base.rstrip('/')}/v1/{urllib.parse.quote(path, safe='/')}" + ("?list=true" if listing else "")
    req = urllib.request.Request(url, headers={"X-Vault-Token": token, "X-Vault-Namespace": ns})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return (json.load(r).get("data") or {})
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise Unavailable(f"OpenBao answered {e.code}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise Unavailable(f"OpenBao isn't reachable ({e.__class__.__name__})")


def _ns(ctx, args=None):
    """The checking student's own namespace. `student` (always {user} in a catalog) may be given so a
    check reads as its own namespace; anything else than the checked student is refused."""
    user = ctx.get("user")
    if not isinstance(user, str) or not USER.match(user):
        raise ValueError("no student to check")
    if args and "student" in args and args["student"] != user:
        raise ValueError("that check may only read your own namespace")
    return f"students/{user}"


# -- policy evaluation (read only, HCL subset: path "x" { capabilities = [...] }) ------------
STANZA = re.compile(r'path\s+"([^"]+)"\s*\{(.*?)\}', re.S)
CAPS = re.compile(r"capabilities\s*=\s*\[([^\]]*)\]", re.S)


def parse_policy(text):
    """[(path pattern, set of capabilities)]"""
    out = []
    for m in STANZA.finditer(text or ""):
        c = CAPS.search(m.group(2))
        caps = set(re.findall(r'"([a-z]+)"', c.group(1))) if c else set()
        out.append((m.group(1), caps))
    return out


def _matches(pattern, path):
    if pattern.endswith("*"):
        pattern, prefix = pattern[:-1], True
    else:
        prefix = False
    rx = "".join("[^/]+" if part == "+" else re.escape(part) for part in re.split(r"(\+)", pattern))
    return re.match(rx + ("" if prefix else "$"), path) is not None


def can_read(stanzas, path):
    hit = [caps for pat, caps in stanzas if _matches(pat, path)]
    if not hit or any("deny" in c for c in hit):
        return False
    return any("read" in c for c in hit)


def _judge(stanzas, args):
    for p in args.get("allow") or []:
        if not can_read(stanzas, p):
            return False, f"the policy doesn't let it read {p}"
    for p in args.get("deny") or []:
        if can_read(stanzas, p):
            return False, f"the policy lets it read {p}, which it shouldn't"
    return True, "ok"


def _policy_text(ns, name):
    doc = _get(ns, f"sys/policies/acl/{name}")
    return None if doc is None else doc.get("policy", "")


def policy_grants(api, args, ctx):
    ns, name = _ns(ctx, args), args.get("policy")
    _safe(name)
    text = _policy_text(ns, name)
    if text is None:
        return False, f"there is no policy {name} yet"
    stanzas = parse_policy(text)
    for prefix in args.get("only") or []:
        _safe(prefix)
    only = args.get("only")
    if only:
        for pat, _ in stanzas:
            if not any(pat.startswith(p) for p in only):
                return False, f"the policy names {pat}, which is wider than it needs"
    return _judge(stanzas, args)


def _role(ns, args):
    mount, role = args.get("mount"), args.get("role")
    _safe(mount, role)
    return _get(ns, f"auth/{mount}/role/{role}"), f"{mount} role {role}"


def _role_policies(doc):
    return [p for p in (doc.get("token_policies") or doc.get("policies") or []) if p != "default"]


def role_policy_grants(api, args, ctx):
    ns = _ns(ctx, args)
    doc, label = _role(ns, args)
    if doc is None:
        return False, f"there is no {label} yet"
    pols = _role_policies(doc)
    if not pols:
        return False, f"{label} has no policy attached yet"
    stanzas = []
    for name in pols:
        _safe(name)
        text = _policy_text(ns, name)
        if text is None:
            return False, f"{label} names the policy {name}, which doesn't exist"
        stanzas += parse_policy(text)
    return _judge(stanzas, args)


def auth_role(api, args, ctx):
    doc, label = _role(_ns(ctx, args), args)
    if doc is None:
        return False, f"there is no {label} yet"
    have = set(_role_policies(doc))
    for p in args.get("policies") or []:
        if p not in have:
            return False, f"{label} doesn't have the policy {p}"
    return True, "ok"


def seconds(v):
    if isinstance(v, (int, float)):
        return int(v)
    m = re.fullmatch(r"(\d+)([smh]?)", str(v).strip())
    if not m:
        return None
    return int(m.group(1)) * {"": 1, "s": 1, "m": 60, "h": 3600}[m.group(2)]


def db_role(api, args, ctx):
    role = args.get("role")
    _safe(role)
    doc = _get(_ns(ctx, args), f"database/roles/{role}")
    if doc is None:
        return False, f"there is no database role {role} yet"
    for key in ("default_ttl", "max_ttl"):
        if key in args and seconds(doc.get(key)) != seconds(args[key]):
            return False, f"{role}: {key} is {doc.get(key)}, not {args[key]}"
    return True, "ok"


def lease_exists(api, args, ctx):
    prefix = args.get("prefix")
    _safe(prefix)
    doc = _get(_ns(ctx, args), "sys/leases/lookup/" + prefix.strip("/") + "/", listing=True)
    if not doc or not doc.get("keys"):
        return False, f"no credential has been issued from {prefix} yet"
    return True, "ok"


def kv_version(api, args, ctx):
    mount, path = args.get("mount"), args.get("path")
    _safe(mount, path)
    doc = _get(_ns(ctx, args), f"{mount}/metadata/{path}")
    if doc is None:
        return False, f"there is no secret at {mount}/{path} yet"
    if int(doc.get("current_version") or 0) < int(args.get("min_version", 1)):
        return False, f"{mount}/{path} is still at version {doc.get('current_version')}"
    return True, "ok"


VERBS = {"policy_grants": policy_grants, "role_policy_grants": role_policy_grants, "auth_role": auth_role,
         "db_role": db_role, "lease_exists": lease_exists, "kv_version": kv_version}
