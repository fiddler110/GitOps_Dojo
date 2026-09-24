# PLAN — `vault-fundamentals`: secrets in code, git, pipelines and deployments (OpenBao)

> **Purpose of this file:** the single source of truth for building this
> workshop. It is written so a brand-new session (human or Claude) can pick up
> exactly where the last one stopped. Keep it current — tick boxes in §11 and
> append to the Session Log (§15) as you go.

| | |
|---|---|
| Created | 2026-09-23 (design conversation with the user; moved here from `keyvault-workshop-plan.md` the same day) |
| Owner | scott |
| Workshop folder | `workshops/vault-fundamentals/` |
| Run command (when built) | `./run.sh vault-fundamentals` |
| Overall status | **Design agreed (§1, S1-S17). No code yet. Ready to start P0 (spike), waiting on the user's go-ahead.** |
| Working branch | `feat/vault-fundamentals` (branched from `main` at `ebd0457`, after tofu-basics merged) |
| Last updated | 2026-09-23 (plan moved into the workshop folder; resume section, task list and session log added) |

---

## 0. HOW TO RESUME (read this first)

1. Read this whole file once.
2. `git status` and `git log --oneline -20`. Every finished task records its
   commit SHA (or "findings in §10") next to its checkbox in §11. If a box is
   ticked but the SHA is not in `git log`, treat the task as **not done**.
3. Check §1 (decisions) and §12 (open questions). Do not start work that
   depends on an open question. Read **§14 (Worth knowing)** for surprises and
   problems found along the way.
4. **Ask the user before moving from one phase to the next** (P0 → P0.5 → P1 …).
   Ask before editing any `engine/` file, even for a spike.
5. Find the first `[ ]` or `[~]` task in §11. Before starting it, run the
   **Verify** line of the previous finished task to make sure the foundation
   still holds.
6. Work the task. When finished: tick the box, add the commit SHA, and append a
   dated entry to §15. If you learned something that changes the plan, edit the
   relevant section — do not just note it in the log.
7. If you are blocked, mark the task `[!]`, say why in §15, and move to the
   next unblocked task.

**Task markers:** `[ ]` todo · `[~]` in progress · `[x]` done (+ SHA) ·
`[!]` blocked · `[-]` dropped (say why).

**Working style (from `CLAUDE.md` and memory):** podman + podman-compose only,
build and start through `./run.sh`; verify on the real stack; keep the main
context small and hand builds, live tests and wide searches to sub-agents with
token rules in every brief (tail/grep logs, capped retries, cheaper models).

**Prompt to paste into a fresh Claude Code session:**

```text
Read workshops/vault-fundamentals/PLAN.md fully. Follow its "HOW TO RESUME"
section: check git log against the ticked tasks, verify the last completed task
still works, then continue with the first unchecked task. Update PLAN.md
(checkboxes, commit SHAs, Session Log) as you go. Ask me before moving to a new
phase, before editing engine/, and about anything in section 12.
```

---

## 1. Decisions so far (user, 2026-09-23)

| # | Decision |
|---|----------|
| S1 | **A separate workshop**, not an addition to tofu-basics. Name: **`vault-fundamentals`**. |
| S2 | **Use a real vault: OpenBao**, not an emulation of Azure Key Vault. No Dojo Cloud / `cloud-api` work. |
| S3 | **Drop Azure parity.** Add a talk slide that maps OpenBao to Azure Key Vault (§9), because the corporate audience uses Key Vault. |
| S4 | **Teach how companies really do it.** The audience is corporate: people who will use a vault, already use one, or will administer one. |
| S5 | **Security runs through every lab**, not in one security lab at the end (§3). |
| S6 | **Slot is 2-3 hours**, with plenty of hands-on time. Cover every core concept. |
| S7 | **One OpenBao for the class, two tenancy models:** a shared path with **one templated policy** (the student as a vault *user*) and **a namespace per student** (the student as a vault *admin*). |
| S8 | **Cover four areas: secrets in code, in git, in pipelines and in deployments.** |
| S9 | **The web UI is on**, for students and the facilitator. It's another **card on the landing page**, reached through Caddy on the same host and port as everything else (§5.4). Labs lead with the CLI and use the UI where it helps. |
| S10 | **Deployment target: `app-host`**, a small in-stack "platform" with a platform identity (§5.6). |
| S11 | **Policy as code is deferred** to a later lab or a follow-up workshop (§13). Policies are still written in the UI and CLI (lab 3). This workshop's "as code" focus is **CI**. |
| S12 | **CI runners: one job each at a time, autoscaled**, with an `/admin` **Runners panel**: a status light per runner and **− / +** buttons (§6). |
| S13 | **Runs on one machine**: the facilitator's laptop for testing, an Azure VM for real classes. Nothing may need extra ports, extra DNS names or anything outside the stack. |
| S14 | **Engine changes go through a new general "workshop extensions" mechanism** (option B, §8.1): a workshop declares its own landing cards, `/admin` tabs and gated routes. No more per-workshop flags. |
| S15 | **The Runners panel starts every class in Auto.** |
| S16 | **Runner isolation: the process pool** (§6.2 A), with **Docker-in-Docker as the fallback** if it fails P0. Chosen to balance security and resource use. |
| S17 | **The extensions mechanism is foundational.** Once it's proven, **every workshop moves onto it** (`CLOUD_ENABLED` and `DEMO_APP_ENABLED` retired), each re-tested on the real stack. Design its format so it can later describe reusable **modules** too (§13). |

