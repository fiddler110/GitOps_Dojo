# Releases

What has shipped, newest first. [`ROADMAP.md`](ROADMAP.md) holds what is still open; when an item there is done
and verified, it moves here in a line or two. Detail behind older entries (design, decisions, per-task logs) is in
[`docs/archive/`](docs/archive/), kept for reference and no longer updated.

Entries are grouped by what reached `main`. Dates are commit or merge dates; "locally" means tested on the
WSL2 desktop stack at `http://localhost:8080`.

## Unreleased: `feat/achievements` (not yet merged to `main`)

**OpenBao network holder and start-up (2026-09-30, locally).** `openbao` is now a tiny holder that owns the network namespace and `openbao-server` is the real server, so restarting the server no longer strands the SSO shim (it kept `network_mode: service:openbao`). `performance_multiplier = 1` cuts a first-start election from about 8 s to 1.7 s, and `run.sh` drops `/mnt/*` from `PATH` for podman on WSL2 (each call 1.2 s down to 0.07 s; compose up about 1:30). On the holder topology, unit, tenancy, cli_login, setup_tokens, labs 2 and 5-13, audit and browser all pass, pool passed on the earlier stack, and a server-only restart left the shim healthy. Not run: bots, load, a holder restart.

**vault-fundamentals setup and lab 12 (2026-09-30, locally).** `openbao-setup` hooks run per student in parallel (`par_each`, `enable_once`): a fresh start reaches `ready` in about 63 s and a restart in about 15 s (was about 24 s). The `lab_12` flake was real: `bao lease revoke` only queues the revoke, so the login still worked for a moment; the lab now says `-sync`. Full e2e (no pool, bots on) passes, and the three browser scripts log in through the class form.

**Achievements phase 3 and 4 for git-fundamentals (2026-09-30, locally).** Shell hook and Forgejo system webhook feed a
matcher; all 29 items have a `match`, and the hand-checked funny items fire. Challenges: `dojo-check ID`,
`dojo-challenge start/reset`, verifier plug-ins and a per-student seed in `{user}/challenge-repo`; c1, c2 and the capstone
run live with two students (isolation, hints, first blood, class-clear, reset). Lab-page Start/Reset buttons from a
`<!-- dojo-challenge: ID -->` marker. Catalog editor (`modules/achievements/edit.sh`, `enabled` field). Landing page and
workspace reordered, with a top bar (Home, Sign out).

**Host setup and podman-first.** `setup.sh` (Linux, WSL, macOS) and `setup.ps1` (Windows, bootstraps WSL2 Ubuntu
then runs `setup.sh`) check what the host lacks, show the install commands and run them only on a yes. `run.sh`,
`teardown.sh` and `capacity-calc.sh` now prefer podman (rootless, safer) over docker when both are installed;
docker remains the fallback. Checked locally on podman (`setup.sh --check`, syntax); macOS and the docker path untested.

## Unreleased: `feat/front-door` (not yet merged to `main`)

**Front door.** The browser Basic Auth popup is replaced by a styled `/login` page (logo, dark/light, workshop name and
description, show-password, error shake). Sign-in sets a signed 12-hour `dojo_login` cookie checked by Caddy through
the allocator's `/session-check`; same class and facilitator accounts, same `X-Auth-User` trust model, `/admin` still
facilitator-only, wrong guesses limited to 30 a minute per address. The `caddy-ratelimit` plugin is gone. New
`WORKSHOP_DESCRIPTION` in each `workshop.env`. Tested locally (git-fundamentals): login, redirect with `#slide`
fragment, student and facilitator flows, `/admin` 403 for students, IDE/terminal/Forgejo/slides, rate limit, browser
screenshots dark/light/mobile. Not tested: `--env home` behind the proxy, other workshops' extension routes.

## Unreleased: `feat/remediation` (not yet merged to `main`)

