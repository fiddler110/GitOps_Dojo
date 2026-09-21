---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/presentation.css');
footer: '[&larr; Hub](index.md) &nbsp;|&nbsp; OpenTofu Basics | Engineering & IT Operations'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# OpenTofu Basics

## Describe the infrastructure you want. Let the tool make it so.

Builds on Git Fundamentals: same files-in-git habit, applied to servers and clouds

**Talk + hands-on lab · about 2¼ hours**

<!--
TIMING (whole session, ~135 min; the lab times are the estimates in
~/lab/README.md, the talk times are a guess until the dry run, T9.4):
  Talk, parts 1-3 ............ ~20 min   (slides up to "Track A")
  Track A labs 0-3 ........... ~37 min   (5 + 12 + 12 + 8)
  Dojo Cloud tour ............ ~10 min   (part 4, before Track B)
  Track B labs 4-10 .......... ~66 min   (8 + 10 + 12 + 8 + 12 + 8 + 8)
  Recap and questions ........ ~5 min

To fit a 2-hour slot, trim Track B (see the Track B slide notes).

Assumes the room did Git Fundamentals (or knows clone/commit/push). The
new idea today is not a new tool for its own sake: it is that the
infrastructure itself becomes a file you review, the same way code is.
-->

---

## Today

1. Why write infrastructure down instead of clicking it
2. OpenTofu, and why `terraform` works here too
3. The building blocks and how a repo is laid out
4. The lifecycle: `init` → `plan` → `apply` → `destroy`
5. **Track A:** an offline sandbox, zero risk (~37 min)
6. **Track B:** deploy a real container into "Dojo Cloud" (~65 min)

> Learning the basics is the goal. Nothing you do today can break anything that matters.

<!--
Set expectations: the talk is short on purpose. Most of the learning is in
the labs. Track A is the safety net: if Track B has a problem on the day,
everyone still finishes the core loop.
-->

---

<!-- _class: section-title -->

# Part 1

## Why Infrastructure as Code

---

## How infrastructure usually gets made

<div class="two-column">

- Open a web console
- Click through a wizard
- Pick a region, a size, a name, a few tags (maybe)
- It works. Nobody wrote down *what* you clicked
- Six months later: "who made this, and why is it here?"
- Making a second copy means clicking it all again, slightly differently

</div>

> The console is the only record, and it only shows what exists **now**, not how it got there.

<!--
Ask the room: who has built something in a cloud console and then had to
rebuild it? What did you forget? That memory is the whole motivation.
-->

---

## What changes when it's code

- The setup is **a file**, in a git repo
- A change is a **pull request**: reviewed before anything is touched
- The tool shows the **exact diff** of what it *would* do (`plan`) before it does it
- `git log` says who changed what, when and why
- Making a second copy is running the same files again
- Deleting it all is one command, and it removes exactly what was created

**Declarative:** you describe the result you want; the tool works out the steps.

<!--
Connect back: the file-is-the-truth idea is the same one from the DNS as
Code session, if the room did it. Preview in dnscontrol is plan here.
-->

---

<!-- _class: section-title -->

# Part 2

## OpenTofu and the building blocks

---

## OpenTofu, and why `terraform` works too

- **OpenTofu** is the open-source fork of Terraform, run by the Linux Foundation
- Same language (HCL), same workflow, same file names: `.tf`, `.tfvars`, `.terraform/`, `terraform.tfstate`
- What you learn here carries straight over to Terraform, and the reverse
- In your terminal, **`terraform` is a symlink to `tofu`**: type either

```sh
terraform version     # prints "OpenTofu v1.12.6"
```

> Error hints say `tofu init` even when you typed `terraform`. That is expected, not a bug.

<!--
Do not get pulled into the licensing history. One line: comparable tool,
open source, drop-in for what we do today. Version is pinned to 1.12.6 in
the image.
-->

---

## Four building blocks

| Block | What it is | Example |
| ----- | ---------- | ------- |
| **provider** | The plugin that talks to one system | `azurerm`, `random`, `local` |
| **resource** | One thing that should exist | a resource group, a container |
| **variable** | An input you can change without editing resources | `location`, `message` |
| **output** | A value worth printing when it's done | the site's URL |

And one thing the tool keeps for itself: **state**, its memory of what it created.

<!--
Write these four on the board if there is one. Everything in the labs is
one of these. State gets its own slide shortly.
-->

---

## A resource, line by line

