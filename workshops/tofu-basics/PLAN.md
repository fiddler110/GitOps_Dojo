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
| Overall status | **M1 + M2 + M3 reached; P4 portal and P5 gateway route done (facilitator Class progress board built, live-tested). P6 Track B labs 4–10, cheat sheet and starter repo done and verified live through the API (`25a7176`); P7 slides written and render-tested (`d750be5`); P8 done, live-tested and committed (README, facilitator guide, capacity flag, Forgejo-password panel, facilitator status strip, start-up decoupling); T8.10 (cloud-host restart) fixed; next: P9 or the T9.9 browser pass (ask the user first)** |
| Working branch | `feat/tofu-basics` (planning commit is on `main`) |
| Last updated | 2026-09-21 (P0–P8 done and committed (`8ce91e2`, `72b85fc`, `e0e6bff`); D2–D6 all decided) |

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
4. Find the first `[ ]` or `[~]` task in §12 (skip tasks marked *optional*, e.g. T6.4, unless asked; as of
   2026-09-21 the first open item is **P9**, after asking at the phase gate). Run that task's **Verify** line
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
with a terminal and git; new to IaC. Target session **~2¼ hours**: talk ~30 min (a guess until
the dry run, T9.4), Track A ~37 min and Track B ~66 min (the lab README's estimates). To fit 2 hours, drop Lab 9
and/or Lab 8's optional section (deck speaker notes say so).

---

## 2. Status dashboard

Update this table whenever a phase changes state. "Done" means the phase's own tasks are ticked; the last column
lists what is **still open inside a done phase** so a green row is never read as "fully finished".

| Phase | Title | Status | Still open in this phase (task / section) |
|---|---|---|---|
| P0 | Prep & repo hygiene | **done** | none |
| P1 | Track A — offline sandbox + terminal image | **done** (`ef3e36a`) | HCL highlighting not checked visually in a browser (T1.3, T9.9); Labs 0–3 not re-run on the current image (T9.9); arm64 image never built (§15a-E) |
| P2 | Provider-strategy spike (gate D1) | **done** | none |
| P3 | Control plane ("cloud-api") + cloud host | **done** (`6301cc8`) | fuzz test of raw ARM bodies against the executor (T9.2/T9.6); deploy holds the global lock ≈3.3 s while Docker creates (T9.7); isolation checks under real docker (T9.8); the P3/P5/P6 verification runs are not committed scripts (T9.6) |
| P4 | Portal (Azure-inspired console) | **done** (`49c168e`) | no real screen-reader / Firefox / Safari pass; no real-browser pass over portal buttons (T9.9) |
| P5 | Gateway / allocator integration | **done** (`a2eb28f`; progress board `1b22631`; fixes `2e8e818`, `25a7176`) | attention-tile text `code: message` only unit-tested (T9.9); deferred findings in §15a-H (`publicBaseUrl` ignores the dev port, presentation image rebuilds every run, leftover network survives stop) |
| P6 | Lab content — Track B | **done** (`5d0ad28` + `25a7176`) | stretch labs 11–12 (T6.4, optional); browser pass over labs 4–10 (T9.9); labs say `<class-address>` because the dev portal URL lacks the port |
| P7 | Slides | **done** (`d750be5`) | talk timings are guesses until the dry run (T9.4); the four post-render fixes were not re-rendered; not checked in the `/admin` Slides tab iframe or with real student traffic (the shared-theme code colours were fixed in `82b9e36`) |
| P8 | Docs, registration, capacity, delivery | **done** (T8.1–T8.3, T8.5–T8.10 written and live-tested 2026-09-21) | the guide and README are untested against a real class (T9.4); T8.4 dropped |
| P9 | Validation (bots, load, dry-run) | **in progress** (2026-09-21): T9.1, T9.2, T9.3 (M4 at 15), T9.6, T9.7 done live | open: T9.5 (other workshops), T9.9 (browser), T9.4 (people, yours), T9.8 on docker proper, and 20+ students |
| P10 | Optional stretch | not started | T10.1–T10.4 |

### Milestones

| | Milestone | Status | Caveats — what "reached" does not cover |
|---|---|---|---|
| **M1** | Track A shippable | ✅ reached (`ef3e36a`) | the deck is written and render-tested (P7) but not dry-run with people; HCL highlighting and Labs 0–3 not re-checked in a browser / on the current image; amd64 only |
| **M2** | Provider decision made (`azurerm`) | ✅ reached | none |
| **M3** | One student deploys end-to-end | ✅ reached (`6301cc8`) | proven for one student on podman; not concurrent, not docker proper (T9.3, T9.7, T9.8) |
| **M4** | Load test passes at the largest class this machine can hold (**redefined 2026-09-21: 15 students, not 30**; 30 needs a bigger box or a VM, and is a separate run) | ✅ **reached at 15** (2026-09-21, T9.3; 30 not tried) | only the read side was checked with 30 *rostered* students (progress board p50 3 ms). No 30-way concurrent apply has run; the `--test` bots only exercise git, so a dedicated driver is needed (§15a-F1); the 3 GB `cloud-host` ceiling is unmeasured; the lock stall (T9.7) is unfixed |
| **M5** | Release-ready | ❌ **not reached** | needs the T8.5 `engine/README.md` note, P9 validation (incl. a human dry-run, T9.4, and the regression run of the other workshops, T9.5) |

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

### 5.7 Startup decoupling, facilitator status strip, Forgejo-password panel (contract, 2026-09-21)

*Decided with the user on 2026-09-21. Builders work from this section; change it if you change the code.*

**A. Landing page shows the student's Forgejo password** (`engine/allocator/server.py`, `render_confirmation`).
Always on for every workshop (every workshop pushes to Forgejo; no flag). Shows only secrets the student owns: the
value of `STUDENT_PASSWORD`, labelled **Forgejo password**, visible (no click-to-reveal), in a `<code>` element,
`html.escape`d. Short hint: use it when git asks for a password (`git push`) and for the terminal account. **Never**
show `TTYD_*`, `FORGEJO_ADMIN_*`, `CONTROL_TOKEN`, `GATEWAY_TOKEN`, or the facilitator's or bots' passwords. Every
response that carries it (both `render_confirmation` call sites) sends `Cache-Control: no-store` and `Pragma: no-cache`
(`send_html(headers=...)` iterates `for k, v in (headers or {})`, so pass a list of `(name, value)` tuples). The
`student01` badge stays. Labs call the value "your **Forgejo password**, shown on your landing page".

**B. Facilitator-only service status** (`engine/allocator/server.py`; students see no status at all).
The allocator's *request path stays single-threaded* (atomic slot claim, see its docstring). Probing runs in **one
background daemon thread** that only writes a snapshot; request handlers only read it (no I/O in a request).
- Probes (every `STATUS_INTERVAL_SECONDS`, default 5, each with a 2 s timeout, run sequentially):
  **Forgejo** `http://git-server:3000/api/healthz`; **Terminals** `control_request("GET", "/status")` (web-terminal);
  **Slides** through the gateway, `http://gateway:80/slides/` (the presentation container is on `web_lab`, which the
  allocator is not on; the builder must find a URL that really returns 200 when slides work, and say what it is);
  plus workshop extras from env `STATUS_CHECKS` = `Label=URL` items separated by `;` (split each item at its first
  `=`). An extra is OK when it answers HTTP 200. No auth header is sent to any probe.
- State per service, colour decided by the allocator (not by the service): **green** = last probe OK. Not OK:
  **yellow** if it has never been OK since allocator start and less than `STATUS_STARTUP_GRACE_SECONDS` (default 300)
  have passed, or if it was OK within the last `STATUS_LOSS_GRACE_SECONDS` (default 30); otherwise **red**. Each
  service also has a short `detail` string (the probe error, or `detail` from a JSON body if present); `null` when green.
- `GET /admin/api/status` (facilitator only, like `/admin/api/sessions`; Caddy's `/admin*` basic_auth already gates it and
  the allocator's `gateway_authorized()` check runs first) returns
  `{"generatedAt": "<ISO-8601 UTC>", "services": [{"name": "...", "state": "green|yellow|red", "detail": null|"..."}]}`,
  served from the snapshot. Before the first probe completes, every service is `yellow` / `"waiting for first check"`.
- `/admin` page: a compact strip of services, each with a coloured dot **and** a word (Ready / Starting / Down) so colour
  is never the only signal, name, and `detail` as a tooltip; polled with the page's existing 5 s refresh. Build DOM with
  `textContent` only (names and details are data), never `innerHTML`.
- Test overrides: the three `STATUS_*_SECONDS` variables exist so a test can shorten the timings.

**C. cloud-api** (`compose/cloud-api/`).
- `GET /readyz` on the plain-HTTP port, unauthenticated (like `/healthz`), returns HTTP **200** only when ready, else
  **503**, with JSON `{"ready": bool, "state": "ready|starting|unavailable", "detail": "<fixed string>"}`. Ready =
  cloud-host's Docker answers **and** `dojo/hello:1.0` and `:2.0` are present **and** the startup reconcile has finished.
  `starting` = never ready since cloud-api started; `unavailable` = was ready, is not now. Computed by a **background
  thread every ~3 s**; the handler reads the cache (no Docker call per request, never under `State.lock`).
  `/healthz` keeps returning 200 whenever the process is up (it is the container healthcheck).
- `main()` currently blocks up to 60 s pinging Docker *before* it starts listening. Change it: create PKI and the app,
  **start both servers immediately**, and run "wait for the host, then `reconcile()`" in the background, retrying until
  it has worked once (reconcile is skipped, not fatal, while the host is down).
- While the host is not ready, ARM writes (PUT/PATCH/DELETE of container groups AND resource groups: `apply` sends the group first, so refusing it fails the whole run before anything changes) and the portal's delete/tag actions
  answer an ARM-shaped **503 `ServiceUnavailable`** ("Dojo Cloud is not ready" or "... is unavailable") *before* mutating
  any state, so nothing is half-recorded. Reads keep working. Also fix the two paths that let a `DockerError` escape
  (`executor.remove(existing[...])` in `put_container_group`; `delete_container_group` pops the record before it removes).

**D. Overlay and terminal** (`compose/docker-compose.override.yml`, `compose/terminal/entrypoint-wrapper.sh`).
- `web-terminal` `depends_on: cloud-api: condition: service_started` (was `service_healthy`);
  `cloud-api` `depends_on: cloud-host: condition: service_started` (was `service_healthy`).
- `allocator` gets `STATUS_CHECKS=Dojo Cloud=http://cloud-api:8080/readyz` (the overlay may set it; no base compose edit).
- The wrapper's CA-bundle step becomes a **background loop with no timeout** (wait for the CA and signing key, write
  `/etc/dojo/ca-bundle.pem` atomically, stop). It prints one "Dojo Cloud not available yet, Track A works" line after 60 s
  and keeps waiting. The header comment must stop claiming more than the code does. The broker already tolerates a late key.
- Because a shell captures `ARM_*` when it starts, a shell opened before the cloud was ready needs a **new terminal tab**
  (Lab 4 already says so; the facilitator guide says to tell the room when the Dojo Cloud dot goes green).

*As built and live-tested (2026-09-21), deviations from the contract above:* the Slides probe goes through the gateway with the
scheme, port and Host of `PUBLIC_BASE_URL` (plus a non-empty-body check) because `gateway:80` reads a false green or a permanent red; the Terminals
probe is `GET /status` with the control token through the same probe helper; `/readyz` detail says "not ready" (not "still starting") so a red chip
never reads "starting"; resource-group `PUT` and reads of resource groups still work while the host is down, but **container-group reads answer 503,
not 200** (T8.9); credentials do not depend on `cloud-host` (cloud-api creates the CA and key on its own), so the "new tab" case is a `cloud-api` that
started after the shell; the broker returns nothing until `/etc/dojo/ca-bundle.pem` exists; the allocator now reads the whole 200 body in a probe
(closing with unread data made `cloud-api` log a `ConnectionResetError` traceback about every 5 s).
*Later the same day (T8.9):* container-group reads no longer 503 while the host is down (they answer from the stored record), ARM writes that cannot proceed answer
`NOT_READY_STATUS` (409) with an actionable message instead of 503 (the provider retried 503 for minutes), student containers use `unless-stopped`, and the portal
shows `Unknown` after 10 s without a Docker answer.

---

### 5.8 Lock narrowing — T9.7 contract (2026-09-21)

**Goal:** no Docker call is ever made while `State.lock` is held. Two places still do it: `Handler.put_container_group`
(the old container's `remove` and the new one's `create`) and the resource-group `DELETE` in `Handler.resource_group`.
Reads (`get_container_group`, `cg_list`, `cg_views`) and `App.delete_container_group` are already outside the lock.
**Mechanism: reserve → Docker → commit**, all in `server.py` and `state.py`:

- `State.pending`: `{cg_key: {"sub", "port", "dnsLabel"}}` for container groups with an operation in flight (a PUT that
  creates/replaces, an ARM or portal DELETE, and every child of a resource group being deleted). `State.deleting_rgs`:
  set of rg keys being deleted. Both in memory only (a restart mid-operation is what `reconcile()` already handles).
- **Phase 1, under the lock:** everything that is decided today (rg exists, JSON, policy) with the reservations counted:
  the quota's `others` and `dns_taken` include pending groups, `free_port()` skips pending ports. If the key is already
  pending, or its rg is in `deleting_rgs`, answer `arm_error(409, "Conflict", "Another operation on this container
  group is in progress. Wait for it to finish, then try again.")` and change nothing. Otherwise record the reservation.
- **Phase 2, no lock:** `executor.remove` (old container), `executor.create`.
- **Phase 3, under the lock, in a `try/finally` so a reservation is ALWAYS released:** commit or record the failure
  exactly as today. Status codes, error bodies, activity-log operation names and messages, "old container already gone →
  forget the record when create fails", and the 409 `ServiceUnavailable` host-down text must not change.
- **Resource-group DELETE** claims the rg and every child key in phase 1 (409 if a child is pending or the rg is already
  being deleted); removes containers in phase 2; on a `DockerError` drops only the records whose container was removed,
  logs `Failed`, releases, and answers today's host-down 409; on success drops the child records and the rg, logs, saves.
  A container-group PUT into an rg that is being deleted gets the 409 above.
- **`App.delete_container_group`** (ARM and portal) claims the key the same way; the portal shows the same message.
- **The GET drift path** (`Container disappeared outside IaC`) must not delete a record whose key is pending (a replace
  removes the old container while its record still exists); in that case answer the stored record as it does when Docker
  cannot be asked.
- **Audit every iteration over `st.cgs` / `st.rgs` / `st.data["activity"]`** (§15a-G5): each must be under the lock or over
  a snapshot, because commits now interleave with readers.
- **Tests (new `test_concurrency.py`, fake executor with a controllable delay/barrier; every existing test still passes
  unedited, or the edit is explained):** N parallel PUTs from N subscriptions finish in about one executor delay, not N;
  a GET and a portal overview during a slow create answer in well under the delay; 5 parallel PUTs from one subscription
  (quota 2) → exactly 2 succeed; 10 parallel PUTs get 10 distinct ports; two PUTs for the same DNS label → one wins; two
  PUTs for the same key → one 201, one 409; PUT vs. rg DELETE (both orders) → 409 and no orphan record; an executor failure
  releases the reservation (a retry succeeds and reuses the port); a GET during a replace does not log "disappeared".

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
| Network isolation | `cloud-host` only on `cloud_net` (`internal: true`); not on `workshop_lab`; no ports published; no internet. Student containers: `--icc=false`, plus an iptables `DOCKER-USER` rule that drops NEW connections initiated from `docker0` (added 2026-09-21: without it a container could reach `cloud-api` through dind's NAT). Verified by `tests/e2e.sh --only security` |
| No Docker API for students | (T2) students only speak ARM to cloud-api; executor uses a **fixed template** (image from allow-list, memory/CPU/pids caps, no privileged/mounts/host net/caps, read-only rootfs where possible, restart policy `unless-stopped` so containers survive a cloud-host restart) |
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

**Authoring notes (learned in P7):** (a) **no emoji-range characters** (e.g. `↔`, `→` is fine): Marp swaps them for
twemoji `<img>` tags fetched from jsdelivr, an external request in an offline lab; (b) Markdown is **not** processed
inside raw HTML like `<p class="tag">`, so write `<code>` there, not backticks; (c) a `two-column` block splits
paragraphs mid-sentence, so use it only for short bullet lists; (d) the shared themes must set the
`--color-prettylights-*` variables on `section`, not `:root` (see `82b9e36`); (e) `hcl` fences render but get no
colouring (Marp has no HCL grammar); (f) render check without the stack: `podman run --rm -v <dir>:/home/marp/app:Z
docker.io/marpteam/marp-cli:v3.4.0 <file>.md --html </dev/null` (make `<dir>` world-writable and copy
`workshops/assets/themes` to `<dir>/assets/themes`), then screenshot with Windows Edge headless from WSL.

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
| `engine/scripts/capacity-calc.sh` | **not edited.** It already has `--other-services-mb`; `FACILITATOR.md` tells the facilitator to pass `6400` (3072 engine + 3072 cloud-host + 256 cloud-api) so the engine stays workshop-agnostic (T8.2) | none |
| `engine/README.md` | `/cloud` route row, "Workshop hooks" (`CLOUD_ENABLED`, `STATUS_CHECKS`), Forgejo password on the landing page, status strip (done, T8.5) | docs only |
| `engine/allocator/server.py` | **second edit (2026-09-21, user-approved):** the student landing page shows the Forgejo password (`no-store`); a background probe thread and `/admin/api/status` feed a facilitator-only status strip on `/admin` (§5.7 A/B); `STATUS_CHECKS` for workshop extras | always on for every workshop (the password panel and the strip); request path unchanged and still single-threaded |
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
- [ ] **T6.4** *(optional — skip unless the user asks)* Stretch labs 11–12.

### P7 — Slides

- [x] **T7.1** *(`d750be5`; 23 slides; rendered by the real Marp container, every slide screenshotted in headless Edge)* `presentation.md` per §10 outline; render with the presentation
      service. *Verify:* visible at `/slides`, links from `index.md` work.
- [x] **T7.2** *(`d750be5`; hub links and "← Hub" footers all return 200)* `index.md`, `labs.md`, `cheat-sheet.md` slide/lab hubs.
- [x] **T7.3** *(`d750be5`; notes on most slides; timings from the lab README, talk times are estimates)* Speaker notes, timing marks.

### P8 — Docs, registration, capacity, delivery

- [x] **T8.1** *(2026-09-21, committed `e0e6bff`; unit tests 90 + 5 re-run, links and code claims cross-checked, nothing run live)* Workshop `README.md`: what it is, architecture, security notes,
      how to reset, how to add a policy/image, troubleshooting.
- [x] **T8.2** *(2026-09-21, committed `e0e6bff`; no engine edit)* `capacity-calc.sh` sizing: the existing `--other-services-mb 6400` flag covers `cloud-host` + `cloud-api`
      (checked: 30 students on 32 GB → total 30346 MB, up from 27018 MB); documented in `FACILITATOR.md` and §14.
- [x] **T8.3** *(2026-09-21, committed `e0e6bff`)* Facilitator guide `FACILITATOR.md` (run-of-show, timings, pre-flight, progress-board stages, common failures, Purge,
      restarting parts, fallback to Track A). Deliberately not under `content/`, which is seeded to students.
- [-] **T8.4** *(not applicable: `infra/` is absent and the docs no longer reference Azure-VM delivery, `45afcb7`)* If `infra/` exists: add `tofu-basics.tfvars`, bump VM size if
      needed. Revisit only if that delivery path comes back.
- [x] **T8.5** *(2026-09-21, committed `8ce91e2`; the user approved engine edits on 2026-09-21)* `engine/README.md`: `/cloud` route row, a "Workshop hooks"
      section (`CLOUD_ENABLED`, `STATUS_CHECKS`), the landing page's Forgejo password, and the facilitator service-status strip.

- [x] **T8.6** *(2026-09-21, committed `8ce91e2`, `72b85fc`, `e0e6bff`; live-verified on tofu-basics, git-fundamentals and cert-autorenewal)* Landing page shows the student's **Forgejo password** (always on, `no-store`,
      escaped); labs 3, 10 and git-fundamentals lab1 refer to it. Live: the panel value matched `STUDENT_PASSWORD` and a real `git push` with it
      worked (a wrong one was refused); no other secret on the page; non-facilitator `/admin/api/status` refused. **Not run live:** escaping
      with a special-character password (offline check with `<b>&"x` only) and `no-store` on the `POST /assign` call site (read from code).
- [x] **T8.7** *(2026-09-21, committed `8ce91e2`; live-verified)* Facilitator-only service status strip on `/admin` (background probe thread, `/admin/api/status`,
      `STATUS_CHECKS` for workshop extras). Live: all four chips green on a warm start (Forgejo +5 s, Slides +30 s, Dojo Cloud +36 s,
      Terminals +66 s); Slides chip yellow then red 30 s after the presentation container was stopped, green again 3 s after restart; Dojo Cloud
      yellow then red 31 s after `cloud-host` stopped; red after the 304 s start-up grace when the host could not start; seen in Edge (green,
      yellow, red, dark mode). The Slides probe goes through the gateway with the public Host/scheme (`gateway:80` reads a false green). **Not
      checked:** the Terminals chip turning red, the chip tooltip, light theme, 420 px width (chips wrap and one looked clipped).
- [x] **T8.8** *(2026-09-21, committed `72b85fc`; live-verified, with two open issues: T8.9)* Start-up decoupling: terminal and cloud-api `depends_on: service_started`, wrapper CA loop,
      `cloud-api` `/readyz`, background host wait + reconcile retry, 503 guard while the host is down. Live: with a host that OOMs at start
      (`CLOUD_HOST_MEM_LIMIT=16m`) everything else came up healthy, Track A ran offline, `/readyz` said 503, and `podman update --memory 3g` +
      `restart` on the host brought Dojo Cloud green without touching the rest. With `cloud-api` itself crash-looping (`CLOUD_API_MEM_LIMIT=8m`) the
      terminal still started, the 60 s notice printed, a shell opened meanwhile had no `ARM_` vars, and after recovery only a NEW shell had them
      and `curl` worked without `-k` (proves the wrapper loop and the broker withholding credentials). Container-group writes while down: 503 with
      nothing changed (ARM and portal). Not caught: the sub-second window where the CA and key exist but the bundle does not.
- [x] **T8.9** *(2026-09-21, committed `72b85fc`; live-verified)* Host outage and restart, decided with the user ("I don't love the idea of the lab freezing for minutes"; `unless-stopped`
      approved): (1) student containers use restart policy `unless-stopped`; (2) container-group reads answer 200 from the stored record when Docker is
      unreachable (`ASSUME_RUNNING`, byte-identical JSON so `plan` says `No changes`); (3) ARM writes refused or failed because the host is down answer
      `NOT_READY_STATUS = 409` (code string `ServiceUnavailable`) with an actionable message (the portal keeps 503); (4) `cloud-host`'s
      `/var/lib/docker` is the named volume `cloud_docker`, so `./run.sh stop` removes it; the 16 orphaned anonymous dind volumes left by earlier runs
      (~240 MB, all dangling and dind-shaped) were deleted by name. Live: host down: `plan` 6 s `No changes`, unchanged `apply` 3 s, replace/tag-edit/create/`destroy`
      each fail in 3 s or less on ONE request with the message intact (the provider does not retry 409; no other code needed testing); host restart: student
      container back Running by itself, site 200 again about 40-50 s after the restart, `plan` `No changes`, no student action; normal apply 38 s; stop
      (normal and after `podman kill workshop_cloud_host`) leaves no containers, volumes, networks or stray processes (`engine_workshop_lab` no longer survives
      stop). 126 + 5 unit tests at that point. **Then fixed here:** the portal kept saying `Running` for a container nobody could see (its status cache served the
      last list forever on a Docker error); it now keeps a stale list for `STATUS_STALE_MAX` = 10 s and then shows `Unknown` (+1 unit test, 127 total;
      the new test was not run against the old code, and the fix was not re-run live).
- [x] **T8.10** *(2026-09-21, committed `72b85fc`; live-verified)* `cloud-host` often failed its FIRST start after a hard stop while a student container was running
      (`failed to start containerd: timeout waiting for containerd to start`, exit 1, retried ~8 s later by `unless-stopped`): recovery took 40-50 s. Reproduced on a lone
      cloud-host rig with a student container inside (old image: 2 of 6 restarts failed; stop took 13.5 s and ended in SIGKILL, exit 137). Two changes in
      `compose/cloud-host/entrypoint.sh`: (1) remove the last run's leftovers before starting dockerd (`/var/run/docker`, `/var/run/docker.pid`, `/run/cloud/docker.sock`; a restarted
      container keeps its filesystem); (2) trap TERM/INT, forward it to dockerd, wait for it, exit 0 when asked to stop (PID 1 ignores TERM without a handler). And in
      `hello/entrypoint.sh` httpd is now a child that the script stops on TERM (as PID 1 of the site container it ignored TERM, so dockerd's shutdown waited out Docker's 10 s
      per site). **Result:** rig 0 failures in 14 restarts, recovery about 11 s (was 20-40 s); live stack (test agent, 7 cycles incl. simulated crashes): 0 containerd timeouts, `/readyz` 200
      again after 9-13 s, site back after 8-12 s, `plan` `No changes` every time, same container each time; plain `podman stop` 5.5-6.5 s, exit 0 (was 13.5 s, 137). **Which of the two
      changes fixed the timeout was not isolated**; both stay. **Found:** `podman kill` (and any hand `stop`) counts as a manual stop, so `unless-stopped` does NOT bring the host back:
      run `podman start workshop_cloud_host`. A crash (process killed from outside) is restarted by itself.

