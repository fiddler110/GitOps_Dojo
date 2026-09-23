# Lab 6 — Break a policy on purpose

**Goal:** make three deliberate mistakes, read the errors the cloud gives back, and learn where each kind of mistake gets caught.

```sh
cd ~/lab/tofu-basics
```

You need Lab 5's deployment still running (`terraform state list` shows two resources).

---

## Policy: the cloud's house rules

Real clouds let an organisation attach **policy** ("Azure Policy"): rules checked on **every** request, whatever tool sent it. Dojo Cloud has these:

| Rule | Error code you'll see |
| ---- | --------------------- |
| Only regions `canadacentral` and `canadaeast` | `RequestDisallowedByPolicy` (policy "Allowed locations") |
| Every resource needs tags `owner` and `env` | `RequestDisallowedByPolicy` (policy "Require tag ...") |
| Resource groups start with `rg-`, container groups with `ci-` | `InvalidResourceGroupName`, `InvalidContainerGroupName` |
| Only images `dojo/hello:1.0` and `dojo/hello:2.0` | `InvalidImage` |
| Between 0.05 and 0.25 vCPU, and 0.03125 and 0.125 GB, per container | `InvalidResourceRequest` |
| Only port 80 | `InvalidRequestContent` |
| At most 2 container groups per subscription | `QuotaExceeded` (Lab 9) |

The important idea: **`plan` cannot see policy.** `plan` only reads your files and (once state exists) refreshes what is there. Policy is checked when a request is actually **sent**, so it fails during `apply`.

Undo your experiments with git as you go: everything you edit is a tracked file, so `git checkout <file>` puts it back.

---

## 1. Mistake one: a missing required tag

Remove the `owner` tag from `locals.tf`: delete the line `owner = var.owner` inside `tags` (line 16), or do it from the terminal:

```sh
sed -i '/^    owner /d' locals.tf
git diff
```

```diff
   tags = {
-    owner      = var.owner
     env        = var.environment
     managed_by = "opentofu"
   }
```

(Only the changed lines are shown; the `git diff` header is trimmed.) Now plan:

```sh
terraform plan
```

Expected (abridged: the "Refreshing state" lines and the footer are trimmed):

```terraform
  # azurerm_container_group.hello will be updated in-place
  ~ resource "azurerm_container_group" "hello" {
        id                          = "/subscriptions/260eb175-.../containerGroups/ci-hello-dev"
        name                        = "ci-hello-dev"
      ~ tags                        = {
            "env"        = "dev"
            "managed_by" = "opentofu"
          - "owner"      = "student01" -> null
        }
        # (13 unchanged attributes hidden)

        # (1 unchanged block hidden)
    }

  # azurerm_resource_group.main will be updated in-place
  ~ resource "azurerm_resource_group" "main" {
        id       = "/subscriptions/260eb175-.../resourceGroups/rg-hello-dev-cac"
        name     = "rg-hello-dev-cac"
      ~ tags     = {
            "env"        = "dev"
            "managed_by" = "opentofu"
          - "owner"      = "student01" -> null
        }
        # (1 unchanged attribute hidden)
    }

Plan: 0 to add, 2 to change, 0 to destroy.
```

The plan looks perfectly reasonable. That is the point: it doesn't know the rule. Apply it:

```sh
terraform apply
```

Type `yes`. It fails in about two seconds:

```text
azurerm_resource_group.main: Modifying... [id=/subscriptions/260eb175-2be3-5b4e-a481-d14ff2e938cf/resourceGroups/rg-hello-dev-cac]

Error: updating "Resource Group (Subscription: \"260eb175-2be3-5b4e-a481-d14ff2e938cf\"\nResource Group Name: \"rg-hello-dev-cac\")": unexpected status 403 (403 Forbidden) with error: RequestDisallowedByPolicy: Resource 'rg-hello-dev-cac' was disallowed by policy. Policy: 'Require tag 'owner''. The resource is missing the required tag 'owner'.

  with azurerm_resource_group.main,
  on main.tf line 4, in resource "azurerm_resource_group" "main":
   4: resource "azurerm_resource_group" "main" {
```

**How to read a cloud error.** Work from the end backwards, the way you'd read a stack trace:

