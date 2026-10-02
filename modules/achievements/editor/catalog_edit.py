"""Catalog editor logic: read every achievement JSON into rows, apply a batch of edits, validate
them with the real catalog loader, then write the changed files and regenerate ACHIEVEMENTS.md.

No HTTP here (server.py is a thin layer) and stdlib only. Paths the client names are checked
against the files this editor loaded, so it can only ever write catalog JSON and the markdown
generated from it.
"""

import hashlib
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "catalog"))
import catalog as cat  # noqa: E402
import render_md  # noqa: E402

SHARED_REL = "modules/achievements/catalog/shared.json"
TEXT_REQUIRED = ("title", "joke", "when", "goal")
# What the editor may change, per kind. `id` and `match` are read-only (ids are forever).
EDITABLE = {
    "milestone": ("enabled", "title", "joke", "when", "points", "core"),
    "funny": ("enabled", "title", "joke", "when", "points"),
    "cheat": ("enabled", "title", "joke", "when", "points"),
    "challenge": ("enabled", "title", "goal", "hints", "answer", "points"),
    "capstone": ("enabled", "title", "goal", "hints", "answer", "points"),
}


class EditError(Exception):
    """Edits refused. `status` is the HTTP code, `errors` every reason."""

    def __init__(self, status, errors):
        self.status = status
        self.errors = list(errors)
        super().__init__("\n".join(self.errors))


def workshops(root):
    """Names of every workshop with an achievements catalog, sorted."""
    base = os.path.join(root, "workshops")
    if not os.path.isdir(base):
        return []
    return sorted(d for d in os.listdir(base) if os.path.isfile(os.path.join(base, d, "achievements", "catalog.json")))


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_text(root, rel):
    with open(os.path.join(root, rel), encoding="utf-8") as fh:
        return fh.read()


def dump(doc, original=None):
    """JSON text in the catalog's house style (2-space indent, key order kept, trailing newline).
    Escaping follows the original text so an untouched string never changes."""
    ensure_ascii = False
    if original is not None:
        before = json.loads(original)
        ensure_ascii = json.dumps(before, indent=2, ensure_ascii=False) + "\n" != original and \
            json.dumps(before, indent=2, ensure_ascii=True) + "\n" == original
    return json.dumps(doc, indent=2, ensure_ascii=ensure_ascii) + "\n"


def _files(root, name):
    """[(rel path, group label, kind)] for one workshop, in catalog order."""
    base = f"workshops/{name}/achievements"
    out = []
    try:
        meta = json.loads(_read_text(root, f"{base}/catalog.json"))
    except (OSError, ValueError):
        meta = {}
    for lab in meta.get("labs", []) if isinstance(meta, dict) else []:
        if isinstance(lab, dict) and isinstance(lab.get("id"), str) and cat.LAB_RE.match(lab["id"]):
            label = f"{lab['id'].replace('lab', 'Lab ')}: {lab.get('title', '')}"
            out.append((f"{base}/labs/{lab['id']}.json", label, "milestone"))
    out.append((f"{base}/funny.json", "Funny unlocks", "funny"))
    cdir = os.path.join(root, base, "challenges")
    if os.path.isdir(cdir):
        for fn in sorted(os.listdir(cdir), key=lambda n: (len(n), n)):
            if fn.endswith(".json"):
                out.append((f"{base}/challenges/{fn}", "Challenges", "challenge"))
    out.append((f"{base}/capstone.json", "Capstone", "capstone"))
    return out, meta.get("title", name) if isinstance(meta, dict) else name


def _items(doc, kind):
    """[(kind, item dict)] inside one parsed file."""
    if kind in ("challenge", "capstone"):
        return [(kind, doc)] if isinstance(doc, dict) else []
    if not isinstance(doc, dict):
        return []
    out = []
    for key, k in (("milestones", "milestone"), ("unlocks", kind if kind != "shared" else "funny"), ("cheats", "cheat")):
        for it in doc.get(key, []) if isinstance(doc.get(key), list) else []:
            if isinstance(it, dict):
                out.append((k, it))
    return out


def _fields(item, kind):
    f = {"enabled": cat.is_enabled(item)}
    for key in EDITABLE[kind]:
        if key == "enabled":
            continue
        if key == "hints":
            h = item.get("hints") if isinstance(item.get("hints"), list) else []
            f["hints"] = [(h[i] if i < len(h) and isinstance(h[i], str) else "") for i in (0, 1)]
        elif key == "points":
            f["points"] = item.get("points")
        elif key == "core":
            f["core"] = item.get("core")
        else:
            v = item.get(key)
            f[key] = v if isinstance(v, str) else ""
    return f


