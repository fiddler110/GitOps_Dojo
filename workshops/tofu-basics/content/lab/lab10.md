# Lab 10 — Clean up

**Goal:** destroy everything you built, prove the cloud is empty, understand what OpenTofu leaves behind, and commit your work.

> **Starting here?** This lab needs something deployed to clean up: hello (Lab 5). Run `dojo prep 10` to set that up; it's safe to run even if you did the earlier labs.

```sh
cd ~/lab/tofu-basics
```

Cloud resources cost money and, here, count against your quota. Real teams destroy what they don't need, and they check that it is actually gone.

---

## 1. Preview the destroy

`destroy` removes what OpenTofu created and tracks; it can't remove things it doesn't know about. `plan -destroy` previews exactly that.

**Your turn:** before you run it, predict how many resources are listed. (`-no-color` keeps OpenTofu from wrapping the lines in colour codes, which would hide them from `grep`.)

```sh
terraform plan -destroy -no-color | grep -E '^  # |^Plan:'
```

<!-- dojo-reveal: Results of plan -destroy -->

Expected (yours may show `["green"]`, and will show one fewer or more line if you changed the number of extras):

```text
  # azurerm_container_group.extra["blue"] will be destroyed
  # azurerm_container_group.hello will be destroyed
  # azurerm_resource_group.main will be destroyed
Plan: 0 to add, 0 to change, 3 to destroy.
```

Everything in state, and nothing else.

<!-- /dojo-reveal -->

## 2. Destroy

Destroy runs the dependency graph in reverse: things that depend on others go first, and independent things go in parallel.

**Your turn:** before you run it, predict the order: which goes last?

```sh
terraform destroy
```

Review the plan, type `yes`.

<!-- dojo-reveal: Results of destroy -->

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

<!-- /dojo-reveal -->

## 3. Verify: is it really gone?

Don't trust the terminal alone: check the cloud itself, then look at what OpenTofu remembers. Same idea as Lab 3, different provider: the state file stays behind, as do `.terraform/` and `.terraform.lock.hcl` (`destroy` doesn't uninstall plugins).

**Your turn:** in the portal, look at Home, Resource groups, Container instances and the Activity log, and open your site's link. Then run the commands below. Predict what each will show.

```sh
terraform state list
ls -la terraform.tfstate*
cat terraform.tfstate
```

<!-- dojo-reveal: Results of the portal and state checks -->

In the portal:

- **Home**: `0 resource groups`, `0 container instances`, **Quota: 0 / 2**, and the "Nothing here yet" message.
- **Resource groups** and **Container instances**: empty.
- **Activity log**: the newest rows are the deletions, `Delete container group` and `Delete resource group`, by you.
- Your site's link now shows "No site is deployed under that name (yet)."

In the terminal, `terraform state list` prints nothing. Then:

```text
-rw-r--r-- 1 studentXX studentXX  821 Sep 19 14:32 terraform.tfstate
-rw-r--r-- 1 studentXX studentXX 5634 Sep 19 14:32 terraform.tfstate.backup
```

