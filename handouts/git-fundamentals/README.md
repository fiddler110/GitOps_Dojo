# Git Fundamentals — Take-Home Practice

Welcome back! This is a self-paced continuation of the **Git Fundamentals**
workshop, for practicing on your own time against your own free GitHub
account instead of the workshop's temporary Forgejo server. Everything
here is the same five labs you saw in the session, adapted so they work
against a real repo you control.

If you didn't finish all five labs during the workshop, or want to redo
them from scratch to cement the workflow, this is built for exactly that.

## Before you start

Read [`00-github-setup.md`](00-github-setup.md) first — it walks through
signing up for a free GitHub.com account, installing Git locally, and
creating your own practice repository. It takes about 10 minutes and you
only need to do it once.

## What you'll do

**Lab 1 is the one to do first** — it covers the everyday workflow end to
end. Labs 2-5 are optional deep dives on one topic each, and can be done
in any order.

| Lab | Topic | Time | Required? |
| --- | ----- | ---- | ---------- |
| [lab1.md](lab1.md) | The core workflow: clone → branch → edit → commit → push → pull request | ~15 min | **Start here** |
| [lab2.md](lab2.md) | Reviewing changes and undoing mistakes before you commit | ~10 min | Optional |
| [lab3.md](lab3.md) | Stashing — switching gears without committing | ~8 min | Optional |
| [lab4.md](lab4.md) | Investigating history: log, blame, show | ~10 min | Optional |
| [lab5.md](lab5.md) | Merge conflicts and safely undoing a shared change | ~12 min | Optional |

Keep [cheat-sheet.md](cheat-sheet.md) open in a split pane or another tab
while you work — it's a condensed reference to every command used across
all five labs.

## What's different from the workshop

- **You're on GitHub, not Forgejo.** Same git commands throughout — clone,
  branch, commit, push are identical. Only the "open a pull request" step
  looks different (GitHub's web UI instead of the "Open Forgejo" button),
  and pull requests are covered in [00-github-setup.md](00-github-setup.md)
  and each lab.
- **You review and merge your own pull requests.** In the workshop, a
  facilitator did this. Practicing solo, you'll merge your own — reading
  the diff carefully before you do is still the whole point of the step.
- **Your git identity isn't pre-configured.** [00-github-setup.md](00-github-setup.md)
  covers setting it once.
- **The workshop's terminal helpers** (`z`, `rg`, `batcat`, `glow`) are
  conveniences, not requirements — see [00-github-setup.md](00-github-setup.md)
  for optional installs, or just use your normal terminal and editor.

## Getting unstuck

- `git status` is still your best friend — it always tells you where you
  are and what to do next.
- You can't break anything that matters — this is your own private
  practice repo. If something goes sideways, worst case you delete the
  repo and start over from [00-github-setup.md](00-github-setup.md).
- If a command errors, read the error message — git's errors are usually
  specific about what to do next.
- The official docs at <https://git-scm.com/doc> and GitHub's own guides
  at <https://docs.github.com/> are good places to dig deeper.

## Quick reference

```sh
git status                 # what's changed?
git diff                   # exact changes, unstaged
git add <file>              # stage a file
git commit -m "message"     # save a snapshot
git push                    # send commits to the remote
git log --oneline           # recent history, one line each
```

See [cheat-sheet.md](cheat-sheet.md) for the full version, including
undoing changes, stashing, conflicts, and investigating history.
