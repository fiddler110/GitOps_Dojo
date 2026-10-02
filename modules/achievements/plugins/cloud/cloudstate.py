"""cloud verifier verbs (see verifiers.json). Stdlib only. Every verb is `fn(api, args, ctx) -> (passed, message)`.
`api` is the Forgejo client the runner passes to every verb; these ignore it.

Isolation: the account whose subscription is read is always ctx["user"], the student who asked for the check.
No argument can name another account, and the portal API answers `scope=mine` with that account's own
subscription only."""
import json
import os
import urllib.error
import urllib.request


class Unavailable(Exception):
    """The Dojo Cloud API couldn't be read (try again)."""


def _overview(user):
    base, token = os.environ.get("CLOUD_API_URL", ""), os.environ.get("CLOUD_CHECK_TOKEN", "")
    if not base or not token:
        raise Unavailable("no CLOUD_API_URL or CLOUD_CHECK_TOKEN set")
    req = urllib.request.Request(f"{base.rstrip('/')}/cloud/api/overview?scope=mine",
                                 headers={"X-Check-Token": token, "X-Auth-User": user})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise Unavailable(f"the Dojo Cloud API answered {e.code}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise Unavailable(f"the Dojo Cloud API isn't reachable ({e.__class__.__name__})")


def cloud_containers(api, args, ctx):
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


VERBS = {"cloud_containers": cloud_containers}
