# Lab 0 — Get the repo and take the tour

**Goal:** clone the starter repository and learn what each file is for. No commands change anything yet.

---

## 1. Clone the starter repo

```sh
cd ~/lab
git clone http://git-server:3000/iac-team/tofu-basics.git
cd tofu-basics
ls -la
```

Same clone you did in Git Fundamentals. Infrastructure-as-Code is *just files in a git repo* — the same review, history and rollback tools apply.

## 2. Is `terraform` really OpenTofu?

```sh
terraform version
which terraform tofu
```

Expected: `OpenTofu v1.12.6` (or similar), and `terraform` is a link that points at `tofu`. You can use either name for every command in this lab.

## 3. The tour

Track A lives in `sandbox/`. (The files at the top level of the repo, `main.tf`, `locals.tf` and friends, are **Track B**, the cloud part, from Lab 4 onward. Ignore them for now.) Look inside:

```sh
cd sandbox
ls -la
```

| File | What it is | Commit it? |
| ---- | ---------- | ---------- |
| `versions.tf` | Which OpenTofu version and which **providers** (plugins) are required, and their allowed versions. | Yes |
| `variables.tf` | The **inputs**: names, types, defaults, validation rules. | Yes |
| `main.tf` | The **resources** — what should exist. The heart of the config. | Yes |
| `outputs.tf` | The **outputs** — values printed after `apply`. | Yes |
| `terraform.tfvars` | The values you're setting for the variables. Edited most often. | Yes (no secrets!) |
| `.terraform.lock.hcl` | Exact provider versions + checksums, so everyone gets the same ones. | **Yes** |
| `.terraform/` *(appears after `init`)* | Downloaded providers. | **No** |
| `terraform.tfstate` *(appears after `apply`)* | OpenTofu's record of what it created. | **No** — can hold secrets |

OpenTofu reads **every `.tf` file in the folder** as one configuration. Splitting into `main.tf`, `variables.tf`, etc. is only a convention to make repos easy to read — you could put everything in one file and it would behave identically.

Read the config now — it is short:

```sh
cat versions.tf
cat main.tf
```

Notice `main.tf` uses `random_pet.nickname.id` inside the `local_file` — that reference is how OpenTofu learns *create the pet first*.

## Check yourself

1. Which file would you edit to change a value without touching any resource? *(`terraform.tfvars`)*
2. Which two things must never be committed? *(`.terraform/` and state files — see `../.gitignore`)*

**Next:** [lab1.md](lab1.md)
