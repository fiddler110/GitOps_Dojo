# PLAN — `tofu-basics`: OpenTofu on "Dojo Cloud" (Azure-inspired)

> **Purpose of this file:** the single source of truth for building this
> workshop. It is written so a brand-new session (human or Claude) can pick up
> exactly where the last one stopped. Keep it current — tick boxes and append
> to the Session Log (§16) as you go.

| | |
|---|---|
| Created | 2026-09-18 |
| Owner | scott |
| Workshop folder | `workshops/tofu-basics/` |
| Run command (when built) | `cd engine && ./run.sh tofu-basics` |
| Overall status | **M1 + M2 reached — Track A shippable; provider = real `azurerm`. Next: P3 control plane** |
| Working branch | `feat/tofu-basics` (planning commit is on `main`) |
| Last updated | 2026-09-18 (P0–P2 done) |

---

## 0. HOW TO RESUME (read this first)

1. Read this whole file once. It is long on purpose.
2. `git status` and `git log --oneline -20` — every completed task records its
   commit SHA next to its checkbox in §12. If a box is ticked but the SHA is
   missing from `git log`, treat the task as **not done**.
3. Check §4 (Decisions & Gates). Do not start a phase whose gate is still
   `PENDING`.
4. Find the first `[ ]` or `[~]` task in §12. Run that task's **Verify** line
   for the *previous* task first, to make sure the foundation still holds.
5. Work the task. When finished: tick the box, add the commit SHA, and append a
   dated entry to §16 (Session Log). If you learned something that changes the
   plan, edit the relevant section — do not just note it in the log.
6. If you are blocked, mark the task `[!]`, say why in §16, and move to the
   next unblocked task.

**Task markers:** `[ ]` todo · `[~]` in progress · `[x]` done (+ SHA) ·
`[!]` blocked · `[-]` dropped (say why).

**Prompt to paste into a fresh Claude Code session:**

```text
Read workshops/tofu-basics/PLAN.md fully. Follow its "HOW TO RESUME" section:
check git log against the ticked tasks, verify the last completed task still
works, then continue with the first unchecked task. Update PLAN.md (checkboxes,
commit SHAs, Session Log) as you go. Ask me before any decision marked PENDING
in section 4 that needs my input.
```

---

## 1. Requirements (what the user asked for)

Captured from the conversation on 2026-09-18 so they are never lost:

1. A **Terraform-style lab** inside the existing lab environment. Students get
   a terminal and written instructions.
2. It must **teach the basics**: how the documents/files are structured, and the
   `plan` → `apply` → `destroy` lifecycle. *Learning the basics is the primary
   goal.*
3. It should **deploy a hello-world container temporarily**, so learners *see*
   something real get created and removed.
4. Provide **both** an offline track (**Track A**, no container needed) and a
   real-deployment track (**Track B**). "Don't mind having A and B."
5. Use **OpenTofu** instead of Terraform, provided it's comparable.
6. **Alias:** typing `terraform` in a student terminal must run `tofu`.
7. Give it a **"real" cloud feel**, and the ideal is that it **feels like
   Azure** to the learners.
8. Fits the existing engine conventions (ephemeral, gateway-routed, no changes
   to the base engine beyond what is unavoidable and explicitly listed in §11).

**Non-goals** (explicitly out of scope unless promoted later):
real Azure access from the lab; remote state backends; multi-cloud;
Kubernetes; importing pre-existing infrastructure at scale; Microsoft logos,
trademarks, or copied portal assets (we use Azure *concepts and naming*, not
Microsoft branding — see §6).

**Audience:** engineers who did (or are doing) Git Fundamentals; comfortable
with a terminal and git; new to IaC. Target session **~2 hours** including
Track A (~35 min) and Track B (~60 min) plus slides.

---

## 2. Status dashboard

Update this table whenever a phase changes state.

| Phase | Title | Status | Milestone |
|---|---|---|---|
| P0 | Prep & repo hygiene | **done** | |
| P1 | Track A — offline sandbox + terminal image | **done** (`ef3e36a`) | **M1: Track A shippable ✅** |
| P2 | Provider-strategy spike (gate D1) | **done** | **M2: provider decision made ✅ (azurerm)** |
| P3 | Control plane ("cloud-api") + cloud host | not started | **M3: one student can deploy end-to-end** |
| P4 | Portal (Azure-inspired console) | not started | |
| P5 | Gateway / allocator integration | not started | |
| P6 | Lab content — Track B | not started | |
| P7 | Slides | not started | |
| P8 | Docs, registration, capacity, delivery | not started | |
| P9 | Validation (bots, load, dry-run) | not started | **M5: release-ready** |
| P10 | Optional stretch | not started | |

Milestone **M4** = 30-student load test passes (inside P9).

---

## 3. Facts: verified vs. assumed

Never build on an **assumed** item without first proving it (each has a task).

### Verified (checked in this repo / environment on 2026-09-18)

| Fact | Evidence |
|---|---|
| OpenTofu's registry serves `kreuzwerker/docker` (v4.6.0 listed) | `curl https://registry.opentofu.org/v1/providers/kreuzwerker/docker/versions` |
| **No `docker.sock` is mounted anywhere** in the stack | comment in `workshops/dns-as-code/compose/docker-compose.override.yml` |
| Terminal container is on the internal-only network `workshop_lab` → **no internet at lab time** | `engine/docker-compose.yml`, `engine/web-terminal/Dockerfile` comments |
| All student accounts **share one network namespace** (one container) → source IP cannot identify a student | comment on `cap_add: NET_ADMIN` in `engine/docker-compose.yml` |
| Base terminal image is Debian bookworm-slim, no Terraform/OpenTofu, no HCL editor extension | `engine/web-terminal/Dockerfile` |
| Tool downloads are **version-pinned and sha256-verified** per-arch (amd64/arm64) | every `wget` block in that Dockerfile; copy that pattern |
| Workshop terminal images extend the base: `FROM gitopsdojo/web-terminal:base`, and the override **must** set its own `image: gitopsdojo/web-terminal:<name>` tag | `workshops/README.md` step 4; `workshops/dns-as-code/compose/` |
| Compose paths in an overlay resolve relative to `engine/`, not the overlay file | `workshops/README.md`; header of `dns-as-code/compose/docker-compose.override.yml` |
| `./run.sh list` **skips** folders without a `workshop.env` → a folder holding only `PLAN.md` is harmless | `engine/run.sh` `list_workshops()` |
| Gateway is Caddy with path routing and `forward_auth` to the allocator. A workshop-specific route already has precedent: `/demo*` → `demo-app`, gated by `DEMO_APP_ENABLED` | `engine/gateway/Caddyfile:115-127`; `engine/allocator/server.py:76,402,871`; `engine/docker-compose.yml:229` |
| Slide decks are Marp with `assets/themes/presentation.css`; each workshop has `index.md`, `presentation.md`, `labs.md`, `cheat-sheet.md` | `workshops/dns-as-code/content/slides/presentation.md`, `workshops/cert-autorenewal/content/slides/` |
| Lab content layout: `content/{slides,lab,sample-repo}`; `lab/` is seeded to each student's `~/lab`, `sample-repo/` is seeded into Forgejo | `workshops/README.md` |
| `/home/scott/Development/GitOps_Dojo` has **~22 modified + 2 untracked files unrelated to this work** at planning time | `git status` snapshot |
| **Lab flow (T0.3):** `content/lab/` is copied into each student's `~/lab` (`cp -Rn`, README.md symlinked); students `git clone http://git-server:3000/<FORGEJO_ORG>/<FORGEJO_REPO>.git` (anonymous clone works) and **push with student account + password `student123`** (VS Code popup / ttyd prompt). `sample-repo/` is what bootstrap seeds into Forgejo | live stack test, 2026-09-18 |
| **Base `HEALTHCHECK` sends `X-Control-Token: ${CONTROL_TOKEN}`**; workspace-control returns 403 otherwise. The restated healthchecks in `dns-as-code` and `cert-autorenewal` Dockerfiles still lack the header → those workshops' terminals report *unhealthy* (pre-existing, not fixed here) | `engine/web-terminal/Dockerfile:259`; observed |
| The stack builds/runs with **podman + podman-compose** here (no docker). `./run.sh <w> --test 2` starts 2 bots; a re-run does **not** recreate a running container after an image rebuild → `./run.sh stop` first | run.sh; observed |
| Marp presentation container **exits 0 with a help dump if `content/slides/` is empty** → a workshop needs at least one slide file | observed |
| `azurerm` provider docs list `metadata_host` (`ARM_METADATA_HOSTNAME`), `client_secret` auth, `environment`, `resource_provider_registrations` — the knobs the T2 design needs. Registry latest: `azurerm` 5.6.0, `azapi` 2.12.0 | provider docs (main branch) |
| `infra/corp-dev/gdojo-cc/` (referenced by `workshops/README.md` for Azure delivery) **does not exist in this checkout** | `ls infra` failed |

