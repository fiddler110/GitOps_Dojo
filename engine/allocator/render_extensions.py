#!/usr/bin/env python3
"""Check and render workshop/module extensions (engine/MODULES-PLAN.md §3).

A workshop pack or module declares its front door -- landing cards, /admin
tabs, gated routes, status checks -- in an extensions.json. This script
merges every manifest run.sh hands it, rejects anything unsafe or colliding,
and writes the two files the stack reads:

  <out>/gateway/extensions.caddy     imported by gateway/Caddyfile
  <out>/allocator/extensions.json    read by allocator/server.py at start

It runs once per `./run.sh <workshop>`, before anything starts, in a
throwaway allocator container (the host needs no Python). Any error stops
the start. Manifests are repo content, not student input, but they are the
only thing between a pack and the gateway config, so every value that
reaches the Caddy snippet is checked against a strict pattern and no
manifest value is ever copied into it unchecked. Gates are fixed templates
owned here; a manifest can only pick one by name.

Usage:
  render_extensions.py --in DIR --out DIR --services "svc1 svc2 ..."

DIR/*.json are read in name order (run.sh numbers them: modules first, then
the workshop). Strings may use ${NAME} for a variable the environment
provides (run.sh passes the keys of workshop.env / module.env).
"""

import argparse
import json
import os
import re
import sys

VERSION = 1

# Paths the engine already routes. The gateway's own matchers are raw
# prefixes ("/git*", "/ide*", ...) and come before the imported snippet, so
# an extension path merely *starting with* one of these would be shadowed.
# The allocator-only paths are exact, but the allocator is the catch-all,
# so an extension route there would hijack it.
ENGINE_PREFIXES = ("/slides", "/admin", "/git", "/ide", "/term")
ENGINE_EXACT = ("/", "/assign", "/forgejo-login", "/auth-check", "/auth-check-watch")

# Built-in /admin tab ids (allocator/server.py render_facilitator_workspace).
ENGINE_TAB_IDS = ("roster", "ide", "term", "forgejo", "slides")

# Icons the allocator has inline SVG for; a manifest picks one by name.
ICONS = ("code", "terminal", "git", "slides", "rocket", "cloud", "key")

GATES = ("shared", "identity", "facilitator")

ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,30}$")
PATH_RE = re.compile(r"^/[a-z][a-z0-9-]{0,40}$")
SERVICE_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,62}$")
# A same-origin link: starts with one "/", then URL-safe characters only.
# No "//" (scheme-relative), no backslash, quotes, spaces or angle brackets.
LOCAL_URL_RE = re.compile(r"^/(?!/)[A-Za-z0-9._~!$&'()*+,;=:@%/?#-]*$")
STATUS_URL_RE = re.compile(r"^https?://([a-z0-9][a-z0-9_.-]{0,62})(:[0-9]{1,5})?(/[A-Za-z0-9._~%/?=&-]*)?$")
# Host header template: DNS labels, optionally with {user} standing in for a whole label.
HOST_RE = re.compile(r"^(\{user\}|[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$")
VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

TEXT_MAX = {"label": 40, "desc": 120}

KINDS = {
    "cards": {"required": ("id", "label", "href", "icon"), "optional": ("desc",)},
    "admin_tabs": {"required": ("id", "label", "src"), "optional": ()},
    "routes": {"required": ("id", "path", "upstream", "gate"), "optional": ("strip_prefix", "host")},
    "status_checks": {"required": ("label", "url"), "optional": ()},
}


class ManifestError(Exception):
    pass


def expand(value, where):
    """${NAME} from the environment; an unset NAME is an error, not ""."""
    def sub(m):
        name = m.group(1)
        if name not in os.environ:
            raise ManifestError(f"{where}: ${{{name}}} is not set (define it in workshop.env or module.env)")
        return os.environ[name]
    return VAR_RE.sub(sub, value)


def check_text(value, field, where):
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{where}: {field} must be a non-empty string")
    if len(value) > TEXT_MAX[field]:
        raise ManifestError(f"{where}: {field} is longer than {TEXT_MAX[field]} characters")
    if any(ord(c) < 32 for c in value):
        raise ManifestError(f"{where}: {field} contains control characters")
    return value


def check_local_url(value, field, where):
    if not isinstance(value, str) or not LOCAL_URL_RE.match(value):
        raise ManifestError(f"{where}: {field} must be a same-origin path starting with one '/', got {value!r}")
    return value


