"""A small in-memory Forgejo for the challenge tests: repos, branches, commits with full trees,
pull requests, and just the API routes the verifier verbs and the seed builder call. It speaks
the plug-ins' `api(method, path, body=None, raw=False) -> (status, data)`. Test helpers play
the student's part (commit, push a branch, open and merge a pull request)."""

import base64
import difflib
import hashlib
import itertools
import json
import threading
import urllib.parse


def blob_sha(text):
    data = text.encode()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


class FakeForgejo:
    def __init__(self, users=()):
        self.users = set(users)
        self.repos = {}
        self.blobs = {}           # blob sha -> text, filled as trees are listed
        self.writes = []          # (method, path) of every change, for the isolation tests
        self.down = False
        self._n = itertools.count(1)
        self.lock = threading.Lock()

    # -- the api -------------------------------------------------------------------------
    def __call__(self, method, path, body=None, raw=False):
        if self.down:
            return 0, None
        with self.lock:
            url = urllib.parse.urlsplit(path)
            q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
            parts = [urllib.parse.unquote(p) for p in url.path.strip("/").split("/")]
            if method != "GET":
                self.writes.append((method, url.path))
            return self._route(method, parts, q, body, raw)

    def _route(self, method, parts, q, body, raw):
        if parts[:2] == ["admin", "users"] and len(parts) == 4 and parts[3] == "repos" and method == "POST":
            owner = parts[2]
            if owner not in self.users:
                return 404, None
            full = f"{owner}/{body['name']}"
            if full in self.repos:
                return 409, None
            self.repos[full] = {"branches": {}, "commits": {}, "pulls": [], "default": body.get("default_branch", "main")}
            return 201, {"full_name": full}
        if parts[0] != "repos" or len(parts) < 3:
            return 404, None
        full = f"{parts[1]}/{parts[2]}"
        repo = self.repos.get(full)
        rest = parts[3:]
        if repo is None:
            return 404, None
        if not rest:
            if method == "GET":
                return 200, {"full_name": full}
            if method == "DELETE":
                del self.repos[full]
                return 204, None
        if rest == ["contents"] and method == "POST":
            return self._contents(repo, body)
        if rest == ["branches"] and method == "GET":
            return 200, self._page([{"name": b, "commit": {"id": h}} for b, h in sorted(repo["branches"].items())], q)
        if rest[:2] == ["git", "trees"] and len(rest) == 3 and method == "GET":
            # A tree's id here is "t" + its commit's sha; always recursive, never truncated.
            c = repo["commits"].get(rest[2][1:]) if rest[2].startswith("t") else None
            if c is None:
                return 404, None
            rows = []
            for path, text in sorted(c["tree"].items()):
                sha = blob_sha(text)
                self.blobs[sha] = text
                rows.append({"path": path, "type": "blob", "sha": sha, "size": len(text.encode())})
            return 200, {"sha": rest[2], "tree": rows, "truncated": False, "page": 1, "total_count": len(rows)}
        if rest[:2] == ["git", "blobs"] and len(rest) == 3 and method == "GET":
            text = self.blobs.get(rest[2])
            if text is None:
                return 404, None
            return 200, {"sha": rest[2], "encoding": "base64", "size": len(text.encode()),
                         "content": base64.b64encode(text.encode()).decode()}
        if rest[0] == "branches" and len(rest) == 2 and method == "GET":
            return (200, {"name": rest[1]}) if rest[1] in repo["branches"] else (404, None)
        if rest == ["commits"] and method == "GET":
            head = repo["branches"].get(q.get("sha", repo["default"])) or (q.get("sha") if q.get("sha") in repo["commits"] else None)
            if head is None:
                return 404, None
            shas = self._log(repo, head)
            if q.get("path"):
                shas = [s for s in shas if self._touches(repo, s, q["path"])]
            return 200, self._page([self._commit_json(repo, s) for s in shas], q)
        if rest[:2] == ["git", "commits"] and len(rest) == 3 and rest[2].endswith(".diff"):
            sha = rest[2][:-5]
            return (200, self._diff(repo, sha)) if sha in repo["commits"] else (404, None)
        if rest[0] == "raw":
            path = "/".join(rest[1:])
            ref = q.get("ref", repo["default"])
            sha = repo["branches"].get(ref, ref)
            c = repo["commits"].get(sha)
            if c is None or path not in c["tree"]:
                return 404, None
            return 200, c["tree"][path]
        if rest == ["pulls"] and method == "GET":
            return 200, self._page([self._pr_json(repo, p) for p in reversed(repo["pulls"])], q)
        if rest[0] == "pulls" and len(rest) == 3 and method == "GET":
            pr = next((p for p in repo["pulls"] if p["number"] == int(rest[1])), None)
            if pr is None:
                return 404, None
            head = self._pr_head(repo, pr)
            if rest[2] == "files":
                a, b = repo["commits"][pr["base_sha"]]["tree"], repo["commits"][head]["tree"]
                return 200, self._page([{"filename": f} for f in sorted(set(a) | set(b)) if a.get(f) != b.get(f)], q)
            if rest[2] == "commits":
                own = set(self._log(repo, head)) - set(self._log(repo, pr["base_sha"]))
                return 200, self._page([self._commit_json(repo, s) for s in self._log(repo, head) if s in own], q)
        return 404, None

    @staticmethod
    def _page(rows, q):
        limit, page = int(q.get("limit", 30)), int(q.get("page", 1))
        return rows[(page - 1) * limit: page * limit]

    def _contents(self, repo, body):
        if not repo["branches"]:
            branch, start = repo["default"], None
        elif body.get("new_branch"):
            branch, start = body["new_branch"], repo["branches"].get(body.get("branch", repo["default"]))
            if start is None or branch in repo["branches"]:
                return 422, None
        else:
            branch = body.get("branch", repo["default"])
            start = repo["branches"].get(branch)
            if start is None:
                return 404, None
        tree = dict(repo["commits"][start]["tree"]) if start else {}
        for op in body["files"]:
            content = base64.b64decode(op["content"]).decode()
            if op["operation"] == "create":
                if op["path"] in tree:
                    return 422, None
            elif op["operation"] == "update":
                if op["path"] not in tree or op.get("sha") != blob_sha(tree[op["path"]]):
                    return 409, None
            tree[op["path"]] = content
        sha = self._new_commit(repo, [start] if start else [], tree, body["author"], body["committer"], body["message"])
        repo["branches"][branch] = sha
        return 201, {"commit": {"sha": sha}}

    # -- git model -----------------------------------------------------------------------
    def _new_commit(self, repo, parents, tree, author, committer, message):
        n = next(self._n)
        sha = hashlib.sha1(json.dumps([n, parents, tree, author, message]).encode()).hexdigest()
        repo["commits"][sha] = {"n": n, "parents": parents, "tree": tree, "author": author,
                                "committer": committer, "message": message}
        return sha

    def _log(self, repo, head):
        seen, todo = set(), [head]
        while todo:
            s = todo.pop()
            if s not in seen:
                seen.add(s)
                todo.extend(repo["commits"][s]["parents"])
        return sorted(seen, key=lambda s: -repo["commits"][s]["n"])

    def _touches(self, repo, sha, path):
        c = repo["commits"][sha]
        before = repo["commits"][c["parents"][0]]["tree"].get(path) if c["parents"] else None
        return c["tree"].get(path) != before

    def _diff(self, repo, sha):
        c = repo["commits"][sha]
        before = repo["commits"][c["parents"][0]]["tree"] if c["parents"] else {}
        out = []
        for f in sorted(set(before) | set(c["tree"])):
            a, b = before.get(f), c["tree"].get(f)
            if a == b:
                continue
            out.append(f"diff --git a/{f} b/{f}")
            out += difflib.unified_diff((a or "").splitlines(), (b or "").splitlines(),
                                        f"a/{f}" if a is not None else "/dev/null", f"b/{f}", lineterm="")
        return "\n".join(out) + "\n"

    def _commit_json(self, repo, sha):
        c = repo["commits"][sha]
        return {"sha": sha, "parents": [{"sha": p} for p in c["parents"]],
                "commit": {"author": c["author"], "committer": c["committer"], "message": c["message"],
                           "tree": {"sha": "t" + sha}}}

    def _pr_head(self, repo, pr):
        return pr["merged_head"] if pr["merged"] else repo["branches"].get(pr["head"], pr.get("last_head"))

    def _pr_json(self, repo, pr):
        return {"number": pr["number"], "title": pr["title"], "state": pr["state"], "merged": pr["merged"],
                "merge_commit_sha": pr.get("merge_commit_sha"),
                "head": {"ref": pr["head"], "sha": self._pr_head(repo, pr)}, "base": {"ref": pr["base"]}}

    # -- the student's side ------------------------------------------------------------
    def commit(self, full, branch, files, who, start=None, message=None, merge=None):
        """Commit `files` ({path: text, or None to delete}) on `branch` as `who`, creating it from `start`
        (a branch) when new. Like a commit plus a push. `merge` (a branch) makes it a local
        merge commit with that branch's head as its second parent."""
        with self.lock:
            repo = self.repos[full]
            head = repo["branches"].get(branch) or repo["branches"][start or repo["default"]]
            tree = dict(repo["commits"][head]["tree"])
            tree.update(files)
            tree = {k: v for k, v in tree.items() if v is not None}  # None deletes the file
            person = {"name": who, "email": f"{who}@lab.test"}
            parents = [head] + ([repo["branches"][merge]] if merge else [])
            sha = self._new_commit(repo, parents, tree, person, person, message or f"work by {who}")
            repo["branches"][branch] = sha
            return sha

    def open_pr(self, full, head, base, title):
        with self.lock:
            repo = self.repos[full]
            n = len(repo["pulls"]) + 1
            repo["pulls"].append({"number": n, "head": head, "base": base, "title": title, "state": "open",
                                  "merged": False, "base_sha": repo["branches"][base]})
            return n

    def merge_pr(self, full, number, who, delete_branch=False):
        with self.lock:
            repo = self.repos[full]
            pr = repo["pulls"][number - 1]
            head, base_head = repo["branches"][pr["head"]], repo["branches"][pr["base"]]
            tree = dict(repo["commits"][base_head]["tree"])
            start = repo["commits"][pr["base_sha"]]["tree"]
            for f, text in repo["commits"][head]["tree"].items():
                if start.get(f) != text:
                    tree[f] = text
            person = {"name": who, "email": f"{who}@lab.test"}
            sha = self._new_commit(repo, [base_head, head], tree, person, person, f"Merge pull request #{number}")
            repo["branches"][pr["base"]] = sha
            pr.update(state="closed", merged=True, merge_commit_sha=sha, merged_head=head)
            if delete_branch:
                del repo["branches"][pr["head"]]

    def file(self, full, ref, path):
        repo = self.repos[full]
        return repo["commits"][repo["branches"].get(ref, ref)]["tree"].get(path)