### Assumed — must be proven (task in brackets)

| Assumption | Proven by |
|---|---|
| ✅ *(proven T1.1)* OpenTofu keeps Terraform's on-disk names (`.terraform/`, `.terraform.lock.hcl`, `terraform.tfstate`, `*.tf`, `*.tfvars`) so the alias is seamless | T1.1 |
| ✅ *(proven T1.1: sh, zsh, tmux; ttyd/code-server share zsh)* A `terraform → tofu` **symlink in `/usr/local/bin`** works in zsh, tmux, ttyd and the code-server terminal | T1.1 |
| ✅ *(proven T1.2: exported from `/etc/zsh/zshenv`; survives `su -`)* `TF_CLI_CONFIG_FILE` / env vars set for the terminal reach student shells after `su` | T1.2 (fallback: `/etc/zsh/zshenv` + `/etc/profile.d`) |
| ✅ *(proven T1.2 with `--network none` and in the live stack)* Offline `tofu init` works from a **filesystem mirror** | T1.2 (`docker run --network none`) |
| ✅ *(installed; visual check pending P9)* A HCL syntax-highlighting extension is available on Open VSX and works offline with its language server disabled (`hashicorp.terraform` or `opentofu.vscode-opentofu`) | T1.3 |
| ✅ *(PROVEN T2.2: azurerm 5.6.0, full cycle + drift; see §5.5)* **`azurerm` (or `azapi`) can run init/plan/apply/destroy against a custom ARM-compatible endpoint** via `metadata_host` (used upstream for Azure Stack/sovereign clouds) with a mocked token endpoint | **T2.2 — the big one** |
| ✅ *(recorded T2.2, §5.5)* `azurerm_container_group` change behaviour (which attribute edits are in-place `~` vs replace `-/+`) matches what the lab teaches | T2.2 (record real plan output; rewrite lab text to match) |
| ✅ *(dind runs privileged under rootless podman; preload + build + run + published-port reachability proven on a plain bridge. **`internal: true` / no-internet still to confirm in P3**)* `docker:dind` can run privileged on an `internal: true` network with images preloaded via `docker load` | T2.1 |
| ✅ *(proven T2.2)* Go providers trust a private CA supplied via `SSL_CERT_FILE` / system store | T2.2 |
| ✅ *(measured, §5.5)* Size/time cost of mirroring `azurerm` into the image is acceptable (it is a very large provider) | T1.2/T2.2 — measure and record |
| LocalStack/other emulators: **not used**; licensing changing and unverified | not planned |

---

## 4. Decisions & gates

| ID | Decision | Status | Notes |
|---|---|---|---|
| D0 | Use **OpenTofu**, expose as `terraform` too | ✅ DECIDED (user) | Symlink, not just a shell alias — works in scripts/tmux/ttyd/code-server, not only interactive zsh. Also add a zsh `alias` only if T1.1 shows the symlink misses a case. |
| D0b | Deliver **Track A + Track B** | ✅ DECIDED (user) | A = offline sandbox, B = "Dojo Cloud". A doubles as fallback if the cloud host misbehaves mid-session. |
| D0c | Cloud should feel like **Azure** | ✅ DECIDED (user) | Azure *concepts, naming, resource shapes, policy errors, portal layout* — no Microsoft logos/marks. Brand is "Dojo Cloud". |
| D1 | **Provider strategy for Track B** | ✅ DECIDED 2026-09-18 by spike P2: **T2 — real `azurerm` 5.6.0 → ARM facade** (azapi + docker fallback not needed) | Option **T2** (preferred): real `azurerm` (fallback `azapi`) → a small ARM-compatible facade. Option **T1** (fallback): `kreuzwerker/docker` → policy-filtering Docker API proxy with mTLS. See §5.4. |
| D2 | Cloud host isolation: privileged `docker:dind` on an isolated internal network, vs. alternative runtimes | ⏳ PENDING (default: privileged dind, isolated) | Sysbox/rootless are not assumed available. Compensating controls in §7. Revisit only if you object to a privileged sidecar. |
| D3 | Student identity to the cloud: (a) **broker with `SO_PEERCRED`** or (b) shared class secret + honour system | ⏳ PENDING (default **a**) | (a) proves *which Linux user* is calling; (b) is simpler but lets a student impersonate another. The repo's recent "Harden internal control-plane auth" commit suggests (a). |
| D4 | Add a `/cloud*` route + landing-page button to the **base** Caddyfile/allocator, gated by `CLOUD_ENABLED` | ⏳ PENDING (default yes) | Mirrors the existing `DEMO_APP_ENABLED` pattern exactly; additive and off by default. Only base-engine edit besides docs/capacity-calc. |
| D5 | Default region / subscription / naming values | ⏳ PENDING (defaults in §6) | Default region `uksouth`; change freely in `variables.tf`. |
| D6 | Per-student quota | ⏳ PENDING (default: 2 container groups, 0.25 vCPU, 128 MB each) | Sized in §14. |
| D7 | Should students see each other's deployed sites? | ✅ DEFAULT yes (read-only "Class view") | Any authenticated session may **browse** any site; only the owner can **change** anything. |

**Gate rule:** P3 cannot start until D1 is decided (P2 produces it). P3 has two
task lists (T2 path and T1 fallback path); only one is executed.

---

## 5. Architecture

### 5.1 Concept

