# Lab 10 — Clean up

**Goal:** destroy everything you built, prove the cloud is empty, understand what OpenTofu leaves behind, and commit your work.

```sh
cd ~/lab/tofu-basics
```

Cloud resources cost money and, here, count against your quota. Real teams destroy what they don't need, and they check that it is actually gone.

---

## 1. Preview the destroy

```sh
terraform plan -destroy -no-color | grep -E '^  # |^Plan:'
```

(`-no-color` keeps OpenTofu from wrapping the lines in colour codes, which would hide them from `grep`.) Expected (yours may show `["green"]`, and will show one fewer or more line if you changed the number of extras):

```text
  # azurerm_container_group.extra["blue"] will be destroyed
  # azurerm_container_group.hello will be destroyed
  # azurerm_resource_group.main will be destroyed
Plan: 0 to add, 0 to change, 3 to destroy.
```

Everything in state, and nothing else. `destroy` removes what OpenTofu created and tracks; it can't remove things it doesn't know about.

## 2. Destroy

```sh
terraform destroy
```

Review the plan, type `yes`:

```text
azurerm_container_group.hello: Destroying... [id=/subscriptions/260eb175-...]
azurerm_container_group.extra["blue"]: Destroying... [id=/subscriptions/260eb175-...]
azurerm_container_group.extra["blue"]: Still destroying... [id=/subscriptions/260eb175-...ance/containerGroups/ci-hello-dev-blue, 10s elapsed]
azurerm_container_group.hello: Still destroying... [id=/subscriptions/260eb175-...rInstance/containerGroups/ci-hello-dev, 10s elapsed]
azurerm_container_group.extra["blue"]: Destruction complete after 13s
azurerm_container_group.hello: Destruction complete after 13s
azurerm_resource_group.main: Destroying... [id=/subscriptions/260eb175-...]
azurerm_resource_group.main: Still destroying... [id=/subscriptions/260eb175-...e938cf/resourceGroups/rg-hello-dev-cac, 10s elapsed]
azurerm_resource_group.main: Still destroying... [id=/subscriptions/260eb175-...e938cf/resourceGroups/rg-hello-dev-cac, 20s elapsed]
azurerm_resource_group.main: Destruction complete after 20s

Destroy complete! Resources: 3 destroyed.
```