def path_overlaps(a, b):
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def load_manifest(path):
    source = os.path.basename(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise ManifestError(f"{source}: not valid JSON ({e})")
    if not isinstance(data, dict):
        raise ManifestError(f"{source}: top level must be an object")
    if data.get("version") != VERSION:
        raise ManifestError(f"{source}: \"version\": {VERSION} is required")
    unknown = set(data) - set(KINDS) - {"version"}
    if unknown:
        raise ManifestError(f"{source}: unknown keys {sorted(unknown)} (allowed: version, {', '.join(KINDS)})")
    for kind in KINDS:
        items = data.get(kind, [])
        if not isinstance(items, list):
            raise ManifestError(f"{source}: {kind} must be a list")
        for i, item in enumerate(items):
            where = f"{source}: {kind}[{i}]"
            if not isinstance(item, dict):
                raise ManifestError(f"{where}: must be an object")
            spec = KINDS[kind]
            missing = [k for k in spec["required"] if k not in item]
            if missing:
                raise ManifestError(f"{where}: missing {missing}")
            extra = set(item) - set(spec["required"]) - set(spec["optional"])
            if extra:
                raise ManifestError(f"{where}: unknown fields {sorted(extra)}")
            for k, v in item.items():
                if isinstance(v, str):
                    item[k] = expand(v, where)
    return source, data


def merge(manifests, services):
    """manifests: [(source, data)] in order. Returns (normalised, warnings)."""
    out = {kind: [] for kind in KINDS}
    warnings = []
    seen_ids = {kind: {} for kind in KINDS}

    for source, data in manifests:
        for kind in KINDS:
            for i, item in enumerate(data.get(kind, [])):
                where = f"{source}: {kind}[{i}]"
                entry = {"source": source}

                if "id" in item:
                    rid = item["id"]
                    if not isinstance(rid, str) or not ID_RE.match(rid):
                        raise ManifestError(f"{where}: id must match {ID_RE.pattern}, got {rid!r}")
                    if rid in seen_ids[kind]:
                        raise ManifestError(f"{where}: id {rid!r} already used by {seen_ids[kind][rid]}")
                    if kind == "admin_tabs" and rid in ENGINE_TAB_IDS:
                        raise ManifestError(f"{where}: tab id {rid!r} is a built-in /admin tab")
                    seen_ids[kind][rid] = source
                    entry["id"] = rid

                if kind == "cards":
                    entry["label"] = check_text(item["label"], "label", where)
                    entry["desc"] = check_text(item["desc"], "desc", where) if "desc" in item else ""
                    entry["href"] = check_local_url(item["href"], "href", where)
                    if item["icon"] not in ICONS:
                        raise ManifestError(f"{where}: icon must be one of {', '.join(ICONS)}")
                    entry["icon"] = item["icon"]

                elif kind == "admin_tabs":
                    entry["label"] = check_text(item["label"], "label", where)
                    entry["src"] = check_local_url(item["src"], "src", where)

                elif kind == "routes":
                    path = item["path"]
                    if not isinstance(path, str) or not PATH_RE.match(path):
                        raise ManifestError(f"{where}: path must match {PATH_RE.pattern}, got {path!r}")
                    for p in ENGINE_PREFIXES:
                        if path.startswith(p):
                            raise ManifestError(f"{where}: path {path} collides with the engine's {p}* route")
                    if path in ENGINE_EXACT:
                        raise ManifestError(f"{where}: path {path} is served by the allocator")
                    for other in out["routes"]:
                        if path_overlaps(path, other["path"]):
                            raise ManifestError(
                                f"{where}: path {path} overlaps {other['path']} from {other['source']}")
                    upstream = item["upstream"]
                    service, sep, port = str(upstream).rpartition(":")
                    if not sep or not SERVICE_RE.match(service) or not port.isdigit() or not 0 < int(port) < 65536:
                        raise ManifestError(f"{where}: upstream must be <service>:<port>, got {upstream!r}")
                    if service not in services:
                        raise ManifestError(f"{where}: upstream service {service!r} is not in this stack "
                                            f"(services: {', '.join(sorted(services))})")
                    gate = item["gate"]
                    if gate not in GATES:
                        raise ManifestError(f"{where}: gate must be one of {', '.join(GATES)}, got {gate!r}")
                    strip = item.get("strip_prefix", False)
                    if not isinstance(strip, bool):
                        raise ManifestError(f"{where}: strip_prefix must be true or false")
                    host = item.get("host")
                    if host is not None:
                        if gate == "shared":
                            raise ManifestError(f"{where}: host needs a gate that knows the user (identity, facilitator)")
                        if not isinstance(host, str) or not HOST_RE.match(host):
                            raise ManifestError(f"{where}: host must be a DNS name, optionally with {{user}} "
                                                f"as a whole label, got {host!r}")
                    entry.update(path=path, upstream=f"{service}:{int(port)}", gate=gate, strip_prefix=strip)
                    if host is not None:
                        entry["host"] = host

                elif kind == "status_checks":
                    entry["label"] = check_text(item["label"], "label", where)
                    url = item["url"]
                    m = STATUS_URL_RE.match(url) if isinstance(url, str) else None
                    if not m:
                        raise ManifestError(f"{where}: url must be http(s)://<service>[:port]/path, got {url!r}")
                    if m.group(1) not in services:
                        raise ManifestError(f"{where}: url host {m.group(1)!r} is not a service in this stack")
                    entry["url"] = url

                out[kind].append(entry)

    tab_ids = {t["id"] for t in out["admin_tabs"]}
    for card in out["cards"]:
        if card["id"] not in tab_ids:
            warnings.append(f"{card['source']}: card {card['id']!r} has no admin tab with the same id; "
                            "the facilitator must be able to reach every student tool (CLAUDE.md)")
    return out, warnings


def caddy_for_route(r):
    """One route, from a fixed template. Every interpolated value was matched
    against a strict pattern in merge(): id, path and upstream contain only
    [a-z0-9_.:/-], so nothing here can break out of the Caddyfile syntax."""
    name = "ext_" + r["id"].replace("-", "_")
    path = r["path"]
    lines = [f"# {r['id']} ({r['gate']} gate), from {r['source']}",
             f"@{name} path {path} {path}/*",
             f"handle @{name} {{",
             # route keeps these in written order (Caddy would otherwise sort
             # request_header after forward_auth and undo the copy).
             "\troute {",
             # Never let a client supply the headers the gate hands over.
             "\t\trequest_header -X-Dojo-User",
             "\t\trequest_header -X-Dojo-Host"]
    if r["gate"] in ("identity", "facilitator"):
        lines += ["\t\tforward_auth allocator:8080 {",
                  f"\t\t\turi /auth-check?route={r['id']}",
                  "\t\t\theader_up X-Auth-User {http.auth.user.id}",
                  "\t\t\theader_up X-Gateway-Token {$GATEWAY_TOKEN}",
                  "\t\t\tcopy_headers X-Dojo-User X-Dojo-Host",
                  "\t\t}"]
    if r["strip_prefix"]:
        lines.append(f"\t\turi strip_prefix {path}")
    lines.append(f"\t\treverse_proxy {r['upstream']} {{")
    # The shared login's Basic credentials are ours, not the upstream's.
    lines.append("\t\t\theader_up -Authorization")
    if r["gate"] in ("identity", "facilitator"):
        # header_up with no +/- replaces, so the upstream only ever sees
        # what the allocator vouched for, next to the token only Caddy has.
        lines += ["\t\t\theader_up X-Auth-User {http.request.header.X-Dojo-User}",
                  "\t\t\theader_up X-Gateway-Token {$GATEWAY_TOKEN}"]
        if "host" in r:
            lines.append("\t\t\theader_up Host {http.request.header.X-Dojo-Host}")
    else:
        lines += ["\t\t\theader_up -X-Auth-User",
                  "\t\t\theader_up -X-Gateway-Token"]
    lines += ["\t\t\theader_up -X-Dojo-User",
              "\t\t\theader_up -X-Dojo-Host",
              "\t\t}",
              "\t}",
              "}"]
    return "\n".join(lines)


def render_caddy(routes):
    head = ("# Generated by engine/allocator/render_extensions.py on every ./run.sh start.\n"
            "# Do not edit: change the workshop's or module's extensions.json instead.\n")
    if not routes:
        return head + "# (no extension routes in this workshop)\n"
    return head + "\n" + "\n\n".join(caddy_for_route(r) for r in routes) + "\n"


def write_atomic(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--in", dest="in_dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--services", required=True, help="space-separated compose services of this run")
    args = ap.parse_args(argv)

    services = set(args.services.split())
    try:
        files = sorted(f for f in os.listdir(args.in_dir) if f.endswith(".json"))
        manifests = [load_manifest(os.path.join(args.in_dir, f)) for f in files]
        merged, warnings = merge(manifests, services)
    except ManifestError as e:
        print(f"extensions: ERROR {e}", file=sys.stderr)
        return 1

    for w in warnings:
        print(f"extensions: WARNING {w}", file=sys.stderr)

    write_atomic(os.path.join(args.out, "gateway", "extensions.caddy"), render_caddy(merged["routes"]))
    allocator_view = dict(merged, version=VERSION)
    write_atomic(os.path.join(args.out, "allocator", "extensions.json"),
                 json.dumps(allocator_view, indent=2) + "\n")
    counts = ", ".join(f"{len(merged[k])} {k.replace('_', ' ')}" for k in KINDS)
    print(f"extensions: {len(manifests)} manifest(s): {counts}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
