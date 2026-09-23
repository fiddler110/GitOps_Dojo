# Lab 0 — Get the repo and take the tour

**Goal:** get your own copy of the starter repository and learn what each file is for. Nothing you run here changes any infrastructure.

---

## 1. Fork the starter repo, then clone your fork

The team's repo is `iac-team/tofu-basics`. Instead of everyone pushing branches into that one repo, each of you works in your own **fork**: a copy on the git server under your account, which still knows where it came from. This one command asks the git server's API to make it:

```sh
curl -u "$USER" -H "Content-Type: application/json" -d '{}' \
  http://git-server:3000/api/v1/repos/iac-team/tofu-basics/forks
```

`curl` asks for your **Forgejo password**, which is shown on your landing page (the page with the VS Code, Terminal and Forgejo cards). A block of JSON describing the new repo means it worked. If you see `repository is already forked`, you made it earlier; carry on.

Now clone **your** fork (`$USER` is your account name, for example `student01`):

```sh
cd ~/lab
git clone http://git-server:3000/$USER/tofu-basics.git
cd tofu-basics
ls -la
```

Infrastructure-as-Code is *just files in a git repo*: the same review, history and rollback tools apply. You can see your fork in Forgejo too, under your own account, marked "forked from iac-team/tofu-basics".

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
