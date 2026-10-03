"""Forgejo/git verifier verbs and the per-student repo seed builder (achievements plug-in, A22).

Declared in verifiers.json beside this file and loaded by the service (service/challenges.py).
Stdlib only. Everything talks to Forgejo through one injected function

    api(method, path, body=None, raw=False) -> (status, data)

(path under /api/v1; `data` is parsed JSON, or text when raw=True; status 0 = unreachable),
using the service's own admin login, so tests swap in a fake Forgejo.

A verb is fn(api, args, ctx) -> (passed, message), with `args` already templated for the
student and `ctx` = {"user", "seed"} (seed: what the builder recorded for this student, or {}).
A Forgejo that can't be reached or answers oddly raises Unavailable: the check is "try again",
never a wrong answer. The message of a failed check is shown to the student, so it says what
is missing without giving the answer away.
"""

import base64
import datetime
import hashlib
import re
import urllib.parse

SEED_AUTHOR = {"name": "Dojo Seed", "email": "seed@dojo.invalid"}
MAX_PAGES = 5
PAGE = 50


class Unavailable(Exception):
    """Forgejo couldn't answer; nothing about the student's work is known."""


class SeedError(Exception):
    """The seed builder couldn't create the repo."""


# -- helpers ---------------------------------------------------------------------------
def _seg(s):
    return urllib.parse.quote(str(s), safe="")


def repo_path(repo):
    owner, _, name = repo.partition("/")
    return f"/repos/{_seg(owner)}/{_seg(name)}"


def _get(api, path, raw=False):
    """GET; None on 404, Unavailable on anything else that isn't 200."""
    status, data = api("GET", path, raw=raw)
    if status == 404:
        return None
    if status != 200:
        raise Unavailable(f"Forgejo answered {status} for {path.split('?')[0]}")
    return data


def _paged(api, path):
    sep = "&" if "?" in path else "?"
    out = []
    for page in range(1, MAX_PAGES + 1):
        rows = _get(api, f"{path}{sep}limit={PAGE}&page={page}")
        if rows is None:
            return None if page == 1 else out
        out.extend(rows)
        if len(rows) < PAGE:
            break
    return out


def _raw(api, repo, ref, path):
    return _get(api, f"{repo_path(repo)}/raw/{urllib.parse.quote(path)}?ref={_seg(ref)}", raw=True)


def _content_ok(content, a):
    if "regex" in a:
        hit = re.search(a["regex"], content, re.M) is not None
    else:
        hit = a["text"] in content
    return hit != bool(a.get("absent"))


def _pulls(api, repo):
    return _paged(api, f"{repo_path(repo)}/pulls?state=all") or []


def _find_pr(api, a):
    """The newest pull request that fits a's head (any head when not given), base, state and
    title_prefix, and why not."""
    head, base, state = a.get("head"), a.get("base", "main"), a.get("state", "open_or_merged")
    prefix = (a.get("title_prefix") or "").lower()
    near = None
    for pr in sorted(_pulls(api, a["repo"]), key=lambda p: -p.get("number", 0)):
        if (head and (pr.get("head") or {}).get("ref") != head) or (pr.get("base") or {}).get("ref") != base:
            continue
        merged = bool(pr.get("merged"))
        open_ = pr.get("state") == "open"
        fits = {"open": open_, "merged": merged, "open_or_merged": open_ or merged}.get(state, False)
        if not fits:
            near = near or "closed without merging"
            continue
        if prefix and not (pr.get("title") or "").lower().startswith(prefix):
            near = near or f"its title doesn't start with '{a['title_prefix']}'"
            continue
        return pr, ""
    what = {"open": "open", "merged": "merged"}.get(state, "open or merged")
    why = f"no {what} pull request " + (f"from {head} " if head else "") + f"into {base}"
    return None, why + (f" (found one, but {near})" if near else "")


def _commits(api, repo, branch, path=None):
    q = f"{repo_path(repo)}/commits?sha={_seg(branch)}&stat=false&verification=false&files=false"
    if path:
        q += f"&path={urllib.parse.quote(path)}"
    return _paged(api, q)


