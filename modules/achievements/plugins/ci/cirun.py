"""Forgejo Actions run and folder verbs (see verifiers.json). Stdlib only.

`fn(api, args, ctx) -> (passed, message)`, `api` the service's Forgejo admin client the runner injects
(api(method, path, raw=False) -> (status, data)). Reads `GET /repos/{owner}/{repo}/actions/runs` (Forgejo's
ActionRun list: id, workflow_id the file name, event, status) and the contents API; never writes.

Isolation: the repo must be the checking student's own (`{user}/...`); the runner already refuses an assertion
that reads any other student's repo, and these verbs refuse it as well."""
import re
import urllib.parse

DONE = ("success", "failure", "cancelled", "skipped")
PAGE, PAGES, MAX_FILES = 50, 3, 40


class Unavailable(Exception):
    """Forgejo couldn't answer (try again)."""


def _path(repo):
    owner, _, name = repo.partition("/")
    return f"/repos/{urllib.parse.quote(owner, safe='')}/{urllib.parse.quote(name, safe='')}"


def _own(repo, ctx):
    return isinstance(repo, str) and repo.startswith(ctx["user"] + "/") and len(repo.split("/")) == 2


def _runs(api, repo):
    """The repository's newest Actions runs (newest first), or None when there is no such repo."""
    out = []
    for page in range(1, PAGES + 1):
        status, data = api("GET", f"{_path(repo)}/actions/runs?limit={PAGE}&page={page}")
        if status == 404:
            return None if page == 1 else out
        if status != 200:
            raise Unavailable(f"Forgejo answered {status} for the Actions runs")
        rows = data.get("workflow_runs") if isinstance(data, dict) else data
        rows = [r for r in rows or [] if isinstance(r, dict)]
        out.extend(rows)
        if len(rows) < PAGE:
            break
    return sorted(out, key=lambda r: int(r.get("id") or 0), reverse=True)


def _is_workflow(run, wf):
    for key in ("workflow_id", "path", "workflow_path"):
        v = str(run.get(key) or "")
        if v == wf or v.endswith("/" + wf) or v.split("@")[0].endswith("/" + wf):
            return True
    return False


def ci_run(api, args, ctx):
    repo, wf = args.get("repo", ""), args.get("workflow", "")
    if not _own(repo, ctx) or not wf:
        return False, "this check reads only your own repository's runs"
    runs = _runs(api, repo)
    if runs is None:
        return False, f"no repository {repo} yet"
    events = args.get("event")
    events = [events] if isinstance(events, str) else events
    done = [r for r in runs if _is_workflow(r, wf) and r.get("status") in DONE
            and (not events or r.get("event") in events)]
    if not done:
        return False, f"no finished {wf} run yet"
    if args.get("recovered"):
        if done[0].get("status") != "success":
            return False, f"the newest {wf} run ended {done[0].get('status')}; it should be green"
        if not any(r.get("status") == "failure" for r in done[1:]):
            return False, f"no failed {wf} run before the green one"
        return True, "ok"
    want = args.get("status", "success")
    if args.get("latest"):
        got = done[0].get("status")
        return (got == want), ("ok" if got == want else f"the newest {wf} run ended {got}, not {want}")
    if any(r.get("status") == want for r in done):
        return True, "ok"
    return False, f"no {wf} run has ended {want} yet"


def tree_file_contains(api, args, ctx):
    repo, ref, folder = args.get("repo", ""), args.get("ref", "main"), str(args.get("dir", "")).strip("/")
    if not _own(repo, ctx):
        return False, "this check reads only your own repository"
    q = urllib.parse.quote(folder)
    status, rows = api("GET", f"{_path(repo)}/contents/{q}?ref={urllib.parse.quote(ref, safe='')}")
    if status == 404:
        return False, f"no folder {folder} on {ref} yet"
    if status != 200 or not isinstance(rows, list):
        raise Unavailable(f"Forgejo answered {status} for {folder}")
    name_rx = re.compile(args.get("name_regex") or ".")
    regexes = args.get("regex") or []
    regexes = [regexes] if isinstance(regexes, str) else regexes
    count_rx, count_min = args.get("count_regex"), int(args.get("count_min", 1))
    files = [r for r in rows if isinstance(r, dict) and r.get("type") == "file" and name_rx.search(r.get("name") or "")]
    for f in files[:MAX_FILES]:
        path = f.get("path") or f"{folder}/{f.get('name')}"
        st, text = api("GET", f"{_path(repo)}/raw/{urllib.parse.quote(path)}?ref={urllib.parse.quote(ref, safe='')}",
                       raw=True)
        if st == 404:
            continue
        if st != 200 or not isinstance(text, str):
            raise Unavailable(f"Forgejo answered {st} for {path}")
        if not all(re.search(rx, text, re.M) for rx in regexes):
            continue
        if count_rx and len(re.findall(count_rx, text, re.M)) < count_min:
            continue
        return True, "ok"
    return False, f"no file in {folder} on {ref} has what this check looks for yet"


VERBS = {"ci_run": ci_run, "tree_file_contains": tree_file_contains}