### P9 — Validation → **M4, M5**

- [x] **T9.1** *(2026-09-21: RAN LIVE, 1 student, all areas: 281 checks, 0 failed, 0 skipped, 937 s (`tests/e2e.sh`, then the restart area, 11 checks, 142 s). It passed at the first attempt, so the scripts and labs agree; see the 2026-09-21 log entry. Still open: the browser (T9.9) and other students' labs (T9.4))* Automated e2e script in `tests/`: for a student user run Track A
      and Track B commands, assert outputs, assert cleanup.
- [x] **T9.2** *(2026-09-21: offline fuzz (`test_fuzz.py`, 8 fixes) and the live `security` area (`tests/e2e/60_security.sh`): 42 checks pass. The live run found one real hole, fixed: a student container could open connections to `cloud-api` (8080 and 443) through dind's NAT; `cloud-host/entrypoint.sh` now drops NEW outbound connections from `docker0`, fail closed. Not covered: Caddy's header handling (gateway) and docker proper)* Security checks: cross-tenant access denied; fuzz executor;
      student cannot reach `cloud-host`, cannot read signing key, cannot
      escalate through any documented endpoint.
- [~] **T9.3** *(2026-09-21: `tests/load.sh` ran live at 5, 10 and 15 students, all PASS: 0 failed steps, apply p95 51 / 69 / 76 s, portal overview p95 24 ms at 15, no OOM. Peak memory at 15: `workshop_terminal` 1.2 GB, `cloud-host` 0.16 GB, `cloud-api` 0.04 GB. **M4 (15) reached; 30 not tried** (`STUDENT_COUNT=20` on this box, so 20 is the next step))* Load test with demo bots (`--test`): N students × full flow. **M4**
- [ ] **T9.4** Human dry-run with 3–5 people; collect confusion points; fix labs.
- [x] **T9.6** *(2026-09-21: the scripts are committed under `tests/` and ran green live, see T9.1)* Turn the throw-away P3 checks into **committed** e2e scripts under
      `workshops/tofu-basics/tests/` — the lifecycle run (init/apply/tag edit/replace/quota/drift/destroy/restart)
      and the policy-violation run currently exist only in a lost session scratchpad (§15a-F). Include the
      live missing-tag check and the `CURL_CA_BUNDLE` check. The P5 and P6 verification runs were scratch scripts too (not committed).
- [x] **T9.7** *(2026-09-21: unit-tested (§5.8, `test_concurrency.py`) AND measured live: 15 concurrent students, apply p95 76 s (dominated by the provider's own poll ticks), overview p95 24 ms, max 1.5 s, no failures. Uncommitted)* Concurrency: 30 students applying at once against one global lock (§15a-F) —
      measure `apply` latency; if bad, narrow the lock (per-subscription) or move Docker calls outside it.
      **P4 measured a concrete instance:** `put_container_group` holds `State.lock` while Docker creates the container, so every portal read and every other student's ARM call stalls ≈3.3 s per deploy (§15a-G1). Do this fix here — reserve quota+port under the lock, create outside it, then commit.
- [~] **T9.8** *(2026-09-21: RAN LIVE on rootless podman: `enable_icc=false`, container-to-container blocked (with a working control), no route from a student container to the Docker API or, after the fix, to `cloud-api`; a real deployed container has no privileges or caps, `no-new-privileges`, and non-zero limits. **Still open: repeat on docker proper (the VM), where privileged is much closer to root.**)* Isolation checks: `--icc=false` really blocks container-to-container
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
- [~] **F.3** *(2026-09-21: cert-autorenewal confirmed live: `workshop_terminal` `(unhealthy)`, `wget` gets 403 without `X-Control-Token`; dns-as-code not run)* *Verify first:* run `./run.sh dns-as-code` and `./run.sh cert-autorenewal`
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
  256 MB. Both are covered by `./run.sh capacity --students 30 --other-services-mb 6400` (T8.2, `FACILITATOR.md`).
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

- **Not built yet:** committed e2e/load
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
5. **Container-to-container isolation on `cloud-host` is unverified.** **UPDATE 2026-09-21: verified live on rootless podman (T9.8); it found and closed the container-to-`cloud-api` path. Still unverified on docker proper.** *Reasoned:* dockerd runs with
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
   during a deploy; simultaneous deploys queue. **Fixed in T9.7 (2026-09-21, §5.8): unit-tested only, not yet measured live.** Portal reads themselves are fast (30 parallel class overviews: p95
   258 ms; 30 pollers every 3 s: p95 186 ms). **Fix in T9.7** before the 30-student test.
2. **The hello image was silent**, so the Logs tab was always empty — fixed in `49c168e` (startup line + `httpd -v`).
   *Verified* in plain busybox only; the log **framing** through the executor was checked with a container that
   prints. **Re-check the Logs tab once after the next full image rebuild.**
3. `Handler.log_message` raises `AttributeError` on a malformed HTTP request line — only a thread traceback in
   the log (existing code). Low priority. **CLOSED 2026-09-21** (the offline fuzz found it killed the handler thread with no reply at all; see §16).
4. The container-group `owner` **tag value is not validated** — a student can claim any owner name in the tags
   (the *real* owner is the subscription, so authz is unaffected). Still open: the P6 labs do not rely on it, so no policy was added; decide only if a lab needs it.
5. The ARM list endpoints read state without the lock (existing code). Benign today; fold into T9.7. **CLOSED 2026-09-21** (the rg list and `site()` lookups now take the lock).
6. `_body()` reads at most 1 MB and leaves any excess unread on the socket (existing code). Low priority. **CLOSED 2026-09-21** (the connection is closed instead; the leftover bytes were parsed as a second request).
7. **Portal identity relies on `GATEWAY_TOKEN`** reaching cloud-api via the overlay. Verified a bare
   `X-Auth-User` is rejected (401) and the token is not in student environments or `/proc/1/environ`. The
   allocator-style trust model only holds if the Caddy block sets both headers with `header_up`; **it does (P5), verified against an echo upstream with forged headers.**
8. Facilitator username in this dev `engine/.env` is `admin` (not the `root` default) — the code reads
   `FACILITATOR_USERNAME`, so nothing to fix; just don't hard-code `root` in labs.
9. Anonymous podman volumes from earlier runs survive `./run.sh stop`. **Fixed for `cloud-host` in T8.9** (its `/var/lib/docker` is now the named volume `cloud_docker`, verified: zero volumes left after stop); 16 orphans (~240 MB) were deleted on 2026-09-21. Other services' anonymous volumes were not checked.
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

### 2026-09-21 — P7 slides (`d750be5`)
- User approved P7 at the phase gate. Wrote `presentation.md` (23 slides, §10 outline), `labs.md`, `cheat-sheet.md`
  and the real `index.md` hub; a sub-agent rendered them on a live stack (real Marp container, all four served, every
  link 200, all 46 slides screenshotted) and reported findings; I checked them against the files and fixed four in the
  same commit: a two-column slide splitting a paragraph, literal backticks in the hub tagline (`<p>` HTML is not
  Markdown), `↔` (Marp turns it into a jsdelivr twemoji image, an external fetch in an offline lab: **avoid emoji-range
  characters in slides**), a stray gap on the cheat-sheet.
- **Timing correction:** the lab README's estimates sum to 37 + 66 min, so with the talk the session is about 2¼ hours,
  not 2. The deck says so and its notes name what to trim (Lab 9, Lab 8's optional section).
- **Not fixed (shared theme, not this workshop):** `whoami` in `sh` fences is dark orange on the dark background in
  `labs.css` (highlight.js builtin colour); `dns-as-code/labs.md` shares it, so probably affected too (not rendered).
  The Marp container also logs "Cannot register theme CSS" for the four shared themes; harmless (they load via
  `@import`), not checked against another workshop.
- **Not verified:** the four fixes after the render (text-only edits, not re-rendered); the `/admin` Slides tab;
  students' browsers (only Windows Edge was used); nobody has presented it.
- **Next:** ask the user before the next phase. Candidates: P8 (README, `capacity-calc.sh`, facilitator guide) or T9.9 /
  T9.7 (browser pass, lock stall) which carry the larger unverified risk.

### 2026-09-21 — shared theme fix, CLAUDE.md, P1–P7 audit (`82b9e36`, `2c35a9b`)
- **Theme (`82b9e36`):** root cause of the `whoami` colour was broader than one word: the `--color-prettylights-*`
  overrides sat on `:root`, but the themes load via `@import` (so `:root` is `<html>`) and Marp's default theme sets the
  same variables on `<section>`, which beats an inherited value even against `!important`. **None** of our syntax colours
  applied. Moved to `section` in `labs.css`, `presentation.css`, `cheat-sheet.css` (all workshops share them). Rendered and
  looked at: tofu-basics `labs` slide 2 and `presentation` slides 7 and 9, plus a `dns-as-code` cheat-sheet `js` slide
  (colours now dark-theme correct, no regression). The other workshops' remaining slides were not re-rendered.
- **CLAUDE.md** (local, git-ignored): D2–D6 now described as confirmed on 2026-09-19.
- **README stub** no longer says Track B is in progress (`2c35a9b`); the full README is still T8.1.
- **Audit of P1–P7 (no live testing):** every SHA cited in this file exists in git; the only unticked task in P1–P7 is the
  optional T6.4; 90 + 5 offline tests pass; slide claims cross-checked against the portal (`Class view`, `Refresh now`,
  `Browse`, `Activity log`, …), the pinned OpenTofu version, and the facilitator `/admin` Dojo Cloud tab code.
  **Nothing in P1–P7 is blocked or half-done.** What remains open inside those phases is either live-only or assigned to P9:
  - *Live only (user will run):* HCL highlighting in code-server (T1.3/T9.9); Labs 0–3 on the current image; a real-browser
    pass over the portal and Labs 4–10 (T9.9); the attention-tile `code: message` text; the `/admin` Slides and Dojo Cloud
    tabs; isolation under docker proper (T9.8); arm64 image build; the 30-way concurrent apply (T9.3).
  - *Offline-doable but deliberately left in P9:* a fuzz test of raw ARM bodies against the executor (T9.2/T9.6); the
    lock-held-during-Docker fix (T9.7, code change that needs a live re-measure); committing the throw-away e2e scripts (T9.6).
  - *Owner's call, not this workstream:* §15a-H8 engine notes (presentation image rebuilt every run, leftover
    `engine_workshop_lab` network), follow-ups F.1–F.7 (other workshops' healthchecks, unpinned images, commit `a24f08b` review).
  - *Known limitation in the labs:* they say `<class-address>` because the dev portal URL lacks the port (§15a-C).
- **Next:** P8 (T8.1 README, T8.2 `capacity-calc.sh`, T8.3 facilitator guide, T8.5 `engine/README.md` note); T8.2 and T8.5 edit
  `engine/` files, so ask the user first. Ask at the phase gate before starting.

### 2026-09-21 — P8 docs, facilitator guide, capacity (committed 8ce91e2 / 72b85fc / e0e6bff)
- User asked to start P8 with the README (that is the phase-gate go-ahead). Wrote the full workshop `README.md` (T8.1: what
  it is, layout, architecture, policy table and how to change a limit / add a rule / add an image, security model, reset
  table, tests, known limits) and a new `FACILITATOR.md` (T8.3: run-of-show, pre-flight, progress-board stages, timing
  notes, failure table, restarting parts, Track A fallback). The guide sits beside the README, not in `content/`,
  because `content/lab/` is seeded into every student's home.
- **T8.2 without touching the engine:** `capacity-calc.sh` already takes `--other-services-mb`; passing `6400`
  (3072 for the four engine services + 3072 cloud-host + 256 cloud-api) raises the 30-student plan from 27018 MB to
  30346 MB (`--host-mem-mb 32768` run). The guide tells the facilitator to pass it; no engine file was edited. If the
  user wants it automatic, that needs an engine change (a per-workshop extra-memory setting), which needs their OK.
- **Checked:** 90 + 5 offline tests pass; every link in the two files resolves; executor template flags (CapDrop ALL,
  no-new-privileges, not privileged, pids 64) match the README; the portal's Facilitator panel is on Home and the Class
  progress nav item is facilitator-only, as the guide says.
- **Found while writing:** Labs 3 and 10 tell students to push with `student123`, which is only the default of
  `./run.sh setup --default`; interactive `setup` generates a random `STUDENT_PASSWORD`. The guide now says so. Also
  the terminal container waits for a healthy `cloud-api`, so a broken control plane at start blocks the whole terminal.
- **Not verified:** none of the guide's procedures were run on a live stack this session (restarting `cloud-host`,
  `docker restart workshop_terminal`, the rehearsal steps). Claims are from code and earlier logged runs; the two
  untested restarts are labelled untested in the text. Wave-starting Lab 5 is a reasoned suggestion (§15a-G1), not a measurement.
- **Next:** T8.5 needs the user's OK (it edits `engine/README.md`). Then P9 (ask at the gate): T9.9 browser pass and T9.7
  lock fix carry the most unverified risk.

### 2026-09-21 — Forgejo password panel, facilitator status strip, start-up decoupling (committed 8ce91e2 / 72b85fc / e0e6bff)
- **Decisions (user):** show each student's own Forgejo password on their landing page (visible, `no-store`, escaped, always on, one name "Forgejo
  password" in the labs); terminal and cloud-api start on `service_started`; a facilitator-only status strip for all services (students see none);
  fix `git-fundamentals` lab1's hard-coded `student123` too; engine edits approved. Asked whether the allocator must stay single-threaded: it keeps a
  single-threaded request path (atomic slot claim) and gets one background probe thread instead of a new container.
- **How:** contract §5.7; two builder agents on disjoint files (allocator; cloud-api + terminal wrapper + overlay), I reviewed both diffs and added the
  broker change (no credentials until the CA bundle exists), then a third agent ran the live stack (7 tests, results in T8.6–T8.8 above). Unit tests:
  117 + 5 pass. Docs: labs 3/4/10 + lab README + git-fundamentals lab1, workshop README, FACILITATOR.md, engine README (T8.5).
- **Live results in short:** panel, strip and decoupling work (details on the task lines). Found and fixed here: `cloud-api` traceback every 5 s from the
  allocator's probe not reading the 200 body (fix verified by the test agent's measurement of the read variant against the real server; my own local
  repro could not reproduce the noise, and the edited probe was not re-run on the live stack); the red chip's tooltip said "still starting" (wording
  changed, tests updated); docs said a host restart deletes containers and `+ create` shows (the opposite is true) and that a shell opened while the host
  is down lacks credentials (it has them).
- **Open:** T8.9 (container-group reads hang `plan` ~4 min during a host outage; containers stay Exited after a host restart and `plan` says `No changes`).
  Other workshops: cert-autorenewal starts but its terminal is unhealthy (F.1/F.2, the stale restated healthcheck, now seen live) and its `step-ca`
  reports unhealthy (`step ca health` cannot resolve `step-ca`; not investigated). git-fundamentals is fine. dns-as-code was not run.
- **Not verified:** escaping with a special-character password live; `no-store` on `POST /assign` live; the Terminals chip going red; light theme and
  420 px width of the strip; real browser terminals (ttyd/tmux) and `--test` bots; Docker proper, arm64, concurrent students.
- **Security note:** during that live test an agent's `curl -w` echoed the shared browser-gate (`TTYD_*`) password into its own tool output. It is in that
  session's transcript, not in any repo file; rotate it if the transcript is kept or shared.

### 2026-09-21 (later) — host outage, restart recovery and stop hygiene (T8.9, committed 8ce91e2 / 72b85fc / e0e6bff)
- **User asked** how to avoid multi-minute freezes when the cloud host is down, what "host" meant (the `cloud-host` container, not the OS; an OS reboot has the same
  effect on student containers), approved `unless-stopped`, and asked whether `./run.sh stop` decommissions everything if a stop goes wrong. **Found while checking:** 16
  orphaned anonymous dind volumes (~240 MB) that `stop` never removed (deleted by name after checking each was dangling, anonymous and dind-shaped); fixed for the future
  with the named volume `cloud_docker`. Then: builder agent (restart policy, fast reads, fail-fast writes), me (overlay volume, portal cache), live-test agent.
- **Result:** see T8.9. The provider does not retry HTTP 409, so a write during an outage fails in about 3 s with the message intact; `plan` finishes in 6 s; a host restart
  recovers with no student action in about 40-50 s; stop, including after SIGKILL of `cloud-host`, leaves nothing behind.
- **Open then, closed next (T8.10, below):** slow first start after a hard stop, and the partial apply. **Not verified:** Docker proper, arm64, concurrency, a real browser.

### 2026-09-21 (later still) — T8.10 and the partial apply (committed 8ce91e2 / 72b85fc / e0e6bff)
- **User asked** whether anything can be done about the partial apply, and to fix T8.10. **Partial apply:** every ARM write, resource groups included, is now refused with the 409
  while Dojo Cloud is not ready (`resource_group()` checks `not_ready()` first; the old check on group DELETE was folded in; one test rewritten, 127 tests). Live: an `apply` that
  changed both the group's tag and the container group failed in 1.2-1.5 s on the FIRST request (a replace sends the container group's DELETE first), and a tag-only `apply` failed on the
  group's PATCH (409, 1.5 s); afterwards `plan` still showed both changes pending (nothing was half-applied), and after the host came back one `apply` (27 s) landed both. A run started 0.3 s
  after the stop began was refused too. What is left is inherent to Terraform: the host dying BETWEEN two requests of one `apply` (a re-run finishes it). **T8.10:** see the task.
