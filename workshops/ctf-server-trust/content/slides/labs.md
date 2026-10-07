---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/labs.css');
footer: '[&larr; Labs](lab-index.md) &nbsp;|&nbsp; CTF-2: Server-side Trust and APIs | Lab Overview'
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
| **1** | Network diagnostics page | A "run this command for me" page that trusts what you type a little too much | ~30 min |
| **2** | URL preview feature | A "fetch this for me" feature that trusts where you point it | ~30 min |
| **3** | Accounts API | A profile update that trusts every field in your request body | ~30 min |
| **4** | Internal ops API | An admin route that trusts "logged in", not "who" | ~30 min |

Budget ~150 minutes for all four, including scanning and setup.

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