## 2. Teaching goal

Not "how to install a vault". The goal is **how to use one well**: get secrets out of code, git, pipelines and servers,
and replace long-lived secrets with **identity** and **short-lived credentials**, while GitOps keeps working.

Prerequisite: `git-fundamentals`.

## 3. Security principles (every lab points back to these)

The talk introduces them, each lab ends with a "which principle did this apply?" line, and the cheat sheet lists them.

1. **Least privilege**: every token and identity can read only what it needs. Policies deny by default.
2. **Identity over secrets**: prove *who you are* (OIDC, JWT, platform identity) instead of holding a password.
3. **Short-lived and revocable**: TTLs, leases, dynamic credentials. A leaked credential should expire by itself.
4. **The "secret zero" problem**: the first credential has to come from somewhere; know where yours comes from.
5. **Separation of duties**: the pipeline can deploy the app but can't read its production secrets.
6. **Audit everything**: every read is logged. You can answer "who read this, and when?"
7. **Plan for leaks**: rotation, revocation and the incident drill are normal operations, not emergencies.
8. **Never in git, never in logs, never in images**: including history, CI output and container layers.

## 4. Lab outline (draft, 12 labs over 2-3 hours)

**Part 1: Foundations (the vault user)**

0. **Orientation.** Open the Vault card and sign in with Forgejo (single sign-on, §5.4); the CLI is already
   logged in. `bao token lookup`: tokens have a TTL and policies. Tour the UI.
1. **Leak it.** Commit a secret, "delete" it, find it with `git log -p`. Rotating is the only fix. Add a `gitleaks`
   pre-commit hook and scan history. The next attempt is blocked before it leaves the machine.
2. **Use the shared vault.** KV v2 in the shared `secret/` mount under `secret/students/<you>/`: put, get, versions,
   roll back, delete vs destroy. Try a neighbour's path and get a 403. Read the **templated policy** that did it.

**Part 2: Administering a vault (your namespace)**

3. **You are the admin.** In your own namespace: enable a KV engine, write a least-privilege policy (first in the
   **UI**, then the same policy with `bao policy write`), create a token with it, prove what it can and can't do.
   Read your own audit trail.

**Part 3: Secrets in code**

4. **The app reads a secret.** The same small app in three versions:
   - a secret hard-coded in the source
   - a secret from an env var loaded from a git-ignored `.env` file
   - the secret read from the vault with the SDK

   Don't log secrets; tokens need renewing.
5. **OpenBao Agent.** Agent logs in by itself and writes the secret to a file (`0600`, in memory, not on disk).
   Rotate the secret in the vault and the app picks it up **without a commit or a redeploy**.

**Part 4: Secrets in git**

6. **Encrypted config in the repo.** `sops` with OpenBao's **transit** engine: the file lives in git, and the key
   never leaves the vault. Show who can decrypt, what a diff looks like, and rotating the transit key (`rewrap`).

**Part 5: Secrets in pipelines**

7. **Forgejo Actions secrets.** A repository secret used in a workflow. Masking in logs, and how easily masking is
   bypassed (`base64`). Why a workflow from a pull request can steal secrets.
