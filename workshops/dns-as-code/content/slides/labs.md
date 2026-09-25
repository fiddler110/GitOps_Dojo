---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/labs.css');
footer: '[&larr; Labs](lab-index.md) &nbsp;|&nbsp; DNS as Code | Lab Overview'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Labs](lab-index.md)" -->

# Lab Overview

## What each lab covers, before you dive in

Two parts: **your own zone**, then **the shared zone, the company way**.
**Labs 1 and 3 are required**; the rest go deeper on one topic each.

<p class="nav">Keep <code>cheat-sheet.md</code> open in another tab while you work.</p>

---

## Before you start

```sh
whoami
dnscontrol version
dig -v
git --version
```

Preinstalled in your terminal: `dnscontrol`, `dig` (from `dnsutils`),
`git`, `python3` — nothing to install.

> Full detail lives in `~/lab/README.md` once you're in the terminal.

---

## The six labs

| Part | Lab | Topic | Time | Required? |
| --- | --- | ----- | ---- | --------- |
| 1: your zone | **1** | Preview, push, verify; add, edit, remove; catch mistakes | ~20 min | <span class="required">Yes — start here</span> |
| 1: your zone | 2 | Drift, and undoing your own changes | ~10 min | Optional |
| 2: shared zone | **3** | Branch → PR → CI preview → review → merge → CI applies | ~25 min | <span class="required">Yes</span> |
| 2: shared zone | 4 | `dnsctl.py` — the same process, one command per step | ~15 min | Optional |
| 2: shared zone | 5 | History and rolling back a merged change | ~10 min | Optional |
| 2: shared zone | 6 | Merge conflicts in `dnsconfig.js` | ~12 min | Optional |

---

<!-- _class: section-title -->

# Lab 1 — Required

## Your own zone: you run every step

<div class="flow">
<span><b>1</b><br>edit</span>
<span>→</span>
<span><b>2</b><br>preview</span>
<span>→</span>
<span><b>3</b><br>push<br><small>you</small></span>
<span>→</span>
<span><b>4</b><br>dig</span>
</div>

Create `<you>.dojo.test` from `~/lab/my-zone`, check it with `dig`, then
add, change and remove records, and catch a mistake before it's live.

---

<!-- _class: section-title -->

# Lab 3 — Required

## The shared zone: the process does the pushing

<div class="flow">
<span><b>1</b><br>branch</span>
<span>→</span>
<span><b>2</b><br>PR<br><small>CI previews</small></span>
<span>→</span>
<span><b>3</b><br>review<br><small>someone else</small></span>
<span>→</span>
<span><b>4</b><br>merge</span>
<span>→</span>
<span><b>5</b><br>push<br><small>CI only</small></span>
</div>

Change `dojo.test` through a PR: CI previews it, a classmate approves, and
only CI applies it. A push from your terminal is refused.

---

## Optional labs

<div class="cards">
<div>
<h3>Lab 2 — Drift &amp; Undo</h3>
<p>A dashboard edit meets the next push; undo a pushed change with <code>git revert</code>.</p>
</div>
<div>
<h3>Lab 4 — dnsctl.py</h3>
<p>Lab 3's process, wrapped into one command per step.</p>
</div>
<div>
<h3>Lab 5 — History &amp; Rollback</h3>
<p>Investigate what changed, when, and undo a merged change through a PR.</p>
</div>
<div>
<h3>Lab 6 — Merge Conflicts</h3>
<p>Two changes collide in <code>dnsconfig.js</code> — resolve it by hand.</p>
</div>
</div>

---

## Getting unstuck

- `dnscontrol preview` is your best friend here — same role `git status`
  played last session. Safe to run any time, changes nothing.
- You can't break anyone else's work: Part 1 is your own zone, and every
  change to the shared zone goes through a reviewed PR (Lab 5: rollback).
- Stuck more than a minute or two? Ask the facilitator.

---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Labs](lab-index.md)" -->

# Ready

## Open `~/lab/README.md` in your terminal and start with `lab1.md`

<p class="nav">Next: <a href="cheat-sheet.md">Cheat sheet &rarr;</a> &middot; <a href="lab-index.md">&larr; Back to labs</a></p>
