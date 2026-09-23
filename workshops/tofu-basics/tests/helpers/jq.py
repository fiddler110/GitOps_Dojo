#!/usr/bin/env python3
"""A tiny JSON reader for the test scripts (there is no jq on this host or in the terminal image).

JSON comes from stdin. PATH is dotted keys; a numeric part indexes a list. '.' or '' means the whole document.

    jq.py get   PATH                       the value: a plain string as-is, anything else as JSON; empty if missing
    jq.py len   PATH                       length of a list / object / string; 0 if missing
    jq.py pluck PATH FIELD                 one line per list element: element[FIELD] (skips elements without it)
    jq.py count PATH FIELD=VALUE ...       how many list elements match every condition
                                           (FIELD=VALUE is exact, FIELD^=PREFIX is "starts with")
    jq.py json  PATH                       the value as compact JSON

Always exits 0 (a missing path is an empty answer, not an error) so callers can use it inside $( ) safely; exits 2
only for a usage error or input that is not JSON.
"""
import json
import sys


def walk(doc, path):
    cur = doc
    for part in [p for p in path.split(".") if p]:
        if isinstance(cur, dict):
            if part not in cur:
                return None
            cur = cur[part]
        elif isinstance(cur, list) and part.lstrip("-").isdigit():
            i = int(part)
            if not -len(cur) <= i < len(cur):
                return None
            cur = cur[i]
        else:
            return None
    return cur


def show(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def matches(item, conditions):
    if not isinstance(item, dict):
        return False
    for cond in conditions:
        if "^=" in cond:
            field, _, want = cond.partition("^=")
            if not str(item.get(field, "")).startswith(want):
                return False
        else:
            field, _, want = cond.partition("=")
            if str(item.get(field, "")) != want:
                return False
    return True


def main(argv):
    if len(argv) < 2:
        sys.stderr.write(__doc__)
        return 2
    op, path, rest = argv[0], argv[1], argv[2:]
    try:
        doc = json.load(sys.stdin)
    except ValueError:
        sys.stderr.write("jq.py: stdin is not JSON\n")
        return 2
    value = walk(doc, path)
    if op in ("get", "json"):
        print(show(value) if op == "get" else ("" if value is None else json.dumps(value, separators=(",", ":"))))
    elif op == "len":
        print(len(value) if isinstance(value, (list, dict, str)) else 0)
    elif op == "pluck":
        for item in value if isinstance(value, list) else []:
            if isinstance(item, dict) and rest and rest[0] in item:
                print(show(item[rest[0]]))
    elif op == "count":
        print(sum(1 for item in (value if isinstance(value, list) else []) if matches(item, rest)))
    else:
        sys.stderr.write(f"jq.py: unknown operation {op!r}\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