8. **CI logs in to OpenBao.** First with AppRole: it works, but the AppRole login secret is itself stored in the
   pipeline (secret zero). Then with the **job's own OIDC token**, bound to *this repo on the `main` branch*, so nothing
   is stored at all. A job on another branch is refused.

**Part 6: Secrets in deployments**

9. **Deploy with workload identity** (§5.6). The pipeline deploys the app to `app-host` but **cannot read the app's
   secrets**. The app proves its identity to OpenBao through the platform and gets its own secrets.
10. **Dynamic database credentials.** The app gets a Postgres login made for it, with a lease. Watch it expire, renew
    it, revoke it. There is no shared database password left to leak.
11. **Incident drill (capstone).** "A token leaked." Use the audit log to find what it read, revoke it (and
    everything under it), rotate what it touched, and check that the app recovers by itself.

**Stretch:** response wrapping for handing over an AppRole login secret safely; the PKI engine for short-lived
certificates (ties in with `cert-autorenewal`).

## 5. Architecture

### 5.1 Services (all in the workshop overlay)

| Service | Purpose |
|---|---|
| `openbao` | One server for the class. Raft storage on a volume, UI on. |
| `openbao-setup` | One-shot: initialise, unseal, create the tenancy layout (§5.3), the auth methods (§5.4), the facilitator policy, the audit device; then **revoke the root token**. Re-unseals after a restart. |
| `runner-pool` + `runner-controller` | CI runners (one job each at a time) and the controller that scales them and serves the Runners panel (§6). |
| `app-host` | The deployment target: a small "platform" with one slot per student and a platform identity (§5.6). |
| `postgres` | A shared database for lab 10's dynamic credentials. |
| terminal image | Adds `bao`, `sops`, `gitleaks`, Python with `hvac`, and the identity broker for CLI login. All pinned and sha256-verified per architecture. |

The unseal key sits on a setup-only volume. Say openly that this is a lab shortcut: in production you use
**auto-unseal** with a cloud key service or an HSM. That makes a good slide.

### 5.2 Networks

- Terminals, `openbao`, `app-host`, `postgres` on `workshop_lab`.
- Runners on their own `runner_net`, as `dns-as-code` does: they reach `git-server`, `openbao`, `app-host` only, never
  the control plane (`allocator`, `web-terminal`).
- Students can reach OpenBao directly. That is allowed under our trust model because OpenBao checks its **own**
  tokens and never trusts our identity headers.

### 5.3 Tenancy: one server, two models

- **Root namespace, shared mount `secret/`**: one **templated ACL policy** gives every student
  `secret/data/students/{{identity.entity.name}}/*`. This is the corporate "shared vault, one team path each" pattern.
- **Namespace `students/<name>`** per student, where the student holds an admin policy **inside their own namespace
  only**. This is the "your team's own vault" pattern (in Azure, a Key Vault per team or environment). Lab 3 and
  labs 8-10 happen here: students enable engines, configure auth methods and write policies themselves.
- **Facilitator**: an admin policy across all namespaces (not root), plus the audit log.

### 5.4 Reaching the UI, and single sign-on

- **The UI is a landing-page card, like every other tool.** OpenBao is inside our stack, so Caddy can forward to it.
  OpenBao's UI can't live under a path of our choosing (such as `/vault/`), but it doesn't need to: it lives at
  **`/ui/`** and calls its API at **`/v1/`**, and neither path is used by our gateway today (checked against
  `engine/gateway/Caddyfile` on 2026-09-23). So Caddy routes `/ui/*` and `/v1/*` to `openbao:8200` on the
  **same host and port 443**, behind the same login gate as the other tools. The card links to `/ui/`.
  - No extra port and no extra DNS name, so it works on a laptop and on an Azure VM alike, and through corporate
    firewalls.
  - The terminal CLI doesn't go through Caddy: it talks to `openbao:8200` directly on `workshop_lab`.
  - The routes only exist when the workshop turns them on (§8).
- **UI login is single sign-on through Forgejo.** OpenBao's OIDC auth method uses Forgejo as the identity provider,
  so logging in is "Sign in with Forgejo". It's the same pattern as Entra ID at work.
- **CLI login is automatic.** The browser can't reach the terminal's `localhost`, so the CLI OIDC flow won't work.
  Instead, a broker in the terminal (the `SO_PEERCRED` pattern from tofu-basics D3) gives each Linux user a signed
  JWT, and `bao login -method=jwt` uses it. Setup links both logins to **one identity entity** per student, so the
  same policies apply to both.
