# DNS as Code Lab

Welcome! This is your personal workspace for the **DNS as Code** session. Everything here runs against a real, local Forgejo server and a real PowerDNS container, so the branches, commits, pull requests, and DNS records you create are real — not a simulation.

This lab builds directly on [Git Fundamentals](../../../git-fundamentals/) — same clone/branch/commit/push/PR flow you already know, applied to a `dnsconfig.js` file instead of a roster. If any of that git vocabulary is unfamiliar, that workshop's [cheat-sheet.md](../../../git-fundamentals/content/lab/cheat-sheet.md) is still a good reference.

You are working in your own student account. Keep all lab work under this `~/lab` folder.

## What you'll do

The session slides cover the *why*. This lab is the *how* — five short, self-contained labs. **Lab 1 is required** and covers the everyday DNS-as-code workflow end to end. Labs 2-5 are optional, go deeper on one topic each, and can be done in any order once Lab 1 is done.

| Lab | Topic | Time | Required? |
| --- | ----- | ---- | ---------- |
| [lab1.md](lab1.md) | The core workflow: preview → branch → edit → PR → CI → merge → verify | ~20 min | **Yes — start here** |
| [lab2.md](lab2.md) | Editing and removing records, and catching mistakes before you commit | ~12 min | Optional |
| [lab3.md](lab3.md) | `dnsctl.py` — the same workflow, one command per step | ~15 min | Optional |
| [lab4.md](lab4.md) | Investigating history and safely rolling back a merged change | ~10 min | Optional |
| [lab5.md](lab5.md) | Merge conflicts in `dnsconfig.js` | ~12 min | Optional |

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

`dnsconfig.js` is the **source of truth** for the `dojo.test` zone. You never edit records by hand anywhere else — `dnscontrol` reads that file and reconciles the `dns-server` (PowerDNS) container to match it. That reconciliation is always a two-step move:

| Step | Command | What it means |
| ---- | ------- | -------------- |
| Preview | `dnscontrol preview` | Dry-run diff between `dnsconfig.js` and live PowerDNS. Changes nothing — safe to run any time, as often as you like. |
| Push | `dnscontrol push` | Applies that diff for real. |

Every change to `dnsconfig.js` goes through the same loop:

```text
edit dnsconfig.js → preview (locally) → branch/commit/push → pull request
   → CI posts the preview diff as a comment → merge → CI runs push for you → verify with dig
```

Lab 1 walks through this loop once, end to end, by hand. Once it clicks, Labs 2-5 go deeper on specific pieces of it — editing/removing records safely, automating the loop with `dnsctl.py`, investigating and rolling back history, and resolving a conflict when two changes collide.

---

## Getting unstuck

- `dnscontrol preview` is your best friend here, the same way `git status` was in Git Fundamentals — it always tells you exactly what would change before anything actually does.
- Nothing in these labs can break the shared zone for good — every change goes through a pull request the facilitator (or CI) reviews before it's live, and any merged change can be rolled back (Lab 4).
- If `dnscontrol preview` errors instead of showing a diff, read the message carefully — it's usually specific (e.g. a missing trailing dot on a `CNAME`/`MX` target).
- Stuck for more than a minute or two? Ask the facilitator — that's what they're walking the room for.

## Quick reference

```sh
dnscontrol preview          # what would change? (safe, no side effects)
dnscontrol push              # apply it
dig @dns-server <name> A +short   # confirm a record is actually live
git status                   # what's changed locally?
git add / commit / push      # same as Git Fundamentals
```

See [cheat-sheet.md](cheat-sheet.md) for the full version of this, including record syntax, reading a `preview` diff, `dnsctl.py`, and merge conflicts.
