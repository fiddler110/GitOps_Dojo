---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
    @import url('assets/themes/presentation.css');
footer: "[&larr; Hub](index.md) &nbsp;|&nbsp; OpenTofu Basics | Engineering & IT Operations"
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# OpenTofu Basics

## Describe the infrastructure you want. Let the tool make it so.

Builds on Git Fundamentals: same files-in-git habit, applied to servers and clouds

**Talk + hands-on lab · about 2¼ hours**

<!--
TIMING (whole session, ~140 min; the lab times are the estimates in
~/lab/README.md, the talk times are a guess until the dry run, T9.4):
  Talk, parts 1-3 ............ ~25 min   (slides up to "Track A")
  Track A labs 0-3 ........... ~37 min   (5 + 12 + 12 + 8)
  Dojo Cloud tour ............ ~10 min   (part 4, before Track B)
  Track B labs 4-10 .......... ~66 min   (8 + 10 + 12 + 8 + 12 + 8 + 8)
  Recap and questions ........ ~5 min

To fit a 2-hour slot, trim Track B (see the Track B slide notes). If the
talk runs long, the "Variables and outputs" slide can be skipped: Lab 0
and Lab 2 cover the same ground.

Assumes the room did Git Fundamentals (or knows clone/commit/push). The
new idea today is not a new tool for its own sake: it is that the
infrastructure itself becomes a file you review, the same way code is.
-->

---

## Today

1. Why write infrastructure down instead of clicking it
2. OpenTofu: what it is and how it works
3. The building blocks and how a repo is laid out
4. The lifecycle: `init` → `plan` → `apply` → `destroy`
5. **Track A:** an offline sandbox, zero risk (~37 min)
6. **Track B:** deploy a real container into "Dojo Cloud" (~66 min)

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
- It works. Nobody wrote down _what_ you clicked
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

**Infrastructure as Code (IaC):** you write down what should exist, in text files, and a tool builds it for you.

- The setup is **a file**, in a git repo
- A change is a **pull request**: reviewed before anything is touched
- The tool shows **exactly** what it _would_ do (`plan`) before it does it
- `git log` says who changed what, when and why
- Making a second copy is running the same files again
- Deleting it all is one command, and it removes exactly what the tool created

<!--
Connect back: the file-is-the-truth idea is the same one from the DNS as
Code session, if the room did it. Preview in dnscontrol is plan here.
-->

---

## Say _what_, not _how_

OpenTofu is **declarative**: you describe the result you want, and the tool works out the steps.

<div class="two-column">

**Step by step (a script)**

1. Check if the folder exists
2. If not, create it
3. Check if the file exists
4. If not, create it; if it's wrong, fix it

**Declarative (OpenTofu)**

- "There is a file called `hello.txt`"
- "It says `Hi`"

The tool checks what is already there and does only what's missing.

</div>

> Run it twice and the second run does **nothing**: _"No changes. Your infrastructure matches the configuration."_

<!--
Analogy that lands: a script is turn-by-turn directions; declarative is
giving the taxi driver the address. If you're already there, the driver
does nothing.

The quoted line is OpenTofu's real message when there is nothing to do.
The word for "safe to run again" is idempotent; say it once, but don't lean
on it. Lab 2 starts by proving it (apply twice, change once).
-->

---

<!-- _class: section-title -->

# Part 2

## OpenTofu and the building blocks

---

## OpenTofu, and why `terraform` works too

- **OpenTofu** is the open-source fork of Terraform, a Linux Foundation project
- Same language (**HCL**, a simple config format), same workflow, same file names: `.tf`, `.tfvars`, `.terraform/`, `terraform.tfstate`
- Almost everything you learn here works the same in Terraform
- In your terminal, **`terraform` is a symlink to `tofu`**: type either

```sh
terraform version     # prints "OpenTofu v1.12.6"
```

> Error hints say `tofu init` even when you typed `terraform`. That is expected, not a bug.

<!--
Do not get pulled into the licensing history. One line: comparable tool,
open source, drop-in for what we do today. Version is pinned to 1.12.6 in
the image. "Almost": the two projects have added a few different features
since the fork (2023), none of which we use today.
-->

---

## How OpenTofu works

