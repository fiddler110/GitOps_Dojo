---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/labs.css');
footer: '[&larr; Labs](lab-index.md) &nbsp;|&nbsp; OpenTofu Basics | Lab Overview'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Labs](lab-index.md)" -->

# Lab Overview

## What each lab covers, before you dive in

Eleven short labs in two tracks. **Do them in order:** each one builds on the last, and nothing is destroyed until Lab 3 (Track A) and Lab 10 (Track B).

<p class="nav">Keep <code>cheat-sheet.md</code> open in another tab while you work.</p>

---

## Before you start

```sh
whoami
tofu version
terraform version
git --version
```

Preinstalled in your terminal: `tofu` (and `terraform`, which **is** `tofu`), `git`. Nothing to install, and the lab has no internet: that's why `init` works from a local copy of the providers.

> Full detail lives in `~/lab/README.md` once you're in the terminal. Each lab is a file next to it: `lab0.md` … `lab10.md`.

---

## Track A: the sandbox (~37 min)

Everything happens inside your terminal: OpenTofu makes a random name, a text file and a note in its own state.

| Lab | Topic | Time |
| --- | ----- | ---- |
| **0** | Clone the repo, tour every file, `terraform` = `tofu` | ~5 min |
| **1** | `init`, `validate`, `plan`, `apply`: your first run | ~12 min |
| **2** | Change a value, read the plan (`~`, `-/+`), state and outputs | ~12 min |
| **3** | `destroy`, and what is (and isn't) left behind | ~8 min |

---

## Track B: Dojo Cloud (~66 min)

You deploy a real container and watch it in the portal. Work in `~/lab/tofu-basics`.

| Lab | Topic | Time |
| --- | ----- | ---- |
| **4** | Meet Dojo Cloud: the portal, your credentials, `init` | ~8 min |
| **5** | **Deploy hello:** `apply`, open the site, watch the portal | ~10 min |
| **6** | Break a policy on purpose and read the cloud's errors | ~12 min |
| **7** | Drift: change things in the portal, then `plan` | ~8 min |
| **8** | In-place (`~`) vs replace (`-/+`), `-replace` | ~12 min |
| **9** | `for_each`, and run into a quota | ~8 min |
| **10** | Clean up: `destroy`, verify the portal is empty | ~8 min |

---

<!-- _class: section-title -->

# Track A

## The offline sandbox

---

## What you'll learn in Track A

- **Lab 0:** fork the starter repo so you have your own copy, what each file in it is for, and that `terraform` really is OpenTofu
- **Lab 1:** the four commands in order. `plan` changes nothing; `apply` asks before it acts
- **Lab 2:** one edit can give a `~` *and* a `-/+`. Applying twice changes nothing (**idempotent**)
- **Lab 3:** `destroy` removes what was created, but the state file and your `.tf` files stay

> Check yourself after Lab 2: can you say, before running `plan`, which of your edits will rebuild something?

---

<!-- _class: section-title -->

# Track B

## Dojo Cloud

---

## What you'll learn in Track B

- **Lab 4:** the cloud is just an API; your login is already in your environment
- **Lab 5:** one reference (`azurerm_resource_group.main.name`) makes the resource group come first
- **Lab 6:** `plan` cannot see policy. Read a cloud error from the bottom up
- **Lab 7:** drift: the portal changed it, `plan` notices, `apply` puts it back
- **Lab 8:** a tag is `~` (about a second); a message or image is `-/+` (about half a minute, site down)
- **Lab 9:** a quota is a hard cap that no plan can predict
- **Lab 10:** verify the cloud is empty, don't just trust the terminal

---

## Expect these

- `apply` takes **about 35 seconds** for a resource group plus a container. Give it a full minute before worrying
- The portal refreshes itself every ~3 s. **Refresh now** if you're impatient
- An error in Lab 6 or Lab 9 is **the point**, not a mistake. Read it, fix the file
- **Never delete `terraform.tfstate`.** If you lose it, ask the facilitator to **Purge** your subscription
- `git checkout <file>` undoes an edit. It is your friend

---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Labs](lab-index.md)" -->

# Ready?

## Open `~/lab/README.md` in your terminal and start with Lab 0

Stuck? Ask. Done early? Try the optional last section of Lab 8.
