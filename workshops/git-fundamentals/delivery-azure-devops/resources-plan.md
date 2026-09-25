# Resources Plan — Cheat Sheet & Glossary

Reference materials to hand out alongside Session 1, so attendees don't need
to memorize anything during the live session.

## Cheat Sheet (to build)

One-page, command-focused, grouped to match the "everyday workflow" from the
session plan:

- **Setup (once):** `git config --global user.name`, `git config --global user.email`
- **Start work:** `git clone <url>`, `git pull`, `git checkout -b <branch>`
- **See what changed:** `git status`, `git diff`
- **Save work:** `git add <file>`, `git commit -m "<message>"`
- **Share work:** `git push -u origin <branch>`
- **Switch around:** `git checkout <branch>`, `git branch` (list), `git log --oneline`
- **Merge conflicts:** how to spot conflict markers, `git status` during a
  conflict, `git add` + `git commit` to finish a resolved merge, `git merge --abort`
  as an escape hatch.
- **Stash (switch gears without committing):** `git stash`, `git stash list`,
  `git stash pop`.
- **Undo / rollback, by stage:**
  - Uncommitted, unstaged: `git restore <file>`
  - Uncommitted, staged: `git restore --staged <file>`
  - Committed, not pushed: `git commit --amend`, `git reset` (local only)
  - Committed and pushed/shared: `git revert <commit>` (the safe default)
- **Investigate what happened:** `git log --oneline --graph`, `git log -p <file>`,
  `git show <commit>`, `git blame <file>`, `git diff <branch1>..<branch2>`,
  `git bisect` (find the commit that broke something).
- **"Oops" section (light touch for Session 1, expanded in a later session):**
  when to just ask for help instead of guessing, and why `revert` beats
  `reset`/force-push once something is shared.

## Glossary (to build)

Plain-English, one line each — reuse definitions from
[session-01-plan.md](session-01-plan.md) section 3, plus:
- Working directory / staging area / commit history (the three-stage model)
- `origin`, `HEAD`, `main`/`master`
- Stash — a shelf for uncommitted changes you're not ready to commit yet
- Revert vs. reset — undo by adding a new commit vs. moving the branch
  pointer back (only safe before something is shared)
- Bisect — binary search through history to find the commit that broke
  something
- Fast-forward vs. merge commit (brief, optional — only if time/interest)
- Fork (not part of the Azure Repos workflow for this session)

## Format & Distribution

- Single markdown file rendered to a PDF, or a pinned page in the team's
  wiki/internal docs — decide based on where the team already looks for
  reference material.
- Link from the sample repo's `README.md` so it's discoverable after the
  session, not just during it.

## Status

✅ **Complete** — See [cheat-sheet.md](cheat-sheet.md) for the built cheat sheet and glossary.

The document is formatted as a markdown file (ready to print to PDF, share via wiki, or display in the team's docs).

### Distribution

Print and hand out during the session, or share the link before/after:
- Link to cheat-sheet.md in the team wiki/docs.
- PDF: Use your browser's "Print to PDF" feature to create a printable version.
- Embed: Link from the sample repo's `README.md` so attendees can reference it after the session.
