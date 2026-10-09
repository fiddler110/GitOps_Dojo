# git-fundamentals — facilitator guide

For the person running the session. The technical reference is [`README.md`](README.md); the deck's
speaker notes carry the talking points. This guide is the practical part: before, during, after, and
what to do when something breaks.

**Honest status:** the simplest pack — content only, no overlay, the engine as-is. Exercised end to end
with the demo bots and the student-reset live pass; the per-lab times below are the labs' own estimates
(`content/lab/README.md`), not measured against a room. Do the rehearsal.

## The session at a glance (about 60 minutes)

| Block | Minutes | What |
| ----- | ------- | ---- |
| Talk | ~10 | Why version control, the everyday workflow, pull requests. *A guess until a dry run.* |
| Lab 1 | ~15 | The core workflow: clone → branch → edit → commit → push → PR. Adds themselves to `roster/team.yaml` |
| Labs 2-5 | ~40 | 10 + 8 + 10 + 12. Reviewing/undoing, stashing, history (log/blame/show), merge conflicts |
| Recap | ~5 | What surprised them (usual: rebase vs merge, what a PR really is) |

**Every lab is mandatory and they build in order** (Lab 1 first, then 2-5 go deeper each). In a shorter
slot, Lab 1 alone is the whole everyday workflow; drop from Lab 5 back.

**Sensei (the only module here)** auto-merges the Lab 1 roster PR: a student adds their entry to
`roster/team.yaml`, opens a PR, and Sensei reviews it against the rules (allowed files, YAML parses,
their own entry present, nothing else removed) and merges a good one with a friendly comment, flags a bad
one. The `/admin` **Sensei** tab lists every roster PR (merged, waiting, failing and why) with **merge
anyway** and **comment**. Challenge PRs are never touched.

## Before the session

**A day ahead**

1. `./dojo setup` if there is no `.env` (or `--default` for the stock
   `student`/`student123`, `admin`/`admin` logins). It must carry `PUBLIC_BASE_URL` (what students type,
   including the port if not 80/443) and `GATEWAY_TOKEN`. Set `STUDENT_COUNT`.
2. **No password to announce.** Each student's terminal is signed in to Forgejo with their own token, so
   no lab asks for one. If you ever need it, **Password** on the student's Roster tile shows it.
3. Build and start: `./dojo git-fundamentals`. Open `/admin` and check the status strip (top right):
   **Forgejo**, **Terminals** and **Slides** green (Ready). Terminals is the slowest — it is creating every
   student account — so yellow there for up to a minute is normal, not a fault.
4. **Size the machine:** `./dojo capacity git-fundamentals --students 30`. This pack adds no backend, so
   it is the lightest of the series; the terminals are the whole memory line.
5. **Rehearse as a student.** Open the landing page in a private window — you get a real student account,
   the same experience the room will have. Do Lab 1, confirm the roster PR is auto-merged by Sensei and
   appears on the `/admin` Sensei tab, then `./dojo stop` and start clean. (Your facilitator workspace
   never takes a student slot, so it does not show what students see.)
6. Skim the deck once with its speaker notes on.

**On the day, 15 minutes before**

- Start the stack, then confirm `/` (landing page cards: VS Code, Terminal, Forgejo, Slides), `/slides`
  and `/admin` (strip all green).
- Keep `/admin` on a second screen: the **Roster** is a live view of every student's terminal.

## During the session

**What you can see.** `/admin` tabs: Roster (every student's live terminal), VS Code, Terminal, Forgejo,
Slides, and **Sensei** (roster-PR status). The status strip (facilitator only; students never see service
health) is one chip per service — green **Ready**, yellow **Starting**, red **Down** (hover for the reason).

- **Lagging student:** `lab-prep <N>` in their terminal sets up what lab N needs from the earlier ones.
  It is safe to re-run and never undoes their own work.
- **Merge conflicts (Lab 5)** are the step people get stuck on. It is deliberately the hardest lab; expect
  questions, and that a wall of "conflict" messages is the lesson, not a fault.
- **Achievements** (if `ACHIEVEMENTS_ENABLED`): toasts on every surface, a class leaderboard on the landing
  page and an `/admin` tab. Off by default; nothing extra loads when off.

**Updating content mid-session.** Slide and lab files are bind-mounted: edits to `content/slides/` show up
immediately; a new file in `content/lab/` reaches students' `~/lab` on their next terminal restart, and a
file a student has already edited is never overwritten.

## When something breaks

| Symptom | Likely cause and fix |
| ------- | -------------------- |
| `git push` asks for a password | The token is missing from `~/.git-credentials` (`ls -l` to check). As a stop-gap, **Password** on their Roster tile shows the Forgejo password to type |
| `git push` rejected, or it goes to `training/sample-training-repo` | They cloned the team repo instead of their own copy. Check `git remote -v` in the repo |
| Roster PR never merges | The **Sensei** tab says why (wrong file, YAML doesn't parse, entry missing). Fix the PR, or **merge anyway** if the content is fine |
| One student's terminal is wedged | `/admin` Roster, **Release** on their tile; their next visit reassigns an account (the same one if still free) |
| Student has made a mess of their repo | Roster tile → **Reset** puts them back to stack-start (optionally clearing their achievements/score), keeps the seat |
| Terminals chip stays yellow/red | Account creation is slow on first start; give it a minute. If still red, `./dojo logs web-terminal \| tail -40` |

## After the session

- `./dojo stop` wipes everything: every container and volume, all accounts and repos. Nothing is kept.
- If you learned something (a lab step that confused people, a timing that was wrong, a failure not in the
  table above), note it in `ROADMAP.md` (Manual checks) and fix the lab.
