---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/cheat-sheet.css');
footer: '[&larr; Hub](index.md) &nbsp;|&nbsp; OpenTofu Basics | Cheat Sheet'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# Cheat Sheet

## Every command from Labs 0-10, in one place

Keep this open in a split pane or another tab while you work. You don't need to memorize any of it.

<p class="nav">Full detail: <code>~/lab/cheat-sheet.md</code> in your terminal.</p>

---

## The loop

```text
edit .tf files → init → validate → plan → apply → (change → plan → apply)… → destroy
```

| Step | Command | Changes anything? |
| ---- | ------- | ----------------- |
| Prepare | <span class="command">terraform init</span> | Only `.terraform/` |
| Check | <span class="command">terraform validate</span> | No |
| Preview | <span class="command">terraform plan</span> | **No** |
| Do it | <span class="command">terraform apply</span> | **Yes**, after you type `yes` |
| Undo it | <span class="command">terraform destroy</span> | **Yes**, after you type `yes` |

`terraform` and `tofu` are the same program here. Use either.

---

## Inspecting

| Command | What it does |
| ------- | ------------ |
| <span class="command">terraform output [name]</span> | Print outputs (`terraform output url`) |
| <span class="command">terraform show</span> | Everything in state |
| <span class="command">terraform state list</span> | What OpenTofu is tracking |
| <span class="command">terraform graph</span> | Dependency graph as DOT text (`A -> B`: A waits for B) |
| <span class="command">terraform plan -destroy</span> | Preview a destroy |
| <span class="command">terraform plan -replace=ADDR</span> | Preview rebuilding one resource |
| <span class="command">terraform plan -var name=value</span> | Override a variable for one run |
| <span class="command">terraform fmt</span> | Tidy formatting (style only) |

Add `-no-color` when piping into `grep`, or the lines are wrapped in colour codes.

---

## Plan symbols

| Symbol | Meaning |
| ------ | ------- |
| `+` | create |
| `~` | update **in place** |
| `-` | destroy |
| `-/+` | **replace** (destroy, then create) |
| `+/-` | replace, new one first (`create_before_destroy`) |
| `(known after apply)` | doesn't exist until it's created |
| `# forces replacement` | this attribute can't be edited in place |

---

## What each file is for

| File | Purpose | Commit? |
| ---- | ------- | ------- |
| `versions.tf` | required OpenTofu + provider versions | yes |
| `providers.tf`, `variables.tf`, `locals.tf` | provider settings · inputs · computed names and tags | yes |
| `main.tf`, `outputs.tf` | the resources · values printed after apply | yes |
| `terraform.tfvars` | your values for the variables | yes (no secrets) |
| `.terraform.lock.hcl` | pinned provider versions + checksums | **yes** |
| `.terraform/` | downloaded providers | no |
| `terraform.tfstate` | what OpenTofu created | **no** |

---

## HCL in 30 seconds

```hcl
variable "name" { type = string }               # input:    var.name
locals { greeting = "Hi ${var.name}" }          # local:    local.greeting
resource "random_pet" "x" { length = 2 }        # resource: random_pet.x
output "pet" { value = random_pet.x.id }        # output
```

A reference like `random_pet.x.id` is a **dependency**: OpenTofu orders the work for you.

Any environment variable `TF_VAR_x` becomes `var.x`.

---

<!-- _class: section-title -->

# Track B

## Dojo Cloud

---

## Timings to expect

| Step | Takes |
| ---- | ----- |
| `init` | ~2 s |
| `apply` (resource group + container) | ~35 s |
| in-place edit (`~`, a tag) | ~1-2 s |
| replace (`-/+`, message or image) | ~27 s, **site is down meanwhile** |
| `destroy` | ~35 s |

The portal refreshes every ~3 s. **Refresh now** if you're impatient.

---

## Words

| Term | Meaning |
| ---- | ------- |
| Subscription | your private slice of the cloud |
| Resource group (`rg-…`) | folder for related resources |
| Container group (`ci-…`) | a running container (`azurerm_container_group`) |
| Tags | labels; `owner` and `env` are **required** |
| Policy | rules the cloud enforces at `apply` |
| Quota | hard limit: 2 container groups |
| Drift | reality changed outside your code |

---

## Dojo Cloud rules

| Rule | Error code |
| ---- | ---------- |
| Regions: `canadacentral` or `canadaeast` only | `RequestDisallowedByPolicy` |
| Tags `owner` and `env` required | `RequestDisallowedByPolicy` |
| `rg-…` for resource groups, `ci-…` for container groups | `InvalidResourceGroupName`, `InvalidContainerGroupName` |
| Images: `dojo/hello:1.0` or `:2.0` only | `InvalidImage` |
| At most 0.25 vCPU and 0.125 GB | `InvalidResourceRequest` |
| Port 80 only | `InvalidRequestContent` |
| Site name unique across the class | `DnsNameLabelInUse` |
| At most 2 container groups | `QuotaExceeded` |

---

## Which edits change in place, which rebuild

| Edit to a container group | Plan |
| ------------------------- | ---- |
| a tag | `~` in place |
| environment variable (message), image, size, DNS label | `-/+` replace |

**Reading a cloud error**, from the bottom up:

1. `with …, on main.tf line N`: which resource, which file
2. the code (`RequestDisallowedByPolicy`): what kind of problem
3. the text after it: which rule, and what to change

---

## When something goes wrong

| You see | Do this |
| ------- | ------- |
| `… already exists … needs to be imported` | State was lost. **Ask the facilitator to Purge** your subscription, then `apply`. Never delete `terraform.tfstate` |
| `RequestDisallowedByPolicy` | You broke a house rule. The message names it. Fix the code, `apply` again |
| `QuotaExceeded` | You have 2 container groups. Destroy one or shrink `for_each` |
| `Required plugins are not installed` | Run `terraform init` in `~/lab/tofu-basics` (the message says `tofu`: same program) |
| `var.owner` asks for a value | Open a new terminal tab. Still asking? Tell the facilitator |
| Portal looks stale | **Refresh now**; `terraform state list` is what OpenTofu believes |
| Link from `url` doesn't open | Use **Browse** on the container in the portal |