- **Facilitator**: the same OIDC login with the facilitator account gets the facilitator policy. The `/admin`
  workspace gets a **Vault** tab (OpenBao may refuse to be framed; its response headers are configurable, to verify).

### 5.5 CI identity (lab 8)

Forgejo 16 (our pinned version) should be able to give a job its own **OIDC token**, as GitHub Actions does. OpenBao's
JWT auth trusts Forgejo's signing keys, and a role bound to `repository` + `ref` claims decides what the job can read.
**To verify in P0.** Fallback: AppRole only, and teach OIDC on a slide.

### 5.6 Deployment secrets: the "proper" way (labs 9-10)

**The answer to "how should an app on a server get its secrets?", from best to worst:**

1. **Platform identity.** The platform the app runs on vouches for it: Azure managed identity, a Kubernetes service
   account token, AWS instance roles. The app (or an Agent next to it) exchanges that identity for a short-lived vault
   token and reads only its own secrets. No secret is ever handed to the app. **This is the goal.**
2. **Dynamic credentials on top of that.** Instead of a stored database password, the vault creates one for this
   app instance, with a lease, and revokes it when the lease ends.
3. **AppRole plus a trusted deliverer.** When there is no platform identity, the deploy pipeline delivers a
   single-use, **response-wrapped** login secret, never the secrets themselves.
4. **Anti-patterns:** secrets in the image, in a committed compose file or `.env`, pushed by the pipeline into env
   vars, or one shared long-lived token.

**How the lab does this.** `app-host` is a small "platform":

- **One slot per student.** Each slot is its own Linux user, and processes can't see other users' processes
  (`hidepid`).
- **A platform identity service** keeps a signed JWT for each slot in a file only that slot can read, refreshed every
  few minutes. This mirrors a Kubernetes projected service-account token and the Azure managed identity endpoint.
- **In the student's namespace,** the student sets up JWT auth that trusts the platform's signing keys and a role bound
  to their slot.
- **The pipeline deploys but can't read.** It deploys the app with its own CI identity, which has *deploy* rights on
  `app-host` and **no** read access to the app's secrets.
- **At startup,** the app's Agent logs in with the slot's JWT and writes the secrets to a file.

This needs its own security design, the same kind as tofu-basics D3: one slot must not be able to get another slot's
JWT. It is the largest build item in this plan.

## 6. Runners: one job each, autoscaled, and the Runners panel

### 6.1 The model: single-use runners (how companies do it)

This copies GitHub's Actions Runner Controller on Kubernetes:

- **Every runner takes one job and is then thrown away.** A controller keeps a few **warm, idle** runners ready and
  replaces each one as it is used.
- **No residue.** A runner never runs a second job, so student B's job can't find anything student A's job left behind.
  This isolation is itself a lesson (it's why companies use single-use runners).
- **Instance-wide registration.** Runners serve the whole instance, so any free runner takes any student's next job.
- To verify in P0: whether our `forgejo-runner:13` can run once and exit (a one-job / ephemeral mode). If it can't, the
  fallback is long-lived runners with `capacity: 1` that the controller wipes after each job.

### 6.2 Where runners run, and who may start them

**Fact to design around:** the engine deliberately has **no container-engine socket anywhere**. `allocator` reaches
the terminals through `web-terminal`'s control port (`engine/README.md:77`), and `workspace-control.py` manages
per-student *processes* "so no docker.sock or cross-container privilege is" needed. Only tofu-basics' `cloud-host`
(privileged Docker-in-Docker, D2) breaks from that, and only inside its overlay.

Three options were compared (2026-09-23):

| | **A. Process pool** (recommended) | B. Docker-in-Docker (like `cloud-host`) | C. Socket proxy to the host engine |
|---|---|---|---|
| How | One **unprivileged** `runner-pool` container. A supervisor runs N `forgejo-runner` processes, each as its **own Linux user** with its own home/workspace. After each job: kill the process, delete the user and its files, create a fresh one. | A privileged container with its own engine; one runner container per runner inside it. | Runners are sibling containers on the host engine; the controller reaches the host socket through a filtering proxy. |
| Container API needed | **None.** Scaling is starting/stopping processes. | The inner engine's API only. | **The host's.** |
| If the controller is compromised | It can run processes as runner users inside one unprivileged container. | It can start a *privileged* inner container, and from there reach the privileged outer one, then the host. **Privileged dind is not a real security boundary**: correcting an earlier draft of this plan, which said it was. | Generic proxies (e.g. docker-socket-proxy) filter by **endpoint**, not by request body. Anything allowed to *create* a container can create a privileged one with `/` mounted, which is **root on the host**. Only a proxy that checks the body (image allow-list, no mounts, not privileged, fixed network) prevents that, and we'd have to write it. |
| If a student job breaks out | It lands as an unprivileged user in an unprivileged container. | It lands in a privileged container, one step from the host. | It lands in an unprivileged sibling container, the same as any container. |
| Isolation between runners | Unix users, `umask 077`, per-user `TMPDIR`, other users' processes hidden. Weaker than separate containers, but each runner is thrown away after one job. | Separate containers. | Separate containers. |
| Resources | **Lowest**: one container, about 30-50 MB per idle runner process (to measure), no second engine, no duplicate images. | An extra engine (about 50-100 MB) plus a second copy of the runner image and nested storage. | Low: shares the host's image cache. |
| Host setup | None. | None. | Podman's API socket must be enabled on the laptop and the VM, and its path differs between rootful and rootless. |
| Fits the engine's "no socket" design | **Yes**, and it follows the `workspace-control.py` pattern. | Partly (it's the `cloud-host` exception). | **No**: it would be the first host socket in the stack. |