<div class="flow">
<span><b>1</b><br>.tf files<br><small>what you want</small></span>
<span>→</span>
<span><b>2</b><br>OpenTofu<br><small>plans changes</small></span>
<span>→</span>
<span><b>3</b><br>provider<br><small>plugin</small></span>
<span>→</span>
<span><b>4</b><br>real system<br><small>cloud, files</small></span>
</div>

- OpenTofu compares what you want with what exists, and works out the difference
- A **provider** carries it out: a plugin that knows one system (`azurerm` talks to Azure, `local` writes files)
- Afterwards OpenTofu records what it made in **state**

<!--
This is the mental model for the rest of the day. Every error students see
comes from one of these boxes: a typo in the files (1), a plan they didn't
expect (2), a provider install problem at init (3), or the real system
saying no (4, Dojo Cloud's policy and quota in Track B).
-->

---

## Four building blocks

| Block        | What it is                                        | Example                       |
| ------------ | ------------------------------------------------- | ----------------------------- |
| **provider** | The plugin that talks to one system               | `azurerm`, `random`, `local`  |
| **resource** | One thing you want to exist                       | a resource group, a container |
| **variable** | An input you can change without editing resources | `location`, `message`         |
| **output**   | A value worth printing when it's done             | the site's URL                |

And one thing the tool keeps for itself: **state**, its memory of what it created.

<!--
Write these four on the board if there is one. Everything in the labs is
one of these. State gets its own slide shortly.
-->

---

## A resource, line by line

```hcl
resource "random_pet" "nickname" {
  length = 2
}
```

- `resource`: this block describes **one thing that should exist**
- `"random_pet"`: the **type**, what kind of thing it is. The part before the first `_` names the **provider** (`random`)
- `"nickname"`: **your label** for it, used to refer to it from elsewhere
- `length = 2`: an **argument**, a setting for this thing. Each type has its own
- Type plus label is the resource's **address**: `random_pet.nickname`. You'll see it in every plan

<!--
random_pet makes a random name like "light-porpoise". It is a good first
resource because it's harmless, and because it only exists in OpenTofu's
state: nothing outside the tool is created. If someone asks "where does the
pet live?", that's the answer.

The label only has to be unique per type in a folder. Renaming it is a
change of address, which OpenTofu reads as delete-and-create.
-->

---

## Connecting resources

```hcl
resource "random_pet" "nickname" {
  length = var.pet_words
}

resource "local_file" "greeting" {
  filename = "${path.module}/out/hello.txt"
  content  = "Hi ${random_pet.nickname.id}\n"
}
```

- `var.pet_words` reads a **variable**; `random_pet.nickname.id` reads **another resource** (for a pet, `id` is the generated name)
- That reference is a **dependency**: OpenTofu creates the pet _before_ the file, and deletes them in reverse
- You don't write the order down; OpenTofu works it out from the references

<!--
This is the sandbox from Track A, simplified. The dependency-by-reference
point is the most important thing on the slide: the order is implicit.
${...} inside a string inserts a value, and path.module means "this
folder". Result: out/hello.txt contains "Hi light-porpoise".

If asked: depends_on exists for the rare dependency OpenTofu can't see from
a reference. You won't need it today.

If asked "can I see the graph?": `terraform graph` prints it as DOT text
(Lab 5 has an optional step). It shows what waits for what, not a fixed
order: independent resources run in parallel (10 at a time by default).

Foreshadow Lab 2: change pet_words and BOTH get replaced, because a new
pet means a new name, which means new file content.
-->

---

## Variables and outputs

```hcl
# variables.tf: declare an input
variable "pet_words" { default = 2 }

# terraform.tfvars: choose its value
pet_words = 3

# outputs.tf: print a result
output "nickname" { value = random_pet.nickname.id }
```

- A **variable** is declared once, then read anywhere as `var.pet_words`
- Its value comes from the `default`, `terraform.tfvars`, a `TF_VAR_pet_words` environment variable, or `-var` on the command line
- An **output** is printed after `apply`; `terraform output` shows it again

<!--
The point of variables: the same code, different settings (dev vs prod, a
different region) without touching the resource blocks.

Precedence, if asked: -var wins, then terraform.tfvars, then TF_VAR_, then
the default. Track B uses TF_VAR_owner: your terminal sets your username
for you, which is why variables.tf gives owner no default.
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
├── sandbox/            Track A: its own small set of the same files
└── terraform.tfstate   created by apply: the tool's memory (never commit)
```

> OpenTofu reads **every `.tf` file** in the folder, as if they were one. The split is for people, not the tool.

<!--
The file structure is a stated learning objective. The names are
convention; the tool would work with one giant main.tf. Real repos split
them this way so a reviewer knows where to look. Each folder is its own
separate configuration with its own state: sandbox/ doesn't see the files
above it, and vice versa.
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

- **`init`** installs the providers. Once per folder (again if you add one)
- **`plan`** shows what _would_ change. It changes nothing: run it often
- **`apply`** shows the plan, waits for you to type `yes`, then does it
- **`destroy`** deletes everything this folder created (it asks first too)
- Day to day, your loop: **change a file → `plan` → `apply`**

<!--
Emphasise that plan is safe. People are scared of the tool at first; the
fix is to run plan constantly. Apply and destroy are the only steps with
consequences, and both ask first.
-->

---

## How `plan` decides what to do

It looks at three things: **your files** (what you want), **state** (what it made last time), and **the real system** (what is there now, checked fresh every time).

| Situation                                          | Plan says                          |
| -------------------------------------------------- | ---------------------------------- |
| In your files, not created yet                     | `+` create it                      |
| Exists, but your files now say something different | `~` change it, or `-/+` replace it |
| Removed from your files                            | `-` destroy it                     |
| Deleted by someone else, behind the tool's back    | `+` create it again                |
| Everything matches                                 | _No changes_                       |

<!--
This is the heart of how the tool works: it doesn't replay a script, it
compares "wanted" with "is" and plans the difference. The fourth row is
drift, which students will cause on purpose in Lab 7. Whether a change is
~ or -/+ is the next slide.
-->

---

## Reading a plan: the symbols

| Symbol | Meaning                                                 | Feels like |
| ------ | ------------------------------------------------------- | ---------- |
| `+`    | create                                                  | new        |
| `~`    | update **in place**: the same thing, edited             | tweak      |
| `-`    | destroy                                                 | gone       |
| `-/+`  | **replace**: destroy the old one, then create a new one | rebuild    |

```text
Plan: 2 to add, 1 to change, 0 to destroy.
```

**Always read the last line, and always look for `-/+`.** A replace means downtime and a brand-new thing; anything stored on the old one is gone.

<!--
Whether an edit is ~ or -/+ is decided by the provider, attribute by
attribute: some settings simply can't be changed on a thing that already
exists. The plan prints "# forces replacement" next to the attribute
responsible: tell people to look for it. Lab 8 measures it on a real resource: a tag is ~, a message or
image is -/+ (and the site is down for ~26 s). Lab 8 also shows +/-, the
reverse order (create the new one first), which you opt into with
create_before_destroy. A replace counts in both "to add" and "to destroy".
-->

---

## State: the tool's memory

- `apply` writes `terraform.tfstate`: _"I created these, with these IDs"_. That's how OpenTofu knows which real things are **its own**
- Never hand-edit it. <u>**Never commit it**</u>: it can hold passwords in plain text
- Lose it and the tool forgets what it made: the resources are still there, but nothing manages them

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

| Lab   | You will                                                    | Time    |
| ----- | ----------------------------------------------------------- | ------- |
| **0** | fork + clone the repo, take the tour, meet `terraform` = `tofu`    | ~5 min  |
| **1** | `init`, `validate`, `plan`, `apply`: make a name and a file | ~12 min |
| **2** | change a variable, read the plan, apply it again            | ~12 min |
| **3** | `destroy`, and see what's left behind                       | ~8 min  |

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

> Azure-inspired training environment. Not affiliated or connected with Microsoft.

<!--
Be honest about what it is: a small stand-in that speaks Azure's language.
The provider is the real one, so skills transfer. Do not oversell it as
real Azure, and do not say it is Azure.
-->

---

## What happens when you `apply` to a cloud

<div class="flow">
<span><b>1</b><br>OpenTofu<br><small>the plan</small></span>
<span>→</span>
<span><b>2</b><br>azurerm<br><small>web requests</small></span>
<span>→</span>
<span><b>3</b><br>cloud API<br><small>checks rules</small></span>
<span>→</span>
<span><b>4</b><br>resources<br><small>made, or refused</small></span>
</div>

- A cloud is a web API: the provider sends requests like _"create this resource group"_
- It logs in with **credentials** from your terminal (`ARM_*` variables), never from a `.tf` file
- The cloud checks each request against its **rules** (policy, quota), then says yes or no

<!--
Lab 4 shows this for real: students look at their ARM_* variables and
curl the cloud's front door. The takeaway: OpenTofu doesn't do anything a
script couldn't; it just sends the right requests in the right order and
remembers the results.
-->

---

## The vocabulary you'll meet

| Azure idea         | In Dojo Cloud                                               |
| ------------------ | ----------------------------------------------------------- |
| Subscription       | your own account area, named after your username            |
| Resource group     | a folder for related resources (`rg-…`)                     |
| Container instance | one running container (`ci-…`), a "container group" in code |
| Region             | where it runs: `canadacentral` or `canadaeast`              |
| Tags               | labels: `owner` and `env` are **required**                  |
| Policy             | the cloud's house rules; it says no, in words               |
| Quota              | a cap: 2 container instances each                           |
| Activity log       | who did what, and whether it worked                         |

<!--
Do not read the table out. Point at "Policy" and "Quota": those are the
two that produce errors students will see, on purpose, in Labs 6 and 9.
The portal says "container instance"; Azure's API and the provider say
"container group" (a group can hold several containers; ours hold one).
-->

---

## The portal

Open **Dojo Cloud** from the landing page. It shows your subscription **live**: you will watch your resources appear as you `apply`.

- **Home / Resource groups / All resources / Container instances**
- **Activity log** for every change and its result
- **Class view** to browse everyone's sites (read-only)
- A **Delete** button, on purpose: clicking around behind your code's back is how we make **drift** (Lab 7)

Your site's address prints as an output: `…/cloud/site/hello-dev-<username>/`

<!--
The facilitator has the whole class on a Class progress board, so do not
worry about a student getting stuck silently. Say that out loud: it is
reassuring.
-->

---

## Three things the labs will do to you

- **Policy** _(Lab 6)_: remove the `owner` tag. `plan` looks fine, but `apply` is refused with `RequestDisallowedByPolicy`. Read the error, fix the file
- **Drift** _(Lab 7)_: someone deletes your container in the portal. `plan` notices reality changed and offers to put it back
- **Replace** _(Lab 8)_: edit a tag and get `~`; edit the message and get `-/+`. Predict it _before_ you run `plan`

> `plan` can't see the cloud's rules; only a real request can. Your own `validation` rules in `variables.tf` catch some mistakes earlier: try `eastus` and `plan` stops you.

<!--
This is the foreshadowing slide. The key insight for Lab 6 and Lab 9:
plan computes what to ask for; the cloud decides whether to say yes.
Two layers: validation (your code, at plan, instant) repeats some of the
cloud's rules so you fail fast; policy (the cloud, at apply) is the real
rule and can't be bypassed. Lab 6 shows both.
-->

---

## Track B: deploy for real

Labs **4-10** · about **66 minutes** (an apply takes ~35 s: that's normal)

| Lab    | You will                                                           | Time    |
| ------ | ------------------------------------------------------------------ | ------- |
| **4**  | meet Dojo Cloud, look at the files, `init` with the cloud provider | ~8 min  |
| **5**  | **deploy hello**, open the site, watch the portal                  | ~10 min |
| **6**  | break policy on purpose, read the error                            | ~12 min |
| **7**  | cause drift, then reconcile it                                     | ~8 min  |
| **8**  | in-place vs replace                                                | ~12 min |
| **9**  | `for_each`, and hit your quota                                     | ~8 min  |
| **10** | `destroy`, and check the portal is empty                           | ~8 min  |

<!--
Each lab builds on Lab 5's deployment, so keep the order and do not let
anyone destroy before Lab 10. Labs 4, 5 and 10 are the spine. To save time,
drop Lab 9 (Lab 10 copes with or without its extra containers) and/or the
optional last section of Lab 8. Lab 9 half-applies on purpose (the quota
error); make sure people finish its clean-up section before Lab 10.
-->

---

## Recap

- **Code, not clicks:** infrastructure in files, reviewed and versioned in git
- **Declarative:** say what you want; the tool compares it with what exists and does the difference
- Four blocks: **provider, resource, variable, output**, plus **state**
- **`init` → `plan` → `apply` → `destroy`**, and read every plan before you say `yes`
- `+` create · `~` in place · `-` destroy · `-/+` **replace**
- Your `validation` is checked at `plan`; the cloud's policy and quota at `apply`; drift is what `plan` finds

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
