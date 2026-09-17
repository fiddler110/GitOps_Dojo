"""Parsing and building dnscontrol record lines, and resolving a record
target (name + zone) from user input. Stateless - callers pass in the list
of managed zones (dnsctl.py's ZONES) and, where relevant, the dnsconfig.js
lines to operate on; nothing here reads dnsconfig.js from disk itself."""

from __future__ import annotations

import json
import re

# A record name is either "@" (apex), "*" (wildcard), or dot-separated labels
# made of letters/digits/hyphen/underscore (each label non-empty, no leading/
# trailing hyphen requirement enforced - Cloudflare/dnscontrol will reject
# anything actually invalid at preview time regardless).
VALID_NAME_PATTERN = re.compile(r'^(\*|[A-Za-z0-9_](?:[A-Za-z0-9_-]*[A-Za-z0-9_])?)'
                                 r'(\.[A-Za-z0-9_](?:[A-Za-z0-9_-]*[A-Za-z0-9_])?)*$')

# Only actual record-type functions - deliberately excludes D(...) (the domain
# declaration itself), which would otherwise match "D(" as a one-letter type.
KNOWN_RECORD_TYPES = ("A", "AAAA", "CNAME", "MX", "TXT", "NS", "CAA", "SRV", "PTR", "ALIAS")
RECORD_LINE_PATTERN = re.compile(
    r'^\s*(' + "|".join(KNOWN_RECORD_TYPES) + r')\(\s*"((?:[^"\\]|\\.)*)"'
)
FULL_RECORD_LINE_PATTERN = re.compile(
    r'^\s*(' + "|".join(KNOWN_RECORD_TYPES) + r')\((.*)\),?\s*(//.*)?$'
)
# For these record types, only this many positional args (after name) are
# meaningful (MX: priority + value, everything else: value). Anything beyond
# that - an unrecognized modifier call, say - is preserved verbatim in
# `extras` instead of being silently absorbed into the record's value.
EXPECTED_POSITIONAL_COUNT = {"A": 1, "CNAME": 1, "TXT": 1, "MX": 2}
# Non-record lines that are expected inside a D(...) block besides records
# themselves - anything else gets flagged by classify_zone_line() below
# instead of being silently skipped.
DIRECTIVE_LINE_PATTERN = re.compile(r'^\s*(DnsProvider|DefaultTTL)\(')


def detect_zone(spec: str, zones: list[str]) -> str | None:
    """Return the zone from `zones` that `spec` is fully-qualified under, if any."""
    lower_spec = spec.strip().rstrip(".").lower()
    for z in zones:
        lz = z.lower()
        if lower_spec == lz or lower_spec.endswith("." + lz):
            return z
    return None


def parse_record_target(spec: str, zones: list[str], zone: str | None = None) -> tuple[str, str]:
    """
    Parse an input like "plex.example.com", "www.plex.example.com",
    "example.com" (apex), "*.example.com" (wildcard), or an
    already-relative name like "plex" or "www.plex", into (name, zone) -
    name is what dnscontrol expects ("@" for the apex), zone is one of `zones`.
    Case-insensitive; tolerates a trailing dot on a fully-qualified name.

    If `zone` is given, it's used directly (and validated against `zones`) -
    required for a bare relative name when more than one zone is managed,
    since e.g. "plex" alone doesn't say which zone it belongs to.
    """
    spec = spec.strip().rstrip(".")
    if not spec:
        raise ValueError("record name cannot be empty.")
    lower_spec = spec.lower()

    if zone:
        if zone not in zones:
            raise ValueError(f"'{zone}' is not a zone this project manages ({', '.join(zones)}).")
        target_zone = zone
    else:
        target_zone = detect_zone(spec, zones)
        if target_zone is None:
            if "." not in lower_spec:
                raise ValueError(
                    f"'{spec}' is a bare relative name, and this project manages more than "
                    f"one zone ({', '.join(zones)}) - pass --zone to say which one."
                )
            raise ValueError(
                f"'{spec}' doesn't match any zone this project manages ({', '.join(zones)})."
            )

    lower_zone = target_zone.lower()
    if lower_spec == lower_zone:
        name = "@"
    else:
        suffix = "." + lower_zone
        if lower_spec.endswith(suffix):
            name = spec[: -len(suffix)].lower()
            name = name or "@"
        else:
            # No zone suffix present - the caller pinned the zone via --zone,
            # so treat the whole spec as an already-relative name (e.g. "plex"
            # or the compound "www.plex").
            name = lower_spec

    if name != "@" and not VALID_NAME_PATTERN.match(name):
        raise ValueError(
            f"'{name}' doesn't look like a valid DNS label/name "
            "(letters, digits, hyphens, underscores, and dots only)."
        )
    return name, target_zone


def fqdn_for(name: str, zone: str) -> str:
    return zone if name == "@" else f"{name}.{zone}"


def split_top_level_args(argstr: str) -> list[str]:
    """Split a call's argument text on top-level commas (ignores commas
    inside quoted strings or nested parens like TTL(120))."""
    args = []
    cur = []
    depth = 0
    in_str = False
    escape = False
    for ch in argstr:
        if in_str:
            cur.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            cur.append(ch)
        elif ch == "(":
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            args.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        args.append("".join(cur).strip())
    return args


