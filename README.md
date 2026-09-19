# Git & Version Control Lunch-and-Learn Series

A lunch-and-learn training series for engineering and IT operations,
building git fundamentals before moving into team-specific workflows (e.g.
DNS-as-Code, certificate automation, Infrastructure-as-Code).

## Layout

```
├── run.sh                          # Forwards to engine/run.sh, so ./run.sh <workshop> works from the repo root
├── engine/                         # Reusable workshop runtime (Forgejo + web terminal + slides), shared by every workshop
├── assets/branding/                # Shared branding
├── handouts/                       # Printable handouts (git-fundamentals, dns-as-code)
└── workshops/
    ├── README.md                   # Workshop catalog + how selection/overlay works + how to add one
    ├── assets/themes/              # Shared slide CSS, mounted into every workshop's deck
    ├── git-fundamentals/           # Session 1: core git workflow (content-only workshop pack)
    │   ├── content/                # Mounted into the engine: slides, lab instructions, seed repo
    │   ├── docs/                   # Student/facilitator docs for the local-lab delivery
    │   └── delivery-azure-devops/  # Alternate delivery mode: Azure Repos, doc-only
    ├── dns-as-code/                # Session 3: DNS-as-Code via dnscontrol
    │   ├── content/
    │   └── compose/                # Overlay: PowerDNS + Forgejo Actions runner + terminal with dnscontrol
    ├── cert-autorenewal/           # TLS certificate issuance and renewal via ACME
    │   ├── content/
    │   └── compose/                # Overlay: step-ca + PowerDNS + shared demo web app + terminal with certbot/acme.sh
    └── tofu-basics/                # OpenTofu basics (in progress): offline sandbox + "Dojo Cloud"
        ├── content/
        ├── compose/                # Overlay: cloud-api + cloud-host + terminal with tofu and a credential broker
        └── PLAN.md                 # Design, decisions, task list, progress log
```

`engine/` is the reusable part — a self-hosted Git server, browser terminal,
and slide deck, wired together so a student needs nothing but a browser.
Nothing in it is specific to any one workshop's topic: which workshop runs
is a runtime choice, not something you edit `engine/` to change.

Each `workshops/<name>/` is a self-contained **workshop pack** — content,
and (only if the lab needs it) its own Compose overlay for different
tooling or extra backend services. Pick one with `./run.sh <name>`. See
[`workshops/README.md`](workshops/README.md) for exactly how that works and
how to add a new workshop.

```mermaid
graph LR
    Student(["Student's browser"]) -->|"one URL"| Gateway["engine/<br/>gateway + git server +<br/>terminal + slides"]
    Facilitator(["Facilitator"]) -->|"./run.sh WORKSHOP"| Gateway
    Gateway -->|"mounts WORKSHOP_CONTENT_DIR"| Content["workshops/NAME/content/<br/>slides, lab, sample-repo"]
    Gateway -.->|"optional overlay"| Extra["workshops/NAME/compose/<br/>extra services, custom terminal image"]
    Facilitator -->|"edits, no engine changes"| Content
```

## Start here

- **Run a workshop locally:** `./run.sh setup`, then `./run.sh <workshop>` — see [`engine/README.md`](engine/README.md)
- **Which workshops exist, and how to add one:** [`workshops/README.md`](workshops/README.md)
- **Session 1 (Git Fundamentals):** [`workshops/git-fundamentals/README.md`](workshops/git-fundamentals/README.md)
- **Session 3 (DNS as Code):** [`workshops/dns-as-code/README.md`](workshops/dns-as-code/README.md)
- **Certificate Autorenewal:** [`workshops/cert-autorenewal/`](workshops/cert-autorenewal/) (lab instructions in `content/lab/`)
- **OpenTofu Basics:** [`workshops/tofu-basics/README.md`](workshops/tofu-basics/README.md) (design and status in [`PLAN.md`](workshops/tofu-basics/PLAN.md))

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
```

`lab/` files a student has already edited are never overwritten by an
update. `FORGEJO_ORG`/`FORGEJO_REPO` come from the workshop's
`workshop.env`.

### Summary: what each workshop adds

| Workshop | Extra services | Extra networks | Terminal image adds | Data leaves the terminal to |
| -------- | -------------- | -------------- | ------------------- | --------------------------- |
| `git-fundamentals` | none | none | nothing (base image) | Forgejo only |
| `dns-as-code` | `dns-server`, `runner-setup`, `forgejo-runner` | `runner_net` | `dnscontrol`, `dig`, `python3` | Forgejo, PowerDNS |
| `cert-autorenewal` | `dns-server`, `dns-seed`, `step-ca`, `demo-app` | static subnet on `workshop_lab` | `step`, `certbot`, `acme.sh`, `openssl`, `dig`, `jq` | step-ca, PowerDNS, shared webroot volume |
| `tofu-basics` | `cloud-api`, `cloud-host` | `cloud_net` | `tofu` (also `terraform`), offline provider mirror, credential broker | `cloud-api` (Track B) |

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
    participant WT as web-terminal (~/lab)
    participant GS as git-server (Forgejo)
    participant GW as gateway
    actor F as Facilitator

    S->>WT: git clone http://git-server:3000/training/sample-training-repo
    WT->>GS: clone, direct over workshop_lab
    S->>WT: branch, edit, commit
    WT->>GS: git push (studentNN + STUDENT_PASSWORD)
    S->>GW: Open Forgejo (/forgejo-login, then /git/...)
    GW->>GS: proxy, already signed in as studentNN
    S->>GS: open a pull request
    F->>GS: review and merge (facilitator's Forgejo tab under /admin)
```

