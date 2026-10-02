"""dns verifier verbs (see verifiers.json). Stdlib only. Every verb is `fn(api, args, ctx) -> (passed, message)`.
`api` is the Forgejo client the runner passes to every verb; these ignore it."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request


class Unavailable(Exception):
    """The DNS API couldn't be read (try again)."""


def _get(zone):
    base, key = os.environ.get("DNS_API_URL", ""), os.environ.get("DNS_READ_KEY", "")
    if not base:
        raise Unavailable("no DNS_API_URL set")
    url = f"{base.rstrip('/')}/api/v1/servers/localhost/zones/{urllib.parse.quote(zone + '.', safe='')}"
    req = urllib.request.Request(url, headers={"X-API-Key": key})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise Unavailable(f"the DNS API answered {e.code}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise Unavailable(f"the DNS API isn't reachable ({e.__class__.__name__})")


def _own(zone, ctx):
    return isinstance(zone, str) and zone.startswith(ctx["user"] + ".")


def _fqdn(name, zone):
    name = str(name).lower().rstrip(".")
    if name == "@":
        return zone + "."
    return name + "." if name.endswith(zone) else f"{name}.{zone}."


def _load(args, ctx):
    """({(fqdn, type): sorted values}, None) or (None, failure message)."""
    zone = args.get("zone")
    if not _own(zone, ctx):
        return None, "that check may only read your own zone"
    doc = _get(zone)
    if doc is None:
        return None, f"{zone} doesn't exist yet: `dnscontrol push` it first"
    out = {}
    for rr in doc.get("rrsets") or []:
        vals = sorted(r.get("content", "") for r in rr.get("records") or [] if not r.get("disabled"))
        if vals:
            out[(rr["name"].lower(), rr["type"])] = vals
    return out, None


def _want(rec):
    vals = rec.get("values") if "values" in rec else [rec.get("value")]
    return sorted(str(v) for v in vals if v is not None)


def zone_records(api, args, ctx):
    have, fail = _load(args, ctx)
    if fail:
        return False, fail
    zone = args["zone"]
    wanted = set()
    for rec in args.get("records") or []:
        key = (_fqdn(rec["name"], zone), rec["type"])
        wanted.add(key)
        if key not in have:
            return False, f"no {rec['type']} record for {rec['name']} in {zone} yet"
        if _want(rec) and have[key] != _want(rec):
            return False, f"{rec['name']} {rec['type']} is {', '.join(have[key])}, not what it should be"
    if args.get("exact"):
        for (name, typ) in have:
            if typ == "SOA" or (typ == "NS" and name == zone + "."):
                continue
            if (name, typ) not in wanted:
                return False, f"{name.rstrip('.')} ({typ}) shouldn't be in the zone"
    return True, "ok"


def zone_absent(api, args, ctx):
    have, fail = _load(args, ctx)
    if fail:
        return False, fail
    zone = args["zone"]
    for rec in args.get("records") or []:
        for (name, typ), vals in have.items():
            if name != _fqdn(rec["name"], zone) or ("type" in rec and typ != rec["type"]):
                continue
            if _want(rec) and not set(_want(rec)) & set(vals):
                continue
            return False, f"{rec['name']} is still in the zone"
    return True, "ok"


VERBS = {"zone_records": zone_records, "zone_absent": zone_absent}
