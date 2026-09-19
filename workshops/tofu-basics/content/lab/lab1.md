# Lab 1 — First run: `init`, `plan`, `apply`

**Goal:** run the core loop once and see what each step does. All commands run in `~/lab/tofu-basics/sandbox`.

```sh
cd ~/lab/tofu-basics/sandbox
```

---

## 1. `init` — prepare the folder

```sh
terraform init
```

Expected (abridged):

```text
Initializing provider plugins...
- Reusing previous version of hashicorp/local from the dependency lock file
- Reusing previous version of hashicorp/random from the dependency lock file
- Installing hashicorp/random v3.9.1...
- Installing hashicorp/local v2.9.1...
OpenTofu has been successfully initialized!
```

**What just happened:** `init` read `versions.tf`, found the providers it needs, and installed them into `.terraform/`. Normally it downloads from a public registry; this lab has no internet, so a local copy is used — the commands and output are the same. It also honoured `.terraform.lock.hcl` (pinned versions). Run `ls -a` and find `.terraform/`.

Run `init` once per new folder, and again after changing providers.

## 2. `validate` — check the syntax

```sh
terraform validate
```

Expected: `Success! The configuration is valid.` This checks the files are well-formed; it does not touch anything.

## 3. `plan` — preview, change nothing

```sh
terraform plan
```

Expected (abridged):

```text
  # local_file.greeting will be created
  + resource "local_file" "greeting" { ... }

  # random_pet.nickname will be created
  + resource "random_pet" "nickname" { ... }

  # terraform_data.note will be created
  + resource "terraform_data" "note" { ... }

Plan: 3 to add, 0 to change, 0 to destroy.
```

**Reading a plan:**

| Symbol | Meaning |
| ------ | ------- |
| `+` | will be **created** |
| `~` | will be **changed in place** |
| `-` | will be **destroyed** |
| `-/+` | will be **replaced** (destroyed, then created) |

`(known after apply)` means the value doesn't exist until the resource is made — like the random name.

`plan` compares three things: your **config** (what you want), the **state** (what OpenTofu remembers), and the **real world**. It never changes anything.

## 4. `apply` — make it real

```sh
terraform apply
```

OpenTofu shows the same plan and asks for approval. Read it, then type `yes`.

Expected (abridged):

```text
terraform_data.note: Creation complete after 0s [id=...]
random_pet.nickname: Creation complete after 0s [id=deep-wildcat]
local_file.greeting: Creation complete after 0s [id=...]

Apply complete! Resources: 3 added, 0 changed, 0 destroyed.

Outputs:

greeting_file = "./out/hello.txt"
nickname = "deep-wildcat"
```

Your pet name will differ. Look at what was made:

```sh
cat out/hello.txt
ls -la
```

You now have a `terraform.tfstate` file — OpenTofu's memory of what it created.

## What just happened

`apply` = `plan` + your approval + doing it. It created the random name **first**, then the file, because the file's `content` referenced the name. You never wrote an order; OpenTofu built a **dependency graph** from the references.

## Check yourself

1. What would happen if you ran `terraform apply` again right now? *(Nothing — try it: "No changes.")*
2. Why did OpenTofu ask you to type `yes`? *(`apply` changes real things; the prompt is your last chance to review.)*

## Troubleshooting

| You see | Cause / fix |
| ------- | ----------- |
| `Required plugins are not installed ... run: tofu init` | You skipped `init` (or are in the wrong folder). Run `terraform init`. |
| `No configuration files` | Wrong directory. `cd ~/lab/tofu-basics/sandbox`. |
| `Error: Invalid ...` with a file and line number | A typo in a `.tf` file. Fix the line it points at, run `terraform validate`. |

**Next:** [lab2.md](lab2.md)
