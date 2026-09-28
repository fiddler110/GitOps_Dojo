# PLAN: threat-model remediation (report `threat-model-20260926-154208`)

> **Purpose of this file:** the single source of truth for fixing the findings of the 2026-09-26 threat model. It is
> written so a brand-new session (human or Claude) can pick up exactly where the last one stopped. Keep it current:
> tick boxes in §5 and append to the Session Log (§8) as you go. Same format as `workshops/vault-fundamentals/PLAN.md`.

| | |
|---|---|
| Created | 2026-09-26 (draft plan validated against the report and the code, decisions D1-D11 taken with the user) |
| Owner | scott |
| Report | `threat-model-20260926-154208/` (0-assessment, 0.1-architecture, 1-threatmodel + DFDs, 2-stride-analysis, 3-findings, threat-inventory.json), analysed at `6ca99bd` on `feat/vault-fundamentals` |
| Scope | 19 findings (FIND-01..19) covering 101 threats: 75 Open, 26 Mitigated. Every Open threat maps to a finding (report §Threat Coverage Verification) |
| Goal | Overall rating **Elevated → Moderate**: close the student-to-student crossings (FIND-03, 04, 05) and the edge exposure (FIND-01, 02), then defence in depth |
| Overall status | **P0, P1 done; P2 T2.1-T2.3 done (2026-09-28). Open in P2: T2.4 (docs). Then P3 after the user's go.** |
| Working branch | `feat/remediation` (from `main` after PR #3, 2026-09-28; D12) |
| Last updated | 2026-09-28 (T0.5: P0 closed; open items also listed in `/ROADMAP.md`) |

---

## 0. HOW TO RESUME (read this first)

1. Read this whole file once.
2. `git status` and `git log --oneline -20`. Every finished task records its commit SHA next to its checkbox in §5.
   If a box is ticked but the SHA is not in `git log`, treat the task as **not done**.
3. Check §1 (decisions) and §6 (open questions). Do not start work that depends on an open question. Read **§7
   (Worth knowing)** for surprises found along the way.
4. **Ask the user before moving from one phase to the next** (P0 → P1 → P2 …). **Ask before editing any `engine/`
   file** that D1 does not already approve (the task says `[ENGINE, approved]` or `[ENGINE, ask]`).
5. Find the first `[ ]` or `[~]` task in §5. Before starting it, run the **Verify** line of the previous finished
   task to make sure the foundation still holds.
6. Work the task. When finished: tick the box, add the commit SHA and where it was verified (e.g. "locally"),
   append a dated entry to §8. If you learned something that changes the plan, edit the relevant section.
7. If you are blocked, mark the task `[!]`, say why in §8, and move to the next unblocked task.
8. When a finding is fixed, note it for the P6 incremental report (the report's Finding Overrides table is filled
   in there, not by hand in the old report).

### Where we stopped (2026-09-26): start here next

- The draft plan was checked against the report and the code (results in §8, first entry). The user took D1-D11.
- 2026-09-28: the plan and the report's diagram updates moved onto `feat/vault-fundamentals`; the
  `fix/threat-model-remediation` branch is gone. Work happens here (D12). The user's own uncommitted edits to the
  report files are **theirs**: never stage them. `/ROADMAP.md` lists this plan's phases next to the other open work;
  the task detail stays here.
- 2026-09-28: vault-fundamentals merged to `main` (PR #3); the old feature branches are deleted and this work
  continues on `feat/remediation`. **P0 is done** (T0.1-T0.5, results under each task and in §8).
- **Next: P1, T1.1** (the user gave the go on 2026-09-28). Check `podman ps` first: the user also tests other
  workshops on this machine.

**Task markers:** `[ ]` todo · `[~]` in progress · `[x]` done (+ SHA) · `[!]` blocked · `[-]` dropped (say why).

**Scope tags:** **[ENGINE, approved]** (D1 approved it) · **[ENGINE, ask]** (ask the user first) · **[MODULE]** ·
**[WORKSHOP]**.

**Working style (from `CLAUDE.md`):** podman + podman-compose only, build and start through `./run.sh`; `./run.sh
stop` wipes every volume, so ask before it while the user may be testing; verify on the real stack and a real
browser (Playwright container, see `CLAUDE.md`); keep the main context small and hand builds, live tests and wide
searches to sub-agents; stage only your own files; `python3 -B`.

**Prompt to paste into a fresh session:**

```text
Read threat-model-20260926-154208/REMEDIATION-PLAN.md fully. Follow its "HOW TO RESUME"
section: check git log against the ticked tasks, verify the last completed task still
works, then continue with the first unchecked task. Update the plan (checkboxes, commit
SHAs, Session Log) as you go. Ask me before moving to a new phase, before any engine/
edit not approved in D1, and about anything in section 6.
```

---

## 1. Decisions (user, 2026-09-26)

| # | Decision |
|---|----------|
| D1 | **Approved [ENGINE] edits:** T1.1 (FIND-01), T1.2 (FIND-02), T1.3 (FIND-08), T1.4 (FIND-13), T1.5 (FIND-18, incl. `check-pins.sh`), T2.1 (FIND-03), T2.2 (FIND-04). **Not yet approved, ask first:** the engine part of T2.3 (FIND-10 PID namespace), T3.4 (FIND-07), T4.2 (FIND-14), the terminal part of T4.3 (FIND-12), T5.2 (FIND-16 per-upstream gateway tokens), and anything else under `engine/`. |
| D2 | **Put all of `/slides` behind the shared class gate** (option b). Students and the facilitator already hold that credential (the browser reuses it), so nothing changes for them; a projector signs in once. |
| D3 | **Student git auth: a pre-written per-student Forgejo access token in `~/.git-credentials` (`0600`)**, and git-fundamentals lab1 (plus other labs that mention the Forgejo password) is rewritten to drop the password prompt. Each student still gets a **per-student Forgejo password** (HMAC-derived, D13) because the allocator's one-click Forgejo SSO signs in with it; students need never see it. |
| D4 | **Terminal ingress: a dedicated `terminal_ingress` network** (only `gateway` and `web-terminal`) plus an interface-based `INPUT` rule in the terminal for ports 9000-9899 (accept `lo` and `terminal_ingress`, drop the rest). |
| D5 | **Yes to a time-boxed (½ day) spike** on a PID namespace per student shell/IDE (FIND-10). It edits `workspace-control.py`, so it still needs the engine go (D1). |
| D6 | **dns-api trusts Forgejo Actions OIDC tokens, not source IP** (the report's suggestion; proven in vault T0.6): protected-zone writes need an ID token whose `repository` is the class repo, `ref` is `refs/heads/main` and event is `push`. The PR model (same-repo PR + base-branch workflow, or fork PRs) is decided after V4. |
| D7 | **step-ca: a name policy now** (the `acme` provisioner issues only `*.certs.dojo.test`) **and rely on FIND-11's per-student DNS keys** for dns-01. http-01 stays weak between students (shared network namespace); that is recorded as residual. No per-student provisioners/EAB. |
| D8 | **`/assign` gets a rate limit only.** A join code is later, if needed. |
| D9 | **Accepted residual risks (documented, not fixed):** FIND-19 (plaintext to OpenBao/Postgres), FIND-17's single unseal share, FIND-15's privileged DinD if the rootless spike shows no gain. |
| D10 | **Brute-force limit in the repo: build the gateway with `xcaddy` + `github.com/mholt/caddy-ratelimit`**, pinned by version and digest (not only in the home-lab Caddy). |
| D11 | **Revoke the OpenBao provisioner token after setup, re-mint it every start** (the report's suggestion): each start generates a temporary root from the unseal key, mints the provisioner, runs the hooks, then revokes both. Accepted: it doesn't help against someone who has the setup volume (the unseal key is there, D9). |
| D12 | **Work on `feat/remediation`** (2026-09-28: branched from `main` after vault-fundamentals merged in PR #3; before that the work lived on `feat/vault-fundamentals`). Keep each remediation fix in its own commit (`security:` or the finding ID in the subject) so it can be cherry-picked or reviewed apart from workshop work. |
| D13 | *(From the draft, confirmed by D3.)* **Per-student secrets are derived, not stored:** `STUDENT_PASSWORD_SEED` (random, written by `env-setup.sh`), `pw(user) = base32(HMAC-SHA256(seed, "forgejo:" + user))[:16]`. The same helper in shell and Python with a known-answer test so they can't drift. Reused for DNS keys (FIND-11) with a different label. |
| D15 | *(2026-09-28, with the student-reset plan's R9.)* **D11 stays; T5.3 also mints a narrow reset token.** In the same temporary-root window, mint a periodic token with the narrowed provisioner policy limited to `sys/namespaces/student*` and the per-student hook paths, handed to a resident `openbao-reset` service (memory only, never the setup volume). One narrowed policy serves both the start-up hooks and the reset. No long-lived provisioner token and no unseal key outside `openbao-setup`. |
| D16 | *(2026-09-28, with the student-reset plan's R10.)* **T2.1 builds on `provision-account.sh`.** The reset plan's R1.1 (a behaviour-free extraction of the per-account work out of `entrypoint.sh`, **engine, ask**) goes before T2.1, and T2.1's a/b/c/e changes land in that script, so a reset re-runs the hardened provisioning. T2.1c's token step must stay idempotent (a reset calls it again). |
| D14 | **This plan lives next to the report** (`threat-model-20260926-154208/REMEDIATION-PLAN.md`). |

## 2. Validation of the draft (2026-09-26)

The draft (then `REMEDIATION-PLAN.md` at the repo root) was checked against the report and the tree at `5b07401`:

- **Matches the report:** 19 findings; 101 threats (75 Open, 26 Mitigated); every finding's tier, SDL severity and
  CVSS (01 9.5, 02 6.9, 03 9.3, 04 8.8, 05 8.4, 06 7.3, 07 7.1, 08 6.0, 09 6.0, 10 5.7, 11-13 5.3, 14 2.0, 15 8.7,
  16 8.5, 17 8.4, 18 7.5, 19 2.0); the five "Needs Verification" items (0-assessment); the Elevated → Moderate path.
- **Code evidence confirmed:** `engine/web-terminal/entrypoint.sh:206` (one `chpasswd` password for all students);
  `engine/allocator/server.py` ~694 (password on the landing page) and ~1189 (Forgejo SSO); `workspace-control.py:226`
  (`--auth none`; the draft said 227); `DOJO_ISOLATION` on `OUTPUT` only; `/slides` open by design (Caddyfile
  header), `/slides/lab/*` in the same handle; `dns-preview.yml` `on: pull_request` + `runs-on: host`; `gate.py`
  trusts source IP and a shared key; no-op `log_message` in allocator (517), workspace-control (350), dns-api gate
  (124), and quiet ones in CloudAPI, app-host, runner controller, DNS UI, openbao-audit; single-threaded
  `HTTPServer` in the allocator; mutable tags as listed (OpenBao, Postgres, PowerDNS-Admin already pinned); step-ca
  default password `workshop-not-a-secret` and an `admin` JWK provisioner; privileged DinD with a `0666` socket;
  `env-setup.sh` doesn't `chmod 600 .env`; allocator inline script, `innerHTML`, no CSP; runner-pool and app-host as
  root with default capabilities.
- **Corrected here:** test names after the S37/S39 renumbering (`labs_9_11.sh` → `labs_11_13.sh`, `labs_7_8.sh` →
  `labs_8_9.sh`); the base branch (D12); three places where the draft differed from the report are now decisions
  (D6 OIDC instead of a static CI token, D11 revoke instead of keep, and FIND-09's password generated by the
  workshop rather than `env-setup.sh`, which keeps the engine agnostic).

## 3. Rules that shape the fixes

| Rule | Consequence |
|------|-------------|
| Engine stays workshop-agnostic; no per-workshop flags | Engine fixes are generic ("the terminal accepts IDE ports only from the gateway"). Workshop-specific fixes go in overlays, module `compose.yml`, `start.d` hooks. |
| Facilitator reaches everything | Every fix is checked from `/admin`: Roster, VS Code, Terminal, Forgejo, Slides, Runners, Audit, Apps, watch tiles. |
| `./run.sh stop` loads only `engine/.env` | New secrets used by fragments never use `${VAR:?}` unless `engine/.env` defines them. |
| Student-controlled strings | `textContent` only, strict CSP. |
| No Docker call under a shared lock; one list per request | Limits the allocator fixes (T3.4). |
| Docs in the same commit | `engine/README.md`, `workshops/README.md`, module READMEs, lab text + `.md.txt` copies on a running stack, `.env.example`. |

## 4. Roadmap

| Phase | Theme | Findings | Rating impact | Effort |
|-------|-------|----------|---------------|--------|
| **P0** | Live verification of the "Needs Verification" items | 03, 04, 05, app-db | Confirms or downgrades 3 of the top 5 | ~½ day |
| **P1** | Edge and quick wins | 01, 02, 08, 13, 18 | Removes all Tier 1 exposure | Low |
| **P2** | Student identity and isolation | 03, 04, 10 | **Critical → Moderate**; the largest drop | Medium |
| **P3** | CI and shared-service trust | 05, 11, 09, 07 | Closes the last Important T2 | Medium |
| **P4** | Container and UI hardening | 06, 14, 12 | Defence in depth for T2 | Medium |
| **P5** | Tier 3 defence in depth | 15, 16, 17, 19 | Blast radius | Medium-High |
| **P6** | Incremental `/threat-model-analyst` against this report | all | Records Fixed/Partial | ~1 h |

Order: P0 → P1 → P2 → P3, then P4/P5. P2 and P3 touch different files and may overlap. Vault-fundamentals pieces
(T2.2 AppHost egress, T4.1, T2.3 lab text, T5.3) can be exercised in the same live pass as vault T5.6.

**Dependencies:** T2.1's seed (D13) is reused by T3.2 → do T2.1 first. T2.2 (AppHost egress, needs `NET_ADMIN`) and
T4.1 (drop capabilities) interact → do them together. T3.1 step 3 (dns-as-code on `runner-pool`) needs the vault
branch merged to `main` only if it's done there; on this branch it's available. T1.1's off-localhost check relies on
a24d0e7 (present on this branch).

## 5. Phases and task list (ask the user before moving between phases)

### P0 — Live verification (before changing anything)

The analysis was static. These checks decide how far the top findings reach. Run on a disposable local stack; ask
before any `stop`. Results go into this section and into §8; the P6 report records them as overrides.

- [x] **T0.1** (734ed33, locally) (FIND-03, V1+V2) On `./run.sh git-fundamentals`: from student01's terminal, `su - student02` with the
      landing-page password; `ls -ld /home/student*`.
      *Verify:* result recorded. If `su` fails, FIND-03's Linux path is already closed (T2.1a stays as defence in
      depth); if homes are `0700`, drop T2.1c.
      *Result (2026-09-28, locally, vault-fundamentals; the account setup is engine-level):* `su - student02` from
      student01's terminal with the class password **succeeds** (`uid=1002(student02)`); homes are `drwxr-xr-x` (0755).
      FIND-03 is open on both counts: T2.1a and T2.1c stay.
- [x] **T0.2** (734ed33, locally) (FIND-04, V3) From a deployed app on `vault-fundamentals` (AppHost slot) and from a `dns-as-code`
      host-runner job: `curl -m 3 http://web-terminal:9001/`.
      *Verify:* result recorded. If it times out, FIND-04 downgrades; T2.2 stays as defence in depth.
      *Result (2026-09-28, locally, vault-fundamentals, AppHost part):* as a slot user in `app-host` (same `su` +
      `unshare` wrapper as an app), `web-terminal:9001` is **connection refused**: this terminal image listens only on
      7682. `web-terminal:7682/` is reachable over TCP but answers **403** without the gateway token. *Result (2026-09-28, locally, dns-as-code, host-runner job):* `web-terminal` **does not resolve** (curl rc=6 on
      9001, 7682, 7681); `dns-api:8080` is refused (rc=7). The runner can't reach the terminal.
- [x] **T0.3** (734ed33, locally) (FIND-05, V4) On `dns-as-code`: push a branch that edits `dns-preview.yml`, open a same-repo PR. Does
      it run the PR's version? Are repo secrets visible? Does Forgejo 16 support `pull_request_target`? Does the
      Actions ID-token URL come out broken under `/git/` as in vault §14 (S24)?
      *Verify:* answers recorded; they settle Q-A (§6) for T3.1.
      *Result (2026-09-28, locally, dns-as-code, Forgejo 16.0.4):* (1) **Yes**, a same-repo PR from student01 that edits
      `dns-preview.yml` runs the PR's version (the run printed the probe line), and it reports the required "DNS Preview"
      check itself. (2) No repo or org secrets exist; the job gets `GITHUB_TOKEN`/`FORGEJO_TOKEN`/`GITEA_TOKEN` (40 chars)
      and runs as the runner's uid 1000. (3) `pull_request_target`: a workflow on `main` with it queued a run (listed
      as event `pull_request`) that stayed `waiting` for 2 min: inconclusive, not settled. (4) **Yes, broken**: the
      ID-token URL is `http://localhost:8080/git//gitapi/actions/_apis/pipelines/workflows/2/idtoken?...` (double slash,
      localhost), and the request fails (curl rc=7).
      *(3) settled in T0.5 without a live run:* Forgejo documents `pull_request_target` (base-branch workflow, repo
      secrets visible), which matches what the user found online. Not confirmed locally, and T3.1 no longer needs it
      (see Q-A).
- [x] **T0.4** (734ed33, locally) (app-db, V5) On `vault-fundamentals`: as student01's dynamic DB role, `\c <student02's db>`.
      *Verify:* result recorded. If it connects, add **T3.5** (`REVOKE CONNECT ... FROM PUBLIC` in
      `compose/app-db/init.sh`, [WORKSHOP]).
      *Result (2026-09-28, locally, vault-fundamentals):* **refused**: `\c app_student02` and `-d app_student02` both give
      `FATAL: permission denied for database "app_student02" / User does not have CONNECT privilege`. The dynamic role
      can connect to `postgres` (and `template1`), the default PUBLIC grant; no student data there. T3.5 not needed.
- [x] **T0.5** Write-up: results above, plan edits, a §8 entry. **Ask the user before starting P1.** (2026-09-28;
      the user gave the go for P1.)

### P1 — Edge and quick wins

- [x] **T1.1** (FIND-01, T1, Important) **[ENGINE, approved]** Default credentials and brute force.
      Files: `engine/scripts/env-setup.sh`, `engine/run.sh`, `engine/gateway/Dockerfile`, `engine/gateway/Caddyfile`.
      a. `run.sh` refuses to start when `TTYD_PASSWORD`, `FACILITATOR_PASSWORD`, `FORGEJO_ADMIN_PASSWORD` (and any
         remaining `STUDENT_PASSWORD`) equal the `--default` values and the effective `PUBLIC_BASE_URL` host isn't
         `localhost`/`127.0.0.1`; the error names `./run.sh setup --force`. Override: `--allow-default-passwords`.
         Runs after `.env.<name>` is loaded.
      b. `--default` keeps `admin/admin` for the facilitator but generates `FORGEJO_ADMIN_PASSWORD` and
         `STUDENT_PASSWORD_SEED` (D13).
      c. (D10) Gateway built with `xcaddy` + `caddy-ratelimit`, both pinned (version + digest, builder image by
         digest). Rate-limit zone in front of both `basic_auth` blocks. **Design point:** a LAN class sits behind one
         NAT address and every student polls every ~3 s, so a key of `{remote_host}` must allow a whole class
         (e.g. 35 × polling) while stopping a guessing loop; measure with `--test 20` before picking numbers.
      d. `./run.sh setup --rotate-class` regenerates only `TTYD_PASSWORD` (optional, cheap).
      *Status (2026-09-28):* a and d done (bf3b98c, setup follow-ups 9f36484, 7bac4a8). b: `--default` generates
      `FORGEJO_ADMIN_PASSWORD`; `STUDENT_PASSWORD_SEED` moves to T2.1, its first user. c: the limit counts only
      requests whose `Authorization` is not exactly one of the two valid headers (`entrypoint.sh` computes them from
      the plaintext it already hashes), 30/min per `{remote_host}`, so a NAT'd class or the home-lab proxy is never
      limited for being signed in, and no class-size tuning is needed. Keyed on `{client_ip}`:
      `GATEWAY_TRUSTED_PROXIES` (unset by default) names the proxy in front, e.g. the home-lab Caddy, so one guesser
      there can't block everyone's login prompt. Caddy 2.11.4 + caddy-ratelimit
      `v0.1.1-0.20260612195517-5625512f24f6`, both images by index digest (d934055).
      *Verified locally* (git-fundamentals `--test 20`): 50 wrong → 30×401 then 429; 200 correct class and 100
      `/admin` requests never limited; `/slides` never limited; window resets after 60 s; a different
      `X-Forwarded-For` per request doesn't split the count; zero 429s for the 20 bots. **Open:** set
      `GATEWAY_TRUSTED_PROXIES` in `engine/.env.home` to the address the gateway sees for the home-lab Caddy (read it
      from the gateway log on the first `--env home` run).
      *Verify:* `--default` + `--env home` refuses to start; `--default` on localhost starts; 50 bad attempts in a
      loop get 429; `--test 20` bots and a browser student are never limited; `/admin` still loads.
- [x] **T1.2** (FIND-02, T1, Low) **[ENGINE, approved]** (D2) All of `/slides` behind the shared class gate: move
      `@slides` inside the shared `handle` (after `basic_auth`), keep the `/admin` Slides tab working (the
      facilitator credential passes the shared gate). Update the Caddyfile header comment, `engine/README.md`, and
      `CLAUDE.md`'s Playwright note (slide checks now need `http_credentials`).
      *Verify:* `curl -i localhost:8080/slides/` and `/slides/lab/<file>.md.txt` without credentials → 401; with the
      class credential → 200; in Playwright the decks, lab reader and labs index load for a student and from the
      `/admin` Slides tab with no second prompt; existing slide tests (`p4_browser.py`, `p5_browser.py`) pass after
      adding credentials.
      *Done 2026-09-28 (cad3132):* also the allocator's Slides status check signs in with the class login (else 401,
      and its polling would count towards T1.1's rate limit). Verified locally on vault-fundamentals: 401 without /
      200 with credentials, status green, `p4_browser.py`/`p5_browser.py` pass (they already sent credentials),
      `/admin` Slides tab loads with no second prompt.
- [x] **T1.3** (FIND-08, T2, Moderate) **[ENGINE, approved]** Cleartext over HTTP.
      a. `run.sh` warns when `PUBLIC_BASE_URL` is `http://` and the host isn't localhost.
      b. `Strict-Transport-Security` when `PUBLIC_BASE_URL` is `https://` (env-driven matcher in the Caddyfile, or
         documented for the fronting proxy when `GATEWAY_LISTEN` is plain HTTP).
      c. `engine/README.md`: "LAN class over HTTPS" recipe (`tls internal` + distributing the root, or a real name).
      *Verify:* under `--env home`, `Set-Cookie` has `Secure` and HSTS is present; an `http://<lan-ip>` URL prints
      the warning.
      *Done 2026-09-28 (94ca136):* all three, verified locally (proxy-shaped run: HSTS, `Secure` cookie, status
      green; dry-run warning). The IP + Caddy-CA route needed `default_sni` (no SNI for an IP address), confirmed
      on a standalone gateway. HSTS `max-age` is one day.
- [x] **T1.4** (FIND-13, T2, Low) **[ENGINE, approved]** + [MODULE] + [WORKSHOP] Log identity and control-plane
      decisions.
      a. Allocator, `workspace-control.py`, dns-api `gate.py`: keep the per-request no-op, add one structured line per
         decision (`assign`, `release`, `forgejo-login`, `watch`, workspace start/stop, zone write): slot, account,
         action, target, result; never a secret. Also one line per `/auth-check` result (tool, account, 200/202/303,
         milliseconds): the facilitator's VS Code flake under load (vault PLAN, 2026-09-28) is suspected to be a 202
         (the starting page) served to a VS Code asset request instead of a page load, and today nothing logs it.
      b. Caddy access log to stdout with `X-Auth-User`; confirm this Caddy redacts `Authorization`/`Cookie` by
         default; never `log_credentials`.
      c. CloudAPI, runner controller, app-host: check their audit trails, add the same line format where missing.
      *Verify:* `podman logs allocator` shows one line per assign/release/SSO; `grep -i 'authorization: basic'` on
      the gateway log finds nothing.
      *Done 2026-09-28 (244ff59):* allocator (assign, release, forgejo-login, auth-check, route-check, watch),
      workspace-control, cloud-api (`cloud-op`), runner controller (`runners`), dns-api gate (`zone-write`);
      app-host already logged deploys. `/auth-check` logs every non-200 with the path and ms, a 200 only after a
      change. Gateway access log on stdout, `Authorization` shows `REDACTED`. Verified locally (git-fundamentals
      with 3 bots, a dns-as-code write, a vault Runners scale). **Open:** auth-check volume under a real browser
      load (bots don't use `/ide`); look at it on the first 20+ student run, with the VS Code flake.
- [x] **T1.5** (FIND-18, T3, Low) **[ENGINE, approved]** + [MODULE] + [WORKSHOP] Pin images by digest:
      `engine/gateway/Dockerfile` (incl. the new xcaddy builder), `engine/allocator/Dockerfile`, other
      `python:3.12-alpine` bases, `modules/dojo-cloud/cloud-host/Dockerfile` (`docker:dind`), `forgejo/runner:13`,
      `workshops/cert-autorenewal/compose/step-ca/Dockerfile`, dns-as-code's `pdns-auth-49:latest`. Human tag as a
      comment (the OpenBao/Postgres/PowerDNS-Admin pattern). New `engine/scripts/check-pins.sh`, called by
      `run.sh --dry-run`, fails on an external `FROM`/`image:` without a digest.
      *Verify:* `check-pins.sh` passes; each workshop reaches healthy with `./run.sh <workshop>`.
      *Done 2026-09-28 (6b047ca):* floating tags pinned to the version they pointed at (pdns-auth-49 4.9.17,
      step-ca 0.30.2, docker 29.8.1-dind, forgejo/runner 13.2.0); `FORGEJO_VERSION` removed. All five workshops
      healthy with every status green, locally.
- [x] **T1.6** P1 docs, `.env.example`, §8 entry. **Ask the user before starting P2.** (2026-09-28: the user
      chose to close P1 only; P2 and R1.1 wait for their go.)

### P2 — Student identity and isolation

- [x] **T2.1** *(17fcb1a, on R1.1 7172d9b)* (FIND-03, T2, **Critical**) **[ENGINE, approved]** One shared student password. *Needs the reset
      plan's R1.1 first (D16); the account steps below go in `provision-account.sh`.*
      Files: `engine/scripts/env-setup.sh`, `engine/web-terminal/provision-account.sh` (after R1.1), `engine/web-terminal/entrypoint.sh`, `engine/git-server/bootstrap.sh`,
      `engine/allocator/server.py`, `engine/docker-compose.yml`, lab text.
      a. **Lock student Linux passwords:** replace the students' `chpasswd` with `usermod -p '!'`. Root's `su -`
         (code-server, ttyd) still works; `su - student07` from another student fails. Bots keep their own path.
      b. **Per-student Forgejo password** (D13), computed in `bootstrap.sh` (user creation) and `server.py` (SSO);
         shared helpers + known-answer test. `STUDENT_PASSWORD` stays one release as a fallback only when no seed is
         set, else removed from `docker-compose.yml`.
      c. **Per-student Forgejo token** (D3): at start, a `start.d` step (root, after accounts exist) creates a
         scoped token (`write:repository`, `read:user`) per student through the Forgejo API with the derived
         password, and writes `~/.git-credentials` (`0600`, owned by the student) plus
         `credential.helper store` in the student's git config. Idempotent across restarts (reuse or re-create by
         token name). The landing page stops showing a password.
      d. **Facilitator:** Roster gets a per-student "show Forgejo password" action (for the desk), so the
         facilitator still reaches everything.
      e. **Homes `0700`** after `chown` (skip if T0.1 showed it). Check the watch tiles (tmux as that user) and the
         `SO_PEERCRED` brokers still work.
      f. **Labs:** rewrite git-fundamentals `lab1.md` (no password prompt; say where the token lives and why it's
         `0600`), and every other page that mentions the Forgejo password: `dns-as-code/lab3.md`, tofu-basics
         `lab0.md`, `lab3.md`, `lab10.md`, `README.md`, `slides/lab-index.md`, vault-fundamentals `lab8.md`,
         `slides/labs.md`, `engine/README.md`. `cp` to the `.md.txt` copies on a running stack.
      *Verify:* `su - student02` from student01 fails; Forgejo login as student02 with student01's password fails;
      lab1's clone and push work with no prompt; Forgejo SSO works for a student and the facilitator; Roster "show
      password" works; vault `sso_browser.py` passes; git-fundamentals smoke run and `--test` bots pass.
- [x] **T2.2** *(47e477e)* (FIND-04, T2, Important) **[ENGINE, approved]** + [WORKSHOP] Unauthenticated IDE/terminal ports.
      a. **Engine (D4):** network `terminal_ingress` (gateway + web-terminal only). `entrypoint.sh` adds `INPUT`
         rules for 9000-9899: accept on `lo` (workspace-control's `port_open` probe) and on the `terminal_ingress`
         interface (found by its subnet at start), drop the rest. The renderer rejects module fragments that join
         `terminal_ingress`. `workshops/README.md` documents the rule for fragments.
      b. **vault-fundamentals AppHost:** a uid-owner `OUTPUT` allowlist in `app-host` (the `DOJO_ISOLATION`
         pattern): slot uids reach only `openbao:8200`, `app-db:5432` and DNS. `NET_ADMIN` only at start (T4.1).
      *Verify:* T0.2 repeated: curl from an AppHost slot and from a dns-as-code runner job to `web-terminal:9001`
      times out; student IDE and terminal, `/admin` VS Code/Terminal tabs and watch tiles work (Playwright);
      `tests/labs_11_13.sh` and `tests/lab_10.sh` pass.
- [x] **T2.3** *(a: 9074e7f; b: 1caf9d3, spike 38bbfaa)* (FIND-10, T2, Moderate) [WORKSHOP] + **[ENGINE, ask]** Command lines in `/proc`.
      a. **Labs now:** labs that put secrets on the command line use stdin or `@file` (`bao kv put ... key=-`,
         `curl -H @hdr`), taught as a lesson ("why argv leaks"), vault-fundamentals first.
      b. **Spike (D5, ½ day, needs the engine go):** each student's shell and IDE in its own PID namespace
         (`unshare -p -f --mount-proc` in `workspace-control.py`), as runner-pool and AppHost already do; check it
         works under rootless podman (`hidepid` doesn't, vault §10.5e). Record the result; implement only after the
         user's go.
      *Verify:* no inline secrets in lab text (grep review); with the spike, `ps aux` as student02 doesn't show
      student01's long-running `bao` arguments.
- [ ] **T2.4** P2 docs, §8 entry. **Ask the user before starting P3.**

### P3 — CI and shared-service trust

- [ ] **T3.1** (FIND-05, T2, Important) [WORKSHOP] + [MODULE] PR workflows on a shared host runner trusted by IP.
      Files: `workshops/dns-as-code/content/sample-repo/.forgejo/workflows/*.yml`,
      `workshops/dns-as-code/compose/dns-api/gate.py`, `modules/forgejo-runner/`.
      a. **(D6)** `gate.py` accepts protected-zone writes only with a Forgejo Actions ID token: RS256 checked against
         Forgejo's JWKS (the app-host `openssl` pattern, no new Python dependency), `iss`, `aud`, `repository` = the
         class repo, `ref` = `refs/heads/main`, `event_name` = `push`, not expired. Source IP is no longer trusted.
         `dns-apply.yml` fetches the token with `curl` (S20 style); if T0.3 shows the broken `/git/` token URL, fix
         it the S24 way (a shim) or in the job.
      b. **PR model** (Q-A, after T0.3): (A) preview runs from the base-branch definition and stays read-only, with
         branch protection on `main` (one approval), or (B) students open PRs from forks.
      c. **Ephemeral runners:** switch dns-as-code `MODULES` from `forgejo-runner` to `runner-pool` (available on
         this branch). Until then, the host runner's registration file is root-only `0600`.
      *Verify:* a PR that edits `dns-preview.yml` to PATCH `dojo.test` gets 403; a token from another repo or branch
      gets 403; a merge to `main` still applies; the dns-as-code lab passes end to end.
- [ ] **T3.2** (FIND-11, T2, Moderate) [WORKSHOP] Shared DNS API key.
      a. **dns-as-code:** per-student key `HMAC(seed, "dns:" + user)` (D13) written `0600` to the student's home by
         `90-my-zone.sh`; `gate.py` maps key → user and allows only `<user>.dojo.test`; every student zone is
         pre-created at start (no squatting).
      b. **cert-autorenewal:** the same gate in front of PowerDNS; students get only their key, never
         `PDNS_AUTH_API_KEY` (generated, not `workshop-not-a-secret`). Consider `modules/dns-gate/` shared by both.
      *Verify:* student01's key → 403 on `student02.dojo.test`, 2xx on its own zone; cert-autorenewal renewals work.
- [ ] **T3.3** (FIND-09, T2, Moderate) [WORKSHOP] Shared ACME CA.
      a. `STEP_CA_PASSWORD` generated at first start by the workshop (its entrypoint or `workshop.env`, not the
         engine), never given to students.
      b. The `admin` JWK provisioner gets its own random password, out of student reach.
      c. **(D7)** An `x509` name policy on the `acme` provisioner: allow `*.certs.dojo.test` only. dns-01 becomes
         per-student through T3.2. http-01 between students stays open (shared network namespace): residual, noted
         in the workshop README.
      *Verify:* a certificate for a name outside `certs.dojo.test` is refused; with T3.2, dns-01 for
      `student02.certs.dojo.test` as student01 fails; the lab's own renewal flow passes.
- [ ] **T3.4** (FIND-07, T2, Moderate) **[ENGINE, ask]** Slot exhaustion and head-of-line blocking.
      a. Global `/assign` rate limit (N per minute + burst), in memory, no Docker call under a lock. (D8: no join code.)
      b. `/admin` "release all unclaimed / idle" if missing.
      c. Allocator socket timeout 10 s → 3 s; Caddy dial/response timeouts to the allocator. `ThreadingHTTPServer`
         is a separate spike (locking rules).
      *Verify:* 40 cookie-less `/assign` POSTs grant at most the burst; with 5 idle sockets `/auth-check` stays
      under 1 s; `--test 20` bots still get slots.
- [ ] **T3.5** *(only if T0.4 connects)* [WORKSHOP] `REVOKE CONNECT ON DATABASE ... FROM PUBLIC` in app-db init.
      *Verify:* student01's role can't `\c` student02's database; `tests/labs_11_13.sh` passes.
- [ ] **T3.6** P3 docs, §8 entry. **Ask the user before starting P4.**

### P4 — Container and UI hardening

- [ ] **T4.1** (FIND-06, T2, Moderate) [MODULE] + [WORKSHOP] runner-pool and app-host as root with default caps.
      a. `security_opt: [no-new-privileges:true]`, `cap_drop: [ALL]`, add back only what tests need (candidates
         `SETUID`, `SETGID`, `CHOWN`, `DAC_OVERRIDE`, `FOWNER`, `KILL`). Check `unshare -U` and `setpriv` under
         no-new-privileges. (dns-as-code's compose services already do this: copy their form.)
      b. app-host: `NET_ADMIN` for T2.2b only at start; drop it from the long-running process (`setpriv
         --bounding-set -net_admin` or `capsh`).
      c. State the seccomp profile (podman default) explicitly.
      *Verify:* `podman inspect` shows the dropped caps and `NoNewPrivileges`; `modules/runner-pool/tests/pool.sh`,
      `tests/labs_8_9.sh`, `tests/lab_10.sh`, `tests/labs_11_13.sh` pass.
- [ ] **T4.2** (FIND-14, T2, Low) **[ENGINE, ask]** Allocator pages: landing and `/admin` scripts to static files,
      roster fields with `textContent` (delete `escapeHtml` + `innerHTML`),
      `Content-Security-Policy: default-src 'self'; frame-ancestors 'self'; object-src 'none'; base-uri 'none'`.
      *Verify:* headers present; no CSP violations on `/` and `/admin` in Playwright; `/admin` iframes (IDE,
      terminal, Forgejo, slides, module tabs) still frame; roster updates live.
- [ ] **T4.3** (FIND-12, T2, Low) [MODULE] + [WORKSHOP] + **[ENGINE, ask]** Rate limits and shared pools:
      OpenBao `sys/quotas/rate-limit` per student namespace (tenancy hook); app-db `CONNECTION LIMIT 5` per student
      role; token bucket per identity in CloudAPI and dns-api; terminal (engine) per-user `nproc`/`as` via
      `limits.d` or `prlimit` around the `su` in `workspace-control.py`.
      *Verify:* a 1000-request loop from one student is throttled while another's succeed; a fork bomb in one
      account doesn't stall others.
- [ ] **T4.4** P4 docs, §8 entry. **Ask the user before starting P5.**

### P5 — Tier 3 defence in depth

- [ ] **T5.1** (FIND-15, T3, Important) [MODULE] dojo-cloud: socket `0660` with a `cloud` group shared only with
      CloudAPI (digest pin in T1.5). Spike rootless DinD / podman-in-container on WSL2; if no gain, accept (D9) and
      document in the module README.
      *Verify:* `stat` on the socket; tofu-basics labs pass.
- [ ] **T5.2** (FIND-16, T3, Moderate) a. `chmod 600 engine/.env` in `env-setup.sh` **[ENGINE, ask]**. b. Per-upstream
      gateway tokens minted by `render_extensions.py`, set per route with `header_up` **[ENGINE, ask]**. c. The
      runner controller uses a scoped Forgejo token instead of `FORGEJO_ADMIN_PASSWORD` [MODULE]. d. Evaluate
      compose `secrets:` under podman-compose.
      *Verify:* app-host's token is refused by CloudAPI; runner-pool tests pass.
- [ ] **T5.3** (FIND-17, T3, Moderate) [MODULE] openbao (D11): `setup.sh` on every start generates a temporary root
      from the unseal share (`bao operator generate-root`), mints the provisioner, runs the hooks, revokes both;
      the setup container keeps only the unseal key for re-unsealing. Narrow `provisioner.hcl` to the hooks' paths.
      (D15) In the same window, mint the periodic reset token (narrowed policy limited to `student*`) for the
      `openbao-reset` service of the student-reset plan (R9); it never touches `/setup`.
      Update `modules/openbao/tests/cli_login.sh` (it reads `/setup/provisioner-token`) and the module README. The
      single unseal share stays (D9), stated on the slides and README.
      *Verify:* after start, `/setup` holds no live token (`bao token lookup` with any stored token fails); the
      reset token can delete and re-create `student01`'s namespace but is refused on the root namespace's `sys/`;
      a `podman restart workshop_openbao` still re-unseals; a second `./run.sh vault-fundamentals` start re-runs the
      hooks; `tenancy.sh`, `cli_login.sh`, `sso_browser.py` pass.
- [ ] **T5.4** (FIND-19, T3, Low) **Accepted (D9).** Document in the openbao module README and vault workshop
      README; keep `hmac_accessor = false` (the Audit tab needs it).
- [ ] **T5.5** P5 docs, §8 entry.

### P6 — Incremental threat model

- [ ] **T6.1** Run `/threat-model-analyst` in incremental mode with this report as the baseline; record Fixed /
      Partial / Accepted per finding and the P0 results as overrides.
      *Verify:* the new report exists and shows the rating; no Critical or Important Tier 2 finding remains open.

### Tracking summary

| Task | Finding | Sev | Scope | Status |
|------|---------|-----|-------|--------|
| T0.1-T0.5 | Live verification | — | — | Done 2026-09-28 (734ed33 + T0.5 write-up) |
| T1.1 | FIND-01 | Important | ENGINE | Done 2026-09-28 (bf3b98c, d934055) |
| T1.2 | FIND-02 | Low | ENGINE | Done 2026-09-28 (cad3132) |
| T1.3 | FIND-08 | Moderate | ENGINE | Done 2026-09-28 (94ca136) |
| T1.4 | FIND-13 | Low | ENGINE+MODULE+WS | Done 2026-09-28 (244ff59) |
| T1.5 | FIND-18 | Low | all | Done 2026-09-28 (6b047ca) |
| T2.1 | FIND-03 | **Critical** | ENGINE | Done 17fcb1a |
| T2.2 | FIND-04 | Important | ENGINE+WS | Done 47e477e |
| T2.3 | FIND-10 | Moderate | WS (+ENGINE, ask) | Done 9074e7f, 1caf9d3 |
| T3.1 | FIND-05 | Important | WS+MODULE | Not started; Q-A has a recommendation (§6), user to confirm |
| T3.2 | FIND-11 | Moderate | WS | Not started |
| T3.3 | FIND-09 | Moderate | WS | Not started |
| T3.4 | FIND-07 | Moderate | ENGINE, ask | Not started |
| T4.1 | FIND-06 | Moderate | MODULE+WS | Not started |
| T4.2 | FIND-14 | Low | ENGINE, ask | Not started |
| T4.3 | FIND-12 | Low | mixed | Not started |
| T5.1-T5.4 | FIND-15/16/17/19 | Imp/Mod/Mod/Low | mixed | Not started |
| T6.1 | Incremental report | — | — | Not started |

**Expected after P1-P3:** no Tier 1 findings and no Critical or Important Tier 2 findings; overall **Moderate**, the
rest tracked as defence in depth or accepted risk (D9).

## 6. Open questions for the user

- **Q-A (after T0.3).** dns-as-code PR model for T3.1b: (A) base-branch workflow + branch protection, or (B) fork
  PRs (changes the lab flow). **Recommendation (T0.5): (A) without `pull_request_target`.** Keep the preview on
  `pull_request`. T3.1a's claim check (`event_name` = `push`, `ref` = `refs/heads/main`, the class repo) is what
  stops a PR from writing, whichever workflow version runs, so a PR that rewrites `dns-preview.yml` still gets 403.
  Add branch protection on `main` (one approval) so an edited workflow can't reach `main` unreviewed.
  `pull_request_target` would only protect the preview's output, and it brings the usual risk of a secret-bearing
  run that checks out PR code; (B) changes the lab flow for no extra protection. **Confirmed by the user
  2026-09-28: (A).**
- **Q-B (before T2.3b and every `[ENGINE, ask]` task).** Engine go for that task.

## 7. Worth knowing

- Since PR #3, `main` has everything this plan builds on (openbao, runner-pool, app-host, a24d0e7);
  `feat/remediation` branches from it (D12).
- The shared class gate authenticates the *class*, not `studentXX`; identity comes from the allocator cookie after
  it. D2 needs only the class gate.
- With D2, `CLAUDE.md`'s "slides are open at `/slides/...`" stops being true: Playwright checks pass
  `http_credentials` (update `CLAUDE.md` locally; it is git-ignored).
- Rate limits keyed on the client address see a LAN class as one address (T1.1c).
- dns-as-code's compose services already have `cap_drop` and `no-new-privileges`: a working example for T4.1.
- Caddy (2.5+) redacts `Authorization`, `Cookie` and `Set-Cookie` in access logs unless `log_credentials` is on;
  confirm on the pinned version in T1.4.

## 8. SESSION LOG (append-only, newest at the bottom)

### 2026-09-26 — Plan validated, decisions, branch

- Checked the draft against the report and the code (§2). Corrections: test names after the S37/S39 renumbering,
  `workspace-control.py:226`, the base branch; three differences from the report became decisions (D6, D11, and
  FIND-09's password in the workshop).
- The user decided D1-D11 (plus D12-D14 on branch, derivation and location). Changed from the draft's
  recommendations: D2 gate all of `/slides`; D3 token file in `~/.git-credentials` with lab1 rewritten; D6 OIDC for
  dns-api; D10 the Caddy rate-limit plugin in the repo; D11 revoke the provisioner token.
- Rewrote the plan in the vault-fundamentals `PLAN.md` format and moved it next to the report. Branch
  `fix/threat-model-remediation` created from `feat/vault-fundamentals` (`5b07401`). Nothing implemented or tested.

### 2026-09-28 — Folded into `feat/vault-fundamentals`

- The user asked to drop the separate branch. This file and the report's diagram updates (dark-theme colours in
  `0.1-architecture.md`, the `init` line after the diagram type in the `.mmd` files) came over with `git checkout`;
  `fix/threat-model-remediation` was deleted. D12 updated. Open phases are also summarised in `/ROADMAP.md`.

### 2026-09-28 — Two decisions with the student-reset plan

- D15: D11 stays, and T5.3 also mints a narrow reset token for `openbao-reset` (the reset plan's R9, its Q2).
- D16: the reset plan's R1.1 (`provision-account.sh`, engine, ask) goes before T2.1, which then builds on it
  (R10). The order is in `/ROADMAP.md`.

### 2026-09-28 — T0.5: P0 closed

- T0.1-T0.4 results are under each task (734ed33). Summary: FIND-03 open (`su` to another student works, homes
  `0755`): T2.1a and c stay. FIND-04 can be downgraded (app gets connection refused or 403 without the token; the
  host runner can't resolve `web-terminal`): T2.2 stays as defence in depth. FIND-05 confirmed (a same-repo PR
  runs its own `dns-preview.yml`; the ID-token URL is broken under `/git/`, so T3.1a needs the S24-style fix).
  app-db cross-database connect refused: no T3.5.
- `pull_request_target` (T0.3 part 3) settled without another stack: Forgejo documents it; the local run that sat
  `waiting` was not retried. Not needed: Q-A now recommends (A) without it (§6), pending the user's confirmation.
- Work moved to `feat/remediation` (D12). The user gave the go for P1.

### 2026-09-28 — P1 closed

- T1.1-T1.5 done and verified locally (commits under each task). Tested as a batch at the user's request: cheap
  checks per task, then one live pass over all five workshops.
- Changes from the plan: T1.1c counts only requests without a valid `Authorization` header (no class-size tuning;
  `GATEWAY_TRUSTED_PROXIES` for a proxy in front); T1.2 also gave the allocator the class login for its Slides
  check; T1.3 added `default_sni` for the IP + Caddy-CA route; `STUDENT_PASSWORD_SEED` moved to T2.1.
- Open: `GATEWAY_TRUSTED_PROXIES` in `.env.home` (read the proxy's address from the gateway log on the next home
  run); auth-check volume under real browsers.
- Also: `core.fileMode` was false in this clone; now true, and the scripts run directly are 755 (5fae93c, e914b5d).
- Q-A confirmed (A). The user chose to close P1 only: P2 and R1.1 wait for their go.

### 2026-09-28 — P2: R1.1, T2.1, T2.2, T2.3a

- Built in a worktree (`wt/p2`) while another session added `dojo-introduction`, then fast-forwarded. Verified
  locally as one batch: vault-fundamentals (33 shell checks, a new browser check of landing page, IDE, terminal,
  watch view and Roster **Password**, labs 8-13 tests, OpenBao SSO, p4 browser) and git-fundamentals `--test 3`
  (28 checks, lab 1 push with no prompt, bots into round 2 with no failed steps).
- R1.1: `/home` identical before and after, started twice; the script also refills a home from `/etc/skel`
  after a reset.
- Changes from the plan: T2.1b's shell helper builds HMAC from `sha256sum`/`xxd` (the Forgejo image has no
  openssl or python); T2.1c also writes `~/.netrc` (labs call the API with `curl --netrc`) and the token has
  `write:issue` (dnsctl reads PR comments); bootstrap re-sets existing accounts' passwords. T2.2a: the gateway
  dials the alias `web-terminal-ingress` (podman DNS returns every shared network's address, in no fixed order),
  so web-terminal uses map-form `networks:`; the fragment check is in `run.sh`, not the renderer. T2.2b matches
  by port (8200, 5432, 53), not address. T2.3a: CI steps unchanged (single-use runners, own PID namespace).
- Trap: the main tree and a worktree share image tags (`gitopsdojo/allocator:local`...). The first vault run
  served an older allocator (no Password API, SSO with the old shared password); a restart from the worktree
  fixed it, and every check passed. Don't run stacks from two trees at once.
- Open: T2.3b spike (engine go), T2.4. `engine/.env` and `.env.home` need a `STUDENT_PASSWORD_SEED`
  (`run.sh` warns until then).

### 2026-09-28 — T2.3b spike: a PID namespace per student works

Tested in the terminal image with the stack's capabilities (rootless podman, `NET_ADMIN` only):
- Root can't `unshare -p` (no `CAP_SYS_ADMIN`). As the student it works, as in AppHost and the runner pool:
  `unshare -U --map-current-user -p -f --mount-proc`. Inside, student02's `ps` shows none of student01's
  processes (0 matches; 4 today). Files keep the right owner; `node` (code-server) runs inside.
- A PID namespace dies with its first process, so a namespace per tool would kill tmux (and the student's
  session) when the connection that started it closes. Design: one holder per student
  (`unshare ... --kill-child sleep infinity`, started by workspace-control.py on first use, as the student);
  code-server and ttyd's shell enter it with `nsenter -t <holder> -U -p -m --preserve-credentials`. Checked:
  tmux outlives its starter, the facilitator's watch (`tmux attach -r` from outside) still attaches, the
  openbao and dojo-cloud brokers get the student's real uid through `SO_PEERCRED`.
- Limits: setuid tools (`su`, `sudo`, `ping`) don't work inside; no lab uses them. The facilitator and bots stay
  outside. DOJO_ISOLATION still matches (the kernel uid is unchanged).
- Build (after the go): holder lifecycle in workspace-control.py (start, check, restart; `stop_user` kills it),
  the two spawn commands, then a live pass (IDE, terminal, watch, reconnect, vault labs with the broker, bots).

### 2026-09-28 — T2.3b built (user's go)

- 1caf9d3: the holder design from the spike, in workspace-control.py; `is_alive` skips the holder; release
  kills it; no namespace for the facilitator or bots; fallback without one (`pidns-unavailable`).
- Verified locally (vault-fundamentals): student01's shells, tmux server and code-server run in the namespace;
  its `ps` shows 13 processes, all its own, none of student02's; the OpenBao broker signs a shell there in as
  `jwt-student01`; p2 browser check 8/8 (IDE, terminal, watch, Roster), 33 shell checks, labs 8-9 pass. An
  offline test in the terminal image covered stop and restart (new namespace) and bots staying outside.
- Lab 3's lesson now says this platform isolates `ps`, most machines don't. Not re-tested: dojo-cloud's broker
  (same `SO_PEERCRED` uid check as openbao's, which passed), git-fundamentals bots (outside, unchanged).