def _row(rel, kind, item):
    return {"file": rel, "id": str(item.get("id", "")), "kind": kind,
            "default_points": cat.DEFAULT_POINTS["funny" if kind == "cheat" else kind],
            "retired": bool(item.get("retired")),
            "match": json.dumps(item["match"], ensure_ascii=False) if item.get("match") else "",
            "fields": _fields(item, kind)}


def _group_rows(root, rel, label, kind, groups, bases, errors):
    try:
        text = _read_text(root, rel)
        doc = json.loads(text)
    except FileNotFoundError:
        return
    except (OSError, ValueError) as exc:
        errors.append(f"{rel}: {exc}")
        return
    bases[rel] = _sha(text)
    rows = [_row(rel, k, it) for k, it in _items(doc, kind)]
    if groups and groups[-1]["label"] == label:
        groups[-1]["rows"].extend(rows)
    else:
        groups.append({"label": label, "kind": kind if kind != "shared" else "funny", "rows": rows})


def scope_names(root, scope):
    names = workshops(root)
    if scope == "all":
        return names
    if scope not in names:
        raise EditError(404, [f"no workshop '{scope}' with an achievements catalog (have: {', '.join(names)})"])
    return [scope]


def load_all(root, scope="all"):
    """Everything the page shows: {workshops: [{name, title, groups}], shared, bases, errors}."""
    bases, errors, out = {}, [], []
    for name in scope_names(root, scope):
        files, title = _files(root, name)
        groups = []
        for rel, label, kind in files:
            _group_rows(root, rel, label, kind, groups, bases, errors)
        out.append({"name": name, "title": title, "groups": groups})
    shared_groups = []
    if os.path.isfile(os.path.join(root, SHARED_REL)):
        try:
            doc = json.loads(_read_text(root, SHARED_REL))
        except (OSError, ValueError) as exc:
            errors.append(f"{SHARED_REL}: {exc}")
            doc = None
        if doc is not None:
            bases[SHARED_REL] = _sha(_read_text(root, SHARED_REL))
            for key, label, kind in (("cheats", "Cheating tiers", "cheat"), ("unlocks", "Shared unlocks", "funny")):
                items = doc.get(key) if isinstance(doc, dict) and isinstance(doc.get(key), list) else []
                rows = [_row(SHARED_REL, kind, it) for it in items if isinstance(it, dict)]
                shared_groups.append({"label": label, "kind": kind, "rows": rows})
    out.append({"name": "shared", "title": "Shared (every workshop)", "groups": shared_groups})
    return {"workshops": out, "bases": bases, "errors": errors, "scope": scope}


# -- applying edits ---------------------------------------------------------------------------
def _check_value(where, kind, field, value):
    """Type check of one edited value; returns a list of problems."""
    if field not in EDITABLE[kind]:
        return [f"{where}: '{field}' can't be edited here"]
    if field in ("enabled", "core"):
        return [] if isinstance(value, bool) else [f"{where}: {field} must be true or false"]
    if field == "points":
        if value is None:
            return []
        if not isinstance(value, int) or isinstance(value, bool) or not -100 <= value <= 1000:
            return [f"{where}: points must be empty or a whole number from -100 to 1000"]
        return []
    if field == "hints":
        ok = isinstance(value, list) and len(value) == 2 and all(isinstance(h, str) and h.strip() for h in value)
        return [] if ok else [f"{where}: hints must be two non-empty texts"]
    if not isinstance(value, str):
        return [f"{where}: {field} must be text"]
    if field in TEXT_REQUIRED and not value.strip():
        return [f"{where}: {field} can't be empty"]
    return []


def _set(item, field, value):
    if field == "enabled":
        if value:
            item.pop("enabled", None)       # the default: no key, so turning it back on is no diff
        else:
            item["enabled"] = False
    elif field == "points" and value is None:
        item.pop("points", None)
    elif field == "answer" and value == "":
        item.pop("answer", None)
    else:
        item[field] = value


