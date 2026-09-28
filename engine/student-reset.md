# Student reset: plan

| | |
|---|---|
| Branch | not started (plan written on `feat/vault-fundamentals`, 2026-09-27); sequenced with the threat-model remediation in `/ROADMAP.md` |
| Overall status | **Planned.** Nothing built. Decisions in §1 marked "proposed" need the user's OK. |
| Related | `engine/MODULES-PLAN.md` (manifests, modules, start.d hooks), `engine/README.md` "Facilitator operations" |

## 0. HOW TO RESUME (read this first)

1. Read this whole file once.
2. `git status` and `git log --oneline -20`. Every finished task records its commit SHA next to its checkbox in §7.
   If a box is ticked but the SHA is not in `git log`, treat the task as **not done**.
3. Check §1 (decisions) and §8 (open questions). Don't start work that depends on an open question.
4. **Ask the user before moving from one phase to the next** (R0 → R1 → …), and **before editing any `engine/`
   file** other than this plan.
5. Find the first `[ ]` or `[~]` task in §7. Run the **Verify** line of the previous finished task first.
6. Work the task. When done: tick it, add the commit SHA, append a dated entry to §10.

Resume prompt:

```text
Read engine/student-reset.md fully and follow its "HOW TO RESUME" section. Ask me before a new phase,
before editing engine/ files, and about anything in section 8.
```

---

## 1. Decisions