```text
Student terminal (web-terminal container, tofu + provider mirror, NO internet)
      │  tofu init/plan/apply/destroy  (HTTPS, private CA, token from broker)
      ▼
┌───────────── cloud-api  ("Dojo Cloud" control plane) ─────────────┐
│  • metadata + token endpoints (Entra-ID-like)                     │
│  • ARM-style REST: subscriptions / resourceGroups / containerGroups│
│  • Policy engine ("Azure Policy"): region, tags, naming, images,   │
│    size caps, quotas  → ARM-shaped errors (RequestDisallowedBy…)   │
│  • Executor: turns an approved request into a FIXED, SAFE          │
│    `docker run` on the cloud host (student never speaks Docker)    │
│  • Activity log  • Portal (static SPA)  • Site ingress /cloud/site │
└───────────────┬───────────────────────────────┬────────────────────┘
      cloud_net │ (internal: true)              │ workshop_lab
                ▼                               ▼
      cloud-host (docker:dind,              gateway (Caddy) ⇄ browser
      privileged, preloaded image,          /cloud → portal, /cloud/site/<label>/ → site
      NO route to anything else)
```

### 5.2 Services (all added by the workshop's compose overlay — base engine untouched except D4)

| Service | Image / build | Networks | Purpose |
|---|---|---|---|
| `cloud-host` | build `compose/cloud-host/` (FROM `docker:dind`) | `cloud_net` only | Runs student containers. Preloads `dojo/hello:1.0`/`2.0` at start. No published ports. `mem_limit`, `pids_limit` set. **Not** on `workshop_lab`. |
| `cloud-api` | build `compose/cloud-api/` (Python, same style as `engine/allocator/server.py`) | `cloud_net` + `workshop_lab` | Control plane, policy, executor, portal, ingress. Only service that can talk to `cloud-host`. |
| `web-terminal` (override) | build `compose/terminal/` → `gitopsdojo/web-terminal:tofu-basics` | `workshop_lab` | Adds `tofu`, `terraform` symlink, provider mirror, HCL extension, broker, env glue. |

Network aliases on `cloud-api` (for TLS realism, requires private CA):
`management.dojo.cloud`, `login.dojo.cloud`, `portal.dojo.cloud`.

New named volumes (ephemeral, like everything else): `cloud_pki` (CA + certs,
written by cloud-api, mounted read-only into terminal), `cloud_secrets`
(signing key, root-0400).

### 5.3 Request flow — `tofu apply` (Track B, option T2)

1. Shell starts → `zshenv` runs `dojo-env` → broker (Unix socket in terminal)
   learns caller's uid via `SO_PEERCRED` → returns `ARM_*` variables
   (`ARM_TENANT_ID`, `ARM_SUBSCRIPTION_ID`, `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET`,
   `ARM_METADATA_HOSTNAME`, `SSL_CERT_FILE`, `TF_VAR_portal_base_url`).
2. `tofu init` → offline, from `/opt/tofu-providers` mirror.
3. `tofu plan/apply` → provider fetches metadata → obtains token → `PUT
   resourcegroups/…` → `PUT containerGroups/…` (long-running operation).
4. cloud-api authenticates (token ⇒ student), authorises (path subscription ==
   token subscription), runs policy, then the executor creates the container on
   `cloud-host` with a **fixed template** (no student-controlled Docker flags).
5. Provider polls → `Succeeded`. `output "url"` prints a `/cloud/site/<label>/`
   link. Portal shows the new resource within a few seconds.
6. `tofu destroy` → `DELETE` → container removed → portal reflects it.

### 5.4 The two provider options (decided at gate D1)

| | **T2 (preferred): real `azurerm` → ARM facade** | **T1 (fallback): `kreuzwerker/docker` → policy proxy** |
|---|---|---|
| Student writes | `azurerm_resource_group`, `azurerm_container_group` — recognisably Azure | `docker_network`, `docker_container` — generic |
| "Azure feel" | Highest | Medium (naming/tags/portal only) |
| Security | **Best** — student never sends Docker API; server-side template | Hard — must filter Docker create bodies (privileged, mounts, host net, caps, ports) |
| Identity | Client-credentials token from broker | Must use **mTLS client certs** (provider can't send custom headers) issued by broker |
| Build cost | Fake metadata+OAuth+ARM subset (~hundreds of lines) | Docker API reverse proxy + body rewriting |
| Risk | Provider may demand endpoints/JWT shape we can't cheaply fake → **spike first** | Fewer unknowns, more code |
| Mirror size | Large (azurerm) | Small |

**Rule:** spike T2 first (P2, time-boxed). If `azurerm` fails but `azapi` works,
use `azapi` for the ARM path. Only if both fail do we execute the T1 path.
Everything else in the plan (portal, quotas, lab flow, Track A) is the same.

### 5.5 P2 spike results (2026-09-18) — the facts the build depends on

**Outcome: real `azurerm` v5.6.0 runs init/plan/apply/destroy against our facade.**
Student HCL is genuine Azure HCL; only the environment differs.

*How the provider is pointed at Dojo Cloud (all via env vars, so `providers.tf`
is just `provider "azurerm" { features {} }`):*

```text
ARM_METADATA_HOSTNAME=<cloud-api host>     # provider does GET https://<host>/metadata/endpoints?api-version=2022-09-01
ARM_TENANT_ID / ARM_SUBSCRIPTION_ID / ARM_CLIENT_ID / ARM_CLIENT_SECRET
ARM_USE_CLI=false
ARM_RESOURCE_PROVIDER_REGISTRATIONS=none   # else it lists/registers providers
SSL_CERT_FILE=<private CA pem>             # facade must be HTTPS; Go trusts this
# do NOT set ARM_ENVIRONMENT (ignored when metadata host is set)
```

*Metadata document the provider requires* (miss any → hard error, see the three we hit):
`name`; `resourceManager`; `microsoftGraphResourceId`;
`authentication{loginEndpoint, audiences[], identityProvider:"AAD", tenant:"common"}`;
`suffixes{keyVaultDns, storage}` (+ optional others).
**Gotchas found the hard way:** (1) `tenant` MUST be the literal `"common"` and
`identityProvider` `"AAD"`, otherwise go-azure-sdk `IsAzureStack()` is true and
azurerm refuses with "does not support Azure Stack"; (2) `keyVaultDns` (and
`storage`) suffixes must exist or the provider fails building the Key Vault
authorizer ("endpoint KeyVault is not supported").

*Auth:* `POST {loginEndpoint}{tenant}/oauth2/v2.0/token` (form:
`grant_type=client_credentials&client_id&client_secret&scope=<aud>/.default`) —
the provider requests ~4 tokens (resource manager, storage, key vault, graph). It
does **not** verify the JWT signature; it only needs a well-formed access token
(we issue an unsigned-`alg:none` one with `tid/oid/appid/exp`). Real auth
decisions are ours to make from `client_id`/`client_secret` (P3).

*ARM surface actually used* (with `resource_provider_registrations=none`) — tiny:

| Call | API version |
|---|---|
| `GET https://<host>/metadata/endpoints` | `2022-09-01` |
| `POST /<tenant>/oauth2/v2.0/token` | — |
| `PUT/GET/DELETE /subscriptions/<s>/resourceGroups/<rg>` | `2023-07-01` |
| `PUT/GET/DELETE …/resourceGroups/<rg>/providers/Microsoft.ContainerInstance/containerGroups/<cg>` | `2025-09-01` |

No `GET /subscriptions/<s>`, no provider listing, no locks calls were made.

*Long-running operations:* the facade answered `201`/`200` with
`provisioningState: Succeeded` and no async headers; the provider then waited a
poll tick — **RG create ≈20 s, container group ≈10 s, deletes similar** — real
`plan` refreshes are fast. Acceptable (feels like a cloud), but tune in P3 (send
`Azure-AsyncOperation`/`Retry-After: 1`, or accept) so Lab timings are sensible.

*Plan behaviour of `azurerm_container_group` (recorded from real plans):*

| Edit | Plan result |
|---|---|
| tag on the container group | **`~` update in place** |
| `environment_variables` value | **`-/+` replace** (`# forces replacement`) |
| container `image` | **`-/+` replace** |
| container `cpu` | **`-/+` replace** |
| `dns_name_label` | **`-/+` replace** |

So Lab 8 works as designed: tag ⇒ in-place, env/image ⇒ replace. An unchanged
config plans **"No changes"** against the facade (so the facade's GET response
shape is sufficient — keep echoing the request back plus computed fields:
`id/name/type`, `properties.provisioningState`, `properties.ipAddress{ip,fqdn}`).

*Drift (Lab 7):* deleting the container group out-of-band, then `plan` →
`+ create` (1 to add). Works.

*Mirror / capacity:* `azurerm` 5.6.0 linux_amd64 is **56 MB zipped / 218 MB
unpacked**. **A packed (zip) mirror makes every `tofu init` copy 218 MB into the
student's folder; an UNPACKED mirror (extract the zips into
`<host>/<ns>/<type>/<ver>/<os_arch>/`) makes `init` create a *symlink* — 0 bytes
per student.** ⇒ the terminal image must ship the mirror **unpacked** (also switch
random/local for consistency) and the lock file must carry `h1:` hashes. Image
grows ≈ +220 MB for azurerm (on top of the +190 MB already). *(Not yet verified
that a student's `su`-owned working dir can follow the symlink — it can: it is a
plain read of a world-readable dir.)*

