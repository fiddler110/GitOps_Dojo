# Modules

A module is a reusable bundle of services, terminal tools, front-door entries and defaults that a workshop opts into
with `MODULES="a b"` in its `workshop.env`. `./dojo modules` prints the live list and who uses each. How to *write*
one is in the [Authoring guide](authoring.md#6-writing-a-module); each module's own `README.md` is the detailed reference.

| Module | One line | Used by |
|---|---|---|
| [`runner-pool`](#runner-pool) | Single-use Forgejo Actions runners, autoscaled, with a Runners panel | dns-as-code, vault-fundamentals, cloud-policy-as-code, dojo-introduction, ctf-defend (+test) |
| [`dojo-cloud`](#dojo-cloud) | Azure-inspired training cloud: ARM-style API, portal, real containers | tofu-basics, cloud-policy-as-code, dojo-introduction |
| [`dns-gate`](#dns-gate) | `dns-api`: a gate in front of PowerDNS with per-account keys and CI by ID token | dns-as-code, cert-autorenewal, dojo-introduction |
| [`dns-ui`](#dns-ui) | Live DNS Zones page and PowerDNS-Admin for the facilitator | dns-as-code, cert-autorenewal, dojo-introduction |
| [`openbao`](#openbao) | One OpenBao for the class, SSO through Forgejo, audit reader, `bao` CLI | vault-fundamentals, ctf-secrets-config |
| [`sensei`](#sensei) | PR reviewer, help desk (`sensei ask/why/hand`), stuck radar | all main-path workshops |
| [`achievements`](#achievements) | Scoring, toasts, leaderboard, challenges, certificate | any pack with a catalog, when `ACHIEVEMENTS_ENABLED` |
| [`ctf-range`](#ctf-range) | Vulnerable targets, boxed Docker host, flag service, attacker bots | ctf-* packs |
| `_shared` | Single copies of helper code (`dojo_http.py`, `adapter_client.py`) | built into several modules via `SHARED=` |

## Anatomy of every module

```text
modules/<name>/
  README.md           # first line after the heading is the one-line summary ./dojo modules prints
  module.env          # defaults; workshop.env overrides them
  compose.yml         # services, volumes, networks; may extend engine services
  extensions.json     # cards, /admin tabs, routes, status checks, resets
  terminal/Dockerfile # ARG BASE / FROM ${BASE}; start hooks as /etc/dojo/start.d/50-<name>.sh
```

Every part is optional and found by name. At start, `module.env` is sourced first, then `.env` and `workshop.env`
again, so the workshop wins. Compose files merge in `MODULES` order; the module's terminal link joins the image chain
as `:<workshop>.<module>`.

---

## runner-pool

**Single-use runners for every repo on the instance, autoscaled.** Each runner takes exactly one job and is then
deleted with everything it left, so no job can find another's files or processes (the idea of GitHub's Actions Runner
Controller). It is the only runner module: it turns on Actions in Forgejo and defines `runner_net`.

| Part | Role |
|---|---|
| `runner-pool` | One container that drops all but six capabilities, `no-new-privileges`. For each config the controller drops in `/spool/start/` its supervisor creates a Linux user (home `0700`, umask 077, own `TMPDIR`) and runs `forgejo-runner one-job` in its own user + PID namespace with `prlimit` caps |
| `runner-pool-shim` | Caddy in the pool's namespace that answers for the public URL and routes Actions ID-token requests to `git-server` (Forgejo malforms the token URL under `/git/`) |
| `runner-controller` | Every 3 s reads runners and waiting jobs, deletes dead registrations, scales Auto (warm idle minimum up to a cap) or Manual. Checks every request itself: gateway token, facilitator identity, `X-Requested-With` on POSTs |
| `runner-token-init` | One-shot: mints a revocable `write:admin` token so the controller never holds the admin password |

- **Panel** (`/admin` → Runners): a light per runner (green ready, yellow running with the repo, red failed/offline/stuck),
  − / +, Auto/Manual.
- **Settings**: `RUNNER_MIN_IDLE` 2, `RUNNER_MAX` (default ceil(students/3), 2-12), `RUNNER_IDLE_TIMEOUT` 120 s,
  `RUNNER_JOB_TIMEOUT` 900 s, `RUNNER_LABELS` `host:host`, `RUNNER_POOL_MEM_LIMIT` 2g, `RUNNER_POOL_PIDS` 2048.
- **A workshop using it** names job tools with `JOB_TOOLS: "bao sops"` (copied from the terminal image just built) and
  adds `runner_net` to whatever its jobs may call. Jobs use `runs-on: host`.
- **Why processes, not containers**: the stack has no container-engine socket anywhere; this keeps it that way.
- **Host caveat**: Ubuntu 24.04 AppArmor user-namespace restriction, and macOS rootful Podman (`--env mac-podman`).

## dojo-cloud

**An Azure-inspired training cloud**: an ARM-style API, a portal and real containers, reached by the real `azurerm`
provider.

| Part | Role |
|---|---|
| `cloud-api` | Control plane (workshop_lab + cloud_net). `:443` ARM, login and metadata under a private CA with aliases `management.dojo.cloud`, `login.dojo.cloud`; `:8080` portal and site ingress. Authenticates the token, checks subscription, runs the **Policy** engine, runs containers by fixed templates. Rate-limited per student (burst 200, 20/s) |
| `cloud-host` | Privileged Docker-in-Docker on `cloud_net` only, no published port, only a unix socket shared with `cloud-api` (`0660 root:cloud`, gid 1900) |
| `terminal/` | Root-owned credential broker, `dojo-env` (gives each shell its own `ARM_*`), `start.d/50-dojo-cloud.sh` (installs the CA trust bundle) |

- **Front door**: **Dojo Cloud** card, `/admin` tab (class-progress board for the facilitator), `/cloud` route
  (identity gate), `/readyz` status check.
- **Residual risk accepted (D9)**: the host stays privileged; the box (internal network, no port, single client,
  fixed templates) is what limits it.
- **Settings**: `CLOUD_HOST_MEM_LIMIT` 3g, `CLOUD_HOST_PIDS_LIMIT` 4096, `CLOUD_API_MEM_LIMIT` 256m.
- Tests: `cd modules/dojo-cloud/cloud-api && python3 -B -m unittest test_portal_api test_executor test_policy_auth test_readiness`;
  `python3 -B -m unittest test_parity` (broker and API derive identical ids).

## dns-gate

**`dns-api`**, a gate in front of the workshop's PowerDNS API, with a key per account. The workshop runs PowerDNS as
service `dns-server` (API `:8081`, key `POWERDNS_API_KEY` never given to students) and adds `dns-api: depends_on: [dns-server]`.

`X-API-Key` carries one of three things:

| Key | May |
|---|---|
| The **read key** (`DNS_GATE_READ_KEY`, public) | Read only |
| An **account's own key** `<user>.<mac>` | Own `<user>.<parent>` and everything under it for each `DNS_GATE_USER_PARENTS`; in a shared zone (`DNS_GATE_SHARED_ZONES`) a PATCH only of its own names |
| A **Forgejo Actions ID token** (audience `dns-api`) | Change CI-only zones (`DNS_GATE_CI_ZONES`) only when `repository == DNS_GATE_CI_REPO`, `ref == refs/heads/main` and `event_name == push`. Any other valid token reads |

Server config, TSIG keys and out-of-lab zones are refused to everyone. One JSON audit line per zone change. Terminals
get `DNS_API_KEY` from `~/.config/dojo/dns-api-key` (`50-dns-key.sh`). It also reports events to achievements.

## dns-ui

A live, read-only **DNS Zones** page (`/dns`, shared gate: the data is what `dig` already shows) that highlights records
added, changed or removed since the page opened, and **DNS Admin** (`/dns-admin`, facilitator only) running
PowerDNS-Admin already signed in, for making the "dashboard edit" that the next `dnscontrol push` removes. Needs
PowerDNS as `dns-server` with `networks:` in map form. `dns-admin` sits on `dns_admin_net` with only the gateway and
`dns-server`, so students cannot reach it around the gate.

## openbao

One OpenBao for the class, built for vault-fundamentals.

- `openbao` (network holder), `openbao-server` (raft storage, UI on, file audit device, plain http on `workshop_lab`),
  `openbao-setup`, `openbao-sso-shim`, `openbao-audit`, plus `openbao-reset` for student resets.
- **`openbao-setup` on every start**: unseal (one key share on a volume, a lab shortcut), make a *temporary root*,
  write policies, mint a 2-hour provisioner token (and a reset token if the workshop has `reset.hcl`), revoke the root,
  run the workshop's hooks, revoke the provisioner. No live root or provisioner token remains on disk.
- **SSO**: Forgejo is the OIDC provider (a confidential OAuth2 app); one identity entity per account; policy `student`
  for students and `facilitator` for the facilitator. Each account approves Forgejo's Authorize page once.
- **CLI login**: a root broker in the terminal signs a two-minute RS256 JWT for the caller's uid (`SO_PEERCRED`); the
  `jwt` auth method trades it for a token written to `~/.vault-token`. No password anywhere.
- **Audit**: `openbao-audit` follows the audit file and answers `GET /entries?ns=` to a caller presenting their own
  token. The **Audit** tab and `bao-audit` CLI use it.
- **Rate limit**: a per-namespace `sys/quotas/rate-limit` (`OPENBAO_NAMESPACE_RATE`, 200/s) as a tripwire.
- **Accepted risks** (told to the class): one unseal share on a volume, plain http, `hmac_accessor = false` (so tokens
  can be traced by accessor).

## sensei

An offline reviewer and support desk. It reads like a helpful senior engineer; it is not an AI model.

- **Reviewer**: reviews every open PR into `SENSEI_REPO`'s `main`. Rules live in code (`roster.py`, `dnsrules.py`),
  and it only approves a change to `SENSEI_FILE` that passes them. A good PR is merged (or, in *approve* mode,
  approved) with a comment; others get a comment once per push and are flagged **needs-review**. A stale branch gets a
  `git merge main` pushed to it.
- **Modes**: default merges the roster PR (git-fundamentals). `SENSEI_MODE=approve` (dns-as-code) approves but never
  merges, and requires a student to have reviewed someone else first (or `SENSEI_PATIENCE_SECONDS` 180).
- **Terminal commands**: `sensei help|status|review|approve [--force]`, `ask "..."`, `why`, `hand "..."`, `inbox`, `check`.
- **Support desk**: hand-written answers (`modules/sensei/answers/shared.json`, optional `workshops/<name>/sensei/answers.json`)
  first, then a section-by-section search of the pack's own `content/lab/*.md`; `why` explains the nearest known error
  from the last 60 screen lines using a table derived from the labs' "You see | Cause / fix" tables plus
  `patterns/shared.json` and the pack's `sensei/patterns.json`. Challenge headings are never indexed.
- **Facilitator tab**: PR list with status/why/minutes stuck, **Merge anyway**, **Comment**, **Look now**, **Pause**
  (`SENSEI_ENABLED=0` starts paused), raised hands with replies, and the **stuck radar** (`failing`, `stalled`,
  `quiet`; per-student times and exit codes, never command text; facilitator-only, never nudges a student itself).

## achievements

Scoring layered over a pack's labs. On by default (`ACHIEVEMENTS_ENABLED`) for packs with
`workshops/<name>/achievements/catalog.json`; the catalog is validated before start and an error stops it.

- **Catalog** (data files): `catalog.json`, `labs/labN.json` (milestones), `funny.json`, `challenges/cN.json`,
  `capstone.json`, `seeds/`. Plus `modules/achievements/catalog/shared.json` (cheating tiers). Ids are forever
  (retire with `"retired": true`). `render_md.py --all` regenerates each `ACHIEVEMENTS.md`; `edit.sh <workshop>` opens a
  local editor.
- **Default points**: milestone 10, funny 0, challenge 100, capstone 300.
- **Triggers** (`match`): `shell` (command, flags, exit, branch, merging, output regex), `forgejo` (event/action),
  `cloud`/`bao`/`ca`/`dns`/`ctf`/`soc` adapter events, `verify` state milestones, `service`-fired cheats.
- **Service** (`server.py`, `store.py`, `ledger.py`): signed events (HMAC), replay protection, a masher limit,
  `state.json` on a volume, student pages under `/achievements`, facilitator tab under `/achievements-admin`.
- **Terminal**: `dojo-check`, `dojo-challenge start|reset`, a zsh prompt hook that echoes new unlocks. Tamper-evident:
  an edited client or someone else's identity headers cost a point ("cheat-client", "cheat-identity").
- **Challenges**: a student's own seeded repo, verified by the service with assertions that must mention `{user}`;
  exactly two hints; Start/Reset buttons from `<!-- dojo-challenge: c1 -->` markers in a lab; `watch` challenges
  re-checked over time.
- **Privacy**: commands are matched and dropped; no command text is stored.

## ctf-range

The shared runtime of the CTF series.

| Part | Role |
|---|---|
| `targets/<name>/` | One self-contained vulnerable app per directory, with its README, flaw and reference exploit (14 in the catalog, `customer-portal` is #14 for CTF-5) |
| `ctf-host` | Boxed privileged Docker-in-Docker daemon holding the target slots; offline image import; scoped per pack via `CTF_HOST_BUILD_TARGET` |
| `ctf-controller` | The single unprivileged client of `ctf-host` (pull/create/start/stop/rm, never build). Reconciles one always-on slot per student (CTF-5), runs the **AttackManager** (queue, state machine, idle auto-stop) for CTF-1..4, and serves `/redeploy` |
| `ctf-builder` | The only client allowed to ask for a **build**. Clones the student's repo itself, builds and pushes to the in-lab registry; never accepts a Dockerfile or tar |
| `registry` | Internal-only image registry on `ctf_ops` |
| `ctf-flags` | Verifies a student's HMAC flag and credits achievements; `dojo-flag` is its CLI |
| `attacker-bot`, SOC feed, wall of shame | CTF-5: a swarm drives each student's slot on a shared green → yellow → red clock |
| `terminal/` | Offensive tool suite (`nmap`, `tcpdump`/`tshark`, `sqlmap`, `john`, `ffuf`, `opa`...), `dojo-flag`, and a per-uid firewall hook that lets each student reach **only their own slot's port** |
| `lab-info/` | The Linux/shell and per-tool primer library, in `~/lab-info` and as a browser card |

Networks: `ctf_net` (targets, the only address a student terminal may reach), `ctf_ops` (internal control plane),
and `runner_net` (for CI to reach `ctf-builder` and `ctf-controller`, which needs `runner-pool` in `MODULES`).
The module's own README is long and keeps its own status notes: read it before changing the range.

---

## _shared helpers

`modules/_shared/dojo_http.py` is the one every web service uses: `gateway_user`/`is_facilitator` (identity only
alongside the right `X-Gateway-Token`, failing closed when unset), `token_ok`, security headers with a strict CSP, and
`send`/`send_json`. `adapter_client.py` is the bounded, never-raising, signed event poster to achievements
(`AdapterClient(url, secret, source).post(doc)`; off unless both env vars are set; a full queue drops events). A module
lists the files it needs in its `module.env` as `SHARED="<context>/<file> ..."`; each start copies them into
`<context>/_shared/` before building (git-ignored, never edit a copy).
