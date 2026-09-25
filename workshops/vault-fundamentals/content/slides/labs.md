---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/labs.css');
footer: '[&larr; Labs](lab-index.md) &nbsp;|&nbsp; Vault Fundamentals | Lab Overview'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Labs](lab-index.md)" -->

# Lab Overview

## What each lab covers, before you dive in

**Do them in order:** each one uses what the last one showed you.

<p class="nav">Keep <code>cheat-sheet.md</code> open in another tab while you work.</p>

---

## Before you start

```bash
whoami           # studentNN
bao status       # Sealed: false
bao token lookup # already signed in: no password
```

Open the **Vault** card on your landing page too. The first time, Forgejo asks you to **Authorize** OpenBao: click it once.

---

## Part 1: Foundations, and Part 2: your own vault

| Lab   | You will                                                          | Time    |
| ----- | ----------------------------------------------------------------- | ------- |
| **0** | sign in (browser and terminal), read your token, find your secret | ~8 min  |
| **1** | leak a token into git, find it, block the next one with gitleaks  | ~12 min |
| **2** | the shared vault: put, versions, delete vs destroy, the policy    | ~15 min |
| **3** | your namespace: an engine, a policy (UI, then code), a token      | ~15 min |

Everything stays in the class vault and your own terminal. Nothing is pushed anywhere.
