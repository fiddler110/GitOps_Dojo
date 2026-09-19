# OpenTofu Basics Lab

Welcome! This is your personal workspace for the **OpenTofu Basics** session. You will learn the everyday Infrastructure-as-Code loop — **write → init → plan → apply → destroy** — and how a real IaC repository is laid out.

You are working in your own student account. Keep all lab work under this `~/lab` folder.

## OpenTofu, Terraform — what should I type?

Either. This terminal has **OpenTofu** (`tofu`), the open-source fork of Terraform, and `terraform` is set up as a shortcut to it:

```sh
tofu version
terraform version    # same program — prints "OpenTofu ..."
```

The HCL language, the commands, and the files (`*.tf`, `.terraform/`, `terraform.tfstate`) are the same, so everything you learn here transfers to Terraform. The labs say `terraform`; use whichever you like.

## What you'll do

| Lab | Topic | Time | Track |
| --- | ----- | ---- | ----- |
| [lab0.md](lab0.md) | Get the repo and tour what every file is for | ~5 min | A — Sandbox |
| [lab1.md](lab1.md) | `init`, `validate`, `plan`, `apply` — your first run | ~12 min | A — Sandbox |
| [lab2.md](lab2.md) | Change a value and read the plan: `~`, `-/+`, state, outputs | ~12 min | A — Sandbox |
| [lab3.md](lab3.md) | `destroy`, and what is (and isn't) left behind | ~8 min | A — Sandbox |

**Track A (Sandbox)** runs entirely inside your terminal: OpenTofu creates a random name, a text file and a note in its own state. No cloud, no risk — perfect for learning the mechanics. Do Labs 0-3 in order.

Keep [cheat-sheet.md](cheat-sheet.md) open in a split pane (`Ctrl+b %` in tmux) while you work.

Open any lab file with:

```sh
glow lab0.md   # or: nano lab0.md, batcat lab0.md, etc.
```

## Check your shell

```sh
whoami
tofu version
git --version
```

Your username looks like `student01`, `student02`, and so on. Nothing needs downloading: OpenTofu and the providers it needs are already installed. The lab network has no internet — that's why `tofu init` works from a local copy of the providers (you'll see this in Lab 1).