```hcl
resource "random_pet" "nickname" {
  length = var.pet_words
}

resource "local_file" "greeting" {
  filename = "${path.module}/out/hello.txt"
  content  = "Hi ${random_pet.nickname.id}\n"
}
```

- `random_pet` = **type** (the provider is `random`), `nickname` = **your name** for it
- `var.pet_words` reads a variable; `random_pet.nickname.id` reads another resource
- That reference is a **dependency**: the pet is created *before* the file. You never write the order down.

<!--
This is the sandbox from Track A, simplified. The dependency-by-reference
point is the most important thing on the slide: the graph is implicit.
-->

---

## What each file is

```text
tofu-basics/
├── versions.tf         which OpenTofu and which providers (pinned)
├── providers.tf        provider settings
├── variables.tf        the inputs, with descriptions and validation
├── terraform.tfvars    the values you choose for those inputs
├── locals.tf           names and tags worked out once, reused
├── main.tf             the resources: what should exist
├── outputs.tf          what to print when done
├── .terraform.lock.hcl exact provider versions and checksums (commit it)
├── .gitignore          keeps .terraform/ and state out of git
└── terraform.tfstate   created by apply: the tool's memory (never commit)
```

> OpenTofu reads **every `.tf` file** in the folder. The split is for people, not the tool.

<!--
The file structure is a stated learning objective. The names are
convention; the tool would work with one giant main.tf. Real repos split
them this way so a reviewer knows where to look.
-->

---

<!-- _class: section-title -->

# Part 3

## The lifecycle

---

## init → plan → apply → destroy

<div class="flow">
<span><b>1</b><br>init<br><small>get providers</small></span>
<span>→</span>
<span><b>2</b><br>plan<br><small>preview, changes nothing</small></span>
<span>→</span>
<span><b>3</b><br>apply<br><small>do it</small></span>
<span>→</span>
<span><b>4</b><br>destroy<br><small>undo it</small></span>
</div>

<br>

- `init` once per folder. `plan` as often as you like: it is **read-only**
- `apply` shows the plan again and waits for you to type `yes`
- Then loop: **change a file → `plan` → `apply`**

<!--
Emphasise that plan is safe. People are scared of the tool at first; the
fix is to run plan constantly. Apply is the only step with consequences,
and it asks first.
-->

---

## Reading a plan: the symbols

| Symbol | Meaning | Feels like |
| ------ | ------- | ---------- |
| `+` | create | new |
| `~` | update **in place** | tweak |
| `-` | destroy | gone |
| `-/+` | **replace** (destroy, then create) | rebuild |

```text
Plan: 2 to add, 1 to change, 0 to destroy.
```

**Always read the last line, and always look for `-/+`.** A replace is where surprises live.

<!--
Whether an edit is ~ or -/+ is decided by the provider, attribute by
attribute. Lab 8 measures it on a real resource: a tag is ~, a message or
image is -/+.
-->

---

## State: the tool's memory

- After `apply`, OpenTofu writes `terraform.tfstate`: *"I created these, with these ids"*
- `plan` compares **your files**, **state** and **what is really there**
- Never hand-edit it. Never commit it (it can hold secrets)
- Lose it and the tool forgets what it made: the resources are still there, orphaned

```sh
terraform state list     # what is tracked
terraform show           # everything it knows
```

> Real teams keep state in a shared, locked remote store. Out of scope today, but it is the next step.

<!--
The orphaned-resources point pays off in Track B: a student who deletes
their state file has cloud resources they cannot manage. The facilitator
can Purge that student's subscription from the portal. Mention that so
nobody panics.
-->

---

## Track A: the offline sandbox

Labs **0-3** · about **37 minutes** · runs entirely in your terminal

| Lab | You will | Time |
| --- | -------- | ---- |
| **0** | clone the repo, take the tour, meet `terraform` = `tofu` | ~5 min |
| **1** | `init`, `validate`, `plan`, `apply`: make a name and a file | ~12 min |
| **2** | change a variable, read the plan, apply it again | ~12 min |
| **3** | `destroy`, and see what's left behind | ~8 min |

Nothing leaves your terminal. No internet, no cloud, no risk.

<!--
Hand over to the room here. Walk to the labs page (labs.md) and point at
~/lab/README.md inside the terminal. Check in at around 15 minutes; Lab 2
is where the ~ vs -/+ mix first shows up.
-->

---

<!-- _class: section-title -->

# Part 4

## Dojo Cloud

