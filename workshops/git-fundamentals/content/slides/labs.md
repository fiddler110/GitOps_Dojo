---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/labs.css');
footer: '[&larr; Labs](lab-index.md) &nbsp;|&nbsp; Git Fundamentals | Lab Overview'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Labs](lab-index.md)" -->

# Lab Overview

## What each lab covers, before you dive in

Five short, self-contained labs. **Lab 1 is required** — it's the whole
workflow end to end. Labs 2-5 go deeper on one topic each, any order.

<p class="nav">Keep <code>cheat-sheet.md</code> open in another tab while you work.</p>

---

## Before you start

```sh
whoami
git --version
git config --global user.name
git config --global user.email
```

Your Git identity is pre-configured to match your student account —
nothing to set up yourself.

> Full detail lives in `~/lab/README.md` once you're in the terminal.

---

## The five labs

| Lab | Topic | Time | Required? |
| --- | ----- | ---- | --------- |
| **1** | Core workflow: clone → branch → edit → commit → push → PR | ~15 min | <span class="required">Yes — start here</span> |
| 2 | Reviewing changes and undoing mistakes before you commit | ~10 min | Optional |
| 3 | Stashing — switching gears without committing | ~8 min | Optional |
| 4 | Investigating history: log, blame, show | ~10 min | Optional |
| 5 | Merge conflicts and safely undoing a shared change | ~12 min | Optional |

---

<!-- _class: section-title -->

# Lab 1 — Required

## The core workflow, end to end

<div class="flow">
<span><b>1</b><br>clone</span>
<span>→</span>
<span><b>2</b><br>branch</span>
<span>→</span>
<span><b>3</b><br>edit</span>
<span>→</span>
<span><b>4</b><br>status/diff</span>
<span>→</span>
<span><b>5</b><br>add + commit</span>
<span>→</span>
<span><b>6</b><br>push → PR</span>
</div>

Clone the repo, branch, edit a file, review with `status`/`diff`, stage
and commit, push, and open a pull request into `main`.

---

## Labs 2-5 — optional, any order

<div class="cards">
<div>
<h3>Lab 2 — Review &amp; Undo</h3>
<p>Catch and undo a mistake before it's ever committed.</p>
</div>
<div>
<h3>Lab 3 — Stashing</h3>
<p>Switch branches mid-change without committing half-done work.</p>
</div>
<div>
<h3>Lab 4 — History</h3>
<p><code>log</code>, <code>blame</code>, <code>show</code> — find out what changed, when, and why.</p>
</div>
<div>
<h3>Lab 5 — Merge Conflicts</h3>
<p>Two branches collide — resolve it, then safely undo a shared change.</p>
</div>
</div>

---

## Getting unstuck

- `git status` is your best friend — it always tells you where you are
  and what to do next.
- Nothing here can break the shared `main` branch — you're always on your
  own branch, and merges go through a reviewed pull request.
- Stuck more than a minute or two? Ask the facilitator.

---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Labs](lab-index.md)" -->

# Ready

## Open `~/lab/README.md` in your terminal and start with `lab1.md`

<p class="nav">Next: <a href="cheat-sheet.md">Cheat sheet &rarr;</a> &middot; <a href="lab-index.md">&larr; Back to labs</a></p>