# -- verbs -----------------------------------------------------------------------------
def no_push_since_step(api, a, ctx):
    """Nothing reached the branch after step 1 of a two-step challenge passed (on main, a push deploys).
    Goes by the newest commit's committer date: the API keeps no push times."""
    commits = _commits(api, a["repo"], a["ref"])
    if not commits:
        return False, f"no branch {a['ref']} in {a['repo']}"
    stamp = ((commits[0].get("commit") or {}).get("committer") or {}).get("date") or ""
    try:
        at = datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return False, f"can't read the date of the newest commit on {a['ref']}"
    if ctx.get("step_at") is None or at > ctx["step_at"]:
        return False, f"{a['ref']} of {a['repo']} changed after step 1 passed (a push deploys)"
    return True, f"nothing pushed to {a['ref']} since step 1"


def repo_exists(api, a, ctx):
    if _get(api, repo_path(a["repo"])) is None:
        return False, f"{a['repo']} doesn't exist yet (dojo-challenge start first)"
    return True, "repo exists"


def branch_exists(api, a, ctx):
    if _get(api, f"{repo_path(a['repo'])}/branches/{_seg(a['branch'])}") is None:
        return False, f"no branch {a['branch']} in {a['repo']}"
    return True, "branch exists"


def pr_exists(api, a, ctx):
    pr, why = _find_pr(api, a)
    return (True, "pull request found") if pr else (False, why)


def pr_files(api, a, ctx):
    pr, why = _find_pr(api, a)
    if not pr:
        return False, why
    rows = _paged(api, f"{repo_path(a['repo'])}/pulls/{int(pr['number'])}/files") or []
    got = sorted({r.get("filename") for r in rows})
    want = sorted(set(a["files"]))
    if got != want:
        return False, f"the pull request should change only {', '.join(want)}"
    return True, "pull request changes the right files"


def pr_file_contains(api, a, ctx):
    pr, why = _find_pr(api, a)
    if not pr:
        return False, why
    content = _raw(api, a["repo"], (pr.get("head") or {}).get("sha") or a["head"], a["path"])
    if content is None:
        return False, f"{a['path']} is missing in the pull request"
    if not _content_ok(content, a):
        return False, f"{a['path']} in the pull request isn't right yet"
    return True, "file is right"


def file_contains(api, a, ctx):
    content = _raw(api, a["repo"], a["ref"], a["path"])
    if content is None:
        return False, f"no {a['path']} on {a['ref']}"
    if not _content_ok(content, a):
        return False, f"{a['path']} on {a['ref']} isn't right yet"
    return True, "file is right"


def no_direct_push(api, a, ctx):
    repo, branch = a["repo"], a["branch"]
    commits = _commits(api, repo, branch)
    if commits is None:
        return False, f"no branch {branch} in {repo}"
    allowed = set((ctx.get("seed") or {}).get("commits") or [])
    for pr in _pulls(api, repo):
        if pr.get("merged") and (pr.get("base") or {}).get("ref") == branch:
            if pr.get("merge_commit_sha"):
                allowed.add(pr["merge_commit_sha"])
            for c in _paged(api, f"{repo_path(repo)}/pulls/{int(pr['number'])}/commits") or []:
                allowed.add(c.get("sha"))
    for c in commits:
        committer = ((c.get("commit") or {}).get("committer") or {}).get("email")
        if c.get("sha") not in allowed and committer != SEED_AUTHOR["email"]:
            return False, f"{branch} has a commit that didn't come through a pull request"
    return True, f"{branch} only changed through pull requests"


def introduced_by(api, repo, branch, path, text):
    """The oldest commit on `branch` whose diff adds a line equal to `text` in `path`."""
    want = text.strip()
    found = None
    for c in _commits(api, repo, branch, path) or []:
        diff = _get(api, f"{repo_path(repo)}/git/commits/{_seg(c['sha'])}.diff", raw=True) or ""
        current = None
        for line in diff.splitlines():
            if line.startswith("+++ "):
                current = line[4:].strip()
                current = current[2:] if current.startswith("b/") else current
            elif line.startswith("+") and current == path and line[1:].strip() == want:
                found = c      # listed newest first, so the last hit is the oldest
                break
    return found


