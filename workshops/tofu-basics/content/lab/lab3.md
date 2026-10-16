# Lab 3 — Tear it down

**Goal:** destroy what you created, and understand what is left behind and what belongs in git.

> **Starting here?** This lab needs your clone, with your name in the sandbox and applied (Labs 1-2). Run `dojo prep 3` to set that up; it's safe to run even if you did the earlier labs.

```sh
cd ~/lab/tofu-basics/sandbox
```

---

## 1. Preview the destroy

`plan -destroy` is a safe preview of teardown: the same "look before you leap" as `plan`, but it shows what would be removed.

```text
terraform plan -destroy
```

**Your turn:** predict how many resources it will list, and with which symbol.

```sh
terraform plan -destroy
```

<!-- dojo-reveal: Results of plan -destroy -->

Expected (abridged): every resource shown with `-`, ending in:

```text
Plan: 0 to add, 0 to change, 3 to destroy.
```

<!-- /dojo-reveal -->

## 2. Destroy

`terraform destroy` removes **only what is in state**, in reverse dependency order, so anything that depends on another resource goes first.

```text
terraform destroy
```

**Your turn:** before you run it, predict: the file or the pet first? Review the plan, type `yes`.

```sh
terraform destroy
```

<!-- dojo-reveal: Results of destroy -->

```text
Destroy complete! Resources: 3 destroyed.
```

- The file went first, then the pet.

<!-- /dojo-reveal -->

## 3. See what's left

Destroy removes resources, not the files OpenTofu keeps about them.

**Your turn:** before you run these, predict what will be gone and what will remain.

```sh
ls -la
ls out/
terraform state list
cat terraform.tfstate
```

<!-- dojo-reveal: Results of looking at what is left -->

- `out/hello.txt` is gone.
- `terraform state list` prints nothing — OpenTofu tracks no resources.
- `terraform.tfstate` still exists but has `"resources": []`.
- `terraform.tfstate.backup` holds the previous state.
- `.terraform/` (the downloaded providers) is untouched — `destroy` doesn't uninstall plugins.

<!-- /dojo-reveal -->

Confirm it is clean. Predict what `plan` says when nothing exists but the config still describes three resources.

```sh
terraform plan
```

<!-- dojo-reveal: Results of plan -->

- You'll see `Plan: 3 to add`: nothing exists, so OpenTofu would build it all again. Deleting is just another state your config can be reconciled to.

<!-- /dojo-reveal -->

## 4. What belongs in git?

State can contain secrets in plain text, and it is specific to one person's run, so it is never committed (real teams keep it in a shared, locked remote backend). The lock file **is** committed so everyone uses the same provider versions. The `.gitignore` file at the repo root is what keeps state and `.terraform/` out.

**Your turn:** go up to the repo root and check git's view. Before you run it, predict which of your files git will list.

```sh
cd ..
git status
cat .gitignore
```

<!-- dojo-reveal: Results of git status -->

- You'll see your `terraform.tfvars` edit, but **not** `terraform.tfstate` or `.terraform/`. The `.gitignore` explains why.

<!-- /dojo-reveal -->

Commit your change on a branch, the same way as every other lab:

```sh
git checkout -b my-tofu-change
git add sandbox/terraform.tfvars
git commit -m "Set my name in the sandbox"
git push -u origin my-tofu-change
```

This pushes to **your fork** (the `origin` you cloned in Lab 0), so your branch name can't clash with anyone else's. Git signs in with your access token (in `~/.git-credentials`), so there's no password prompt.

## Track A complete

You have used the whole lifecycle: **init → validate → plan → apply → change → plan → apply → destroy**, and know the file layout of a Terraform/OpenTofu repo.

**Next: Track B.** In [lab4.md](lab4.md) you leave the sandbox and deploy a real container to "Dojo Cloud", a practice cloud that works like Azure. The commands are the ones you just learned.

## Check yourself

1. What does `destroy` remove?
2. Why is `terraform.tfstate` in `.gitignore`, but `.terraform.lock.hcl` is not?
3. After `destroy`, would `plan` show changes?

<!-- dojo-reveal: Show the answer -->

1. Everything tracked in state.
2. State may hold secrets and is per-run; the lock file makes everyone use identical providers.
3. Yes: 3 to add, because the config still describes them.

<!-- /dojo-reveal -->
