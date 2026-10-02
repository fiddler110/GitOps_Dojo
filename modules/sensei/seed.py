"""Seeds one pull request for the class to review (A26: the dns-as-code `dns-bot` PR).

Opens a branch and a PR into `base` of `repo` through Forgejo's contents API (no git needed) so
every student has something to review in Lab 3 even without a neighbour. Sensei only *opens* it: it
is never approved or merged by the bot (students review it; the facilitator merges or closes it).
Runs once per stack: the state file remembers the PR number, so a closed or merged one is not reopened.
With `"after_ci": true` it waits until `base`'s head commit has passed CI (combined status `success`), so the
PR's own CI preview runs against what that first CI run set up (dns-as-code: the first DNS Apply creates the
`dojo.test` zone; a preview started alongside it reported the zone as missing).
Same injected `api(method, path, body=None, raw=False) -> (status, data)` as bot.py.
"""
import base64
import json
import os
import urllib.parse

SIGN = "\U0001F94B **Sensei:** "


def _q(s):
    return urllib.parse.quote(s, safe="/")


class Seeder:
    def __init__(self, cfg, api, state_path=None):
        self.repo, self.base = cfg["repo"], cfg.get("base", "main")
        self.branch = cfg.get("branch", "dns-bot/add-status")
        self.file = cfg["file"]
        self.before, self.line = cfg["before"], cfg["line"]
        self.title, self.body = cfg["title"], cfg.get("body", "")
        self.after_ci = bool(cfg.get("after_ci"))
        self.api, self.state_path = api, state_path
        self.number = None
        if state_path and os.path.exists(state_path):
            try:
                with open(state_path) as f:
                    self.number = json.load(f).get("number")
            except (OSError, ValueError):
                pass

    def _save(self):
        if self.state_path:
            with open(self.state_path + ".tmp", "w") as f:
                json.dump({"number": self.number}, f)
            os.replace(self.state_path + ".tmp", self.state_path)

    def seed(self):
        """Open the PR if it has never been opened. True when it opened one now."""
        if self.number:
            return False
        if self.after_ci:
            status, st = self.api("GET", f"/repos/{self.repo}/commits/{_q(self.base)}/status")
            if status != 200 or st.get("state") != "success":
                return False  # base's first CI run still going (or failed): try again next pass
        status, meta = self.api("GET", f"/repos/{self.repo}/contents/{_q(self.file)}?ref={_q(self.base)}")
        if status != 200 or not isinstance(meta, dict):
            return False  # repo or file not there yet (an empty repo lists []): try again next pass
        text = base64.b64decode(meta["content"]).decode()
        if self.line in text or self.before not in text:
            return False  # already there, or not the file we expect: never guess
        new = text.replace(self.before, self.line + "\n" + self.before, 1)
        status, _ = self.api("POST", f"/repos/{self.repo}/branches",
                             {"new_branch_name": self.branch, "old_branch_name": self.base})
        if status not in (201, 409):  # 409: branch already there from a half-finished try
            return False
        status, _ = self.api("PUT", f"/repos/{self.repo}/contents/{_q(self.file)}", {
            "content": base64.b64encode(new.encode()).decode(), "sha": meta["sha"], "branch": self.branch,
            "message": self.title})
        if status not in (200, 201):
            return False
        status, pr = self.api("POST", f"/repos/{self.repo}/pulls",
                              {"title": self.title, "head": self.branch, "base": self.base, "body": self.body})
        if status not in (200, 201):
            return False
        self.number = pr["number"]
        self._save()
        return True
