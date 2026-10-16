# Lab 0 — Get the repo and take the tour

**Goal:** get your own copy of the starter repository and learn what each file is for. Nothing you run here changes any infrastructure.

---

## 1. Fork the starter repo, then clone your fork

The team's repo is `iac-team/tofu-basics`. Instead of everyone pushing branches into that one repo, each of you works in your own **fork**: a copy on the git server under your account, which still knows where it came from. Forking is one request to the git server's API, made with `curl`. The `--netrc` flag signs in as you with the access token your terminal came with (in `~/.netrc`, readable by you only), so there's no password to type. Then you **clone** your fork, which downloads a working copy to `~/lab`.

```text
curl --netrc -d '{}' <server>/api/v1/repos/<owner>/<repo>/forks
git clone <server>/<you>/<repo>.git
```

Infrastructure-as-Code is *just files in a git repo*: the same review, history and rollback tools apply.

**Your turn:** fork the repo. Before you run it, predict: what will the server send back?

```sh
curl --netrc -H "Content-Type: application/json" -d '{}' \
  http://git-server:3000/api/v1/repos/iac-team/tofu-basics/forks
```

<!-- dojo-reveal: Results of the fork request -->

A block of JSON describing the new repo means it worked. If you see `repository is already forked`, you made it earlier; carry on.

<!-- /dojo-reveal -->

Now clone **your** fork (`$USER` is your account name, `studentXX`):

```sh
cd ~/lab
git clone http://git-server:3000/$USER/tofu-basics.git
cd tofu-basics
ls -la
```

You can see your fork in Forgejo too, under your own account, marked "forked from iac-team/tofu-basics".

## 2. Is `terraform` really OpenTofu?

OpenTofu is the open-source fork of Terraform. It keeps the same commands and file format, so the `terraform` name on this machine is just a link to the `tofu` program. You can use either name for every command in this lab.

```text
terraform version
which terraform tofu
```

**Your turn:** before you run it, predict which program `terraform version` will say it is.

```sh
terraform version
which terraform tofu
```

<!-- dojo-reveal: Results of terraform version -->

- The version line reads `OpenTofu v1.12.6` (or similar).
- `terraform` is a link that points at `tofu`.

<!-- /dojo-reveal -->

## 3. The tour

Track A lives in `sandbox/`. (The files at the top level of the repo, `main.tf`, `locals.tf` and friends, are **Track B**, the cloud part, from Lab 4 onward. Ignore them for now.) Here is what each file in the folder is for:

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

**Your turn:** look inside the folder and read the config; it is short. Before you open `main.tf`, predict: which resource has to be created first, and how would OpenTofu know?

```sh
cd sandbox
ls -la
cat versions.tf
cat main.tf
```

<!-- dojo-reveal: Results of reading the config -->

- `main.tf` uses `random_pet.nickname.id` inside the `local_file`. That reference is how OpenTofu learns *create the pet first*.

<!-- /dojo-reveal -->

## Check yourself

1. Which file would you edit to change a value without touching any resource?
2. Which two things must never be committed?

<!-- dojo-reveal: Show the answer -->

1. `terraform.tfvars`
2. `.terraform/` and state files (see `../.gitignore`)

<!-- /dojo-reveal -->

**Next:** [lab1.md](lab1.md)
