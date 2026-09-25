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
| [lab4.md](lab4.md) | Meet Dojo Cloud: the portal, your credentials, `init` for a real cloud provider | ~8 min | B — Dojo Cloud |
| [lab5.md](lab5.md) | Deploy hello: `apply` a container, open the site, watch the portal | ~10 min | B — Dojo Cloud |
| [lab6.md](lab6.md) | Break a policy on purpose and read the cloud's errors | ~12 min | B — Dojo Cloud |
| [lab7.md](lab7.md) | Drift: change things in the portal, then `plan` and `apply` | ~8 min | B — Dojo Cloud |
| [lab8.md](lab8.md) | In-place (`~`) vs replace (`-/+`), `-replace`, `create_before_destroy` | ~12 min | B — Dojo Cloud |
| [lab9.md](lab9.md) | Scale it with `for_each` and run into a quota | ~8 min | B — Dojo Cloud |
| [lab10.md](lab10.md) | Clean up: `destroy`, verify the cloud is empty, state after destroy, commit | ~8 min | B — Dojo Cloud |

**Track A (Sandbox)** runs entirely inside your terminal: OpenTofu creates a random name, a text file and a note in its own state. No cloud, no risk — perfect for learning the mechanics. Do Labs 0-3 in order.

**Track B (Dojo Cloud)** deploys a real container to a practice cloud that works like Azure: you get your own subscription, a web **portal** to watch it, and **policy** and **quota** rules to run into. It is an Azure-*inspired* training environment (not affiliated with Microsoft) but you use the real `azurerm` provider, so the HCL you write is genuine Azure HCL. Do Labs 4-10 in order, after Track A. Each lab builds on the previous one's deployment, so don't destroy anything until Lab 10. Open the portal from the landing page's **Dojo Cloud** card, and keep it open in its own tab.

**Starting partway through?** Run `lab-prep <N>` in your terminal (for example `lab-prep 6`). It sets up what the earlier labs would have left behind (your fork and clone, `init`, the deployment and its edits) so you can start Lab N right away. Each lab also says what it needs at the top.

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

Your username looks like `student01`, `student02`, and so on. Your landing page (the page with the tool cards) shows it again, together with your **Forgejo password**, which you need in Lab 0 to fork the starter repo and in Labs 3 and 10 when you push to git. Nothing needs downloading: OpenTofu and the providers it needs are already installed. The lab network has no internet — that's why `tofu init` works from a local copy of the providers (you'll see this in Lab 1). Dojo Cloud is reached over the lab network only, and your credentials for it are already set in your shell (Lab 4).
