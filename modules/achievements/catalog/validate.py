#!/usr/bin/env python3
"""Check one workshop's achievement catalog. run.sh calls this at start when
ACHIEVEMENTS_ENABLED=1 (in the allocator image, workshop folder mounted read-only):

    python3 -B validate.py <workshop dir>

Prints every error and exits 1 (the run stops), or a one-line summary and exits 0.
Warnings (an item with no `match` yet, a challenge with no structured `verify`) are counted,
and listed with --verbose.
"""

import glob
import json
import os
import sys

import catalog as cat

SHARED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shared.json")


def known_verbs():
    """Verifier verbs the achievements module declares: its own `achievements/verifiers.json` and
    every backend plug-in's `plugins/*/verifiers.json` (this script sits in the module's catalog/
    folder, and run.sh mounts the whole module). None when neither is found."""
    here = os.path.dirname(os.path.abspath(__file__))
    modules = os.path.normpath(os.path.join(here, "..", ".."))
    specs = sorted(glob.glob(os.path.join(modules, "*", "achievements", "verifiers.json")))
    specs += sorted(glob.glob(os.path.join(here, "..", "achievements", "verifiers.json")))
    specs += sorted(glob.glob(os.path.join(here, "..", "plugins", "*", "verifiers.json")))
    found = None
    for spec in dict.fromkeys(os.path.normpath(s) for s in specs):
        try:
            with open(spec) as f:
                verbs = json.load(f).get("verbs", {})
        except (OSError, ValueError):
            continue
        found = (found or set()) | set(verbs)
    return found


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        c, warnings = cat.load(args[0], SHARED, known_verbs=known_verbs())
    except cat.CatalogError as exc:
        for problem in exc.problems:
            print(f"achievements: ERROR {problem}", file=sys.stderr)
        return 1
    if "--verbose" in argv:
        for w in warnings:
            print(f"achievements: warning: {w}", file=sys.stderr)
    core = len(cat.core_milestones(c))
    print(f"achievements: {c['workshop']}: {len(cat.milestones(c))} milestones ({core} core), "
          f"{len(c['funny'])} funny, {len(c['challenges'])} challenges, 1 capstone; {len(warnings)} warnings.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
