#!/usr/bin/env python3
# Live-check helper (N3): run from the repo root against a running stack.
"""Compare fired achievements against a pack's catalog.

Usage (repo root): python3 -B fired.py <workshop>
Reads state.json from workshop_achievements; prints, per milestone/funny/challenge item, which users have it,
then the ids nobody has.
"""
import json, os, subprocess, sys

ROOT = os.getcwd()
sys.path.insert(0, os.path.join(ROOT, "modules/achievements/catalog"))
import catalog as cat  # noqa: E402

ws = sys.argv[1]
catalog, _ = cat.load(os.path.join(ROOT, "workshops", ws),
                      os.path.join(ROOT, "modules/achievements/catalog/shared.json"))
raw = subprocess.run(["podman", "exec", "workshop_achievements", "cat", "/data/state.json"],
                     capture_output=True, text=True, check=True).stdout
state = json.loads(raw)["ledger"]
users = state["users"]

rows = []
for lab in catalog["labs"]:
    for m in lab["milestones"]:
        if cat.is_active(m):
            rows.append(("core" if m["core"] else "extra", m["id"]))
for key in ("funny", "shared"):
    v = catalog.get(key) or []
    for f in (sum(v.values(), []) if isinstance(v, dict) else v):
        if isinstance(f, dict) and cat.is_active(f):
            rows.append((key, f["id"]))
for key in ("challenges", "capstone"):
    v = catalog.get(key) or []
    for ch in (v if isinstance(v, list) else [v]):
        if isinstance(ch, dict) and ch.get("id"):
            rows.append((key, ch["id"]))
for lab in catalog["labs"]:
    for ch in lab.get("challenges", []) or []:
        rows.append(("challenge", ch["id"]))

never = []
for kind, iid in rows:
    who = sorted(u for u, rec in users.items() if iid in rec.get("unlocked", {}))
    print(f"{kind:9} {iid:24} {len(who)}  {' '.join(who)}")
    if not who:
        never.append(f"{kind}:{iid}")
print("\nusers:", " ".join(sorted(users)))
print("NEVER FIRED:", " ".join(never) or "none")
