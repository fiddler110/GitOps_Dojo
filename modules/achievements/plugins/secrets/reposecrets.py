"""Forgejo Actions repository-secret verb (see verifiers.json). Stdlib only.

`fn(api, args, ctx) -> (passed, message)`, `api` the service's Forgejo admin client the runner
injects (api(method, path) -> (status, data)). Reads only the secret *names* Forgejo lists
(`GET /repos/{owner}/{repo}/actions/secrets`); Forgejo never returns a value.

Isolation: the repo must be the checking student's own (`{user}/...`); the runner already refuses
an assertion that reads any other student's repo, and this verb refuses it as well."""
import urllib.parse


class Unavailable(Exception):
    """Forgejo couldn't answer (try again)."""


def repo_secret(api, args, ctx):
    repo, name = args.get("repo", ""), args.get("name", "")
    if not repo.startswith(ctx["user"] + "/") or "/" not in repo or not name:
        return False, "this check reads only your own repository's secrets"
    owner, _, rname = repo.partition("/")
    path = f"/repos/{urllib.parse.quote(owner, safe='')}/{urllib.parse.quote(rname, safe='')}/actions/secrets"
    names, page = set(), 1
    while page <= 5:
        status, data = api("GET", f"{path}?limit=50&page={page}")
        if status == 404:
            return False, f"no repository {repo} yet"
        if status != 200 or not isinstance(data, list):
            raise Unavailable(f"Forgejo answered {status} for the secrets list")
        names |= {s.get("name") for s in data if isinstance(s, dict)}
        if len(data) < 50:
            break
        page += 1
    present = name in names
    if args.get("absent"):
        return (not present), (f"the secret {name} is still there" if present else "ok")
    return present, ("ok" if present else f"no secret named {name} on {repo} yet")


VERBS = {"repo_secret": repo_secret}