def _validate(root, docs, names):
    """Run the real loader over each workshop in `names` with `docs` ({rel: doc}) in place of
    the files on disk. Returns ({name: catalog}, problems, warning count)."""
    tmp = tempfile.mkdtemp(prefix="achievements-edit-")
    catalogs, problems, warns = {}, [], 0
    try:
        shared = os.path.join(tmp, "shared.json")
        if SHARED_REL in docs:
            with open(shared, "w", encoding="utf-8") as fh:
                json.dump(docs[SHARED_REL], fh)
        elif os.path.isfile(os.path.join(root, SHARED_REL)):
            shutil.copy(os.path.join(root, SHARED_REL), shared)
        else:
            shared = None
        for name in names:
            src = os.path.join(root, "workshops", name, "achievements")
            dst = os.path.join(tmp, name, "achievements")
            shutil.copytree(src, dst)
            prefix = f"workshops/{name}/achievements/"
            for rel, doc in docs.items():
                if rel.startswith(prefix):
                    with open(os.path.join(dst, rel[len(prefix):]), "w", encoding="utf-8") as fh:
                        json.dump(doc, fh)
            try:
                catalogs[name], w = cat.load(os.path.join(tmp, name), shared)
                warns += len(w)
            except cat.CatalogError as exc:
                problems += [f"{name}: {p}" for p in exc.problems]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return catalogs, problems, warns


def _write(path, text):
    tmp = f"{path}.edit-tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    return tmp


def save(root, scope, changes, bases):
    """Apply `changes` ([{file, id, set: {field: value}}]) to the files loaded for `scope`.

    `bases` ({file: sha256}) is what the page loaded; a file changed on disk since then is a
    conflict (409). Every edit is type-checked, then the whole result is validated with the
    catalog loader; any problem refuses the lot (422) and nothing is written. Otherwise the
    changed files are written (temp file + rename each) and ACHIEVEMENTS.md regenerated.
    Returns {written: [rel], rendered: [rel], warnings: n}."""
    if not isinstance(changes, list) or not changes:
        raise EditError(400, ["nothing to save"])
    names = scope_names(root, scope)
    allowed = {SHARED_REL}
    for name in names:
        allowed |= {rel for rel, _, _ in _files(root, name)[0]}
    bases = bases if isinstance(bases, dict) else {}

    originals, docs, errors = {}, {}, []
    for ch in changes:
        if not isinstance(ch, dict) or not isinstance(ch.get("file"), str) or not isinstance(ch.get("set"), dict):
            errors.append("each change needs file, id and set")
            continue
        rel = ch["file"]
        if rel not in allowed or not os.path.isfile(os.path.join(root, rel)):
            errors.append(f"{rel}: not a catalog file this editor loaded")
            continue
        if rel not in docs:
            text = _read_text(root, rel)
            if bases.get(rel) != _sha(text):
                raise EditError(409, [f"{rel} changed on disk since the page loaded: reload (your edits are kept "
                                      "only in the page)"])
            originals[rel] = text
            docs[rel] = json.loads(text)
        kind_hint = ("capstone" if rel.endswith("/capstone.json") else "challenge" if "/challenges/" in rel
                     else "milestone" if "/labs/" in rel else "shared" if rel == SHARED_REL else "funny")
        found = [(k, it) for k, it in _items(docs[rel], kind_hint) if it.get("id") == ch.get("id")]
        if len(found) != 1:
            errors.append(f"{rel}: no item '{ch.get('id')}'")
            continue
        kind, item = found[0]
        where = f"{rel} {ch['id']}"
        for field, value in ch["set"].items():
            p = _check_value(where, kind, field, value)
            if p:
                errors += p
            else:
                _set(item, field, value)
    if errors:
        raise EditError(422, errors)

    touched = {rel.split("/")[1] for rel in docs if rel.startswith("workshops/")}
    check = workshops(root) if SHARED_REL in docs else sorted(touched)
    catalogs, problems, warns = _validate(root, docs, check)
    if problems:
        raise EditError(422, problems)

    texts = {rel: dump(doc, originals[rel]) for rel, doc in docs.items()}
    texts = {rel: t for rel, t in texts.items() if t != originals[rel]}
    renders = {}
    for name, catalog in catalogs.items():
        md = f"workshops/{name}/ACHIEVEMENTS.md"
        path = os.path.join(root, md)
        current = _read_text(root, md) if os.path.exists(path) else None
        text = render_md.render(catalog)
        if text != current:
            renders[md] = text
    pending = []
    try:
        for rel, text in list(texts.items()) + list(renders.items()):
            pending.append((_write(os.path.join(root, rel), text), os.path.join(root, rel)))
    except OSError as exc:
        for tmp, _ in pending:
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise EditError(500, [f"write failed, nothing changed: {exc}"])
    for tmp, path in pending:
        os.replace(tmp, path)
    return {"written": sorted(texts), "rendered": sorted(renders), "warnings": warns}
