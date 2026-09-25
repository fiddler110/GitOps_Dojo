# DNS as Code — Take-Home Practice

Welcome back! This is a self-paced continuation of the **DNS as Code**
workshop, for practicing on your own time after the session ends. It's
the same five labs you saw in the workshop, adapted to run against your
own infrastructure instead of the workshop's temporary Forgejo + PowerDNS
containers.

This builds directly on [Git Fundamentals](../git-fundamentals/) — same
clone/branch/commit/push/PR flow, applied to a `dnsconfig.js` file
instead of a roster. If any of that git vocabulary is unfamiliar, do that
handout first, or keep its [cheat-sheet.md](../git-fundamentals/cheat-sheet.md)
handy as a reference.

## Before you start

Two setup guides, done in order:

1. **[00-github-setup.md](00-github-setup.md)** — create a free GitHub
   account and an empty practice repo.
2. **Pick a DNS backend:**
   - **[01-local-powerdns-stack.md](01-local-powerdns-stack.md)** — free,
     runs entirely on your own machine via Docker, using the same
     `dojo.test` reserved test zone from the workshop. **Do this one** —
     it covers every command in all five labs at no cost.
   - **[02-cloudflare-domain-setup.md](02-cloudflare-domain-setup.md)** —
     optional, more advanced: a real, purchased domain managed through a
     real, free Cloudflare account. Costs a small amount of money for the
     domain itself. Do this later, if you want the full production-like
     experience — it's not required to finish any of the five labs.

## What you'll do

**Lab 1 is the one to do first** — it covers the everyday DNS-as-code
workflow end to end. Labs 2-5 are optional deep dives, and can be done in
any order once Lab 1 is done.

| Lab | Topic | Time | Required? |
| --- | ----- | ---- | ---------- |
| [lab1.md](lab1.md) | The core workflow: preview → branch → edit → PR → merge → verify | ~20 min | **Start here** |
| [lab2.md](lab2.md) | Editing and removing records, and catching mistakes before you commit | ~12 min | Optional |
| [lab3.md](lab3.md) | `dnsctl.py` — the same workflow, one command per step | ~15 min | Optional |
| [lab4.md](lab4.md) | Investigating history and safely rolling back a merged change | ~10 min | Optional |
| [lab5.md](lab5.md) | Merge conflicts in `dnsconfig.js` | ~12 min | Optional |

Keep [cheat-sheet.md](cheat-sheet.md) open in a split pane or another tab
while you work — it's a condensed reference to every command used across
all five labs.

## What's different from the workshop

- **You're on GitHub, not Forgejo**, and (with the local PowerDNS path)
  **there's no CI automatically running `dnscontrol push` on merge** — a
  cloud-hosted GitHub Actions runner has no route to a PowerDNS container
  running on your own laptop. You run `dnscontrol push` yourself after
  merging instead. Full explanation in
  [01-local-powerdns-stack.md](01-local-powerdns-stack.md).
- **`dnsctl.py` still works** — it auto-detects GitHub vs. Forgejo from
  your repo's remote and uses the `gh` CLI accordingly. See
  [lab3.md](lab3.md).
- **You review and merge your own pull requests** — practicing solo,
  reading the diff carefully before you merge is still the point of the
  step, even without a facilitator.
- **`dig` targets are different.** The workshop used `@dns-server`; the
  local stack uses `@127.0.0.1 -p 5353`; the real-Cloudflare path needs
  no special target at all. Each lab and the cheat sheet call this out.

## Getting unstuck

- `dnscontrol preview` is still your best friend — it always tells you
  exactly what would change before anything actually does.
- The local PowerDNS stack is disposable — worst case, `docker compose
  down && docker compose up -d` gives you a clean slate, and
  `dnscontrol push` repopulates it from `dnsconfig.js`.
- If `dnscontrol preview` errors instead of showing a diff, read the
  message carefully — it's usually specific (e.g. a missing trailing dot
  on a `CNAME`/`MX` target).
- <https://docs.dnscontrol.org/> for dnscontrol's own docs.

## Quick reference

```sh
dnscontrol preview          # what would change? (safe, no side effects)
dnscontrol push              # apply it
dig @127.0.0.1 -p 5353 <name> A +short   # confirm a record is actually live (local stack)
git status                   # what's changed locally?
git add / commit / push      # same as Git Fundamentals
```

See [cheat-sheet.md](cheat-sheet.md) for the full version.
