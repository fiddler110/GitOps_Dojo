"""Achievement catalog: load a workshop's modular catalog and validate it.

Layout (see ROADMAP.md, "Catalog layout"):

    workshops/<name>/achievements/
        catalog.json        workshop id, title, intro, lab list, challenge order
        labs/<lab>.json     {"milestones": [item, ...]}
        funny.json          {"unlocks": [item, ...]}
        challenges/<id>.json
        capstone.json
    modules/achievements/catalog/shared.json    cheating tiers, cross-workshop unlocks

Stdlib only, no I/O beyond reading those files. `load` raises CatalogError with every
problem it finds, so a bad catalog stops the run with one readable message; warnings are
returned alongside the catalog.
"""

import json
import os
import re

KINDS = ("milestone", "funny", "challenge", "capstone")
DEFAULT_POINTS = {"milestone": 10, "funny": 5, "challenge": 100, "capstone": 300}

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
LAB_RE = re.compile(r"^lab[0-9]+$")
CHALLENGE_RE = re.compile(r"^c[0-9]+$")

# Fields each JSON object may carry. Anything else is an error, so a typo is caught
# instead of silently ignored.
ITEM_FIELDS = {"id", "title", "joke", "points", "core", "when", "match", "note", "retired"}
CHALLENGE_FIELDS = {
    "id", "title", "after", "space", "goal", "constraints", "seed", "verify_text", "verify",
    "hints", "answer", "isolation", "facilitator", "points", "badge_tier", "retired",
}
CATALOG_FIELDS = {"workshop", "title", "intro", "challenges_intro", "labs", "badge"}
LAB_FIELDS = {"id", "title"}
MATCH_SOURCES = ("shell", "forgejo", "dns", "ca", "cloud", "bao", "verify", "lab")


