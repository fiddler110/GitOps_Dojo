# OpenTofu / Terraform Cheat Sheet

`terraform` and `tofu` are the same program in this terminal. Use either.

## The loop

```text
edit .tf files → init → validate → plan → apply → (change → plan → apply)… → destroy
```

| Command | What it does | Changes anything? |
| ------- | ------------ | ----------------- |
| `terraform init` | Install providers, prepare the folder. Once per folder. | Only `.terraform/` |
| `terraform validate` | Check syntax and references. | No |
| `terraform fmt` | Auto-format `.tf` files. | Your files (style only) |
| `terraform plan` | Show what would change. | **No** |
| `terraform apply` | Plan, ask, then do it. | **Yes** |
| `terraform destroy` | Remove everything in state. | **Yes** |
| `terraform plan -destroy` | Preview a destroy. | No |
| `terraform output [name]` | Print outputs. | No |
| `terraform show` | Print everything in state. | No |
| `terraform state list` | List tracked resources. | No |
| `terraform plan -replace=ADDR` | Preview rebuilding one resource. | No |
| `terraform plan -var name=value` | Override a variable for one run. | No |

## Plan symbols

| Symbol | Meaning |
| ------ | ------- |
| `+` | create |
| `~` | update in place |
| `-` | destroy |
| `-/+` | replace (destroy, then create) |
| `+/-` | replace, but create the new one first (`create_before_destroy`) |
| `(known after apply)` | value doesn't exist until it's created |
| `# forces replacement` | this attribute can't be edited in place |

## What each file is for

| File | Purpose | Commit? |
| ---- | ------- | ------- |
| `versions.tf` | required OpenTofu + provider versions | yes |
| `providers.tf` | provider settings | yes |
| `variables.tf` | inputs (type, default, validation) | yes |
| `locals.tf` | computed names and tags | yes |
| `main.tf` | the resources | yes |
| `outputs.tf` | values printed after apply | yes |
| `terraform.tfvars` | your values for the variables | yes (no secrets) |
| `.terraform.lock.hcl` | pinned provider versions + checksums | **yes** |
| `.terraform/` | downloaded providers | no |
| `terraform.tfstate` | what OpenTofu created | **no** |

## HCL in 30 seconds

```hcl
variable "name" { type = string }                    # input:  var.name
locals { greeting = "Hi ${var.name}" }               # local:  local.greeting
resource "random_pet" "x" { length = 2 }             # resource: random_pet.x
output "pet" { value = random_pet.x.id }             # output
```

A reference like `random_pet.x.id` creates a dependency — OpenTofu orders the work for you.

---

# Track B: Dojo Cloud

Work in `~/lab/tofu-basics` (the top of the repo, not `sandbox/`). Same loop as Track A, plus the portal (landing page > **Dojo Cloud** card) to watch what you built. The portal refreshes itself every ~3 seconds.

## Timings to expect

| Step | Takes |
| ---- | ----- |
| `init` | ~2 s |
| `apply` (resource group + container) | ~35 s (group ~20 s, container ~13 s) |
| in-place edit (`~`, a tag) | ~1-2 s |
| replace (`-/+`, message or image) | ~27 s, and the site is down meanwhile |
| `destroy` | ~35 s |

## Your credentials (already in your environment)

| Variable | Meaning |
| -------- | ------- |
| `ARM_TENANT_ID`, `ARM_SUBSCRIPTION_ID` | which tenant and which subscription are yours |
| `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET` | your "service principal" login (never paste the secret) |
| `ARM_METADATA_HOSTNAME` | where the cloud's API lives (`management.dojo.cloud`) |
| `TF_VAR_owner` | your username, becomes `var.owner` (any `TF_VAR_x` becomes `var.x`) |
| `TF_VAR_portal_base_url` | start of the site link in the `url` output |

```sh
env | grep -E '^(ARM_|TF_VAR_)' | grep -v SECRET
```

## Words

| Term | Meaning |
| ---- | ------- |
| Subscription | your private slice of the cloud (ID in the portal Home) |
| Resource group (`rg-...`) | folder for related resources |
| Container instance / group (`ci-...`) | a running container (`azurerm_container_group`) |
| Tags | labels; `owner` and `env` are **required** |
| Policy | rules the cloud enforces at `apply` time |
| Quota | hard limit: 2 container groups per subscription |
| Drift | reality changed outside your code |

