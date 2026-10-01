"""Sensei: reviews and merges the roster pull request (A19). Stdlib plus the `git` binary.

One pass (`tick`) lists the open PRs into the configured branch of the configured repo and,
for each one it hasn't judged at its current head, either
  * refuses it with a review comment that says what is wrong (nothing is merged), or
  * merges it. A stale branch is brought up to date with a real merge commit pushed to the
    student's own branch (so their commit stays in history and their `git pull` just works);
    the one conflict every roster PR has, two people appending to the same spot, is resolved
    by keeping `main`'s file and appending the student's entry.
Everything talks to Forgejo through one injected function
    api(method, path, body=None, raw=False) -> (status, data)
with the service's own admin login, so tests swap in a fake. Actions are taken as that admin
account; comments are signed "Sensei".
"""
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.parse

import roster

SIGN = "\U0001F94B **Sensei:** "
MERGE_TRIES = 5


class GitFailed(Exception):
    pass


def _q(s):
    return urllib.parse.quote(s, safe="/")


class Sensei:
    def __init__(self, cfg, api, git_base, secret="", clock=time.time, state_path=None, sleep=time.sleep,
                 git_bin="git"):
        self.repo = cfg["repo"]
        self.base = cfg.get("base", "main")
        self.file = cfg.get("file", "roster/team.yaml")
        self.allowed = cfg.get("allowed_files") or [self.file]
        self.api, self.git_base, self.secret = api, git_base.rstrip("/"), secret
        self.clock, self.sleep, self.git_bin = clock, sleep, git_bin
        self.state_path = state_path
        self.enabled = True
        self.prs = {}
        if state_path and os.path.exists(state_path):
            try:
                with open(state_path) as f:
                    self.prs = {int(k): v for k, v in json.load(f).items()}
            except (OSError, ValueError):
                self.prs = {}

    # -- state ---------------------------------------------------------------------------
    def _save(self):
        if not self.state_path:
            return
        tmp = self.state_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.prs, f)
        os.replace(tmp, self.state_path)

    def _set(self, pr, status, reason="", **kw):
        n = pr["number"]
        old = self.prs.get(n, {})
        now = self.clock()
        row = {"number": n, "title": pr.get("title", ""), "user": (pr.get("user") or {}).get("login", ""),
               "sha": (pr.get("head") or {}).get("sha", ""), "status": status, "reason": reason,
               "since": old.get("since", now) if old.get("status") == status else now, "updated": now,
               "commented": old.get("commented", "")}
        row.update(kw)
        self.prs[n] = row
        self._save()

    def attention(self):
        """How many PRs are waiting on the facilitator."""
        return sum(1 for r in self.prs.values() if r["status"] in ("needs-review", "error"))

    def snapshot(self):
        now = self.clock()
        rows = sorted(self.prs.values(), key=lambda r: (r["status"] not in ("needs-review", "error"), -r["number"]))
        return [dict(r, minutes=int((now - r["since"]) // 60)) for r in rows]

    # -- forgejo -------------------------------------------------------------------------
    def _raw(self, repo, ref, path):
        status, data = self.api("GET", f"/repos/{repo}/raw/{_q(ref)}/{_q(path)}", raw=True)
        if status == 404:
            return None
        if status != 200:
            raise GitFailed(f"Forgejo answered {status} reading {path}")
        return data

    def _open_prs(self):
        out = []
        for page in range(1, 6):
            status, data = self.api("GET", f"/repos/{self.repo}/pulls?state=open&limit=50&page={page}")
            if status != 200:
                raise GitFailed(f"Forgejo answered {status} listing pull requests")
            out += [p for p in data if (p.get("base") or {}).get("ref") == self.base]
            if len(data) < 50:
                break
        return out

    def comment(self, number, text):
        status, _ = self.api("POST", f"/repos/{self.repo}/issues/{number}/comments", {"body": SIGN + text})
        return status in (200, 201)

    def _say_once(self, pr, text):
        row = self.prs.get(pr["number"], {})
        sha = pr["head"].get("sha", "")
        if row.get("commented") == sha:
            return
        if self.comment(pr["number"], text):
            self.prs[pr["number"]]["commented"] = sha
            self._save()

    # -- one pass ------------------------------------------------------------------------
    def tick(self):
        """Judge every new or changed open PR. Returns the numbers handled."""
        if not self.enabled:
            return []
        done = []
        try:
            prs = self._open_prs()
        except GitFailed:
            return done
        open_numbers = {p["number"] for p in prs}
        for n, row in self.prs.items():
            if n not in open_numbers and row["status"] not in ("merged", "closed"):
                row["status"], row["since"] = "closed", self.clock()
        for pr in sorted(prs, key=lambda p: p["number"]):
            row = self.prs.get(pr["number"])
            if row and row["sha"] == pr["head"]["sha"] and row["status"] in ("needs-review", "merged"):
                continue
            if row and row["status"] == "error" and self.clock() - row["updated"] < 30:
                continue
            if pr.get("draft") or pr.get("title", "").lower().startswith("wip"):
                continue
            self.handle(pr["number"])
            done.append(pr["number"])
        self._save()
        return done

    def handle(self, number, force=False):
        """Review and merge one PR. `force` (the facilitator's "merge anyway") skips the review."""
        try:
            return self._handle(number, force)
        except GitFailed as e:
            pr = self._get_pr(number) or {"number": number, "head": {}}
            self._set(pr, "error", str(e))
            self._say_once(pr, "I got stuck merging this one, so I've flagged it for the facilitator.")
            return "error"

    def _get_pr(self, number):
        status, pr = self.api("GET", f"/repos/{self.repo}/pulls/{number}")
        return pr if status == 200 else None

    def _handle(self, number, force):
        pr = self._get_pr(number)
        if pr is None:
            raise GitFailed("could not read the pull request")
        if pr.get("merged") or pr.get("state") != "open":
            self._set(pr, "merged" if pr.get("merged") else "closed")
            return "closed"
        # Confinement: Sensei only ever acts on the one configured repo and target branch.
        if (pr.get("base") or {}).get("ref") != self.base or ((pr["base"].get("repo") or {}).get("full_name") or self.repo) != self.repo:
            raise GitFailed("this pull request is outside what Sensei is allowed to approve")
        head_repo = (pr["head"].get("repo") or {}).get("full_name") or self.repo
        status, files = self.api("GET", f"/repos/{self.repo}/pulls/{number}/files?limit=50")
        if status != 200:
            raise GitFailed(f"Forgejo answered {status} listing the changed files")
        base_text = self._raw(self.repo, pr.get("merge_base") or self.base, self.file)
        head_text = self._raw(head_repo, pr["head"]["sha"], self.file)
        main_text = self._raw(self.repo, self.base, self.file)
        verdict = roster.review(base_text, head_text, main_text, self.allowed, [f["filename"] for f in files])
        if not verdict["ok"] and not force:
            self._set(pr, "needs-review", " ".join(verdict["problems"]))
            self._say_once(pr, "I can't rubber-stamp this one:\n\n" + "\n".join("- " + p for p in verdict["problems"]) +
                           "\n\nI've flagged it for the facilitator to review. You can also fix it on your branch "
                           "and push again; I'll look again straight away.")
            return "needs-review"
        added = verdict["added"]
        note = ""
        if not self._merge(pr):
            if not added:
                raise GitFailed("conflict I can't resolve without a single new roster entry")
            self._resolve(pr, head_repo, main_text, added)
            note = (" Your branch was behind `%s`, so I merged it in and kept everyone's entries. "
                    "Run `git pull` if you want that commit locally." % self.base)
            for _ in range(MERGE_TRIES):
                if self._merge(pr):
                    break
                self.sleep(1)
            else:
                raise GitFailed("merge still refused after resolving the conflict")
        who = added[0][0] if added else pr["user"]["login"]
        self.comment(number, f"*thunk* Rubber-stamped and merged. Welcome to the team, {who}!" + note)
        self._set(pr, "merged", "merged anyway" if force and not verdict["ok"] else "")
        return "merged"

    def _merge(self, pr):
        status, _ = self.api("POST", f"/repos/{self.repo}/pulls/{pr['number']}/merge",
                             {"Do": "merge", "delete_branch_after_merge": True})
        if status in (200, 204):
            return True
        if status in (405, 409):
            return False
        raise GitFailed(f"Forgejo answered {status} merging")

    # -- the conflict: real git ----------------------------------------------------------
    def _url(self, repo):
        p = urllib.parse.urlsplit(self.git_base)
        return f"{p.scheme}://{self.secret + '@' if self.secret else ''}{p.netloc}{p.path}/{repo}.git"

    def _git(self, cwd, *args, check=True):
        r = subprocess.run([self.git_bin, *args], cwd=cwd, capture_output=True, text=True, timeout=60,
                           env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
        if check and r.returncode:
            msg = (r.stderr or r.stdout).strip().splitlines()[-1:] or ["git failed"]
            raise GitFailed(("git %s: %s" % (args[0], msg[0])).replace(self.secret, "***") if self.secret else msg[0])
        return r

    def _resolve(self, pr, head_repo, main_text, added):
        ref = pr["head"]["ref"]
        work = tempfile.mkdtemp(prefix="sensei-")
        try:
            g = lambda *a, **k: self._git(work, *a, **k)  # noqa: E731
            self._git(None, "clone", "--quiet", "--branch", ref, self._url(head_repo), work)
            g("config", "user.name", "Sensei")
            g("config", "user.email", "sensei@dojo.invalid")
            g("remote", "add", "upstream", self._url(self.repo))
            g("fetch", "--quiet", "upstream", self.base)
            r = g("merge", "--no-edit", "-m", f"Merge {self.base} into {ref} (Sensei)", f"upstream/{self.base}",
                  check=False)
            if r.returncode:
                unmerged = g("diff", "--name-only", "--diff-filter=U").stdout.split()
                if unmerged != [self.file]:
                    g("merge", "--abort", check=False)
                    raise GitFailed("conflict in more than the roster file: " + ", ".join(unmerged[:5]))
                with open(os.path.join(work, self.file), "w") as f:
                    f.write(roster.combine(main_text or "", added))
                g("add", self.file)
                g("commit", "--no-edit")
            with open(os.path.join(work, self.file)) as f:
                entries, problems = roster.parse(f.read())
            want, _ = roster.parse(main_text or "")
            if problems or any(e not in entries for e in want + list(added)):
                raise GitFailed("the merged roster lost or garbled an entry; not pushing")
            g("push", "--quiet", "origin", f"HEAD:refs/heads/{ref}")
        finally:
            shutil.rmtree(work, ignore_errors=True)
