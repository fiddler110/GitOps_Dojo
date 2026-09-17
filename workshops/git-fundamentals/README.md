# Git Fundamentals — Session 1

A 60-minute lunch-and-learn: version control fundamentals + a hands-on lab,
for engineering and IT operations staff with mixed git experience.

## Two delivery modes

| Mode | Where | Status | Use when |
| ---- | ----- | ------ | -------- |
| **Local lab (Forgejo)** | this folder's `content/` + `docs/`, run via [`engine/`](../../engine/) | Primary, tested end-to-end | You control the host — runs entirely offline, self-hosted, zero external accounts needed |
| **Azure DevOps** | [`delivery-azure-devops/`](delivery-azure-devops/) | Doc-only, not wired to any automation | Your org standardizes on Azure Repos and attendees already have accounts there |

The two are independent — pick one per session. They share the same
teaching content (branching, PRs, the everyday workflow) but different
lab mechanics and facilitator setup.

## Running the local lab

```sh
cd ../../engine
cp .env.example .env    # first time only — account/secret settings
./run.sh git-fundamentals
```

`run.sh` picks this workshop's identity (content dir, Forgejo org/repo) from
[`workshop.env`](workshop.env) — see [`workshops/README.md`](../README.md)
for how workshop selection works, and how to run a different workshop
(e.g. `./run.sh dns-as-code`) instead.

Full facilitator setup, account provisioning, and troubleshooting:
[`engine/README.md`](../../engine/README.md). Student-facing walkthrough:
[`docs/student-workflow.md`](docs/student-workflow.md).

Workshop content you can edit per-session, with no script changes required:

- [`content/slides/presentation.md`](content/slides/presentation.md) — the deck
- [`content/lab/README.md`](content/lab/README.md) — instructions seeded into every student's `~/lab`
- [`content/sample-repo/`](content/sample-repo/) — seeded into Forgejo as `training/sample-training-repo` by the `bootstrap` service

## Running the Azure DevOps edition

See [`delivery-azure-devops/README.md`](delivery-azure-devops/README.md) for
the full checklist. That path predates the local-lab engine and needs a
manually created Azure Repos project — nothing in `engine/` applies to it.

## Session Roadmap

| # | Session | Format | Status |
| - | ------- | ------ | ------ |
| 1 | Git Fundamentals: What/Why/How + Hands-on Lab | 60 min | This workshop |
| 2 | Branching Workflows & Pull Requests in Practice | 45-60 min | Future |
| 3 | Team Git Conventions + DNS-as-Code Repo Walkthrough | 45-60 min | [`workshops/dns-as-code/`](../dns-as-code/) |
| 4 | Handling Conflicts, Rebasing, and "Oh No" Recovery | 45-60 min | Future |
| 5 | Automating Checks: Pre-commit Hooks & CI Pipelines | 45-60 min | Future |

## Delivery notes

- Keep the talk conceptual and light on typed commands — save typing for the lab.
- Provide a printed/shared cheat sheet ([Azure edition's copy](delivery-azure-devops/cheat-sheet.md) works for either mode).
- Record the session if possible.