| # | Decision | Set by |
|---|----------|--------|
| R1 | The plan lives in `engine/student-reset.md`. | user, 2026-09-27 |
| R2 | A reset puts **one** student back to how they were at stack start: fresh home and lab, fresh Forgejo account, fresh per-student state in every module. Other students never notice. | user (goal), 2026-09-27 |
| R3 | The engine owns the **orchestration** (button, confirm, ordering, progress, retries) and the engine-owned state (terminal home, Forgejo). Modules and workshops reset **their own** state through hooks they declare; the engine never learns what OpenBao or Dojo Cloud is. Same rule as `MODULES-PLAN.md` M4. | proposed |
| R4 | A reset keeps the student's **seat**: same `studentNN`, same name on the roster, same browser cookie. They reload and start again. "Reset and release" is a separate, later option (§8 Q1). | proposed |
| R5 | Reset is **idempotent and re-runnable**. Each step can be run again after a partial failure; a second reset of a clean student is a no-op apart from the log line. | proposed |
| R6 | Shared state (the shared org repo's `main`, shared DNS zone, audit logs, Dojo Cloud activity log) is **not rolled back**. A reset may *remove what the student owns* inside shared state (their branches, PRs, forks, records they own), never anything else. | proposed |
| R7 | Reset is facilitator-only, per student, with a typed confirmation. No "reset everyone" button (that is `./run.sh stop` + start). | proposed |
| R9 | **OpenBao reset uses a narrow reset token held by a new resident `openbao-reset` service** (answers Q2). Each start, inside the temporary-root window of remediation T5.3, `openbao-setup` also mints a periodic token whose policy is the narrowed provisioner policy limited to `sys/namespaces/student*` and the per-student hook paths. `openbao-reset` keeps it in memory only (never on the setup volume), renews it, checks `X-Gateway-Token`, and is called by the allocator. Not the unseal key, not the provisioner token (both would undo remediation D11). Residual: it can wipe any student namespace; facilitator-only through the gateway. | user, 2026-09-28 |
| R10 | **Order with the threat-model remediation:** R1.1 (extract `provision-account.sh`, no behaviour change) goes first, then remediation T2.1 hardens accounts *inside* that script (locked Linux password, D13 derived Forgejo password, `~/.git-credentials` token, homes `0700`), then R1.2 onwards. A reset re-runs `provision-account.sh <user>`: the derived password comes out the same and T2.1c's token step is already idempotent (reuse or re-create by name). | user, 2026-09-28 |
| R8 | The allocator stays single-threaded for request handling. The reset runs in **one worker thread**; request handlers only start it and read its published progress (same pattern as the status probe thread). | proposed |

## 2. Problem

A student who breaks their lab badly enough (deleted `~/lab`, force-pushed over their fork, wedged their OpenBao
namespace, left Dojo Cloud resources in a state the lab can't recover from, a runaway app on `app-host`) has no way
back today except the facilitator fixing it by hand in several places. **Release** only kills their processes and
frees the seat; their home, Forgejo account, namespace and cloud resources all survive, so the next person to get
that seat inherits the mess too. The only full reset is `./run.sh stop`, which resets the whole class.

## 3. What "the student's environment" is today

Inventory taken 2026-09-27 from the code (re-check before R1; paths are the ones that create the state).

| Where | Per-student state | Created by | Existing way to remove it |
|---|---|---|---|
| web-terminal, `terminal_home` volume | `/home/<user>`: `lab/` (copy of the seed), `.gitconfig`, code-server settings, `lab/.vscode/tasks.json`, `.zshrc` symlink, shell history, anything the student made | `engine/web-terminal/entrypoint.sh` per-account block (~l.195-310), `cp -Rn` so it never overwrites | none; `stop_user` only kills processes |
| web-terminal, outside home | processes (code-server, ttyd, tmux), `/tmp` and `/dev/shm/<user>` files (vault lab 6 renders secrets there), watch ttyd | `workspace-control.py` | `POST /stop/<user>` (processes only) |
| web-terminal, module/workshop hooks | anything `start.d` hooks or `lab-prep` did per account (e.g. `workshops/cert-autorenewal/.../90-cert-autorenewal.sh`) | `/etc/dojo/start.d/NN-*.sh`, run once for all accounts | none |
| Forgejo | account `<user>`, membership of the `students` team, forks (`<user>/<repo>`, tofu-basics and vault lab 8 use `FORGEJO_FORK_WORKFLOW=1`), branches/PRs/comments in the shared org repo, SSH/GPG keys, access tokens, Actions secrets on their fork | `engine/git-server/bootstrap.sh` (user + team, idempotent); the rest by the student | Forgejo admin API with `FORGEJO_ADMIN_USER/PASSWORD` (delete user with purge, delete repo, close PR, delete branch) |
| Browser | Forgejo session cookie, code-server state in browser storage | the student's browser | Forgejo sessions die with the account; code-server browser state: §8 Q4 |
| `modules/openbao` (+ vault workshop) | namespace `students/<user>`, entity/alias, mounts, KV data, JWT/AppRole/DB config, tokens and leases; `secret/students/<user>/…` in the shared mount | `workshops/vault-fundamentals/compose/openbao-setup.d/10-tenancy.sh`, `20-ci.sh`, `30-platform.sh` via the one-shot `openbao-setup` | provisioner token can delete and recreate the namespace (`modules/openbao/setup/policies/provisioner.hcl`); nothing resident holds it (§8 Q2) |
| `modules/dojo-cloud` | subscription (derived from username), resource groups, container groups (real containers, ports, DNS labels) in the cloud-api state volume | the student's `tofu apply` / ARM calls | portal purge of one subscription (`modules/dojo-cloud/cloud-api/portal_api.py` `_purge`), already removes containers outside the lock |
| `modules/runner-pool` | queued/running CI jobs from the student's fork, single-use runners, job workspaces | the student's pushes | controller can stop runners; no "cancel this user's jobs" |
| `modules/forgejo-runner` | jobs from the student on the shared runner | the student's pushes | cancel via Forgejo API |
| vault `app-host` / `app-db` | deploy slot `<user>` (Linux user, unpacked app, running process, platform token in `/run/platform/<user>`), per-student DB objects | `compose/app-host/apphost.py`, `compose/app-db/init.sh` | none per slot |
| `modules/dns-ui` / dns-as-code / cert-autorenewal | records in the **shared** zone, shared step-CA state | the student's PRs through CI | PowerDNS API; ownership of a record is not recorded (§8 Q3) |

## 4. Design

### 4.1 Facilitator experience

- The roster tile menu gets **Reset** next to **Release**. It opens a dialog: what will be reset (the list of steps
  for this run, from the engine plus every declared hook), and a text box where the facilitator types the student id
  (`student07`) to enable the button.
- While it runs, the tile shows "Resetting…" and a step list with ✓ / ✗ / … per step, polled from
  `/admin/api/sessions` (a new `reset` field per row, no extra poll).
- On failure the tile shows which step failed and its short error, and offers **Retry** (reruns the whole reset;
  every step is idempotent, R5).
- The student, meanwhile: every `/ide`, `/term`, `/forgejo-login` and extension route for that student returns the
  existing "starting" page with the text "Your environment is being reset…" until the reset finishes, then works
  normally on reload. No new page template: it is the starting page with a different message.
- Demo bots can be reset the same way (useful for testing); the bot restarts from round 1.

### 4.2 Order of a reset

The worker runs these steps in order and records each result. Steps 1 and 7 always run, even after a failure.

1. **Fence.** Mark the student `resetting` (auth-check stops proxying their routes). Kill their processes
   (`POST /stop/<user>`, as Release does).
2. **Module/workshop teardown hooks**, in manifest order (§4.4): cancel CI jobs, delete cloud resources, delete the
   OpenBao namespace, stop the app-host slot, etc. Done before the Forgejo account goes, so hooks can still look the
   student up.
3. **Forgejo teardown.** Delete the user with purge (removes their repos/forks, keys, tokens). Then, in the shared
   org repo: close open PRs they authored and delete branches whose head commit is theirs and that no other open PR
   uses (§8 Q5 on exact rules). Spike R0.2 confirms what purge already does.
4. **Forgejo re-provision.** Recreate the account and team membership exactly as `bootstrap.sh` does.
5. **Terminal re-provision.** New workspace-control endpoint `POST /reset/<user>`: run `reset.d` hooks, remove
   `/home/<user>` and the student's files in `/tmp`, `/var/tmp`, `/dev/shm`, then run the same per-account
   provisioning as start-up (4.3), then per-account hooks.
6. **Module/workshop provision hooks**, in manifest order: recreate the namespace, re-seed the welcome secret, etc.
7. **Unfence.** Clear `resetting`, append a line to the facilitator log (who, which student, when, result per step).

### 4.3 Engine changes

- `entrypoint.sh`: move the per-account block (home, lab seed, `.gitconfig`, code-server settings, tasks.json,
  `.zshrc`, and the bot variant) into `/usr/local/lib/dojo/provision-account.sh <user>`. Start-up calls it in its
  loop; reset calls it for one user. Behaviour at start-up must be byte-for-byte the same (R1.1 verifies).
- **Per-account hooks**, beside `start.d`: `/etc/dojo/account.d/NN-name.sh <user>` (provision one account,
  idempotent, run at start for every account and after a reset) and `/etc/dojo/reset.d/NN-name.sh <user>` (clean up
  what the hook owns for one account before the home is removed). Numbering as `start.d` (modules `50-`, workshops
  `90-`). A hook that does per-account work in `start.d` today moves it to `account.d`.
- `workspace-control.py`: `POST /reset/<user>` (control token, `valid_username`, never the facilitator). Runs 4.2
  step 5 synchronously and returns per-hook results; the allocator's call gets its own longer timeout, not
  `CONTROL_TIMEOUT` (3 s).
- `bootstrap.sh`: split "ensure one student account" into a function the reset step can call for one user, or have
  the allocator make the same two API calls itself (§8 Q6).
- `server.py`: `POST /admin/reset/<sid>` (same `X-Requested-With: dojo-admin` CSRF check as Release, plus the typed
  id in the body), the worker thread, the `resetting` fence in `handle_auth_check` / `handle_route_check`, the
  `reset` field in `/admin/api/sessions`, and the roster UI (textContent only, no inline script/style).
- `render_extensions.py`: validate a new `resets` key (4.4).
- Docs: `engine/README.md` "Facilitator operations", `workshops/README.md` (the hook contract for authors).

### 4.4 Hook contract for modules and workshops

Two ways, both optional, both declared only in the module's or workshop's own files:

1. **Terminal-side**: `account.d` / `reset.d` scripts in the tools image (4.3). For state that lives in
   web-terminal.
2. **Service-side**: a `resets` list in `extensions.json`:

   ```json
   "resets": [
     { "id": "dojo-cloud", "label": "Dojo Cloud resources",
       "upstream": "cloud-api:8080", "path": "/_dojo/reset/{user}", "timeout": 30 }
   ]
   ```

   The allocator calls `POST <upstream><path>?phase=teardown` in step 2 and `?phase=provision` in step 6, with
   header `X-Dojo-Reset-Token`. The service answers `200` with `{"ok": true, "detail": "…"}` or an error.
   Rules, enforced by the renderer like `routes`: `upstream` must be a service in this run, `{user}` is the only
   placeholder, `id` unique across manifests, `timeout` 1-120 s, a bad entry stops the start.

`RESET_TOKEN` is a new engine secret (made by `env-setup.sh`, like `CONTROL_TOKEN`), passed only to the allocator
and to services that declare a `resets` entry. Every reset endpoint **must** check it with a constant-time compare:
the services sit on `workshop_lab`, which students can reach.

### 4.5 What each module/workshop would provide

| Owner | Teardown | Provision |
|---|---|---|
| `dojo-cloud` | purge the student's subscription (reuse `_purge`) | nothing |
| `openbao` + vault | revoke tokens/leases, delete `students/<user>` and `secret/students/<user>/` | rerun the tenancy/CI/platform hooks for one user (they are idempotent per the inventory) |
| `runner-pool` | cancel the user's queued/running jobs, stop their runners, clear workspaces | nothing |
| `forgejo-runner` | cancel the user's jobs | nothing |
| vault `app-host` / `app-db` | stop slot, wipe slot home and token, drop the student's DB objects | recreate slot and DB objects as at start |
| `dns-ui`, dns-as-code, cert-autorenewal | only if ownership can be known (§8 Q3); otherwise nothing, and the dialog says shared DNS is not reset | nothing |
| `git-fundamentals`, `tofu-basics` | nothing beyond engine steps (tofu-basics state is in the fork and in Dojo Cloud) | `lab-prep` via `account.d` if it does per-user work |

## 5. Risks to check first (R0)

- **Forgejo purge semantics.** What `DELETE /admin/users/{u}?purge=true` removes in *other* users' repos (PRs,
  comments, branches in the shared org repo), and whether recreating the same name right after hits caches or
  "name reserved" rules.
- **Recreated Forgejo account and existing clones.** A student's old credentials still work (same password), but
  Actions IDs, runner registrations tied to the fork and OIDC `repository_id` claims change. Check app-host's claim
  check and OpenBao's CI JWT role still accept the new fork.
- **Killing processes vs. open browser tabs.** code-server tabs reconnect; check that they land on the fenced page,
  not a half-deleted home.
- **Files owned by the student outside `/home`.** `find -xdev -user` on web-terminal; runner-pool and app-host have
  their own Linux users per student.
- **Podman-compose.** Nothing in reset starts or removes compose services; if a hook needs Docker (dojo-cloud), it is
  that service's call, outside any lock (existing rule).
- **Time.** A full reset must finish well inside a lab (target: under 30 s with every module).

## 6. Security notes

- Only the facilitator can start a reset: `/admin*` basic auth, the `X-Requested-With` check, typed id in the body.
  Never the facilitator account itself, never an id outside `STUDENT_IDS` + `BOT_IDS`.
- Every service reset endpoint checks `X-Dojo-Reset-Token`. A reset endpoint is as dangerous as a delete-everything
  API for that student; tests must include "no token" and "wrong token" → 403.
- The dialog and progress show module labels (from manifests) and short error text; render with `textContent`.
  Errors from services may echo student input.
- A reset deletes data. It is logged (facilitator log, and each service's own audit log, e.g. OpenBao's, keeps its
  history).
- `{user}` is only ever a validated `studentNN`/bot id, so it is safe in a path; the renderer still rejects any other
  placeholder.

## 7. Tasks

### R0: spikes (throwaway, in the scratchpad; no engine edits kept)

- [ ] R0.1 List every file owned by a student on a running stack after doing all labs of one workshop
  (`find -xdev -user`), in web-terminal, runner-pool, app-host. Update §3.
- [ ] R0.2 Forgejo purge + recreate by hand via the admin API on a running stack; record what survives. Answers
  part of §8 Q5.
- [ ] R0.3 Manual reset of one vault-fundamentals student (namespace delete + tenancy hooks for one user) and rerun
  of labs 1-2 as that student.
- [ ] R0.4 Time each step; confirm the < 30 s target is realistic.

### R1: engine core (engine edits; ask before each)

- [ ] R1.1 *(before remediation T2.1, R10)* `provision-account.sh` extracted from `entrypoint.sh`; start-up unchanged. **Verify:** diff of
  `/home/*` listing and contents on a fresh start before and after the change.
- [ ] R1.2 *(after remediation T2.1, R10)* `account.d` / `reset.d` hook runner + `POST /reset/<user>` in `workspace-control.py`.
- [ ] R1.3 Forgejo steps (teardown + re-provision) in the allocator or `bootstrap.sh` (per §8 Q6).
- [ ] R1.4 Allocator: `POST /admin/reset/<sid>`, worker thread, fence, `reset` in sessions API.
- [ ] R1.5 Roster UI: Reset item, confirm dialog, progress, Retry.
- [ ] R1.6 Tests in `engine/allocator/tests/` (auth, fence, idempotency, bot reset) and a live check with
  git-fundamentals (no modules).

### R2: hook contract

- [ ] R2.1 `resets` in `render_extensions.py` (+ tests), `RESET_TOKEN` in `env-setup.sh` and compose.
- [ ] R2.2 Allocator calls service hooks (teardown/provision), with per-hook timeout and results.

### R3: modules and workshops adopt

- [ ] R3.1 `dojo-cloud` (reset endpoint on cloud-api, reuse `_purge`) — tofu-basics live check.
- [ ] R3.2 `openbao` + vault tenancy/CI/platform: the `openbao-reset` service and its token (R9; minted in remediation
  T5.3, so do that first).
- [ ] R3.3 `runner-pool`, `forgejo-runner`.
- [ ] R3.4 vault `app-host`, `app-db`.
- [ ] R3.5 dns-ui / dns-as-code / cert-autorenewal per §8 Q3; move any per-account `start.d` work to `account.d`.

### R4: docs and hand-over

- [ ] R4.1 `engine/README.md` "Facilitator operations"; `workshops/README.md` hook contract; module READMEs.
- [ ] R4.2 Live pass per workshop: break a student on purpose, reset, redo the first labs as them, while a second
  student and `--test` bots carry on unaffected. Browser pass by the user.

## 8. Open questions

- **Q1** Reset keeps the seat (R4). Also want "reset and release" (wipe, then free the seat for someone else), e.g.
  so Release always leaves a clean seat?
- ~~**Q2**~~ *Answered 2026-09-28: R9.* OpenBao reset needs the provisioner token in a resident service (`openbao-setup` is one-shot). Put the
  endpoint in `sso-shim`, a new small `openbao-reset` service, or keep `openbao-setup` running?
- **Q3** Shared DNS zone: record who created which record (e.g. a naming convention like `<user>-*.dojo.test`, or
  the CI commit author) so reset can remove them, or state that DNS is out of scope?
- **Q4** code-server keeps some UI state in the browser (open editors, layout). Accept it, or have the reset page
  clear it (it can only clear its own origin's storage for that browser)?
- **Q5** Exactly what to remove from the shared org repo: close the student's open PRs, delete their branches,
  delete their comments? Leave merged history alone (R6)?
- **Q6** Forgejo re-provision: call a single-user function in `bootstrap.sh` (keeps one source of truth, needs the
  bootstrap image reachable at runtime) or have the allocator make the two API calls itself?
- **Q7** Should a student be able to ask for a reset from their own page (facilitator approves), or facilitator only?

## 9. Findings

(none yet)

## 10. Session log

### 2026-09-27: plan

Wrote this plan from a read of the engine (allocator, workspace-control, entrypoint, bootstrap) and every module and
workshop's per-student state (§3). Nothing built.

### 2026-09-28: two decisions with the threat-model remediation

The user took R9 (a narrow reset token in a resident `openbao-reset` service, answering Q2) and R10 (R1.1 before
remediation T2.1, which then builds on `provision-account.sh`). Both resolve clashes with
`threat-model-20260926-154208/REMEDIATION-PLAN.md` (D11/T5.3 and T2.1); see that plan's D15 and D16.
