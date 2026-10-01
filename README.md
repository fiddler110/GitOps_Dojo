# GitOps Dojo

**A self-contained, offline, hands-on learning environment for practical
infrastructure skills.**

GitOps Dojo runs short-lived workshops where students do the real work: they
push commits and open pull requests, watch CI change a live DNS server, get TLS
certificates from a working ACME authority, and deploy containers into a cloud
that the real `azurerm` provider talks to. Every exercise uses real tools
against real services. Each workshop's lab is built for one class and removed
completely at the end.

**Zero install for students.** A student opens one URL in any browser and gets
their own VS Code, terminal, git server, slides and lab guide, already signed
in. There is nothing to download, no accounts to create and no laptop setup to
debug before the class can start.

**Fully self-contained and offline.** Everything a class needs runs inside the
stack: the git server, CI runners, DNS servers, a certificate authority and a
practice cloud. Once the images are built, a session needs no internet and no
outside accounts. Every tool is baked in, pinned to a version and checked
against a sha256.

**Ephemeral by design.** `./run.sh <workshop>` starts a whole lab on a laptop or
a single VM, and `./run.sh stop` removes it without a trace. Each class starts
clean, and several workshops run on the same engine.

**Safe to break.** Student terminals have no internet and no Docker socket. The
DNS zones, certificates and cloud resources belong to the lab, so a mistake
is part of the lesson and never an incident.

```sh
./run.sh setup              # first time only: writes engine/.env
./run.sh doctor             # will a start work here? (exits 1 if not)
./run.sh list               # which workshops exist
./run.sh tofu-basics        # build and start one
./run.sh tofu-basics --test # the same, with simulated students
./run.sh status             # what is running, healthy, who is signed in
./run.sh restart            # stuck? recreate every container, keep student work
./run.sh stop               # tear down and wipe
```

## What's here

### The workshops

| # | Workshop | What students learn | Labs | Length |
| - | -------- | ------------------- | ---- | ------ |
| 0 | [**Dojo Introduction**](workshops/dojo-introduction/) | A show-and-tell of the whole platform for a facilitator, not a lab: every module runs at once (vault, DNS, certificates, Dojo Cloud, CI runners) with a platform tour, a workshop library and a tools tour. | none | ~30 min |
| 1 | [**Git Fundamentals**](workshops/git-fundamentals/) | The core git workflow: clone, branch, commit, push, pull request, then reviewing and undoing changes, stashing, reading history and resolving merge conflicts. | 5 | 60 min |
| 2 | [**DNS as Code**](workshops/dns-as-code/) | Managing DNS records in git with `dnscontrol`. A pull request runs a CI preview, and merging it applies the change to a live PowerDNS server. | 5 | 45-60 min |
| 3 | [**Certificate Autorenewal**](workshops/cert-autorenewal/) | Getting TLS certificates over ACME from a private CA with `certbot` and `acme.sh`, installing them on a real web server, automating renewal (certificates last 5-10 minutes, so students see renewals happen) and the dns-01 challenge. | 5 | ~75 min |
| 4 | [**OpenTofu Basics**](workshops/tofu-basics/) | The Terraform workflow (`init`, `plan`, `apply`, `destroy`) and how an IaC repo is laid out. Track A is an offline sandbox. Track B deploys real containers through the real `azurerm` provider into **Dojo Cloud**, an Azure-inspired practice cloud with a portal, policies, quotas and drift. `terraform` runs OpenTofu. | 11 | ~2¼ h |
| 5 | [**Vault Fundamentals**](workshops/vault-fundamentals/) | Using a vault well, on a real OpenBao: get secrets out of code, git, pipelines and servers, and swap long-lived secrets for identity and short-lived credentials. Labs cover leaking and scanning, `sops` and `pass`, per-student namespaces and policies, an app and OpenBao Agent, CI that logs in with its Forgejo identity on single-use runners, deployments with a delivered secret ID or workload identity, dynamic Postgres logins and an incident drill. | 14 | ~3½ h |

The numbers are a learning path: teach them in order. `0` showcases the platform and is not a course; `1` to `5`
build on each other (DNS as Code reuses the git flow, Certificate Autorenewal's capstone drives the DNS API from
workshop 2, OpenTofu Basics extends the plan-before-apply and drift ideas, and Vault Fundamentals, which lists Git
Fundamentals as a prerequisite, comes last as the longest).

Each workshop pack has its own slide deck, lab guides, cheat sheet and a seed
repository. The lab guides are copied into every student's `~/lab` and shown
in the browser.

### The platform

- **One URL per class.** A Caddy gateway is the only exposed service. It assigns
  each browser a student account and routes it to that student's VS Code
  (code-server), terminal (ttyd + tmux), the Forgejo git server and the Marp
  slides, all signed in already.
- **A facilitator workspace at `/admin`.** A live roster with a read-only view
  of every student's terminal, a Release button to free a stuck account, a
  service status strip, and the facilitator's own VS Code, Terminal, Forgejo,
  Slides tabs, plus the tabs a workshop's modules add: Dojo Cloud and the **Class
  progress** board (tofu-basics), Vault, Audit, Runners and Apps
  (vault-fundamentals), DNS Admin (dns-as-code, cert-autorenewal).