- **Not verified:** Docker proper, arm64, concurrency, real browser, the old image against the new test (only the new image ran on the full stack).

### 2026-09-21 — P9 started: lock fix (T9.7) and offline fuzz (T9.2)
- **User:** "start on P9". Then, twice, that token use was too high ("Such high token counts will blow through my usage"): stopped the two running builder agents, chose the **minimal live run** (build the stack once, e2e, a small load run sized to this machine, the security checks; no browser pass or other-workshop regression until asked). Saved as a feedback memory (short briefs, logs to files, short reports).
- **T9.7:** built by one agent from §5.8 (reserve → Docker → commit; `State.pending`, `deleting_rgs`, 409 `Conflict` for a busy key), reviewed by me line by line. Known gaps left alone: portal Purge during an in-flight create; a tags PATCH during a replace (the replace commit wins); a resource-group PUT/PATCH during that group's DELETE. **Not run live.**
- **Fuzz (`test_fuzz.py`, 1,731 lines, from the agent stopped mid-work):** it failed 22 of 42 tests on the code as it stood. Real bugs found and fixed by me (each in the same change): (1) `log_message` read `self.path` before it existed, so a malformed request line killed the handler thread and got no reply (was §15a-G3); (2) **a tiny positive CPU/memory request passed the policy and became `Memory: 0` / `NanoCpus: 0` = UNLIMITED in Docker** (policy now has `MIN_CPU` 0.05 / `MIN_MEMORY_GB` 0.03125, and `build_create_request` refuses anything below); (3) `NaN`/`Infinity` passed the caps; (4) the name patterns used `$`, so `rg-foo\n` and an env name with a trailing newline passed (now `\Z`); (5) wrong-shaped JSON reached `policy.py` and answered HTTP 500 (now one `_shape_guarded` wrapper: 400); (6) 500s from a bad `Content-Length`, deeply nested JSON (`RecursionError`), non-ASCII client secret (`hmac.compare_digest`), and control characters in a `/cloud/site/` path; (7) body over 1 MB, or a bad `Content-Length`, left bytes on a kept-alive connection that were parsed as a second request (now the connection is closed; was §15a-G6); (8) unparsable requests got an HTML body with no status line (now a JSON error with a status line); plus two groups whose joined names give one container name (`rg-ab`+`ci-b-ci-cc` vs `rg-ab-ci-b`+`ci-cc`) now get a 409 instead of a 500. Test changes: the harness self-check now expects the builder to refuse 1e-12, blank request lines are not required to be answered (RFC 9112), `505` is accepted for an unsupported HTTP version. One `expectedFailure` remains on purpose (builder-only defence in depth, not reachable over the network).
- **State:** 151 + 5 unit tests and 42 fuzz tests pass (the fuzz suite was run 4 times after the last edit). **Nothing is committed.** No live stack was started this session.
- **Drafts to treat with suspicion:** `tests/` (about 2,000 lines incl. a `selftest/` mock harness that may be more than needed) was written by an agent stopped mid-work; only `bash -n` was run on it.
- **Next (minimal live run):** rebuild the stack (`./run.sh stop`, then `./run.sh tofu-basics`), run `tests/e2e.sh`, a load run sized to the machine, and the security checks (still to be written, small); then T9.5 and T9.9 only if asked.

