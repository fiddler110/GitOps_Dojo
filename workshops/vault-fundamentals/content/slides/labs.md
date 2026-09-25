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

---

## Part 3: Secrets in code, and Part 4: Secrets in git

| Lab   | You will                                                              | Time    |
| ----- | --------------------------------------------------------------------- | ------- |
| **4** | one app three ways: in the code, a `.env` file, the vault with `hvac` | ~15 min |
| **5** | OpenBao Agent logs in for the app; rotate a secret with no restart    | ~15 min |
| **6** | sops + transit: encrypted config in git, who can decrypt, key rotation | ~15 min |

Labs 5 and 6 work in your namespace (`students/<you>`); lab 5 reuses lab 3's `team/app` and `app-read`.

---

## Part 5: Secrets in pipelines

| Lab   | You will                                                                    | Time    |
| ----- | --------------------------------------------------------------------------- | ------- |
| **7** | fork the repo; a repository secret, masking, and who can really read it     | ~15 min |
| **8** | CI reads the vault: AppRole first, then the job's own OIDC token, no secret | ~20 min |

Your workflows run on **single-use runners**: each takes one job and is thrown away. Pushing asks for your
**Forgejo password** (on your landing page); lab 7 sets git to remember it, in memory, for an hour.
