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
| Overall status | **P0-P4 done (P4 committed 2026-09-25: 91031d6, 21daddf). Next: P5, after the user's go. Read "Where we stopped" in §0 first.** |
| Working branch | `feat/vault-fundamentals` (branched from `main` at `ebd0457`, after tofu-basics merged) |
| Last updated | 2026-09-25 (P3 done) |

---

## 0. HOW TO RESUME (read this first)

1. Read this whole file once.
2. `git status` and `git log --oneline -20`. Every finished task records its
   commit SHA (or "findings in §10") next to its checkbox in §11. If a box is
   ticked but the SHA is not in `git log`, treat the task as **not done**.
3. Check §1 (decisions) and §12 (open questions). Do not start work that
   depends on an open question. Read **§14 (Worth knowing)** for surprises and
   problems found along the way.
4. **Ask the user before moving from one phase to the next** (P0 → P1 → P2 …).
   Ask before editing any `engine/` file, even for a spike.
5. Find the first `[ ]` or `[~]` task in §11. Before starting it, run the
   **Verify** line of the previous finished task to make sure the foundation
   still holds.
6. Work the task. When finished: tick the box, add the commit SHA, and append a
   dated entry to §15. If you learned something that changes the plan, edit the
   relevant section — do not just note it in the log.
7. If you are blocked, mark the task `[!]`, say why in §15, and move to the
   next unblocked task.

### Where we stopped (2026-09-25): start here next

- **P4 is done** (T4.1-T4.8; 91031d6 `openbao-audit`, 21daddf app-host, app-db, labs 9-11). Passed locally:
  `tests/labs_9_11.sh` (student03, student01, and twice on student02, so a redeploy on a used slot is covered),
  `tests/p4_browser.py` (Apps page as student at 390 px and the facilitator's tab, labs 9-11 in the reader, Part 6
  slides + labs.md + lab-index within 16:9, screenshots looked at), unit tests (app-host 16, runner-pool 25), live
  security checks (forged / no-token deploys 403/401, sandbox CSP, each app PID 1 in its own namespace, other slots'
  files and tokens refused), and the earlier tests again: `cli_login.sh`, `tenancy.sh`, `labs_4_6.sh`,
  `labs_7_8.sh`, `pool.sh`. `./run.sh stop` leaves no `engine_` volume. The user approved the two `openbao` module
  changes (the `openbao-audit` service, unhashed accessors). **The user's own browser pass of P4 is still open**
  (My App card, `/admin` Apps tab, labs 9-11 in the reader, slides 28-35). The machine is free (stack stopped).
- **Next: P5**, ask the user before starting it.
- **P3 is done** (T3.1-T3.9; ee6e59b, 5be3d6e, fixes from the live run in d80e078). Verified locally on a fresh
  stack: `modules/runner-pool/tests/pool.sh` PASS (22 checks: warm pool, panel 403s and CSRF, two concurrent jobs
  that see nothing of each other, `bao`/`sops` in jobs, no files left in `/tmp`, a burst of 8 up to the max, Manual
  − / + and + refused at the max, runner users = live runners), `tests/labs_7_8.sh` PASS (every step of both labs,
  the branch refused, AppRole not), `tenancy.sh`, `cli_login.sh`, `labs_4_6.sh` still PASS, controller unit tests
  (25) PASS; in Chromium (Playwright): the Runners tab in `/admin` (no CSP errors, no horizontal scroll at 390 px),
  labs 7-8 in the lab reader, slides 22-29, `labs.md` and the lab index within 16:9. Pool memory peaked at 181 MiB
  over labs 7-8 (limit 2 GB). `./run.sh stop` left no container, network or `engine_` volume. **Next: P4**
  (deployments, `app-host`, labs 9-11) once the user says go; its task block isn't written yet.