### 2026-09-21 (later) — P9 non-live work
- **User asked** which validation to run, whether 15 students fit ("gpu" taken to mean RAM), and what non-live work P9 still needs. **Fit:** `./run.sh capacity --students 15` says 19,141 MB needed against 9,945 MB detected. That is a
  limit-based plan for real IDE students, not a measurement; 15 scripted shells (no IDE) are unmeasured, so the run sheet ramps 5, 10, 15 and stops below about 1.5 GB free. **M4 redefined to 15** (30 needs a bigger box).
- **Done (all offline):** explicit policy tests for the new floor/ceiling, NaN/Infinity, trailing newline and structural surprises (`test_policy_auth.py`; whole suite 197 tests, one intentional `expectedFailure`); README/lab 6 policy tables
  and the FACILITATOR troubleshooting table (the new 409s); the `tests/` drafts reviewed and their selftest fixed (its mock wrote state to a different directory than the mock portal read, plus a miscount): 66 checks pass.
- **Real bug found in the drafts and fixed:** when `e2e.sh` or `load.sh` **refused** to run because a student's subscription was not empty, the exit cleanup still verified the portal and **purged that subscription**. Both now set
  `SAFE_TO_CLEAN` only after the refusal checks pass (`--cleanup-only` sets it itself); the selftest asserts a refused run leaves the state alone.
