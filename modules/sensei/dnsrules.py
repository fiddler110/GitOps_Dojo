"""The DNS rules Sensei applies when it approves a demo bot's pull request (pure: no Forgejo, no git).

`dnsconfig.js` is a JavaScript file, so this does not parse it: it compares the PR's file with the file at
the merge base line by line and only accepts a change made of record lines (`A("name", ...)`, `CNAME(...)`,
...) whose name starts with the author's own login. That is what Lab 3 asks of a student ("named after your
username so nobody else's record is touched"), and what the Lab 5 rollback of that record looks like.
"""
import difflib
import re

_RECORD = re.compile(r'^\s*(?:A|AAAA|CNAME|TXT|MX|SRV|CAA)\(\s*"([^"]+)"')
MAX_LINES = 4


def review(base_text, head_text, author, changed_files, file="dnsconfig.js", main_text=None):
    """Judge one PR. Returns {"ok", "problems": [...], "added": [name], "removed": [name]}.

    `base_text` is the file at the merge base, `head_text` the PR branch's, `main_text` the target's
    current file. With many people merging `main` into their branches the history is criss-crossed and the
    merge base can be older than what the branch brought in, so a line the branch took from `main` would
    look like the author's. What a merge changes is the branch's edits that `main` doesn't already have:
    an added line `main` already has, or a removed line `main` no longer has, is not this PR's change."""
    problems = []
    extra = sorted(set(changed_files) - {file})
    if extra:
        problems.append("This pull request changes files other than %s: %s." % (file, ", ".join(extra[:5])))
    if head_text is None or base_text is None:
        problems.append("%s is missing on one side of the pull request." % file)
        return {"ok": False, "problems": problems, "added": [], "removed": []}
    added, removed = [], []
    in_main = set(main_text.splitlines()) if main_text is not None else None
    changed = 0
    for line in difflib.ndiff(base_text.splitlines(), head_text.splitlines()):
        if line[:2] not in ("+ ", "- "):
            continue
        body = line[2:]
        if not body.strip():
            continue
        if in_main is not None and ((line[0] == "+" and body in in_main) or (line[0] == "-" and body not in in_main)):
            continue
        changed += 1
        m = _RECORD.match(body)
        if not m:
            problems.append("A changed line is not a DNS record: %s" % body.strip()[:60])
        elif not m.group(1).startswith(author + "-"):
            problems.append("The record \"%s\" is not one of %s's own (its name should start with \"%s-\")."
                            % (m.group(1), author, author))
        else:
            (added if line[0] == "+" else removed).append(m.group(1))
    if not changed:
        problems.append("There is no change to dnsconfig.js.")
    elif changed > MAX_LINES:
        problems.append("%d lines changed; one record at a time (at most %d lines)." % (changed, MAX_LINES))
    return {"ok": not problems, "problems": problems[:5], "added": added, "removed": removed}
