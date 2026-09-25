# Git Training Lab

Welcome! This is your personal workspace for the **Git Fundamentals** session. Everything here runs against a real, local Forgejo server, so the branches, commits, and pull requests you create are real — not a simulation.

You are working in your own student account. Keep all lab work under this `~/lab` folder.

## What you'll do

The session slides cover the *why*. This lab is the *how* — five short, self-contained labs. **Lab 1 is required** and covers the everyday workflow end to end. Labs 2-5 are optional, go deeper on one topic each, and can be done in any order if you have time left after Lab 1.

| Lab | Topic | Time | Required? |
| --- | ----- | ---- | ---------- |
| [lab1.md](lab1.md) | The core workflow: clone → branch → edit → commit → push → pull request | ~15 min | **Yes — start here** |
| [lab2.md](lab2.md) | Reviewing changes and undoing mistakes before you commit | ~10 min | Optional |
| [lab3.md](lab3.md) | Stashing — switching gears without committing | ~8 min | Optional |
| [lab4.md](lab4.md) | Investigating history: log, blame, show | ~10 min | Optional |
| [lab5.md](lab5.md) | Merge conflicts and safely undoing a shared change | ~12 min | Optional |

**Starting partway through?** Run `lab-prep <N>` in the terminal to set up what lab N needs from the earlier labs (for example `lab-prep 4`). It's safe to run more than once and never undoes your own work.

Keep [cheat-sheet.md](cheat-sheet.md) open in a split pane or another tab while you work — it's a condensed reference to every command used across all five labs, with a short explanation of how each one works.

Your terminal runs inside `tmux`, which is what lets you open that split pane in the first place (`Ctrl+b %`) — see [tmux-guide.md](tmux-guide.md) for that and a few other handy shortcuts. None of it is required for the labs.

Open any lab file (or the cheat sheet) with:

```sh
glow lab1.md   # or: nano lab1.md, batcat lab1.md, etc.
```

---

## 1. Check your shell

```sh
whoami
pwd
git --version
git config --global user.name
git config --global user.email
```

Your username should look like `student01`, `student02`, and so on. Your Git identity is pre-configured to match it — you don't need to set `user.name`/`user.email` yourself.

You're working from either **VS Code** (a browser-based editor with an integrated terminal) or a plain **Terminal** — whichever you opened from the workshop landing page. Every command in these labs works identically in either one; use whichever terminal is in front of you.

The shell is `zsh`, with these helpers installed:

```sh
z <directory-fragment>  # jump to a recent matching directory
rg <text>              # search files with ripgrep
batcat <file>          # read a file with syntax highlighting
glow <file.md>         # read Markdown in the terminal
```

### Optional: your own shortcuts

You'll type `git status` a lot. Your `~/.zshrc` is shared and read-only, but `~/.zshrc_aliases` is yours: every new shell loads it last, so anything you put there sticks for the rest of the session. Add a few short aliases:

```sh
echo 'alias gs="git status"' >> ~/.zshrc_aliases
echo 'alias gd="git diff"' >> ~/.zshrc_aliases
echo 'alias gl="git log --oneline --graph"' >> ~/.zshrc_aliases
source ~/.zshrc_aliases   # load them into this shell now
```

Now `gs` does the same as `git status`:

```sh
gs
aliases   # list everything in ~/.zshrc_aliases
```

You can also open the file in VS Code or `nano ~/.zshrc_aliases` and edit it directly; run `source ~/.zshrc_aliases` (or open a new terminal) afterwards. The labs spell out the full `git` commands so you learn them, but use your shortcuts wherever you like.

---

## 2. The workflow you're about to practice

This is the loop you'll use for basically all of your day-to-day git work, not just this lab:

```text
clone → branch → edit → status/diff → add → commit → push → pull request → merge
```

| Step | Command | What it means |
| ---- | ------- | -------------- |
| Clone | `git clone <url>` | Download the full repo, with its whole history, to your machine. Once per repo. |
| Branch | `git checkout -b <name>` | Start an independent line of work so you don't edit `main` directly. |
| Edit | *(your editor)* | Change files in your working directory. |
| Review | `git status`, `git diff` | See what changed before you commit it. |
| Stage | `git add <file>` | Mark exactly which changes go into the next commit. |
| Commit | `git commit -m "..."` | Save a snapshot of the staged changes, with a message explaining why. |
| Push | `git push` | Upload your commits to the shared Forgejo server. |
| Pull request | *(in Forgejo)* | Ask a teammate (here, the facilitator) to review before merging. |
| Clean up | `git fetch --prune`, `git branch -d <name>` | Once merged, drop the stale remote-tracking branch and your local branch. |

Lab 1 walks through every step of this loop once, in order. Once it clicks, the rest of the labs are about the "escape hatches" — what to do when you need to switch context, made a mistake, or need to understand history.

---

## Getting unstuck

- `git status` is your best friend — it always tells you where you are and what to do next.
- Nothing in these labs can break the shared `main` branch — you're always working on your own branch, and merges into `main` go through a pull request the facilitator reviews.
- If a command errors and you're not sure why, read the error message out loud — git's error messages usually say exactly what to do next (e.g. "use `git pull` before pushing again").
- Stuck for more than a minute or two? Ask the facilitator — that's what they're walking the room for.

## Quick reference

```sh
git status                 # what's changed?
git diff                   # exact changes, unstaged
git add <file>              # stage a file
git commit -m "message"     # save a snapshot
git push                    # send commits to the remote
git log --oneline           # recent history, one line each
```

See [cheat-sheet.md](cheat-sheet.md) for the full version of this, including undoing changes, stashing, conflicts, and investigating history.