def answer_names_commit(api, a, ctx):
    s = a["search"]
    culprit = introduced_by(api, a["repo"], s.get("branch", "main"), s["path"], s["text"])
    if culprit is None:
        return False, f"the planted line is no longer in {s.get('branch', 'main')}'s history; dojo-challenge reset gives a fresh copy"
    content = _raw(api, a["repo"], a["ref"], a["path"])
    if content is None:
        return False, f"no {a['path']} on {a['ref']}"
    low = content.lower()
    sha = culprit["sha"].lower()
    hashes = re.findall(r"\b[0-9a-f]{7,40}\b", low)
    author = (((culprit.get("commit") or {}).get("author") or {}).get("name") or "").lower()
    if not any(sha.startswith(h) for h in hashes):
        return False, f"{a['path']} doesn't name the right commit hash yet"
    if not author or author not in low:
        return False, f"{a['path']} has the right hash but not the right author"
    return True, "case closed"


def _subject(c):
    lines = (((c.get("commit") or {}).get("message")) or "").strip().splitlines()
    return lines[0].strip() if lines else ""


def commit_reverted(api, a, ctx):
    """The commit whose subject is a['message'] is in the branch's history (kept, not
    rewritten away) and a later commit there reverts it: git revert's own message, either
    'This reverts commit <sha>' or the subject 'Revert "<subject>"'."""
    repo, branch, subject = a["repo"], a.get("branch", "main"), a["message"].strip()
    commits = _commits(api, repo, branch)
    if commits is None:
        return False, f"no branch {branch} in {repo}"
    revert_subject = f'revert "{subject.lower()}"'
    bad = [c for c in commits if _subject(c) == subject]
    if not bad:
        return False, (f"the commit '{subject}' isn't in {branch}'s history; bring it in, then undo it "
                       "with a new commit (history is rewritten if it just disappears)")
    shas = [c["sha"].lower() for c in bad if c.get("sha")]
    for c in commits:
        msg = (((c.get("commit") or {}).get("message")) or "").lower()
        if _subject(c).lower() == revert_subject:
            return True, "the bad commit is reverted"
        for m in re.finditer(r"this reverts commit ([0-9a-f]{7,40})", msg):
            if any(s.startswith(m.group(1)) for s in shas):
                return True, "the bad commit is reverted"
    return False, f"'{subject}' is still in effect on {branch}: undo it with a commit that reverts it"


MAX_SCAN_BLOBS = 300           # history_absent reads at most this many distinct files
MAX_SCAN_BYTES = 256 * 1024    # and skips any single file bigger than this


def history_absent(api, a, ctx):
    """No file on any branch, in any commit, matches the regex: a secret deleted in a later
    commit is still in the history, so it still fails. Reads each distinct blob once."""
    repo, rx = a["repo"], re.compile(a["regex"], re.M)
    rp = repo_path(repo)
    branches = _paged(api, f"{rp}/branches")
    if branches is None:
        return False, f"{repo} doesn't exist yet (dojo-challenge start first)"
    trees = set()
    for b in branches:
        for c in _commits(api, repo, b["name"]) or []:
            sha = ((c.get("commit") or {}).get("tree") or {}).get("sha")
            if sha:
                trees.add(sha)
    blobs = {}
    for t in sorted(trees):
        data = _get(api, f"{rp}/git/trees/{_seg(t)}?recursive=true&per_page=1000") or {}
        for e in data.get("tree") or []:
            if e.get("type") == "blob" and (e.get("size") or 0) <= MAX_SCAN_BYTES:
                blobs.setdefault(e["sha"], e["path"])
    if len(blobs) > MAX_SCAN_BLOBS:
        return False, f"{repo} has too many files to scan ({len(blobs)}); keep it to the challenge's files"
    for sha, path in sorted(blobs.items(), key=lambda kv: kv[1]):
        data = _get(api, f"{rp}/git/blobs/{_seg(sha)}") or {}
        try:
            text = base64.b64decode(data.get("content") or "").decode(errors="replace")
        except ValueError:
            continue
        if rx.search(text):
            return False, (f"{a.get('what', 'something that must stay out of git')} is in {path}, somewhere in "
                           f"{repo}'s history. Deleting it in a later commit doesn't remove it: "
                           f"`dojo-challenge reset {ctx.get('challenge', 'ID')}` rebuilds the repo")
    return True, f"no {a.get('what', 'match')} anywhere in the history"


