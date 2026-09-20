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
| Overall status | **M1 + M2 + M3 reached; P4 portal and P5 gateway route done (facilitator Class progress board built, live-tested). P6 Track B labs 4–10, cheat sheet and starter repo done and verified live through the API (`25a7176`); next: P7 slides (ask the user first)** |
| Working branch | `feat/tofu-basics` (planning commit is on `main`) |
| Last updated | 2026-09-20 (P0–P6 done; D2–D6 all decided) |

---

## 0. HOW TO RESUME (read this first)

1. Read this whole file once. It is long on purpose.
2. `git status` and `git log --oneline -20` — every completed task records its
   commit SHA next to its checkbox in §12. If a box is ticked but the SHA is
   missing from `git log`, treat the task as **not done**.
3. Check §4 (Decisions & Gates). Do not start a phase whose gate is still
   `PENDING`. Also read **§15a (Worth knowing & follow-ups)** — it lists
   unconfirmed decisions, behaviours that surprised us, and problems found in
   *other* workshops.
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
| P3 | Control plane ("cloud-api") + cloud host | **done** (`6301cc8`) | **M3: one student can deploy end-to-end ✅** |
| P4 | Portal (Azure-inspired console) | **done** (`49c168e`; through-the-gateway check done in P5) | |
| P5 | Gateway / allocator integration | **done** (`a2eb28f`; facilitator progress board `1b22631`) | |
| P6 | Lab content — Track B | **done** (`5d0ad28` + `25a7176`; T6.4 stretch labs optional; browser pass still owed) | |
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
| **No `docker.sock` is mounted into any student terminal.** (tofu-basics adds one Docker daemon, `cloud-host`'s own dind, reachable only by `cloud-api` over a unix socket on a shared volume; §7) | comment in `workshops/dns-as-code/compose/docker-compose.override.yml` |
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
| `infra/` (Azure-VM delivery) **does not exist in this checkout**, and the docs no longer reference it (root README cleanup `45afcb7`) | `ls infra` fails; `grep infra README.md workshops/README.md` |

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
| D2 | Cloud host isolation: privileged `docker:dind` on an isolated internal network, vs. alternative runtimes | ✅ **CONFIRMED (user, 2026-09-19):** privileged dind, isolated (see §7, §15a-A) | Sysbox/rootless are not assumed available. Compensating controls in §7. Revisit only if you object to a privileged sidecar. |
| D3 | Student identity to the cloud: (a) **broker with `SO_PEERCRED`** or (b) shared class secret + honour system | ✅ **CONFIRMED (user, 2026-09-19): (a) broker with `SO_PEERCRED`** (see §15a-A) | (a) proves *which Linux user* is calling; (b) is simpler but lets a student impersonate another. The repo's recent "Harden internal control-plane auth" commit suggests (a). |
| D4 | Add a `/cloud` + `/cloud/*` route and landing-page button to the **base** Caddyfile/allocator, gated by `CLOUD_ENABLED` | ✅ **DECIDED — user green-lit P5 (2026-09-19); built in P5** (`CLOUD_ENABLED`, `@cloud` route, landing card, facilitator Dojo Cloud tab) | Mirrors the existing `DEMO_APP_ENABLED` pattern exactly; additive and off by default. Only base-engine edit besides docs/capacity-calc. |
| D5 | Default region / subscription / naming values | ✅ **DECIDED (user, 2026-09-19: Canadian audience)** (`canadacentral`; `rg-`/`ci-` prefixes enforced by policy) | Default region `canadacentral`, the only other allowed one is `canadaeast`; change freely in `variables.tf`. |
| D6 | Per-student quota | ✅ **DECIDED (user delegated the sizing, 2026-09-19)** (2 container groups, 0.25 vCPU, 0.125 GB each; `cloud-host` `mem_limit` 3 GB) | 2 groups is dictated by Lab 9 (Lab 5 hello + a two-instance `for_each` = 3 → `QuotaExceeded`; a limit of 3 would break it). The per-container numbers are caps, not reservations; students cannot run their own code (fixed image allow-list), so real use is a few MB each. 60 containers ≈ well under 1 GB expected; **T9.3 measures it and may lower the 3 GB ceiling.** |
| D7 | Should students see each other's deployed sites? | ✅ DEFAULT yes (read-only "Class view") | Any authenticated session may **browse** any site; only the owner can **change** anything. |

**Gate rule:** P3 could not start until D1 was decided — done (D1 = `azurerm`, so the
T2 path of P3 was executed and the T1 fallback path is dropped). The user green-lit
implementation without answering D2–D6; they were **all confirmed or set on 2026-09-19** (table above, §15a-A).

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
(`python:3.12-alpine` running the v0 `arm_facade.py` from commit `ec2f664` — superseded by `compose/cloud-api/server.py` — with
`CLOUD_TLS_CERT/KEY`, alias `dojo-cloud`), and the tofu image run with
`SSL_CERT_FILE`, the `ARM_*` vars above, `TF_CLI_CONFIG_FILE=` (empty, so
azurerm downloads directly since it isn't in the mirror yet).

### 5.6 Portal API contract (P4 — the interface between `portal_api.py` and the SPA)

*Written 2026-09-19 at the start of P4 so the backend and the SPA can be built independently.
If you change either side, change this section.*

**Serving.** cloud-api serves the SPA (`compose/cloud-api/portal/`) at `/cloud/` (→ `index.html`) and
`/cloud/static/<file>` (fixed allow-list: `app.js`, `app.css`, `favicon.svg`; no path traversal). Static
files need no identity. Every portal HTML/static response carries
`Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'`,
`X-Content-Type-Options: nosniff`. **No inline scripts/styles, no external assets** (no CDN, no web fonts).
The JSON API lives under `/cloud/api/`. Student sites stay at `/cloud/site/<label>/` (unchanged, CSP `sandbox`).

**Trust model (important).** Students share a network with cloud-api and can `curl cloud-api:8080`
directly, so a bare `X-Auth-User` header is forgeable. The portal API therefore trusts identity **only** when
the request also carries `X-Gateway-Token` equal (constant-time compare) to the `GATEWAY_TOKEN` env var —
exactly the allocator's `gateway_authorized()` model (the P5 Caddy block sets both headers with `header_up`
so clients cannot; verified live, §15a-H). If `GATEWAY_TOKEN` is unset the API answers `503 PortalNotConfigured`; a missing/wrong token
answers `401 Unauthenticated`. `user = X-Auth-User`; it must be in the roster (`auth.roster`) or be the facilitator,
else `403`. Subscription = `auth.subscription_id(user)`. Facilitator = `FACILITATOR_USERNAME`.
Students authorise on **subscription ownership** (path `sub` must equal their own) — same rule as ARM.

**Errors:** `{"error": {"code": "...", "message": "..."}}` with the right HTTP status (ARM shape).
**All JSON. Every string field is student-controlled data → the SPA must render with `textContent`, never `innerHTML`.**

| Method + path | Who | Returns / does |
|---|---|---|
| `GET /cloud/api/me` | any | `{user, subscriptionId, isFacilitator, writeActions, quota:{containerGroups:{used,limit}}, publicBaseUrl}` |
| `GET /cloud/api/overview?scope=mine\|class` | any (`class` = every subscription, **summaries only**) | `{resourceGroups:[RG], containerGroups:[CG], generatedAt}` |
| `GET /cloud/api/containers/<sub>/<rg>/<name>` | owner / facilitator | `{summary: CG, arm: <the ARM JSON, i.e. App.cg_body>}` |
| `GET /cloud/api/containers/<sub>/<rg>/<name>/logs?tail=N` | owner / facilitator | `{logs: "<text>"}`; `tail` 1–500, default 200 |
| `GET /cloud/api/activity?scope=mine\|all&limit=N` | `mine`: any; `all`: facilitator | `{events:[Event]}` newest first; `limit` 1–500, default 200 |
| `DELETE /cloud/api/containers/<sub>/<rg>/<name>` | owner / facilitator | deletes the container group (logged as a portal action); `204`-like `{deleted:true}` |
| `PATCH /cloud/api/containers/<sub>/<rg>/<name>` body `{"tags":{…}}` | owner / facilitator | **replaces** the tag set, runs the same policy as ARM (required tags `owner`,`env`) → `RequestDisallowedByPolicy` on violation; returns `{summary: CG}` |
| `GET /cloud/api/admin/settings` | facilitator | `{writeActions: bool}` |
| `PUT /cloud/api/admin/settings` body `{"writeActions": bool}` | facilitator | sets it (kept in state; **default true**) |
| `POST /cloud/api/admin/purge` body `{"subscriptionId": "<sub>"}` | facilitator | removes every container group + resource group of that subscription (+ containers on cloud-host); `{removed:{containerGroups:n, resourceGroups:m}}` |

*Write actions off* (`writeActions=false`): `DELETE`/`PATCH` by a **student** → `403 PortalWriteActionsDisabled`;
the facilitator is unaffected. Read endpoints are unaffected. Resource-group deletion is **not** offered in the portal
(students use `tofu destroy`).

**Shapes**

```text
CG    = {id, name, resourceGroup, subscriptionId, owner, location, state:"Running"|"Terminated",
         fqdn, ip, image, cpu, memoryGb, tags:{}, dnsLabel, siteUrl:"/cloud/site/<label>/", isMine:bool}
RG    = {id, name, subscriptionId, owner, location, tags:{}, containerCount, isMine:bool}
Event = {time, subscription, caller, operation, resourceId, status, message}
```

`state` comes from ONE `docker ps`-style list per request (cached ~2 s), **not** one `inspect` per container, and Docker
is never called while holding the global state lock — the portal is polled every ~3 s by every student (T9.7).
Portal-initiated changes must appear in the activity log with operation text that says they came from the portal
(e.g. `Delete container group (portal)`), so the drift lab can point at them.

*As built (2026-09-19) — deviations from the table above:* `state` can also be `"Unknown"` (cloud-host could not be listed and nothing is cached; the SPA renders it neutral); purge adds `orphanedContainers` to its response only if a container removal failed; responses carry `Cache-Control`; changing the write-actions setting adds a "Change portal settings" activity entry. There is no dedicated resource-group endpoint — the RG blade filters `overview`. `/cloud` (no slash) is a `301` to `/cloud/` because `<base>` is blocked by the CSP.

*Verification without the gateway:* from any container on `workshop_lab`,
`curl -H 'X-Auth-User: student01' -H "X-Gateway-Token: $GATEWAY_TOKEN" http://cloud-api:8080/cloud/api/me`.
The gateway route (`/cloud` and `/cloud/*`, built in P5) is not needed for this check.

### 5.6a Class progress board (P5 addition — facilitator only)

Principle (repo `CLAUDE.md`): the facilitator has access to every part of an active workshop. Students see the
state of *their* deployment in the portal; the facilitator sees **everyone's, live, as they come up**, in the same
portal (also embedded as the "Dojo Cloud" tab of `/admin`, which opens `/cloud/#/progress`).

`GET /cloud/api/admin/progress` — facilitator only (same check as the other `admin/*` routes: 403 for students,
401/403 auth rules unchanged). Built from data the control plane already records (resource groups, container
groups, the activity log, plus a small per-subscription summary `State` keeps beside the capped log so a noisy
student cannot evict others' failures — §15a-H1); **no Docker call under `State.lock`**, container state comes from the same
cached `_running()` set as `overview`. Response:

```json
{ "generatedAt": "2026-09-19T12:00:00Z",
  "summary":  { "total": 30, "notStarted": 12, "inProgress": 3, "running": 14, "attention": 1 },
  "students": [ {
      "user": "student01", "subscriptionId": "…",
      "stage": "notStarted | inProgress | running | attention",
      "resourceGroups": 1,
      "containerGroups": [ { "name": "hello", "resourceGroup": "rg-x", "state": "Running|Terminated|Unknown", "siteUrl": "/cloud/site/<label>/" } ],
      "lastEvent": null,
      "failures": 0 } ] }
```
`lastEvent` is `null` or `{ "time", "operation", "status", "message" }` (message ≤ 200 chars) — the student's most
recent activity-log entry. `failures` = that student's `Failed` events in the last 15 minutes. `students` = every
roster user (students and demo bots) **except the facilitator**, in roster order. `stage`, first match wins:
1. `attention` — the student's most recent event has status `Failed`, **or** any of their container groups is `Terminated`;
2. `running` — at least one container group and all of them `Running`;
3. `inProgress` — otherwise, if they have any resource group, container group (e.g. `Unknown` state) or event
   (this is the "apply is part-way" state: the RG exists before the container does; also a drift-demo delete lands here);
4. `notStarted`.
`summary` counts the four stages; `total` = `len(students)`. Every string is student-controlled → SPA uses textContent only.

SPA (facilitator only; students never see the nav item, and `#/progress` shows the ordinary "not found/forbidden"
state for them): nav entry **Class progress** → `#/progress`. A summary strip ("14 of 30 running · 3 in progress ·
1 needs attention · 12 not started"), then one tile per student: name, stage badge (**text label, not colour alone**),
container list with state, "last: <operation> · <status> · <n>s ago" (relative time re-rendered on each 3 s poll),
failure count when > 0, and a link to that student's container/site where one exists. Sort control: roster order /
needs attention first / most recently active. A tile whose stage changed since the previous poll is briefly
highlighted (skipped under `prefers-reduced-motion`). Empty/loading/error states like the other views; polling
pauses when the tab is hidden, like the others.

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
| Region / location | label + policy: allowed `canadacentral`, `canadaeast` only (Canadian data residency; any other region → policy denial) |
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
| Provider mirror | build runs `tofu providers mirror` → **then unpacks the zips into the *unpacked* layout** (`<host>/<ns>/<type>/<ver>/<os_arch>/`) at `/opt/tofu-providers`, so `tofu init` symlinks instead of copying 218 MB per student (§5.5). Providers: `hashicorp/local` 2.9.1, `hashicorp/random` 3.9.1, and (D1) `hashicorp/azurerm` 5.6.0. `terraform_data` is built in. *(Done in P1/P3: unpacked layout, azurerm included; a fresh `tofu init` offline takes ≈3 s and leaves the lock file untouched, verified 2026-09-20.)* |
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
| `engine/gateway/Caddyfile` | additive `@cloud path /cloud /cloud/*` block (`forward_auth` `/auth-check?tool=cloud`, `copy_headers X-Cloud-User`, then `header_up` identity + gateway token) (D4, done `a2eb28f`) | only base edit that changes behaviour; the allocator answers 404 unless `CLOUD_ENABLED=1`, so other workshops never reach the upstream |
| `engine/allocator/server.py` | `CLOUD_ENABLED` flag, `tool=cloud` in `/auth-check` (returns `X-Cloud-User`), landing card, and the facilitator `/admin` **Dojo Cloud tab** (D4, done `a2eb28f`) | additive, off by default |
| `engine/docker-compose.yml` | pass `CLOUD_ENABLED` env to allocator (done `a2eb28f`; the overlay sets it to 1) | additive |
| `engine/scripts/capacity-calc.sh` | account for cloud-host memory (**not done yet**, T8.2) | docs/tooling |
| `engine/README.md` | document the `CLOUD_ENABLED` route (**not done yet**, T8.5; it does not mention it today) | docs only |
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
- [x] **T2.2** *(done; the throwaway `arm_facade.py` v0 is in commit `ec2f664` and was superseded by `server.py` in P3; see §5.5)* Minimal ARM facade (throwaway quality): metadata, token, resource
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
- [x] **T3.1** *(`6301cc8`; PKI: CA+server cert in cloud-api's private `/data/pki`, only the CA cert is shared via `cloud_pki`. Verified `curl --cacert` + provider trust; plain `curl` needs `CURL_CA_BUNDLE`, added to the broker and **verified live 2026-09-20** in Lab 4's `curl` step)* PKI: CA + server cert generated at start into `cloud_pki`;
      terminal trust wiring. *Verify:* `curl https://management.dojo.cloud/metadata/endpoints…` from a student shell without `-k`.
- [x] **T3.2** *(`6301cc8`; broker + `dojo-env` + HMAC secrets; verified: distinct subscriptions per student, cross-student write → `AuthorizationFailed` 403, signing key unreadable by students)* Identity: broker (SO_PEERCRED) + `dojo-env` + signing key in
      `cloud_secrets`; token endpoint; subscription derivation. *Verify:* two
      students get different subscriptions; student A's token is rejected on
      student B's subscription path (403); a student cannot read the signing key.
- [x] **T3.3** *(`6301cc8`; PUT/PATCH/GET/DELETE + lists; **PATCH is required for tag edits** — found by testing; LRO not implemented, provider's own poll ticks make apply ≈35 s)* ARM resources: subscriptions, resource groups, container groups
      (PUT/GET/DELETE/list, LRO, ARM-shaped errors). *Verify:* provider contract
      test from T2.2 still passes.
- [x] **T3.4** *(`6301cc8`; 19 unit tests + live checks of every policy error through the real provider)* Policy engine (§6.3 catalogue) with unit tests. *Verify:* each
      policy produces its documented error.
- [x] **T3.5** *(`6301cc8`; live: 3rd group → `QuotaExceeded`, 2 allowed)* Quotas + per-container caps. *Verify:* 3rd container group →
      `QuotaExceeded`.
- [x] **T3.6** *(`6301cc8`; fixed-template `build_create_request` tested for forbidden keys/clamping/allow-list; **a fuzz test over the raw HTTP body is still to do in P9**)* Executor: fixed-template `docker run` on `cloud-host`; deletion;
      status/instanceView; log fetch; startup reconcile. *Verify:* no request can
      make the executor pass an unlisted flag (fuzz test on inputs).
- [x] **T3.7** *(`6301cc8`; `/cloud/site/<label>/` proxy with CSP `sandbox`, verified from a student terminal on `cloud-api:8080`; gateway route done in P5 and checked live through the gateway)* Site ingress `/cloud/site/<label>/` → container port, reachable
      via gateway. *Verify:* browser shows student's message.
- [x] **T3.8** *(`6301cc8`; recorded in state; **read API arrives with the portal, P4**)* Activity log store + API.
- [x] **T3.9** *(`6301cc8`; cloud-host on `internal: true`, no host ports, unix socket only, mem/pids limits; verified no internet from host or container, not resolvable from students. **M3 reached.**)* `cloud-host` hardening: `mem_limit`, `pids_limit`, no published
      ports, internal net only. **M3 reached:** one real student completes
      init→apply→browse→destroy.

**Path T1 (fallback: Docker API policy proxy)** — **DROPPED: D1 = `azurerm`, so this path is not used** (kept only as a record)
- [-] **T3-ALT.1** *(dropped — D1 = azurerm)* Identity via mTLS: broker issues per-student client certs;
      proxy maps cert CN → student.
- [-] **T3-ALT.2** *(dropped — D1 = azurerm)* Docker API reverse proxy with body inspection/rewrite:
      deny privileged, mounts, host net/pid, cap_add, devices, unlisted images;
      force `--name` prefix, owner label, network per student, resource caps,
      external-port range per student; filter list/inspect to own resources.
- [-] **T3-ALT.3** *(dropped — D1 = azurerm)* Quotas, activity log, site ingress (as T3.7–T3.8), and a
      replacement of `azurerm_*` starter code with `docker_*`.

### P4 — Portal

- [x] **T4.1** *(`49c168e`; verified in real headless Chromium against the live stack; the through-the-gateway check was done in P5)* SPA shell + nav + theme (neutral, Azure-inspired, light/dark,
      mobile-safe). *Verify:* renders through gateway at `/cloud/`.
- [x] **T4.2** *(`49c168e`; Logs tab needed a hello-image fix to show anything)* Blades: Home, Resource groups, All resources, Container
      instances, resource overview + JSON view + Browse + log tail.
- [x] **T4.3** *(`49c168e`)* Activity log blade; Class view (read-only).
- [x] **T4.4** *(`49c168e`; write-actions toggle persists across a cloud-api restart)* Owner actions: Delete, tag edit (for drift lab). Facilitator:
      whole-class view, Purge subscription, write-actions toggle.
- [x] **T4.5** *(`49c168e`; keyboard/focus/contrast checked in the palette + headless browser — **no real screen-reader or Firefox/Safari pass**; drift demo verified end to end)* Footer disclaimer; accessibility pass (keyboard, contrast).
      *Verify:* deploy from terminal → appears ≤ ~3 s; delete in portal →
      `tofu plan` shows drift.

### P5 — Gateway / allocator integration (D4)

- [x] **T5.1** *(`a2eb28f`)* `CLOUD_ENABLED` in allocator (+ `tool=cloud` auth-check, landing
      button) and `engine/docker-compose.yml` env line, mirroring `DEMO_APP_*`. The allocator hands the resolved
      identity back as `X-Cloud-User` (a student's identity lives only in their `dojo_session` cookie).
- [x] **T5.2** *(`a2eb28f`)* Caddyfile `@cloud path /cloud /cloud/*` block with `forward_auth`, then `reverse_proxy
      cloud-api:8080` with `header_up X-Auth-User {http.request.header.X-Cloud-User}` + `X-Gateway-Token` +
      `-X-Cloud-User` (matcher is `/cloud` and `/cloud/*`, not `/cloud*`, so `/cloudy` is not caught).
- [x] **T5.3** *(`a2eb28f`; verified live through the real gateway: 10/10 checks)* Overlay sets `CLOUD_ENABLED=1`.
      Button appears only for this workshop; git-fundamentals and cert-autorenewal have no card and `/cloud/` → 404
      (never 502); forged `X-Auth-User`/`X-Cloud-User`/`X-Gateway-Token` are overwritten by Caddy (checked against an
      echo upstream); no session → 303, no auth → 401.
- [x] **T5.4** *(`a2eb28f`; live-tested)* **Facilitator "Dojo Cloud" tab** in `/admin` (iframe of `/cloud/#/progress`,
      only when `CLOUD_ENABLED=1`). Repo `CLAUDE.md` rule: the facilitator has access to every part of an active workshop.
- [x] **T5.5** *(`1b22631`; live-tested with real azurerm applies, a real browser and 30 rostered students)* **Class
      progress board** (§5.6a): `GET /cloud/api/admin/progress` + SPA `#/progress`, stages notStarted / inProgress /
      running / attention, failure message inline on attention tiles. `admin/progress` p50 3 ms / p95 6 ms with 10
      facilitator pollers; a real apply was seen moving `notStarted` → `inProgress` (+3.5 s) → `running` (+27 s).
- [x] **T5.6** *(`2e8e818`; offline tests only — 90 + 5 parity; live re-check is T5.7)* Fixed progress-board findings H1 (failure
      history evicted from the capped activity log: per-subscription summary in `State`), H2 (bot roster naming now
      unpadded like the engine, incl. the terminal broker), H3 (BrokenPipe noise), H4 (SIGTERM handler).
- [x] **T5.7** *(live-verified 2026-09-20 on a rebuilt stack; fix in `25a7176`)* `canadacentral` apply through real azurerm
      OK (34 s, site 200); `eastus` rejected with `RequestDisallowedByPolicy ... use one of: canadacentral, canadaeast`;
      `podman stop workshop_cloud_api` 3.0 s and quota survived the restart; bot roster (`testuser1`…) gets creds.
      The attention tile showed only the error *code*: fixed in `25a7176` to `code: message` (offline tests only;
      **re-check the tile text on the next live run**).

### P6 — Lab content (Track B)

> **[Historical — P6 is now verified; see the log entry below.]** State at 2026-09-20 before verification: A builder agent was cut off by a session rate limit part-way through P6, but had
> already written most of the content; the user committed it as-is in `5d0ad28` ("hit session limit, committing to
> save the work"). **None of it has been reviewed, and none of it has been run against a live stack.** The stack is
> fully stopped (all containers `Exited`; nothing is running). Treat everything below as *draft text*, not
> verified fact. Do not tick T6.x until the check named on that line has actually been done.
>
> What `5d0ad28` contains (all under `workshops/tofu-basics/content/`):
> - `sample-repo/`: `versions.tf`, `providers.tf`, `variables.tf`, `locals.tf`, `main.tf`, `outputs.tf`,
>   `terraform.tfvars`, `.terraform.lock.hcl` (azurerm 5.6.0, many `h1:` hashes) and an updated `README.md`.
> - `lab/lab4.md` … `lab/lab10.md` (Meet Dojo Cloud, Deploy hello, Break a policy, Drift, Change types, Scale it,
>   Clean up), a Track B section in `lab/cheat-sheet.md`, and small edits to `lab/README.md`, `lab0.md`, `lab3.md`.
>
> **Order of work when resuming (Monday):**
> 1. Read this file, `git log` (expect `5d0ad28` on top of `3a71f8b`), `git status` (expect clean).
> 2. `cd engine && ./run.sh tofu-basics --test` (rebuilds; ~minutes). Confirm 8 containers healthy.
> 3. **T5.7 first** (below): `canadacentral` apply through real azurerm, `eastus` rejected, an attention tile shows a
>    real policy message, `podman stop workshop_cloud_api` is quick (< ~5 s), a bot roster (`testuser1`…) works.
> 4. Review the drafted labs against the real system, one lab at a time, from a fresh terminal as `student01`:
>    run every command and fix the text to match the real output. Things to check specifically:
>    - the lock file: `tofu init` must succeed **offline** in a student terminal and not rewrite
>      `.terraform.lock.hcl` (hashes must match the offline provider mirror; if not, regenerate with
>      `tofu providers lock` against the mirror and commit the new file);
>    - all region values are `canadacentral` / `canadaeast` (nothing left as `uksouth`/`eastus`, except deliberately as
>      the "bad region" in Lab 6);
>    - Lab 6 error text (missing `owner` tag → `RequestDisallowedByPolicy`; bad region; quota) is pasted from real output;
>    - Lab 8 in-place (`~`) vs replace (`-/+`) plan output is pasted from a real run (§15a and T2.2 have the expected
>      behaviour: tag ⇒ in-place, env/image ⇒ replace);
>    - Lab 9: two-instance `for_each` on top of Lab 5's hello = 3 groups → `QuotaExceeded` (D6 limit is 2);
>    - Lab 7 drift demo: portal delete → `plan` shows `+ create`;
>    - Lab 10 leaves the portal empty; the cheat sheet's commands all exist.
> 5. Only then tick T6.1–T6.3 with the fixing commit's SHA and add a session-log entry.
> 6. Ask the user before moving to P7 (phase gate).

- [x] **T6.1** *(`5d0ad28`; verified live 2026-09-20, no change needed)* Starter repo (§9 layout) with working values.
      *Verify:* fresh `student01` terminal: `cd` into the seeded repo, `tofu init` works offline with no lock rewrite,
      `tofu validate` passes, `tofu plan` proposes the expected 2–3 resources.
- [x] **T6.2** *(`25a7176`; every command run as student01 through real azurerm; pasted output is real)* Labs 4–10, each verified verbatim on a real run; plan output in
      docs must be **pasted from real runs** (esp. Lab 8 in-place vs replace).
- [x] **T6.3** *(`25a7176`; commands and troubleshooting boxes reproduced live)* Cheat sheet (Track B part), troubleshooting boxes (lost state →
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
- [-] **T8.4** *(not applicable: `infra/` is absent and the docs no longer reference Azure-VM delivery, `45afcb7`)* If `infra/` exists: add `tofu-basics.tfvars`, bump VM size if
      needed. Revisit only if that delivery path comes back.
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
- [ ] **T9.6** *(added)* Turn the throw-away P3 checks into **committed** e2e scripts under
      `workshops/tofu-basics/tests/` — the lifecycle run (init/apply/tag edit/replace/quota/drift/destroy/restart)
      and the policy-violation run currently exist only in a lost session scratchpad (§15a-F). Include the
      live missing-tag check and the `CURL_CA_BUNDLE` check. The P5 and P6 verification runs were scratch scripts too (not committed).
- [ ] **T9.7** *(added)* Concurrency: 30 students applying at once against one global lock (§15a-F) —
      measure `apply` latency; if bad, narrow the lock (per-subscription) or move Docker calls outside it.
      **P4 measured a concrete instance:** `put_container_group` holds `State.lock` while Docker creates the container, so every portal read and every other student's ARM call stalls ≈3.3 s per deploy (§15a-G1). Do this fix here — reserve quota+port under the lock, create outside it, then commit.
- [ ] **T9.8** *(added)* Isolation checks not yet done: `--icc=false` really blocks container-to-container
      traffic; a hello container cannot reach `cloud-host`'s own netns or `cloud-api`; re-review D2 under
      **docker** (not rootless podman) before any Azure-VM delivery (§15a-F).
- [ ] **T9.9** *(added 2026-09-20)* Real-browser pass over Labs 4–10 and the portal (Add tag, Save tags, Delete dialog,
      Browse, Quota tile, Refresh now): the P6 verification drove the portal through `/cloud/api` and only
      cross-checked button/label text against `app.js`. Also re-run Track A labs 0–3 on a rebuilt image, and re-check
      the attention-tile text now reading `code: message` (`25a7176`, offline tests only).
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

### F — Follow-ups OUTSIDE tofu-basics (found while building it; not started)

These are problems in other parts of the repo. They are deliberately **not**
fixed on this branch — do them as a separate change so the tofu-basics diff stays
reviewable. Details and evidence are in §15a-B.

- [ ] **F.1** Fix the stale restated `HEALTHCHECK` in
      `workshops/dns-as-code/compose/terminal/Dockerfile:40-41` (add
      `--header="X-Control-Token: ${CONTROL_TOKEN}"`).
- [ ] **F.2** Same fix in
      `workshops/cert-autorenewal/compose/terminal/Dockerfile:68-69`.
- [ ] **F.3** *Verify first:* run `./run.sh dns-as-code` and `./run.sh cert-autorenewal`
      and confirm `workshop_terminal` reports `unhealthy` before the fix and `healthy`
      after (only *inferred* so far — see §15a-B). Rebuild with `./run.sh stop` first.
- [ ] **F.4** Decide whether workshops should keep *restating* the base HEALTHCHECK at
      all (it drifted once; it will again). Options in §15a-B. Then update
      `workshops/README.md` "Adding a new workshop" step 4 accordingly.
- [ ] **F.6** *(user review)* Commit `a24f08b` on `main` bundles ~24 unrelated in-flight engine changes
      that were committed and pushed **on the user's instruction, without a line-by-line review by
      Claude** — see §15a-F. Someone who owns that work should skim it.
- [ ] **F.7** *(decision)* Base images `docker:dind` and `python:3.12-alpine` are unpinned tags in
      the tofu-basics overlay — pin them (repo precedent is mixed) or accept the drift risk; §15a-F.
- [ ] **F.5** Refresh the stale comment in `engine/web-terminal/Dockerfile:175` (says
      no workshop has a `.tf` file / `hashicorp.terraform` is not installed) and add a
      line to `engine/web-terminal/vscode-extensions.md`: the OpenTofu extension is now
      installed by `tofu-basics`' own terminal image, not the base image.

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
- **Measured so far (P3):** cloud-host image 369 MB, cloud-api 52 MB, `:tofu-basics` terminal 1.13 GB (base 692 MB); idle memory cloud-host ≈58 MB, cloud-api ≈13 MB. Per-student `.terraform` is ~30 KB thanks to the unpacked mirror. Memory under 30 running hello containers is **not measured yet** (T9.3).
- **Capacity (initial guess — measure in T9.3):** hello containers ≈ 10–20 MB
  each idle; quota 2/student × 30 = 60 containers with 128 MB cap ⇒ worst-case
  7.7 GB, realistic ≪1 GB. `cloud-host` `mem_limit` 3 GB (`CLOUD_HOST_MEM_LIMIT`, set in the overlay); cloud-api
  256 MB. **Neither is in `capacity-calc.sh` yet (T8.2).**
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

## 15a. Worth knowing & follow-ups

*Added 2026-09-18 after P3. Read this before starting P4.*

### A. Decisions D2–D6 — all confirmed or set by the user on 2026-09-19

*History:* the user first said "commit everything and push it, then start implementing" without
answering §4, so D2–D6 were built at defaults. They have since been decided (§4, §16 entry 2026-09-19); this
table records what was built and how to change it:

| ID | What was built | Why it matters / how to change |
|---|---|---|
| D2 | `cloud-host` is a **privileged** Docker-in-Docker container on an `internal: true` network, unix socket only, no host ports, no internet. | The riskiest component. Boxed in by §7, but a privileged container is a privileged container. Change = re-architect the executor (`docker_api.py`) — say so early. |
| D3 | **Broker with `SO_PEERCRED`** (root daemon in the terminal; each student gets only their own creds). | The alternative (shared class secret) is simpler but lets students impersonate each other. |
| D4 | **Built in P5 (`a2eb28f`)**: a small additive edit to the base `engine/gateway/Caddyfile`, `engine/allocator/server.py`, `engine/docker-compose.yml` (a `CLOUD_ENABLED` flag mirroring `DEMO_APP_ENABLED`). | The user's repo policy is that base engine files stay workshop-agnostic; any further engine edit needs the user's OK first. |
| D5 | Region `canadacentral` (user, 2026-09-19: Canadian audience); policy forces `rg-` / `ci-` name prefixes and allows only `canadacentral` and `canadaeast`. | Edit `compose/cloud-api/policy.py`. |
| D6 | Quota 2 container groups per student, 0.25 vCPU / 0.125 GB each, only `dojo/hello:1.0` and `:2.0`, only port 80. | Edit `policy.py` (and `MAX_*` in `docker_api.py` tests). |

### B. Problems found in OTHER workshops / the base engine (need updating; see tasks F.1–F.5)

1. **Stale restated `HEALTHCHECK` in two workshop terminal images.**
   - The base image's healthcheck now sends a token header:
     `engine/web-terminal/Dockerfile:259-260` →
     `wget -q -O /dev/null --header="X-Control-Token: ${CONTROL_TOKEN}" http://127.0.0.1:7682/status`.
     `workspace-control.py` answers **403** without it (the "Harden internal control-plane
     auth" work).
   - `workshops/dns-as-code/compose/terminal/Dockerfile:40-41` and
     `workshops/cert-autorenewal/compose/terminal/Dockerfile:68-69` still restate the **old**
     check (no header). Because a Dockerfile `HEALTHCHECK` in the child image *replaces* the
     inherited one, those two workshops' `workshop_terminal` should report **unhealthy**.
   - **Evidence level:** *observed* on `tofu-basics` (it copied the same stale line: status
     `unhealthy`, `wget` got 403, fixed by adding the header → `healthy`). *Inferred, not run*
     for `dns-as-code` and `cert-autorenewal` (same line, same base). Task F.3 confirms.
   - **Impact:** cosmetic in this stack today (nothing `depends_on` the terminal's health), but
     `podman ps` / `docker ps` show `unhealthy`, and any monitoring or Azure-VM automation keyed
     on health would misfire.
   - **Fix options (F.4):** (a) patch both lines to add the header — quick, but it will drift
     again; (b) delete the restated `HEALTHCHECK` from workshop images and rely on inheritance
     (the stated reason for restating was to satisfy static scanners that don't resolve `FROM`);
     (c) have the base image expose a tiny `web-terminal-healthcheck` script that workshop images
     call, so the command lives in one place. `tofu-basics` currently uses (a).
2. **Stale comment in the base Dockerfile** (`engine/web-terminal/Dockerfile:175-184`) says no
   workshop has a `.tf` file and `hashicorp.terraform` is deliberately not installed. Still
   true for the *base* image, but `tofu-basics` now installs the **OpenTofu** extension in its own
   image (`compose/terminal/Dockerfile`). Update the comment and `engine/web-terminal/vscode-extensions.md`
   (F.5) so the next person isn't misled.
3. `workshops/README.md` "Adding a new workshop" step 4 tells authors to restate the healthcheck
   but not that it must carry the token header — the root cause of item 1 (F.4).
4. **Compose does not recreate a running container after its image is rebuilt**
   (`./run.sh <w>` a second time reuses the old container). Always `./run.sh stop` first when
   testing image changes. Also `podman rm -f` on a service another one `depends_on` fails silently.

### C. Behaviours of Dojo Cloud that surprised us (use them in the labs)

- `plan` in a folder with **no state never contacts the cloud** — only `apply` (or a plan with
  existing state) does. So authz/policy can only be demonstrated with `apply`.
- A **replacement rejected by policy** (bad image on an existing container) has *already
  destroyed* the old container — Terraform destroys first. Real-cloud behaviour; Lab 6 should
  say "policy failures happen at create time; your old resource may already be gone".
- `apply` takes ≈ **35 s** (resource group ≈ 20 s + container group ≈ 14 s) because of the provider's
  own poll ticks; `destroy` similar. Our API answers instantly. Plan the lab timing around it.
- **Tag edits use `PATCH`** (in-place `~`); env/image/cpu/dns-label edits force replacement `-/+`.
  A missing `PATCH` handler made Lab 8's in-place demo fail — found only by testing.
- `provider "azurerm" { features {} }` must be **multi-line** HCL (one-line block is a syntax error) —
  the starter files must be multi-line.
- Sites are served with CSP `sandbox` (no scripts): a student's `MESSAGE` is HTML-escaped *and*
  sandboxed.
- Deleting a container "in the portal" (or `docker rm` on the host) is detected at next GET →
  shows in `plan` as `+ create`; the activity log records "Container disappeared outside IaC".
- The metadata document **must** say tenant `common` + identity provider `AAD`, or azurerm refuses
  the environment as "Azure Stack" (details §5.5).
- `TF_VAR_owner` and `TF_VAR_portal_base_url` come from the broker as environment variables —
  the starter's `variable "owner"` therefore has **no default** (good place to teach `TF_VAR_`).
  `PUBLIC_BASE_URL` in this dev `.env` is `http://localhost` (no port) while the gateway listens on
  8080, so the printed portal link is wrong locally; it's an `.env` matter, not a bug.

### D. Environment & test notes

- All testing so far used **podman + podman-compose** (no docker on this machine). The Azure VM
  delivery path (docker) has **not** been exercised. `docker:dind` under *docker* proper should behave
  the same, but it is untested here.
- The stack was stopped at the end of each session (`./run.sh stop` wipes volumes). No test data is kept.
- Unit tests: `cd workshops/tofu-basics/compose/cloud-api && python3 -B -m unittest test_portal_api test_executor test_policy_auth` (90 tests)
  and `cd .. && python3 -B -m unittest test_parity` (5 tests) (host Python is enough; no containers).
- Scratch spike harness from P2 lived in the session scratchpad and is gone; §5.5 has the recipe if
  it's ever needed again (the real control plane now supersedes it).

### E. Known gaps / not verified yet *(rewritten 2026-09-20)*

- **Not built yet:** slides (P7; only a placeholder hub exists, and without a slide file the Marp container exits),
  workshop README, facilitator guide, `capacity-calc.sh` and `engine/README.md` entries (P8), committed e2e/load
  scripts (P9), optional stretch labs 11–12 (T6.4). Built since this section was first written: portal and activity
  read API (P4), gateway/allocator route and facilitator tab (P5), the starter repo with its lock file, and labs 4–10
  (P6).
- **Not verified:** a real-browser pass over the portal and labs (T9.9); HCL highlighting in code-server (visual);
  Labs 0–3 re-run on the current image; a fuzz test of raw ARM request bodies against the executor (only the
  template builder is tested); 30 students and 60 containers (T9.3/M4); arm64 (checksums are pinned per arch, only
  amd64 was built); docker proper instead of podman (§15a-D); the attention-tile text after `25a7176`.
- **Verified since:** the missing-tag policy message and every other policy error through the real provider (Lab 6);
  `CURL_CA_BUNDLE` (Lab 4); the site and portal through the gateway (P5).
- **Known limitation:** only one container per group and only `dojo/hello:*` images are allowed, by
  design (§7). LRO (`Azure-AsyncOperation`) is not implemented — the provider's polling is what
  sets the timings above.

### F. Other problems, risks and gaps found in the audit (added 2026-09-18, late)

Each item says how it was established. **Verified** = observed/read in the repo or stack;
**Reasoned** = follows from the code but not measured.

1. **The `--test` demo bots do not exercise tofu-basics.** *Verified* (`engine/web-terminal/bot-runner.sh`
   header): bots "work through the git-fundamentals labs" (clone/branch/edit/commit/push/PR). On this
   workshop they will only produce git noise. So plan item T0.3's hope that bots "drive the workshop" does
   not hold, and **T9.3's load test needs its own driver** (a script that runs the Track A/B commands per
   student), not just `--test N`.
2. **Only the unit tests are committed.** *Verified.* The live checks that proved M3 (lifecycle, policy
   scenarios, isolation probes) were shell scripts in a session scratchpad that no longer exists. What survives
   is the description in §16. → task **T9.6**.
3. **One global lock serialises every ARM call.** *Verified in code* (`server.py`: `with st.lock:` around
   resource-group and container-group handlers, **including GETs, and the Docker calls inside them**).
   *Reasoned:* with ~30 students applying together, each PUT (~1–2 s of Docker work) queues behind the others,
   and every `plan` refresh (a GET that calls `docker inspect`) waits too. **Not measured.** → task **T9.7**.
4. **Privileged-container risk was assessed and tested only under *rootless podman*.** *Verified* (that is
   all this machine has). Under rootless podman `privileged` is not real host root; under **docker** on the
   Azure VM it is much closer to real root, so the D2 risk is higher there. The isolation controls in §7 are
   the same, but they must be re-reviewed and re-tested on docker before that delivery. → **T9.8**, and D2.
5. **Container-to-container isolation on `cloud-host` is unverified.** *Reasoned:* dockerd runs with
   `--icc=false` and containers are launched with `CapDrop ALL`, `no-new-privileges`, memory/CPU/pids caps
   (the caps and template are unit-tested), but nobody has tried to reach one hello container from another
   or from a container to `cloud-api`. → **T9.8**.
6. **Unpinned base images in the overlay.** *Verified:* `docker.io/library/docker:dind` and
   `python:3.12-alpine` float (`busybox:1.37` is pinned). Repo precedent is mixed (`dns-as-code` uses a
   `:latest` PowerDNS). Note the cloud-host build **fails on purpose** if upstream's `dockerd-entrypoint.sh`
   changes shape (the `sed` + assertion that removes the unauthenticated `tcp://…:2375` listener) — a good guard,
   but it will surface as a build failure after an upstream release. → **F.7**.
7. **Private-CA certificates last 30 days** (CA and server cert, `pki.py`) and are only regenerated when the
   files are missing. *Reasoned:* fine while `./run.sh stop` wipes volumes between workshops; a VM left up for
   more than 30 days would break TLS. Low priority; note for the Azure delivery.
8. **No rate limiting on the token endpoint.** *Reasoned:* secrets are 160-bit HMAC output, so guessing is
   infeasible, but a student can hammer `login.dojo.cloud`/`management.dojo.cloud` and slow the class. Request
   bodies are capped at 1 MB. Low priority.
9. **Error messages say `tofu`, labs say `terraform`.** *Verified:* OpenTofu's own hints read
   "run: tofu init" even when the student typed `terraform`. Not a bug, but Lab text and the troubleshooting
   table should mention it so a student isn't puzzled (already noted once in Lab 0).
10. **Commit `a24f08b` was made without a full review.** *Verified* (I read `git diff --stat` and a handful of
    diffs, not the whole 902-line change) and it is **pushed to `main`**. It contains unrelated engine work:
    the repo-root `run.sh`, a locally-built Alpine Marp image replacing `marpteam/marp-cli`, removal of code-server's
    bundled Copilot runtime, teardown `--dry-run`, capacity-calc/env-setup/run.sh changes, code-server idle
    timeouts, and fully-qualified `docker.io/library/…` image names. The commit *message* was written from that
    partial view. → **F.6**.
11. **Building the terminal image with plain `podman build`** drops the `HEALTHCHECK` (OCI format) and prints a
    warning; `./run.sh` sets Docker format via `BUILDAH_FORMAT`. *Verified.* Always build through `./run.sh`
    when checking health.
12. **Benign noise to ignore:** dockerd logs "Failed to find nft tool" on `cloud-host` start (iptables path
    is used); `run.sh` prints "Removed N superseded image(s)". *Verified*, harmless so far.
13. **Local `.env` oddities** (not repo bugs): `PUBLIC_BASE_URL=http://localhost` with the gateway on 8080, so
    portal links and `TF_VAR_portal_base_url` omit the port; the earlier `curl http://localhost/` returned 000
    for the same reason.

*Checked and found NOT to be a problem:* the base image no longer contains `ms-python.debugpy` (an older local
base image did; the freshly built one doesn't); the gateway returning 401 on `/` and `/terminal/` without a
session is expected.

### G. Findings from P4 (added 2026-09-19)

Established by the live integration run (real `azurerm`, real browser); each is *verified* unless marked.

1. **A deploy stalls the whole control plane ≈3.3 s.** Existing ARM code (`server.py` `put_container_group`,
   and GET/PUT of container groups, resource-group DELETE) calls Docker **while holding `State.lock`**; the
   portal's own endpoints do not, but they still wait for that lock. Measured: one `overview` poll waited 3.30 s
   during a deploy; simultaneous deploys queue. Portal reads themselves are fast (30 parallel class overviews: p95
   258 ms; 30 pollers every 3 s: p95 186 ms). **Fix in T9.7** before the 30-student test.
2. **The hello image was silent**, so the Logs tab was always empty — fixed in `49c168e` (startup line + `httpd -v`).
   *Verified* in plain busybox only; the log **framing** through the executor was checked with a container that
   prints. **Re-check the Logs tab once after the next full image rebuild.**
3. `Handler.log_message` raises `AttributeError` on a malformed HTTP request line — only a thread traceback in
   the log (existing code). Low priority.
4. The container-group `owner` **tag value is not validated** — a student can claim any owner name in the tags
   (the *real* owner is the subscription, so authz is unaffected). Still open: the P6 labs do not rely on it, so no policy was added; decide only if a lab needs it.
5. The ARM list endpoints read state without the lock (existing code). Benign today; fold into T9.7.
6. `_body()` reads at most 1 MB and leaves any excess unread on the socket (existing code). Low priority.
7. **Portal identity relies on `GATEWAY_TOKEN`** reaching cloud-api via the overlay. Verified a bare
   `X-Auth-User` is rejected (401) and the token is not in student environments or `/proc/1/environ`. The
   allocator-style trust model only holds if the Caddy block sets both headers with `header_up`; **it does (P5), verified against an echo upstream with forged headers.**
8. Facilitator username in this dev `engine/.env` is `admin` (not the `root` default) — the code reads
   `FACILITATOR_USERNAME`, so nothing to fix; just don't hard-code `root` in labs.
9. Anonymous podman volumes from earlier runs survive `./run.sh stop` — housekeeping, not a bug in this workshop.
10. **Unrelated edits appeared in the working tree during P4** (root `README.md` +438 lines,
    `engine/.env.example`, `engine/README.md`, `engine/docker-compose.yml`, `workshops/README.md`). They were made
    by neither Claude nor its agents (verified: agents were told not to, and the integration agent reported it
    did not touch them). They were **deliberately not committed** with P4 — see the `git status` in §16.

### H. Findings from P5 (added 2026-09-19; live-tested against the real gateway and stack)

1. **Failure history can be evicted (medium).** The activity log is capped at 2000 events (`state.py`
   `ACTIVITY_MAX`) and `_progress` derived `lastEvent`/`failures` from it. One student sending ~2100 failing PUTs
   pushed other students' `Failed` events out, so 3 of 4 attention tiles fell back to `inProgress`. **Fix (T5.6):** a
   small per-subscription summary maintained in `State.log()` and rebuilt from the persisted log; this replaces the
   "no new state" rule in §5.6a.
2. **Bot roster names differ (low).** cloud-api's roster (`auth.py`) uses `testuser01`, the engine's accounts are
   unpadded (`testuser1`…). Board and `/admin` disagree and the broker cannot mint credentials for bots < 10. Fix in T5.6.
3. **Stage can flip before the event is logged (low, cosmetic).** In portal delete, state removal and the log entry are
   separate lock holds; a poll in between shows `inProgress` with the previous `lastEvent`. Next poll corrects it.
   Left alone: T9.7 restructures this locking.
4. **Noisy `BrokenPipeError` tracebacks (low)** when a client drops mid-response (cloud-api and once the allocator).
   Fix cloud-api in T5.6 (the allocator one is base-engine code, not touched).
5. **cloud-api ignores SIGTERM** (Python is PID 1, no handler) so stop/restart waits 10 s then SIGKILLs. Fix in T5.6.
6. **Latency bug found and fixed in `a2eb28f`:** Nagle + delayed ACK stalled small cloud-api responses ~40 ms
   (also slowed the real `azurerm` provider's calls). `disable_nagle_algorithm = True`; p50 47 ms → ~4 ms.
7. `publicBaseUrl` from `/cloud/api/me` (and `TF_VAR_portal_base_url`) ignores the dev host port (`PUBLIC_BASE_URL`
   has no `:8080`). Only matters on a dev box with a non-default port: **labs must not hard-code links from it.**
8. Not caused by P5, recorded for the engine owner: the presentation image is rebuilt on every `./run.sh` (its
   "source changed" check always fires); `engine_workshop_lab` network survives `./run.sh stop`; `/ide/` returned one
   502 on the very first hit while code-server cold-started (a retry works).
9. The root-only signing key is (correctly) unreadable to a test agent; bot credentials were therefore not minted.
10. `/demo/` was only partly verified on cert-autorenewal (the card and the route reach the demo-app; its own 404
    is nginx because nothing was pushed).

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
  isolated net, SO_PEERCRED broker, additive `/cloud*` route, `canadacentral`, quota
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

### 2026-09-18 (night) — P3 Dojo Cloud control plane → M3
- Built and committed (`6301cc8`): `compose/cloud-host/` (privileged dind, internal
  net, unix socket only, hello 1.0/2.0 imported offline from a busybox rootfs),
  `compose/cloud-api/` (`server.py`, `auth.py`, `policy.py`, `docker_api.py`,
  `state.py`, `pki.py` + tests), terminal side (`dojo-broker.py`, `dojo-env`,
  `entrypoint-wrapper.sh`, `unpack-mirror.py`, azurerm added to the mirror), the
  full overlay, and `compose/test_parity.py` (broker ⇄ auth.py must agree).
- **Verified live as `student01` in the running stack:** `terraform init` (28 KB
  `.terraform`, symlinked provider) → `apply` (≈35 s: RG 20 s + container group
  ~14 s, due to the provider's poll ticks) → site reachable via `cloud-api:8080/cloud/site/<label>/`
  from another student's terminal → clean re-plan → tag edit = in-place `~`
  (PATCH) → env edit = `-/+` replace, site shows new message → 3rd container
  group refused (`QuotaExceeded`) → out-of-band container delete = `+ create`
  on plan, `apply` reconciles → `destroy` leaves 0 containers → cloud-api restart
  keeps state (reconciled 1 CG, 1 RG). Track A regression OK on the unpacked mirror.
- Policy errors verified through the real provider (`InvalidImage`,
  `InvalidResourceRequest`, `InvalidContainerGroupName`, `InvalidRequestContent`
  for port 22, `RequestDisallowedByPolicy` for region). Missing-tag policy was
  exercised on PATCH/PUT by unit tests; **re-verify the missing-tag message live in P6.**
- **Surprises / things to remember:**
  1. A `plan` in a directory with no state never contacts the cloud — to test authz
     you must `apply`. (Used in lab text: "plan only looks; apply is what talks".)
  2. When a *replacement* is rejected by policy (e.g. bad image), Terraform has
     already destroyed the old container — the site is gone until fixed. Real
     cloud behaviour; mention in Lab 6 ("policy failures happen at create time").
  3. `provider "azurerm" { features {} }` must be multi-line HCL.
  4. `podman rm -f` of `workshop_cloud_api` silently fails because the terminal
     depends on it → use `./run.sh stop` then start; compose does **not** recreate
     a running container after an image rebuild.
  5. Sizes: `cloud-host` image 369 MB, `cloud-api` 52 MB, `:tofu-basics` terminal
     **1.13 GB** (base 692 MB). Idle memory: cloud-host ~58 MB, cloud-api ~13 MB.
     (Per-container mem while running 30 hello containers still to measure — P9.)
- **Not done / deliberately deferred:** the portal + activity-log read API (P4),
  gateway/allocator integration (P5, needs D4), Track B starter files, lock file
  with azurerm hashes, labs and slides (P6/P7), `CURL_CA_BUNDLE` rebuild check,
  the 30-student load test (P9).
- **Next task: P4 (portal)** — then P5, P6. See §12. The user asked to stop for the
  night after P3, so nothing from P4 has been started.

### 2026-09-18 (late) — Documentation follow-up
- At the user's request, recorded "things worth knowing" and the out-of-date
  `dns-as-code` / `cert-autorenewal` terminal healthchecks in the plan: new **§15a**,
  new follow-up tasks **F.1–F.5** in §12, decision rows D2/D3/D5/D6 relabelled
  "built at default, not confirmed", D4 marked "ask before editing base files".
- No code changed. Nothing in the other workshops was touched.
- Second pass: audited the whole session for problems not yet written down → new §15a-F (13 items),
  tasks **T9.6–T9.8** and **F.6–F.7**; marked the dropped T1 fallback tasks `[-]`; repointed stale
  `arm_facade.py` references to commit `ec2f664`.

### 2026-09-19 — P4 Dojo Portal (`49c168e`)
- **Approach:** wrote the API contract first (§5.6), then built the backend (`portal_api.py` + shared `App`
  delete/tag-patch methods) and the SPA (`compose/cloud-api/portal/`) **in parallel by two sub-agents** on disjoint
  files, then had a third agent run the live integration test. Unit tests: 47 (28 new) + 3 parity, all pass.
- **Live results (real azurerm as `student01`, real browser):** all 8 integration checks passed. Regression of the
  refactored ARM delete/patch: apply ≈35 s, tag edit = in-place `~` (PATCH, 1 s), env edit = `-/+` (13 s), destroy → 0 containers.
  Auth: no headers/forged `X-Auth-User`/wrong token → 401, unknown user → 403, cross-student detail/logs → 403,
  `activity?scope=all` student → 403. **Drift demo works:** portal DELETE → `plan` shows `+ create`, activity log says
  "Delete container group (portal)", `apply` reconciles; a portal tag change shows as `~`; removing `owner` →
  `RequestDisallowedByPolicy`. Write-actions toggle blocks students, not the facilitator, and survives a restart;
  purge removes only the target subscription (incl. the container on cloud-host). Container appears in the portal
  within ≈0.2 s of the PUT (target was ≤3 s). Hostile tag/name payloads render as text; no CSP violations.
- **Fixed after the test:** hello image printed nothing → Logs tab empty (`hello/entrypoint.sh`).
- **Not done / carried forward:** gateway `/cloud*` route and a browser check *through the gateway* (P5, D4 — needs the
  user's OK before touching base-engine files); the lock-during-deploy stall (§15a-G1 → T9.7); a real screen-reader and
  Firefox/Safari pass (P9); re-check Logs after a full rebuild.
- **Working-tree note:** unrelated modified files appeared mid-phase (root `README.md`, three `engine/` files,
  `workshops/README.md`); **not committed**, not touched (§15a-G10). Please confirm they are yours.
- **Also still unconfirmed:** D2–D6 defaults (§15a-A) — flagged again at this hand-off.
- **Next: P5** — stop and ask the user first (phase gate), and confirm D4.

### 2026-09-19 — P5 gateway integration, facilitator progress board, decisions (`a2eb28f`, `1b22631`, `8ee8439`, `45afcb7`)
- **Approach:** small base-engine edit done directly (D4, after the user's go-ahead), then a live-integration agent
  through the real gateway (10/10 PASS; found and fixed the Nagle stall). The user then asked for a facilitator
  Cloud tab and per-student live progress: contract written into §5.6a, backend and SPA built **in parallel by two
  agents**, then a second live-integration agent (real azurerm applies, real browser, 30 rostered students): all 5
  checks PASS. A follow-up made the failure message inline on attention tiles.
- **Decisions (user):** D2 privileged-but-isolated dind **confirmed**; D3 (a) broker **confirmed**; D4 green-lit;
  D5 **Canadian regions** (`canadacentral` default, `canadaeast`; policy now allows only those); D6 "size
  appropriately" → kept 2 groups (Lab 9 needs it), cloud-host ceiling 3 GB, T9.3 to measure. Repo `CLAUDE.md`
  created (git-ignored). Correction: an earlier hand-off said the default region was `uksouth`; that was the code's
  value, `canadacentral` had wrongly entered the plan in `e2f0524` — both are now `canadacentral`.
- **Commits:** `a2eb28f` P5 integration + Nagle fix + 3 GB ceiling; `1b22631` progress board; `8ee8439` Canadian
  regions; `45afcb7` the user's own README/doc edits (their request, separate commit).
- **Not verified live:** attention-tile message and `canadacentral` on the real stack (T5.7); real screen reader,
  Firefox/Safari (P9).
- **Next:** T5.6 fixes landed in `2e8e818`; then **P6 Track B** (approved by the user).

### 2026-09-19/20 — P6 started, cut off by a rate limit; plan brought up to date
- **What happened:** the user approved P6 ("Track B, go ahead") and a builder agent was launched. It hit a session
  rate limit (HTTP 429) and reported failure, but the working tree showed it had already written labs 4–10, the starter
  repo (with a lock file) and a cheat-sheet section. The user committed that unreviewed work as `5d0ad28`.
- **Also from that turn:** the stack was left half-stopped; it is now fully stopped (all containers `Exited`).
- **Status:** P6 is *drafted*, not done. T6.1–T6.3 are `[~]`; nothing has been run live, and T5.7 (rebuilt-stack
  re-checks of the T5.6 fixes and Canadian regions) is still open. The "START HERE" block under P6 in §12 is the
  resume checklist.
- **Git:** the user pushed `feat/tofu-basics`; `origin/feat/tofu-basics` = `5d0ad28` (nothing local-only).
- **Next:** rebuild the stack → T5.7 → verify/fix each drafted lab live → tick T6.x → ask the user before P7.

### 2026-09-20 — P6 verified live (`25a7176`)
- A verification agent rebuilt the stack and ran every command of labs 4–10 as `student01` through real azurerm,
  replacing pasted output with real output, plus the T5.7 checks (all in the task lines above). ANSI note: tofu emits
  colour codes even when piped, so grep examples use `-no-color`. Troubleshooting boxes reproduced live: lost state
  ("already exists … import"), `PortalWriteActionsDisabled`, `DnsNameLabelInUse`, `var.owner` prompt, missing
  plugins, `InvalidImage`, `InvalidContainerGroupName`, `QuotaExceeded` (which of two `for_each` instances wins is a race).
- **Fixed in `25a7176`:** failure events now log `code: message` (tile/activity showed only the code); the RG-name
  example said `-uks`, now `-cac`; "works like Microsoft Azure" → "works like Azure" in the lab text.
- **NOT verified:** no real browser (portal button/label text cross-checked against `app.js` only; portal actions were
  driven through `/cloud/api` with a real session cookie); Labs 0–3 (Track A) not re-run; the `curl: (60)` box and the
  `env` output only inferred; arm64; 30-student load; the facilitator `/admin` tab; the new `code: message` text live.
- **Known:** `url` output / `TF_VAR_portal_base_url` omit the dev port (`:8080`) on this dev box (§15a-C 9), so labs say
  `<class-address>`.
- **Next:** ask the user before P7 (slides). A browser pass over labs 4–10 belongs in P9 (T9.x).

### 2026-09-20 — plan accuracy pass
- Brought stale statements in line with the code and git history: §3 facts (docker.sock, `infra/`), §8 mirror TODO,
  §11 touchpoints (real Caddy matcher, allocator, what is still not done), P4/T3.x notes, §14, §15a-A (D2–D6 now
  confirmed) and §15a-E (rewritten). T8.4 dropped (no `infra/`). Added T9.9 (browser pass). Older §16 entries were
  left as written; they are a dated record, not current state.

<!-- Append new entries below this line. Format:
### YYYY-MM-DD — short title
- what was done (task IDs), commits (SHAs), decisions, surprises, next step -->
