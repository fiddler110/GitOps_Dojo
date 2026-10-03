"""cloud verifier verbs (see verifiers.json). Stdlib only. Every verb is `fn(api, args, ctx) -> (passed, message)`.
`api` is the Forgejo client the runner passes to every verb; these ignore it.

Isolation: the account whose subscription is read is always ctx["user"], the student who asked for the check.
No argument can name another account, and the portal API answers `scope=mine` with that account's own
subscription only; the policy verb reads that account's own Policy blade and activity log the same way."""
import datetime
import json
import os
import urllib.error
import urllib.request


class Unavailable(Exception):
    """The Dojo Cloud API couldn't be read (try again)."""


def _overview(user):
    return _read(user, "overview?scope=mine")


def _policy(user):
    """The student's own Policy blade (policy_api.portal_section): assignments with compliance, exemptions,
    custom definitions and sets."""
    return _read(user, "policy")


def _activity(user):
    """The student's own Dojo Cloud activity log, newest first (the last 500 entries at most)."""
    return _read(user, "activity?limit=500")


def _read(user, what):
    base, token = os.environ.get("CLOUD_API_URL", ""), os.environ.get("CLOUD_CHECK_TOKEN", "")
    if not base or not token:
        raise Unavailable("no CLOUD_API_URL or CLOUD_CHECK_TOKEN set")
    req = urllib.request.Request(f"{base.rstrip('/')}/cloud/api/{what}",
                                 headers={"X-Check-Token": token, "X-Auth-User": user})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise Unavailable(f"the Dojo Cloud API answered {e.code}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise Unavailable(f"the Dojo Cloud API isn't reachable ({e.__class__.__name__})")


def _not_mine(args, ctx):
    """`account` (optional, written "{user}" in a catalog) only states whose subscription is read: it must be the
    checking student. It never selects another account."""
    return "account" in args and args["account"] != ctx["user"]


def cloud_containers(api, args, ctx):
    if _not_mine(args, ctx):
        return False, "this check reads only your own subscription"
    doc = _overview(ctx["user"])
    want_tags = {str(k): str(v) for k, v in (args.get("tags") or {}).items()}
    state = args.get("state", "Running")
    mine = [c for c in (doc.get("containerGroups") or [])
            if c.get("isMine", True)
            and all((c.get("tags") or {}).get(k) == v for k, v in want_tags.items())
            and (state == "any" or c.get("state") == state)]
    prefix, locations = args.get("name_prefix"), args.get("locations")
    for c in mine:
        label = c.get("dnsLabel") or ""
        if prefix and not label.startswith(prefix):
            return False, f"the site name {label} should start with {prefix}"
        if locations and c.get("location") not in locations:
            return False, f"{label} runs in {c.get('location')}, which policy doesn't allow"
        for key in args.get("require_tags") or []:
            if not (c.get("tags") or {}).get(key):
                return False, f"{label} has no {key} tag"
    labels = {c.get("dnsLabel") for c in mine}
    for want in args.get("labels") or []:
        if want not in labels:
            return False, f"no {state if state != 'any' else ''} site named {want} yet".replace("  ", " ")
    low, high = args.get("min", 1), args.get("max")
    if len(mine) < low:
        return False, f"found {len(mine)} of the {low} site(s) needed (tagged {', '.join(f'{k}={v}' for k, v in want_tags.items()) or 'any'}, {state.lower()})"
    if high is not None and len(mine) > high:
        return False, f"found {len(mine)} site(s), at most {high} expected"
    return True, "ok"


# ---------------------------------------------------------------- Dojo Cloud Policy

POLICY_KINDS = {"assignment": "assignments", "definition": "definitions", "set": "sets", "exemption": "exemptions"}


def _low(v):
    return str(v or "").lower()


def _parse_time(text):
    try:
        return datetime.datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None


def _rule_of(obj, doc):
    """The rule JSON (as text) of a definition or set, or of the definition or set an assignment points at."""
    if "policyDefinitionId" in obj:
        want = _low(obj.get("policyDefinitionId"))
        obj = next((d for d in (doc.get("definitions") or []) + (doc.get("sets") or []) if _low(d.get("id")) == want),
                   None)
        if obj is None:
            return "", {}
    return json.dumps(obj.get("rule"), sort_keys=True), obj.get("parameters") or {}


def _has_refused(a, log):
    """Has the student's own assignment `a` refused a write? cloud-api counts refusals per assignment (`refusals`);
    an older cloud-api without the count is read from the activity log (`log()`), which is capped class-wide."""
    if "refusals" in a:
        return (a.get("refusals") or 0) > 0
    return _refused_by(str(a.get("name") or ""), log())


def _refused_by(name, events):
    """Does the student's activity log (`events`) hold a write refused by their own assignment `name`?"""
    marker = f"assignment '{name.lower()}'"
    for e in events:
        msg = _low(e.get("message"))
        if e.get("status") == "Failed" and "requestdisallowedbypolicy" in msg and marker in msg:
            return True
    return False


def _exempted(a, doc, want, now):
    for e in doc.get("exemptions") or []:
        if _low(e.get("policyAssignmentId")) != _low(a.get("id")) or e.get("expired"):
            continue
        if want.get("category") and _low(e.get("category")) != _low(want["category"]):
            continue
        days = want.get("expires_within_days")
        if days is not None:
            t = _parse_time(e.get("expiresOn")) if e.get("expiresOn") else None
            if t is None or t.tzinfo is None or (t - now).total_seconds() > float(days) * 86400:
                continue
        return True
    return False


def cloud_policy(api, args, ctx):
    """See verifiers.json. Narrows the student's own policy objects of one kind by every filter given, in
    order, and says which filter left too few."""
    if _not_mine(args, ctx):
        return False, "this check reads only your own subscription"
    kind = args.get("kind", "assignment")
    if kind not in POLICY_KINDS:
        return False, f"unknown policy kind {kind}"
    user = ctx["user"]
    doc = _policy(user) or {}
    now = datetime.datetime.now(datetime.timezone.utc)
    low, high = args.get("min", 1), args.get("max")
    found = list(doc.get(POLICY_KINDS[kind]) or [])
    label = {"assignment": "policy assignment", "definition": "policy definition", "set": "policy set",
             "exemption": "policy exemption"}[kind]

    seen = []

    def log():
        if not seen:
            seen.append((_activity(user) or {}).get("events") or [])
        return seen[0]

    def rule_ok(o):
        text, _ = _rule_of(o, doc)
        return bool(text) and all(_low(t) in text.lower() for t in args["rule_text"])

    def params_ok(o):
        _, params = _rule_of(o, doc)
        names = {_low(k) for k in params}
        return all(_low(p) in names for p in args["parameters"])

    def bad_resource(o):
        want = _low(args["noncompliant_resource"])
        return any(_low(r.get("name")) == want for r in o.get("resources") or [])

    def not_expiring_late(o):
        t = _parse_time(o.get("expiresOn")) if o.get("expiresOn") else None
        return t is not None and t.tzinfo is not None and (t - now).total_seconds() <= float(
            args["expires_within_days"]) * 86400

    filters = [
        ("name", lambda o: _low(o.get("name")) == _low(args["name"]), f"named {args.get('name')}"),
        ("name_prefix", lambda o: _low(o.get("name")).startswith(_low(args["name_prefix"])),
         f"with a name starting {args.get('name_prefix')}"),
        ("display_name", lambda o: _low(o.get("displayName")) == _low(args["display_name"]),
         f"called \"{args.get('display_name')}\""),
        ("scope_suffix", lambda o: _low(o.get("scope")).rstrip("/").endswith(_low(args["scope_suffix"]).rstrip("/")),
         f"at the scope {args.get('scope_suffix')}"),
        ("enforcement", lambda o: _low(o.get("enforcementMode")) == _low(args["enforcement"]),
         f"with enforcement mode {args.get('enforcement')}"),
        ("effect", lambda o: _low(o.get("effect")) == _low(args["effect"]), f"with the effect {args.get('effect')}"),
        ("is_set", lambda o: bool(o.get("isSet")) == bool(args["is_set"]),
         "that assigns a policy set" if args.get("is_set") else "that assigns a single definition"),
        ("rule_text", rule_ok, "whose rule mentions " + ", ".join(args.get("rule_text") or [])),
        ("parameters", params_ok, "with the parameter(s) " + ", ".join(args.get("parameters") or [])),
        ("category", lambda o: _low(o.get("category")) == _low(args["category"]),
         f"in the category {args.get('category')}"),
        ("expires_within_days", not_expiring_late, f"expiring within {args.get('expires_within_days')} days"),
        ("active", lambda o: not o.get("expired"), "that has not expired"),
        ("noncompliant_min", lambda o: int(o.get("nonCompliant") or 0) >= int(args["noncompliant_min"]),
         f"with at least {args.get('noncompliant_min')} non-compliant resource(s)"),
        ("noncompliant_max", lambda o: int(o.get("nonCompliant") or 0) <= int(args["noncompliant_max"]),
         f"with at most {args.get('noncompliant_max')} non-compliant resource(s)"),
        ("noncompliant_resource", bad_resource, f"listing {args.get('noncompliant_resource')} as non-compliant"),
        ("exempt_min", lambda o: int(o.get("exempt") or 0) >= int(args["exempt_min"]),
         f"with at least {args.get('exempt_min')} exempt resource(s)"),
        ("exemption", lambda o: _exempted(o, doc, args["exemption"] if isinstance(args["exemption"], dict) else {}, now),
         "with an exemption" + (f" ({args['exemption'].get('category')})"
                                if isinstance(args.get("exemption"), dict) and args["exemption"].get("category")
                                else "")),
        ("refused", lambda o: _has_refused(o, log) == bool(args["refused"]),
         "that has refused a write of yours"),
    ]
    if kind == "exemption" and "active" not in args:
        args = dict(args, active=True)
    for key, test, words in filters:
        if key not in args:
            continue
        found = [o for o in found if test(o)]
        if len(found) < low:
            return False, f"no {label} {words} yet" if low <= 1 else f"fewer than {low} {label}s {words}"
    if args.get("same_definition"):
        groups = {}
        for o in found:
            groups.setdefault(_low(o.get("policyDefinitionId")), []).append(o)
        found = max(groups.values(), key=len) if groups else []
        if len(found) < low:
            return False, f"fewer than {low} {label}s of one and the same definition"
    if len(found) < low:
        return False, f"found {len(found)} {label}(s), {low} needed"
    if high is not None and len(found) > high:
        return False, f"found {len(found)} {label}(s), at most {high} expected"
    return True, "ok"


VERBS = {"cloud_containers": cloud_containers, "cloud_policy": cloud_policy}
