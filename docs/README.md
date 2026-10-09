# GitOps Dojo documentation

GitOps Dojo is a lunch-and-learn training platform. A facilitator runs one command, students open one URL in a
browser, and each gets a private VS Code, terminal, git server account, slides and lab guide, already signed in.
Everything the class needs runs inside one stack on one machine, with no internet needed once the images are built.

This folder is the complete tour: what the platform is, how it is built, how data moves through it, and how to
use it as a student, a facilitator or an author. The older per-component READMEs
([`README.md`](../README.md), [`engine/README.md`](../engine/README.md), [`workshops/README.md`](../workshops/README.md))
stay as the detailed references; these pages organise the whole picture and link into them for the fine print.

> **If the docs and the code disagree, the code wins.** The command is `./dojo` (the old `./run.sh` is a stub
> that forwards to it).

## Pick your path

| You are... | Read, in this order |
|---|---|
| **A student** | [Student guide](student-guide.md), then your workshop's lab guide (it opens from the landing page) |
| **A facilitator running a class** | [Concepts](concepts.md), [Facilitator guide](facilitator-guide.md), [CLI reference](cli-reference.md), [Operations and troubleshooting](operations.md), your workshop's own `FACILITATOR.md` |
| **Standing up the platform** (first install, a VM, a home lab) | [Configuration](configuration.md), [CLI reference](cli-reference.md), [Operations](operations.md) |
| **An author writing a workshop or module** | [Concepts](concepts.md), [Architecture](architecture.md), [Authoring guide](authoring.md), [Modules](modules.md), [Workshop catalog](workshops.md) |
| **A contributor changing the engine** | [Architecture](architecture.md), [Data flows](data-flows.md), [Security model](security.md), [Development guide](development.md) |
| **Reviewing the security posture** | [Security model](security.md), then [Architecture](architecture.md) |

## The pages

| Page | What it covers |
|---|---|
| [Concepts](concepts.md) | The ideas everything else rests on: workshop packs, modules, the engine, manifests, slots, gates, the lab lifecycle, plus a glossary |
| [Architecture](architecture.md) | Every service, every network, the build and start pipeline, the terminal image chain, state and volumes |
| [Data flows](data-flows.md) | How a request, a login, a git push, a CI job, a credential and an achievement event actually travel, step by step |
| [Security model](security.md) | Trust zones, identity headers, kernel-level separation, per-service tokens, what is deliberately accepted |
| [Configuration](configuration.md) | The three settings files, precedence, every variable group, profiles, deployment scenarios |
| [CLI reference](cli-reference.md) | Every `./dojo` command and flag, with examples and the files the CLI reads and writes |
| [Student guide](student-guide.md) | What a student sees and does: sign-in, the workspace, the lab loop, Sensei, achievements, getting unstuck |
| [Facilitator guide](facilitator-guide.md) | Before, during and after a class; the `/admin` workspace; releasing, resetting, content updates, bots |
| [Operations and troubleshooting](operations.md) | Sizing, capacity, health, logs, restarts, cleanup, and a symptom-to-fix table |
| [Workshop catalog](workshops.md) | The learning path, each workshop's labs, services and data flow, and the CTF series |
| [Modules](modules.md) | The reusable building blocks (runner pool, Dojo Cloud, OpenBao, DNS gate, Sensei, achievements, CTF range...) |
| [Authoring guide](authoring.md) | Creating a workshop pack or a module, the `extensions.json` manifest, lab-writing conventions, bots, tests |
| [Development guide](development.md) | Repo layout, running the test suites, CI, git workflow and the project rules |

## Existing documents these pages build on

| Document | Role |
|---|---|
| [`README.md`](../README.md) | Product overview, workshop table, per-workshop topology diagrams, security diagrams |
| [`engine/README.md`](../engine/README.md) | Engine reference: routing table, setup, deployment, operations, bots, troubleshooting |
| [`workshops/README.md`](../workshops/README.md) | Author's guide: pack anatomy, `extensions.json` reference, writing a module |
| `modules/<name>/README.md` | One reference per module |
| `workshops/<name>/README.md`, `FACILITATOR.md` | Per-workshop technical reference and run-of-show |
| [`ROADMAP.md`](../ROADMAP.md), [`RELEASES.md`](../RELEASES.md) | Open work, and what shipped |
| [`archive/`](archive/) | Frozen design plans and decision logs (modules, tofu-basics, vault, remediation, student reset). Read for the reasoning, never update |
| [`CTF-WORKSHOP-PLAN.md`](CTF-WORKSHOP-PLAN.md), [`CTF-SPIKES.md`](CTF-SPIKES.md), [`CLOUD-POLICY-AS-CODE-PLAN.md`](CLOUD-POLICY-AS-CODE-PLAN.md) | Live design plans for the CTF series and the policy workshop |

## Conventions used in these pages

- Commands use `./dojo` from the repo root. After `./dojo alias-setup` the same commands work as `dojo ...` anywhere.
- `studentNN` stands for a student account such as `student07`; `<workshop>` for a pack name such as `dns-as-code`.
- Service names (`gateway`, `allocator`, `web-terminal`, `git-server`) are the Compose service names, so they are
  what `./dojo logs <service>` and `./dojo restart <service>` take.
- Diagrams are Mermaid; GitHub and most Markdown viewers render them.
