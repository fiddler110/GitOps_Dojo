# tofu-basics — OpenTofu Basics Lab

Teaches the Terraform-style workflow (`init` → `plan` → `apply` → `destroy`)
and how an IaC repo is structured, using **OpenTofu**. Students can type
`terraform` and get `tofu` — the commands and HCL are identical.

```sh
cd engine && ./run.sh tofu-basics
```

- **Track A — Sandbox** (offline, no cloud): `random_pet`, `local_file`,
  `terraform_data`. Labs 0-3.
- **Track B — Dojo Cloud** (Azure-inspired container deploy through the real
  `azurerm` provider, with a portal, policy and quotas). Labs 4-10.

A full README (architecture, security notes, facilitator guide) is still to
write; see task T8.1 in `PLAN.md`.

Design, decisions, task list and progress log: [`PLAN.md`](PLAN.md).
