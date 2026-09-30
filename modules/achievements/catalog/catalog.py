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
DEFAULT_POINTS = {"milestone": 10, "funny": 0, "challenge": 100, "capstone": 300}

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
CATALOG_FIELDS = {"workshop", "title", "intro", "challenges_intro", "labs", "badge", "require_match"}
LAB_FIELDS = {"id", "title"}
# `service` means the service fires the item itself (the cheating tiers).
MATCH_SOURCES = ("shell", "forgejo", "service", "dns", "ca", "cloud", "bao", "verify", "lab")

# The structured trigger (`match`) for the sources the service matches itself
# (service/matcher.py). Other sources are checked for `source` only until their adapter exists.
#   shell: one command line the student ran in their terminal, as the prompt hook reports it.
#     cmd          "git commit" or a list: a segment of the line starts with these words
#     flags        at least one of these flags is given; flags_none: none of them is
#     regex        searched in the segment ("git diff main..x", redirects kept: "echo x >> .gitignore")
#     exit         0, a list of codes, "nonzero" or "any" (default "any"): the line's exit status
#     branch       branch after the command ("HEAD" when detached); branch_before, before it
#     in_repo      the shell was inside a git work tree before the command
#     merging      a merge was in progress before the command; merging_after, after it
#   forgejo: one webhook event, credited to `user` (the pusher, the PR author, the reviewer).
#     event        push | create | delete | pull_request | pull_request_review
#     action       pull_request: opened, merged, closed, reopened, ...; review: approved, rejected, comment
#     ref_type     create/delete: branch or tag;  branch, tag;  repo "owner/name" ({user} allowed)
#   Any field `x_not` (where listed) is true when the event's x is present and differs.
#   {"any": [match, ...]} fires when one of the listed matches does.
MATCH_FIELDS = {
    "shell": {"cmd", "flags", "flags_none", "regex", "exit", "branch", "branch_not", "branch_before",
              "branch_before_not", "in_repo", "merging", "merging_after"},
    "forgejo": {"event", "action", "ref_type", "branch", "branch_not", "tag", "repo", "repo_not"},
}
FORGEJO_EVENTS = ("push", "create", "delete", "pull_request", "pull_request_review")


def _strs(value):
    """A string or a non-empty list of strings."""
    if isinstance(value, str):
        return bool(value.strip())
    return isinstance(value, list) and bool(value) and all(isinstance(v, str) and v.strip() for v in value)


def check_match(match, where):
    """(problems, sources) for one item's `match`. Empty problems means the matcher can use it."""
    problems, sources = [], set()
    if not isinstance(match, dict):
        return [f"{where}: 'match' must be an object"], sources
    if "any" in match:
        if set(match) != {"any"} or not isinstance(match["any"], list) or not match["any"]:
            return [f"{where}: 'any' must be the only key and a non-empty list of matches"], sources
        for i, sub in enumerate(match["any"], 1):
            p, s = check_match(sub, f"{where} any[{i}]")
            if isinstance(sub, dict) and "any" in sub:
                p.append(f"{where} any[{i}]: 'any' can't be nested")
            problems += p
            sources |= s
        return problems, sources
    source = match.get("source")
    if source not in MATCH_SOURCES:
        return [f"{where}: match.source must be one of {', '.join(MATCH_SOURCES)}"], sources
    sources.add(source)
    allowed = MATCH_FIELDS.get(source)
    if allowed is None:
        return problems, sources
    for key in sorted(set(match) - allowed - {"source"}):
        problems.append(f"{where}: match field '{key}' is not known for source {source}")
    if len(match) == 1:
        problems.append(f"{where}: match needs at least one field besides 'source'")
    for key in ("cmd", "flags", "flags_none", "branch", "branch_not", "branch_before", "branch_before_not",
                "action", "ref_type", "tag", "repo", "repo_not"):
        if key in match and not _strs(match[key]):
            problems.append(f"{where}: match.{key} must be a string or a list of strings")
    for key in ("in_repo", "merging", "merging_after"):
        if key in match and not isinstance(match[key], bool):
            problems.append(f"{where}: match.{key} must be true or false")
    if "exit" in match:
        e = match["exit"]
        ok = e in ("nonzero", "any") or (isinstance(e, int) and not isinstance(e, bool)) or (
            isinstance(e, list) and e and all(isinstance(x, int) and not isinstance(x, bool) for x in e))
        if not ok:
            problems.append(f"{where}: match.exit must be a code, a list of codes, 'nonzero' or 'any'")
    if "regex" in match:
        try:
            re.compile(match["regex"])
        except (re.error, TypeError) as exc:
            problems.append(f"{where}: match.regex does not compile ({exc})")
    if source == "forgejo":
        events = match.get("event")
        if not _strs(events) or any(e not in FORGEJO_EVENTS for e in ([events] if isinstance(events, str) else events)):
            problems.append(f"{where}: match.event must be one of {', '.join(FORGEJO_EVENTS)}")
    return problems, sources


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


def _check_item(item, kind, where, ids, problems, warnings, sources, require_match=False):
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
    if kind == "funny" and isinstance(pts, int) and not isinstance(pts, bool) and pts > 0:
        # Funny unlocks (and the shared cheating tiers) never add to a score: they call you out.
        problems.append(f"{where}: funny unlocks are worth 0 points, or a penalty for cheating, never a bonus")
    if "core" in item and kind != "milestone":
        problems.append(f"{where}: 'core' only applies to milestones")
    if kind == "milestone" and not isinstance(item.get("core"), bool):
        problems.append(f"{where}: milestones need 'core' (true or false)")
    match = item.get("match")
    if match is None or match == {}:
        if item.get("retired"):
            return
        if require_match:
            # The workshop opted in (catalog.json "require_match"): every item must be able to fire.
            problems.append(f"{where}: no 'match' (this workshop sets require_match)")
        else:
            warnings.append(f"{where}: no 'match' yet, so it never fires")
        return
    p, s = check_match(match, where)
    problems += p
    sources |= s


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


def load(workshop_dir, shared_path=None, known_verbs=None, check_name=True):
    """Load and validate one workshop's catalog.

    Returns (catalog, warnings). Raises CatalogError on any error. `known_verbs`, when
    given, is the set of verifier verbs the run's modules provide; a challenge that uses
    another verb is an error. `check_name=False` skips the folder-name check, for a service
    that mounts the workshop under a fixed path.
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
    require = meta.get("require_match", False)
    if not isinstance(require, bool):
        problems.append("catalog.json: 'require_match' must be true or false")
        require = False
    if check_name and meta.get("workshop") and meta["workshop"] != os.path.basename(os.path.normpath(workshop_dir)):
        problems.append("catalog.json: 'workshop' must match the workshop's folder name")

    shared = {"cheats": [], "unlocks": []}
    if shared_path:
        loaded = _read(shared_path, problems)
        if isinstance(loaded, dict):
            shared = loaded
    _check_fields(shared, {"cheats", "unlocks"}, "shared.json", problems)
    for kind_key in ("cheats", "unlocks"):
        for item in shared.get(kind_key, []):
            _check_item(item, "funny", f"shared.json {kind_key}", ids, problems, warnings, sources, require)

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
                _check_item(item, "milestone", f"labs/{lid}.json", ids, problems, warnings, sources, require)
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
            _check_item(item, "funny", "funny.json", ids, problems, warnings, sources, require)

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
        "require_match": require,
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