About 35 seconds. Notice the **order**: the two containers (which don't depend on each other) go **in parallel**, and the resource group goes **last**, because the containers depend on it. Destroy runs the dependency graph in reverse.

## 3. Verify: is it really gone?

Don't trust the terminal alone. Check the cloud itself. In the portal:

- **Home**: `0 resource groups`, `0 container instances`, **Quota: 0 / 2**, and the "Nothing here yet" message.
- **Resource groups** and **Container instances**: empty.
- **Activity log**: the newest rows are the deletions, `Delete container group` and `Delete resource group`, by you.
- Your site's link now shows "No site is deployed under that name (yet)."

Then look at what OpenTofu remembers:

```sh
terraform state list
ls -la terraform.tfstate*
cat terraform.tfstate
```

`terraform state list` prints nothing. Then:

```text
-rw-r--r-- 1 student01 student01  821 Sep 19 14:32 terraform.tfstate
-rw-r--r-- 1 student01 student01 5634 Sep 19 14:32 terraform.tfstate.backup
```

```text
{
  "version": 4,
  "terraform_version": "1.12.6",
  "serial": 13,
  "lineage": "0538175a-f7d2-fa2b-bd32-2b7bda431105",
  "outputs": {},
  "resources": [],
  "check_results": [
    ...
  ]
}
```

(Sizes, dates, `serial` and `lineage` will differ; the `check_results` part is trimmed.) The state file still exists, but `"resources": []` and `"outputs": {}`: it remembers that it manages **nothing**. `terraform.tfstate.backup` is the previous state, the last time it held your resources.

Compare with Lab 3: same idea, different provider. `.terraform/` and `.terraform.lock.hcl` are also still there; `destroy` doesn't uninstall plugins.

Now ask what a plan would do:

```sh
terraform plan -no-color | grep '^Plan:'
```

```text
Plan: 3 to add, 0 to change, 0 to destroy.
```

Your **code** still describes those three resources, so `apply` would build it all again. Destroying is just another state your config can be reconciled to; your `.tf` files are the source of truth, not the cloud.

## 4. Commit your work

The cloud is empty, but your code isn't lost: it's in the repo. See what changed:

```sh
git status --short
```

You'll see only the tracked files you edited (for example `locals.tf`, `main.tf`, `terraform.tfvars`), **not** `terraform.tfstate` or `.terraform/`: `.gitignore` keeps them out, exactly as in Lab 3. Commit on a branch and push it, as in the earlier labs:

```sh
git checkout -b my-dojo-cloud-change
git add locals.tf main.tf terraform.tfvars
git commit -m "Track B: cost_center tag, Hello Canada, 2.0 image, for_each sites"
git push -u origin my-dojo-cloud-change
```

(Add only the files that `git status` shows as modified.) Pushing asks for your git login: your student account name (for example `student01`) and your **Forgejo password**, both shown on your landing page, as before. The server's reply prints a link for opening a pull request:

```text
remote: Create a new pull request for 'my-dojo-cloud-change':
```

Because you cloned your fork, that link proposes your branch to the team's `iac-team/tofu-basics` repo: the usual way to get a change reviewed.

Anyone with access to the repo can now review, reproduce and re-deploy exactly what you built: `git clone`, `terraform init`, `terraform apply`. **That is Infrastructure as Code.**

## Track B complete

You have used the whole lifecycle against a cloud: **init → plan → apply → (drift, changes, policy, scale) → destroy**, and read the results in a portal that works like Azure's. The `.tf` files are the same ones you'd write for real Azure: only the provider's settings (the `ARM_*` variables) would point somewhere else.

Where to go next, in a real project: keep state in a shared, locked **remote backend** instead of a local file; split repeated code into **modules**; run `plan` automatically on every pull request; and use **policy** to keep whole teams inside safe limits.

## Check yourself

1. How can you prove the cloud is empty, without trusting OpenTofu? *(look at the portal: Resource groups, Container instances, Quota 0 / 2, or the Activity log)*
2. After `destroy`, why does `plan` still say `3 to add`? *(your code still describes them; state is empty, so everything is "new")*
3. What must never be committed from this repo? *(`terraform.tfstate*` and `.terraform/`, both listed in `.gitignore`)*

## Troubleshooting

| You see | Cause / fix |
| ------- | ----------- |
| `Error: a resource with the ID ... already exists ... needs to be imported into the State` | OpenTofu has lost track of something it created, usually because `terraform.tfstate` was deleted or you're in the wrong folder. The cloud still has the resource, but your state doesn't know. **Ask the facilitator to Purge your subscription** (they can empty it in the portal), then run `terraform apply` again. |
| `destroy` finishes but the portal still shows a resource | It refreshes every ~3 s. Click **Refresh now**. If it's still there, it wasn't created by this state (an old deleted state file?): ask the facilitator to Purge your subscription. |
| `git push` says `! [rejected] ... (fetch first)`, or its output shows `iac-team/tofu-basics` | You cloned the team repo, not your fork, and someone already pushed that branch name there. Do Lab 0 step 1 (fork), then `git remote set-url origin http://git-server:3000/$USER/tofu-basics.git` and push again. |
| `git push` asks for a password over and over | Use your student account name and the **Forgejo password** shown on your landing page. In VS Code the prompt is a popup at the top of the window. |
| `terraform state list` prints nothing but the portal has resources | You're in the wrong folder, or the state file was deleted. `cd ~/lab/tofu-basics` and check `ls terraform.tfstate`. |
