# tofu-basics

A small Infrastructure-as-Code repository for learning the OpenTofu/Terraform workflow.
`terraform` and `tofu` are the same program in the lab terminal.

| Path | What it is |
| ---- | ---------- |
| `sandbox/` | **Track A** — an offline sandbox (random name, a file, a note). Start here. |
| `versions.tf`, `providers.tf` | **Track B** — required OpenTofu/provider versions; the `azurerm` provider settings (no credentials in code) |
| `variables.tf`, `locals.tf` | **Track B** — inputs with `validation` rules, and CAF-style names and required tags |
| `main.tf`, `outputs.tf` | **Track B** — a resource group and a container group on "Dojo Cloud"; the values printed after `apply` |
| `terraform.tfvars` | **Track B** — the values you edit (location, environment, message, image version) |
| `.terraform.lock.hcl` | **Track B** — the exact `azurerm` version and checksums (commit it) |
| `.gitignore` | keeps state and downloaded providers out of git |

Follow the lab instructions in `~/lab` (start with `lab0.md`). Track A is labs 0-3, Track B (Dojo Cloud) is labs 4-10.

Track B needs the lab's Dojo Cloud: your cloud credentials are already in your shell environment
(`ARM_*` and `TF_VAR_owner`), which is why none of the files above contain a login or an address.

## Commit / don't commit

Commit: `*.tf`, `*.tfvars` (no secrets), `.terraform.lock.hcl`.
Never commit: `.terraform/`, `*.tfstate*` — see `.gitignore`.