class CatalogError(Exception):
    """A catalog that can't be used. `problems` lists every error found."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("\n".join(self.problems))


def _read(path, problems):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        problems.append(f"{path}: missing")
    except (OSError, ValueError) as exc:
        problems.append(f"{path}: {exc}")
    return None


def points_of(item, kind):
    """An item's points: its own value, else the kind's default."""
    value = item.get("points")
    return DEFAULT_POINTS[kind] if value is None else value


def _check_fields(obj, allowed, where, problems):
    for key in sorted(set(obj) - allowed):
        problems.append(f"{where}: unknown field '{key}'")


def _check_item(item, kind, where, ids, problems, warnings, sources):
    if not isinstance(item, dict):
        problems.append(f"{where}: not an object")
        return
    _check_fields(item, ITEM_FIELDS, where, problems)
    iid = item.get("id")
    if not isinstance(iid, str) or not ID_RE.match(iid):
        problems.append(f"{where}: id '{iid}' must be lowercase letters, digits and '-'")
        return
    where = f"{where} {iid}"
    if iid in ids:
        problems.append(f"{where}: duplicate id (also in {ids[iid]})")
    ids[iid] = where
    for field in ("title", "joke", "when"):
        if not isinstance(item.get(field), str) or not item[field].strip():
            problems.append(f"{where}: '{field}' is required")
    pts = item.get("points")
    if pts is not None and (not isinstance(pts, int) or isinstance(pts, bool) or pts > 1000 or pts < -100):
        problems.append(f"{where}: points must be a whole number from -100 to 1000")
    if "core" in item and kind != "milestone":
        problems.append(f"{where}: 'core' only applies to milestones")
    if kind == "milestone" and not isinstance(item.get("core"), bool):
        problems.append(f"{where}: milestones need 'core' (true or false)")
    match = item.get("match")
    if match is None or match == {}:
        if not item.get("retired"):
            warnings.append(f"{where}: no 'match' yet, so it never fires")
        return
    if not isinstance(match, dict) or match.get("source") not in MATCH_SOURCES:
        problems.append(f"{where}: match.source must be one of {', '.join(MATCH_SOURCES)}")
    else:
        sources.add(match["source"])


def _check_challenge(ch, kind, where, ids, problems, warnings):
    if not isinstance(ch, dict):
        problems.append(f"{where}: not an object")
        return
    _check_fields(ch, CHALLENGE_FIELDS, where, problems)
    cid = ch.get("id")
    good = cid == "capstone" if kind == "capstone" else isinstance(cid, str) and bool(CHALLENGE_RE.match(cid))
    if not good:
        problems.append(f"{where}: id '{cid}' must be {'capstone' if kind == 'capstone' else 'c1, c2, ...'}")
        return
    where = f"{where} {cid}"
    if cid in ids:
        problems.append(f"{where}: duplicate id (also in {ids[cid]})")
    ids[cid] = where
    for field in ("title", "goal", "verify_text"):
        if not isinstance(ch.get(field), str) or not ch[field].strip():
            problems.append(f"{where}: '{field}' is required")
    # Isolation rules (A20): a challenge works in one per-student space and needs no peer.
    space = ch.get("space")
    if not isinstance(space, str) or "{user}" not in space:
        problems.append(f"{where}: 'space' must name the student's own space and contain {{user}}")
    hints = ch.get("hints")
    if not isinstance(hints, list) or len(hints) != 2 or not all(isinstance(h, str) and h.strip() for h in hints):
        problems.append(f"{where}: 'hints' must be exactly two non-empty strings")
    if not isinstance(ch.get("answer"), str) or not ch["answer"].strip():
        warnings.append(f"{where}: no 'answer' yet (needed before reveal works)")
    if not isinstance(ch.get("seed"), str) or not ch["seed"].strip():
        warnings.append(f"{where}: no 'seed' text")
    if not isinstance(ch.get("isolation"), str) or not ch["isolation"].strip():
        warnings.append(f"{where}: no 'isolation' note (how it avoids other students)")
    if "facilitator" in ch and not isinstance(ch["facilitator"], bool):
        problems.append(f"{where}: 'facilitator' must be true or false")
    verify = ch.get("verify")
    if verify is None:
        warnings.append(f"{where}: no structured 'verify' yet, so it can't be checked")
    else:
        if not isinstance(verify, list) or not verify:
            problems.append(f"{where}: 'verify' must be a non-empty list of assertions")
        else:
            for i, a in enumerate(verify, 1):
                if not isinstance(a, dict) or not isinstance(a.get("verb"), str):
                    problems.append(f"{where}: verify[{i}] needs a 'verb'")
                elif "{user}" not in json.dumps(a):
                    problems.append(f"{where}: verify[{i}] never mentions {{user}}, so it reads shared state")
    if kind == "capstone" and ch.get("badge_tier") != "capstone":
        problems.append(f"{where}: capstone needs badge_tier 'capstone'")


def load(workshop_dir, shared_path=None, known_verbs=None):
    """Load and validate one workshop's catalog.

    Returns (catalog, warnings). Raises CatalogError on any error. `known_verbs`, when
    given, is the set of verifier verbs the run's modules provide; a challenge that uses
    another verb is an error.
    """
    base = os.path.join(workshop_dir, "achievements")
    problems, warnings = [], []
    ids = {}
    sources = set()

    meta = _read(os.path.join(base, "catalog.json"), problems)
    if problems:
        raise CatalogError(problems)
    if not isinstance(meta, dict):
        raise CatalogError([f"{base}/catalog.json: not an object"])
    _check_fields(meta, CATALOG_FIELDS, "catalog.json", problems)
    for field in ("workshop", "title"):
        if not isinstance(meta.get(field), str) or not meta[field].strip():
            problems.append(f"catalog.json: '{field}' is required")
    if meta.get("workshop") and meta["workshop"] != os.path.basename(os.path.normpath(workshop_dir)):
        problems.append("catalog.json: 'workshop' must match the workshop's folder name")

    shared = {"cheats": [], "unlocks": []}
    if shared_path:
        loaded = _read(shared_path, problems)
        if isinstance(loaded, dict):
            shared = loaded
    _check_fields(shared, {"cheats", "unlocks"}, "shared.json", problems)
    for kind_key in ("cheats", "unlocks"):
        for item in shared.get(kind_key, []):
            _check_item(item, "funny", f"shared.json {kind_key}", ids, problems, warnings, sources)

    labs = []
    seen_labs = set()
    for lab in meta.get("labs", []):
        if not isinstance(lab, dict):
            problems.append("catalog.json: labs entries must be objects")
            continue
        _check_fields(lab, LAB_FIELDS, "catalog.json lab", problems)
        lid = lab.get("id")
        if not isinstance(lid, str) or not LAB_RE.match(lid):
            problems.append(f"catalog.json: lab id '{lid}' must look like lab3")
            continue
        if lid in seen_labs:
            problems.append(f"catalog.json: duplicate lab {lid}")
        seen_labs.add(lid)
        data = _read(os.path.join(base, "labs", f"{lid}.json"), problems)
        milestones = []
        if isinstance(data, dict):
            _check_fields(data, {"milestones"}, f"labs/{lid}.json", problems)
            milestones = data.get("milestones", [])
            for item in milestones:
                _check_item(item, "milestone", f"labs/{lid}.json", ids, problems, warnings, sources)
        labs.append({"id": lid, "title": lab.get("title", ""), "milestones": milestones})
    # A lab file nobody lists is almost certainly a forgotten catalog.json entry.
    labs_dir = os.path.join(base, "labs")
    if os.path.isdir(labs_dir):
        for name in sorted(os.listdir(labs_dir)):
            if name.endswith(".json") and name[:-5] not in seen_labs:
                problems.append(f"labs/{name}: not listed in catalog.json")

    funny = []
    fdata = _read(os.path.join(base, "funny.json"), problems)
    if isinstance(fdata, dict):
        _check_fields(fdata, {"unlocks"}, "funny.json", problems)
        funny = fdata.get("unlocks", [])
        for item in funny:
            _check_item(item, "funny", "funny.json", ids, problems, warnings, sources)

    challenges = []
    cdir = os.path.join(base, "challenges")
    if os.path.isdir(cdir):
        for name in sorted(os.listdir(cdir), key=lambda n: (len(n), n)):
            if not name.endswith(".json"):
                continue
            ch = _read(os.path.join(cdir, name), problems)
            if ch is not None:
                _check_challenge(ch, "challenge", f"challenges/{name}", ids, problems, warnings)
                if isinstance(ch, dict) and ch.get("id") and ch["id"] != name[:-5]:
                    problems.append(f"challenges/{name}: id must match the file name")
                challenges.append(ch)
    capstone = _read(os.path.join(base, "capstone.json"), problems)
    if capstone is not None:
        _check_challenge(capstone, "capstone", "capstone.json", ids, problems, warnings)

    if known_verbs is not None:
        for ch in challenges + ([capstone] if isinstance(capstone, dict) else []):
            for a in (ch.get("verify") or []) if isinstance(ch, dict) else []:
                if isinstance(a, dict) and a.get("verb") not in known_verbs:
                    problems.append(f"challenge {ch.get('id')}: unknown verifier verb '{a.get('verb')}'")

    if problems:
        raise CatalogError(problems)
    return {
        "workshop": meta["workshop"],
        "title": meta["title"],
        "intro": meta.get("intro", ""),
        "challenges_intro": meta.get("challenges_intro", ""),
        "badge": meta.get("badge"),
        "labs": labs,
        "funny": funny,
        "challenges": challenges,
        "capstone": capstone,
        "shared": shared,
        "sources": sorted(sources),
    }, warnings


def milestones(catalog):
    """Every milestone in lab order, retired ones excluded."""
    return [m for lab in catalog["labs"] for m in lab["milestones"] if not m.get("retired")]


def core_milestones(catalog):
    return [m for m in milestones(catalog) if m["core"]]


def completion(catalog, unlocked_ids, percent=80):
    """(done, total, percent_done, complete) for a set of unlocked ids.

    Only `core` milestones count. `complete` is true at `percent` of them (rounded up, so
    80% of 33 is 27, never 26).
    """
    core = [m["id"] for m in core_milestones(catalog)]
    total = len(core)
    done = sum(1 for cid in core if cid in unlocked_ids)
    need = -(-total * percent // 100)
    pct = 100 if total == 0 else done * 100 // total
    return done, total, pct, total > 0 and done >= need
