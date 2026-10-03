---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/labs.css');
footer: '[&larr; Labs](lab-index.md) &nbsp;|&nbsp; Cloud Policy as Code | Lab Overview'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Labs](lab-index.md)" -->

# Lab Overview

## What each lab covers, before you dive in

Thirteen labs and a capstone. **Do them in order:** each one builds on the last.

<p class="nav">Keep <code>cheat-sheet.md</code> open in another tab while you work.</p>

---

## Before you start

```sh
whoami
tofu version
opa version
conftest --version
```

Preinstalled in your terminal: `tofu`, `opa`, `conftest`, `git`. Nothing to install, and the lab has no internet: `init` works from a local copy of the provider.

> Full detail lives in `~/lab/README.md` once you're in the terminal. Each lab is a file next to it: `lab0.md` … `lab12.md`.

---

## Expect slow applies

Creating or destroying a policy definition or assignment takes **about 100 seconds** each, in parallel, so one apply with several of them takes **about 3.5 minutes**. That is the provider waiting for the cloud to settle, not a hang. Each lab is built around one policy apply and tells you what to read while it runs.

---

## The labs

| Lab | Topic |
| --- | ----- |
| **0** | Setup: fork, clone, CI secrets, deploy the app |
| **1** | Why guardrails: the 403 and the Policy blade |
| **2** | Anatomy of a definition: if, then, scope |
| **3** | Your first policy as code: costCenter tag |
| **4** | Audit and compliance: audit before deny |
| **5** | Parameters and reuse: one definition, two assignments |
| **6** | Policy sets: bundle the baseline |
| **7** | Modify and remediation |
| **8** | Exemptions, with an expiry |
| **9** | Shift left with Rego and conftest |
| **10** | Testing policies: `opa test`, fix a planted bug |
| **11** | Policy in the pipeline: PR checks, merge, apply |
| **12** | Drift, and the capstone |

---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Labs](lab-index.md)" -->

# Ready?

## Open `~/lab/README.md` in your terminal and start with Lab 0

Stuck? Ask. A denied apply is **the point**, not a mistake: read the message, fix the file.
