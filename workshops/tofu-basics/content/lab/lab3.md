# Lab 3 — Tear it down

**Goal:** destroy what you created, and understand what is left behind and what belongs in git.

> **Starting here?** This lab needs your clone, with your name in the sandbox and applied (Labs 1-2). Run `lab-prep 3` to set that up; it's safe to run even if you did the earlier labs.

```sh
cd ~/lab/tofu-basics/sandbox
```

---

## 1. Preview the destroy

```sh
terraform plan -destroy
```

Expected (abridged): every resource shown with `-`, ending in:

```text
Plan: 0 to add, 0 to change, 3 to destroy.
```

`plan -destroy` is a safe preview of teardown — the same "look before you leap" as `plan`.

## 2. Destroy

```sh
terraform destroy
```

Review the plan, type `yes`.

```text
Destroy complete! Resources: 3 destroyed.
```

`terraform destroy` removes **only what is in state**, in reverse dependency order: the file first, then the pet.

## 3. See what's left

```sh
ls -la
ls out/
terraform state list
cat terraform.tfstate
```

- `out/hello.txt` is gone.
- `terraform state list` prints nothing — OpenTofu tracks no resources.
- `terraform.tfstate` still exists but has `"resources": []`.
- `terraform.tfstate.backup` holds the previous state.
- `.terraform/` (the downloaded providers) is untouched — `destroy` doesn't uninstall plugins.

Confirm it is clean:

```sh
terraform plan
```

You'll see `Plan: 3 to add` — nothing exists, so OpenTofu would build it all again. Deleting is just another state your config can be reconciled to.

## 4. What belongs in git?

```sh
cd ..
git status
```

You'll see your `terraform.tfvars` edit — but **not** `terraform.tfstate` or `.terraform/`. Why? Look at `.gitignore`:

```sh
cat .gitignore
```

State can contain secrets in plain text, and it is specific to one person's run, so it is never committed (real teams keep it in a shared, locked remote backend). The lock file **is** committed so everyone uses the same provider versions.

Commit your change on a branch, the same way as every other lab:

```sh
git checkout -b my-tofu-change
git add sandbox/terraform.tfvars
git commit -m "Set my name in the sandbox"
git push -u origin my-tofu-change
```

This pushes to **your fork** (the `origin` you cloned in Lab 0), so your branch name can't clash with anyone else's. Pushing asks you to sign in to the git server — in VS Code a popup appears at the top of the screen (username, then password); in the plain terminal you get a `Username for 'http://git-server:3000':` prompt. Use your student account name (`studentXX`) and your **Forgejo password**. Both are shown on your landing page (the page with the VS Code, Terminal and Forgejo cards; reloading it always brings it back), the same as in Git Fundamentals.

## Track A complete

You have used the whole lifecycle: **init → validate → plan → apply → change → plan → apply → destroy**, and know the file layout of a Terraform/OpenTofu repo.

**Next: Track B.** In [lab4.md](lab4.md) you leave the sandbox and deploy a real container to "Dojo Cloud", a practice cloud that works like Azure. The commands are the ones you just learned.

## Check yourself

1. What does `destroy` remove? *(everything tracked in state)*
2. Why is `terraform.tfstate` in `.gitignore`, but `.terraform.lock.hcl` is not? *(state may hold secrets and is per-run; the lock file makes everyone use identical providers)*
3. After `destroy`, would `plan` show changes? *(yes — 3 to add; the config still describes them)*
