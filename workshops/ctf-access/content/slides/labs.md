---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/labs.css');
footer: '[&larr; Labs](lab-index.md) &nbsp;|&nbsp; CTF-1: Access and Identity | Lab Overview'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Labs](lab-index.md)" -->

# Lab Overview

## Four independent targets, pick any order

Each lab is a self-contained target you start from the **Attack Range** card. They don't build on each
other -- do them in any order, and start fresh for each one when you're ready.

<p class="nav">Keep <a href="cheat-sheet.md">the cheat sheet</a> open in another tab while you work.</p>

---

## The labs

| Lab | Target | Topic | Time |
| --- | ------ | ----- | ---- |
| **1** | Staff login portal | A login form that trusts its input a little too much | ~25 min |
| **2** | Password self-service | A reset flow that's guessable, not just forgettable | ~25 min |
| **3** | Support ticket archive | An old ticket anyone can ask for, by number | ~30 min |
| **4** | Internal ops API | A certificate check that checks less than it looks like | ~30 min |

Budget ~130 minutes for all four, on top of the session's `nmap`/Linux primer.

---

## How to work each one

1. Start the target from the **Attack Range** card and note your slot's IP.
2. `nmap` it -- every target publishes more than one port, some real, some decoys.
3. Investigate using the lab's guiding questions, not the exploit guide.
4. Stuck after a real attempt? Each lab's last line points at that target's exploit guide.
5. `dojo-flag submit <target-id> '<flag>'`.

---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Labs](lab-index.md)" -->

# Ready

## Open `~/lab/README.md` in your terminal and start with `lab1.md`

<p class="nav"><a href="lab-index.md">&larr; Back to labs</a></p>
