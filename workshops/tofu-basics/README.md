# tofu-basics — OpenTofu Basics Lab

Teaches the Terraform-style workflow (`init` → `plan` → `apply` → `destroy`)
and how an IaC repo is structured, using **OpenTofu**. Students can type
`terraform` and get `tofu` — the commands and HCL are identical.

```sh
cd engine && ./run.sh tofu-basics
```

- **Track A — Sandbox** (offline, no cloud): `random_pet`, `local_file`,
  `terraform_data`. Runs today.
- **Track B — Dojo Cloud** (Azure-inspired container deploy): in progress.

Design, decisions, task list and progress log: [`PLAN.md`](PLAN.md).