1. `with azurerm_resource_group.main, on main.tf line 4`: **which resource in which file** OpenTofu was working on.
2. `RequestDisallowedByPolicy`: **the error code** (search for this word).
3. `Policy: 'Require tag 'owner''. The resource is missing the required tag 'owner'.`: **which rule, and what to do**.
4. `unexpected status 403`: the HTTP status the cloud answered with (403 = forbidden, 400 = bad request, 409 = conflict).

The cloud named the rule and the tag. Nothing was changed. Undo your edit and confirm:

```sh
git checkout locals.tf
terraform plan
```

Expected: `No changes. Your infrastructure matches the configuration.`

## 2. Mistake two: a region that isn't allowed

Open `terraform.tfvars` and change the location:

```sh
sed -i 's/^location .*/location    = "eastus"/' terraform.tfvars
terraform plan
```

This time it doesn't even reach the cloud:

```text
Planning failed. OpenTofu encountered an error while generating this plan.

Error: Invalid value for variable

  on variables.tf line 21:
  21: variable "location" {
    ├────────────────
    │ var.location is "eastus"

location must be canadacentral or canadaeast (the only regions Dojo Cloud
policy allows).

This was checked by the validation rule at variables.tf:26,3-13.
```

Open `variables.tf` and find the `validation` block on `location`. It repeats the cloud's rule **inside your code**, so the mistake is caught instantly, locally, with a message you wrote yourself. That is the difference between the two layers:

| Layer | Checked when | Speed | Authority |
| ----- | ------------ | ----- | --------- |
| `validation` in `variables.tf` | at `plan`, on your machine | instant | a convenience you write |
| Cloud policy | at `apply`, in the cloud | a real request | the actual rule; can't be bypassed |