**Recommendation: A.** It is the cheapest on resources and has no container-API capability to steal at all. Its
weak point is isolation between runners that are running at the same time, because they share one container. That's
acceptable because every runner is thrown away after one job and every secret in the lab is fake, and the lab says so.

Hardening for A:

- the pool container has a memory and process-count limit, so a runaway job can't starve the VM
- each runner's resources are capped (`prlimit`)
- `runner_net` only, with no route to the control plane
- the controller's web panel and the supervisor that starts processes are separate programs; the panel only writes
  the desired count, and the supervisor has no network listener

To verify in P0: that other users' processes can be hidden inside an unprivileged container (the way `web-terminal`
already isolates students), and that Forgejo's `host` label jobs work with one registered runner per Linux user.

**If A fails P0:** fall back to B with the runner image pre-loaded into the dind image. **C only** with a
body-checking proxy that we write ourselves, never with a generic endpoint filter.

### 6.3 Autoscaling (feasible; it's a small control loop)

Every few seconds the controller reads two numbers from Forgejo, the **jobs waiting** and each **runner's state**,
and then:

- **Scale up:** if jobs are waiting and there are fewer runners than **max**, start one runner per waiting job, up to
  max. This is what happens when a whole class pushes at once.
- **Keep a warm pool:** always keep **min idle** runners ready so the first jobs start at once.
- **Scale down:** remove idle runners above the warm pool after about 2 minutes idle. **Never remove a busy runner.**

It's feasible because the loop is simple. The two unknowns are both **to verify in P0**:

- whether Forgejo's API reports waiting jobs and runner state
- how quickly a fresh runner comes up

Starting points (to measure):

| Students | Warm idle (min) | Max runners |
|---|---|---|
| 10 | 2 | 4 |
| 20 | 3 | 7 |
| 30 | 4 | 10 |

The formula is **max = `ceil(STUDENT_COUNT / 3)`**, with at least 2 and at most 12. With jobs of 30-45 s, three jobs
queued per runner means a worst wait of about 2 minutes. Both numbers can be set in `workshop.env`. The Azure VM size
sets the real ceiling: measure a runner's memory during a job in P0 and put it in the sizing docs.

### 6.4 The Runners panel in `/admin`

