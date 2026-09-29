# Roadmap

The single list of open work. Finished work moves to [`RELEASES.md`](RELEASES.md). The old per-feature plans
(design, decisions, task logs) are frozen in [`docs/archive/`](docs/archive/); read them for the why, but don't
update them. When you finish an item: delete it here and add a line to RELEASES.md.

Last updated: 2026-09-29 · Working branch: `feat/remediation` (from `main` after PR #3, 3a59106)

| Section | What it holds |
|---|---|
| [Now](#now) | Merge, plus checks that need a real run |
| [Next](#next) | Student reset; remediation leftovers |
| [Manual checks](#manual-checks-the-user-in-a-browser) | Browser passes only the user can do |
| [Later](#later) | Follow-ups and known limits |
| [Housekeeping](#housekeeping) | Repo hygiene |

## Now

| # | Item | Detail | Status |
|---|---|---|---|
| 1 | **Merge `feat/remediation` to `main`** | Open a PR (ask before pushing). Remediation P0-P6 are built, live-tested locally and committed; see RELEASES "Unreleased". | Ready |
| 2c | **Facilitator VS Code tab "unknown error"** | Seen under load (a retry fixed it; the 404 is code-server's optional `vsda` files, harmless). Not reproduced at 10 bots. Recheck at the first 20+ student run with the `/auth-check` logging from remediation T1.4. Sizing for 20-35 students is extrapolated from 10 bots. | Needs 20+ run |

## Next

### Student reset (facilitator resets one student's whole environment)

Design: `docs/archive/STUDENT-RESET-PLAN.md` (read §4 design, §4.4 hook contract, §6 security). Rule: **ask before
editing any `engine/` file**, and before moving between phases.

**Decisions set so far**

| ID | Decision |
|---|---|
| R2 | One student goes back to how they were at stack start; others never notice |
| R3 | The engine orchestrates and resets engine-owned state (terminal home, Forgejo); modules and workshops reset their own state through hooks they declare |
| R4 | A reset keeps the seat |
| R5 | Idempotent and re-runnable |
| R6 | Shared state is not rolled back (a reset may remove what the student owns inside it) |
| R7 | Facilitator-only, per student, typed confirmation |
| R8 | One worker thread in the allocator |
| R9 | OpenBao reset uses a narrow reset token held only in memory by a new resident `openbao-reset` service (minted in remediation T5.3's root window; not the unseal key, not the provisioner token) |
| R10 | `provision-account.sh` first (done), then hardening inside it (done), then the rest |
| D11 | Stays: no long-lived provisioner token |

**Phases**

| Phase | Scope | Tasks |
|---|---|---|
| **R0 spikes** | Throwaway, no engine edits kept | R0.1 list every student-owned file after doing all labs of one workshop · R0.2 Forgejo purge and recreate by hand via the admin API, record what survives · R0.3 manual reset of one vault-fundamentals student (namespace delete plus tenancy hooks) and rerun labs · R0.4 time each step (target under 30 s) |
| **R1 engine core** | Engine reset machinery | R1.1 done (7172d9b) · R1.2 `account.d`/`reset.d` hook runner and `POST /reset/<user>` in `workspace-control.py` · R1.3 Forgejo teardown and re-provision (per Q6) · R1.4 allocator `POST /admin/reset/<sid>` with worker thread, fence and `reset` in the sessions API · R1.5 Roster UI (Reset item, confirm dialog, progress, Retry) · R1.6 tests in `engine/allocator/tests/` (auth, fence, idempotency, bot reset) and a live check |
| **R2 hook contract** | How hooks are declared and called | `resets` in `render_extensions.py` (with tests) · `RESET_TOKEN` in `env-setup.sh` and compose · the allocator calls service hooks with a per-hook timeout and results |
| **R3 adoption** | Modules and workshops reset their own state | `dojo-cloud` (reset endpoint on cloud-api, reuse `_purge`; live check on tofu-basics) · `openbao` plus vault tenancy/CI/platform via `openbao-reset` (R9) · `runner-pool` and `forgejo-runner` · vault `app-host` and `app-db` · dns-ui, dns-as-code, cert-autorenewal per Q3 (move any per-account `start.d` work to `account.d`) |
| **R4 docs and live pass** | Documentation and verification | `engine/README.md` "Facilitator operations" · `workshops/README.md` hook contract · module READMEs · per workshop: break a student on purpose, reset, redo the first labs as them while a second student carries on |

**Open questions for the user**

| ID | Question |
|---|---|
| Q1 | Also offer "reset and release" (wipe, then free the seat)? |
| Q3 | Shared DNS zone: record who owns which record (naming convention or CI commit author) so reset can remove them, or out of scope? |
| Q4 | code-server keeps UI state in the browser: accept it, or have the reset page clear that origin's storage? |
| Q5 | What exactly to remove from the shared org repo (close the student's open PRs, delete their branches and comments; leave merged history alone)? |
| Q6 | Forgejo re-provision: a single-user function in `bootstrap.sh` (one source of truth, needs the bootstrap image reachable at runtime) or two API calls from the allocator? |
| Q7 | May a student ask for a reset from their own page (facilitator approves), or facilitator only? |

### Remediation leftovers (none Critical or Important)

| Item | Type | Detail |
|---|---|---|
| FIND-11 | Partial | PowerDNS keys are still derived from the shared token |
| FIND-17 | Partial | The single unseal share stays on the setup volume (accepted, D9) |
| FIND-15 | Accepted, no work | dojo-cloud socket `0660 root:cloud`; privileged DinD stays |
| FIND-19 | Accepted, no work | Plaintext to OpenBao and Postgres, documented |
| Not exercised in P4/P5 | Untested | 300 app-db connections · the app-host shim on 443 (base URL was plain `http://localhost:8080`) · vault **second start** without `stop` (hooks re-run) · a real-browser "Release unused" · vault pool, audit and browser areas after the e2e split (CLI passes were fine) |
| `lab_12` flake | Investigate | Flaked once ("revoked: the login is gone"), passed on retry; probably a revoke vs `DROP ROLE` race, unconfirmed. Re-run it a few times |
| Not re-run after P4 | Untested | dns-as-code, dojo-introduction and git-fundamentals (scope cut by the user; they passed before P4). cert-autorenewal `--test 1` passed after the lab 4/5 cron fix |
| `dojo-introduction` and the cert lab | Decision | Its seed has no `~/lab/sample-repo`, so a student following the cert lab misses `vhost-http.conf.template`. Decide whether that workshop is meant to cover the cert lab |
| Caddy log redaction | Verify | Confirm on the pinned Caddy version that `Authorization`, `Cookie` and `Set-Cookie` are redacted in access logs unless `log_credentials` is on (expected for 2.5+) |

## Manual checks (the user, in a browser)

### Modules browser pass (was MODULES-PLAN T3.4)

For each workshop: `./run.sh stop`, `./run.sh <workshop>`, open the base URL as a student and in a private window as
the facilitator.

**Common checks**

| Area | Expect |
|---|---|
| Student landing page | Cards each open (VS Code, Terminal, Forgejo, Slides plus the workshop's own) |
| `/admin` | Roster, VS Code, Terminal, Forgejo and Slides plus the workshop's tab, each loading in its iframe |
| Status strip | Forgejo, Terminals and Slides Ready plus the workshop's own |
| Terminal | `whoami` gives `studentNN`; the workshop's tools run |
| Teardown | `./run.sh stop` finishes cleanly |

**Per workshop**

| Workshop | Check |
|---|---|
| git-fundamentals | Lab 1, clone, branch, push, open a PR |
| dns-as-code | `dnscontrol version`; push a branch and open a PR; Actions shows **DNS Preview** green; merge and **DNS Apply** goes green; `dig` shows the record |
| cert-autorenewal | **Demo Site** card and tab; after lab 2 the student's card shows `studentNN.certs.dojo.test` and the facilitator's tab shows their own site (`admin.certs.dojo.test`) |
| tofu-basics | **Dojo Cloud** card and tab; the portal opens on the student's subscription; the facilitator's tab shows the progress view; after a Track B `apply` the resource shows in both |

### Other manual checks

| Check | What to do |
|---|---|
| **tofu-basics T9.9** (browser pass) | Labs 0-3 on a rebuilt image (including HCL highlighting in code-server) and labs 4-10 with the portal clicked, not called through the API: Add tag, Save tags, Delete dialog, Browse (to the deployed `dojo/hello` site), Quota tile, Refresh now, and the attention tile reading `code: message` (25a7176, offline-tested only). Facilitator: `/admin` Slides and Dojo Cloud tabs render in their iframes; Terminal, VS Code and Forgejo tabs still fine |
| **tofu-basics T9.4** (human dry-run, 3-5 people) | Run them through Track A only or A + B (about 103 min for both by the lab README's estimates). Note every point of confusion, time the walkthrough against the slide deck's talk timings (guesses so far), then fix labs, slides and README. `workshops/tofu-basics/FACILITATOR.md` says the first real class doubles as this dry run |
| **vault-fundamentals** | A person walking labs 7-9 in the UI (the tests make the UI's secret steps with the same API calls), the Runners panel's look beyond screenshots, and "Release unused" in a real browser. The rest of the P4/P5 browser pass was done by the user 2026-09-29 |
| **UI changes, weekend of 2026-09-26** | The `/admin` sidebar at desktop width and under 700 px, and Mermaid diagrams in the lab reader, light and dark |

## Later

| Area | Items |
|---|---|
| **vault-fundamentals follow-ups** | Policy as code (namespace policies in a git repo, changed by PR and applied by CI with drift shown when someone edits in the UI; OpenTofu `vault` provider building on tofu-basics, or `bao policy write` in CI; a lab or its own workshop) · OpenBao PKI for `cert-autorenewal` · mirror a small pinned set of actions (checkout, a vault-login action) into Forgejo at setup so labs can show `uses:` as companies do · lab 11 should show a restart logging in again (lab 10 ends on that promise) |
| **tofu-basics follow-ups** | `dojo` CLI (`login`, `group list`, `container list/show/logs`) · CI `plan` on pull requests via Forgejo Actions (needs runner network design like dns-as-code's `runner_net`) · more Azure-shaped resources (virtual network, storage account) if the ARM facade extends cheaply · remote state backend simulation · stretch labs 11-12 only if wanted |
| **tofu-basics known limits** | Only one container per group and only `dojo/hello:*` images (by design) · LRO (`Azure-AsyncOperation`) not implemented · arm64 untested (checksums pinned per arch, only amd64 built) · 20+ students out of scope (15 is this box's ceiling) · **T9.8 deferred:** re-test isolation on real Docker before any non-podman delivery (the privileged-DinD risk is materially higher there); this machine has no Docker |
| **Not verified since `f977209`** (code-server memory cut) | tofu-basics `tests/e2e.sh` on the new web-terminal image · `./run.sh capacity` printing "Left out N" for a closed tab (dry-run only) |

## Housekeeping

| Item | Detail |
|---|---|
| Large handout binaries | `handouts/*.pptx` are committed binaries of 30-36 MB, and every deck change adds a full copy to git history. Consider Git LFS or publishing them as release assets instead |
| Deck rebuild trigger too broad | `handouts/build-presentations.sh` hashes all of `workshops/assets/` as a deck input, so a lab-reader-only change re-exports every deck (new 15-36 MB blobs with identical slides). Narrow `shared=` to what Marp reads (the themes, not `lab-reader.*` or `vendor/`) |
| Stale plan references | Many code comments and READMEs cite plan sections (`PLAN.md §5.5`, `MODULES-PLAN.md §4.2`, `engine/student-reset.md`). The files now live in `docs/archive/` under new names (`TOFU-BASICS-PLAN.md`, `VAULT-FUNDAMENTALS-PLAN.md`, `MODULES-PLAN.md`, `STUDENT-RESET-PLAN.md`, `REMEDIATION-PLAN.md`). Comments in `engine/` were left alone (engine edits need approval); reword them when next touched |