def parse_record_line_full(line: str) -> dict | None:
    """Parse one record line into its constituent fields for reporting.

    Best-effort: covers the modifiers actually used in this project
    (CF_PROXY_ON/OFF, TTL(n)) plus positional name/value(s)/MX priority.
    """
    m = FULL_RECORD_LINE_PATTERN.match(line)
    if not m:
        return None
    record_type, argstr, trailing_comment = m.group(1), m.group(2), m.group(3)
    raw_args = split_top_level_args(argstr)
    if not raw_args:
        return None

    def unquote(a: str) -> str:
        if a.startswith('"'):
            try:
                return json.loads(a)
            except (json.JSONDecodeError, ValueError):
                return a.strip('"')
        return a

    proxied = ""
    ttl = ""
    positional = []
    extras = []
    expected = EXPECTED_POSITIONAL_COUNT.get(record_type)
    for a in raw_args[1:]:
        if a == "CF_PROXY_ON":
            proxied = "yes"
        elif a == "CF_PROXY_OFF":
            proxied = "no"
        elif a.startswith("TTL(") and a.endswith(")"):
            ttl = a[len("TTL("):-1].strip()
        elif expected is None or len(positional) < expected:
            positional.append(a)
        else:
            # An unsupported modifier or extra argument this parser doesn't
            # model - keep the raw token so a rewrite can preserve it
            # instead of mashing it into the value (see ROADMAP.md TOOL-2).
            extras.append(a)

    name = unquote(raw_args[0])
    priority = ""
    if record_type == "MX" and positional:
        priority = positional.pop(0)
    value_parts = [unquote(p) for p in positional]
    value = " ".join(value_parts)

    return {
        "type": record_type,
        "name": name,
        "value": value,
        "priority": priority,
        "ttl": ttl,
        "proxied": proxied,
        "extras": extras,
        "comment": (trailing_comment or "").strip(),
        "raw": line.strip(),
    }


def classify_zone_line(line: str) -> tuple[dict | None, str | None]:
    """Classify one line inside a D(...) zone block for `lint` and `show`.

    Returns (parsed, skip_reason): `parsed` is the dict from
    parse_record_line_full() for a record line, `skip_reason` is a
    human-readable string for anything that isn't a record and isn't one of
    the expected non-record directives - callers should surface this rather
    than silently skip it (that silent skip was the TOOL-1 bug: `show`/`lint`
    used to disagree with `record list` about how many records exist).
    Both are None for a blank line, a `//` comment, or a recognised directive
    (DnsProvider/DefaultTTL) - there's nothing to report for those.
    """
    raw = line.strip()
    if not raw or raw.startswith("//") or DIRECTIVE_LINE_PATTERN.match(raw):
        return None, None
    parsed = parse_record_line_full(line)
    if parsed:
        return parsed, None
    if RECORD_LINE_PATTERN.match(line):
        return None, "looks like a record call but could not be fully parsed (unsupported modifier, multi-line call, or syntax dnsctl doesn't understand yet)"
    return None, "is not a recognised directive or record"


def find_zone_block_in_lines(lines: list[str], zone: str, source_name: str = "the file") -> tuple[int, int]:
    """Return (start, end) line indices of D("zone", ...) ... ); within arbitrary
    dnscontrol-JS source lines - shared by dnsctl.py's find_zone_block (for
    dnsconfig.js) and anything parsing a `get-zones` snapshot of live state."""
    start = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(f'D("{zone}"') or stripped.startswith(f"D('{zone}'"):
            start = i
            break
    if start is None:
        raise RuntimeError(f'Could not find D("{zone}", ...) in {source_name}.')
    for j in range(start + 1, len(lines)):
        if lines[j].strip() == ");":
            return start, j
    raise RuntimeError(f'Could not find the closing ");" for zone {zone} in {source_name}.')


def build_record_line(
    record_type: str,
    name: str,
    value: str,
    priority: int | None = None,
    proxy: bool | None = None,
    ttl: int | None = None,
    proxy_off: bool = False,
    extras: list[str] | None = None,
    comment: str = "",
) -> str:
    quoted_name = json.dumps(name)
    quoted_value = json.dumps(value)
    extras = extras or []

    def finish(parts: list[str]) -> str:
        parts = parts + extras
        line = f'\t{record_type}({", ".join(parts)}),'
        if comment:
            line += f"  {comment}" if comment.startswith("//") else f"  // {comment}"
        return line

    if record_type in ("A", "CNAME"):
        parts = [quoted_name, quoted_value]
        if proxy:
            parts.append("CF_PROXY_ON")
        elif proxy_off:
            # Preserve an explicit CF_PROXY_OFF that was already on the line
            # rather than silently normalising it away (see ROADMAP.md TOOL-2).
            parts.append("CF_PROXY_OFF")
        if ttl:
            parts.append(f"TTL({ttl})")
        return finish(parts)

    if record_type == "MX":
        if priority is None:
            raise ValueError("MX records require a priority.")
        return finish([quoted_name, str(priority), quoted_value])

    if record_type == "TXT":
        parts = [quoted_name, quoted_value]
        if ttl:
            parts.append(f"TTL({ttl})")
        return finish(parts)

    raise ValueError(
        f"The record wizard doesn't support {record_type} records yet - "
        "edit dnsconfig.js directly for this type. See docs/record-types.md."
    )
