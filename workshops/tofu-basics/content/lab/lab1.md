# Lab 1 — First run: `init`, `plan`, `apply`

**Goal:** run the core loop once and see what each step does. All commands run in `~/lab/tofu-basics/sandbox`.

> **Starting here?** This lab needs your fork of the repo, cloned (Lab 0). Run `dojo prep 1` to set that up; it's safe to run even if you did the earlier labs.

```sh
cd ~/lab/tofu-basics/sandbox
```

---

## 1. `init` — prepare the folder

Before OpenTofu can do anything, it needs the plugins (**providers**) your config uses. `init` reads `versions.tf`, finds the providers it needs, and installs them into `.terraform/`. It also honours `.terraform.lock.hcl`, which pins exact versions. Normally it downloads from a public registry; this lab has no internet, so a local copy is used, and the commands and output are the same. Run `init` once per new folder, and again after changing providers.

```text
terraform init
```

**Your turn:** before you run it, predict which new folder will appear.

```sh
terraform init
ls -a
```

<!-- dojo-reveal: Results of init -->

Expected (abridged):

```text
Initializing provider plugins...
- Reusing previous version of hashicorp/local from the dependency lock file
- Reusing previous version of hashicorp/random from the dependency lock file
- Installing hashicorp/random v3.9.1...
- Installing hashicorp/local v2.9.1...
OpenTofu has been successfully initialized!
```

`ls -a` shows the new `.terraform/` folder, where the providers were installed.

<!-- /dojo-reveal -->

## 2. `validate` — check the syntax

`validate` checks that the files are well-formed and that references between them make sense. It does not touch anything real, so it is safe to run as often as you like.

```text
terraform validate
```

**Your turn:** run it. Before you do, predict what a healthy config prints.

```sh
terraform validate
```

<!-- dojo-reveal: Results of validate -->

- `Success! The configuration is valid.`

<!-- /dojo-reveal -->

## 3. `plan` — preview, change nothing

`plan` is the preview. It works out what OpenTofu would do and prints it, changing nothing. It compares three things: your **config** (what you want), the **state** (what OpenTofu remembers), and the **real world**.

```text
terraform plan
```

**Reading a plan:**

| Symbol | Meaning |
| ------ | ------- |
| `+` | will be **created** |
| `~` | will be **changed in place** |
| `-` | will be **destroyed** |
| `-/+` | will be **replaced** (destroyed, then created) |

`(known after apply)` means the value doesn't exist until the resource is made, like the random name.

**Your turn:** nothing exists yet. Before you run it, predict how many resources the plan will want to add, and which symbol will appear.

```sh
terraform plan
```

<!-- dojo-reveal: Results of plan -->

Expected (abridged):

```terraform
  # local_file.greeting will be created
  + resource "local_file" "greeting" { ... }

  # random_pet.nickname will be created
  + resource "random_pet" "nickname" { ... }

  # terraform_data.note will be created
  + resource "terraform_data" "note" { ... }

Plan: 3 to add, 0 to change, 0 to destroy.
```

<!-- /dojo-reveal -->

## 4. `apply` — make it real

`apply` is `plan` plus your approval plus doing it. OpenTofu shows the same plan and asks you to type `yes`; that prompt is your last chance to review, because `apply` changes real things. It builds a **dependency graph** from the references in your config, so it creates the random name **first**, then the file whose `content` uses it. You never wrote an order.

```text
terraform apply
```

**Your turn:** run it and read the plan before you type `yes`. Predict which resource is created first.

```sh
terraform apply
```

<!-- dojo-reveal: Results of apply -->

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

Your pet name will differ.

<!-- /dojo-reveal -->

Look at what was made:

```sh
cat out/hello.txt
ls -la
```

<!-- dojo-reveal: Results of cat and ls -->

- `out/hello.txt` holds your greeting.
- You now have a `terraform.tfstate` file, OpenTofu's memory of what it created.

<!-- /dojo-reveal -->

## Check yourself

1. What would happen if you ran `terraform apply` again right now? Try it.
2. Why did OpenTofu ask you to type `yes`?

<!-- dojo-reveal: Show the answer -->

1. Nothing: "No changes."
2. `apply` changes real things; the prompt is your last chance to review.

<!-- /dojo-reveal -->

## Troubleshooting

| You see | Cause / fix |
| ------- | ----------- |
| `Required plugins are not installed ... run: tofu init` | You skipped `init` (or are in the wrong folder). Run `terraform init`. |
| `No configuration files` | Wrong directory. `cd ~/lab/tofu-basics/sandbox`. |
| `Error: Invalid ...` with a file and line number | A typo in a `.tf` file. Fix the line it points at, run `terraform validate`. |

**Next:** [lab2.md](lab2.md)
