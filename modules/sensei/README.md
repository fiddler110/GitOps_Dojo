# sensei

Reviews every open pull request into `SENSEI_REPO`'s `main` (set per workshop in `workshop.env`; blank = Sensei only seeds, it reviews nothing. git-fundamentals uses `training/sample-training-repo`,
the Lab 1 roster PR) and merges the good ones. Listed in a workshop's `MODULES=`; git-fundamentals uses it.

- **Rules** (`roster.py`): only `roster/team.yaml` changes; the file parses as the lab's `- name:` / `role:`
  list; nothing already there is edited or removed; exactly one new entry, not already on the roster.
- **Confined:** it only acts on `SENSEI_REPO`, pull requests into `SENSEI_BASE`, and only approves a change to
  `SENSEI_FILE` that passes every rule above. Nothing else is ever approved or merged (a facilitator's
  "Merge anyway" is the only override). New kinds of approval get their own explicit rule set, like `roster.py`.
- **Good PR:** merged through the Forgejo API with a comment ("rubber-stamped"). **PR that doesn't match:** a
  comment saying what is wrong (once per push) and it is **flagged for the facilitator** (status `needs-review`,
  sorted first in the tab with a "N need you" line); not merged. Pushing a fix is picked up within
  `SENSEI_INTERVAL` seconds (5). A merge Sensei can't finish is flagged the same way (`error`).
- **Stale branch** (the usual case: everyone appends to the same spot): `git merge` of `main` into the
  student's own branch, pushed to it. The one expected conflict is resolved by keeping `main`'s file and
  appending the student's entry, so their commit stays in history and `git branch -d` works after.
  Anything else conflicting is left for the facilitator ("error" in the tab).
- **Facilitator tab** (`/admin` -> Sensei): every PR with status, why, minutes stuck; Merge anyway,
  Comment, Look now, Pause. `SENSEI_ENABLED=0` starts it paused.
- Acts as the Forgejo admin account (comments are signed "Sensei"). Challenge PRs in students' own repos
  are never touched.
- Needs `git`, so it has its own small image (`Dockerfile`). Tests: `python3 -B -m unittest test_roster test_bot`.
