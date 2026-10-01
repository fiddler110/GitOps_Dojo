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
- **Approve mode** (`SENSEI_MODE=approve`, dns-as-code): reviews but never merges. It approves the PRs of demo bots
  (logins starting with `SENSEI_APPROVE_PREFIX`) straight away, and a student's PR once that student has reviewed
  someone else's PR in the repo (Lab 3 step 6: peer review is still practised, nobody waits for a neighbour; until
  then the PR shows `waiting` and gets one explanatory comment). Its own seeded PR is never approved.
  `dnsrules.py` approves a change made only of record lines (`A(...)`, `CNAME(...)`...) named `<author>-...`, at
  most four lines, in `SENSEI_FILE` alone: one new record, or the Lab 5 rollback that removes it. Anything else is
  flagged for the facilitator. People merge their own PRs.
- **The `sensei` command** (`terminal/`, in every terminal of a workshop that lists the module): `sensei help|status|review|approve [--force]`,
  talking to `/api/student/*` on the service with the student's own Forgejo token (confirmed with Forgejo; the port
  is only reachable from the lab network). `review` picks a PR for them to review (not theirs, not a bot's, one they
  haven't reviewed, fewest reviews first, Sensei's practice PR last). `approve` approves their own open PR once they
  have reviewed someone else's, or after `SENSEI_PATIENCE_SECONDS` (default 180, 0 = never) of waiting, which the
  background pass also applies by itself. `approve --force` skips that wait at once but never the `dnsrules.py`
  rules. Sensei never merges for students.
- **Support desk** (every workshop lists the module, so the `sensei` command is always there; offline, no model):
  - `sensei ask "..."`: searches the workshop's own `content/lab/*.md` section by section (`support.LabIndex`; headings
    naming a challenge or capstone are skipped, so it can't leak a hint). Nothing matching says so instead of guessing.
  - `sensei why`: reads the last 60 lines of the student's tmux pane and explains the known error nearest the bottom
    (`support.Patterns`). The table is derived from the labs' own "You see | Cause / fix" tables, plus
    `modules/sensei/patterns/shared.json` (git and shell) and an optional `workshops/<name>/sensei/patterns.json`
    (`{"patterns": [{"id", "regex", "title", "explain", "fix", "where", "section"}]}`).
  - `sensei hand "..."` / `sensei inbox`: raise a hand with the message and the last screen of output; the facilitator
    replies in the Sensei tab (Raised hands) and it shows under `sensei inbox`. Three open at most, one per 20 s per
    student; a request also carries Sensei's own guess (the error it recognised, the lab section that covers it).
  - `sensei check`: the student's core milestones for the current lab (first with one still undone), done or still to
    do, with the lab step each needs. Reads the achievements service (`GET /api/sensei/progress`), so it needs a
    workshop with a scoreboard; without one it says so. Challenges, funny unlocks and cheats are never listed.
  - Mounts the workshop folder read-only at `/opt/workshop` (`WORKSHOP_DIR`); help requests live in `/data/help.json`.
- **Stuck radar** (Sensei tab): flags `failing` (5 failed commands in a row, or 7 in 10 of the last ten minutes),
  `stalled` (busy at the terminal but no new milestone for `SENSEI_STUCK_MINUTES`, default 10) and `quiet` (no command
  for 15 min), worst first, with a raised hand marked. Finished students and ones who haven't typed yet are left out.
  The data is per-student times and exit codes from the achievements service (`GET /api/sensei/activity`, command text
  is never kept); Sensei and the service share Sensei's own gateway token as the key (`SENSEI_KEY` on the service).
  Facilitator-only: Sensei never nudges a student by itself.
- **Facilitator tab** (`/admin` -> Sensei): every PR with status, why, minutes stuck; Merge anyway,
  Comment, Look now, Pause. `SENSEI_ENABLED=0` starts it paused.
- Acts as the Forgejo admin account (comments are signed "Sensei"). Challenge PRs in students' own repos
  are never touched.
- Needs `git`, so it has its own small image (`Dockerfile`). Tests: `python3 -B -m unittest test_roster test_bot`.
