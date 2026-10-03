"""Student reset hook for dns-api (engine `resets`, workshops/README.md "Student reset hooks").

teardown: delete every zone at or under `<user>.<parent>` and, in the zones the class shares, every rrset
named `<user>.<parent>` or under it: exactly what the student's own key may change (gate.owns), so a reset
never touches a name anyone else owns. Names the student added to a CI zone through the shared repo
(dns-as-code's `<user>-app`) stay: the next pipeline run would only put them back.
provision: put back the records the workshop seeds for every account (DNS_GATE_RESET_RECORDS).

`pdns(method, path, body)` talks to PowerDNS with the upstream key and returns (status, parsed JSON or None)."""
import urllib.parse

SERVER = "/api/v1/servers/localhost"


def parse_records(text):
    """DNS_GATE_RESET_RECORDS: whitespace-separated `name/TYPE/content`, `{user}` in the name, e.g.
    `{user}.certs.dojo.test/A/172.30.0.20 *.{user}.certs.dojo.test/A/172.30.0.20`."""
    out = []
    for item in (text or "").split():
        name, rtype, content = (item.split("/", 2) + ["", ""])[:3]
        if name.count("{user}") != 1 or not rtype.isalpha() or not content:
            raise ValueError(f"DNS_GATE_RESET_RECORDS: bad entry {item!r} (want name/TYPE/content with {{user}})")
        out.append((name.rstrip(".") + ".", rtype.upper(), content))
    return out


def _mine(name, user, parents):
    """`name` is `<user>.<parent>` or under it (parents as the gate keeps them: lower case, one trailing dot)."""
    name = name.rstrip(".").lower() + "."
    return any(name == f"{user}.{p}" or name.endswith(f".{user}.{p}") for p in parents)


def _zone_url(zone):
    return f"{SERVER}/zones/{urllib.parse.quote(zone, safe='')}"


def teardown(pdns, user, cfg):
    status, zones = pdns("GET", f"{SERVER}/zones", None)
    if status != 200 or not isinstance(zones, list):
        raise RuntimeError(f"PowerDNS zone list failed ({status})")
    gone, cleared = 0, 0
    for z in zones:
        name = z.get("name", "")
        if _mine(name, user, cfg.user_parents):
            status, _ = pdns("DELETE", _zone_url(name), None)
            if status not in (204, 404):
                raise RuntimeError(f"deleting zone {name} failed ({status})")
            gone += 1
        elif name.lower() in cfg.shared_zones:
            status, doc = pdns("GET", _zone_url(name), None)
            if status != 200:
                raise RuntimeError(f"reading zone {name} failed ({status})")
            dead = [{"name": r["name"], "type": r["type"], "changetype": "DELETE"}
                    for r in (doc or {}).get("rrsets", []) if _mine(r.get("name", ""), user, cfg.user_parents)]
            if dead:
                status, _ = pdns("PATCH", _zone_url(name), {"rrsets": dead})
                if status not in (200, 204):
                    raise RuntimeError(f"clearing {user}'s names in {name} failed ({status})")
                cleared += len(dead)
    return f"{gone} zone(s) deleted, {cleared} record set(s) cleared"


def provision(pdns, user, cfg):
    by_zone = {}
    for name, rtype, content in cfg.reset_records:
        fqdn = name.replace("{user}", user)
        zone = next((z for z in sorted(cfg.shared_zones, key=len, reverse=True)
                     if fqdn.lower().endswith("." + z)), None)
        if zone is None:
            raise RuntimeError(f"{fqdn} is in no shared zone")
        by_zone.setdefault(zone, {}).setdefault((fqdn, rtype), []).append(content)
    for zone, sets in by_zone.items():
        rrsets = [{"name": n, "type": t, "ttl": 60, "changetype": "REPLACE",
                   "records": [{"content": c, "disabled": False} for c in cs]} for (n, t), cs in sets.items()]
        status, _ = pdns("PATCH", _zone_url(zone), {"rrsets": rrsets})
        if status not in (200, 204):
            raise RuntimeError(f"re-seeding {zone} failed ({status})")
    n = sum(len(s) for s in by_zone.values())
    return f"{n} seeded record set(s) back" if n else "nothing to seed"


def run(pdns, user, phase, cfg):
    return (teardown if phase == "teardown" else provision)(pdns, user, cfg)