- **Not checked by hand:** the Runners panel's look beyond screenshots, and a person walking labs 7-8 in the
  browser UI (the tests make the UI's secret steps with the same API calls).
- **P0 is done** (results in §10). **P1 is in progress** (the user said go and answered Q4/Q5 as S31/S32).
- **Done in P1:** T1.1 (`modules/openbao/`, OpenBao 2.7.0), T1.2 (`openbao-setup`, 33e1d36) and T1.3 (SSO,
  ca89792 + 82ff676): the vault comes up initialised and unsealed, root revoked, SSO through Forgejo set up, and
  re-unseals itself within about 10 s after `podman restart workshop_openbao`. The provisioner token is at
  `podman exec workshop_openbao_setup cat /setup/provisioner-token`. The SSO browser test is
  `modules/openbao/tests/sso_browser.py` (the command is in its header).
- **The stack is stopped** and every volume is gone. The user also validates other workshops (e.g. `dns-as-code`)
  on this machine: **check `podman ps` before starting a stack, and tell the user when the machine is free again.**
- **P2 is done** (T2.1-T2.6, 1f8d7c5 and 9ed5f8f): labs 4-6, their slides, `tests/labs_4_6.sh`. Verified locally
  2026-09-25 (details in §15). **Next: P3 (pipelines: `runner-pool`, labs 7-8). Ask the user before starting it.**
  The stack was left **running** at the end of P2.
- **P1 is done** (T1.1-T1.7). The live pass ran locally on 2026-09-25: `cli_login.sh`, `tenancy.sh` and
  `sso_browser.py` pass, labs 0-3 were run as a student (terminal and UI), slides fit 16:9. The stack is stopped.
  Not run on `--env home` this time (T1.3 was; nothing in T1.4-T1.6
  depends on the public name).
- `spike/t09-sops.sh` can't run now: it needs a token that can use transit keys (facilitator after T1.3/T1.4, or a
  student's after T1.5); root is revoked and the provisioner can't.
- **Local tests run in WSL on the user's desktop** (not a laptop): `http://localhost:8080`. The home HTTPS path is
  `./run.sh vault-fundamentals --env home` (https://dojo.macleodtech.ca).
- **`engine/` changes on this branch:** a24d0e7 (`run.sh --env` fix) and ca89792 (`/forgejo-login?next=`, S32),
  both committed and self-contained, so either can be cherry-picked to `main`.

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
| S14 | *(Done by `feat/workshop-modules`, S25.)* **Engine changes go through a new general "workshop extensions" mechanism** (option B, §8.1): a workshop declares its own landing cards, `/admin` tabs and gated routes. No more per-workshop flags. |
| S15 | **The Runners panel starts every class in Auto.** |
| S16 | **Runner isolation: the process pool** (§6.2 A), with **Docker-in-Docker as the fallback** if it fails P0. Chosen to balance security and resource use. |
| S17 | *(Done by `feat/workshop-modules`, S25.)* **The extensions mechanism is foundational.** Once it's proven, **every workshop moves onto it** (`CLOUD_ENABLED` and `DEMO_APP_ENABLED` retired), each re-tested on the real stack. Design its format so it can later describe reusable **modules** too (§13). |
| S18 | **Lab count follows the concepts, not the clock** (2026-09-23): use as many labs as it takes to cover the concepts properly; S6's 2-3 h is a guide, not a cap. Core: every lab except **lab 10 (dynamic database credentials), which is optional**. Lab 6 (`sops`) and lab 7 (Actions secrets) are core. |
| S19 | **Labs 8-9 start half-configured** (2026-09-23): setup has already enabled and pointed the JWT auth methods in each student's namespace; students write the role (bound claims) and the policy. |
| S20 | **CI logs in to OpenBao with plain scripts, no `uses:` actions** (2026-09-23): the job fetches its OIDC token with `curl` and runs `bao login`. The runners have no internet. A slide shows how you'd do it at work with a ready-made action. Mirroring a small pinned set of actions into Forgejo is a follow-up (§13). |
| S21 | **P0 T0.4 uses an uncommitted local edit** to `engine/gateway/Caddyfile` for the `/ui/*` and `/v1/*` routes, reverted after the spike (2026-09-23). *(Superseded by S26: the routes come from `extensions.json`.)* |
| S23 |  **UI single sign-on reaches Forgejo's issuer through an overlay-only "issuer shim"** (2026-09-23, answers Q1): a small Caddy container sharing OpenBao's network namespace answers for `PUBLIC_BASE_URL` and forwards `/git/*` straight to `git-server:3000`. On the VM, `extra_hosts` points the public name at it and it serves HTTPS with its own CA, which OpenBao trusts (`oidc_discovery_ca_pem`). No engine edit, no gate exemption. Fallback if it fails T0.5: token login in the UI, SSO on a slide. The VM's HTTPS path is only approximated until the P5 Azure VM run. |
| S24 | **Fix Forgejo's broken Actions token URL inside the lab, don't file upstream** (2026-09-23): the S23 issuer shim also runs in the runners' network namespace and maps `/git//gitapi/actions/...` to `/api/actions/...`, so jobs use `$ACTIONS_ID_TOKEN_REQUEST_URL` exactly as Forgejo gives it. No `dojo-ci-token` helper needed. Proven in T0.6. |
| S25 | **P0.5 and P6 are replaced by `feat/workshop-modules`** (user, 2026-09-24; its plan is `engine/MODULES-PLAN.md`). That branch built extensions (`extensions.json`: cards, `/admin` tabs, gated routes, status checks) and modules (`modules/<name>/`, listed in `MODULES=`), moved every workshop onto them and deleted `CLOUD_ENABLED`/`DEMO_APP_ENABLED`. **OpenBao becomes a module** (`modules/openbao/`, §8.1), so a later workshop (policy as code, cert-autorenewal's PKI) can reuse it. |
| S26 | *(User, 2026-09-24.)* **No `engine/` edit for the UI routes, even in the spike.** From T0.5 on, `/ui` and `/v1` come from an `extensions.json` (`shared` gate, which strips `Authorization` as the T0.4 edit did). T0.5 uses a spike manifest in the workshop folder; T1.1 moves it to `modules/openbao/`. The S21 stash is dropped. This also makes the `/admin` **Vault** tab testable in T0.5 (T0.4 couldn't). |
| S27 | *(User, 2026-09-24.)* **Don't use the `forgejo-runner` module.** Its runner is long-lived and scoped to one repo: the "considered, not chosen" pattern in the Appendix. The single-use pool, controller and Runners panel become **their own module, `runner-pool`** (P3), because nothing in them is vault-specific and `dns-as-code` could switch to it later. It repeats the two lines it needs from `forgejo-runner` (Actions on, `runner_net`); the two modules are never listed together. |
| S28 | *(User, 2026-09-24.)* **Split the issuer shim by job.** `modules/openbao/` gets a shim that only forwards `/git/*` to `git-server` (UI SSO, S23). `runner-pool` gets its own shim with the Actions ID-token rewrite (S24). Two small Caddyfiles instead of one module reaching into the other's folder. |
| S29 | *(User, 2026-09-24.)* **Module setup, then workshop setup, in one container.** `openbao-setup` (module) initialises, unseals, sets the UI headers, OIDC-to-Forgejo, one entity per student and the facilitator policy, then runs every `/etc/openbao-setup.d/*.sh` in name order and revokes root **after** them, with the provisioner token (§5.1) still in hand. The workshop mounts its hooks (namespaces, templated policy, seed secrets, the half-configured JWT mounts of labs 8-9) there from its overlay; `volumes` append. Same shape as the terminal's `start.d`, and no token has to cross between containers. |
| S30 | *(User, 2026-09-24.)* **Test the real HTTPS path at home, not only "approximately".** `./run.sh vault-fundamentals --env home` serves `https://dojo.macleodtech.ca` behind the home-lab Caddy: a real non-`localhost` HTTPS name, which is what T0.5's VM path needs. The P5 Azure VM run still happens. |
| S31 | *(User, 2026-09-24, answers Q4.)* **Use the latest OpenBao release**: 2.7.0 from T1.1 on (pins in §15). P0's scripts were re-run on it. |
| S32 | *(User, 2026-09-24, answers Q5.)* **`/forgejo-login?next=<local path>`**: a small, workshop-agnostic **engine** change (approved) so the Vault card and tab sign in to Forgejo first and SSO is one click. Only same-origin paths are accepted. Built in T1.3. |
| S22 | **P0 order: the biggest unknowns first** (2026-09-23): T0.6 (Actions OIDC) and T0.7 (one-job runners) run straight after T0.2/T0.3, because labs 8-9 rest on them. |

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
   never leaves the vault. Show who can decrypt, what a diff looks like, and rotating the transit key (then
   `sops rotate`). Teach the key URL with the namespace in its path (`$VAULT_ADDR/v1/students/<you>/transit/keys/sops`):
   sops stores it in the file, so decrypting needs no extra setting (T0.9).

**Part 5: Secrets in pipelines**

7. **Forgejo Actions secrets** (core, S18). A repository secret used in a workflow. Masking in logs, and how easily masking is
   bypassed (`base64`). Why a workflow from a pull request can steal secrets.
8. **CI logs in to OpenBao.** First with AppRole: it works, but the AppRole login secret is itself stored in the
   pipeline (secret zero). Then with the **job's own OIDC token**, bound to *this repo on the `main` branch*, so nothing
   is stored at all. A job on another branch is refused. The JWT auth method is already set up in the student's
   namespace (S19); the student writes the role and policy. The workflow uses `curl` + `bao login`, no `uses:` (S20),
   and a slide shows the ready-made action you'd use at work.

**Part 6: Secrets in deployments**

9. **Deploy with workload identity** (§5.6). The pipeline deploys the app to `app-host` but **cannot read the app's
   secrets**. The app proves its identity to OpenBao through the platform and gets its own secrets. Half-configured,
   as in lab 8 (S19).
10. **Dynamic database credentials** (optional, S18). The app gets a Postgres login made for it, with a lease. Watch it expire, renew
    it, revoke it. There is no shared database password left to leak.
11. **Incident drill (capstone).** "A token leaked." Use the audit log to find what it read, revoke it (and
    everything under it), rotate what it touched, and check that the app recovers by itself.

**Stretch:** response wrapping for handing over an AppRole login secret safely; the PKI engine for short-lived
certificates (ties in with `cert-autorenewal`).

## 5. Architecture

### 5.1 Services (split between the `openbao` module and the workshop, §8.1)

| Service | Purpose |
|---|---|
| `openbao` | One server for the class. Raft storage on a volume, UI on. |
| `openbao-setup` | One-shot: initialise, unseal, create the tenancy layout (§5.3), the auth methods (§5.4), the facilitator policy; then **revoke the root token**. Re-unseals after a restart. (The audit device is declared in `config.hcl`, not by setup: §14.) |
| issuer shims | Small Caddys, one in OpenBao's network namespace (`openbao` module, UI SSO) and one in the runner pool's (`runner-pool` module, ID-token URL fix); each answers for `PUBLIC_BASE_URL` there and forwards to `git-server` (S23, S24, S28). |
| `runner-pool` + `runner-controller` | CI runners (one job each at a time) and the controller that scales them and serves the Runners panel (§6). The `runner-pool` module (S27). |
| `app-host` | The deployment target: a small "platform" with one slot per student and a platform identity (§5.6). |
| `postgres` | A shared database for lab 10's dynamic credentials. |
| terminal image | Adds `bao`, `sops`, `gitleaks`, Python with `hvac`, and the identity broker for CLI login. All pinned and sha256-verified per architecture. Sets `VAULT_ADDR` next to `BAO_ADDR` (sops and `hvac` read the `VAULT_*` names) and `SOPS_DISABLE_VERSION_CHECK=1` (T0.9). |
| runner-pool image | `host`-label jobs run on whatever the pool image has, so it carries the same pinned `bao`, `curl`, `sops` and Python as the terminal. |

**No root after setup, but a provisioner.** Root is revoked once setup finishes. Re-running setup, resetting one
student or re-creating a namespace mid-class needs a scoped **provisioner** identity (a policy that can manage
`students/*` namespaces, the shared templated policy and the auth roles, but not read secrets), kept on the
setup-only volume.

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
  - The routes only exist when a workshop lists the `openbao` module (its `extensions.json`, §8.1).
  - The route must drop the shared Basic Auth header (`header_up -Authorization`, as `/git` does): OpenBao reads
    `Authorization` as a possible token.
- **UI login is single sign-on through Forgejo.** OpenBao's OIDC auth method uses Forgejo as the identity provider,
  so logging in is "Sign in with Forgejo". It's the same pattern as Entra ID at work.
  **Solved by the issuer shim (S23):** Forgejo's issuer is `${PUBLIC_BASE_URL}/git/`, and OpenBao must fetch that URL from *inside*
  the stack (discovery, token exchange, keys). On a laptop that is `http://localhost`, which inside the OpenBao
  container means OpenBao itself; on the VM the public name has no route from the internal `workshop_lab`, and
  `/git/*` sits behind the shared Basic Auth gate. The shim answers for the public URL inside OpenBao's own network
  namespace only, so the browser still goes through the gateway as normal.
- **CLI login is automatic.** The browser can't reach the terminal's `localhost`, so the CLI OIDC flow won't work.
  Instead, a broker in the terminal (the `SO_PEERCRED` pattern from tofu-basics D3) gives each Linux user a signed
  JWT, and `bao login -method=jwt` uses it. Setup links both logins to **one identity entity** per student, so the
  same policies apply to both.
- **Facilitator**: the same OIDC login with the facilitator account gets the facilitator policy. The `/admin`
  workspace gets a **Vault** tab.
- **Verified in T0.4 (2026-09-24):** `/ui/*` and `/v1/*` through the gateway work for a student and the facilitator
  (401 without the gate login; a Basic Auth header alone gives OpenBao's 403, so it isn't taken as a token). The UI
  ships `Content-Security-Policy: ... frame-ancestors 'none'`, so **`openbao-setup` must set**
  `sys/config/ui/headers/Content-Security-Policy` to the same policy with `frame-ancestors 'self'`. With that, the UI
  renders and signs in inside a same-origin iframe (real Chromium). The UI keeps its token in memory, not
  `localStorage`, so every tab or frame signs in separately: SSO (T0.5) makes that one click.
- **Verified in T0.5 (2026-09-24), locally (WSL on the desktop) and `--env home` HTTPS, real Chromium:** a student and the facilitator
  (inside the `/admin` Vault tab) sign in with "OIDC Provider", approve in Forgejo's popup, and land on
  `/ui/vault/secrets` in their own entity (alias = Forgejo login, `workshop-admin` for the facilitator) with that
  entity's policy. Settings: `oidc_discovery_url=${PUBLIC_BASE_URL}/git` (Forgejo's issuer has **no** trailing
  slash), `user_claim=preferred_username`, `oidc_scopes=openid,profile`, redirect
  `${PUBLIC_BASE_URL}/ui/vault/auth/oidc/oidc/callback`; the Forgejo OAuth2 app is confidential and owned by
  `FORGEJO_ADMIN_USER`. The shim is an overlay service (`network_mode: service:openbao`, root, its CA in a named
  volume); OpenBao gets `extra_hosts: <public host>:127.0.0.1`, and on HTTPS `oidc_discovery_ca_pem` = the shim's
  `/data/caddy/pki/authorities/local/root.crt`.

### 5.5 CI identity (lab 8)

Forgejo 16 (our pinned version) should be able to give a job its own **OIDC token**, as GitHub Actions does. OpenBao's
JWT auth trusts Forgejo's signing keys, and a role bound to `repository` + `ref` claims decides what the job can read.
**Confirmed in T0.6 (2026-09-23):** a job with `enable-openid-connect: true` gets `ACTIONS_ID_TOKEN_REQUEST_URL` and
`..._TOKEN`, as on GitHub; `&audience=openbao` sets `aud`. The issuer is `${PUBLIC_BASE_URL}/git/api/actions`, the claims
are GitHub's (`repository`, `ref`, `ref_type`, `sha`, `workflow`, `event_name`, `actor`...), and a role bound to
`repository` + `ref` let `main` read and refused another branch and another repo.
**Catch:** Forgejo builds the token URL from its public `ROOT_URL`, and with our `/git/` sub-path it comes out
malformed (`${PUBLIC_BASE_URL}/git//gitapi/actions/...`, §14), on the public address the runners can't reach.
**Resolved (S24):** the issuer shim (`spike/shim/Caddyfile`) runs in the runners' network namespace too, answers
for `PUBLIC_BASE_URL` and maps the broken path to `/api/actions/...` on `git-server:3000`. Jobs use
`$ACTIONS_ID_TOKEN_REQUEST_URL` unchanged, which also keeps a later mirrored login action (§13) working as-is.
One shim design serves both OpenBao (UI SSO) and the runners.
OpenBao reaches the keys **directly** (`jwks_url` on `git-server:3000`, with `bound_issuer` set to the public issuer
string), so CI login avoids the issuer-reachability problem in §5.4.
**Verified in T0.6**, so the AppRole-only fallback isn't needed (lab 8 still starts with AppRole to show secret zero).

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

- **One slot per student.** Each slot is its own Linux user, and processes can't see other users' processes.
  `hidepid` can't be set inside an unprivileged container (T0.8); use a user + PID namespace per slot, as the runner
  pool does (§6.2).
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
  **Confirmed in T0.7 (2026-09-23):** register through the API with `"ephemeral": true`, then run
  `forgejo-runner one-job --wait`. It takes exactly one job, exits 0, and Forgejo deletes the ephemeral registration
  itself. So the long-lived fallback isn't needed.

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

**Verified in T0.8 (2026-09-23), rootless podman, default capabilities** (`spike/pool/`, `spike/t08-pool.sh`):

- `hidepid` can't be set from inside the container (remounting `/proc` needs CAP_SYS_ADMIN), and `web-terminal`
  does **not** hide processes between students (it only firewalls their ports). The plan's earlier assumption was
  wrong.
- **What works: each runner in its own user + PID namespace.** The supervisor starts each runner as
  `su rN -c 'unshare -U --map-current-user -p -f --mount-proc forgejo-runner one-job ...'`. No extra capability is
  needed. The job keeps its real uid (files are owned by `rN`) and sees only its own processes.
- Two runners (r1, r2) ran two jobs at the same time. Each job saw 7 processes (its own), found **no** trace of the
  other's secret in any command line, and couldn't read the other's home (0700), workspace or `/tmp` file
  (umask 077). Other users' environment, memory and signals are blocked by the kernel anyway.
- Cleanup works: after `one-job` exits, `su rN -c 'kill -9 -1'` then `userdel -r` (both runners' users gone).
  `useradd`/`userdel` lock `/etc/passwd`: run them one at a time (`flock`).
- Alternative seen: podman's `--security-opt proc-opts=hidepid=2` also hides processes (even container root can't
  see other users' processes, since it lacks CAP_SYS_PTRACE). It's podman-only, so the namespace approach is preferred.
- **Risk for the VM (P5):** unprivileged user namespaces can be switched off on the host (e.g. Ubuntu 24.04's
  AppArmor `kernel.apparmor_restrict_unprivileged_userns`). Check on the Azure VM; if blocked, use
  `proc-opts=hidepid=2` or relax that setting for the pool.
- Not yet tested: `prlimit` caps per runner, the issuer shim inside the pool, and a pool on `runner_net`.

**If A fails P0:** fall back to B with the runner image pre-loaded into the dind image. **C only** with a
body-checking proxy that we write ourselves, never with a generic endpoint filter.

### 6.3 Autoscaling (feasible; it's a small control loop)

Every few seconds the controller reads two numbers from Forgejo, the **jobs waiting** and each **runner's state**,
and then:

- **Scale up:** if jobs are waiting and there are fewer runners than **max**, start one runner per waiting job, up to
  max. This is what happens when a whole class pushes at once.
- **Keep a warm pool:** always keep **min idle** runners ready so the first jobs start at once.
- **Scale down:** remove idle runners above the warm pool after about 2 minutes idle. **Never remove a busy runner.**

It's feasible because the loop is simple. **Both unknowns were answered in T0.7 (2026-09-23):**

- **The API has everything the controller needs** (admin basic auth or an admin token):
  - `POST /api/v1/admin/actions/runners` `{"name","ephemeral":true}` → `uuid`, `token` (no CLI, no shared secret)
  - `GET /api/v1/admin/actions/runners` → `id`, `name`, `status` (`idle`, `offline` seen), `ephemeral`
  - `DELETE /api/v1/admin/actions/runners/{id}`
  - `GET /api/v1/admin/actions/runners/jobs?labels=host` → waiting jobs: `id`, `repo_id`, `name`, `runs_on`,
    `status: waiting`, and a `handle`. `one-job --handle <handle>` (Forgejo ≥ 15) claims that exact job, so scale-up
    can start one runner per waiting job. `repo_id` needs a lookup to show the repo name in the panel.
  - `GET /api/v1/repos/{owner}/{repo}/actions/jobs/{job_id}/logs` for job logs.
  - **A runner whose process died keeps `status: idle` for a while.** The controller must trust its own process table,
    not Forgejo's status, and `DELETE` registrations whose process is gone (🔴 on the panel).
- **A fresh runner picks up a waiting job in about 3.8 s**, counted from starting a *container*; a process in the
  pool should be quicker. An idle one-job runner polls Forgejo about every 2 s.

Starting points (to measure):

| Students | Warm idle (min) | Max runners |
|---|---|---|
| 10 | 2 | 4 |
| 20 | 3 | 7 |
| 30 | 4 | 10 |

**Memory (T0.7):** the runner process itself is about 23 MB RSS while running a job (container cgroup 7 MB idle,
10 MB during a light job). The job's own tools dominate, so size by what the lab's jobs run (`bao`, `curl`, `sops`)
and cap each runner with `prlimit` (a starting cap of 256 MB per runner, to confirm with the real lab jobs in P3).

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

- **No `engine/` edits without asking, and none are expected.** The routes `/ui/*` and `/v1/*`, the **Vault** card
  and the **Vault** and **Runners** `/admin` tabs all come from `extensions.json` files (S25, S26, §8.1).
- **Secret names, entity names, repo names and slot output are student-controlled strings** shown to others: render
  with `textContent` only, and keep the strict CSP.
- **Anything on `workshop_lab` must check `X-Gateway-Token`** unless, like OpenBao, it does its own authentication.
  The identity broker, the platform identity service and `runner-controller` need care here.
- **Pin tools in the terminal image** (`bao`, `sops`, `gitleaks`) and sha256-verify them per architecture.
- **"Dojo" branding for anything we build.** Naming Azure Key Vault on the comparison slide is factual comparison, not
  branding.

### 8.1 Extensions and modules (built on `feat/workshop-modules`, S25)

The sketch that was here was built on `feat/workshop-modules`; `engine/MODULES-PLAN.md` there has the design and
`workshops/README.md` the author's guide. What changed from the sketch: the gates are `shared`, `identity`,
`facilitator`; `/demo` and `/cloud` are ordinary manifest routes, not reserved; terminal tools stack as chained
images (`ARG BASE` / `FROM ${BASE}`); start-up work goes in `/etc/dojo/start.d/*.sh` hooks, not an `ENTRYPOINT`
wrapper; a card with no `/admin` tab of the same id is a start-up warning.

**Where the pieces go (2026-09-24, S27-S29; confirm in T1.1):**

`MODULES="openbao runner-pool"` in `workshop.env`. The workshop never lists `forgejo-runner` (S27).

| `modules/openbao/` | `modules/runner-pool/` (P3) | `workshops/vault-fundamentals/` |
|---|---|---|
| `compose.yml`: `openbao`, `openbao-setup`, the SSO shim, their volumes | `compose.yml`: Actions on in `git-server`, `runner_net`, `runner-pool`, `runner-controller`, the ID-token shim | overlay: `app-host`, `postgres`; adds its setup hooks to `openbao-setup` and puts `openbao` / `app-host` on `runner_net` |
| `terminal/`: `bao`, `BAO_ADDR` and `VAULT_ADDR` in zshenv and `ENV`, the identity broker (gives `VAULT_TOKEN` / `~/.vault-token`), `start.d/50-openbao.sh` | runner image: `bao`, `curl`, `sops`, Python (what lab jobs call) | `compose/terminal/`: `sops`, `gitleaks`, Python with `hvac`, `SOPS_DISABLE_VERSION_CHECK=1` |
| `extensions.json`: Vault card and tab, `/ui` and `/v1` routes, status check | `extensions.json`: Runners tab, `/runners` route | `extensions.json`: `app-host` slot status (P4) |
| `module.env`: mem limit, per-student namespaces on/off, OIDC role names | `module.env`: `RUNNER_MIN_IDLE`, `RUNNER_MAX`, per-runner caps | `setup.d/` hooks (S29): namespaces, templated policy, seed secrets, labs 8-9 JWT mounts; labs, slides |

**Setup order (S29).** `openbao-setup` does the generic part, runs the workshop's `/etc/openbao-setup.d/*.sh`
hooks with the provisioner token, then revokes root. It re-runs safely after a restart (unseal only when already
initialised). Nothing reads a `${VAR:?}` that only `module.env` or `workshop.env` sets: `./run.sh stop` loads only
`engine/.env`.

**Runner image and the pool.** The pool image is built by the `runner-pool` module from its own Dockerfile; a
workshop that needs more tools in jobs overrides `build.context` from its overlay, as `forgejo-runner` allows.
`openbao` and `app-host` join `runner_net` from the workshop overlay (list form), never from the module: a
module doesn't know which services a workshop's jobs may call.

Draft manifests (the `openbao` one ran as `workshops/vault-fundamentals/extensions.json` in T0.5), checked against the renderer's rules (`/ui` and `/v1` are free paths; OpenBao does
its own auth, so `shared` is the right gate and `Authorization` is stripped as in T0.4):

```json
{ "version": 1,
  "cards": [ { "id": "vault", "label": "Vault", "desc": "Your secrets, in your own namespace.",
               "href": "/ui/vault/auth?with=oidc", "icon": "key" } ],
  "admin_tabs": [ { "id": "vault", "label": "Vault", "src": "/ui/vault/auth?with=oidc" } ],
  "routes": [ { "id": "openbao-ui",  "path": "/ui", "upstream": "openbao:8200", "gate": "shared" },
              { "id": "openbao-api", "path": "/v1", "upstream": "openbao:8200", "gate": "shared" } ],
  "status_checks": [ { "label": "OpenBao", "url": "http://openbao:8200/v1/sys/health" } ] }
```

```json
{ "version": 1,
  "admin_tabs": [ { "id": "runners", "label": "Runners", "src": "/runners/" } ],
  "routes": [ { "id": "runners", "path": "/runners", "upstream": "runner-controller:8080",
                "gate": "facilitator", "strip_prefix": true } ] }
```

`sys/health` answers 200 only when unsealed and active, so the status chip also shows a sealed vault. The
`runner-controller` must still check `X-Gateway-Token`: runners and terminals can reach it on their networks.

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

## 10. Things to verify first (P0 spike, real stack): results

All verified on the real stack (locally: amd64, WSL2 on the desktop, rootless podman) between 2026-09-23 and 2026-09-24, except where a
line says otherwise. Details live in the section named; surprises in §14.

| # | Question | Result | Where |
|---|---|---|---|
| 1 | OpenBao release with **namespaces**, digests per arch | ✅ OpenBao **2.6.3** (namespaces work); moved to 2.7.0 in T1.1 (S31), where the T0.5 and T0.9 scripts pass again. Image, `bao`, `sops`, `gitleaks` pinned with sha256 per arch. arm64 not built. | §15 T0.3 |
| 2 | UI through Caddy at `/ui/` and `/v1/` behind the gate, framed in `/admin` | ✅ Routes from `extensions.json` (`shared` gate), no engine edit (S26). Framing needs `frame-ancestors 'self'` through `sys/config/ui/headers`. | §5.4 |
| 3 | Forgejo as the OIDC provider for the UI | ✅ Student and facilitator (in the `/admin` Vault tab) sign in and land in their own entity and policy. Needs a Forgejo session first (§12 Q5). | §5.4, §14 |
| 4 | Forgejo 16 Actions OIDC tokens accepted by OpenBao JWT auth | ✅ GitHub-style claims; a role bound to `repository` + `ref` lets `main` in and refuses another branch and repo. The token URL is malformed under `/git/`; the issuer shim fixes it (S24). | §5.5 |
| 5a | One-job / ephemeral runner | ✅ `ephemeral: true` registration + `forgejo-runner one-job --wait`: one job, exit 0, registration removed. | §6.1 |
| 5b | API for waiting jobs and runner state | ✅ Waiting jobs with a `handle`; runner list with `status`. Dead runners stay `idle`: the controller trusts its own process table. | §6.3 |
| 5c | Start-up time | ✅ 3.8 s from container start to job picked up. | §6.3 |
| 5d | Memory per running job | ✅ Runner about 23 MB RSS; the job's tools dominate. Real lab jobs to measure in P3. | §6.3 |
| 5e | Process pool: hide other users' processes, several runners side by side | ✅ Not with `hidepid` (can't remount `/proc`), but with a **user + PID namespace per runner** (`unshare`), no extra capability. Two concurrent jobs couldn't see each other's processes or files. Risk: hosts that block unprivileged user namespaces (P5). | §6.2 |
| 6 | `sops` with transit | ✅ Per student namespace; decrypt-only token decrypts, others get 403; key rotate + `sops rotate` work. Needs `VAULT_ADDR`, and `SOPS_DISABLE_VERSION_CHECK=1`. | §4 lab 6, §14 |
| 7 | Where Forgejo's issuer is reachable from | ✅ The issuer shim in OpenBao's network namespace, on `http://localhost:8080` and on real HTTPS (`--env home`, S30) with the shim's CA. The Azure VM run is still P5. | §5.4 |
| 8 | `/ui` and `/v1` strip Basic Auth `Authorization` | ✅ A Basic Auth header alone gets OpenBao's 403, so it isn't taken as a token. | §5.4 |

**No fallback was needed:** SSO (S23), Actions OIDC, one-job runners and the process pool (S16 A) all hold, so
AppRole-only CI, token-only UI login and Docker-in-Docker stay unused.

**Not covered by P0** (carried into later tasks): arm64 builds; `prlimit` per runner, the ID-token shim inside the
pool and the pool on `runner_net` (P3); memory of real lab jobs (P3); unprivileged user namespaces on the Azure VM
(P5); the identity broker and CLI login (T1.4); `app-host` (P4).

## 11. Phases and task list (ask the user before moving between phases)


- **P0 spike**: §10 on the real stack; write down the findings.
- ~~**P0.5 engine extensions**~~: replaced by `feat/workshop-modules` (S25), merged in 8c71f83.
- **P1 core**: the `openbao` module (§8.1) + setup and its hooks (S29) + SSO + terminal tools + labs 0-3.
- **P2 code and git**: labs 4-6.
- **P3 pipelines**: the `runner-pool` module (S27): pool, `runner-controller`, the Runners panel (manual − / + first, then autoscale) +
  labs 7-8.
- **P4 deployments**: `app-host`, Postgres, labs 9-11.
- **P5 facilitator, talk, tests**: the remaining `/admin` pieces, slides (with §9), `e2e.sh`, demo bots, sizing docs,
  a run on an Azure VM.
- ~~**P6 migrate every workshop to extensions**~~: done on `feat/workshop-modules` (S25).

### P0 — Spike (§10 on the real stack; findings go into §10 and §14)

**Order (S22):** T0.2 → T0.3 → T0.6 → T0.7 → T0.8 → T0.4 → T0.11 → T0.5 → T0.9 → T0.10.

Spike code lives under `workshops/vault-fundamentals/spike/` (throwaway; may be
deleted or folded into P1). No `engine/` edits without asking the user first.

- [x] **T0.1** *(`54ed028`)* Branch `feat/vault-fundamentals` from `main`; move the plan to
      `workshops/vault-fundamentals/PLAN.md`; add resume section, task list and session log;
      point `CLAUDE.md` and the root README at it.
      *Verify:* `git log --oneline -1 -- workshops/vault-fundamentals/PLAN.md`.
- [x] **T0.2** *(ef0d1bc)* Skeleton: `workshop.env` (no labs yet) and a spike compose overlay that adds an
      OpenBao container on `workshop_lab` (own `image:` tag for the terminal, per the overlay rules).
      *Verify:* `./run.sh list` shows the workshop; `./run.sh vault-fundamentals` starts and
      `bao status` answers from the student terminal (tools may be a temporary download on the host
      side for the spike).
- [x] **T0.3** *(ef0d1bc)* (§10.1) Pick the OpenBao release with **namespaces**; record version and image
      digests for amd64 and arm64 in §15. Also pin `bao`, `sops`, `gitleaks` binaries + sha256.
      *Verify:* digests match the registry; `bao namespace create` works on the spike server.
- [x] **T0.4** *(3c49e9a)* (§10.2, §10.8) OpenBao UI through Caddy at `/ui/` and `/v1/` behind the login gate, and
      framed in `/admin`. Ran on an uncommitted `engine/gateway/Caddyfile` edit (S21), since dropped (S26). *Verify:* UI loads and works through the
      gateway URL and inside an `/admin` iframe.
- [x] **T0.11** *(e610c57)* (before T0.5) Put the spike on the module-era image chain: drop `image:` from `web-terminal` in
      `compose/docker-compose.override.yml`, start `compose/terminal/Dockerfile` with
      `ARG BASE=gitopsdojo/web-terminal:base` / `FROM ${BASE}`, and remove a stale
      `gitopsdojo/web-terminal:vault-fundamentals` tag if `run.sh` would reuse it.
      *Verify:* `./run.sh vault-fundamentals --dry-run` is clean; after a start, `bao status` answers from a student
      terminal and the container is `healthy`.
- [x] **T0.5** *(2a2e21f, 0c8a3b0)* (§10.3, §10.7) Forgejo as the OIDC provider for the OpenBao UI login, including the redirect
      back to `/ui/...`, through the issuer shim (S23). Routes, card and `/admin` tab from a spike
      `workshops/vault-fundamentals/extensions.json` (S26, the draft in §8.1); no `engine/` edit. Test the local (`http://localhost`)
      path for real, and the HTTPS path through `--env home` (S30) with the shim's CA.
      *Verify:* a student logs in to the UI with their Forgejo account and lands in the right identity/policy; the
      facilitator does the same inside the `/admin` **Vault** tab.
- [x] **T0.6** *(3e1638c)* (§10.4) Forgejo Actions OIDC job tokens: record the claims; configure OpenBao JWT auth
      to accept them and bind a role to repo/branch. *Verify:* a workflow run reads a secret with no
      stored credential; a run from another repo is refused.
- [x] **T0.7** *(79e2ac0)* (§10.5 a-d) Runners: one-job/ephemeral mode in `forgejo-runner:13`; Forgejo API for
      waiting jobs and runner state; start-up time; memory while running a job.
      *Verify:* numbers recorded in §10/§15; a runner exits after exactly one job.
- [x] **T0.8** *(5eae970)* (§10.5 e) Process-pool isolation (§6.2 A): hide other users' processes in an
      unprivileged container; several runners (one Linux user each) side by side. If it fails, record
      why and fall back to Docker-in-Docker (S16). *Verify:* a job cannot see or signal another job's
      processes or files.
- [x] **T0.9** *(79a005d)* (§10.6) `sops` with OpenBao transit. *Verify:* encrypt a file, commit it, decrypt it
      with a token that has transit decrypt only; a token without it fails.
- [x] **T0.10** *(7f9de64)* Write up: findings into §10, plan changes into the relevant sections, new questions
      into §12, a P0 entry in §15. **Ask the user before starting P1.**

### P1 — Core (firmed up in T0.10, 2026-09-24; waiting for the user's go)

Each task turns spike pieces into the module or the workshop and deletes them from `spike/` as it goes; `spike/` is
gone when P1 ends (the P3 pieces, `pool/` and `t06`-`t08`, move to `modules/runner-pool/` then). Every task is
checked locally (WSL on the desktop); T1.3 and T1.6 also through `--env home` (S30), which needs the a24d0e7 `run.sh` fix.

- [x] **T1.1** *(2f47607)* `modules/openbao/` skeleton: move the `openbao` service, `config.hcl` (with the audit block), the SSO
      shim and the spike manifest out of the workshop, card and tab pointing at `/ui/vault/auth?with=oidc`. `bao`,
      `BAO_ADDR` and `VAULT_ADDR` (zshenv and `ENV`) move to the module's `terminal/`; the workshop keeps `sops`,
      `gitleaks` and adds `SOPS_DISABLE_VERSION_CHECK=1`. `README.md` (one-line summary first); `MODULES="openbao"`;
      `COMPOSE_OVERLAY` only if something is left (nothing was: removed). OpenBao 2.7.0 (S31).
      *Verify:* `./run.sh modules` lists it; `--dry-run` is clean; the stack starts, the Vault card and tab work,
      `./run.sh stop` leaves no volume behind.
- [x] **T1.2** *(33e1d36)* `openbao-setup` in the module (S29): init, unseal, re-unseal after a restart; the UI CSP
      header with `frame-ancestors 'self'` (§5.4); facilitator policy; provisioner token; `setup.d` hooks; revoke
      root. Replaced `spike/init-bao.sh` (and the `t04-*.py` scripts that read its root token).
      *Built, `modules/openbao/setup/`:* `setup.sh` inits with one key share, unseals, writes the provisioner policy,
      creates a **periodic** (168 h) orphan provisioner token, and revokes root. The root token waits on
      `openbao_setup` until it is revoked, so a first start that dies half-way is finished by the next start. Every
      start then uses the provisioner token to set the UI header and the facilitator policy and to source each
      `/etc/openbao-setup.d/*.sh` hook in a subshell (hooks get `BAO_TOKEN` and a `retry` helper). **It then stays
      running** and unseals whenever `openbao` is sealed (checking every 5 s), renewing the token hourly. A one-shot
      container couldn't re-unseal after a restart of `openbao`. If the vault is new but the volume isn't, it moves
      the old key and tokens aside. The provisioner can manage namespaces (including `students/<name>`), policies,
      auth methods, identities and mounts, renew itself, and write but not read seed secrets. Since it can write
      policies it can't be a real boundary, which the policy file says openly (§14).
      *Verify:* after `./run.sh vault-fundamentals` the `openbao_setup` container is healthy, the vault is unsealed with
      no manual step, `/setup` holds no `root-token`, the provisioner token renews and can create
      `students/student01`, and a `podman restart workshop_openbao` re-unseals by itself. *(Passed locally
      2026-09-25: healthy in about 10 s, re-unseal in about 10 s, CSP `frame-ancestors 'self'`, audit log written,
      restarting the setup container doesn't re-init.)*
- [x] **T1.3** (ca89792, 82ff676) SSO in the module, from `spike/t05-sso.sh`: Forgejo OAuth2 app, OIDC method and role (settings in
      §5.4), the shim's CA on HTTPS, one entity per student and the facilitator. The Forgejo session first: the
      `engine/` change `/forgejo-login?next=` (S32, approved) and the card and tab pointing through it; check whether Forgejo 16 can skip its "Authorize Application" page for our own app.
      *Verify:* `t05-sso-browser.py` (moved to the module's tests) passes locally and on `--env home`.
      *(Passed locally and on `--env home` (HTTPS) 2026-09-25 as `modules/openbao/tests/sso_browser.py`: student via
      the card → entity `student01`/`02` with `student`, facilitator via the `/admin` tab → `facilitator`, both
      land on `/ui/vault/secrets`; `?next=//example.com` falls back to the repo. Forgejo 16 **can't** skip the
      Authorize page (§14): each account approves once.)*
- [x] **T1.4** *(55de8e1, c7815c9; `modules/openbao/tests/cli_login.sh` passed locally 2026-09-25)* CLI login: the identity broker in the module's terminal link (the `dojo-cloud` broker's
      `SO_PEERCRED` pattern), JWT auth in the root namespace, linked to the same entity as the UI login. It gives
      `bao` and sops a token (`VAULT_TOKEN` or `~/.vault-token`).
      *Verify:* as `student01`, `bao token lookup` shows the student entity with no manual login; student02 can't
      get student01's JWT.
- [x] **T1.5** *(2109b9d, f7b8bf8; `workshops/vault-fundamentals/tests/tenancy.sh` passed locally 2026-09-25)* The workshop's hooks: per-student namespaces with an admin policy inside each, the shared `secret/`
      mount and templated policy (§5.3), seed secrets.
      *Verify:* student01 reads `secret/students/student01/*`, gets 403 on student02's path, and is admin only in
      `students/student01`.
- [x] **T1.6** *(a1da88a, 1dbe33b; labs 0-3 run as a student and slides screenshotted locally 2026-09-25)* Labs 0-3 and their slides (the lab reader copies, §4).
      *Verify:* a full walk-through of labs 0-3 as a student in a real browser; slides within 16:9 (screenshot).
- [x] **T1.7** *(module README with T1.4; READMEs 898199b)* Docs: module `README.md`, the workshops table in `workshops/README.md`, root `README.md`,
      `CLAUDE.md` module list.

### P2 — Code and git (labs 4-6; the user said go 2026-09-25)

Labs 4-5 carry on from lab 3's namespace where they can (`team/app`, the `app-read` policy): each lab starts with a
short, idempotent catch-up block, so a student who skipped lab 3 isn't stuck. Everything stays in `~/lab` and the
class vault; nothing is pushed (Forgejo repos per student come with P3's pipelines).

- [x] **T2.1** *(1f8d7c5; built by `./run.sh`, `hvac.Client().is_authenticated()` is `True` as student01)* Terminal:
      Python `hvac` 2.4.0 for lab 4 with requests, urllib3, idna, certifi and charset-normalizer, all `py3-none-any`
      (one sha256 per package serves both architectures, `compose/terminal/hvac-wheels.sha256`). `wget` fetches the
      wheels (system CA store; pip would use its own bundle and fail behind a corporate TLS proxy), `sha256sum -c`
      checks them, and pip runs from its own wheel to install offline with `--no-index --no-deps`; no pip is left in
      the image. No new binary: `bao agent` is in `bao`.
      *Verify:* `python3 -c 'import hvac; print(hvac.Client().is_authenticated())'` prints `True` as a student.
- [x] **T2.2** *(9ed5f8f)* Lab 4, "The app reads a secret": the same app hard-coded (lab 1's), from a git-ignored `.env`, then
      from `secret/students/<you>/app` with `hvac` (it finds `VAULT_ADDR` and `~/.vault-token` by itself). Don't log
      secrets (a debug line that prints the config); the token's TTL and `renew_self`.
- [x] **T2.3** *(9ed5f8f)* Lab 5, "OpenBao Agent": in `students/<you>`, AppRole for the app (`app-read`, lab 3), role ID and
      secret ID as files (the "secret zero" that labs 8-9 remove), `bao agent` with approle auto-auth renders
      `team/app` to `/dev/shm/<you>/app.env` (`0600`, tmpfs); a small app reads the file on every loop. Rotate with
      `bao kv put` and the app sees it within seconds, no commit, no restart.
- [x] **T2.4** *(9ed5f8f)* Lab 6, "Encrypted config in the repo": transit in `students/<you>`, `.sops.yaml` with the key URL
      that carries the namespace (§14), encrypt, commit, a readable `git diff` through a `textconv`, an encrypt-only
      token that can't decrypt, rotating the key then `sops rotate -i`, and `min_decryption_version` so the old
      commit's copy stops opening.
- [x] **T2.5** *(9ed5f8f)* Slides and lab pages: presentation Parts 3-4 (code, git), `labs.md`, `lab-index.md`, `cheat-sheet.md`,
      the lab `README.md` table; the lab reader copies.
- [x] **T2.6** *(9ed5f8f; `labs_4_6.sh` PASS, `tenancy.sh` and `cli_login.sh` PASS, labs run literally as written, slides and lab reader checked in Playwright, locally 2026-09-25)* Tests and the live pass: `tests/labs_4_6.sh` runs each lab's commands as a student; a walk-through of
      labs 4-6 in a real browser; slides within 16:9 (screenshot).
      *Verify:* `tests/labs_4_6.sh` passes locally; `tenancy.sh` and `cli_login.sh` still pass.

### P3 — Pipelines (the `runner-pool` module, labs 7-8; the user said go 2026-09-25)

Built without a stack (another session had the machine); the live pass (T3.9) runs with the user at the end.

**Design, fixed here (§6):** two containers and a spool volume. `runner-pool` (unprivileged, `runner_net` only) runs
a **supervisor** with no network listener: it starts one `forgejo-runner one-job` per config file the controller
drops in `/spool/start/`, each as its own Linux user in its own user + PID namespace (T0.8), and writes what it sees
(starting, idle, busy + repo, done, failed) to `/spool/state.json`. `runner-controller` (on `workshop_lab`, holds
the Forgejo admin login, never on `runner_net`) registers ephemeral runners through the API, runs the scaling loop,
removes dead registrations and serves the Runners panel from a cached snapshot. Jobs get the terminal's own `bao`
and `sops`: the pool image copies the tools a workshop names (`JOB_TOOLS`) out of the terminal image `run.sh` has
just built, so there is one pin per tool. Jobs run `runs-on: host`. Students fork `platform-team/vault-fundamentals`
(as in tofu-basics) and push workflows to their fork; the CI role binds `repository=<you>/vault-fundamentals`.

- [x] **T3.1** *(ee6e59b, fixes d80e078; verified in T3.9)* `modules/runner-pool/` skeleton: `compose.yml` (Actions on, `runner_net`, `runner-pool`,
      `runner-controller`, the ID-token shim from `spike/shim`), `pool/Dockerfile`, `module.env` (`RUNNER_MIN_IDLE`,
      `RUNNER_MAX`, caps), `extensions.json` (Runners tab, `/runners` route, facilitator gate), `README.md`. The
      workshop lists `MODULES="openbao runner-pool"` and its overlay puts `openbao` on `runner_net` and sets
      `JOB_TOOLS`. `spike/` goes (`pool/`, `shim/`, `t06`-`t08`).
- [x] **T3.2** *(ee6e59b, fixes d80e078; verified in T3.9)* Pool supervisor (`pool/supervise.py`): spool protocol, a user + PID namespace per runner, `prlimit`
      caps, clean-up after each job (kill, `userdel -r`, one at a time), the shim's CA trusted on an `https://` name.
- [x] **T3.3** *(ee6e59b, fixes d80e078; verified in T3.9)* Controller (`controller/controller.py`): Forgejo API client, Auto (warm idle + one runner per waiting
      job, up to max; idle above the minimum removed after 2 min; never a busy one) and Manual, dead-runner clean-up,
      red lights (failed start, offline, stuck). Unit tests against a fake Forgejo and spool (no stack needed).
- [x] **T3.4** *(ee6e59b, fixes d80e078; verified in T3.9)* The Runners panel: page, JS and CSS served by the controller (strict CSP, `textContent` only), a light
      per runner, − / +, Auto / Manual, jobs waiting, min / max. `X-Gateway-Token` + facilitator only; POSTs need
      `X-Requested-With: dojo-runners` (the allocator's CSRF pattern).
- [x] **T3.5** *(5be3d6e, fixes d80e078; verified in T3.9)* Workshop wiring: setup hook `20-ci.sh` (S19: `auth/jwt-ci` in each namespace, pointed at Forgejo's
      Actions keys and issuer; the student writes the role and policy).
- [x] **T3.6** *(5be3d6e, fixes d80e078; verified in T3.9)* Lab 7, "Forgejo Actions secrets": fork and clone, a repository secret, masking and how `base64`
      gets round it, anyone who can push a workflow can read the secret, fork PRs vs `pull_request_target`, the
      single-use runner seen from inside a job.
- [x] **T3.7** *(5be3d6e, fixes d80e078; verified in T3.9)* Lab 8, "CI logs in to OpenBao": AppRole first (the login secret sits in Forgejo: secret zero), then
      the job's own OIDC token bound to `<you>/vault-fundamentals` on `main`; a branch is refused; remove the AppRole
      secrets. `curl` + `bao`, no `uses:` (S20).
- [x] **T3.8** *(5be3d6e, fixes d80e078; verified in T3.9)* Slides and lab pages: presentation Part 5 (pipelines), the "at work" action slide (S20), `labs.md`,
      `lab-index.md`, cheat sheet, lab README table; module README, `workshops/README.md`, root README, `CLAUDE.md`.
- [x] **T3.9** *(d80e078; all PASS locally 2026-09-25, see §0 and §15)* Tests and the live pass (with the user): `modules/runner-pool/tests/pool.sh` (isolation of two
      concurrent jobs, clean-up, scale-up under a burst, Manual, panel auth and CSRF), `tests/labs_7_8.sh`, memory of
      real lab jobs (§6.3), `--dry-run` clean, `./run.sh stop` leaves nothing; labs 7-8 in a real browser; slides
      within 16:9.

### P4 — Deployments (`app-host`, `app-db`, labs 9-11; the user said go 2026-09-25)

**Design, fixed here (§5.6):** all in the workshop (overlay + `compose/app-host/`), no module and no `engine/` edit.

- **`app-host`** (on `workshop_lab` and `runner_net`): Debian slim like the terminal, with `bao` and the terminal's
  Python packages copied from the terminal image (`TOOLS_IMAGE`, one pin per tool, as the pool does). One Python
  program, `apphost.py`, runs as root and is the whole platform:
  - **Slots:** one Linux user per student (`student01` …, uid 30000+), made at start. A deploy unpacks the bundle
    *as the slot user* into `/srv/apps/<slot>/app` and runs its `start.sh` as that user, in its own user + PID
    namespace with `prlimit` caps (the pool's pattern, T0.8); crash restarts with a limit; `kill -9 -1` as the user
    stops it. The app listens on `$PORT` (9000 + n).
  - **Platform identity:** its own RS256 key (volume `app_host_keys`); every 5 min it writes each slot a 10-min
    JWT (`iss http://app-host:8080`, `aud openbao`, `sub slot:<slot>`, `slot`) to `/run/platform/<slot>/token`
    (dir 0700, file 0400, the slot user's). Public keys at `/.well-known/jwks.json`. Like a Kubernetes projected
    service-account token.
  - **Deploy API:** `POST /deploy` with a tar.gz and `Authorization: Bearer <the job's Forgejo ID token,
    audience app-host>`. The platform checks the signature against Forgejo's keys (openssl, JWK → PEM by hand),
    issuer, audience, expiry, `ref == refs/heads/main` and `repository == <owner>/vault-fundamentals`, and deploys to
    the owner's slot. The deploy credential is the job's identity, not a stored secret; the job's *vault* identity
    (lab 8's `ci-read`) still can't read `team/app`: separation of duties.
  - **HTTP:** direct on `app-host:8080`: `/healthz`, JWKS, `/deploy`, and `/<slot>/…` proxied to the slot's app
    (apps are public in the class, like any web app; they show fingerprints, never values). Through the gateway,
    `/apps` (`identity` gate, stripped): a page with your slot's state, deploy and log tail, and for the facilitator
    every slot (the `/admin` **Apps** tab, the "My app" card). Proxied app responses get `CSP: sandbox` and lose
    `Set-Cookie`; requests to apps lose `Cookie`, `Authorization` and the gateway headers, so student HTML can't
    run script on the class origin or see the gateway token.
- **`app-db`** (Postgres 17, `workshop_lab`): per student a database `app_<s>` with a `notes` table, a group role
  `app_<s>_rw`, and `vault_<s>` (`CREATEROLE`, admin of `app_<s>_rw`) whose first password setup hands to the vault
  and then rotates (`rotate-root`): no person ever knows it. `CONNECT` only to your own database.
- **Setup hook `30-platform.sh`** (S19, half-configured): in each namespace `auth/jwt-platform` pointed at the
  platform's JWKS and issuer, and a `database/` mount with the `app-db` connection; students write the roles.
  The module's provisioner policy gains `students/+/database/config/*` and `rotate-root/*`.
- **Audit for students (lab 11):** `openbao-audit` in the `openbao` module reads the audit file and answers a
  caller who sends their vault token: students get the entries in their own namespace, the facilitator all
  (§7). The audit device stops HMAC-ing accessors (`hmac_accessor = false`) so a leaked token can be traced by
  accessor; tokens stay hashed. Terminal command `bao-audit`.
- Terminal: `psql` (Debian's `postgresql-client`) and `pg8000` (wheels in `hvac-wheels.sha256`, which app-host
  inherits) for lab 10.

- [x] **T4.1** *(21daddf; verified live 2026-09-25)* `app-host`: Dockerfile, `apphost.py` (slots, identity, deploy, proxy, panel), overlay service and
      volumes, `extensions.json` (card, tab, route, status check). Unit tests without a stack (JWT verify, deploy
      claims, proxy header scrubbing).
- [x] **T4.2** *(21daddf; verified live 2026-09-25)* `app-db` and the terminal's `psql`/`pg8000`; hook `30-platform.sh`; provisioner lines.
- [x] **T4.3** *(91031d6; verified live 2026-09-25)* `openbao-audit` in the `openbao` module; `hmac_accessor = false`; `bao-audit` in the terminal.
- [x] **T4.4** *(21daddf; verified live 2026-09-25)* Lab 9, "Deploy with workload identity": the platform's keys, the role bound to your slot, the app
      with an Agent (`remove_jwt_after_reading = false`), a deploy workflow, rotation seen by the app, the pipeline
      refused `team/app`, a branch deploy refused.
- [x] **T4.5** *(21daddf; verified live 2026-09-25)* Lab 10 (optional), "Dynamic database credentials": role, `creds`, `psql`, lease lookup / renew /
      revoke, then the app gets its own through the Agent.
- [x] **T4.6** *(21daddf; verified live 2026-09-25)* Lab 11, "Incident drill": a token leaks and is used; find it in the audit log by accessor, revoke the
      tree, rotate what it read, the app recovers by itself.
- [x] **T4.7** *(21daddf; verified live 2026-09-25)* Slides (Part 6), `labs.md`, `lab-index.md`, cheat sheet, lab README, READMEs, `CLAUDE.md`.
- [x] **T4.8** *(91031d6, 21daddf; verified live 2026-09-25)* Tests and the live pass: `tests/labs_9_11.sh`, the platform's isolation (a slot can't read another's
      token or files, a forged or wrong-branch deploy is refused), earlier tests still pass, the Apps page in a
      real browser, slides within 16:9, `./run.sh stop` leaves nothing.

Later phases get their own task block (IDs `T5.x`) when they start.

## 12. Open questions for the user

Q1 (how OpenBao reaches Forgejo's OIDC issuer) was answered on 2026-09-23 with option A, the issuer shim (S23).

Q2 (S26-S30) and Q3 (drop the S21 stash) were answered on 2026-09-24: all confirmed; `runner-pool` is a module
from the start (S27), workshop setup runs as hooks in `openbao-setup` (S29), and the stash is dropped.

**From the P0 write-up (2026-09-24), answered the same day (S31, S32):**

- **Q4. Which OpenBao for P1?** P0 ran on 2.6.3 (the stable line's patch) because 2.7.0 came out the day T0.3
  pinned it. Options: (a) stay on 2.6.3 for the whole build and look again before P5; (b) move to the newest 2.7.x
  in T1.1 and re-run the T0.3/T0.5/T0.9 spikes once on it. *Recommendation: (b)*, so the workshop doesn't start
  out one minor version behind; the spikes are scripted, so the re-check is cheap. **Answer: the latest (S31).**
- **Q5. How does a student get a Forgejo session before Vault SSO?** Without one, the SSO popup shows Forgejo's
  password page, and students don't know that password (§14). `/forgejo-login` (in `engine/allocator/server.py`)
  signs them in but always lands on the seed repo. Options: (a) no engine change: lab 0 says "open the Forgejo card
  first", and the Vault card's description says so too; (b) a small **engine** change: `/forgejo-login?next=<local
  path>` (only same-origin paths allowed), so the Vault card and tab can go through it and SSO is one click.
  *Recommendation: (b)*, since it is workshop-agnostic and any module using Forgejo SSO needs it; (a) if you'd
  rather not touch the engine. **Answer: (b) (S32).** None open.

## 13. Later / follow-ups

- **Policy as code** (user wants it, deferred 2026-09-23): the namespace's policies in a git repo, changed by pull
  request and applied by CI, with drift shown when someone edits in the UI. Tool to decide then: OpenTofu with the
  `vault` provider (builds on tofu-basics) or `bao policy write` in CI. Could be an extra lab here or its own
  workshop.
- Could `cert-autorenewal` use OpenBao's PKI engine?
- **Mirror a small, pinned set of actions into Forgejo** (deferred 2026-09-23, S20): e.g. checkout and a vault-login
  action, copied into the local Forgejo at setup and pinned by commit, so labs can show `uses:` the way companies do.
- ~~**Modules: reusing one workshop's pieces in another**~~: built on `feat/workshop-modules` (S25). The tofu
  tie-in is now `MODULES="openbao dojo-cloud"`.

## 14. Worth knowing & follow-ups

Surprises, gotchas and problems found in other workshops while working on this one.

- **Student shells are zsh** (`su - <name>` login shell): environment variables for students go in `/etc/zsh/zshenv`
  (as tofu-basics does), not only `/etc/profile.d`. Found in T0.2 when `BAO_ADDR` was empty.
- **Forgejo 16.0.4 builds a broken Actions ID-token URL under a sub-path `ROOT_URL`**: the job sees
  `http://localhost:8080/git//gitapi/actions/_apis/pipelines/workflows/<n>/idtoken` (the sub-path twice, a slash
  missing). The issuer (`.../git/api/actions`) and the JWKS URL are correct. Resolved in the lab by the issuer
  shim (S24, §5.5). The user chose not to file it upstream.
- **OpenBao 2.6 refuses to enable audit devices through the API** ("use declarative, config-based audit device
  management"). The audit device is an `audit "file" "file" { options { file_path = ... } }` block in `config.hcl`.
- **Audit entries HMAC every string**, error messages included. `bao write sys/audit-hash/file input="<text>"`
  turns a guess into the same hash, which confirmed the T0.6 refusals (`error validating claims: claim "ref" ...`
  and `claim "repository" ...`). Good material for labs 3 and 11.
- **Caddy cleans `//` out of the path before `path_regexp` sees it**: match `/git/+git...`, not `/git//git...`.
- **Pushing again to a branch cancels that branch's running runs** in Forgejo 16, and cancelling a job on an
  **ephemeral** runner deletes its registration at once. The runner then retries its final log upload with 401s
  for about 40 s before exiting. The controller should treat this as normal (runner exits; not 🔴).
- **The job-logs API takes a job id, not a task id**: `GET /repos/{o}/{r}/actions/jobs/{task id}/logs` returned a
  different job's log. Archived logs appear in `/data/gitea/actions_log/...` only some seconds after a job ends.
- **Job logs are not in the runner's stdout**, only in Forgejo: `/data/gitea/actions_log/<owner>/<repo>/<nn>/<id>.log.zst`
  (zstd; Python 3.14's `compression.zstd` reads them, the Forgejo image has no `zstd`).
- **OpenBao's UI refuses to be framed by default** (`frame-ancestors 'none'`). Override it through
  `sys/config/ui/headers`, not in Caddy (T0.4).
- **The UI's sign-in lands on `/ui/vault/secrets`**, not a dashboard, and doesn't share a session between tabs.
- **No browser on the dev machine (WSL)**: the browser tests run in `mcr.microsoft.com/playwright/python:v1.55.0-noble`
  with `--network host`, serving the same-origin test page through a Playwright route (`spike/t04-*.py`).
- **OIDC sign-in needs a Forgejo session first**: without one, the popup shows Forgejo's login page (the student
  doesn't know that password). The test goes through `/forgejo-login` first. P1: point the Vault card and tab at
  something that signs in to Forgejo first, or tell students to open Forgejo once (T1.3).
- **The Vault UI fetches `auth_url` when the page loads**; a click before that does nothing (no popup). Tests wait.
- **The `/admin` tab opens on the token method** (`/ui/` → `?with=token`). Use `src`/`href`
  `/ui/vault/auth?with=oidc` in T1.1.
- **Forgejo shows its "Authorize Application" page** on a user's first OIDC login; the test clicks it when shown.
  Worth checking whether Forgejo 16 can skip it for our own app (T1.3).
- **`engine/run.sh` with `MODULES` set re-reads `.env` but not `.env.<name>`** after the module defaults, so under
  `--env home` `PUBLIC_BASE_URL` falls back to `.env`'s value for any workshop with modules. Not hit in T0.5 (no
  modules yet); it will be in T1.1. Fixed with the user's approval (2026-09-24): the modules block now re-reads `.env.<name>` too.
- **The shim can't use the gateway image's healthcheck** (Caddy's admin API, which the shim turns off); it checks
  `${PUBLIC_BASE_URL}/git/api/healthz` through itself instead.
- **The first write to a new KV v2 mount fails for a moment** ("Upgrading from non-versioned to versioned data").
  `openbao-setup` must retry or wait after `bao secrets enable kv-v2` before writing seed secrets.
- **sops + transit works per student namespace** (T0.9, sops 3.13.3, OpenBao 2.6.3). sops uses the Vault client, so it
  reads `VAULT_ADDR`, `VAULT_TOKEN` and `VAULT_NAMESPACE`, not the `BAO_*` names. Two forms work: `VAULT_NAMESPACE=students/<name>`
  with `--hc-vault-transit $BAO_ADDR/v1/transit/keys/sops`, or the namespace in the URL path
  (`.../v1/students/<name>/transit/keys/sops`) with no `VAULT_NAMESPACE`. The URL is stored in the file, so the
  path form is self-contained and is the one to teach (P2). Policies: `update` on `transit/encrypt/sops` and
  `transit/decrypt/sops`; an encrypt-only or default token gets `403 permission denied` on decrypt. After
  `transit/keys/sops/rotate`, the file still opens, and `sops rotate -i` re-wraps it with `vault:v2`.
- **`sops --version` calls GitHub** and prints a warning in the offline terminal. Set `SOPS_DISABLE_VERSION_CHECK=1`
  in the terminal image (zshenv + `ENV`) in P2.
- **The provisioner token is admin-equivalent** (T1.2): anything that can write policies and identities can grant
  itself more. Its protection is where it lives: only on the `openbao_setup` volume. Worth a line on the
  "secret zero" slide.
- **OpenBao says "unsealed" a moment before it accepts writes** (T1.2): the first write straight after `bao operator
  unseal` got `500 internal error` (the audit device's salt couldn't be stored yet), and a `set -e` script died there.
  Retry every write that follows an unseal (`setup.sh` does, 30 × 1 s; one retry was enough locally).
- **A token made with `-no-default-policy` can't renew or look itself up** (T1.2): grant `auth/token/renew-self` and
  `auth/token/lookup-self` in its own policy.
- **Forgejo 16 has no `skip_secondary_authorization`** (T1.3): the API ignores the field, so every account sees
  "Authorize Application" once, on its first OIDC sign-in. Lab 0 should say so.
- **`bao write -field=id identity/lookup/entity` prints "Success! …" when nothing matches** (T1.3), so an empty-output
  test never fires. Writing an entity alias that already exists moves it to the given `canonical_id`, which makes a
  plain write idempotent (and repairs an entity an early login created on its own).
- **The OpenBao image's busybox `wget` does GET and POST only**, and there's no `curl` or `jq`: `sso.sh` never
  deletes the Forgejo app, it keeps the client id and secret on `openbao_setup` and reuses them.
- **Busybox `sh` runs a trap only after a foreground `sleep` ends**: `setup.sh` sleeps with `sleep 5 & wait $!`.
- **The terminal sets `BAO_ADDR` only** *(fixed in T1.1: the `openbao` module sets `VAULT_ADDR` too)*; lab 6 needs `VAULT_ADDR` too (export it alongside `BAO_ADDR`, and the
  identity broker should provide `VAULT_TOKEN` or `~/.vault-token`, which sops also reads).
- **`retry` in `setup.sh` shared `i` with the hook's loop** (sh has no locals): setup looped on student02 forever.
  Fixed in c7815c9 (`_retry_n`, `_retry_i`). Hooks: don't name variables `_retry_*`.
- **A child token carries its parent's entity** (`identity_policies` too). In a namespace, one made by a
  root-namespace entity's token was refused everything, even `lookup-self`. `bao token create -orphan` gives a token
  with no entity and only the policies asked for: lab 3 uses it.
- **Templated paths work across namespaces**: `students/{{identity.entity.name}}/*` in a root policy makes the
  student admin in `students/<name>` only, including `sudo` for `token create -orphan` (T1.5).
- **The OpenBao 2.7 UI's KV routes** are `/ui/vault/secrets/secret/list/<path>/` and `.../show/<path>`; the
  namespace picker is at the bottom of the side menu (`root` → `students` →), and `?namespace=students/<name>` works.
- **gitleaks 8.30.1:** `gitleaks git -v` and `gitleaks git --pre-commit --staged --redact -v` work; `ghp_` + 36
  characters trips `github-pat`.

- **OpenBao Agent: `namespace` in the `auto_auth` method is enough** (T2.3): the templates' `secret "team/data/app"`
  resolves in that namespace with no `BAO_NAMESPACE` in the Agent's environment.
- **sops writes YAML with 4-space indents** (T2.4), so a decrypted file (and a `textconv` diff) doesn't match the
  2-space file the student typed. Harmless; tests match `    password:`.
- **`min_decryption_version` closes the `textconv` diff too** (T2.4): `git diff`/`git log -p` over an older commit
  stops with "ciphertext or signature version is disallowed by policy (too old)". Lab 6 says so.
- **`pkill -f "bao agent"` inside `su - x -c "..."` kills its own shell**, whose command line contains the same
  text; use `pkill -f "[b]ao agent"` in scripts (T2.6). Typed at a prompt it's fine.
- **Only `STUDENT_COUNT` accounts exist** (3 locally): tests default to student03, and a walk-through as a fresh
  student needs one that hasn't done labs 3-6 yet.
- **podman-compose appends `build.args` across files** (T3.1), as it does lists: a module's `JOB_TOOLS: ""` and the
  overlay's `JOB_TOOLS: "bao sops"` both reached the build. The module leaves the arg to the Dockerfile's default.
- **`RUN --mount=type=bind,from=<stage>` works in podman 5.7 / buildah 1.42** (T3.1): the pool copies `bao` and
  `sops` from the terminal image without a second pin. Both are static, so they run on the Alpine runner image.
- **The runner image's `/data` belongs to uid 1000, and `useradd` hands out 1000 first** (T3.2): the first runner
  user owned a volume every runner shares. The supervisor gives `/data` to root and makes runner users from uid 20000.
- **A Python PID 1 leaves zombies** when a killed runner's processes are re-parented to it (T3.2): the pool runs
  under `tini`.
- **Other sessions share this working tree**: a file staged with `git rm` was swept into another session's commit
  (1657cf6 carries the spike deletions of T3.1). Stage right before committing.

- **Forgejo 16 makes forks with Actions off** (T3.9): `DEFAULT_FORK_REPO_UNITS` is code and pull requests only,
  so a fork's `actions/secrets` API answers 404 and its workflows never run. The runner-pool module sets
  `FORGEJO__repository__DEFAULT_FORK_REPO_UNITS=repo.code,repo.pulls,repo.actions`; forks made before that setting
  keep Actions off (turn it on in the fork's Settings → Units, or PATCH `has_actions`).
- **The spool has a gap between "file taken" and "runner listed"** (T3.9): `useradd` takes about a second, and the
  controller saw the runner nowhere and started another (4 runners for a min of 2). The controller now counts
  every runner it registered as starting until `state.json` lists it, up to `GRACE`.
- **A Python PID 1 ignores SIGTERM** (T3.9), so `podman stop` waited its 10 s: the controller sets a handler
  (the pool runs under `tini`, which forwards it).
- **`./run.sh` volumes are prefixed `engine_`** (the compose project is `engine/`): check a teardown with
  `podman volume ls -q | grep '^engine_'`, not by the `workshop_` container prefix. This machine also holds ~31
  anonymous volumes from older stacks; none belong to a running workshop.
- **Slide overflow checks**: a section whose `scrollHeight` beats its height by a few pixels (list margins) or a
  `lead` page's bottom margin is not overflow; list the elements whose box leaves the section, and look at the
  screenshot.

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

### 2026-09-23 — Plan review with the user
- User approved P0. New decisions S18-S22 (§1): lab count follows the concepts (lab 10 optional; 6 and 7 core),
  labs 8-9 half-configured, CI login by script with a "how you'd do it at work" slide (mirroring actions is a
  follow-up in §13), T0.4 as an uncommitted local Caddyfile edit, and the risky P0 tasks first.
- Checked in the repo: `/ui` and `/v1` are free in the gateway. Local `PUBLIC_BASE_URL` is `http://localhost`
  (no TLS); the VM uses a real name with a Let's Encrypt certificate. Forgejo's `ROOT_URL` is
  `${PUBLIC_BASE_URL}/git/`. `STUDENT_COUNT` is a fixed pool (30 by default).
- Early signs from the pinned images: Forgejo 16.0.4 has Actions ID-token code; `forgejo-runner:13` has `one-job`.
- Added to the plan: a provisioner identity instead of root (§5.1), pinned tools in the runner-pool image, the
  `Authorization` header strip (§5.4), and the issuer-reachability risk (§10.7, §12 Q1).
- Q1 options for UI single sign-on: (A) an overlay-only "issuer shim" in OpenBao's network namespace that answers
  for the public URL and forwards `/git/*` straight to `git-server:3000`; (B) engine changes: a network alias for the
  public name on the gateway plus a gate exemption for Forgejo's OIDC endpoints (doesn't work for `localhost`);
  (C) no SSO: log in to the UI with a token from the CLI, and show SSO on a slide. User chose **A** (S23), with C
  as the fallback.

### 2026-09-23 — T0.2, T0.3 (skeleton and pins)
- `workshop.env`, placeholder content and a spike overlay: one `openbao` service (raft storage on the
  `openbao_data` volume, UI on, plain HTTP on `workshop_lab`, config in `compose/openbao/config.hcl`) and the
  terminal image `gitopsdojo/web-terminal:vault-fundamentals`.
- **Pins** (all sha256-verified in the Dockerfile per architecture; OpenBao 2.7.0 came out today, so 2.6.3, the
  patch on the stable line, is used for now):
  - OpenBao image `ghcr.io/openbao/openbao:2.6.3`, index
    `sha256:a60afafda36337abe833c4a63894bf1095098f29abea4091e7e555a33dd52889`; amd64
    `sha256:99c8dd178200d9a5f1a0420d6b1923514280e31e9271bdd92c69f765738c42aa`, arm64
    `sha256:24907b790a5e1480193fcdc8ef4a05ecf8d35d942ce8aa38294277b2a23f43b6`. The pulled image's digest matched.
  - `bao` 2.6.3 (`openbao_2.6.3_linux_<arch>.tar.gz`), `sops` 3.13.3, `gitleaks` 8.30.1 (amd64 asset is `x64`).
- Verified on the real stack (amd64, WSL on the desktop): `./run.sh list` shows the workshop; all containers up and healthy;
  `bao status` from `su - student01` answers (after moving `BAO_ADDR` into zshenv, §14); tool versions print.
  After a manual init/unseal (spike only, keys kept out of the repo), `bao namespace create students/` and
  `students/student01` work, a KV v2 secret written in the namespace reads back, and the root namespace can't see it.
- Not tested: arm64 (checksums come from the release files but no arm64 build was run).
- Next: T0.6 (Actions OIDC), per the S22 order.

### 2026-09-23 — T0.6 (Forgejo Actions OIDC → OpenBao)
- Spike: `spike/t06-ci-oidc.sh` (re-runnable). JWT auth in `students/student01` with
  `jwks_url=http://git-server:3000/api/actions/.well-known/keys` and `bound_issuer=${PUBLIC_BASE_URL}/git/api/actions`;
  role `ci-main` bound to `repository=platform-team/vault-fundamentals`, `ref=refs/heads/main`, `aud=openbao`, policy
  reading `kv/data/ci/*`. A temporary instance-wide runner (`runner:13`, v13.2.0, `host` label) on `workshop_lab`.
- Result: main of the right repo logged in and read the secret; a `feature-x` push of the same repo and a push to
  `other-app` were refused with HTTP 400. The 400 body wasn't visible (busybox `wget`); since the three runs differ
  only in the bound claims, that is almost certainly the claim check. Labs will use `curl`, which shows the message.
- Found the malformed token URL (§14) and planned the `dojo-ci-token` helper (§5.5).
- **Follow-up the same day:** the user asked to resolve the URL bug inside the lab rather than upstream (S24). The
  issuer shim (`spike/shim/Caddyfile`, run with the gateway's Caddy 2.11.4 for the spike) in `spike_runner`'s network
  namespace makes the unmodified `$ACTIONS_ID_TOKEN_REQUEST_URL` work; all three runs gave the same results
  (`9da105f`).
- Added a declarative file audit device to `compose/openbao/config.hcl` (the API refuses, §14). The audit log,
  via `sys/audit-hash`, confirmed the refusals: `claim "ref"` for the branch, `claim "repository"` for the other repo.
- Left running for T0.7: containers `spike_runner` + `spike_runner_shim`, repo `platform-team/other-app`,
  branch `feature-x`.
- Next: T0.7 (one-job runners, Forgejo API for waiting jobs and runner state, start-up time, memory).

### 2026-09-23 — T0.7 (one-job runners, API, timing, memory)
- Spike: `spike/t07-runners.sh`. Queued a job with no runner online, registered an ephemeral runner through
  `POST /admin/actions/runners`, ran `forgejo-runner one-job --wait` in a container.
- Results (details in §6.1 and §6.3): the job was picked up 3.8 s after the container started, ran 25 s, the runner
  exited 0 and Forgejo removed the ephemeral registration. The jobs endpoint lists waiting jobs with a `handle` that
  `one-job --handle` can claim. Runner RSS about 23 MB during a job. A killed runner's registration stays `idle`
  (stale), so the controller must reconcile against its own processes.
- Jobs ran as the runner's user with the workspace under `$HOME/.cache/act/<hash>/`, so a Linux user and home per
  runner (T0.8) isolates workspaces.
- Cleaned up: all spike runner registrations deleted through the API (all `204`), queued runs cancelled, spike
  containers removed. Test repos `other-app` and `runner-test` stay until P0 ends.
- Not measured: the `active` status value (the runner list wasn't queried mid-job); memory of real lab jobs.
- Next: T0.8 (process-pool isolation).

### 2026-09-23 — T0.8 (process pool) and wrap-up for the day
- Spike: `spike/pool/` (runner:13 + util-linux + shadow, a small supervisor) and `spike/t08-pool.sh`. Results and
  the chosen mechanism (a user + PID namespace per runner via `unshare`) are in §6.2.
- Two gotchas on the way (§14): parallel `useradd`/`userdel` collide; a new push cancelled queued runs from an
  earlier attempt, which unregistered their ephemeral runners.
- Added `spike/init-bao.sh` so a new session can re-create the spike vault (keys were only in today's scratchpad).
- Stack left running; the spike containers (`spike_*`) removed. Test repos (`other-app`, `runner-test`,
  `pool-a/b`, `pa-*/pb-*`) and the unsealed spike vault go away with the next `./run.sh stop`.
- Next session: see "Where we stopped" in §0.

### 2026-09-24 — T0.4 (UI through the gateway)
- User approved the S21 Caddyfile edit: `@openbao path /ui /ui/* /v1/*` → `openbao:8200` with
  `header_up -Authorization`, in the shared-gate block after `/git`. Uncommitted, still applied.
- Fresh stack; `spike/init-bao.sh` re-initialised the vault. Results in §5.4: routes work for both roles,
  the gate holds, the framing header needed overriding (`sys/config/ui/headers`), then framed sign-in worked.
- Tested with curl and real Chromium (Playwright container). Not tested: an `/admin` tab itself (needs allocator,
  comes in P0.5); the VM's HTTPS path.
- The user asked for a brief pivot of priorities after this test.

### 2026-09-24 — P0.5/P6 replaced by `feat/workshop-modules`
- The user paused this workshop to build extensions and modules on `feat/workshop-modules` (M0-M2 done and
  live-tested there; M3 docs). That covers P0.5 and P6, so both are struck from §11 (S25).
- Updated §0 (stash, stopped stack, merge before P1), §1 (S25), §5.1, §8, §8.1 (module split and draft manifests),
  §11 and §13. Nothing else in the design changes.

### 2026-09-24 — `main` merged in (8c71f83)
- `feat/workshop-modules` merged to `main` (PR #2, fd971d2) and `main` merged into this branch (8c71f83).
  Conflicts: root README tree (kept both lines); `keyvault-workshop-plan.md` kept deleted (main had only converted it
  to CRLF). Also new on `main`: `./run.sh <workshop> --env NAME` and `GATEWAY_LISTEN` (home LAN hosting). The T0.4
  stash was not popped yet.

### 2026-09-24 — Plan adapted to modules
- `git fetch`: `origin/main` has nothing past 8c71f83, so the branch is current.
- Proposed S26-S30 (§1, awaiting the user as Q2/Q3 in §12): routes from `extensions.json` instead of the stashed
  Caddyfile edit; no `forgejo-runner`, a `runner-pool` module instead; one issuer shim per module; workshop setup as
  hooks inside `openbao-setup`; the real HTTPS path through `--env home`.
- Rewrote §8.1 (three-column split, setup order, runner image), §8, §5.1's shim and runner rows, §0; added T0.11
  and a draft P1 block in §11. Nothing built or run.
- The user confirmed S26-S30 (Q2): `runner-pool` a module now, setup hooks in `openbao-setup`. Stash dropped (Q3).

### 2026-09-24 — T0.11 (terminal on the image chain)
- Overlay no longer sets `build:`/`image:` on `web-terminal`; the Dockerfile starts `ARG BASE` / `FROM ${BASE}` and
  restates the base HEALTHCHECK. `--dry-run` clean; `./run.sh vault-fundamentals` built the `:vault-fundamentals`
  link on `:base`, the terminal is `healthy`, and as `student01` `BAO_ADDR` is set and `bao`, `sops`, `gitleaks`
  answer. The stack is left running with OpenBao **not initialised** (T0.5 starts with `spike/init-bao.sh`).

### 2026-09-24 — T0.5 (UI SSO through Forgejo)
- Spike `extensions.json` (routes `/ui`, `/v1` on the `shared` gate, Vault card and `/admin` tab, status check)
  and the SSO shim as an overlay service in OpenBao's network namespace. No engine edit.
- `spike/t05-sso.sh`: framing header, Forgejo OAuth2 app, OIDC method + role, `student`/`facilitator` policies,
  `students/<name>` namespaces, one entity per account. `spike/t05-sso-browser.py` (Playwright) passed on the
  local stack (`http://localhost:8080`) and, after `./run.sh vault-fundamentals --env home` (no `stop`, then
  `init-bao.sh` to unseal), on `https://dojo.macleodtech.ca` with the shim's CA. Entities checked by id:
  student03/student01 → `student`, facilitator (`workshop-admin`) → `facilitator`. Findings in §5.4 and §14.

### 2026-09-24 — `run.sh` fix, T0.9 (sops + transit)
- With the user's approval, `engine/run.sh` (a24d0e7) re-reads `.env.<name>` in the modules block, so `--env home`
  keeps its `PUBLIC_BASE_URL` for workshops with modules. Checked by replaying the source order for tofu-basics.
- `./run.sh stop` (the user asked), then a clean `./run.sh vault-fundamentals` locally and `init-bao.sh`.
- `spike/t09-sops.sh` (79a005d), as `student01` in the real terminal: encrypted `secrets.yaml` with transit in
  `students/student01`, committed it (plaintext absent), decrypted with a decrypt-only token; encrypt-only and
  default tokens refused (403); rotate + `sops rotate` fine; path-embedded namespace also works. Findings in §14.
  Stack left running (locally), OpenBao unsealed, keys in the session scratchpad.

### 2026-09-24 — T0.10 (P0 write-up)
- §10 is now a results table: every item verified, no fallback needed; what P0 didn't cover is listed there and
  carried into P1/P3/P5.
- Plan changes: lab 6 teaches the namespace-in-path key URL (§4); `VAULT_ADDR` and `SOPS_DISABLE_VERSION_CHECK`
  in the terminal (§5.1, §8.1); `app-host` slots use a user + PID namespace, not `hidepid` (§5.6); the Vault card
  and tab open `/ui/vault/auth?with=oidc` (§8.1); P1 tasks got verify lines and the spike clean-up (§11).
- New questions Q4 (OpenBao 2.6.3 or 2.7.x) and Q5 (Forgejo session before SSO; option (b) is an `engine/` edit).
- Stack still running locally, OpenBao unsealed (keys in the session scratchpad).

### 2026-09-24 — P1 starts; T1.1 (`modules/openbao/`)
- User answered Q4 (latest OpenBao, S31) and Q5 (`/forgejo-login?next=`, an approved engine change for T1.3, S32).
- **Pins, OpenBao 2.7.0** (released 2026-09-23): image `ghcr.io/openbao/openbao:2.7.0`, index
  `sha256:71156a1c6623a5fa3f5e61b0c6a8ead0faf0df29a778339188443551995d1315` (checked against the registry); amd64
  `sha256:6d575d906d70d40b9d789149c8dc09897291c5a1707d4d0ba8a459eaaa94c8c4`, arm64
  `sha256:4ca9310dd2a50c746d4227f44058088ee0470a8470031ee3f09cc8b1a69dd7f6`. `bao` tarballs from `checksums.txt`
  (the file name changed from 2.6's `openbao_<v>_checksums.txt`).
- T1.1 (2f47607): `modules/openbao/` has `compose.yml` (`openbao`, the SSO shim, all volumes named, plus
  `openbao_logs` for the audit log), `config.hcl`, `sso-shim/Caddyfile` (`/git/*` only; the ID-token rewrite stays in
  `spike/shim/` for `runner-pool`, S28), `module.env` (`OPENBAO_MEM_LIMIT`, `OPENBAO_PUBLIC_HOST`),
  `extensions.json` (card and tab on `/ui/vault/auth?with=oidc`), `terminal/` (`bao` 2.7.0, `BAO_ADDR`, `VAULT_ADDR`),
  `README.md`. The workshop has `MODULES="openbao"`, no overlay, and its terminal link adds sops, gitleaks and
  `SOPS_DISABLE_VERSION_CHECK=1`.
- Verified locally (WSL on the desktop): `./run.sh modules` lists it; `--dry-run` clean; `./run.sh vault-fundamentals` over the
  running 2.6.3 stack (no `stop`) upgraded the vault in place (data kept, sealed until `init-bao.sh`); all containers
  up, terminal and shim healthy. As `student01`: `BAO_ADDR`, `VAULT_ADDR`, `SOPS_DISABLE_VERSION_CHECK` set, `bao`
  2.7.0; `t09-sops.sh` passes; `t05-sso.sh` + `t05-sso-browser.py` pass (student → `student`, facilitator in the
  `/admin` tab → `facilitator`, the tab opening on `?with=oidc`). `./run.sh stop --dry-run` lists all four module
  volumes. Not run: `--env home`.
- The user pointed out that the tests run in WSL on their desktop, not on a laptop. The plan's wording is fixed
  where it described the test machine (S13's "laptop" as a class target stays).
- With the user's go, a real `./run.sh stop`: every named volume and container is gone, including the four
  module volumes, which completes T1.1's check.
- T1.2 started: `modules/openbao/setup/` written (see T1.2 in §11), not wired into `compose.yml` and not run.
- End of day: the stack is stopped. Tomorrow's steps are in §0.

### 2026-09-25 — T1.2 done (33e1d36)

- Wired `openbao-setup` into `modules/openbao/compose.yml`. First run crash-looped: the provisioner policy write
  right after unseal got a 500, setup died before creating the token or revoking root, and every restart then
  failed on the missing token file (and root stayed live, unrecoverable). Fixed with retries after unseal and by
  keeping the root token on `openbao_setup` until it is revoked (§14). The provisioner policy also gained
  renew/lookup-self and `students/sys/namespaces/*`; a `trap` makes `stop` quick.
- Re-test passed locally (T1.2 *Verify*); `./run.sh stop` left nothing behind. `init-bao.sh` and `t04-*.py`
  deleted; `t05-sso.sh` uses the provisioner token; module README updated.
- The user runs other workshop stacks here for manual validation: check `podman ps` first and hand the machine
  back (§0).

### 2026-09-25 — T1.3 done (ca89792, 82ff676)

- `engine/`: `/forgejo-login?next=<path>` (S32), same-origin paths only; the Vault card and `/admin` tab go
  through it. `setup/sso.sh` (sourced by `setup.sh`, provisioner token): Forgejo OAuth2 app via busybox `wget`,
  `oidc` method and role, the shim's CA on HTTPS, an entity and alias per account.
- First browser run: logins made their own entities (the alias lookup always printed "Success!", §14); fixed by
  always writing the alias. Forgejo 16 ignores `skip_secondary_authorization`. Stopping setup now takes ~4 s
  (was 10 s and a kill).
- `sso_browser.py` passed locally and on `--env home`; `./run.sh stop` left nothing; allocator unit tests pass.
  `spike/t05-sso.sh` and `t05-sso-browser.py` retired (b5b9faa).

### 2026-09-25 — T1.4 and T1.5 built (not yet run)

- **T1.4 (55de8e1):** `openbao-broker` (root, `SO_PEERCRED`) signs a two-minute RS256 JWT (`iss dojo-terminal`,
  `aud openbao`, `sub` the login name) with `openssl` (from `ca-certificates`); key on `openbao_broker_key`, public
  half on `openbao_broker_pub` for `setup/cli.sh`, which mounts `jwt` in the root namespace (role `terminal`) and
  aliases each login name to the SSO entity. `openbao-login --quiet` in zshenv writes `~/.vault-token` when missing
  or under an hour left, and leaves a user's own `bao login` token alone. Signature checked offline with `openssl`.
- **T1.5 (2109b9d):** hook `compose/openbao-setup.d/10-tenancy.sh` (overlay `COMPOSE_OVERLAY`): `secret/` KV v2, a
  `welcome` secret per student (`cas=0`, so re-runs add no versions), namespaces `students/<name>`, and the templated
  `student` policy. **Deviation from §5.3:** namespace admin comes from `students/{{identity.entity.name}}/*` in the
  root policy, not an admin policy plus group inside each namespace: same effect, nothing per namespace to keep in
  step. Check in the live pass that templating works in that path.

### 2026-09-25 — T1.6 and T1.7 written (not yet run)

- **T1.6 (a1da88a, f7b8bf8):** `content/lab/` README, lab0-3, cheat-sheet; slides `index.md`, `lab-index.md`,
  `labs.md`, `presentation.md` (parts 1-2 and the Azure comparison, cut to what labs 0-3 use). Lab 1 is a local repo
  (`~/lab/leaky-app`, nothing pushed) with made-up `ghp_` tokens. `student.hcl` now also lists `secret/metadata/` and
  `secret/metadata/students/` (for UI browsing) and reads `sys/policies/acl/student` (lab 2).
  **Dropped from lab 3:** "read your own audit trail" (students can't read the audit file); it moves to lab 11.
  **Unverified guesses to check live:** `gitleaks git --pre-commit --staged` flags on 8.30.1; that the `ghp_`
  strings trip gitleaks; `bao token create -policy=app-read` in the namespace with only `sudo` from the root policy;
  where the UI's namespace picker is; a git identity (the terminal sets none, lab 1 sets it).
- **T1.7:** `workshops/README.md` table, root `README.md` (status, layout, services table, the broker bullet).

### 2026-09-25 — Live pass: P1 done

- Local stack (`./run.sh vault-fundamentals`). First start: setup never became ready (the `retry` counter bug,
  §14), fixed in c7815c9 and re-run. Then `cli_login.sh` PASS (15 checks), `tenancy.sh` PASS (9), `sso_browser.py`
  PASS. Labs 0-3 run as a student in the terminal: all as written except lab 3's app token (now `-orphan`,
  1dbe33b). UI: click-through to the welcome secret, the namespace picker, and creating a policy in the
  namespace all work. Slides: no overflow; slide 9's emoji arrows replaced. A setup restart keeps the welcome
  secret at version 1. `./run.sh stop`: nothing left.

### 2026-09-25 — P2 (labs 4-6) done

- The user said go for P2. Task block written (T2.1-T2.6).
- **T2.1 (1f8d7c5):** `hvac` 2.4.0 and deps as pinned pure-Python wheels (`hvac-wheels.sha256`), fetched with `wget`,
  installed offline by pip run from its own wheel. Built through `./run.sh`; `is_authenticated()` True.
- **T2.2-T2.6 (9ed5f8f):** labs 4-6, presentation Parts 3-4 (+2 rows on the Azure table), `labs.md`, `lab-index.md`,
  cheat sheet, lab README, lab 3's "Next" link. `tests/labs_4_6.sh` (student03, resets itself): PASS after two test
  fixes (sops' 4-space YAML; `pkill` killing its own shell, §14). `tenancy.sh` and `cli_login.sh` still PASS. A
  literal walk-through of every block as student02: labs 4 and 6 as written; lab 5's catch-up `kv put` hit the
  mount-upgrade error and broke the rest, so the block now retries (re-checked). Agent renewed and re-logged in within
  ~130 s, the fingerprint changed ~3 s after a rotation. Slides 15-23 and `labs.md` 1-4: no overflow (Playwright
  1280×720); lab reader renders labs 4-6 (lab 6's reader 404s prefetching `lab7.md.txt` until P3 writes it).
- While the stack started, `workshop_cloud_api`/`workshop_cloud_host` (tofu-basics' `dojo-cloud`) were running too,
  started a few minutes earlier than the vault stack, not by this session. Left alone; told the user.

### 2026-09-25 — P3 built (not yet run live)

- The user said go for P3, with the build done now and the live run at the end (another session had the lab stack).
  Task block written (T3.1-T3.9), with the design fixed there: pool + controller + spool volume, `JOB_TOOLS` from the
  terminal image, forks for per-student repos.
- **ee6e59b, `modules/runner-pool/`:** `pool/supervise.py` (spool protocol, user + PID namespace, prlimit, clean-up,
  the shim's CA on `https://`), `controller/controller.py` (Forgejo API, Auto/Manual, dead-registration clean-up,
  lights, a start-failure pause, HTTP with token + facilitator + CSRF header), the panel, the ID-token shim,
  `module.env`, `extensions.json`, README, `tests/test_controller.py` (24 pass), `tests/pool.sh` (unrun).
- **5be3d6e, the workshop:** `MODULES="openbao runner-pool"`; `openbao` on `runner_net`; `JOB_TOOLS="bao sops"`;
  hook `20-ci.sh` (`auth/jwt-ci` in each namespace, S19); labs 7-8; presentation Part 5 (5 slides, one more Azure
  row), `labs.md`, `lab-index.md`, cheat sheet, lab README, seed repo README; module tables in the READMEs;
  `tests/labs_7_8.sh` (unrun; it takes the workflows from `lab8.md` itself).
- Checked without a stack: see §0. Found and fixed on the way: duplicate build args, uid 1000 and `/data`, zombies
  (§14). The spike's `pool/`, `shim/`, `t06`-`t08` are gone (in 1657cf6, §14); `t09-sops.sh` stays.

### 2026-09-25 — P3 live pass (T3.9): done

- The user said to run the live tests and close P3. The machine was free (`podman ps` empty); started
  `./run.sh vault-fundamentals`.
- First start: 4 runners for a min of 2 (the spool gap, §14): fixed in the controller, unit test added,
  controller restarted (its folder is mounted read-only, so no rebuild). `pool.sh`: everything passed except the
  Manual part, which assumed room below the max (3 students: max 2); the test now does − then + and checks the
  409 at the max. The controller took 10 s to stop (no SIGTERM handler): fixed.
- `labs_7_8.sh`: the repository secret 404'd. Forks come with Actions off (§14): the module now turns it on for new
  forks; the test also wrote lab 8's workflows into a folder lab 7 had removed. Restarted the stack from nothing
  (`./run.sh stop` first) for the setting; then `labs_7_8.sh` PASS, `pool.sh` PASS again (22 checks),
  `tenancy.sh`, `cli_login.sh`, `labs_4_6.sh` PASS.
- Browser (Playwright): the Runners tab and panel, labs 7-8 in the reader. Slides 24 and 25 were too full and 28
  lost its last row to the new Azure row: shortened, two KV rows merged, the lab index in three columns;
  screenshots checked.
- Pool memory peak 181 MiB. `./run.sh stop` left nothing of the stack. All fixes in d80e078. Machine free.
- **Next: P4, after the user's go.**

### 2026-09-25 — P4 built (T4.1-T4.7), live pass

- The user said go. Design and task block in §11 P4. Built: `compose/app-host/` (`apphost.py`, renamed from
  platform.py so it doesn't shadow Python's `platform`; panel; Dockerfile FROM debian slim with `bao` and Python
  packages copied from the terminal image), `app-db` (Postgres 17.11 pinned, `compose/app-db/init.sh`), hook
  `30-platform.sh`, provisioner lines for `database/`, `openbao-audit` + `bao-audit` in the openbao module
  (`hmac_accessor = false`), terminal `jq`, `psql`, `pg8000` wheels, labs 9-11, Part 6 slides, lab pages, READMEs,
  `extensions.json` (My App card, Apps tab, `/apps` identity route), tests `labs_9_11.sh`, `p4_browser.py`.
- Found on the stack: (1) **a volume mounted by two containers belongs to the user of the one podman sets up
  first**: `openbao-audit` (root) took `openbao_logs` and OpenBao couldn't write its audit file, so init failed.
  `openbao-audit` now runs as OpenBao's uid 100:1000. (2) A fresh fork has no `.forgejo/workflows/`: lab 9 does
  `mkdir -p`. (3) `bao token lookup -accessor` on a revoked token says `invalid accessor`. (4) Forgejo's Actions
  ID tokens are RS256 with a `kid`: the platform's openssl check works. (5) The CLI's `sys/internal/ui/mounts/...`
  look-ups clutter the audit: `bao-audit` hides them unless `--all`. (6) Slide 35 overflowed at 10 rows: smaller
  table font (scoped style); the overflow check now includes table rows.

### 2026-09-25 — P4 done (T4.8), committed

- Regression run all PASS locally: `cli_login.sh`, `tenancy.sh`, `labs_4_6.sh`, `labs_7_8.sh`, `pool.sh`; then
  `labs_9_11.sh` on student01 and student02. It found three things, all fixed and re-run:
  (1) `openbao-audit` read the file once a second, so lab 11's query right after the spare token was made missed
  it (`$CHILD` empty). Each `/entries` query now reads the file up to date first. (2) Lab 10's "another student's
  database" step used `app_student02`, which is student02's own: it now picks a neighbour. (3) A redeploy kept the
  last version's `secrets/db.env`, so a fresh lab 9 app showed lab 10's database login. A deploy now empties the
  slot's home first.
- `./run.sh stop`: no containers, no `engine_` volume. Commits 91031d6 (`openbao-audit`), 21daddf (the rest).
  The user approved the two `openbao` module changes. Their browser pass of P4 is still open.

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