Git traffic never goes through the gateway — pushes and clones go straight
from the terminal to `git-server:3000`, and only the browser UI is proxied.

---

### `dns-as-code` — Forgejo Actions runner + PowerDNS

**Infrastructure and connectivity.** Adds a PowerDNS authoritative server
and a CI runner. The runner executes student-authored workflow steps
directly on its own filesystem (no sandbox, no `docker.sock`), so it lives
on its own `runner_net` and can reach only `git-server` and `dns-server` —
never `allocator` or `web-terminal`.

```mermaid
graph TB
    Browser(["Browser"]) --> GW["gateway"]
    GW -->|"/git"| GS

    subgraph lab["workshop_lab - internal"]
        WT["web-terminal<br/>dnscontrol, dig"]
        GS["git-server (Forgejo)<br/>Actions enabled<br/>also on runner_net"]
        DNS["dns-server (PowerDNS)<br/>:53 DNS, :8081 API<br/>also on runner_net"]
    end

    subgraph rn["runner_net - internal"]
        RS["runner-setup<br/>one-shot"]
        RN["forgejo-runner<br/>host label, runs CI in place"]
    end

    RC[("dns_runner_config<br/>volume")]
    FD[("forgejo_data<br/>volume")]

    WT -->|"git clone / push"| GS
    WT -->|"dnscontrol preview / push, :8081"| DNS
    WT -->|"dig @dns-server, :53"| DNS
    RN -->|"poll for jobs, clone, post status"| GS
    RN -->|"dnscontrol preview / push, :8081"| DNS
    RS -->|"registers the runner with the forgejo CLI"| FD
    RS -->|"writes config.yaml"| RC
    RC -.->|"read-only"| RN
```

**Dataflow.** One change travels the whole loop: local preview, PR, CI
preview, merge, CI apply, verify. The record only goes live when CI pushes
it after the merge — not when the student pushes their branch.

```mermaid
sequenceDiagram
    actor S as Student (terminal)
    participant GS as git-server (Forgejo)
    participant RN as forgejo-runner
    participant DNS as dns-server (PowerDNS)

    S->>DNS: dnscontrol preview (reads zone via :8081, changes nothing)
    S->>GS: git push branch, open pull request
    GS-->>RN: pull_request event, job queued (runner polls)
    RN->>GS: clone PR head over runner_net
    RN->>DNS: dnscontrol preview (:8081)
    RN->>GS: comment the diff on the PR, set "DNS Preview" status
    S->>GS: merge the PR to main
    GS-->>RN: push to main, job queued
    RN->>GS: clone main
    RN->>DNS: dnscontrol push (:8081), the record goes live
    RN->>GS: set "DNS Apply" status
    S->>DNS: dig @dns-server name A +short (:53), verify
```

Zone data lives only in the PowerDNS container's own filesystem, so it
resets on every teardown. Credentials for the API (`creds.json`) are in the
seeded repo and are workshop-only, not secrets.

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
    participant CA as step-ca
    participant V as /srv/webroot (shared volume)
    participant APP as demo-app (nginx)
    participant DNS as dns-server (PowerDNS)

    Note over S,CA: Lab 1 - trust the CA
    S->>CA: step ca bootstrap, using the root cert from /opt/step-ca-root

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

    Note over S,APP: Lab 4 - automated renewal
    loop cron runs the renewal script
        S->>CA: renew (ACME)
        S->>V: install the new cert
        V-->>APP: reload
    end

    Note over S,DNS: Lab 5 - dns-01 instead
    S->>CA: certbot --manual --preferred-challenges dns-01
    S->>DNS: PUT _acme-challenge TXT record (:8081 API)
    CA->>DNS: look up the TXT record
    CA-->>S: signed certificate
```

The `/demo` link on the workshop homepage is HTTP-only and never touches a
student's certificate, so `curl --cacert` from the terminal is the real
check that a cert is valid.

---

### `tofu-basics` — offline sandbox + "Dojo Cloud" (in progress)

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
    Browser(["Browser"]) -.->|"planned"| GW["gateway"]
    GW -.->|"/cloud, not routed yet"| API

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
```

