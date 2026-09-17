# Workshop 1 Lab Plan — Hands-on Git Basics

Companion to [session-01-plan.md](session-01-plan.md), Part B.
**Duration:** ~30 minutes. Designed to be followed step-by-step, individually
or in pairs, with the facilitator walking the room.

**Structure:** Lab 1 is the instructor-led, must-run workflow from the
presentation. Lab 2 is an optional self-directed workshop for attendees who
want to practice recovery and investigation techniques. Keep Lab 2 available
as a follow-on activity; it does not displace Lab 1.

## Learning Outcomes

By the end of Lab 1, each attendee will have personally:
- Cloned a repo
- Created a branch
- Made and committed a change
- Pushed a branch and opened a pull request

Lab 2 gives interested attendees guided practice with stash/restore,
investigating history, reverting a shared change, and resolving a conflict.

## Prerequisites (pre-work, sent before the session)

- Git installed locally (`git --version` works).
- `git config --global user.name` / `user.email` set.
- Azure DevOps account with access to the facilitator's sample repository.
- If Azure DevOps access is unavailable, use the facilitator-provided
  temporary Git service described in the setup guide.
- A terminal and a text editor (VS Code recommended, but any editor works).

## Sample Repo Concept

A small, low-stakes "sandbox" repo created specifically for this training,
themed around something relatable to both engineering and ops — proposal:
a simple **team directory / on-call roster** in plain text or YAML, e.g.:

```
roster/
  team.yaml         # name, role, on-call rotation notes
  README.md
CONTRIBUTING.md      # 2-3 lines: "branch, commit, open a PR"
```

Rationale: everyone can make a trivial, understandable edit (add themselves
to the roster) without needing domain knowledge, so the lab stays focused on
git mechanics rather than the file format. (A DNS-flavored version of this
repo can be introduced in Session 3 once git basics are second nature.)

## Lab 1 — Core Workflow (Instructor Led, ~23 minutes)

### Exercise 1 — Clone (3 min)
```
git clone <sample-repo-url>
cd <sample-repo>
```
- Checkpoint: `git status` shows a clean working tree on `main`.

### Exercise 2 — Branch (3 min)
```
git checkout -b add-<yourname>
```
- Talking point: naming branches so others know whose work it is / what
  it's for.

### Exercise 3 — Make a Change (5 min)
- Open `roster/team.yaml`, add a line with your name/role.
- `git status` → see the file listed as modified.
- `git diff` → see exactly what changed before staging.

### Exercise 4 — Stage & Commit (5 min)
```
git add roster/team.yaml
git commit -m "Add <yourname> to team roster"
```
- Talking point: staging lets you choose exactly what goes into a commit,
  even if you have unrelated changes sitting in your working directory.

### Exercise 5 — Push & Open a Pull Request (7 min)
```
git push -u origin add-<yourname>
```
- Open the PR in the Azure DevOps portal.
- Facilitator demonstrates reviewing/approving one PR live, then merges it,
  narrating what reviewers typically look for.
- Everyone else's PRs get merged after the session (or facilitator merges a
  batch live if time allows) — avoid 15 people merging into `main`
  simultaneously during the lab.

### Lab 1 Checkpoint (2 minutes)
- Each attendee shows the facilitator or a partner:
  - `git status` on their personal branch.
  - `git log -1` showing their commit.
  - The URL of their pull request.
- Ask: "What changed locally at `git commit`, and what changed remotely at
  `git push`?"

## Lab 2 — Optional Git Recovery Workshop (Self Directed, ~15 minutes)

Start from a clean branch or a disposable clone. The facilitator should
provide a prepared branch or reset instructions so these exercises cannot
damage the shared `main` branch.

### Exercise 6 — Resolve a Merge Conflict
- Facilitator pre-stages a conflict: two attendees (or facilitator + one
  attendee) edit the *same line* of a shared file on two different branches
  and both attempt to merge into `main`.
- Walk through the conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) as a
  group, resolve together, commit the resolution.
- Key message: conflicts are normal, not scary, and git tells you exactly
  where to look.
- If time runs short, this becomes a live facilitator demo instead of an
  attendee exercise — decide in the room based on pace.

### Exercise 7 — Stash a Change (~3 min)
- Make an unrelated edit to `roster/team.yaml` (don't stage/commit it).
- `git stash` → `git status` shows a clean tree.
- `git stash pop` → the edit comes back.
- Talking point: this is the "I need to switch branches right now" escape
  hatch — no need to make a throwaway commit just to context-switch.

### Exercise 8 — Investigate & Undo (~5 min)
- `git log --oneline` on `main` → see the history of merged roster entries.
- `git blame roster/team.yaml` → identify who added a specific line and in
  which commit.
- `git show <commit>` on one of the merged commits → see exactly what it
  changed.
- Facilitator picks one already-merged commit and demonstrates
  `git revert <commit>` on a throwaway branch, opening a PR for the revert
  — reinforcing that `revert` (not `reset`) is the safe move once something
  is shared.
- If time is short, run this as a facilitator-led demo rather than an
  individual exercise.

### Lab 2 Wrap-up (2 minutes)
- Recap the loop: clone → branch → edit → status/diff → add → commit → push
  → PR → merge.
- Recap the "good-to-know" moves: stash to switch gears, `log`/`blame`/`show`
  to investigate, `revert` to safely undo something shared.
- Point to the cheat sheet for reference.
- Preview Session 2 (branching workflows/PRs in depth) and Session 3
  (DNS-as-code repo walkthrough).

## Facilitator Notes

- Keep a spare "rescue" branch/instructions ready for anyone who gets stuck
  (e.g. `git checkout main && git checkout -b add-<yourname>-retry`) rather
  than debugging deeply during the session — collect stuck people for a
  short follow-up instead of stalling the group.
- The Azure DevOps environment protects `main` by default. Verify the
  facilitator's sample repository inherits that policy before the session.
- Consider capping roster file conflicts by having each attendee add their
  line in a unique, agreed section (e.g. alphabetical by first name) to
  reduce *accidental* conflicts, since Exercise 6 already provides an
  intentional one.

## To Do Before This Lab Can Run

- [ ] Create and populate the actual Azure Repos sample repo per the
  "Sample Repo Concept".
- [ ] Verify the environment's default protection on `main` applies to the
  sample repo.
- [ ] Prepare a disposable clone or facilitator branches for Lab 2 conflict
  and revert exercises.
- [ ] Dry-run the lab timing with 1-2 colleagues before the real session.
