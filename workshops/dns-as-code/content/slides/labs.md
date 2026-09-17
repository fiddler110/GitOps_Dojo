---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/labs.css');
footer: '[&larr; Hub](index.md) &nbsp;|&nbsp; DNS as Code | Lab Overview'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# Lab Overview

## What each lab covers, before you dive in

Five short, self-contained labs. **Lab 1 is required** — it's the whole
workflow end to end. Labs 2-5 go deeper on one topic each, any order.

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

## The five labs

| Lab | Topic | Time | Required? |
| --- | ----- | ---- | --------- |
| **1** | Core workflow: preview → branch → edit → PR → CI → merge → verify | ~20 min | <span class="required">Yes — start here</span> |
| 2 | Editing/removing records, catching mistakes before you commit | ~12 min | Optional |
| 3 | `dnsctl.py` — the same workflow, one command per step | ~15 min | Optional |
| 4 | Investigating history and rolling back a merged change | ~10 min | Optional |
| 5 | Merge conflicts in `dnsconfig.js` | ~12 min | Optional |

---

<!-- _class: section-title -->

# Lab 1 — Required

## The core workflow, end to end

<div class="flow">
<span><b>1</b><br>branch</span>
<span>→</span>
<span><b>2</b><br>edit<br><small>dnsconfig.js</small></span>
<span>→</span>
<span><b>3</b><br>preview<br><small>local diff</small></span>
<span>→</span>
<span><b>4</b><br>PR<br><small>Forgejo</small></span>
<span>→</span>
<span><b>5</b><br>merge</span>
<span>→</span>
<span><b>6</b><br>push<br><small>CI applies it</small></span>
</div>

Add your own record by hand, preview it locally, open a PR, watch CI
comment the diff, merge, let CI apply it, then confirm with `dig`.

---

## Labs 2-5 — optional, any order

<div class="cards">
<div>
<h3>Lab 2 — Edit &amp; Remove</h3>
<p>Change and delete records, and catch the mistakes <code>preview</code> is built to catch.</p>
</div>
<div>
<h3>Lab 3 — dnsctl.py</h3>
<p>Same loop as Lab 1, wrapped into one command per step.</p>
</div>
<div>
<h3>Lab 4 — History &amp; Rollback</h3>
<p>Investigate what changed, when, and safely undo a merged change.</p>
</div>
<div>
<h3>Lab 5 — Merge Conflicts</h3>
<p>Two changes collide in <code>dnsconfig.js</code> — resolve it by hand.</p>
</div>
</div>

---

## Getting unstuck

- `dnscontrol preview` is your best friend here — same role `git status`
  played last session. Safe to run any time, changes nothing.
- Nothing here can break the shared zone for good — every change goes
  through a PR, and Lab 4 covers rollback.
- Stuck more than a minute or two? Ask the facilitator.

---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# Ready

## Open `~/lab/README.md` in your terminal and start with `lab1.md`

<p class="nav">Next: <a href="cheat-sheet.md">Cheat sheet &rarr;</a> &middot; <a href="index.md">&larr; Back to hub</a></p>
