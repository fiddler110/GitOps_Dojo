# tofu-basics

A small Infrastructure-as-Code repository for learning the OpenTofu/Terraform workflow.
`terraform` and `tofu` are the same program in the lab terminal.

| Path | What it is |
| ---- | ---------- |
| `sandbox/` | **Track A** — an offline sandbox (random name, a file, a note). Start here. |
| `.gitignore` | keeps state and downloaded providers out of git |

Follow the lab instructions in `~/lab` (start with `lab0.md`).

## Commit / don't commit

Commit: `*.tf`, `*.tfvars` (no secrets), `.terraform.lock.hcl`.
Never commit: `.terraform/`, `*.tfstate*` — see `.gitignore`.