**Optional: what does the cloud itself say?** Switch the validation off and ask it. Do this in a **scratch copy** so your real resources are safe (a folder has its own state; if you did it in your real folder, changing a resource group's region would make OpenTofu try to *replace* your working deployment):

```sh
mkdir ~/scratch
cp *.tf terraform.tfvars .terraform.lock.hcl ~/scratch/
cd ~/scratch
terraform init
sed -i '26,29s/^/# /' variables.tf
terraform apply
```

The `sed` puts a `#` in front of lines 26-29, the four lines of the `location` validation block. Type `yes` at the prompt (the plan just says "2 to add", the same as Lab 5). The answer:

```text
azurerm_resource_group.main: Creating...

Error: creating "Resource Group (Subscription: \"260eb175-2be3-5b4e-a481-d14ff2e938cf\"\nResource Group Name: \"rg-hello-dev-eastus\")": unexpected status 403 (403 Forbidden) with error: RequestDisallowedByPolicy: Resource 'rg-hello-dev-eastus' was disallowed by policy. Policy: 'Allowed locations'. Location 'eastus' is not allowed; use one of: canadacentral, canadaeast.

  with azurerm_resource_group.main,
  on main.tf line 4, in resource "azurerm_resource_group" "main":
   4: resource "azurerm_resource_group" "main" {
```

Same rule, same fix, but the cloud is the one enforcing it. (Your subscription ID will differ.) Clean up:

```sh
cd ~/lab/tofu-basics
rm -rf ~/scratch
git checkout terraform.tfvars
```

## 3. Mistake three: too big

Ask for 2 vCPUs instead of 0.25:

```sh
sed -i 's/cpu    = 0.25/cpu    = 2/' main.tf
git diff main.tf
terraform plan
```

Expected (abridged):

```terraform
  # azurerm_container_group.hello must be replaced
-/+ resource "azurerm_container_group" "hello" {
      ~ fqdn                        = "hello-dev-student01.canadacentral.dojo-cloud.test" -> (known after apply)
      ~ id                          = "/subscriptions/260eb175-.../containerGroups/ci-hello-dev" -> (known after apply)
      ~ ip_address                  = "10.20.78.32" -> (known after apply)
        name                        = "ci-hello-dev"
      ...
      ~ container {
          ~ commands                     = [] -> (known after apply)
          ~ cpu                          = 0.25 -> 2 # forces replacement
          ...
            name                         = "hello"
          ...
        }
    }

Plan: 1 to add, 0 to change, 1 to destroy.
```

`# forces replacement`: the size of a container can't be edited in place, so OpenTofu will **destroy** the container and **create** a new one. Again the plan is happy. Apply it, and watch closely:

```sh
terraform apply
```

Type `yes`:

```text
azurerm_container_group.hello: Destroying... [id=/subscriptions/260eb175-2be3-5b4e-a481-d14ff2e938cf/resourceGroups/rg-hello-dev-cac/providers/Microsoft.ContainerInstance/containerGroups/ci-hello-dev]
azurerm_container_group.hello: Still destroying... [id=/subscriptions/260eb175-2be3-5b4e-a481-...rInstance/containerGroups/ci-hello-dev, 10s elapsed]
azurerm_container_group.hello: Destruction complete after 12s
azurerm_container_group.hello: Creating...

Error: creating Container Group (Subscription: "260eb175-2be3-5b4e-a481-d14ff2e938cf"
Resource Group Name: "rg-hello-dev-cac"
Container Group Name: "ci-hello-dev"): performing ContainerGroupsCreateOrUpdate: unexpected status 400 (400 Bad Request) with error: InvalidResourceRequest: Requested 2.0 vCPU / 0.125 GB exceeds the per-container limit of 0.25 vCPU / 0.125 GB.

  with azurerm_container_group.hello,
  on main.tf line 13, in resource "azurerm_container_group" "hello" {
  13: resource "azurerm_container_group" "hello" {
```

**Look at what happened.** The cloud only checks the rules when the *new* container is created, and by then the *old* one had already been destroyed. Check:

```sh
terraform state list
```

```text
azurerm_resource_group.main
```

Your site is **gone**. Look at the portal's **Container instances** page: empty. Refresh your site: 404. This is how real clouds behave too: **policy failures happen at create time, and a failed replacement can leave you with less than you started with.** Always read a plan for `-/+` before you say `yes`, and remember `# forces replacement` means *downtime*.

Recovery is the loop you already know. Undo the edit and apply again:

```sh
git checkout main.tf
terraform apply
```

Type `yes`. The plan is `Plan: 1 to add, 0 to change, 0 to destroy.` and it finishes in about 14 seconds:

```text
azurerm_container_group.hello: Creating...
azurerm_container_group.hello: Still creating... [10s elapsed]
azurerm_container_group.hello: Creation complete after 13s [id=...]

Apply complete! Resources: 1 added, 0 changed, 0 destroyed.
```

That is the GitOps safety net: your code is in git, so getting back to a known-good state is `git checkout` plus `apply`.

## What just happened

Three mistakes, three different catches:

| Mistake | Caught by | When | Damage |
| ------- | --------- | ---- | ------ |
| Missing `owner` tag | cloud policy | `apply` | none (in-place edit rejected) |
| Region `eastus` | your `validation` block (and, if you skip it, cloud policy) | `plan` | none |
| 2 vCPUs | cloud policy | `apply`, *after* the old container was destroyed | site down until you fix it |

## Check yourself

1. Why did `plan` succeed with the missing tag? *(`plan` only computes changes; policy is enforced when a request is sent by `apply`)*
2. What are the three things to find in a cloud error? *(the resource and file line, the error code, the rule/reason)*
3. Why is `-/+` more dangerous than `~`? *(the old resource is destroyed first, so a failure part-way leaves it gone)*

## Troubleshooting

| You see | Cause / fix |
| ------- | ----------- |
| `RequestDisallowedByPolicy` | You broke a rule. The message names the policy ("Allowed locations", "Require tag 'owner'"). Fix your HCL, `apply` again. |
| `InvalidImage` / `InvalidResourceRequest` / `InvalidRequestContent` | Image, size or port outside what's allowed. The message lists the allowed values. |
| `InvalidResourceGroupName` / `InvalidContainerGroupName` | Names must start with `rg-` / `ci-` and use only lowercase letters, digits and hyphens. |
| `Invalid value for variable` | Your own `validation` block caught it at `plan`. Read the `error_message` you wrote. |
| The site is gone after a failed `apply` | See section 3: fix the edit, then `apply` recreates it. |
| You broke something and can't remember what | `git diff` shows exactly what you changed; `git checkout <file>` undoes it. |

**Next:** [lab7.md](lab7.md)