- **New:** the `security` area (T9.2 live half, T9.8): `tests/e2e/60_security.sh`, `helpers/sec_arm.py` (cross-tenant and forged-token probes, in the student's shell), `helpers/sec_deploy.py` (deploys and deletes one policy-clean container
  through ARM so a real container can be inspected). The two helpers were run against the real handlers with a fake executor: every status matched (403 across tenants, 401 for payload-swapped, `alg none`, wrong-key and borrowed-secret
  cases; deploy 201/201, delete 200). Key names avoid `token=` and `secret=` because the scripts' `mask()` would rewrite them.
- **Not done, needs a stack:** everything the user runs by hand (`tests/README.md` run sheet). Likely outcomes to watch: the bridge-to-`cloud-api` probe (a student container reaching `cloud-api` through dind's NAT is plausible and
  would be a genuine finding), `nobody` existing in the terminal image, `nc`/`wget` behaviour in busybox, and the first-contact fixes any 2,500-line shell suite needs. **Nothing is committed.**

### 2026-09-21 (later still) — P9 live run
- **User asked** to run the e2e, load and security scripts live and fix the likely first-run problems. Rebuilt the stack (`./run.sh stop`, `./run.sh tofu-basics`) and ran them.
- **Security area, first run: 40 pass, 2 fail.** (1) The probe used `.NetworkSettings.IPAddress`, which this Docker no longer has, and served `/` without an index (wget calls the 403 a failure): the test's own bugs, fixed, so the
  `--icc=false` result is now backed by a working control. (2) **A real hole: a student container could reach `cloud-api` on 8080 and 443** through dind's NAT (`--icc=false` only stops container-to-container). Fixed in
  `compose/cloud-host/entrypoint.sh` with a fail-closed `DOCKER-USER` rule (drop NEW connections initiated from `docker0`); verified by the rerun, published ports and sites still work, and the rule survives a cloud-host restart.
  Impact was limited (hello runs fixed code and `cloud-api` still needs tokens), but it was the path §15a-F5 worried about.
