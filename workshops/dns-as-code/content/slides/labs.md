---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Manrope:wght@400;600;700&display=swap');
  :root {
    --canvas: #111820;
    --surface: #18242e;
    --surface-raised: #21313c;
    --line: #38505d;
    --text: #e8f0f2;
    --muted: #a9bac2;
    --teal: #3dd6c3;
    --teal-deep: #137f7a;
    --blue: #69aee8;
    --amber: #f0b95b;
  }
  section {
    background:
      linear-gradient(135deg, rgba(61, 214, 195, 0.05), transparent 42%),
      var(--canvas);
    color: var(--text);
    font-family: 'Manrope', sans-serif;
    font-size: 28px;
    padding: 54px 68px;
  }
  section::after {
    color: var(--muted);
    font-size: 18px;
  }
  h1, h2, h3 { color: var(--text); letter-spacing: 0; }
  h1 { font-size: 54px; }
  h2 { border-bottom: 4px solid var(--teal); padding-bottom: 8px; }
  h3 { color: var(--blue); }
  strong { color: var(--teal); }
  a { color: var(--teal); }
  li::marker { color: var(--teal); }
  code {
    background: var(--surface-raised);
    color: #b8f4ea;
    font-family: 'IBM Plex Mono', monospace;
  }
  pre {
    background: #0a1117;
    border: 1px solid var(--line);
    border-left: 7px solid var(--teal);
    border-radius: 4px;
    box-shadow: 0 12px 30px rgba(0, 0, 0, 0.22);
    color: var(--text);
    font-size: 23px;
  }
  pre code { background: transparent; color: inherit; }
  blockquote {
    background: rgba(61, 214, 195, 0.08);
    border-left: 7px solid var(--teal);
    color: var(--text);
    font-size: 32px;
    font-weight: 600;
    padding: 16px 24px;
  }
  table {
    background: var(--surface);
    border: 1px solid var(--line);
    font-size: 24px;
  }
  th, td { color: var(--text); }
  th { background: var(--surface-raised); color: var(--teal); }
  td { background: var(--surface); border-color: var(--line); }
  tr:nth-child(even) { background: rgba(105, 174, 232, 0.05); }
  .lead {
    background:
      linear-gradient(125deg, rgba(19, 127, 122, 0.34), transparent 55%),
      #0c131a;
    color: var(--text);
    text-align: left;
  }
  .lead h1, .lead h2 { color: var(--text); }
  .lead strong { color: var(--teal); }
  .lead h1 { border-bottom: 7px solid var(--teal); padding-bottom: 18px; }
  .section-title {
    background:
      linear-gradient(135deg, rgba(61, 214, 195, 0.14), transparent 50%),
      var(--surface);
    color: var(--text);
  }
  .section-title h1, .section-title h2 { color: var(--text); }
  .section-title h1 { border-left: 9px solid var(--teal); padding-left: 28px; }
  .flow {
    align-items: center;
    display: flex;
    gap: 12px;
    justify-content: center;
    margin-top: 40px;
  }
  .flow span {
    background: var(--surface);
    border: 2px solid var(--line);
    border-top: 5px solid var(--teal);
    border-radius: 6px;
    box-shadow: 0 12px 24px rgba(0, 0, 0, 0.18);
    padding: 18px 12px;
    text-align: center;
  }
  .flow b { color: var(--amber); font-size: 34px; }
  .flow small { color: var(--muted); }
  .required { color: var(--amber); font-weight: 700; }
  .cards {
    display: grid;
    gap: 20px;
    grid-template-columns: 1fr 1fr;
    margin-top: 30px;
  }
  .cards > div {
    background: var(--surface);
    border: 1px solid var(--line);
    border-left: 6px solid var(--blue);
    border-radius: 6px;
    padding: 18px 22px;
  }
  .cards h3 { margin: 0 0 6px; }
  .cards p { color: var(--muted); font-size: 22px; margin: 0; }
  .nav { color: var(--muted); font-size: 20px; margin-top: 50px; }
  footer { color: var(--muted); font-size: 16px; }
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