- **Isolated labs.** Student terminals have no internet and no Docker socket.
  Every tool is baked into the workshop's image, pinned to a version and checked
  against a sha256. Extra services sit on internal-only networks, and anything a
  student can reach checks a gateway token before trusting who the caller is.
  See [Security boundaries](#security-boundaries).
- **Workshops are plug-ins.** A workshop is a folder under `workshops/`: a
  `workshop.env`, its content and, only if it needs them, reusable modules
  (`MODULES="runner-pool dns-gate"`), a Compose overlay, extra terminal tools and an
  `extensions.json` that declares its landing cards, `/admin` tabs and routes.
  The engine is never edited to add a workshop. See [`workshops/README.md`](workshops/README.md).
- **Demo bots.** `--test [N]` adds up to 35 simulated students (expert,
  intermediate and novice personas) who work through the labs for real, pushing
  branches and opening pull requests. Use them to rehearse solo, demo the
  admin dashboard or load-test a machine before a class.
- **A live start-up view.** In a terminal, `./run.sh` shows one status table
  that updates in place while the stack starts, and `./run.sh stop` shows one
  while it comes down (plain lines when piped or with `NO_COLOR`).
- **Runs on one machine.** A laptop for rehearsal or a single cloud VM for a
  real class, with Docker or Podman. `./run.sh capacity --students 30` sizes the
  per-student memory and process limits for that host. Nothing persists once the
  stack is stopped.

### Beyond the live lab

- **Azure DevOps edition** of Git Fundamentals
  ([`workshops/git-fundamentals/delivery-azure-devops/`](workshops/git-fundamentals/delivery-azure-devops/)):
  the same session delivered against Azure Repos, with a facilitator guide,
  checklists and a feedback survey.
- **Facilitator guides.** [`engine/README.md`](engine/README.md) covers setup,
  deployment, the admin workspace, mid-session content updates, cleanup and
  troubleshooting. OpenTofu Basics also has a run-of-show in
  [`FACILITATOR.md`](workshops/tofu-basics/FACILITATOR.md), and the roadmap and
  release history are in [`ROADMAP.md`](ROADMAP.md) and [`RELEASES.md`](RELEASES.md).
- **Tests.** OpenTofu Basics ships an end-to-end suite and a load test against
  the live stack ([`workshops/tofu-basics/tests/`](workshops/tofu-basics/tests/)),
  and Dojo Cloud's control plane has its own unit tests. Vault Fundamentals has
  one script per lab, a runner-pool and audit check, browser checks and a
  demo-bot load run ([`workshops/vault-fundamentals/tests/`](workshops/vault-fundamentals/tests/)).

## What you need on the host

The facilitator's machine needs a container engine, git and openssl. Students need only a browser.
**Podman** (with `podman-compose`) is the recommended engine; **Docker** with the Compose plugin also works.
`run.sh` is bash and the containers are Linux, so:

| Host | What to use |
|---|---|
| Ubuntu / Debian / Fedora | `./setup.sh` |
| Windows | `.\setup.ps1` in PowerShell: sets up WSL2 + Ubuntu, clones the repo inside it, then runs `setup.sh` there |
| macOS | `./setup.sh` (Homebrew; podman needs `podman machine`, or use Docker Desktop). Not yet tested on a Mac. |

`./setup.sh` detects the OS, asks you to confirm, shows what is missing and asks before installing anything
(`--check` only reports). `./run.sh` uses podman whenever `podman` and `podman-compose` are installed (rootless, no root daemon, so a
container escape lands on an unprivileged user) and falls back to Docker otherwise.

## Who it's for

Engineering and IT operations teams: people who use git every day, and people
who have never used version control. It assumes comfort with a terminal and no
git knowledge. The workshops build on each other: Git Fundamentals gives
everyone the clone, branch, pull request routine, and the later workshops apply
that routine to real operational work, where a change goes through review and
automation instead of being made by hand.

## Status and roadmap

| Workshop | Status |
| -------- | ------ |
| Git Fundamentals | Ready |
| DNS as Code | Ready |
| Certificate Autorenewal | Ready |
| OpenTofu Basics | Built and tested live. A human dry-run and a final browser pass remain (see [`ROADMAP.md`](ROADMAP.md)). |
| Vault Fundamentals (OpenBao) | Ready. Merged to `main` (PR #3): labs 0-13, the talk and the facilitator's Vault, Audit, Runners and Apps tabs. Live-tested with demo bots (10 students, about 2 GiB); a person walking labs 7-9 in the browser remains ([`ROADMAP.md`](ROADMAP.md)). |
| Dojo Introduction | Built and tested locally; a showcase, not a lab. |
| Threat-model remediation | 15 of 19 findings fixed, 2 partial, 2 accepted, on `feat/remediation` and not yet merged to `main`; see [`RELEASES.md`](RELEASES.md). |
| Git follow-ups: branching workflows and pull requests; conflicts, rebasing and recovery; pre-commit hooks and CI | Ideas, not started |

## Repository layout

```text
├── run.sh                    # Forwards to engine/run.sh
├── engine/                   # The shared runtime: gateway, allocator, web-terminal, Forgejo, slides
│   ├── README.md             # Setup, routing, auth, facilitator operations, troubleshooting
│   └── scripts/              # env setup, capacity calculator, teardown, shell completion
├── modules/                  # Reusable services + tools a workshop lists in MODULES (./run.sh modules)
│   ├── dns-gate/             # dns-api: PowerDNS API gate, per-account keys, CI by ID token (dns-as-code, cert-autorenewal)
│   ├── dns-ui/               # DNS Zones page and the facilitator's DNS Admin (dns-as-code, cert-autorenewal)
│   ├── dojo-cloud/           # Dojo Cloud: cloud-api, cloud-host, /cloud route, terminal broker (tofu-basics)
│   ├── forgejo-runner/       # One long-lived Actions runner for one repo (no workshop uses it now)
│   ├── openbao/              # OpenBao server, setup, SSO through Forgejo, terminal identity broker (vault-fundamentals)
│   └── runner-pool/          # Single-use Actions runners, autoscaled, Runners panel in /admin (vault-fundamentals, dns-as-code)
├── workshops/
│   ├── README.md             # How workshops are selected and how to add one
│   ├── assets/               # Shared slide theme and the in-browser lab reader
│   ├── git-fundamentals/     # Content only; also the Azure DevOps delivery mode
│   ├── dns-as-code/          # + PowerDNS; runner-pool, dns-ui and dns-gate modules
│   ├── cert-autorenewal/     # + step-ca, PowerDNS, shared nginx demo app
│   ├── dojo-introduction/    # Showcase of the whole platform; all modules at once
│   ├── tofu-basics/          # + tofu toolchain; uses the dojo-cloud module; FACILITATOR.md, tests/
│   └── vault-fundamentals/   # openbao + runner-pool modules, app-host and app-db; labs 0-13, tests/
├── ROADMAP.md                # All open work: the single list of tasks
├── RELEASES.md               # What shipped, newest first
├── docs/archive/             # Frozen design plans and decision logs (modules, tofu-basics, vault, remediation, reset)
├── threat-model-20260926-154208/  # Threat model report (fix history is in RELEASES.md)
└── assets/branding/          # Shared branding
```

```mermaid
graph LR
    Student(["Student's browser"]) -->|"one URL"| Gateway["engine/<br/>gateway + git server +<br/>terminal + slides"]
    Facilitator(["Facilitator"]) -->|"./run.sh WORKSHOP"| Gateway
    Gateway -->|"mounts WORKSHOP_CONTENT_DIR"| Content["workshops/NAME/content/<br/>slides, lab, sample-repo"]
    Gateway -.->|"optional overlay"| Extra["workshops/NAME/compose/<br/>extra services, custom terminal image"]
    Gateway -.->|"MODULES=..."| Mods["modules/NAME/<br/>shared services, tools, routes"]
    Facilitator -->|"edits, no engine changes"| Content

    classDef addon fill:#10b9812e,stroke:#10b981,stroke-width:2px
    classDef content fill:#ec48992e,stroke:#ec4899,stroke-width:2px
    classDef gw fill:#8b5cf62e,stroke:#8b5cf6,stroke-width:2px
    classDef person fill:#f59e0b2e,stroke:#f59e0b,stroke-width:2px
    class Extra,Mods addon
    class Content content
    class Gateway gw
    class Student,Facilitator person
```

## Where to go next

- **Run a class:** [`engine/README.md`](engine/README.md), then the workshop's own README.
- **Add a workshop:** [`workshops/README.md`](workshops/README.md).
- **Understand how it fits together:** keep reading.

## How the platform is put together

Every workshop runs on the same engine, so the base topology is identical
each time. A workshop only ever *adds* to it. The sections below first show
the shared base, then what each workshop adds to it — its extra services,
who can reach whom, and how data moves through its labs.

### The shared engine (every workshop)

Only `gateway` has a published port. Everything else sits on internal-only
networks, so the gateway is the sole entry point and the only thing that
needs a hole in a firewall.

```mermaid
graph TB
    Browser(["Browser<br/>student or facilitator"])

    subgraph pub["public network"]
        GW["gateway (Caddy)<br/>:80 / :443"]
    end

    subgraph lab["workshop_lab - internal"]
        AL["allocator<br/>assigns studentNN, facilitator dashboard"]
        WT["web-terminal<br/>per-student code-server + ttyd"]
        GS["git-server (Forgejo)<br/>:3000"]
    end

    subgraph web["web_lab - internal"]
        PR["presentation (Marp)<br/>:8080"]
    end

    subgraph boot["bootstrap_net - internal"]
        BS["bootstrap<br/>one-shot"]
    end

    Browser -->|"PUBLIC_BASE_URL"| GW
    GW -->|"/ and /admin"| AL
    GW -->|"/ide and /term, after allocator forward_auth"| WT
    GW -->|"/git"| GS
    GW -->|"/slides"| PR
    AL -.->|"start / stop / status"| WT
    WT -->|"git clone / push, direct"| GS
    BS -->|"creates admin, org, repo, student accounts"| GS

    classDef core fill:#3b82f62e,stroke:#3b82f6,stroke-width:2px
    classDef gw fill:#8b5cf62e,stroke:#8b5cf6,stroke-width:2px
    classDef person fill:#f59e0b2e,stroke:#f59e0b,stroke-width:2px
    class AL,WT,GS,PR,BS core
    class GW gw
    class Browser person
    style pub fill:#8b5cf60f,stroke:#8b5cf6,stroke-width:1px,stroke-dasharray:5 4
    style lab fill:#3b82f60f,stroke:#3b82f6,stroke-width:1px,stroke-dasharray:5 4
    style web fill:#3b82f60f,stroke:#3b82f6,stroke-width:1px,stroke-dasharray:5 4
    style boot fill:#64748b0f,stroke:#64748b,stroke-width:1px,stroke-dasharray:5 4
```

`git-server` is attached to both `workshop_lab` and `bootstrap_net`;
`bootstrap` lives on `bootstrap_net` only, so it can reach Forgejo and
nothing else. Full routing, auth and request flow:
[`engine/README.md`](engine/README.md#architecture).

**What a student's terminal can reach.** It sits only on `workshop_lab` —
no internet, no `docker.sock`, and every student account shares one network
namespace, so a source IP never identifies a student. It reaches
`git-server:3000` directly and can't reach `presentation` (slides are
browser-only). Any tool a workshop needs is baked into that workshop's
terminal image, pinned and checksum-verified.

### How workshop content flows into the engine (every workshop)

This is the one dataflow every workshop shares. A workshop's `content/`
folder is bind-mounted read-only into three places; nothing is copied into
an image.

```mermaid
graph LR
    subgraph pack["workshops/NAME/content"]
        SL["slides/"]
        LB["lab/"]
        SR["sample-repo/"]
    end

    SL -->|"ro mount"| PR["presentation"]
    PR -->|"/slides"| Browser(["Browser"])
    LB -->|"ro mount at /opt/lab,<br/>copied to ~/lab on first login"| WT["web-terminal<br/>student ~/lab"]
    SR -->|"ro mount at /seed"| BS["bootstrap"]
    BS -->|"git push, only if the repo is empty"| GS["Forgejo repo<br/>ORG/REPO"]
    GS -->|"git clone"| WT
    WT -->|"git push, then pull request"| GS

    classDef content fill:#ec48992e,stroke:#ec4899,stroke-width:2px
    classDef core fill:#3b82f62e,stroke:#3b82f6,stroke-width:2px
    classDef person fill:#f59e0b2e,stroke:#f59e0b,stroke-width:2px
    class SL,LB,SR content
    class PR,WT,BS,GS core
    class Browser person
    style pack fill:#ec48990f,stroke:#ec4899,stroke-width:1px,stroke-dasharray:5 4
```

`lab/` files a student has already edited are never overwritten by an
update. `FORGEJO_ORG`/`FORGEJO_REPO` come from the workshop's
`workshop.env`.

### Summary: what each workshop adds

| Workshop | Modules | Extra services | Extra networks | Terminal image adds | Data leaves the terminal to |
| -------- | ------- | -------------- | -------------- | ------------------- | --------------------------- |
| `git-fundamentals` | — | none | none | nothing (base image) | Forgejo only |
| `dns-as-code` | `runner-pool`, `dns-ui`, `dns-gate` | `dns-server`, `dns-gates`; `runner-pool`, `runner-pool-shim`, `runner-controller`, `zone-viewer`, `dns-admin`, `dns-api` (modules) | `runner_net` (module) | `dnscontrol`, `dig`, `python3`; own DNS key (module) | Forgejo, `dns-api` |
| `cert-autorenewal` | `dns-ui`, `dns-gate` | `dns-server`, `dns-seed`, `step-ca`, `demo-app`; `zone-viewer`, `dns-admin`, `dns-api` (modules) | static subnet on `workshop_lab` | `step`, `certbot`, `acme.sh`, `openssl`, `dig`, `jq`; own DNS key (module) | step-ca, `dns-api`, shared webroot volume |
| `tofu-basics` | `dojo-cloud` | `cloud-api`, `cloud-host` (module) | `cloud_net` (module) | `tofu` (also `terraform`), offline provider mirror; credential broker (module) | `cloud-api` (Track B) |
| `vault-fundamentals` | `openbao`, `runner-pool` | `openbao`, `openbao-setup`, `openbao-sso-shim`, `openbao-audit`; `runner-pool`, `runner-pool-shim`, `runner-controller` (modules); `app-host`, `app-db` | `runner_net` (module; `openbao` and `app-host` join it) | `bao`, `bao-audit`, identity broker (module); `sops`, `gitleaks`, `pass`, `hvac`, `pg8000`, `psql`, `jq` | OpenBao, Forgejo, My App |
| `dojo-introduction` | `openbao`, `runner-pool`, `dojo-cloud`, `dns-ui`, `dns-gate` | Every module's services, plus PowerDNS, `step-ca` and the demo site reused from cert-autorenewal | `runner_net`, `cloud_net` (modules) | One image with `bao`, `sops`, `gitleaks`, `pass`, `dnscontrol`, `dig`, `step`, `certbot`, `acme.sh`, `tofu` | Everything above; nothing to complete |

Everything below is layered on the shared engine above — any service or
network not named there is unchanged.

---

### `git-fundamentals` — content only

**Infrastructure and connectivity:** the shared engine, exactly as-is. No
overlay, no extra services.

**Dataflow.** The labs are pure git against Forgejo. Clone, push and PR
review all talk to `git-server`; the browser only ever sees Forgejo through
the gateway.

```mermaid
sequenceDiagram
    actor S as Student
    box rgba(59,130,246,0.1) Engine
    participant WT as web-terminal (~/lab)
    participant GS as git-server (Forgejo)
    participant GW as gateway
    end
    actor F as Facilitator

    rect rgba(59,130,246,0.16)
    Note over S,GS: Work in the terminal
    S->>WT: git clone http://git-server:3000/training/sample-training-repo
    WT->>GS: clone, direct over workshop_lab
    S->>WT: branch, edit, commit
    WT->>GS: git push (studentNN's own token, ~/.git-credentials)
    end

    rect rgba(139,92,246,0.16)
    Note over S,F: Review in the browser
    S->>GW: Open Forgejo (/forgejo-login, then /git/...)
    GW->>GS: proxy, already signed in as studentNN
    S->>GS: open a pull request
    F->>GS: review and merge (facilitator's Forgejo tab under /admin)
    end
```

Git traffic never goes through the gateway — pushes and clones go straight
from the terminal to `git-server:3000`, and only the browser UI is proxied.

---

### `dns-as-code` — Forgejo Actions runner + PowerDNS

**Infrastructure and connectivity.** Adds a PowerDNS authoritative server,
the `dns-gate` module's `dns-api` in front of its API, and single-use CI
runners from the `runner-pool` module. Jobs run student-authored steps as
processes in the pool (no `docker.sock`), each on a fresh runner that is
deleted afterwards; the pool lives on its own `runner_net` and reaches only
`git-server`, `dns-api` and `dns-server` — never `allocator` or
`web-terminal`. PowerDNS's own API key is derived in `workshop.env` and
reaches only `dns-api` and the `dns-ui` module.

```mermaid
graph TB
    Browser(["Browser"]) --> GW["gateway"]
    GW -->|"/git"| GS

    subgraph lab["workshop_lab - internal"]
        WT["web-terminal<br/>dnscontrol, dig<br/>own key in $DNS_API_KEY"]
        GS["git-server (Forgejo)<br/>Actions enabled<br/>also on runner_net"]
        API["dns-api (dns-gate)<br/>checks the key or ID token<br/>also on runner_net"]
        DNS["dns-server (PowerDNS)<br/>:53 DNS, :8081 API<br/>also on runner_net"]
    end

    subgraph rn["runner_net - internal"]
        RP["runner-pool<br/>single-use runners, host label"]
        SH["runner-pool-shim<br/>public URL, ID-token path"]
    end

    WT -->|"git clone / push"| GS
    WT -->|"dnscontrol preview / push, own zone only"| API
    WT -->|"dig @dns-server, :53"| DNS
    API -->|"PowerDNS key, :8081"| DNS
    RP -->|"poll for jobs, clone, post status"| GS
    RP -->|"ID token request"| SH
    SH --> GS
    RP -->|"dnscontrol preview (read key) / push (ID token)"| API

    classDef addon fill:#10b9812e,stroke:#10b981,stroke-width:2px
    classDef core fill:#3b82f62e,stroke:#3b82f6,stroke-width:2px
    classDef gw fill:#8b5cf62e,stroke:#8b5cf6,stroke-width:2px
    classDef person fill:#f59e0b2e,stroke:#f59e0b,stroke-width:2px
    classDef priv fill:#ef44442e,stroke:#ef4444,stroke-width:2px
    class DNS,API,SH addon
    class WT,GS core
    class GW gw
    class Browser person
    class RP priv
    style lab fill:#3b82f60f,stroke:#3b82f6,stroke-width:1px,stroke-dasharray:5 4
    style rn fill:#ef44440f,stroke:#ef4444,stroke-width:1px,stroke-dasharray:5 4
```

**Dataflow.** One change travels the whole loop: local preview, PR, CI
preview, merge, CI apply, verify. The record only goes live when CI pushes
it after the merge — not when the student pushes their branch. `dns-api`
lets the apply job change `dojo.test` only because Forgejo signed its ID
token for a push to `main` of the class repo; a PR's job, a feature branch
or a fork gets `403` whatever its workflow says.

```mermaid
sequenceDiagram
    actor S as Student (terminal)
    box rgba(59,130,246,0.1) Engine
    participant GS as git-server (Forgejo)
    end
    box rgba(16,185,129,0.1) dns-as-code adds
    participant RN as runner-pool
    participant API as dns-api
    participant DNS as dns-server (PowerDNS)
    end

    rect rgba(59,130,246,0.16)
    Note over S,DNS: Pull request - preview only
    S->>API: dnscontrol preview (own key, reads dojo.test)
    S->>GS: git push branch, open pull request
    GS-->>RN: pull_request event, a fresh runner takes the job
    RN->>GS: clone main, merge the PR head
    RN->>API: dnscontrol preview (read key)
    RN->>GS: comment the diff on the PR, set "DNS Preview" status
    end

    rect rgba(16,185,129,0.16)
    Note over S,DNS: Merge - CI applies the change
    S->>GS: merge the PR to main (review + passing preview)
    GS-->>RN: push to main, a fresh runner takes the job
    RN->>GS: clone main, ask for an ID token (audience dns-api)
    RN->>API: dnscontrol push with the token
    API->>DNS: checked: class repo, main, push - forwarded
    RN->>GS: set "DNS Apply" status
    S->>DNS: dig @dns-server name A +short (:53), verify
    end
```

Zone data lives only in the PowerDNS container's own filesystem, so it
resets on every teardown. `creds.json` in the seeded repo names no secret:
`"apiKey": "$DNS_API_KEY"`, each account's own key in its terminal and the
job's ID token in CI.

---

### `cert-autorenewal` — ACME CA + DNS + shared demo app

**Infrastructure and connectivity.** Adds a private ACME certificate
authority, a PowerDNS server that resolves every student's hostname, and one
shared nginx that serves every student's site. All of it lives on
`workshop_lab`, whose subnet is pinned (`172.30.0.0/24`) so `dns-server`
(`.10`) and `demo-app` (`.20`) have stable addresses that `step-ca` and the
seeded DNS records can point at.

Students never touch `demo-app` directly. Isolation is per-student
ownership of a subdirectory on a shared volume, not per-container. A
watcher inside `demo-app` reloads nginx when files change, so no
`docker.sock` or cross-container exec is needed.

```mermaid
graph TB
    Browser(["Browser"]) --> GW["gateway"]
    GW -->|"/demo, after allocator forward_auth, HTTP only"| APP

    subgraph lab["workshop_lab - internal, 172.30.0.0/24"]
        WT["web-terminal<br/>step, certbot, acme.sh, cron"]
        CA["step-ca<br/>ACME :9000, 5-10 min certs"]
        APP["demo-app (nginx)<br/>172.30.0.20 :80 / :443<br/>one vhost per student"]
        DNS["dns-server (PowerDNS)<br/>172.30.0.10 :53 / :8081"]
        SEED["dns-seed<br/>one-shot"]
    end

    WEB[("cert_lab_webroot<br/>/srv/webroot/studentNN")]
    ROOT[("step_ca_root_pub<br/>root_ca.crt only")]

    SEED -->|"creates the zone + one A record per student, pointing at demo-app"| DNS
    WT -->|"ACME over HTTPS :9000"| CA
    CA -->|"resolves studentNN.certs.dojo.test"| DNS
    CA -->|"http-01: GET /.well-known/acme-challenge/..."| APP
    WT -->|"dig :53, dns-01 TXT via :8081 API"| DNS
    WT -->|"curl --resolve, HTTPS"| APP
    WT -.->|"rw, own subdirectory"| WEB
    APP -.->|"serves and watches"| WEB
    CA -.->|"publishes"| ROOT
    ROOT -.->|"ro at /opt/step-ca-root"| WT

    classDef addon fill:#10b9812e,stroke:#10b981,stroke-width:2px
    classDef core fill:#3b82f62e,stroke:#3b82f6,stroke-width:2px
    classDef gw fill:#8b5cf62e,stroke:#8b5cf6,stroke-width:2px
    classDef person fill:#f59e0b2e,stroke:#f59e0b,stroke-width:2px
    classDef store fill:#06b6d42e,stroke:#06b6d4,stroke-width:2px
    class CA,APP,DNS,SEED addon
    class WT core
    class GW gw
    class Browser person
    class WEB,ROOT store
    style lab fill:#3b82f60f,stroke:#3b82f6,stroke-width:1px,stroke-dasharray:5 4
```

The CA's private keys stay in `step-ca`'s own volume; only the public root
certificate is shared into the terminal. This workshop's `sample-repo` is
mounted straight into `~/lab/sample-repo` — there is no Forgejo clone step
in its labs.

**Dataflow.** Two proofs of control (http-01 in Labs 2–4, dns-01 in Lab 5)
and one renewal loop.

```mermaid
sequenceDiagram
    actor S as Student (terminal)
    box rgba(16,185,129,0.1) cert-autorenewal adds
    participant CA as step-ca
    participant V as /srv/webroot (shared volume)
    participant APP as demo-app (nginx)
    participant DNS as dns-server (PowerDNS)
    end

    rect rgba(59,130,246,0.16)
    Note over S,CA: Lab 1 - trust the CA
    S->>CA: step ca bootstrap, using the root cert from /opt/step-ca-root
    end

    rect rgba(16,185,129,0.16)
    Note over S,APP: Lab 2 - issue with http-01
    S->>V: write vhost, html, certs dirs under studentNN/
    V-->>APP: file change, watcher runs nginx -t and reload
    S->>CA: certbot certonly --webroot (ACME order, HTTPS :9000)
    S->>V: certbot writes the challenge token into html/.well-known/
    CA->>DNS: resolve studentNN.certs.dojo.test, gets 172.30.0.20
    CA->>APP: GET http://studentNN.certs.dojo.test/.well-known/acme-challenge/token
    APP-->>CA: token, served from the shared volume
    CA-->>S: signed certificate (5-10 minute lifetime)
    S->>V: copy fullchain and privkey to certs/, add a :443 server block
    V-->>APP: reload
    S->>APP: curl --resolve ... https, verified against the root cert
    end

    rect rgba(139,92,246,0.16)
    Note over S,APP: Lab 4 - automated renewal
    loop cron runs the renewal script
        S->>CA: renew (ACME)
        S->>V: install the new cert
        V-->>APP: reload
    end
    end

    rect rgba(6,182,212,0.16)
    Note over S,DNS: Lab 5 - dns-01 instead
    S->>CA: certbot --manual --preferred-challenges dns-01
    S->>DNS: PUT _acme-challenge TXT record (:8081 API)
    CA->>DNS: look up the TXT record
    CA-->>S: signed certificate
    end
```

The `/demo` link on the workshop homepage is HTTP-only and never touches a
student's certificate, so `curl --cacert` from the terminal is the real
check that a cert is valid.

---

### `tofu-basics` — offline sandbox + "Dojo Cloud"

Two tracks. **Track A** (sandbox) needs no infrastructure beyond the swapped
terminal image. **Track B** (Dojo Cloud) adds an Azure-inspired control
plane that the real `azurerm` provider talks to, so students run
`init`/`plan`/`apply`/`destroy` against something that behaves like a cloud.

**Infrastructure and connectivity.** The privileged `cloud-host` (a
Docker-in-Docker daemon that actually runs student containers) is
acceptable only because it is boxed in: it sits on an internal network with
no route to the internet or to any student, publishes nothing, and has no
listener except a unix socket shared with `cloud-api`. `cloud-api` is the
only thing that ever talks to it, using fixed templates — students never
speak Docker.

```mermaid
graph TB
    Browser(["Browser"]) --> GW["gateway"]
    GW -->|"/cloud, after allocator forward_auth"| API

    subgraph lab["workshop_lab - internal"]
        WT["web-terminal<br/>tofu / terraform + provider mirror<br/>dojo-broker (root, unix socket)"]
        API["cloud-api<br/>:443 ARM, login, metadata (private CA)<br/>:8080 portal and site ingress<br/>alias: management.dojo.cloud, login.dojo.cloud"]
        GS["git-server (Forgejo)"]
    end

    subgraph cn["cloud_net - internal, no route out"]
        HOST["cloud-host<br/>privileged docker-in-docker<br/>runs student containers"]
    end

    RUN[("cloud_run<br/>docker.sock")]
    PKI[("cloud_pki<br/>CA certificate")]
    SEC[("cloud_secrets<br/>signing key, root-only")]
    DATA[("cloud_data<br/>control-plane state")]

    WT -->|"HTTPS ARM calls from azurerm"| API
    WT -->|"git clone / push"| GS
    API -->|"fixed-template docker run"| RUN
    RUN --> HOST
    API -->|"writes the CA"| PKI
    PKI -.->|"ro"| WT
    API -->|"writes the signing key"| SEC
    SEC -.->|"ro, only the root broker can read it"| WT
    API -.-> DATA

    classDef addon fill:#10b9812e,stroke:#10b981,stroke-width:2px
    classDef core fill:#3b82f62e,stroke:#3b82f6,stroke-width:2px
    classDef gw fill:#8b5cf62e,stroke:#8b5cf6,stroke-width:2px
    classDef person fill:#f59e0b2e,stroke:#f59e0b,stroke-width:2px
    classDef priv fill:#ef44442e,stroke:#ef4444,stroke-width:2px
    classDef store fill:#06b6d42e,stroke:#06b6d4,stroke-width:2px
    class API addon
    class WT,GS core
    class GW gw
    class Browser person
    class HOST priv
    class RUN,PKI,SEC,DATA store
    style lab fill:#3b82f60f,stroke:#3b82f6,stroke-width:1px,stroke-dasharray:5 4
    style cn fill:#ef44440f,stroke:#ef4444,stroke-width:1px,stroke-dasharray:5 4
```

The gateway routes `/cloud` to `cloud-api`'s `:8080` listener: the Dojo
Portal at `/cloud/` and each deployed site at `/cloud/site/<label>/`. The
route, the landing-page card and the facilitator's matching **Dojo Cloud**
tab in `/admin` come from the `dojo-cloud` module's `extensions.json`, so
they exist only in a workshop that lists the module. `cloud_data` mirrors control-plane state to disk so a
`cloud-api` restart doesn't forget what was deployed; `./run.sh stop` still
wipes it.

**Dataflow — Track A (sandbox).** Fully local; nothing leaves the
terminal container.

```mermaid
graph LR
    M[("provider mirror<br/>/opt/tofu-providers<br/>baked into the image")] -->|"tofu init, offline"| WD["~/lab/sandbox<br/>.terraform/ and lock file"]
    WD -->|"plan / apply"| ST["terraform.tfstate<br/>plus random_pet, local_file outputs"]
    ST -->|"tofu destroy"| WD
    WD -.->|"git commit .tf files, never state"| GS["Forgejo"]

    classDef content fill:#ec48992e,stroke:#ec4899,stroke-width:2px
    classDef core fill:#3b82f62e,stroke:#3b82f6,stroke-width:2px
    classDef store fill:#06b6d42e,stroke:#06b6d4,stroke-width:2px
    class WD,ST content
    class GS core
    class M store
```

**Dataflow — Track B (Dojo Cloud).** The student never holds a long-lived
secret: the broker derives that student's credentials from the caller's
real uid, and `cloud-api` authorises every call against the token's own
subscription.

```mermaid
sequenceDiagram
    box rgba(59,130,246,0.1) web-terminal
    actor S as Student shell
    participant BR as dojo-broker (root)
    end
    box rgba(16,185,129,0.1) Dojo Cloud
    participant API as cloud-api
    participant HOST as cloud-host
    end

    rect rgba(59,130,246,0.16)
    Note over S,BR: Credentials
    S->>BR: new shell asks for credentials (unix socket)
    BR-->>S: ARM_* values for that uid only (uid comes from SO_PEERCRED)
    S->>S: tofu init, offline, from the provider mirror
    end

    rect rgba(16,185,129,0.16)
    Note over S,HOST: tofu apply
    S->>API: fetch metadata, get a token (HTTPS, private CA)
    S->>API: PUT resource group, PUT container group
    API->>API: authenticate token, check subscription, run policy
    API->>HOST: fixed-template docker run over the shared socket
    HOST-->>API: container running
    API-->>S: Succeeded, the provider polls the operation
    S->>S: output "url" prints /cloud/site/label/
    end

    rect rgba(239,68,68,0.16)
    Note over S,HOST: tofu destroy
    S->>API: DELETE, container removed
    API->>HOST: remove the container
    end
```

Policy rejections come back as ARM-shaped errors (a required tag missing,
a disallowed region, an oversized container, over quota) so the labs can
teach reading real-looking failures.

---

### `vault-fundamentals` — a real OpenBao, CI runners and a deploy target

One OpenBao serves the whole class, and each student works in a namespace of
their own under one shared, templated policy. The workshop adds three things
on top of the engine: the `openbao` module (the vault, its start-up setup,
single sign-on through Forgejo and an audit reader), the `runner-pool` module
(single-use CI runners, autoscaled) and, in the workshop's own overlay,
`app-host` (a deploy target with one slot per student) and `app-db`
(Postgres for the dynamic-credentials lab).

**Infrastructure and connectivity.** OpenBao listens on plain HTTP on
`workshop_lab` only. The gateway fronts its UI at `/ui` and `/v1` for browsers.
`openbao-setup` runs on every start: it unseals the vault, uses a temporary
root token to provision namespaces, policies, auth methods and one identity per
account, then revokes it, so no live root or provisioner token stays on disk.
Students log in from the terminal with no password: a broker on a unix socket
signs a short-lived JWT for the account on the other end (`SO_PEERCRED`) and
OpenBao trades it for a token. In the browser, the vault signs in through
Forgejo (OIDC).

```mermaid
graph TB
    Browser(["Browser"]) --> GW["gateway"]
    GW -->|"/ui, /v1"| OB
    GW -->|"/admin: Vault, Audit, Runners, Apps"| Panels["openbao-audit, runner-controller,<br/>app-host"]

    subgraph lab["workshop_lab - internal"]
        WT["web-terminal<br/>bao, sops, gitleaks, pass, psql<br/>identity broker (root, unix socket)"]
        OB["openbao<br/>namespace per student,<br/>one templated policy"]
        SETUP["openbao-setup<br/>every start: unseal, provision,<br/>revoke temporary root"]
        AUD["openbao-audit<br/>reads the audit log"]
        GS["git-server (Forgejo)<br/>OIDC provider, Actions on"]
        CTL["runner-controller<br/>autoscales the pool"]
        AH["app-host<br/>one slot per student, own user,<br/>egress allowlist"]
        DB[("app-db<br/>Postgres")]
    end

    subgraph rn["runner_net - internal"]
        POOL["runner-pool<br/>single-use runners,<br/>one job each"]
    end

    WT -->|"JWT from broker, then bao"| OB
    WT -->|"git push, fork, PR"| GS
    SETUP --> OB
    OB -->|"audit file"| AUD
    OB -.->|"OIDC login"| GS
    GS -->|"job"| POOL
    CTL -->|"start and delete runners"| POOL
    POOL -->|"Actions ID token to OpenBao, deploy"| OB
    POOL -->|"deploy"| AH
    AH -->|"workload identity"| OB
    AH -->|"dynamic logins"| DB

    classDef core fill:#3b82f62e,stroke:#3b82f6,stroke-width:2px
    classDef addon fill:#10b9812e,stroke:#10b981,stroke-width:2px
    classDef gw fill:#8b5cf62e,stroke:#8b5cf6,stroke-width:2px
    classDef person fill:#f59e0b2e,stroke:#f59e0b,stroke-width:2px
    class WT,GS core
    class OB,SETUP,AUD,CTL,POOL,AH,DB,Panels addon
    class GW gw
    class Browser person
```

**The labs.** 0 sign in and take the tour, 1 leak a secret, 2 keep it
encrypted on your own machine (`sops`, `pass`), 3 use the shared vault, 4 be
the admin of your namespace, 5 an app reads a secret, 6 OpenBao Agent, 7
encrypted config in the repo, 8 Forgejo Actions secrets, 9 CI logs in to
OpenBao with its Actions ID token, 10 deploy with a delivered secret ID, 11
deploy with workload identity, 12 dynamic database credentials (optional), 13
an incident drill where a token leaks.

**Runners.** Each job runs on a runner that takes one job and is deleted with
everything it left behind, so no job finds another's files. The controller
keeps a warm idle minimum and scales up to a cap; the facilitator's **Runners**
panel shows each runner and has Auto / Manual and − / + controls.

**Facilitator tabs.** **Vault** (the UI, signed in as the facilitator),
**Audit** (every request, filterable by student, operation and path) and
**Apps** (each app-host slot and its log), next to Runners.

**Shortcuts stated to the class.** One unseal key share stays on a volume so the
vault unseals itself after a restart, and traffic to OpenBao and Postgres is
plain HTTP on the lab networks. See the workshop's
[README](workshops/vault-fundamentals/README.md) for why, and for sizing
(about 2 GiB for 10 demo bots).

### `dojo-introduction` — everything at once

Not a lab. The terminal image carries the tools of all four workshops and the
stack runs the vault, the runner pool, DNS with per-account zones, the
certificate authority and Dojo Cloud together, so a facilitator can click
through each capability as a student and as the facilitator. It adds no
services of its own: it lists the modules and reuses the other packs' sources
in one overlay, and serves each workshop's slides under a Workshop Library.

---

## Security boundaries

The lab assumes students will poke at everything they can reach, whether out of
curiosity or by accident. Three layers stop that from turning into access to
another student's work, to the host or to the internet:

1. **Trust zones.** There is one published port. Everything behind it sits on
   internal networks with no route out.
2. **Identity.** Only the gateway can say who a request is from, and every
   service checks that the claim really came from the gateway.
3. **Kernel checks.** Inside the shared terminal container, the Linux kernel
   decides which student is which, not anything a student can type.

### 1. Trust zones: one way in

```mermaid
graph TB
    NET(["Internet / class network<br/>untrusted"])

    subgraph z1["Zone 1 - the only way in"]
        GW["gateway (Caddy)<br/>the only published ports: :80 / :443<br/>TLS, sign-in, routing, identity headers"]
    end

    subgraph z2["Zone 2 - workshop_lab, internal: true, no route out"]
        AL["allocator<br/>sessions and student slots"]
        WT["web-terminal<br/>one Linux user per student<br/>no internet, no docker.sock"]
        GS["git-server (Forgejo)"]
        SVC["workshop services<br/>PowerDNS, step-ca, demo-app, cloud-api"]
    end

    subgraph z2b["web_lab - internal"]
        PR["presentation (Marp)"]
    end

    OUT(["Internet, outbound"])

    subgraph z3["Zone 3 - sandboxes, each with one door"]
        subgraph boot["bootstrap_net"]
            BS["bootstrap<br/>one-shot provisioning"]
        end
        subgraph rn["runner_net"]
            RN["runner-pool<br/>single-use runners, student-written CI"]
        end
        subgraph cn["cloud_net"]
            HOST["cloud-host<br/>privileged docker-in-docker"]
        end
    end

    NET ==>|"HTTPS, the one way in"| GW
    GW -->|"/, /admin"| AL
    GW -->|"/ide, /term, after /auth-check"| WT
    GW -->|"/git"| GS
    GW -->|"/cloud, /demo, after /auth-check"| SVC
    GW -->|"/slides"| PR
    WT -->|"lab traffic"| GS
    WT -->|"lab traffic"| SVC
    GS ---|"bootstrap's only door"| BS
    GS ---|"runners' doors: Forgejo,<br/>dns-api, OpenBao, app-host"| RN
    SVC ---|" "| RN
    SVC -->|"cloud-api's fixed templates only"| HOST
    WT -.-x|"no route"| OUT
    HOST -.-x|"no route"| OUT

    classDef person fill:#f59e0b2e,stroke:#f59e0b,stroke-width:2px
    classDef gw fill:#8b5cf62e,stroke:#8b5cf6,stroke-width:2px
    classDef core fill:#3b82f62e,stroke:#3b82f6,stroke-width:2px
    classDef addon fill:#10b9812e,stroke:#10b981,stroke-width:2px
    classDef priv fill:#ef44442e,stroke:#ef4444,stroke-width:2px
    class NET,OUT person
    class GW gw
    class AL,WT,GS,PR,BS core
    class SVC addon
    class RN,HOST priv
    style z1 fill:#8b5cf60f,stroke:#8b5cf6,stroke-width:1px,stroke-dasharray:5 4
    style z2 fill:#3b82f60f,stroke:#3b82f6,stroke-width:1px,stroke-dasharray:5 4
    style z2b fill:#3b82f60f,stroke:#3b82f6,stroke-width:1px,stroke-dasharray:5 4
    style z3 fill:#ef44440f,stroke:#ef4444,stroke-width:1px,stroke-dasharray:5 4
    style boot fill:#64748b0f,stroke:#64748b,stroke-width:1px,stroke-dasharray:5 4
    style rn fill:#ef44440f,stroke:#ef4444,stroke-width:1px,stroke-dasharray:5 4
    style cn fill:#ef44440f,stroke:#ef4444,stroke-width:1px,stroke-dasharray:5 4
```

- **Zone 1:** `gateway` is the only container with published ports, so it is
  the only thing that needs a hole in a firewall. It is also the only
  container attached to both the outside and the inside.
- **Zone 2:** every lab network is a Compose network with `internal: true`, so
  it has no route to the internet. Student terminals can reach Forgejo and
  their workshop's services, and nothing outside. Tools are baked into the
  image (pinned and sha256-checked) because nothing can be downloaded at lab time.
- **Zone 3:** the parts that are risky by nature each get a network of their
  own with exactly one door. Provisioning can reach Forgejo and nothing else.
  Student-written CI can reach Forgejo and PowerDNS, never the allocator or the
  terminals. The privileged Docker host runs student containers, but only
  `cloud-api` can reach it, through a shared socket, using fixed templates.
  Students never speak Docker, and `cloud-api` itself drops every Linux
  capability except binding :443.

### 2. Identity: only the gateway can say who you are

The gateway signs everyone in and tells the services behind it who each request
is from. To make that claim impossible to forge, it always travels as a pair of
headers that Caddy sets itself: `X-Auth-User` (who) and `X-Gateway-Token` (a
secret from `engine/.env`, owner-only, that only Caddy and that one service know:
each upstream gets a token of its own, so one service can't replay another's).

```mermaid
sequenceDiagram
    actor B as Browser
    box rgba(139,92,246,0.12) Zone 1
    participant GW as gateway (Caddy)
    end
    box rgba(59,130,246,0.12) Zone 2
    participant AL as allocator
    participant UP as the service (allocator, web-terminal, cloud-api)
    end

    rect rgba(139,92,246,0.16)
    Note over B,GW: Sign in
    B->>GW: request with the class login, the dojo_session cookie and perhaps a forged X-Auth-User
    GW->>GW: session_gate - a signed dojo_login cookie from /login for the class or the facilitator (only the facilitator's opens /admin)
    end

    rect rgba(59,130,246,0.16)
    Note over GW,AL: Check the session
    GW->>AL: /auth-check, with X-Auth-User and X-Gateway-Token set by Caddy
    AL->>AL: token correct (constant-time compare)? cookie holds a live student slot?
    AL-->>GW: yes - this student, and their workspace port
    AL-->>GW: no - send them back to / (or 404 for a tool this workshop doesn't have)
    end

    rect rgba(16,185,129,0.16)
    Note over GW,UP: Forward
    GW->>UP: proxy, with header_up REPLACING X-Auth-User and X-Gateway-Token
    UP->>UP: no valid token, no trust - then act as the user X-Auth-User names
    end
```

- **Headers are replaced, never passed through.** `header_up X-Auth-User ...`
  overwrites whatever the client sent, so a browser can't claim to be someone
  else by setting the header itself.
- **The token proves the request came through Caddy.** All students share one
  network, so a terminal can reach `allocator` or `cloud-api` directly. Without
  `X-Gateway-Token` those requests are refused (the Dojo Cloud portal answers
  `401`) before the identity header is ever read.
- **The cookie says which student.** The class shares one sign-in, so the
  student's own identity lives in their `dojo_session` cookie, which the
  allocator issues and checks on every `/auth-check`. A released or
  never-assigned session can't reach a workspace, even with the class password.
- **The facilitator has a separate door.** `/admin` accepts only a session
  signed in as the facilitator; the class login gets 403.

### 3. Kernel checks: students share a container, not an identity

Every student's shell, VS Code and terminal run in one `web-terminal`
container, and all students share its network namespace, so a source IP never
identifies anyone. Separation comes from Linux users instead, and the kernel
enforces it.

```mermaid
graph LR
    GW["gateway<br/>proxies to the port /auth-check chose"]

    subgraph wt["web-terminal container - one shared network namespace"]
        subgraph u1["student01 - its own Linux uid"]
            SH1["shell, VS Code"]
        end
        subgraph u2["student02 - its own Linux uid"]
            SH2["shell, VS Code"]
        end
        IPT{{"iptables DOJO_ISOLATION<br/>-m owner --uid-owner"}}
        P1["student01's code-server + ttyd<br/>ports 9001 / 9501"]
        P2["student02's code-server + ttyd<br/>ports 9002 / 9502"]
        BR["dojo-broker (root)<br/>unix socket"]
        KEY[("signing key<br/>root-only file")]
    end

    API["cloud-api<br/>checks the token's subscription"]

    GW --> P1
    GW --> P2
    SH1 -->|"connect to a workspace port"| IPT
    IPT -->|"own uid: ACCEPT"| P1
    IPT -.-x|"any other uid: DROP"| P2
    SH2 -->|"ask for credentials"| BR
    BR -->|"SO_PEERCRED: the kernel reports uid"| BR
    BR -->|"ARM_* for student02 only"| SH2
    KEY -.->|"readable by root only"| BR
    SH2 -->|"tofu apply"| API

    classDef gw fill:#8b5cf62e,stroke:#8b5cf6,stroke-width:2px
    classDef core fill:#3b82f62e,stroke:#3b82f6,stroke-width:2px
    classDef addon fill:#10b9812e,stroke:#10b981,stroke-width:2px
    classDef priv fill:#ef44442e,stroke:#ef4444,stroke-width:2px
    classDef store fill:#06b6d42e,stroke:#06b6d4,stroke-width:2px
    class GW gw
    class SH1,SH2,P1,P2 core
    class API addon
    class IPT,BR priv
    class KEY store
    style wt fill:#3b82f60f,stroke:#3b82f6,stroke-width:1px,stroke-dasharray:5 4
    style u1 fill:#f59e0b0f,stroke:#f59e0b,stroke-width:1px,stroke-dasharray:5 4
    style u2 fill:#f59e0b0f,stroke:#f59e0b,stroke-width:1px,stroke-dasharray:5 4
```

- **One Linux user per student.** `entrypoint.sh` creates `student01`..`studentNN`,
  each with its own uid and home directory. No student runs as root (the
  facilitator's shell does, by default, so they can help anyone). Homes are
  `0700`, and student Linux passwords are locked, so `su - student02` from
  student01's shell fails.
- **Each student has their own Forgejo login.** Every student's Forgejo password
  is derived from `STUDENT_PASSWORD_SEED` and their name, so one student's
  password doesn't open another's account. At start each terminal gets a scoped
  Forgejo token in `~/.git-credentials` and `~/.netrc` (both `0600`), so `git`
  and `curl` never ask for a password. The facilitator's Roster shows a
  student's password on demand (**Password** on their tile).
- **Workspace ports belong to their owner.** Each student's code-server and ttyd
  listen on a port of their own (9000+N and 9500+N). An `iptables` chain with an
  `owner` match lets a uid connect only to its own ports and drops everything
  else in those ranges, so student01 can't open student02's terminal from inside
  the container. From outside, only the gateway reaches them: it shares the
  `terminal_ingress` network with the terminal, and those ports are dropped on
  every other network. It only ever sends a request to the port `/auth-check`
  chose.
- **Each student sees only their own processes.** A student's IDE and terminal
  run in a PID namespace of their own, so `ps` shows nothing of a neighbour's
  command lines. The facilitator and the demo bots stay outside it.
- **Cloud credentials come from the kernel, not from the student**
  (tofu-basics). A shell asks the root-owned broker for its `ARM_*` values over
  a unix socket. The broker asks the kernel who is on the other end
  (`SO_PEERCRED`), so a student can only get their own credentials. The key that
  derives them is readable by root only, and `cloud-api` accepts a token only
  for that student's own subscription. The `openbao` module's identity broker
  (vault-fundamentals) works the same way: it signs a short-lived JWT only for
  the account on the other end of its socket, which OpenBao trades for a token.

### Other hardening

- **Sign-in.** The gateway refuses the default class and facilitator passwords
  off loopback and rate-limits wrong logins. `/slides` sits behind the class
  login. Plain HTTP off localhost prints a warning, and HTTPS sends HSTS.
- **Pages and services.** The allocator's pages run under a strict CSP with no
  inline script, and student-supplied text is only ever shown as text. The
  allocator is threaded, with a rate limit on new student assignments, so idle
  sockets can't stall sign-in.
- **Limits.** Each student's processes are capped, OpenBao has a request-rate
  quota per namespace, and `app-db`, `dns-api` and Dojo Cloud limit connections
  and request rates. Each limit is an env setting, and 0 turns it off.
- **Containers.** Runner-pool, app-host and their shims drop capabilities and
  set `no-new-privileges`. External images are pinned by digest. Every identity
  and control-plane decision writes one JSON log line.
- **Shared services.** CI writes DNS only with a Forgejo ID token issued for
  the class repository's `main` branch (`dns-gate`), so a pull request can't
  change live records. Each account has its own DNS key.

The threat-model report is in `threat-model-20260926-154208/`, and
[`RELEASES.md`](RELEASES.md) says which findings are fixed, partial or accepted.

### Who can reach what

Rows are the caller; a ✓ is a real network path. Everything else is either
blocked by network isolation or never routed.

| From ↓ / To → | `git-server` | `presentation` | `dns-server` | `step-ca` / `demo-app` | `cloud-api` | `cloud-host` | Internet |
| ------------- | :----------: | :------------: | :----------: | :--------------------: | :---------: | :----------: | :------: |
| Student terminal | ✓ | — | dns-as-code, cert-autorenewal | cert-autorenewal | tofu-basics (:443; :8080 needs the gateway token) | — | — |
| `gateway` | ✓ | ✓ | — | `/demo` (cert-autorenewal) | `/cloud` (tofu-basics) | — | published :80/:443 in, nothing else |
| `runner-pool` (dns-as-code: also `dns-api`; vault-fundamentals: also `openbao`, `app-host`) | ✓ | — | dns-as-code | — | — | — | — |
| `step-ca` (cert-autorenewal) | — | — | ✓ | ✓ | — | — | — |
| `cloud-api` (tofu-basics) | — | — | — | — | — | ✓ | — |
| `bootstrap` | ✓ | — | — | — | — | — | — |

vault-fundamentals adds `openbao` (`workshop_lab`), which the student terminal and app-host reach and the gateway fronts at `/ui` and `/v1`, and `runner_net`, which only the runner pool, `git-server`, `openbao` and `app-host` join.
