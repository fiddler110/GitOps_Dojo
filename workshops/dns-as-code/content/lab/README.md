# DNS as Code Lab

Welcome! This is your personal workspace for the **DNS as Code** session. Everything here runs against a real, local Forgejo server and a real PowerDNS container, so the branches, commits, pull requests, and DNS records you create are real — not a simulation.

This lab builds directly on [Git Fundamentals](../../../git-fundamentals/) — same clone/branch/commit/push/PR flow you already know, applied to a `dnsconfig.js` file instead of a roster. If any of that git vocabulary is unfamiliar, that workshop's [cheat-sheet.md](../../../git-fundamentals/content/lab/cheat-sheet.md) is still a good reference.

You are working in your own student account. Keep all lab work under this `~/lab` folder.

## What you'll do

The session slides cover the *why*. This lab is the *how*, in two parts.

**Part 1: your own zone.** Every student has a zone of their own, `<your-username>.dojo.test` (yours is `studentXX.dojo.test`), in `~/lab/my-zone`. Nobody else's config touches it, so you can add, break, fix and delete records freely, and apply them yourself with `dnscontrol push`. This is where you learn how DNS as code works.

**Part 2: the shared zone, the company way.** `dojo.test` is the whole class's zone, standing in for a company's production DNS. Its config lives in the shared `dns-team/dns-as-code` repo, and **only CI can change it**: a `dnscontrol push` from your terminal is refused, and nobody can push to `main`. Every change goes through a branch, a pull request, an automatic preview, a review by someone else, and a merge, and then the pipeline applies it. This is where you learn the process around DNS as code.

**Every lab is part of the workshop.** Work through them in order: Part 1, then Part 2.

| Part | Lab | Topic | Time |
| ---- | --- | ----- | ---- |
| 1: your zone | [lab1.md](lab1.md) | Preview, push, verify; add, edit and remove records; catch mistakes | ~20 min |
| 1: your zone | [lab2.md](lab2.md) | Drift: when someone changes DNS outside the code, and undoing your own changes | ~10 min |
| 2: shared zone | [lab3.md](lab3.md) | The change process: branch, PR, CI preview, review, merge, CI apply | ~25 min |
| 2: shared zone | [lab4.md](lab4.md) | `dnsctl.py`: the same process, one command per step | ~15 min |
| 2: shared zone | [lab5.md](lab5.md) | Investigating history and rolling back a merged change | ~10 min |
| 2: shared zone | [lab6.md](lab6.md) | Merge conflicts in `dnsconfig.js` | ~12 min |

The **DNS Zones** page (a card on the workshop landing page) shows every zone and record PowerDNS is serving right now, and highlights what changed since you opened it. Keep it open in a tab and watch your changes land.

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
dnscontrol version
dig -v
git --version
```

Your username should look like `student01`, `student02`, and so on. `dnscontrol`, `dig` (from `dnsutils`), `git`, and `python3` are all preinstalled — nothing to download for this lab.

You're working from either **VS Code** (a browser-based editor with an integrated terminal) or a plain **Terminal** — whichever you opened from the workshop landing page. Every command in these labs works identically in either one.

The shell is `zsh`, with these helpers installed:

```sh
z <directory-fragment>  # jump to a recent matching directory
rg <text>               # search files with ripgrep
batcat <file>            # read a file with syntax highlighting
glow <file.md>           # read Markdown in the terminal
```

---

## 2. What "DNS as Code" means here

A `dnsconfig.js` file is the **source of truth** for a zone. You never edit records by hand anywhere else: `dnscontrol` reads the file and makes the `dns-server` (PowerDNS) container match it. That is always a two-step move:

| Step | Command | What it means |
| ---- | ------- | -------------- |
| Preview | `dnscontrol preview` | Dry-run diff between `dnsconfig.js` and live PowerDNS. Changes nothing, so it's safe to run any time, as often as you like. |
| Push | `dnscontrol push` | Applies that diff for real. |

Who runs `push` is the difference between the two parts:

| | Part 1: your zone | Part 2: the shared zone |
| --- | --- | --- |
| Zone | `<your-username>.dojo.test` | `dojo.test` |
| Config | `~/lab/my-zone/dnsconfig.js`, a local git repo | `dns-team/dns-as-code` on Forgejo, cloned to `~/lab/dns-as-code` |
| Who runs `dnscontrol push` | You | Only CI, after a reviewed merge to `main` |

```text
Part 1:  edit → preview → push → dig
Part 2:  edit → preview → branch/commit/push → pull request → CI preview comment
            → review and approve → merge → CI runs push → dig
```

---

## Getting unstuck

- `dnscontrol preview` is your best friend here, the same way `git status` was in Git Fundamentals — it always tells you exactly what would change before anything actually does.
- You can't break anyone else's work. Part 1 only touches your own zone, and in Part 2 every change to the shared zone is previewed, reviewed and applied by CI, and any merged change can be rolled back (Lab 5).
- If `dnscontrol preview` errors instead of showing a diff, read the message carefully — it's usually specific (e.g. a missing trailing dot on a `CNAME`/`MX` target).
- Stuck for more than a minute or two? Ask the facilitator — that's what they're walking the room for.

## Quick reference

```sh
dnscontrol preview          # what would change? (safe, no side effects)
dnscontrol push              # apply it (Part 1, your zone only)
dig @dns-server <name> A +short   # confirm a record is actually live
git status                   # what's changed locally?
git add / commit / push      # same as Git Fundamentals
```

See [cheat-sheet.md](cheat-sheet.md) for the full version of this, including record syntax, reading a `preview` diff, `dnsctl.py`, and merge conflicts.
