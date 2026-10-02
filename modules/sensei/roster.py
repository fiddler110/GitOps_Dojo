"""The roster rules Sensei applies (pure: no Forgejo, no git). Stdlib only.

`roster/team.yaml` is a comment header and then a flat list of `- name: X` / `  role: Y`
entries. We parse exactly that shape (no PyYAML in the image) and refuse anything else, so a
"the YAML parses" check means the lab's format was followed.
"""
import re

_ENTRY = re.compile(r"^- name:[ \t]*(.*?)[ \t]*$")
_ROLE = re.compile(r"^  role:[ \t]*(.*?)[ \t]*$")


def _unquote(v):
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def parse(text):
    """(entries, problems). An entry is (name, role). Comments and blank lines are ignored."""
    entries, problems, name = [], [], None
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = _ENTRY.match(line)
        if m:
            if name is not None:
                problems.append(f"line {n}: the entry for \"{name}\" has no role")
            name = _unquote(m.group(1))
            if not name:
                problems.append(f"line {n}: name is empty")
            continue
        m = _ROLE.match(line)
        if m and name is not None:
            role = _unquote(m.group(1))
            if not role:
                problems.append(f"line {n}: role is empty")
            entries.append((name, role))
            name = None
            continue
        problems.append(f"line {n}: expected `- name: ...` then `  role: ...` (two-space indent), got: {line.strip()[:60]}")
    if name is not None:
        problems.append(f"the entry for \"{name}\" has no role")
    return entries, problems


def render(entries):
    return "".join(f"- name: {n}\n  role: {r}\n" for n, r in entries)


def combine(main_text, added):
    """`main`'s file with the new entries appended at the end (what a manual resolution does)."""
    out = main_text if main_text.endswith("\n") or not main_text else main_text + "\n"
    return out + render(added)


def review(base_text, head_text, main_text, allowed_files, changed_files):
    """Judge one roster PR. `base_text` is the file at the merge base (what the student started
    from), `head_text` the PR branch's file, `main_text` the target's current file.

    Returns {"ok", "problems": [...], "added": [(name, role)]}. Problems are written for the
    student and never give away more than the format they were asked to follow."""
    problems = []
    extra = sorted(set(changed_files) - set(allowed_files))
    if extra:
        problems.append("This pull request changes files other than roster/team.yaml: " + ", ".join(extra[:5]) +
                        ". Undo those changes so only the roster file is in the PR.")
    if head_text is None:
        problems.append("roster/team.yaml is missing on your branch.")
        return {"ok": False, "problems": problems, "added": []}
    head, bad = parse(head_text)
    problems += bad
    base, _ = parse(base_text or "")
    if bad:
        return {"ok": False, "problems": problems, "added": []}
    missing = [e for e in base if e not in head]
    if missing:
        problems.append("Entries that were already in the roster were changed or removed: " +
                        ", ".join(n for n, _ in missing[:5]) + ". Only add your own entry.")
    added = [e for e in head if e not in base]
    if not added:
        problems.append("There is no new entry: add `- name:` and `role:` for yourself at the bottom.")
    elif len(added) > 1:
        problems.append("Add only one entry (yours); this PR adds %d." % len(added))
    main, _ = parse(main_text or "")
    if added and not missing and len(added) == 1 and added[0] in main:
        problems.append(f"\"{added[0][0]}\" is already on the roster.")
    return {"ok": not problems, "problems": problems, "added": added}
