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

import dnsrules
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
        # mode "approve": review (never merge) the PRs of accounts whose login starts with `approve_prefix`
        # (the demo bots) against the DNS rules; everyone else's pull requests are left alone.
        self.mode = cfg.get("mode", "merge")
        self.approve_prefix = cfg.get("approve_prefix", "")
        self.patience = int(cfg.get("patience", 0))  # seconds a student's PR waits for peer review; 0 = never
        self.me = cfg.get("self", "")  # Sensei's own login: its PRs (the seeded one) are never approved
        self._reviewers_at, self._reviewers_set = -1e9, set()
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
            if self.mode == "approve" and not self._approvable(pr):
                continue
            if row and row["sha"] == pr["head"]["sha"] and row["status"] in ("needs-review", "merged", "approved"):
                continue
            if row and row["status"] == "error" and self.clock() - row["updated"] < 30:
                continue
            if pr.get("draft") or pr.get("title", "").lower().startswith("wip"):
                continue
            self.handle(pr["number"])
            done.append(pr["number"])
        self._save()
        return done

    def handle(self, number, force=False, bypass=False):
        """Review and merge one PR. `force` (the facilitator's "merge anyway") skips the review; `bypass`
        (approve mode, `sensei approve --force`) skips only the wait for peer review, not the DNS rules."""
        try:
            return self._handle(number, force, bypass)
        except GitFailed as e:
            pr = self._get_pr(number) or {"number": number, "head": {}}
            self._set(pr, "error", str(e))
            self._say_once(pr, "I got stuck merging this one, so I've flagged it for the facilitator.")
            return "error"

    def _get_pr(self, number):
        status, pr = self.api("GET", f"/repos/{self.repo}/pulls/{number}")
        return pr if status == 200 else None

    def _handle(self, number, force, bypass=False):
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
        if self.mode == "approve":
            if not force:
                return self._approve(pr, head_repo, files, bypass)
            if not self._merge(pr):  # the facilitator's "merge anyway": no conflict-resolving in this mode
                raise GitFailed("Forgejo refused the merge (conflicts, a missing approval or a failing check)")
            self._set(pr, "merged", "merged anyway")
            return "merged"
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

    def _approvable(self, pr):
        login = (pr.get("user") or {}).get("login", "")
        return bool(login) and login != self.me

    def _is_bot(self, login):
        return bool(self.approve_prefix) and login.startswith(self.approve_prefix)

    def _reviewers(self):
        """Logins that have reviewed someone else's PR in the repo (cached a few seconds)."""
        if self.clock() - self._reviewers_at < 10:
            return self._reviewers_set
        found = set()
        status, prs = self.api("GET", f"/repos/{self.repo}/pulls?state=all&limit=50")
        for p in prs if status == 200 else []:
            st, reviews = self.api("GET", f"/repos/{self.repo}/pulls/{p['number']}/reviews")
            for r in reviews if st == 200 else []:
                who = (r.get("user") or {}).get("login", "")
                if who and who != (p.get("user") or {}).get("login"):
                    found.add(who)
        self._reviewers_at, self._reviewers_set = self.clock(), found
        return found

    def _approve(self, pr, head_repo, files, bypass=False):
        number = pr["number"]
        if not self._approvable(pr):
            raise GitFailed("this pull request is outside what Sensei is allowed to approve")
        author = pr["user"]["login"]
        if not (bypass or self._is_bot(author) or author in self._reviewers() or self._patience_over(pr)):
            # Peer review is part of the lesson: Sensei stands in for the neighbour once the student has
            # done their half (Lab 3 step 6), or has waited long enough, and checks again every pass.
            self._set(pr, "waiting", "review someone else's pull request first")
            self._say_once(pr, "I'll approve this one as soon as you have reviewed someone else's pull request "
                           "(Lab 3, step 6: run `sensei review` in your terminal and I'll pick one for you). "
                           "I check every few seconds.")
            return "waiting"
        if pr.get("mergeable") is False:
            # Nothing to judge until the branch has `main` in it: the merge base of a branch that has
            # been conflicting with a moving `main` can be anywhere. Looked at again on every pass.
            self._set(pr, "conflicts", "the branch conflicts with %s: bring %s into it" % (self.base, self.base))
            self._say_once(pr, "This branch has conflicts with `%s`, so there is nothing for me to approve yet. "
                           "Bring `%s` into it (`git pull origin %s`, keep both records, preview, commit, push) "
                           "and I'll look again straight away." % (self.base, self.base, self.base))
            return "conflicts"
        base_text = self._raw(self.repo, pr.get("merge_base") or self.base, self.file)
        head_text = self._raw(head_repo, pr["head"]["sha"], self.file)
        main_text = self._raw(self.repo, self.base, self.file)
        verdict = dnsrules.review(base_text, head_text, author, [f["filename"] for f in files], self.file, main_text)
        if not verdict["ok"]:
            self._set(pr, "needs-review", " ".join(verdict["problems"]))
            self._say_once(pr, "I can't approve this one:\n\n" + "\n".join("- " + p for p in verdict["problems"]) +
                           "\n\nI've flagged it for the facilitator.")
            return "needs-review"
        what = ", ".join(["adds " + n for n in verdict["added"]] + ["removes " + n for n in verdict["removed"]])
        status, _ = self.api("POST", f"/repos/{self.repo}/pulls/{number}/reviews",
                             {"event": "APPROVED", "body": SIGN + f"One record of your own ({what}), nothing else. Approved."})
        if status not in (200, 201):
            raise GitFailed(f"Forgejo answered {status} approving")
        self._set(pr, "approved", what + (" (on request, without waiting for a review)" if bypass else ""))
        return "approved"

    def _patience_over(self, pr):
        row = self.prs.get(pr["number"])
        return bool(self.patience and row and row["status"] == "waiting"
                    and self.clock() - row["since"] >= self.patience)

    # -- the student's `sensei` command ----------------------------------------------------
    def _my_open(self, login):
        return sorted((p for p in self._open_prs() if (p.get("user") or {}).get("login") == login),
                      key=lambda p: -p["number"])

    def student_status(self, login):
        rows = [r for r in self.snapshot() if r["user"] == login and r["status"] not in ("closed",)][:3]
        out = {"mode": self.mode, "patience": self.patience, "prs": rows,
               "reviewed": login in self._reviewers() if self.mode == "approve" else None}
        return out

    def student_review(self, login):
        """Pick a pull request for `login` to review: not theirs, not a bot's, not one they already reviewed;
        the one with the fewest reviews first, then the longest waiting, Sensei's practice PR last."""
        if self.mode != "approve":
            return {"ok": False, "message": "Nobody needs a review in this workshop."}
        choices = []
        for pr in self._open_prs():
            author = (pr.get("user") or {}).get("login", "")
            if not author or author == login or self._is_bot(author):
                continue
            st, reviews = self.api("GET", f"/repos/{self.repo}/pulls/{pr['number']}/reviews")
            reviews = reviews if st == 200 else []
            if any((r.get("user") or {}).get("login") == login for r in reviews):
                continue
            choices.append((author == self.me, len(reviews), pr["number"], pr))
        if not choices:
            return {"ok": True, "pr": None, "message": "Nothing waiting for you to review: you've covered every open pull request."}
        practice, _, _, pr = sorted(choices, key=lambda c: c[:3])[0]
        return {"ok": True, "pr": {"number": pr["number"], "author": pr["user"]["login"], "title": pr.get("title", ""),
                                   "practice": practice}}

    def student_approve(self, login, force=False):
        """`sensei approve [--force]`: approve the student's own open PR if it follows the rules and they have
        reviewed someone else's (or have waited long enough); `--force` skips that wait, never the rules."""
        if self.mode != "approve":
            return {"ok": False, "message": "Nothing to approve in this workshop."}
        mine = self._my_open(login)
        if not mine:
            return {"ok": False, "message": "You have no open pull request into %s." % self.base}
        pr = mine[0]
        self._reviewers_at = -1e9  # they may have just reviewed
        result = self.handle(pr["number"], bypass=force)
        row = self.prs.get(pr["number"], {})
        return {"ok": result == "approved", "result": result, "number": pr["number"], "reason": row.get("reason", ""),
                "patience": self.patience}

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
