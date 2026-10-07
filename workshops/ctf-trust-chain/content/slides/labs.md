---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/labs.css');
footer: '[&larr; Labs](lab-index.md) &nbsp;|&nbsp; CTF-4: Trusting the Wrong Thing | Lab Overview'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Labs](lab-index.md)" -->

# Lab Overview

## Two independent targets, pick any order

Each lab is a self-contained target you start from the **Attack Range** card. They don't build on each
other -- do them in any order, and start fresh for each one when you're ready.

<p class="nav">Keep <a href="cheat-sheet.md">the cheat sheet</a> open in another tab while you work.</p>

---

## The labs

| Lab | Target | Topic | Time |
| --- | ------ | ----- | ---- |
| **1** | Internal DNS-backed agent | A real CVE in a pinned-old resolver's transaction IDs -- two flags | ~45 min |
| **2** | Cloud resource policy | A rule with no bug, just the wrong logic | ~40 min |

Budget ~85 minutes for both, on top of the session's `nmap`/Linux primer.

---

## How to work each one

1. Start the target from the **Attack Range** card and note your slot's IP.
2. `nmap` it -- every target publishes more than one port, some real, some decoys.
3. Investigate using the lab's guiding questions, not the exploit guide.
4. Stuck after a real attempt? Each lab's last line points at that target's exploit guide.
5. `dojo-flag submit <target-id> '<flag>'` -- Lab 1 needs this **twice**, once per flag.

---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Labs](lab-index.md)" -->

# Ready

## Open `~/lab/README.md` in your terminal and start with `lab1.md`

<p class="nav"><a href="lab-index.md">&larr; Back to labs</a></p>