**Threat-model remediation** (report: `threat-model-20260926-154208/`; plan: `docs/archive/REMEDIATION-PLAN.md`).
15 of 19 findings fixed, 2 partial, 2 accepted; no Tier 1 or Critical/Important finding open. Rating Elevated to
Moderate by a validation pass on 2026-09-29 (not a re-scored model). All built and live-tested locally.

- **Home run and start-up (2026-09-29).** `./run.sh list` prints the learning path (`WORKSHOP_ORDER=` in each
  `workshop.env`: 0 dojo-introduction, 1 git-fundamentals, 2 dns-as-code, 3 cert-autorenewal, 4 tofu-basics,
  5 vault-fundamentals). `ALLOW_DEFAULT_PASSWORDS=1` in an env file does what `--allow-default-passwords` does.
  Behind the home-lab proxy, `GATEWAY_TRUSTED_PROXIES` must include the gateway's own ingress subnet
  (`172.30.9.0/24`), because podman NATs the source: checked with two devices, each logged under its own
  address. The start table now waits until every container is ready (`STARTUP_WAIT`, default 300 s); start and stop
  tables checked under a pty.
- **Edge (P1, 2026-09-28).** Default passwords refused off loopback and wrong logins rate-limited (FIND-01);
  `/slides` behind the class login (FIND-02); HTTP warning and HSTS (FIND-08); one JSON audit line per identity and
  control-plane decision (FIND-13); external images pinned by digest (FIND-18).
- **Student identity and isolation (P2, 2026-09-28).** Per-student Forgejo passwords and git tokens, locked Linux
  passwords (FIND-03, the Critical one); IDE and terminal ports only through the gateway (FIND-04); each student's
  IDE and terminal in a PID namespace of their own (FIND-10). `provision-account.sh` extracted (student reset R1.1).
- **CI and shared-service trust (P3, 2026-09-28/29).** New `dns-gate` module: CI writes DNS only with a Forgejo ID
  token from the class repo's `main` (FIND-05); per-account DNS keys (FIND-11, partial); locked-down step-ca
  (FIND-09); threaded allocator with locks, assignment rate limit and Release unused (FIND-07).
- **Container and UI hardening (P4, 2026-09-29).** Capabilities dropped and `no-new-privileges` on runner-pool and
  app-host (FIND-06); strict CSP on allocator pages (FIND-14); per-student process limit, OpenBao per-namespace rate
  quota, app-db connection limits, dns-gate and CloudAPI rate limits (FIND-12). All limits are env knobs, 0 = off.
- **Defence in depth (P5, 2026-09-29).** Dojo Cloud docker socket `0660 root:cloud` (FIND-15, accepted risk);
  per-upstream gateway tokens and owner-only `engine/.env`, runner controller on a scoped Forgejo token (FIND-16); no
  live OpenBao token on the setup volume (FIND-17, partial); plaintext to OpenBao/Postgres documented (FIND-19).
- **Validation (P6, 2026-09-29).** Method: a commit per finding, an `rg` check of each fix and the P3/P4 live
  passes. Write-up: `threat-model-20260926-154208/4-verification.md`.

**Other changes on the branch**

- `./run.sh` shows one in-place status table while the stack starts, and `stop` shows one while it comes down
  (terminal only; plain lines when piped or with `NO_COLOR`). Drawing tested against live containers only.
- Fixed a hang on `./run.sh vault-fundamentals`: the runner controller waited for the one-shot `runner-token-init`
  to be running; it now uses `service_completed_successfully` (8387736). Next fresh start came up 16 of 16 healthy.
- The landing page shows the student's own Forgejo password again (efda7c4).
- `dojo-introduction` workshop: the whole platform running at once, with a run-of-show, demo bots and live DNS
  pushes (39900b8, 6bf0208).
- `cert-autorenewal`: lab 4's every-minute cron no longer collides with lab 5 on certbot's lock.
- vault-fundamentals: one test script per lab (3f9a0f0); lab 10's delivery flow drawn as Mermaid (7c44a3b); labs
  keep secrets off the command line (9074e7f).
- `setup` reuses values from an old `.env` and offers 8080/8443 (9f36484, 7bac4a8).