## Dojo Cloud rules (policy)

| Rule | Error code |
| ---- | ---------- |
| Regions: `canadacentral` (default) or `canadaeast` only | `RequestDisallowedByPolicy` ("Allowed locations") |
| Tags `owner` and `env` required | `RequestDisallowedByPolicy` ("Require tag ...") |
| Names: `rg-...` for resource groups, `ci-...` for container groups | `InvalidResourceGroupName`, `InvalidContainerGroupName` |
| Images: `dojo/hello:1.0` or `dojo/hello:2.0` only | `InvalidImage` |
| Size: at most 0.25 vCPU and 0.125 GB | `InvalidResourceRequest` |
| Port 80 only | `InvalidRequestContent` |
| Site name (`dns_name_label`) unique across the class | `DnsNameLabelInUse` |
| At most 2 container groups | `QuotaExceeded` |

Naming used in the starter (Cloud Adoption Framework style): `rg-<workload>-<env>-<region>` (e.g. `rg-hello-dev-cac`), `ci-<workload>-<env>` (e.g. `ci-hello-dev`).

## Which edits change in place, which rebuild

| Edit to a container group | Plan |
| ------------------------- | ---- |
| a tag | `~` in place |
| environment variable (message), image, size, DNS label | `-/+` replace (`# forces replacement`) |

## Track B commands

| Command | What it does |
| ------- | ------------ |
| `terraform apply -replace=ADDR` | rebuild one resource even though nothing changed |
| `terraform state list` | what OpenTofu is tracking (`azurerm_container_group.hello`) |
| `terraform output url` | the link to your site |
| `terraform fmt` | tidy the formatting of your `.tf` files |
| `git diff` / `git checkout FILE` | see, or undo, your edits (a quick way out of a mistake) |

## Reading a cloud error

```text
Error: ...: unexpected status 403 (403 Forbidden) with error: RequestDisallowedByPolicy: Resource 'rg-hello-dev-cac' was disallowed by policy. Policy: 'Require tag 'owner''. The resource is missing the required tag 'owner'.

  with azurerm_resource_group.main,
  on main.tf line 4, in resource "azurerm_resource_group" "main":
```

1. `with ..., on main.tf line N`: which resource, which file.
2. The code (`RequestDisallowedByPolicy`): what kind of problem.
3. The text after it: which rule, and what to change.

## Troubleshooting

| You see | What it means / what to do |
| ------- | -------------------------- |
| `Error: a resource with the ID ... already exists ... needs to be imported into the State` | OpenTofu lost its memory (state deleted, or wrong folder), but the resource is still in the cloud. **Ask the facilitator to Purge your subscription** in the Portal, then `apply` again. Never delete `terraform.tfstate` yourself. |
| `RequestDisallowedByPolicy` | You broke a house rule. The message names it (`Allowed locations`, `Require tag 'owner'`). Fix the code, `apply` again. `plan` can't warn you: policy is checked at `apply`. |
| `Invalid value for variable` | Your own `validation` block caught it at `plan`. Read the `error_message`. |
| `QuotaExceeded` | You already have 2 container groups. Destroy one (or shrink `for_each`). `plan` can't predict quotas. |
| Region / location error | Only `canadacentral` and `canadaeast` are allowed. Check `location` in `terraform.tfvars`. |
| The portal looks stale | It polls every ~3 s. Click **Refresh now**. `terraform state list` is what OpenTofu believes. |
| Site missing after a failed `apply` | A replace (`-/+`) destroys the old container first. Fix the cause and `apply`; see Lab 6. |
| `Error: Required plugins are not installed ... run: tofu init` | Run `terraform init` in `~/lab/tofu-basics`. The message says `tofu` because `terraform` **is** OpenTofu. |
| `var.owner` asks you for a value | Your shell has no `TF_VAR_owner`. Open a new terminal tab. Still asking? Tell the facilitator. |
| The link from `url` doesn't open | Use **Browse** on the container in the portal instead. |