Dashed edges through the gateway are **planned, not wired yet**: the Dojo
Portal and the deployed-site links (`/cloud/site/<label>/`) need a gateway
route and a landing-page button (phase P5 in
[`PLAN.md`](workshops/tofu-basics/PLAN.md), which touches the base engine
and is gated on the maintainer's OK). Today a student deploys entirely from
their terminal. `cloud_data` mirrors control-plane state to disk so a
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
```

**Dataflow — Track B (Dojo Cloud).** The student never holds a long-lived
secret: the broker derives that student's credentials from the caller's
real uid, and `cloud-api` authorises every call against the token's own
subscription.

```mermaid
sequenceDiagram
    actor S as Student shell
    participant BR as dojo-broker (root)
    participant API as cloud-api
    participant HOST as cloud-host

    S->>BR: new shell asks for credentials (unix socket)
    BR-->>S: ARM_* values for that uid only (uid comes from SO_PEERCRED)
    S->>S: tofu init, offline, from the provider mirror
    S->>API: tofu apply - fetch metadata, get a token (HTTPS, private CA)
    S->>API: PUT resource group, PUT container group
    API->>API: authenticate token, check subscription, run policy
    API->>HOST: fixed-template docker run over the shared socket
    HOST-->>API: container running
    API-->>S: Succeeded, the provider polls the operation
    S->>S: output "url" prints /cloud/site/label/
    S->>API: tofu destroy - DELETE, container removed
```

Policy rejections come back as ARM-shaped errors (a required tag missing,
a disallowed region, an oversized container, over quota) so the labs can
teach reading real-looking failures.

---

## Who can reach what

Rows are the caller; a ✓ is a real network path. Everything else is either
blocked by network isolation or never routed.

| From ↓ / To → | `git-server` | `presentation` | `dns-server` | `step-ca` / `demo-app` | `cloud-api` | `cloud-host` | Internet |
| ------------- | :----------: | :------------: | :----------: | :--------------------: | :---------: | :----------: | :------: |
| Student terminal | ✓ | — | dns-as-code, cert-autorenewal | cert-autorenewal | tofu-basics (:443; :8080 needs the gateway token) | — | — |
| `gateway` | ✓ | ✓ | — | `/demo` (cert-autorenewal) | planned (tofu-basics, P5) | — | published :80/:443 in, nothing else |
| `forgejo-runner` (dns-as-code) | ✓ | — | ✓ | — | — | — | — |
| `step-ca` (cert-autorenewal) | — | — | ✓ | ✓ | — | — | — |
| `cloud-api` (tofu-basics) | — | — | — | — | — | ✓ | — |
| `bootstrap` | ✓ | — | — | — | — | — | — |

Three deliberate boundaries carry the security model: `bootstrap_net`
(provisioning can reach Forgejo and nothing else), `runner_net` (student-authored
CI can't reach the control plane), and `cloud_net` (the privileged host is
reachable only through `cloud-api`'s fixed templates).

## Audience

- Engineering team members (mixed git experience, some daily users)
- IT operations team members (little to no git/version control experience)
- Assumes comfort with a terminal; no assumed git knowledge

## Goals of the series

1. Get everyone speaking the same language around version control and git.
2. Build confidence with the core git workflow through hands-on practice.
3. Establish a shared team workflow/convention to point back to later.
4. Lay the foundation for later, more specific sessions (e.g. managing DNS
   zone files as code, PR review process, CI checks on infra changes).

## Session roadmap

| # | Session | Format | Status |
| - | ------- | ------ | ------ |
| 1 | Git Fundamentals: What/Why/How + Hands-on Lab | 60 min | [`workshops/git-fundamentals/`](workshops/git-fundamentals/) |
| 2 | Branching Workflows & Pull Requests in Practice | 45-60 min | Future |
| 3 | Team Git Conventions + DNS-as-Code Repo Walkthrough | 45-60 min | [`workshops/dns-as-code/`](workshops/dns-as-code/) |
| 4 | Handling Conflicts, Rebasing, and "Oh No" Recovery | 45-60 min | Future |
| 5 | Automating Checks: Pre-commit Hooks & CI Pipelines | 45-60 min | Future |

### Additional workshops (not yet slotted into the numbered series)

| Workshop | Topic | Status |
| -------- | ----- | ------ |
| [`workshops/cert-autorenewal/`](workshops/cert-autorenewal/) | Automated TLS certificate issuance and renewal via ACME (step-ca, certbot, acme.sh) | Runs today |
| [`workshops/tofu-basics/`](workshops/tofu-basics/) | OpenTofu/Terraform basics: `init`/`plan`/`apply`/`destroy` and repo layout. Track A (offline sandbox) runs today; Track B (Dojo Cloud) is in progress | In progress — see [`PLAN.md`](workshops/tofu-basics/PLAN.md) |