VERBS = {
    "repo_exists": repo_exists,
    "branch_exists": branch_exists,
    "pr_exists": pr_exists,
    "pr_files": pr_files,
    "pr_file_contains": pr_file_contains,
    "file_contains": file_contains,
    "no_direct_push": no_direct_push,
    "answer_names_commit": answer_names_commit,
    "commit_reverted": commit_reverted,
    "history_absent": history_absent,
    "no_push_since_step": no_push_since_step,
}


# -- seed builder ----------------------------------------------------------------------
def blob_sha(text):
    """git's blob id, which Forgejo's contents API wants for an update."""
    data = text.encode()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def person(value):
    """'Name <email>' or 'Name' -> {name, email} (a made-up address for a bare name)."""
    m = re.match(r"^\s*(.*?)\s*<([^>]+)>\s*$", value)
    if m:
        return {"name": m.group(1), "email": m.group(2)}
    slug = re.sub(r"[^a-z0-9]+", ".", value.lower()).strip(".") or "someone"
    return {"name": value.strip(), "email": f"{slug}@example.test"}


def build_repo(api, plan, fill, read_seed, now, reset=False):
    """Create the student's repo from `plan` (see seeds/README in the workshop). `fill`
    templates a string for this student, `read_seed(name)` returns a seed file's text.

    Returns {"repo", "created", "commits"}. An existing repo is left alone unless `reset`,
    which deletes it first (so start is idempotent and reset can run any number of times)."""
    repo = fill(plan["repo"])
    rp = repo_path(repo)
    exists = _get(api, rp) is not None
    if exists and not reset:
        return {"repo": repo, "created": False, "commits": []}
    if exists:
        status, _ = api("DELETE", rp)
        if status not in (204, 404):
            raise SeedError(f"couldn't delete the old {repo} (Forgejo answered {status})")
    owner, _, name = repo.partition("/")
    status, _ = api("POST", f"/admin/users/{_seg(owner)}/repos",
                    {"name": name, "private": bool(plan.get("private", False)), "auto_init": False,
                     "default_branch": "main", "description": fill(plan.get("description", ""))})
    if status != 201:
        raise SeedError(f"couldn't create {repo} (Forgejo answered {status})")
    trees = {}
    shas = []
    for i, c in enumerate(plan["commits"]):
        branch = c.get("branch", "main")
        body = {"message": fill(c["message"]), "author": person(fill(c.get("author", "Dojo Seed <seed@dojo.invalid>"))),
                "committer": dict(SEED_AUTHOR), "files": []}
        if branch in trees:
            body["branch"] = branch
        elif trees:
            start = c.get("from", "main")
            trees[branch] = dict(trees[start])
            body["branch"], body["new_branch"] = start, branch
        else:
            trees[branch] = {}      # the first commit of an empty repo lands on its default branch
        if "days_ago" in c:
            when = datetime.datetime.fromtimestamp(now - float(c["days_ago"]) * 86400, datetime.timezone.utc)
            stamp = when.strftime("%Y-%m-%dT%H:%M:%SZ")
            body["dates"] = {"author": stamp, "committer": stamp}
        tree = trees[branch]
        for f in c["files"]:
            path = f["path"]
            if "from" in f:
                content = fill(read_seed(f["from"]))
            elif "append" in f:
                content = tree.get(path, "") + fill(f["append"]) + "\n"
            elif "replace" in f:
                old, new = (fill(x) for x in f["replace"])
                if old not in tree.get(path, ""):
                    raise SeedError(f"seed commit {i + 1}: '{old}' is not in {path}")
                content = tree[path].replace(old, new, 1)
            else:
                raise SeedError(f"seed commit {i + 1}: {path} needs from, append or replace")
            op = {"path": path, "content": base64.b64encode(content.encode()).decode()}
            if path in tree:
                op.update(operation="update", sha=blob_sha(tree[path]))
            else:
                op["operation"] = "create"
            body["files"].append(op)
            tree[path] = content
        status, data = api("POST", f"{rp}/contents", body)
        if status not in (200, 201) or not isinstance(data, dict):
            raise SeedError(f"seed commit {i + 1} was refused (Forgejo answered {status})")
        shas.append(((data.get("commit") or {}).get("sha")))
    return {"repo": repo, "created": True, "commits": [s for s in shas if s]}


BUILDERS = {"forgejo-repo": build_repo}
