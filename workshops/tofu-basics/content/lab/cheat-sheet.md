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
