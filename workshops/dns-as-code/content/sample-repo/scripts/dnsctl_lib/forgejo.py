"""A minimal Forgejo REST API client that stands in for `gh` on a Forgejo
remote, alongside `gh` - not instead of it. procutil.py picks between the
two per-remote (see detect_forge()) so this project can be worked against
either GitHub or a self-hosted Forgejo without dnsctl.py itself knowing or
caring which. Python 3 standard library only, matching the rest of dnsctl -
no `requests`, just urllib.

Only implements the subset of `gh pr`/`gh run` that dnsctl.py actually
calls (see procutil.gh() for the dispatch), each returning a
subprocess.CompletedProcess so command functions don't need to know which
forge answered. JSON shapes are hand-mapped to match what dnsctl.py expects
from `gh --json ...` (see docs/dnsctl-cli.md and the gh manual) - field
names are gh's, not Forgejo's, on purpose.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class ForgejoError(Exception):
    pass


def _ok(stdout: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["forgejo"], returncode=0, stdout=stdout, stderr="")


def _err(stderr: str, returncode: int = 1) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["forgejo"], returncode=returncode, stdout="", stderr=stderr)


def parse_remote(url: str) -> tuple[str, str, str]:
    """('http://git-server:3000/dns-team/dns-as-code.git', ...) ->
    (base_api_url, owner, repo). Strips an embedded user@ and a trailing
    .git the same way `gh`/git tolerate either being present or absent."""
    parsed = urllib.parse.urlsplit(url)
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc += f":{parsed.port}"
    path = parsed.path.strip("/")
    if path.endswith(".git"):
        path = path[: -len(".git")]
    parts = path.split("/")
    if len(parts) < 2:
        raise ForgejoError(f"can't parse owner/repo out of remote '{url}'")
    owner, repo = parts[-2], parts[-1]
    scheme = parsed.scheme or "http"
    return f"{scheme}://{netloc}/api/v1", owner, repo


def _git_credential(action: str, fields: dict) -> dict:
    """Run `git credential <fill|approve|reject>` for this remote. `fill`
    asks git's configured helper (this lab caches your login in memory after
    the first `git push`) and, if it has nothing, prompts in the terminal
    exactly as `git push` would."""
    text = "".join(f"{k}={v}\n" for k, v in fields.items()) + "\n"
    result = subprocess.run(
        ["git", "credential", action], cwd=REPO_ROOT, input=text,
        capture_output=(action == "fill"), text=True,
    )
    if action != "fill":
        return {}
    if result.returncode != 0:
        raise ForgejoError("no Forgejo login given - run it again and enter your username and password")
    out = {}
    for line in result.stdout.splitlines():
        key, sep, value = line.partition("=")
        if sep:
            out[key] = value
    return out


# The login git handed us for this run, so a 401 can tell git to forget it
# and a success can tell git to keep it (same as git push does).
_git_login: dict | None = None


def _auth_header() -> str:
    """FORGEJO_TOKEN (the shell or .env) wins if set. Otherwise use the same
    Forgejo login as `git push` for this remote, via git's credential helper -
    nothing is written to disk by dnsctl."""
    global _git_login
    token = os.environ.get("FORGEJO_TOKEN")
    if token:
        return f"token {token}"

    if _git_login is None:
        url = subprocess.run(
            ["git", "remote", "get-url", "origin"], cwd=REPO_ROOT, capture_output=True, text=True
        ).stdout.strip()
        parsed = urllib.parse.urlsplit(url)
        fields = {"protocol": parsed.scheme or "http", "host": parsed.netloc.split("@")[-1]}
        if parsed.username:
            fields["username"] = parsed.username
        _git_login = _git_credential("fill", fields)

    import base64

    raw = f"{_git_login.get('username', '')}:{_git_login.get('password', '')}".encode()
    return f"Basic {base64.b64encode(raw).decode()}"


def _login_result(ok: bool) -> None:
    global _git_login
    if not _git_login or _git_login.get("_approved") or os.environ.get("FORGEJO_TOKEN"):
        return
    fields = {k: v for k, v in _git_login.items() if not k.startswith("_")}
    _git_credential("approve" if ok else "reject", fields)
    if ok:
        _git_login["_approved"] = "1"
    else:
        _git_login = None


def _request(method: str, url: str, body: dict | None = None, raw: bool = False):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", _auth_header())
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        if exc.code == 401:
            _login_result(False)
            raise ForgejoError(
                "Forgejo rejected your login (401) - run it again and re-enter your "
                "Forgejo username and password"
            ) from exc
        raise ForgejoError(f"Forgejo API {method} {url} -> {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ForgejoError(f"could not reach Forgejo at {url}: {exc.reason}") from exc
    _login_result(True)
    if raw:
        return payload.decode(errors="replace")
    if not payload:
        return None
    return json.loads(payload)


def _repo_context() -> tuple[str, str, str]:
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise ForgejoError("no 'origin' remote configured - can't tell which Forgejo repo this is")
    return parse_remote(result.stdout.strip())


def _commit_status_checks(api: str, owner: str, repo: str, sha: str) -> list[dict]:
    """Maps Forgejo's combined-status endpoint onto gh's statusCheckRollup
    shape (name/conclusion) closely enough for dnsctl.py's own filtering
    logic (it just greps for "preview" in name/context) to work unchanged.
    Returns [] with no error if this repo has no CI wired up - that's the
    normal case for this lab and dnsctl.py already handles an empty list."""
    try:
        statuses = _request("GET", f"{api}/repos/{owner}/{repo}/commits/{sha}/status")
    except ForgejoError:
        return []
    if not statuses:
        return []
    out = []
    for s in statuses.get("statuses", []):
        state = (s.get("status") or "").lower()
        conclusion = "SUCCESS" if state == "success" else state.upper() or "PENDING"
        out.append({"name": s.get("context", ""), "conclusion": conclusion})
    return out


def _pr_view_json(api: str, owner: str, repo: str, index: str, fields: str):
    pr = _request("GET", f"{api}/repos/{owner}/{repo}/pulls/{index}")
    want = set(fields.split(","))
    out: dict = {}
    if "state" in want:
        # gh (backed by GitHub's GraphQL API) exposes three states -
        # OPEN/CLOSED/MERGED; Forgejo's REST `state` is only open/closed,
        # with `merged` as a separate bool - dnsctl.py's own state checks
        # (cmd_merge, resolve_revert_target) expect gh's three-state model,
        # so translate rather than pass Forgejo's state through as-is.
        if pr.get("state") == "open":
            out["state"] = "OPEN"
        elif pr.get("merged"):
            out["state"] = "MERGED"
        else:
            out["state"] = "CLOSED"
    if "title" in want:
        out["title"] = pr.get("title", "")
    if "mergeCommit" in want:
        merged_sha = pr.get("merge_commit_sha")
        out["mergeCommit"] = {"oid": merged_sha} if merged_sha else None
    if "statusCheckRollup" in want:
        sha = (pr.get("head") or {}).get("sha")
        out["statusCheckRollup"] = _commit_status_checks(api, owner, repo, sha) if sha else []
    if "comments" in want:
        comments = _request("GET", f"{api}/repos/{owner}/{repo}/issues/{index}/comments") or []
        out["comments"] = [{"body": c.get("body", "")} for c in comments]
    return out


def run(args: list[str], capture: bool = True) -> subprocess.CompletedProcess:
    """Drop-in for procutil.gh() on a Forgejo remote - same call shape
    (a list of `gh` subcommand args), same CompletedProcess return type."""
    try:
        api, owner, repo = _repo_context()

        if args[:2] == ["pr", "list"]:
            prs = _request("GET", f"{api}/repos/{owner}/{repo}/pulls?state=open&limit=50") or []
            out = []
            for pr in prs:
                sha = (pr.get("head") or {}).get("sha")
                out.append({
                    "number": pr.get("number"),
                    "title": pr.get("title", ""),
                    "headRefName": (pr.get("head") or {}).get("ref", ""),
                    "url": pr.get("html_url", ""),
                    "isDraft": bool(pr.get("draft")),
                    "statusCheckRollup": _commit_status_checks(api, owner, repo, sha) if sha else [],
                })
            return _ok(json.dumps(out))

        if args[:2] == ["pr", "diff"]:
            index = args[2]
            diff = _request("GET", f"{api}/repos/{owner}/{repo}/pulls/{index}.diff", raw=True)
            return _ok(diff)

        if args[:2] == ["pr", "view"]:
            index = args[2]
            fields = args[args.index("--json") + 1] if "--json" in args else ""
            data = _pr_view_json(api, owner, repo, index, fields)
            return _ok(json.dumps(data))

        if args[:2] == ["pr", "review"]:
            index = args[2]
            body = args[args.index("--body") + 1] if "--body" in args else ""
            try:
                _request("POST", f"{api}/repos/{owner}/{repo}/pulls/{index}/reviews",
                          {"event": "APPROVED", "body": body})
            except ForgejoError as exc:
                msg = str(exc)
                if "your own pull" in msg.lower() or "403" in msg:
                    return _err("cannot approve your own pull request")
                raise
            return _ok(f"Approved pull request #{index}")

        if args[:2] == ["pr", "merge"]:
            index = args[2]
            _request("POST", f"{api}/repos/{owner}/{repo}/pulls/{index}/merge",
                      {"Do": "merge", "delete_branch_after_merge": "--delete-branch" in args})
            if not capture:
                print(f"Merged pull request #{index}")
            return _ok(f"Merged pull request #{index}")

        if args[:2] == ["pr", "create"]:
            def flag(name):
                return args[args.index(name) + 1] if name in args else ""
            pr = _request("POST", f"{api}/repos/{owner}/{repo}/pulls", {
                "title": flag("--title"),
                "body": flag("--body"),
                "base": flag("--base"),
                "head": flag("--head"),
            })
            return _ok(pr.get("html_url", ""))

        if args[:2] == ["run", "list"]:
            # /actions/runs (ActionRun), not /actions/tasks (ActionTask):
            # the two use separate id sequences (see ActionRunJob's
            # distinct run_id/task_id fields), and only /actions/runs/{id}
            # exists as a singular GET for `run watch` below to poll - so
            # list and watch have to stay on the same endpoint family for
            # the id one returns to mean anything to the other.
            #
            # Trade-off: ActionRun has no display-name field (only
            # workflow_id, the *file* name) so --workflow "DNS Apply" can't
            # be filtered server-side here the way `gh run list --workflow`
            # does. Left unfiltered - dnsctl.py's own client-side headSha
            # match (see validate_apply()) already picks the right one out
            # of a `limit=20` recent-runs list, which is plenty for this
            # lab's run volume. No CI configured means this list is just
            # empty and dnsctl.py's own "no run found" handling kicks in.
            try:
                data = _request("GET", f"{api}/repos/{owner}/{repo}/actions/runs?limit=20") or {}
            except ForgejoError:
                data = {}
            out = []
            for r in data.get("workflow_runs", []) or []:
                out.append({
                    "databaseId": r.get("id"),
                    "headSha": r.get("commit_sha"),
                    # Forgejo has one terminal `status` (success/failure/
                    # cancelled/skipped/...), not GitHub's separate
                    # status+conclusion pair - surfaced as both so
                    # dnsctl.py's `.get("conclusion") or .get("state")`
                    # fallback chains find it either way.
                    "status": r.get("status"),
                    "conclusion": r.get("status"),
                    "url": r.get("html_url", ""),
                })
            return _ok(json.dumps(out))

        if args[:2] == ["run", "watch"]:
            run_id = args[2]
            deadline = time.time() + 300
            while time.time() < deadline:
                try:
                    run = _request("GET", f"{api}/repos/{owner}/{repo}/actions/runs/{run_id}")
                except ForgejoError as exc:
                    return _err(str(exc))
                status = (run or {}).get("status")
                if status in ("success", "failure", "cancelled", "skipped"):
                    return _ok() if status == "success" else _err(f"run {run_id} ended: {status}")
                time.sleep(5)
            return _err(f"timed out waiting for run {run_id}")

        return _err(f"forgejo.py: unsupported gh-equivalent command: {' '.join(args)}")

    except ForgejoError as exc:
        return _err(str(exc))