## PR #3: `vault-fundamentals` (merged 2026-09-28)

The OpenBao workshop: labs 0-13 over 2-3 hours, a talk slide comparing OpenBao with Azure Key Vault, and the
facilitator's Vault, Audit, Runners and Apps tabs. Design and decisions: `docs/archive/VAULT-FUNDAMENTALS-PLAN.md`.

- `openbao` module (OpenBao 2.7.0): initialised and unsealed at start, root revoked, re-unseals after a restart,
  single sign-on through Forgejo, per-student namespaces with one shared templated policy, `openbao-audit`.
- `runner-pool` module: single-use autoscaled Forgejo runners, a controller, and the `/admin` Runners panel.
- Workshop services `app-host` (per-student deploy slots) and `app-db`; labs 9-11 deploy to them.
- Labs: secrets in code and git (4-6), pipelines with OIDC (7-8), deployments (9-11), the `pass` lab (2) and the
  deliverer lab (10). Slides, `labs.md` and the lab index within 16:9.
- Tests under `workshops/vault-fundamentals/tests/` and `modules/*/tests/`; the long live pass (T5.6) ran locally
  with `--test 10` and `e2e.sh --load 15`, all pass (7684f07). Sizing: about 2 GiB and under one core for 10 bots.
- `engine/`: `run.sh --env` fix for workshops with modules (a24d0e7); `/forgejo-login?next=` (ca89792).
- HCL highlighting in VS Code.

## PR #2: workshop extensions and modules (merged 2026-09-24)

Design and decisions M1-M11: `docs/archive/MODULES-PLAN.md`.

- **Extensions.** A workshop or module adds cards, `/admin` tabs, routes and status checks through
  `extensions.json`; gates are fixed engine templates (`shared`, `identity`, `facilitator`) and the renderer
  rejects anything unsafe. `render_extensions.py` with tests. A card without an `/admin` tab prints a warning.
- **Modules.** Reusable pieces under `modules/<name>/` listed in `workshop.env` as `MODULES="a b"`: compose
  fragment, terminal Dockerfile, manifest. First modules: `forgejo-runner`, `dojo-cloud`, `dns-ui`.
- **Terminal image chain** `:base` to each module to the workshop, with `/etc/dojo/start.d/NN-name.sh` start-up hooks.
- Workshop-specific behaviour now lives in workshop and module folders, not in `engine/` (the base engine stays workshop-agnostic).

## PR #1: `tofu-basics` (merged 2026-09-23)

OpenTofu on "Dojo Cloud", an Azure-inspired control plane (no Microsoft names or marks). Design and decisions:
`docs/archive/TOFU-BASICS-PLAN.md`.

- Track A (offline sandbox, labs 0-3) and Track B (labs 4-10 against Dojo Cloud with the real `azurerm` provider).
- Dojo Cloud control plane (`modules/dojo-cloud`): ARM facade, policy catalogue, quota, activity log, Docker-in-Docker
  host; Dojo Portal SPA; facilitator class progress board.
- Lock narrowing so no Docker call is made under the state lock (T9.7); fuzz tests and a security suite (42 checks).
- Slides, facilitator guide and capacity notes; e2e 281 checks, 0 failed (2026-09-21); load test at 5/10/15
  students all pass (apply p95 76 s at 15). 15 students is this machine's ceiling and stands as the number.
- Base-engine follow-ups found on the way: shared `web-terminal-healthcheck` (230a9ba), demo bots follow
  `$FORGEJO_REPO` (231cd5d), step-ca healthcheck (a5953ec), code-server memory cut (f977209), Forgejo deletes a PR's
  branch on merge, `run.sh` mode `100755`, and a set of low findings from a sub-agent review.

## Initial mirror (2026-09-17)

The platform and the first three workshops: the engine (Caddy `gateway`, `allocator`, `web-terminal`, Forgejo, Marp
slides, `run.sh`), `git-fundamentals`, `dns-as-code` and `cert-autorenewal`.