- **A light per runner:** 🟢 ready, waiting for a job; 🟡 running a job (shows which student's repo); 🔴 something is
  wrong (failed to start, went offline, crashed, stuck on one job too long).
- **The number of runners with − / + on each side.** "+" adds a runner at once; "−" removes an **idle** one (never a
  busy one).
- **An Auto / Manual switch; every class starts in Auto (S15).** In Auto, − / + move the **warm-idle minimum** and the controller still scales up under
  load. In Manual, the controller does nothing by itself, which is useful when troubleshooting.
- Also shows: jobs waiting, and the min / max in use.
- **Built as a normal page served by `runner-controller`** and shown as a tab in `/admin`.
  - **Access:** the page checks `X-Gateway-Token` and allows the facilitator only.
  - **Load:** it makes one container-list call per request, cached for about 2 s, following the engine rule.
  - **Safety:** the − / + buttons are POST requests with a CSRF check.
  - **Display:** runner names and repo names are shown with `textContent` only, since students choose repo names.

## 7. Facilitator view (CLAUDE.md rule)

For every student-facing piece there is a facilitator entry:

- a **Vault** tab with the facilitator policy
- the audit log, readable and filterable by student
- the **Runners** panel (§6.4)
- `app-host` slot status

## 8. Rules to carry over, and the engine changes this needs

- **No `engine/` edits without asking.** The pieces that need the engine, all off by default:
  - Caddy routes `/ui/*` and `/v1/*` to OpenBao
  - a **Vault** card on the landing page
  - **Vault** and **Runners** tabs in `/admin`

  These go through the workshop extensions mechanism (S14, §8.1), not a new flag.
- **Secret names, entity names, repo names and slot output are student-controlled strings** shown to others: render
  with `textContent` only, and keep the strict CSP.
- **Anything on `workshop_lab` must check `X-Gateway-Token`** unless, like OpenBao, it does its own authentication.
  The identity broker, the platform identity service and `runner-controller` need care here.
- **Pin tools in the terminal image** (`bao`, `sops`, `gitleaks`) and sha256-verify them per architecture.
- **"Dojo" branding for anything we build.** Naming Azure Key Vault on the comparison slide is factual comparison, not
  branding.

### 8.1 Workshop extensions mechanism (engine, option B; a first sketch)

**Goal:** a workshop pack adds landing cards, `/admin` tabs and gated routes **declaratively**, and the engine stays
workshop-agnostic.

- **Declared in the pack.** A file such as `workshops/<name>/extensions.json` (or `workshop.env` keys) lists:
  - **cards:** title, link, icon; shown to students
  - **admin tabs:** title and iframe source
  - **routes:** path prefixes, upstream `service:port`, and the **gate** to apply
- **Gates are fixed templates** that the engine owns, so a pack **cannot inject raw Caddy config**. For example:
  - `shared` (the normal login gate)
  - `student-identity` (adds `X-Auth-User` + `X-Gateway-Token`, like `/cloud`)
  - `facilitator-only`
- **Checked at start-up.** The engine rejects paths that collide with its own (`/admin`, `/git`, `/ide`, `/term`,
  `/slides`, `/demo`, `/cloud`, `/watch`, ...) and upstreams that aren't services in the stack.
- **Rendered to config.** `run.sh` turns the file into a Caddy snippet that the base Caddyfile imports, plus
  config that `allocator` reads for the cards and tabs.
- **Migration (S17):** once the mechanism is proven, move `DEMO_APP_ENABLED` (cert-autorenewal) and `CLOUD_ENABLED`
  (tofu-basics) onto it and delete the flags. Re-test each workshop on the real stack; `git-fundamentals` and
  `dns-as-code` just need to confirm nothing changed.
- **Module-ready format:** the same file format must work in a module folder as well as a workshop folder, so the
  modules idea in §13 needs no redesign.
- **Rules:** still ask before editing `engine/` files. The facilitator rule becomes part of the mechanism: a declared
  student card with no matching admin tab is a start-up warning.

## 9. Talk slide: OpenBao ↔ Azure Key Vault

| OpenBao | Azure Key Vault / Azure |
|---|---|
| Namespace | A separate Key Vault per team/app/environment |
| KV v2 secret, versions | Key Vault secret, versions |
| Delete / undelete / destroy | Soft delete / recover / purge |
| ACL policy (path + capabilities) | Azure RBAC roles (Secrets User, Secrets Officer) or access policies |
| OIDC auth method | Entra ID sign-in |
| JWT auth for CI jobs | Workload identity federation (GitHub/Azure DevOps federated credentials) |
| JWT auth for the platform, `app-host` | Managed identity |
| OpenBao Agent writing files | Key Vault references in App Service, CSI Secrets Store driver in AKS |
| Transit engine | Key Vault keys (encrypt / decrypt / wrap) |
| PKI engine | Key Vault certificates |
| Dynamic database credentials | Passwordless: Entra ID authentication to Azure SQL / Postgres |
| Audit device | Diagnostic settings to Log Analytics |
| Seal / auto-unseal | Managed by Azure (HSM-backed) |
| Single-use CI runners from a controller | GitHub Actions Runner Controller, Azure DevOps scale-set agents |

## 10. Things to verify first (P0 spike, real stack)

1. The OpenBao version that has **namespaces**, and its image digest per architecture.
2. **The UI through Caddy at `/ui/` and `/v1/`** behind our login gate, including the OIDC redirect back to
   `/ui/...`, and whether it can be framed in `/admin`.
3. **Forgejo as the OIDC provider** for the OpenBao UI login.
4. **Forgejo 16 Actions OIDC** job tokens: the claims, and whether OpenBao JWT auth accepts them.
5. **Runners:**
   - does `forgejo-runner:13` have a one-job / ephemeral mode?
   - does the Forgejo API report waiting jobs and runner state?
   - how long does a runner take to start?
   - how much memory does one use while running a job?
   - process pool (§6.2 A): can other users' processes be hidden in an unprivileged container, and do several
     runners (one per Linux user) work side by side?
6. `sops` with transit against OpenBao.

## 11. Phases and task list (ask the user before moving between phases)


- **P0 spike**: §10 on the real stack; write down the findings.
- **P0.5 engine extensions** (§8.1): build and test the mechanism with the Vault card, routes and tab; leave the
  existing flags alone.
- **P1 core**: OpenBao + setup + SSO + terminal tools + labs 0-3.
- **P2 code and git**: labs 4-6.
- **P3 pipelines**: `runner-pool`, `runner-controller`, the Runners panel (manual − / + first, then autoscale) +
  labs 7-8.
- **P4 deployments**: `app-host`, Postgres, labs 9-11.
- **P5 facilitator, talk, tests**: the remaining `/admin` pieces, slides (with §9), `e2e.sh`, demo bots, sizing docs,
  a run on an Azure VM.
- **P6 migrate every workshop to extensions** (S17): cert-autorenewal and tofu-basics off their flags, all four
  re-tested, flags removed, `workshops/README.md` and `engine/README.md` updated. (Could run right after P0.5 instead
  if it proves stable early; ask then.)

### P0 — Spike (§10 on the real stack; findings go into §10 and §14)

Spike code lives under `workshops/vault-fundamentals/spike/` (throwaway; may be
deleted or folded into P1). No `engine/` edits without asking the user first.

- [x] **T0.1** *(2026-09-23)* Branch `feat/vault-fundamentals` from `main`; move the plan to
      `workshops/vault-fundamentals/PLAN.md`; add resume section, task list and session log;
      point `CLAUDE.md` and the root README at it.
      *Verify:* `git log --oneline -1 -- workshops/vault-fundamentals/PLAN.md`.
- [ ] **T0.2** Skeleton: `workshop.env` (no labs yet) and a spike compose overlay that adds an
      OpenBao container on `workshop_lab` (own `image:` tag for the terminal, per the overlay rules).
      *Verify:* `./run.sh list` shows the workshop; `./run.sh vault-fundamentals` starts and
      `bao status` answers from the student terminal (tools may be a temporary download on the host
      side for the spike).
- [ ] **T0.3** (§10.1) Pick the OpenBao release with **namespaces**; record version and image
      digests for amd64 and arm64 in §15. Also pin `bao`, `sops`, `gitleaks` binaries + sha256.
      *Verify:* digests match the registry; `bao namespace create` works on the spike server.
- [ ] **T0.4** (§10.2) OpenBao UI through Caddy at `/ui/` and `/v1/` behind the login gate, and
      framed in `/admin`. **Needs a gateway change: ask the user whether to do it as an uncommitted
      local edit or wait for P0.5.** *Verify:* UI loads and works through the gateway URL and inside
      an `/admin` iframe.
- [ ] **T0.5** (§10.3) Forgejo as the OIDC provider for the OpenBao UI login, including the redirect
      back to `/ui/...`. *Verify:* a student logs in to the UI with their Forgejo account and lands in
      the right identity/policy.
- [ ] **T0.6** (§10.4) Forgejo Actions OIDC job tokens: record the claims; configure OpenBao JWT auth
      to accept them and bind a role to repo/branch. *Verify:* a workflow run reads a secret with no
      stored credential; a run from another repo is refused.
- [ ] **T0.7** (§10.5 a-d) Runners: one-job/ephemeral mode in `forgejo-runner:13`; Forgejo API for
      waiting jobs and runner state; start-up time; memory while running a job.
      *Verify:* numbers recorded in §10/§15; a runner exits after exactly one job.
- [ ] **T0.8** (§10.5 e) Process-pool isolation (§6.2 A): hide other users' processes in an
      unprivileged container; several runners (one Linux user each) side by side. If it fails, record
      why and fall back to Docker-in-Docker (S16). *Verify:* a job cannot see or signal another job's
      processes or files.
- [ ] **T0.9** (§10.6) `sops` with OpenBao transit. *Verify:* encrypt a file, commit it, decrypt it
      with a token that has transit decrypt only; a token without it fails.
- [ ] **T0.10** Write up: findings into §10, plan changes into the relevant sections, new questions
      into §12, a P0 entry in §15. **Ask the user before starting P0.5.**

### P0.5 onwards

Each later phase gets its own task block here (IDs `TX.x` for P0.5 extensions, then `T1.x` … `T6.x`) when it starts,
written from the phase description above and the P0 findings.

## 12. Open questions for the user

None open right now (S16 and S17 settled the last two on 2026-09-23). P0 findings will raise new ones.

## 13. Later / follow-ups

- **Policy as code** (user wants it, deferred 2026-09-23): the namespace's policies in a git repo, changed by pull
  request and applied by CI, with drift shown when someone edits in the UI. Tool to decide then: OpenTofu with the
  `vault` provider (builds on tofu-basics) or `bao policy write` in CI. Could be an extra lab here or its own
  workshop.
- Could `cert-autorenewal` use OpenBao's PKI engine?
- **Modules: reusing one workshop's pieces in another** (e.g. Dojo Cloud from tofu-basics in vault-fundamentals).
  Extensions only cover the *front door* (cards, tabs, routes). A module also needs its **services** and its
  **terminal tools**, and today each workshop has exactly one compose overlay (`COMPOSE_OVERLAY`, `engine/run.sh`) and
  one terminal Dockerfile. Sketch: move shared pieces into `workshops/modules/<name>/` (compose fragment +
  extensions file + a tools fragment), a workshop lists `MODULES=dojo-cloud,openbao`, and `run.sh` adds one `-f` per
  module and merges their extensions. Terminal tools are the hard part: they're baked into one image per workshop,
  so modules need a shared way to contribute pinned tools. Build this only when a second workshop actually needs a
  module; the first real case would be the tofu tie-in.

## 14. Worth knowing & follow-ups

Surprises, gotchas and problems found in other workshops while working on this one. Nothing yet.

## 15. SESSION LOG (append-only, newest at the bottom)

### 2026-09-23 — Design session
- Design conversation with the user: decisions S1-S17 (§1), labs (§4), architecture (§5), runners (§6),
  extensions mechanism (§8.1), phases (§11). Written as `keyvault-workshop-plan.md` at the repo root
  (`27b5f59`). No code.

### 2026-09-23 — Set-up for P0
- tofu-basics merged to `main` (PR #1, merge commit `ebd0457`). Branch `feat/vault-fundamentals` created
  from it.
- Plan moved to `workshops/vault-fundamentals/PLAN.md`; added the header table, §0 HOW TO RESUME, the
  P0 task list (§11), §14 and this log. `CLAUDE.md` and the root README now point here.
- Next: T0.2, once the user says go for P0.

## Appendix: considered, not chosen

- **Emulating Azure Key Vault in Dojo Cloud's `cloud-api`** (the first version of this plan). Would have kept the
  `azurerm` resources but needed ARM and data-plane endpoints, a hostname per vault (wildcard DNS inside
  `workshop_lab`), a Key Vault token audience and a fake managed identity. That was a lot of emulation for a workshop
  about *using* a vault well. Replaced by S2/S3.
- **A separate port or subdomain for the OpenBao UI.** Not needed, because `/ui/` and `/v1/` are free on the gateway
  (§5.4); a separate port would also trip corporate firewalls.
- **A shared, long-lived runner running every student's jobs** (the `dns-as-code` pattern). One job's leftovers are
  visible to the next job, which is exactly what this workshop teaches against.
- **Reusing Dojo Cloud container groups as the deployment target.** It would tie this workshop to tofu-basics.