```text
{
  "version": 4,
  "terraform_version": "1.12.8",
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

<!-- /dojo-reveal -->

Now ask what a plan would do. Predict first: the cloud is empty, but your code is still there.

```sh
terraform plan -no-color | grep '^Plan:'
```

<!-- dojo-reveal: Results of plan -->

```text
Plan: 3 to add, 0 to change, 0 to destroy.
```

Your **code** still describes those three resources, so `apply` would build it all again. Destroying is just another state your config can be reconciled to; your `.tf` files are the source of truth, not the cloud.

<!-- /dojo-reveal -->

## 4. Commit your work

The cloud is empty, but your code isn't lost: it's in the repo. `.gitignore` keeps `terraform.tfstate` and `.terraform/` out, exactly as in Lab 3, so only the tracked files you edited show up. Committing on a branch and pushing it works as in the earlier labs; the push goes to your fork.

**Your turn:** see what changed. Predict which files git lists.

```sh
git status --short
```

<!-- dojo-reveal: Results of git status -->

You'll see only the tracked files you edited (for example `locals.tf`, `main.tf`, `terraform.tfvars`), **not** `terraform.tfstate` or `.terraform/`.

<!-- /dojo-reveal -->

Now commit on a branch and push it:

```sh
git checkout -b my-dojo-cloud-change
git add locals.tf main.tf terraform.tfvars
git commit -m "Track B: cost_center tag, Hello Canada, 2.0 image, for_each sites"
git push -u origin my-dojo-cloud-change
```

(Add only the files that `git status` shows as modified.) Git signs in with your token, as before. The server's reply prints a link for opening a pull request:

```text
remote: Create a new pull request for 'my-dojo-cloud-change':
```

Because you cloned your fork, that link proposes your branch to the team's `iac-team/tofu-basics` repo: the usual way to get a change reviewed.

Anyone with access to the repo can now review, reproduce and re-deploy exactly what you built: `git clone`, `terraform init`, `terraform apply`. **That is Infrastructure as Code.**

## Track B complete

You have used the whole lifecycle against a cloud: **init → plan → apply → (drift, changes, policy, scale) → destroy**, and read the results in a portal that works like Azure's. The `.tf` files are the same ones you'd write for real Azure: only the provider's settings (the `ARM_*` variables) would point somewhere else.

Where to go next, in a real project: keep state in a shared, locked **remote backend** instead of a local file; split repeated code into **modules**; run `plan` automatically on every pull request; and use **policy** to keep whole teams inside safe limits.

## Check yourself

1. How can you prove the cloud is empty, without trusting OpenTofu?
2. After `destroy`, why does `plan` still say `3 to add`?
3. What must never be committed from this repo?

<!-- dojo-reveal: Show the answer -->

1. Look at the portal: Resource groups, Container instances, Quota 0 / 2, or the Activity log.
2. Your code still describes them; state is empty, so everything is "new".
3. `terraform.tfstate*` and `.terraform/`, both listed in `.gitignore`.

<!-- /dojo-reveal -->

## Troubleshooting

| You see | Cause / fix |
| ------- | ----------- |
| `Error: a resource with the ID ... already exists ... needs to be imported into the State` | OpenTofu has lost track of something it created, usually because `terraform.tfstate` was deleted or you're in the wrong folder. The cloud still has the resource, but your state doesn't know. **Ask the facilitator to Purge your subscription** (they can empty it in the portal), then run `terraform apply` again. |
| `destroy` finishes but the portal still shows a resource | It refreshes every ~3 s. Click **Refresh now**. If it's still there, it wasn't created by this state (an old deleted state file?): ask the facilitator to Purge your subscription. |
| `git push` says `! [rejected] ... (fetch first)`, or its output shows `iac-team/tofu-basics` | You cloned the team repo, not your fork, and someone already pushed that branch name there. Do Lab 0 step 1 (fork), then `git remote set-url origin http://git-server:3000/$USER/tofu-basics.git` and push again. |
| `git push` asks for a username or password | Your token is missing or was changed. Check `ls -l ~/.git-credentials`; if it's gone or empty, ask the facilitator. |
| `terraform state list` prints nothing but the portal has resources | You're in the wrong folder, or the state file was deleted. `cd ~/lab/tofu-basics` and check `ls terraform.tfstate`. |

---

## Challenge c2 (bonus)

Only when your class has achievements on (you see a score on your landing page). A challenge is a goal with no steps, in
a repo of your own, for extra points. Start it in the terminal:

```sh
dojo challenge start c2
cd ~/lab/challenge-c2
```

That makes your own repo `$USER/challenge-c2`, clones it to `~/lab/challenge-c2` and shows your brief. The brief is
saved as `~/challenge-c2.md` with your own names filled in; read it again any time with `glow ~/challenge-c2.md`. When you think
it's done:

```sh
dojo check c2
```

A wrong answer costs nothing. `dojo check hint c2` gives a hint for part of the points (hints already used stay used).

**Start over.** `dojo challenge reset c2` deletes `~/lab/challenge-c2` (including any uncommitted work),
builds a fresh copy and clones it, as often as you like.

## Quota Whisperer

The code in your repo declares five sites, but your subscription holds only two container groups in total. The apply fails on quota. Make it succeed without asking for more quota. Start it now that this lab has freed your quota.

**End result (what the check looks for)**

- Work in your own repo `<you>/challenge-c2` and your own Dojo Cloud subscription.
- One or two `challenge=c2` containers are running (any count from 1 to 2 passes), each named `<you>-c2-...` with the `owner` and `env` tags.
- `main.tf` on `main` (pushed) no longer declares the original list of five sites.

---

## Capstone (bonus)

Only when your class has achievements on (you see a score on your landing page). A capstone is a goal with no steps, in
a repo of your own, for extra points. Start it in the terminal:

```sh
dojo challenge start capstone
cd ~/lab/site-factory
```

That makes your own repo `$USER/site-factory`, clones it to `~/lab/site-factory` and shows your brief. The brief is
saved as `~/capstone.md` with your own names filled in; read it again any time with `glow ~/capstone.md`. When you think
it's done:

```sh
dojo check capstone
```

Run it twice: once while both sites run, then again after `tofu destroy` (the first check says what's next).

A wrong answer costs nothing. `dojo check hint capstone` gives a hint for part of the points (hints already used stay used).

**Start over.** `dojo challenge reset capstone` deletes `~/lab/site-factory` (including any uncommitted work),
builds a fresh copy and clones it, as often as you like.

## Site Factory

Starting from a near-empty repo, build the code for two differently named sites from one `for_each`, each with the required tags, and an output map of names to URLs. When both are running, check; then tear everything down cleanly and check again.

**End result (what the check looks for)**

- Work in your own repo `<you>/site-factory` and your own Dojo Cloud subscription. Needs both of your container groups, so destroy old lab sites first.
- **Step 1, while the sites run:** exactly two `challenge=capstone` containers, named `<you>-...`, in an allowed region, with the `owner` and `env` tags; and `main.tf` on `main` uses `for_each`.
- **Step 2, after `tofu destroy`:** no `challenge=capstone` container group is left.