---

## A cloud in the room

**Dojo Cloud** is a practice cloud built for this class. It is **Azure-inspired**: same words, same shapes, same kind of errors.

- Your code is genuine Azure code (the real `azurerm` provider)
- It deploys a **real container** and gives you a real website to open
- Everyone has their **own subscription**; you cannot touch anyone else's
- It disappears when the class ends

> Azure-inspired training environment. Not affiliated with Microsoft.

<!--
Be honest about what it is: a small stand-in that speaks Azure's language.
The provider is the real one, so skills transfer. Do not oversell it as
real Azure, and do not say it is Azure.
-->

---

## The vocabulary you'll meet

| Azure idea | In Dojo Cloud |
| ---------- | ------------- |
| Subscription | yours alone, made from your username |
| Resource group | a folder for related resources (`rg-…`) |
| Container group | one running container (`ci-…`), like Azure Container Instances |
| Region | `canadacentral` or `canadaeast` |
| Tags | labels: `owner` and `env` are **required** |
| Policy | the cloud's house rules; it says no, in words |
| Quota | a cap: 2 container groups each |
| Activity log | who did what, and whether it worked |

<!--
Do not read the table out. Point at "Policy" and "Quota": those are the
two that produce errors students will see, on purpose, in Labs 6 and 9.
-->

---

## The portal

Open **Dojo Cloud** from the landing page. It shows your subscription **live**: you will watch your resources appear as you `apply`.

- **Home / Resource groups / All resources / Container instances**
- **Activity log** for every change and its result
- **Class view** to browse everyone's sites (read-only)
- A **Delete** button, on purpose: clicking around behind your code's back is how we make **drift** (Lab 7)

Your site's address prints as an output: `…/cloud/site/<name>/`

<!--
The facilitator has the whole class on a Class progress board, so do not
worry about a student getting stuck silently. Say that out loud: it is
reassuring.
-->

---

## Three things the labs will do to you

- **Policy** *(Lab 6)*: omit a tag or pick `eastus`. `plan` looks fine, `apply` is refused with `RequestDisallowedByPolicy`. Read the error, fix the file
- **Drift** *(Lab 7)*: delete your container in the portal, then `plan`. The tool notices reality changed and offers to put it back
- **Replace** *(Lab 8)*: edit a tag and get `~`; edit the message and get `-/+`. Predict it *before* you run `plan`

> `plan` cannot see policy or quotas. Only a real request can.

<!--
This is the foreshadowing slide. The key insight for Lab 6 and Lab 9:
plan computes what to ask for; the cloud decides whether to say yes.
-->

---

## Track B: deploy for real

Labs **4-10** · about **65 minutes** (apply takes ~35 s: that's normal)

| Lab | You will | Time |
| --- | -------- | ---- |
| **4** | meet Dojo Cloud, look at the files, `init` with the cloud provider | ~8 min |
| **5** | **deploy hello**, open the site, watch the portal | ~10 min |
| **6** | break policy on purpose, read the error | ~12 min |
| **7** | cause drift, then reconcile it | ~8 min |
| **8** | in-place vs replace | ~12 min |
| **9** | `for_each`, and hit your quota | ~8 min |
| **10** | `destroy`, and check the portal is empty | ~8 min |

<!--
Each lab builds on Lab 5's deployment, so keep the order and do not let
anyone destroy before Lab 10. Labs 4, 5 and 10 are the spine. To save time,
drop Lab 9 (Lab 10 copes with or without its extra containers) and/or the
optional last section of Lab 8. Lab 9 half-applies on purpose (the quota
error); make sure people finish its clean-up section before Lab 10.
-->

---

## Recap

- **Code, not clicks:** infrastructure is files, reviewed and versioned in git
- Four blocks: **provider, resource, variable, output**, plus **state**
- **`init` → `plan` → `apply` → `destroy`**, and read every plan before you say `yes`
- `+` create · `~` in place · `-` destroy · `-/+` **replace**
- Policy and quota are enforced at `apply`; drift is what `plan` finds

**Next steps:** real Azure, remote state, modules, and running `plan` on every pull request.

<!--
Ask each table for one thing that surprised them. Common answers: apply
being slow, plan not catching a policy error, drift.
-->

---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# Let's go

## Next: [labs.md](labs.md) for what each lab covers, then your terminal

Keep [cheat-sheet.md](cheat-sheet.md) open in another tab. Ask for help any time. This is a lab, not a test.