- **Full e2e (1 student): 281 passed, 0 failed, 0 skipped, 937 s**, then the restart area (11 checks, 142 s). **Load, waves of 5:** 5 / 10 / 15 students, all PASS, no failed step, no OOM. `apply` p95 51 / 69 / 76 s; `destroy` p95 79 s at 15; overview
  p95 24 ms; `/readyz` never non-200. **Peak memory at 15: terminal 1.21 GB (of 4 GB), cloud-host 0.16 GB, cloud-api 0.04 GB; the host stayed near 6 GB free.** So `./run.sh capacity` (19 GB for 15) is a plan for IDE students, and
  15 scripted shells are cheap. The unmeasured cost of a real class (IDE and browser per student) is the part not tested.
- **Commits:** `745f842` (lock narrowing, fuzz fixes, policy tests, docs), `4d243cf` (cloud-host outbound rule), `4a4729a` (`tests/`), then this plan update.
- **Nothing else needed fixing:** the scripts and the labs agreed on the first run. **Not tested:** 20+ students, docker proper, the gateway's own header handling, a browser (T9.9), other workshops (T9.5), real people (T9.4). **Uncommitted.**

<!-- Append new entries below this line. Format:
### YYYY-MM-DD — short title
- what was done (task IDs), commits (SHAs), decisions, surprises, next step -->
