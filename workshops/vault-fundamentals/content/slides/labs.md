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
| **2** | `pass`: encrypted secrets on your own machine, and where it stops | ~12 min |
| **3** | the shared vault: put, versions, delete vs destroy, the policy    | ~15 min |
| **4** | your namespace: an engine, a policy (UI, then code), a token      | ~15 min |

Everything stays in the class vault and your own terminal. Nothing is pushed anywhere.

---

## Part 3: Secrets in code, and Part 4: Secrets in git

| Lab   | You will                                                              | Time    |
| ----- | --------------------------------------------------------------------- | ------- |
| **5** | one app three ways: in the code, a `.env` file, the vault with `hvac` | ~15 min |
| **6** | OpenBao Agent logs in for the app; rotate a secret with no restart    | ~15 min |
| **7** | sops + transit: encrypted config in git, who can decrypt, key rotation | ~15 min |

Labs 6 and 7 work in your namespace (`students/<you>`); lab 6 reuses lab 4's `team/app` and `app-read`.

---

## Part 5: Secrets in pipelines

| Lab   | You will                                                                    | Time    |
| ----- | --------------------------------------------------------------------------- | ------- |
| **8** | fork the repo; a repository secret, masking, and who can really read it     | ~15 min |
| **9** | CI reads the vault: AppRole first, then the job's own OIDC token, no secret | ~20 min |

Your workflows run on **single-use runners**: each takes one job and is thrown away. git and `curl --netrc`
sign in with the Forgejo token your terminal came with: no password to type.

---

## Part 6: Secrets in deployments

| Lab    | You will                                                                        | Time    |
| ------ | ------------------------------------------------------------------------------- | ------- |
| **10** | deploy to app-host; CI delivers a wrapped, single-use secret ID, can't read | ~25 min |
| **11** | deploy to app-host; the app logs in with its platform identity, CI can't read   | ~20 min |
| **12** | *(optional)* database logins made on demand: lease, renew, revoke; the app's own | ~15 min |
| **13** | incident drill: a leaked token, the audit trail, revoke the tree, rotate        | ~15 min |

Your app is at `http://app-host:8080/<you>/` and on the **My App** card, with its log.