*Cloud host (T2.1):* `docker:dind` runs `--privileged` under rootless podman
(v29.8.1, overlayfs). `docker load` of a preloaded `nginx:alpine`, `docker
build` of `dojo/hello` from it, `docker run -p 20001:80` all work with no
internet needed. The site is reachable from a peer container on the same
network and **not** from the host. Design consequences: cloud-api reaches
sites via `cloud-host:<allocated port>` and reverse-proxies them (students never
get a route to `cloud-host`); allocate host ports from a range (e.g.
20000–20999). Prefer a **shared unix socket volume** between `cloud-host` and
`cloud-api` over `tcp://…:2375` (the dind default listens **unauthenticated** on
TCP 2375 — do not enable that). Container run command pattern:
`docker run -d --name <sub>-<rg>-<cg> -p <port>:80 -e MESSAGE=… -e OWNER=… <allowed image>`
with the hello image's entrypoint writing `index.html` from those env vars.

*Spike harness (recreate if needed):* scratchpad `spike/` = private CA + server
cert (SAN `dojo-cloud`), `podman network create spike-net`, facade container
(`python:3.12-alpine` running `compose/cloud-api/arm_facade.py` with
`CLOUD_TLS_CERT/KEY`, alias `dojo-cloud`), and the tofu image run with
`SSL_CERT_FILE`, the `ARM_*` vars above, `TF_CLI_CONFIG_FILE=` (empty, so
azurerm downloads directly since it isn't in the mirror yet).

---

## 6. Making it feel like Azure

**Principle:** mirror Azure's *mental model and vocabulary* so anything a
learner later does in real Azure feels familiar. Do **not** copy Microsoft
logos, icons, fonts (Segoe UI), or portal artwork; use a neutral system font and
our own "Dojo Cloud" mark. State in the portal footer: *"Azure-inspired training
environment — not affiliated with Microsoft."*

### 6.1 Concept mapping

| Azure concept | Dojo Cloud implementation |
|---|---|
| Tenant | one fixed tenant GUID for the class |
| Subscription | one per student, GUID derived deterministically from username (`uuid5`) — isolation boundary |
| Resource group | first-class resource in ARM facade; portal blade; label `dojo.rg=<name>` on containers |
| Region / location | label + policy: allowed `uksouth`, `ukwest`, `westeurope`, `eastus` (others → policy denial) |
| Azure Container Instances (`containerGroups`) | container on `cloud-host`, shaped as an ACI container group |
| Resource ID | `/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.ContainerInstance/containerGroups/<name>` shown everywhere |
| Tags | container labels; **required tags** policy (`owner`, `env`) |
| Azure Policy | policy engine → `RequestDisallowedByPolicy` errors students must read and fix |
| Quotas | per-subscription limits → `QuotaExceeded` |
| Activity log | portal blade of create/update/delete events with caller & status |
| Service principal env vars | `ARM_CLIENT_ID/SECRET/TENANT_ID/SUBSCRIPTION_ID` — standard names |
| ACI public FQDN | `<dns_name_label>.<region>.dojo-cloud.test` in provider output; **clickable** link is `/cloud/site/<label>/` (no wildcard DNS available) |
| `az` CLI | optional `dojo` CLI (P10) with `login`, `group list`, `container list/show/logs` |
| CAF naming | starter code uses `rg-<workload>-<env>-<region>`, `ci-<workload>-<env>` and a small `locals` naming block |

### 6.2 Portal (P4) — "Dojo Portal"

Left nav: **Home · Resource groups · All resources · Container instances ·
Activity log · Class view (read-only, everyone's sites)**. Blades: resource
group → resource list; container instance → overview (status, FQDN, IP, region,
tags, size, image), **JSON view** (the ARM representation), **Browse** link,
live log tail. Auto-refresh (polling every ~3 s). Owner-only **Delete** button
and tag editor — *deliberately present*, because clicking in the portal and then
running `tofu plan` is the best possible **drift** demonstration (Lab 7).
Facilitator-only: whole-class view, **Purge subscription** (rescues students
who deleted their `terraform.tfstate`), toggle "portal write actions".

### 6.3 Policy catalogue (each becomes a teaching moment)

| Policy | Error the student sees | Lesson |
|---|---|---|
| Required tags `owner`, `env` | `RequestDisallowedByPolicy … missing tag 'owner'` | tags/variables/locals |
| Allowed regions | `RequestDisallowedByPolicy … location 'mars'` | variables & validation |
| Allowed images (`dojo/hello:1.0`, `2.0`) | `InvalidImage` | pinning versions |
| Max size (0.25 vCPU / 128 MB) | `InvalidResourceRequest` | resource sizing |
| Naming (`rg-<studentNN>-…`) | `InvalidResourceGroupName` | naming conventions |
| Quota (2 container groups / subscription) | `QuotaExceeded` | `count`/`for_each` limits, cleanup |

---

## 7. Identity & security model

**Threat model:** 30 curious, possibly mischievous students with a shell.
Cloud host is privileged, so it must be unreachable except through cloud-api.

| Control | Detail |
|---|---|
| Network isolation | `cloud-host` only on `cloud_net` (`internal: true`); not on `workshop_lab`; no ports published; no internet |
| No Docker API for students | (T2) students only speak ARM to cloud-api; executor uses a **fixed template** (image from allow-list, memory/CPU/pids caps, no privileged/mounts/host net/caps, read-only rootfs where possible, restart policy none) |
| Identity | D3(a): root-owned **broker** in terminal container; Unix socket; `SO_PEERCRED` → username → HMAC-signed short-lived token / client secret. Signing key is root-0400 in `cloud_secrets`, never in student-visible env |
| AuthZ | path `subscriptionId` must equal token subject's subscription; facilitator token can act on any |
| TLS | private CA generated by cloud-api at start → `cloud_pki` volume (ro in terminal); terminal trusts it via `SSL_CERT_FILE`/trust store |
| Gateway ingress | `/cloud*` gated by existing allocator `forward_auth` (same as `/demo`); site pages readable by any authenticated session |
| Resource caps | container-level caps + `cloud-host` `mem_limit`/`pids_limit` + per-subscription quota |
| Ephemerality | no volumes for `cloud-host`; `./run.sh stop` wipes all deployments |
| Inputs | strict allow-list validation of every field that reaches the executor; names constrained to `[a-z0-9-]{3,40}`; labels built server-side |
| Audit | every mutating call recorded in activity log with student, action, result |
| Known accepted risk | privileged `dind` (D2). Mitigated by isolation above; no student-controlled code path reaches the Docker API |

---

## 8. Student environment (terminal image) — `compose/terminal/`

`FROM gitopsdojo/web-terminal:base` (never edit the base image).

| Item | Detail |
|---|---|
| `tofu` | pinned release, per-arch sha256, same pattern as dnscontrol Dockerfile. Record version + checksums in §16 (T0.4). |
| **Alias** | `ln -s /usr/local/bin/tofu /usr/local/bin/terraform` so `terraform plan` runs OpenTofu everywhere (scripts, tmux, ttyd, code-server). Note in lab: output says "OpenTofu"; that is expected. Add `alias terraform=tofu` to a system zsh file only if T1.1 proves needed. |
| Provider mirror | build runs `tofu providers mirror` → **then unpacks the zips into the *unpacked* layout** (`<host>/<ns>/<type>/<ver>/<os_arch>/`) at `/opt/tofu-providers`, so `tofu init` symlinks instead of copying 218 MB per student (§5.5). Providers: `hashicorp/local` 2.9.1, `hashicorp/random` 3.9.1, and (D1) `hashicorp/azurerm` 5.6.0. `terraform_data` is built in. **TODO (P3): switch the current packed mirror to unpacked and add azurerm.** |
| CLI config | `/etc/tofu/tofurc` with `provider_installation { filesystem_mirror { path = "/opt/tofu-providers" } direct { exclude = ["*/*"] } }`; exposed via `TF_CLI_CONFIG_FILE`. Root-owned, students cannot edit. |
| Env glue | `/etc/zsh/zshenv` (+ `/etc/profile.d`) runs `dojo-env` so every shell (incl. code-server terminal) gets `ARM_*`, `SSL_CERT_FILE`, `TF_VAR_portal_base_url`, `TF_IN_AUTOMATION` unset. |
| Broker | small root daemon started by a **wrapper entrypoint** *before* `exec`-ing the base `web-terminal-entrypoint` (base entrypoint ends in `exec workspace-control.py`, so it cannot be hooked afterwards). |
| CA trust | wrapper entrypoint waits for `cloud_pki`, appends CA to trust store. |
| Editor | HCL highlighting extension installed into `/opt/code-server-extensions` (same shared, read-only mechanism as base), language server **disabled** (no internet). Update `engine/web-terminal/vscode-extensions.md` note — or, better, document it in this workshop's README because base Dockerfile is untouched. |
| Healthcheck | restate the base HEALTHCHECK (`dns-as-code` Dockerfile does this so static scans pass). |

---

## 9. Lab design (learning path)

Working repo: students clone the seeded Forgejo repo (`content/sample-repo`,
"starter IaC") so the GitOps thread from earlier sessions continues (commit
their `.tf`, ignore state). *(T0.3 confirmed the flow — see §3: labs clone from Forgejo, push with the student account.)*

### Track A — "Sandbox" (offline, ~35 min, zero risk)

| Lab | Goal | Commands | Concepts |
|---|---|---|---|
| **Lab 0** Orientation | tour of the folder; `terraform` is `tofu` | `tofu version`, `ls -la` | what each file is |
| **Lab 1** First run | make random name + write a file | `tofu init`, `validate`, `plan`, `apply` | providers, resources, plan symbols `+ ~ - -/+`, approval prompt |
| **Lab 2** Change & repeat | edit a variable, re-plan | `plan`, `apply`, `output`, `show`, `state list` | variables, outputs, locals, state, idempotency |
| **Lab 3** Tear down | destroy | `destroy`, `plan -destroy` | lifecycle end, what's left behind (state file) |

Track A resources: `random_pet`, `local_file`, `terraform_data`. Also the
fallback if Track B is unavailable.

### Track B — "Dojo Cloud" (~60 min)

| Lab | Goal | Concepts / observation |
|---|---|---|
| **Lab 4** Meet the cloud | open Portal, log in (automatic), see empty subscription; `tofu init` with the cloud provider | providers & versions, lock file, "the cloud is just an API" |
| **Lab 5** Deploy hello | `azurerm_resource_group` + `azurerm_container_group` → `apply` → open the site → watch Portal | resource dependencies, implicit graph, outputs (`url`), state |
| **Lab 6** Break a policy on purpose | omit a required tag / choose bad region / oversize | reading errors, `variables` + `validation`, tags/locals |
| **Lab 7** Drift | delete the container **in the Portal**, then `plan` | drift detection, `plan` vs reality, `apply` reconciles; contrast click-ops vs IaC |
| **Lab 8** Change types | edit a tag (in-place `~`) vs change image tag / env (`-/+` replace *if azurerm behaves so — record real behaviour in T2.2*) | in-place vs replace, `-replace=`, `create_before_destroy` intro |
| **Lab 9** Scale it | `for_each` two instances → hit quota | `count`/`for_each`, quotas |
| **Lab 10** Clean up | `destroy`; verify empty Portal; check `terraform.tfstate` | destroy, verifying, state after destroy |
| *(stretch)* Lab 11 | refactor into a module | modules |
| *(stretch)* Lab 12 | `tofu import` an existing resource | import |

Each lab file: goal, why it matters, steps with **expected output**, a
"what just happened" explainer, a check-yourself question, and a troubleshooting
box. The `cheat-sheet.md` lists commands + plan symbols + file map.

### Starter repo layout (`content/sample-repo/`)

```text
README.md            what this is, how to start
.gitignore           .terraform/, *.tfstate*, crash logs   (teaches what NOT to commit)
versions.tf          required_providers + required_version   (teaches pinning)
providers.tf         provider "azurerm" { features {} … }
variables.tf         location, workload, environment, owner, message  (with validation)
locals.tf            naming + tags  (CAF-style names, required tags)
main.tf              resource group + container group
outputs.tf           resource_id, fqdn, url
terraform.tfvars     student-editable values
sandbox/             Track A files (random_pet, local_file, terraform_data)
```

Files are intentionally **split the way real repos split them** — the file
structure is a stated learning objective.

---

## 10. Slides (P7)

Marp, `presentation.md` + `index.md` + `labs.md` + `cheat-sheet.md`, styled with
`assets/themes/presentation.css` (copy frontmatter from
`workshops/dns-as-code/content/slides/presentation.md`). Outline:

1. Title / recap of Git Fundamentals
2. Why IaC (clicks vs code; repeatability; review in git)
3. OpenTofu vs Terraform — one slide, "same workflow, `terraform` works here too"
4. The 4 building blocks: provider · resource · variable · output (+ state)
5. File map (what each file is)
6. The lifecycle: `init → plan → apply → destroy` with plan-symbol legend
7. State — why it exists, why never hand-edit, why not in git
8. Track A demo
9. Dojo Cloud tour (Azure vocabulary → what students will see)
10. Drift & policy (foreshadow labs 6–7)
11. Recap, cheat sheet, next steps (real Azure, remote state, modules, CI)

---

## 11. Repo touchpoints (full list of files to create/edit)

**Create** (all under `workshops/tofu-basics/`):
`README.md`, `workshop.env`, `PLAN.md` (this), `content/slides/*`,
`content/lab/*`, `content/sample-repo/*`, `compose/docker-compose.override.yml`,
`compose/terminal/*` (Dockerfile, wrapper entrypoint, broker, dojo-env, zshenv,
tofurc), `compose/cloud-host/*` (Dockerfile, entrypoint, `images/hello/`),
`compose/cloud-api/*` (server, policy, executor, portal SPA, PKI helper),
`tests/*`.

**Edit (existing files):**

| File | Change | Why / risk |
|---|---|---|
| `workshops/README.md` | add table row | docs only |
| `engine/gateway/Caddyfile` | additive `@cloud path /cloud*` block mirroring `@demo` (D4) | only base edit that changes behaviour; inert unless cloud-api exists |
| `engine/allocator/server.py` | `CLOUD_ENABLED` flag, `tool=cloud` in `/auth-check`, landing button (mirror `DEMO_APP_ENABLED` at lines ~76, 402, 871) | additive, off by default |
| `engine/docker-compose.yml` | pass `CLOUD_ENABLED` env to allocator (mirror line 229) | additive |
| `engine/scripts/capacity-calc.sh` | account for cloud-host memory | docs/tooling |
| `infra/corp-dev/gdojo-cc/workshops/tofu-basics.tfvars` | only **if** `infra/` exists elsewhere | not in this checkout |

Nothing else in `engine/` changes. **Do not mix with the ~24 unrelated
in-flight changes** — see T0.1.

---

## 12. TASK LIST

Each task: what · files · **Verify** (how to prove it) · `[ ]` status.

### P0 — Prep & repo hygiene

- [x] **T0.1** *(done 2026-09-18: unrelated changes committed on `main` as `a24f08b`, plan as `b5bdb7a`, pushed; branch `feat/tofu-basics` created)* Decide what to do with the unrelated uncommitted changes (commit
      them separately or stash), then create branch `feat/tofu-basics`.
      *Verify:* `git status` clean apart from this workstream; `git branch`.
- [x] **T0.2** *(`ef3e36a`)* Skeleton: `workshop.env` (no overlay yet), empty `content/` tree,
      `README.md` stub. *Verify:* `cd engine && ./run.sh list` shows the workshop.
- [x] **T0.3** *(findings in §3/§9; done 2026-09-18)* Study `workshops/dns-as-code` and `cert-autorenewal`: how `lab/`
      vs `sample-repo/` are used, how `labs.md`/`index.md` link, how bots
      (`--test`, `engine/web-terminal/bot-runner.sh`) drive a workshop. Write
      findings into §3 and §9. *Verify:* §9 no longer says "T0.3 must confirm".
- [x] **T0.4** *(recorded in §16)* Choose and pin OpenTofu version; record version + amd64/arm64
      sha256 in §16. Also pin provider versions (`local`, `random`, and per D1).
      *Verify:* checksums recorded and match the release page.

### P1 — Track A (offline) + terminal image → **M1**

- [x] **T1.1** *(`ef3e36a`)* `compose/terminal/Dockerfile`: `FROM gitopsdojo/web-terminal:base`;
      install pinned `tofu`; `terraform` symlink; restate HEALTHCHECK.
      *Verify:* in the built image, `terraform version` prints "OpenTofu";
      works in `sh -c`, zsh, and inside tmux; proves §3 assumptions 1–2.
- [x] **T1.2** *(`ef3e36a`; image +190 MB over `:base` 692→882 MB)* Provider mirror + `tofurc` + env plumbing. *Verify:*
      `docker run --rm --network none gitopsdojo/web-terminal:tofu-basics …`
      (as a student user) `tofu init` succeeds offline in the sandbox. Confirm
      `TF_CLI_CONFIG_FILE` survives `su`; else use zshenv fallback. Record
      image size delta.
- [x] **T1.3** *(`ef3e36a`; installed + listed by code-server, LS default off. **Visual highlight check in a browser still to do at P9**)* HCL editor support (pinned `.vsix`, sha256, language server off).
      *Verify:* `.tf` file highlighted in code-server; no network errors in
      console beyond the known baseline.
- [x] **T1.4** *(`ef3e36a`; `:base` not clobbered)* `compose/docker-compose.override.yml` (web-terminal image tag
      `gitopsdojo/web-terminal:tofu-basics`, correct `engine/`-relative paths),
      set `COMPOSE_OVERLAY` in `workshop.env`. *Verify:* `./run.sh tofu-basics`
      starts; base `:base` tag not clobbered (`docker images`).
- [x] **T1.5** *(`ef3e36a`; verified as student01 in the live stack incl. clone + push)* Track A starter (`sandbox/`) + Labs 0–3 + cheat sheet (Track A
      part). *Verify:* a fresh student account completes Labs 0–3 with the
      exact commands and gets the documented output.
- [x] **T1.6** *(`ef3e36a`)* Add table row to `workshops/README.md`; commit. **M1 reached:**
      Track A runs end-to-end and could be delivered alone.

### P2 — Provider-strategy spike → **M2** (time-box: about half a day)

- [x] **T2.1** *(done 2026-09-18; see §5.5)* Minimal `cloud-host` (dind) on `cloud_net`: `docker load` the
      preloaded base image, build `dojo/hello:1.0` inside it, run one container
      manually. *Verify:* container serves a page reachable only from
      `cloud_net`; nothing reachable from terminal; no internet.
- [x] **T2.2** *(done; `compose/cloud-api/arm_facade.py` v0; see §5.5)* Minimal ARM facade (throwaway quality): metadata, token, resource
      group, container group (with LRO headers). Point `azurerm` at it from a
      student terminal; run init/plan/apply/destroy. *Record:* exact endpoints
      the provider needs, JWT claims it inspects, real plan output for tag edit
      vs env edit vs image edit, mirror size. *Verify:* full cycle succeeds and
      the container appears/disappears on `cloud-host`.
- [-] **T2.3** *(dropped: T2.2 succeeded, azapi not needed)* If T2.2 fails inside the time-box: repeat with `azapi`.
- [x] **T2.4** *(D1 set in §4; §5.5 records results)* Record the outcome and set **D1** (`azurerm` | `azapi` | `docker
      fallback`) in §4. Update §5.4/§8/§9 provider names. **M2 reached.**

### P3 — Control plane + cloud host → **M3**

*Execute exactly one path, per D1.*

**Path T2 (ARM facade)**
- [ ] **T3.1** PKI: CA + server cert generated at start into `cloud_pki`;
      terminal trust wiring. *Verify:* `curl https://management.dojo.cloud/metadata/endpoints…` from a student shell without `-k`.
- [ ] **T3.2** Identity: broker (SO_PEERCRED) + `dojo-env` + signing key in
      `cloud_secrets`; token endpoint; subscription derivation. *Verify:* two
      students get different subscriptions; student A's token is rejected on
      student B's subscription path (403); a student cannot read the signing key.
- [ ] **T3.3** ARM resources: subscriptions, resource groups, container groups
      (PUT/GET/DELETE/list, LRO, ARM-shaped errors). *Verify:* provider contract
      test from T2.2 still passes.
- [ ] **T3.4** Policy engine (§6.3 catalogue) with unit tests. *Verify:* each
      policy produces its documented error.
- [ ] **T3.5** Quotas + per-container caps. *Verify:* 3rd container group →
      `QuotaExceeded`.
- [ ] **T3.6** Executor: fixed-template `docker run` on `cloud-host`; deletion;
      status/instanceView; log fetch; startup reconcile. *Verify:* no request can
      make the executor pass an unlisted flag (fuzz test on inputs).
- [ ] **T3.7** Site ingress `/cloud/site/<label>/` → container port, reachable
      via gateway. *Verify:* browser shows student's message.
- [ ] **T3.8** Activity log store + API.
- [ ] **T3.9** `cloud-host` hardening: `mem_limit`, `pids_limit`, no published
      ports, internal net only. **M3 reached:** one real student completes
      init→apply→browse→destroy.

**Path T1 (fallback: Docker API policy proxy)** — only if D1 = docker fallback
- [ ] **T3-ALT.1** Identity via mTLS: broker issues per-student client certs;
      proxy maps cert CN → student.
- [ ] **T3-ALT.2** Docker API reverse proxy with body inspection/rewrite:
      deny privileged, mounts, host net/pid, cap_add, devices, unlisted images;
      force `--name` prefix, owner label, network per student, resource caps,
      external-port range per student; filter list/inspect to own resources.
- [ ] **T3-ALT.3** Quotas, activity log, site ingress (as T3.7–T3.8), and a
      replacement of `azurerm_*` starter code with `docker_*`.

### P4 — Portal

- [ ] **T4.1** SPA shell + nav + theme (neutral, Azure-inspired, light/dark,
      mobile-safe). *Verify:* renders through gateway at `/cloud/`.
- [ ] **T4.2** Blades: Home, Resource groups, All resources, Container
      instances, resource overview + JSON view + Browse + log tail.
- [ ] **T4.3** Activity log blade; Class view (read-only).
- [ ] **T4.4** Owner actions: Delete, tag edit (for drift lab). Facilitator:
      whole-class view, Purge subscription, write-actions toggle.
- [ ] **T4.5** Footer disclaimer; accessibility pass (keyboard, contrast).
      *Verify:* deploy from terminal → appears ≤ ~3 s; delete in portal →
      `tofu plan` shows drift.

### P5 — Gateway / allocator integration (D4)

- [ ] **T5.1** `CLOUD_ENABLED` in allocator (+ `tool=cloud` auth-check, landing
      button) and `engine/docker-compose.yml` env line, mirroring `DEMO_APP_*`.
- [ ] **T5.2** Caddyfile `@cloud path /cloud*` block with `forward_auth`.
- [ ] **T5.3** Overlay sets `CLOUD_ENABLED=1`. *Verify:* button appears only for
      this workshop; other workshops unchanged (`./run.sh git-fundamentals`
      regression check); unauthenticated request to `/cloud/site/…` is refused.

### P6 — Lab content (Track B)

- [ ] **T6.1** Starter repo (§9 layout) with working values.
- [ ] **T6.2** Labs 4–10, each verified verbatim on a real run; plan output in
      docs must be **pasted from real runs** (esp. Lab 8 in-place vs replace).
- [ ] **T6.3** Cheat sheet (Track B part), troubleshooting boxes (lost state →
      ask facilitator to Purge; policy errors; portal stale).
- [ ] **T6.4** Stretch labs 11–12 (optional).

### P7 — Slides

- [ ] **T7.1** `presentation.md` per §10 outline; render with the presentation
      service. *Verify:* visible at `/slides`, links from `index.md` work.
- [ ] **T7.2** `index.md`, `labs.md`, `cheat-sheet.md` slide/lab hubs.
- [ ] **T7.3** Speaker notes, timing marks.

### P8 — Docs, registration, capacity, delivery

- [ ] **T8.1** Workshop `README.md`: what it is, architecture, security notes,
      how to reset, how to add a policy/image, troubleshooting.
- [ ] **T8.2** `capacity-calc.sh` includes cloud-host; record sizing in §14.
- [ ] **T8.3** Facilitator guide (run-of-show, timings, common failures, how to
      Purge, fallback to Track A).
- [ ] **T8.4** If `infra/` exists: add `tofu-basics.tfvars`, bump VM size if
      needed. Otherwise note as not applicable.
- [ ] **T8.5** Update `engine/README.md` only if behaviour described there
      changed (CLOUD_ENABLED route).

### P9 — Validation → **M4, M5**

- [ ] **T9.1** Automated e2e script in `tests/`: for a student user run Track A
      and Track B commands, assert outputs, assert cleanup.
- [ ] **T9.2** Security checks: cross-tenant access denied; fuzz executor;
      student cannot reach `cloud-host`, cannot read signing key, cannot
      escalate through any documented endpoint.
- [ ] **T9.3** Load test with demo bots (`--test`): N students × full flow. **M4**
- [ ] **T9.4** Human dry-run with 3–5 people; collect confusion points; fix labs.
- [ ] **T9.5** Regression: other workshops still start (`./run.sh git-fundamentals`,
      `dns-as-code`, `cert-autorenewal`). **M5: release-ready**

### P10 — Optional stretch

- [ ] **T10.1** `dojo` CLI (`login`, `group list`, `container list/show/logs`) — the
      `az` experience.
- [ ] **T10.2** CI `plan` on pull request via Forgejo Actions (fits GitOps theme;
      needs runner network design like dns-as-code's `runner_net`).
- [ ] **T10.3** More Azure-shaped resources (virtual network, storage account
      emulation) — only if the ARM facade proved cheap to extend.
- [ ] **T10.4** Remote state backend simulation.

---

## 13. Test & validation plan (summary)

| Layer | What | Where |
|---|---|---|
| Unit | policy engine, name/label validation, subscription derivation | `tests/unit` |
| Contract | provider init/plan/apply/destroy against cloud-api (golden plan outputs) | `tests/contract` |
| Security | cross-tenant, unauthenticated, executor-flag fuzz, signing-key readability | `tests/security` |
| E2E | scripted student run of every lab command | `tests/e2e.sh` |
| Load | 30 accounts, bots, resource watch on cloud-host | P9 |
| Offline | `docker run --network none` `tofu init` for Track A | T1.2 |
| Regression | other workshops unaffected | T5.3, T9.5 |

---

## 14. Facilitator notes & capacity

- Start: `cd engine && ./run.sh tofu-basics`; stop/reset: `./run.sh stop`.
- **Capacity (initial guess — measure in T9.3):** hello containers ≈ 10–20 MB
  each idle; quota 2/student × 30 = 60 containers with 128 MB cap ⇒ worst-case
  7.7 GB, realistic ≪1 GB. Proposed `cloud-host` `mem_limit` 3 GB; cloud-api
  256 MB. Add both to `capacity-calc.sh`.
- Fallback: if cloud host/API misbehaves mid-session, students continue with
  Track A (already complete) or the facilitator restarts only `cloud-host`
  + `cloud-api` (state is intentionally ephemeral; students may need Purge).
- Students who delete `terraform.tfstate` orphan resources → facilitator
  **Purge subscription** in the Portal.

---

## 15. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `azurerm` won't talk to a fake ARM endpoint | Medium | High (changes architecture) | Spike first (P2); `azapi`; T1 fallback path designed |
| `azurerm` mirror bloats the image / build time | Medium | Medium | measure in T1.2; mirror only needed platforms; use build cache |
| Privileged `dind` is a host-escape vector | Low if isolated | High | D2 controls, fixed-template executor, no Docker API exposure |
| Plan behaviour in Lab 8 differs from text | Medium | Low | write from real output only (T2.2/T6.2) |
| `su` drops env → provider config missing | Medium | Medium | zshenv/profile.d fallback (T1.2) |
| TLS/CA wiring flaky offline | Medium | Medium | PKI on shared volume, healthcheck ordering (`depends_on: condition: service_healthy`) |
| Facade drifts from what provider version expects after a provider upgrade | Low | Medium | pin provider version; contract tests |
| Scope creep into a full Azure emulator | Medium | Medium | §1 non-goals; P10 is optional |
| Unrelated in-flight repo changes get mixed in | Medium | Medium | T0.1 branch discipline |
| `infra/` (Azure VM delivery) missing locally | Known | Low | T8.4 conditional |

---

## 16. SESSION LOG (append-only, newest at the bottom)

### 2026-09-18 — Planning session
- Explored repo: engine architecture, `dns-as-code` overlay pattern, terminal
  Dockerfile conventions, Caddy routing precedent (`/demo`), `run.sh list`
  behaviour.
- Verified OpenTofu registry serves `kreuzwerker/docker`.
- User decisions: OpenTofu; `terraform` alias; Track A + B; Azure feel.
- Recorded design (this file). **No code written. No git changes made besides
  creating this file.**
- Open items needing user input before/at P2–P3: D2 (privileged dind ok?), D3
  (broker vs shared secret), D4 (touch base Caddyfile/allocator?), D5/D6
  defaults.
- **Pinned versions / checksums (T0.4, recorded 2026-09-18):**
  - OpenTofu **1.12.6** — sha256 amd64 `50a6106fa4de523d09c87af85f3db1dd47535fc005727fdca6852146476b88ec`,
    arm64 `9bd0228a81bcd0c88f7045c74378f45a815779f19897191dff7d9efba9976b9e`
    (from the release's `tofu_1.12.6_SHA256SUMS`).
  - Providers (mirrored into the image): `hashicorp/random` **3.9.1**, `hashicorp/local` **2.9.1**.
    Registry latest seen for P2: `hashicorp/azurerm` 5.6.0, `Azure/azapi` 2.12.0.
  - OpenTofu VS Code extension **0.6.3** (Open VSX, `OpenTofu.vscode-opentofu`) — sha256
    linux-x64 `ed0cbd5b8869b7adcc5f1d8fcec5ce573b9e46f4e57ecc66c3d535763a3a85fd`,
    linux-arm64 `94755ee6cd3bd4e90c6c05768f952ed272152e4eb4f836d37d97a612a68045d2`.

### 2026-09-18 — Implementation: P0 + P1 (Track A) — M1
- User said "commit everything and push it, then start implementing the plan".
  Committed the unrelated engine work on `main` (`a24f08b`), the plan
  (`b5bdb7a`), pushed `main`, created `feat/tofu-basics`.
- **Decisions D2–D6:** the user green-lit implementation without answering the
  open questions, so the **defaults in §4 are being used** (privileged dind on an
  isolated net, SO_PEERCRED broker, additive `/cloud*` route, `uksouth`, quota
  2 × 0.25 vCPU/128 MB). They are *not* re-confirmed — flag them in the next
  hand-off so the user can veto. D4 is not exercised until P5.
- Built T0.2–T0.4 and T1.1–T1.6 (commit `ef3e36a`): terminal image with OpenTofu
  1.12.6, `terraform` symlink, offline mirror + `tofurc` via `/etc/zsh/zshenv`,
  OpenTofu VS Code extension (LS off), starter repo, Labs 0–3, cheat sheet.
- Verified: `terraform version` in sh/zsh/tmux; `--network none` init/apply as a
  student; full Track A run + clone + push as `student01` in the live stack;
  `:base` tag intact; terminal healthy after the healthcheck fix.
- Surprises: (1) stale restated HEALTHCHECKs in the other two workshops (see §3);
  (2) a shipped multi-platform `.terraform.lock.hcl` removes the "incomplete lock
  file" warning that mirror installs otherwise print; (3) editing `learner` gives
  a plan with both `~` (terraform_data) and `-/+` (local_file) — used in Lab 2;
  (4) Marp exits on empty slides dir → placeholder `index.md` added.
- Image size: `:tofu-basics` 882 MB vs `:base` 692 MB (+190 MB).
- **Next:** P2 provider-strategy spike (T2.1 cloud-host dind; T2.2 fake ARM
  facade vs `azurerm` 5.6.0). Slides (P7) still only a placeholder hub.

### 2026-09-18 — P2 provider spike → M2 (D1 = real `azurerm`)
- Wrote `compose/cloud-api/arm_facade.py` v0 (stdlib HTTPS ARM facade: metadata,
  OAuth token, resource groups, container groups, in-memory store, logs every
  request) and ran the real `azurerm` 5.6.0 from the tofu image against it.
- **Result:** init/plan/apply/drift/destroy all work; details, gotchas
  (`tenant:"common"`, `keyVaultDns` suffix), the tiny ARM surface, plan
  behaviour per edit type, mirror sizes, and dind findings are in **§5.5**.
- Decided D1 = T2/`azurerm`; dropped T2.3 (azapi) and the T1 docker-provider
  fallback (not needed). Track A remains the offline fallback for a live session.
- Key discovery for capacity: **unpacked** provider mirror ⇒ `init` symlinks
  (0 B/student) vs 218 MB/student packed. Must switch the image to unpacked in P3.
- Not yet proven (carry into P3): dind on an `internal: true` network with no
  internet; a real LRO/`Azure-AsyncOperation` implementation; broker/`SO_PEERCRED`
  identity (facade v0 accepts any client id).
- **Next:** P3 — real `cloud-api` (auth, subscriptions, policy, executor to
  `cloud-host`, activity log) + `cloud-host` service + broker in the terminal
  wrapper, wired into the compose overlay.

<!-- Append new entries below this line. Format:
### YYYY-MM-DD — short title
- what was done (task IDs), commits (SHAs), decisions, surprises, next step -->
