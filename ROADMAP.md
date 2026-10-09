# Roadmap

The single list of open work. Finished work moves to [`RELEASES.md`](RELEASES.md). The old per-feature plans
(design, decisions, task logs) are frozen in [`docs/archive/`](docs/archive/); read them for the why, but don't
update them. When you finish an item: delete it here and add a line to RELEASES.md.

Last updated: 2026-10-09 (content-depth audit of all 5 CTF packs done -- two fixes shipped, content verified
line-by-line against source; see RELEASES). Before that, same day: CTF plan and roadmap rows refreshed; CTF build
log moved to RELEASES. Before that: 2026-10-07 (the ctf-range Target Viewer, themed attack boxes and the `ctf-access` pack merged to `main` in
PR #17; the CTF series, the Zellij flavor and the earlier branch work all landed with it). ·
Working branch: `main`; cut a feature branch for each new batch of work.

**Effort:** **S** one sitting (an hour or two) · **M** a day or so · **L** several days · **—** no work planned.
RV efforts come from the platform review; the rest are estimates. Where something is already built, the effort is
what is left (usually the live check).

| Section | What it holds |
|---|---|
| [Priorities](#priorities) | The order of work, decided at the 2026-10-01 review |
| [Up next](#up-next) | Where to resume; decisions of 2026-10-02 and 2026-10-03 |
| [Now](#now) | Student reset and Phase 10 live checks (the split smoke run is parked in [Later](#later)) |
| [Next](#next) | CTF workshop series; N3 9.4 class-sized run; platform review (RV26-RV38); student reset; achievements leftovers; `dojo` CLI; remediation leftovers |
| [Manual checks](#manual-checks) | Browser passes only the user can do |
| [Later](#later) | Follow-ups and known limits |
| [Housekeeping](#housekeeping) | Repo hygiene |
| [Reference](#reference) | Settled decisions and design notes for student reset and achievements |

## Priorities

Decided at the 2026-10-01 review. Done since: committing the working tree (`4481225`), the home demo dry run,
platform review tier 1 and the merge to `main` (PR #6), the Phase 9 live checks apart from the class-sized run
(PR #7) (2026-10-02), Cloud-Policy-as-Code (RV35) with RV19, the Phase 10 sweep and the student reset build (PR #8)
and the pack's pids cap (PR #9) (2026-10-03), then on `feat/zellij-terminal` (unpushed): the Zellij flavor, the CTF range scaffold/SAST/control plane, RV29/RV30/RV25/RV27 and the ctf-range digest pins (2026-10-04, see RELEASES). The user's own browser checks ([Manual checks](#manual-checks))
fit in around these; tofu-basics T9.4/T9.9 are the oldest.

| # | Work | Effort | Description |
|---|---|---|---|
| 1 | Student reset: live checks | S | All four hooks have now run live: DNS and cert 2026-10-03, cloud (with a non-empty pre-state) and vault's capstone 2026-10-04. Left: the vault reset once on the Ubuntu WSL/Docker host, and the purge-line finding in [Now](#now) |
| 2 | Phase 10 leftovers | S | Done apart from the browser looks: `slide-overflow.sh` ran on dns-as-code and dojo-introduction `--test 5 --fast` re-ran with 0 skips (2026-10-04, [Now](#now)). Left: the two browser looks, and 7 overflowing slides to trim across the vault and dns decks |
| 3 | Platform review tiers 3-4 | L | RV35, RV22-RV25, RV27-RV31 done; left RV26, RV32-RV34, RV36-RV38 |

## Up next

Resume here (updated 2026-10-04). The vault reset fix merged to `main` in PR #12: `lab_11.sh` and `lab_12.sh` pass after
a reset. Branch state 2026-10-07: `feat/zellij-terminal` merged to `main` in PR #17 (CTF range, the Zellij flavor, RV25/RV27/RV30,
the ctf-range pins, the Target Viewer); the branch and the duplicate `feat/zellij-terminal-flavor` can be deleted
(see [Housekeeping](#housekeeping)); the merged `origin/feat/rv22-allocator-split` and `origin/docs/roadmap-resume` can be
deleted by hand.
The split smoke run is parked (see [Later](#later)); the full-stack smoke loop is paused. Next, one stack at a time
(`podman ps` first):
1. ~~**Vault capstone two-step**~~, ~~**cloud reset + capstone**~~, ~~**the Phase 10 leftovers**~~: all run 2026-10-04 on the
   Mac (see [Now](#now)). Nothing is left on a stack here. No stack is up: each run ended with `./dojo stop`.
2. ~~**The two findings of 2026-10-04**~~: `no_push_since_step`'s sub-second hole, and the purge line that
   never named policy objects or tofu states. Both fixed 2026-10-05 (`418d5ad`), unit-tested, no stack needed.
3. **One run on the Ubuntu WSL/Docker host** with `RUNNER_POOL_SECURITY_OPT_1/2` unset, to confirm the defaults
   (`no-new-privileges=true`, bare `no-new-privileges`) change nothing there. This and the browser looks are all
   that the Mac cannot do.

On the Mac (rootful Podman + SELinux) start with `--env mac-podman` (sets `RUNNER_POOL_SECURITY_OPT_1=unmask=/proc/*` and
`RUNNER_POOL_SECURITY_OPT_2=label=type:container_engine_t`), or no runner or app can start (`unshare: mount /proc
failed`). Details in `modules/runner-pool/README.md`. The Mac's
published port 8080 can reset connections from the host; reach the gateway from inside the lab network instead, with
`Host: localhost:8080` (the facilitator login is the `/login` cookie, and Reset needs `X-Requested-With: dojo-admin`).
Every `--test` run uses `--fast`.

**Answered 2026-10-02**

| Question | Answer |
|---|---|
| Reset button | Yes, a full **Reset environment** button on `/admin` (RV38), with Release all as its first step. Nothing may persist past `./dojo stop` |
| Shared helpers (RV20/RV21) | One copy in `modules/_shared/`, copied into `<context>/_shared/` at build time (`SHARED=` in `module.env`) |
| Shared-repo changes on reset (2026-10-03) | Left alone: a student reset never touches what they changed in a shared repo (e.g. dns-as-code `<user>-app` records in `dojo.test` stay) |
| Next workshop | Cloud-Policy-as-Code (RV35), merged to `main` in PR #8 (2026-10-03) |

## Now

Live checks for what was built 2026-10-02 and 2026-10-03 (all unit-tested; nothing below has run on a stack unless
it says so). A brief for an agent is built from these lines.

| Check | Stack | What to confirm |
|---|---|---|
| Vault reset | `vault-fundamentals --test 2 --fast` | **Fixed 2026-10-03** (`fix/vault-reset`): app-db's worker was started with `su-exec`, which the Postgres image no longer has (now `gosu`), and `kv_wipe` failed on an already-empty folder (`bao list -format=json` says `{}`). Two resets in a row of testuser1 passed all 12 steps, locally, and `lab_11.sh` (12 checks) and `lab_12.sh` (9) passed after a reset (rootful Podman on macOS needs `RUNNER_POOL_SECURITY_OPT_1/2` in `.env` for the pool and app-host; `openbao-setup` needed more than 64m). Left: run `vault-fundamentals --test 2 --fast` once on the Ubuntu WSL/Docker host with the two variables unset, to confirm the repeated `no-new-privileges:true` changes nothing there |
| Cloud reset + capstone | `tofu-basics --test 2 --fast` | **Both halves passed 2026-10-04 on the Mac (rootful Podman).** Reset with a non-empty pre-state: testuser1 and testuser2 each given one Running container group, reset of testuser1 ran 9 steps all ok, `dojo-cloud-teardown: removed 1 container group(s), 1 resource group(s)`; afterwards testuser1's was gone, testuser2's still Running, and testuser1's bot restarted from round 1 (so a fresh `ci-hello-dev` appears — don't read that as the old one surviving). Capstone two-step as `student01` (not a bot: bot accounts have no `credential.helper`, so they cannot push outside the bot runner's `GIT_ASKPASS`): two sites from one `for_each` → "Halfway", `tofu destroy` → "Passed! +300". Left: nothing here — the `policyObjects` sub-item became its own finding below |
| Vault capstone two-step | vault stack | **Passed 2026-10-04** (needs `ACHIEVEMENTS_ENABLED=1`; it was 0, so `dojo-check`/`dojo-challenge` were not in the terminal image at all). "Halfway" → rotate `capstone/app` with no push → "Passed! +300", and a push in between answers "main of `<user>`/capstone changed after step 1 passed (a push deploys). Back to step 1". The push case only holds with a gap of more than a second — see the `no_push_since_step` finding below |
| Browser looks (user) | any | Widget frame full height on first load; the Reset dialog's "Also clear their achievements and score" checkbox |

Slide overflow checker: `workshops/assets/slide-overflow.sh <workshop> [page.md ...]`. It timed out after login on dns-as-code (it waited for
`networkidle`, but the portal polls); fixed 2026-10-03 and clean on git-fundamentals (5 pages). **Run on dns-as-code 2026-10-04: the
fix holds (no timeout), and it found 2 overflows** — `cheat-sheet.md` slide 6 `<table>` 110 px past (the `doctor` command table) and
`presentation.md` slide 11 `<p>` 34 px past. Also run on vault-fundamentals the same day (not asked for, but the stack was up):
`index.md`, `lab-index.md` and `labs.md` clean, **`presentation.md` over on 5 slides** — 8 `<li>` 45 px, 10 `<li>` 5 px, 21 `<p>` 10 px,
31 `<p>` 10 px, 49 `<p>` 12 px. So 7 slides across two decks need trimming; the checker itself is now proven on three packs.

Passed 2026-10-03: DNS reset (no purge, PRs kept as Ghost, zone gone, shared records kept, second reset ok), cert reset
(crontab gone, two seeded records, clean reload; the pre-state was not captured) and dojo-introduction `--test 5 --fast` (no skips).

Passed 2026-10-04 (all on the Mac, rootful Podman): the cloud reset and both capstone two-steps above, the dns-as-code slide run,
and dojo-introduction `--test 5 --fast` again now that the bot steps check their results — 5 bots, all 5 finished round 1,
**0 skips and 0 retries** (a skip prints `FAST: <step> failed N times -- skipping it`). The only gateway error in that run was a
single startup 502 on `/slides/` before the presentation container served, after which the stack reached 17 of 17 ready.

Both of the 2026-10-04 findings below are **fixed** (`418d5ad`, unit-tested, no stack needed — see RELEASES.md).

After the live checks pass: move student reset R0-R4 and R3.x to RELEASES (git-fundamentals live result: steps 3-5 s,
idempotent, a bot restarts from round 1, the optional score clear clears only that student), and delete them below.

## Next

### CTF workshop series

A five-session capture-the-flag series (CTF-1 to CTF-5, packs `ctf-access`, `ctf-server-trust`, `ctf-secrets-config`,
`ctf-trust-chain`, `ctf-defend`). The range, all 14 targets and the CTF-5 defend tooling are built (see RELEASES, "CTF range
build log"). The plan, with its checkpoint, is [`docs/CTF-WORKSHOP-PLAN.md`](docs/CTF-WORKSHOP-PLAN.md); it carries the detail.

`workshops/ctf-defend-test` (the old shared facilitator harness) is deleted; `ctf-secrets-config` and `ctf-trust-chain`
now ship all 3 of their targets each (see RELEASES, "`ctf-secrets-config`/`ctf-trust-chain` complete their ladders").

| Step | Work |
|---|---|
| 1 | Class-sized run: 40-student capacity and isolation, the swarm with real dwell and ramp times, the Target Viewer card as a student |
| 2 | Unbuilt design items: `CTF_WALL_OF_SHAME` toggle and route, bonus second flaws for targets 8-11, end-of-session scoring (CTF-D19), plan open questions 1-3 |

### N3 9.4: class-sized run

Skipped for now (user, 2026-10-02); ask before starting it. The rest of N3 (Phase 9 live checks) is in RELEASES.

| Step | Work | Effort | Description |
|---|---|---|---|
| 9.4 | Class-sized concurrency run (last; skipped for now, 2026-10-02) | M | On dns-as-code or git-fundamentals with ~20 bots: shell hook latency, state sweep budget (`gap=20`, `budget=40`), no dropped events, `/admin` leaderboard and toasts still responsive. Also recheck the **facilitator VS Code tab "unknown error"** (seen once under load, a retry fixed it, not reproduced at 10 bots) with the `/auth-check` logging from remediation T1.4; sizing for 20-35 students is extrapolated from 10 bots until this run |

Tools (`modules/achievements/tools/`, run from the repo root): `fired.py <workshop>` lists each catalog item with who
earned it and the never-fired ids; `botaudit.py <workshop>` runs every bot command through the real matcher (static:
runtime values, output and `requires` are not known, so its misses need a look, not a fix); `box.py` (usage in its
header) counts challenge boxes on a lab page in headless Chromium. Working rules: every bot run uses `--test --fast`; long waits go to a sub-agent with a
short brief and one blocking wait loop; bots stay lab-only (decided 2026-10-02: challenges are solved by hand, one
solve each per pack); student commands that must reach achievements run in an interactive zsh (tmux), not `zsh -lc`.

### Platform review (2026-10-01)

A whole-stack review: four read-only passes over the engine runtime, the CLI and terminal images, the modules, and
the workshops and docs. It left out items already on this roadmap and the accepted security residuals. Tiers are
the suggested order. Line numbers are as of `7bc4ce9`.

**Tier 1: load and crash fixes (before the class-sized run).** The engine items (RV1, RV3-RV5, RV8-RV12) shipped
2026-10-01 (see RELEASES); the module items RV2, RV6 and RV7 passed live 2026-10-02 (see RELEASES).

**Tier 2: CI and tests.** RV13-RV19 shipped 2026-10-02 (see RELEASES).

**Tier 3: refactors and hygiene.** RV20 (`dojo_http.py`) and RV21 (`adapter_client.py`) shipped 2026-10-02; RV25
(tool-pin drift check) and RV27 (`forgejo-runner` deleted) 2026-10-04 (see RELEASES). RV26 is all that is left.

| ID | Work | Effort | Description |
|---|---|---|---|
| RV26 | Shared lab-prep and slide assets | M | One `lab-prep` skeleton for the four copies; slide logo and shared slide assets from `workshops/assets/themes` (the 873 KB PNG is in all 6 packs; one shared copy is now at `workshops/assets/GitOps_Dojo_Dark.png`, which the scaffold template uses, so the packs can switch to `assets/GitOps_Dojo_Dark.png`) |

**Tier 4: new features and workshops.**

| ID | Work | Effort | Description |
|---|---|---|---|
| RV32 | Progress export | S | Facilitator export of progress and achievements (CSV/JSON) |
| RV33 | Feedback survey card | M | End-of-class feedback survey card |
| RV34 | Terminal recording | M | Terminal session recording or replay |
| RV36 | More workshops | L each | GitOps with a reconciler (Argo CD or Flux on k3s), needs a capacity check; then supply chain (cosign, SBOM), observability as code, secrets rotation |
| RV37 | Several classes at once | L | One workshop per machine today |
| RV38 | Reset environment button | M | Asked for 2026-10-02: a button on `/admin` that releases every slot and puts every student back to a fresh start without restarting the stack (between two sessions of a class). Build it on the student reset's per-student hook contract (`STUDENT-RESET-PLAN.md` §4.4): run the reset for every student, then module hooks clear their own state (achievements, sensei, dojo-cloud). Facilitator gate, a typed confirmation, audit line. A smaller first step, **Release all**, only clears the slot table. Rule: **nothing survives `./dojo stop`**; every state file stays in a named volume (`allocator_state` is, verified 2026-10-01), and RV13's CI should fail any compose fragment that writes state outside one. Engine change, approved |

### Student reset

The facilitator resets one student's whole environment. Design: `docs/archive/STUDENT-RESET-PLAN.md`; settled
decisions in [Reference](#student-reset-decisions). **Status 2026-10-02: everything is built; engine plus achievements
passed live on git-fundamentals; the module hooks wait for their live runs ([Now](#now)).**

| ID | Work | Status |
|---|---|---|
| R0 | Spikes | Done live on git-fundamentals: a reset takes 3-5 s; Forgejo lets the name be made again at once; the new token reaches git; a bot restarts from round 1. Found: **purge** deleted the student's merged PRs, against Q5, so the teardown now deletes their own repos, leaves the org, and deletes the account without purge (falls back to purge if refused, and says so). Not yet live |
| R1 | Engine machinery and Roster UI | Live on git-fundamentals. Added 2026-10-02: `resets` entries may be `"optional": true` (a checkbox in the dialog, off by default, sent as `optional=<ids>`); the terminal reset also removes the student's crontab |
| R2 | Hook contract | Docs in `workshops/README.md` (incl. `optional`) |
| R3.1 | dojo-cloud | Built: `/_dojo/reset/<user>` on cloud-api, teardown through `Portal._purge` and its policy objects (`policy_api.purge`, added with RV35; live check in [Now](#now)) |
| R3.2 | openbao | Built: `openbao-reset` relay; `openbao-setup` stays up and runs reset jobs with its own token (the token never moves, unlike R9's wording); one-user mode in `10-tenancy.sh`, `20-ci.sh`, `30-platform.sh` |
| R3.3 | runners | Built: runner-pool stops runners busy with the student's own repos (`/spool/kill/`) |
| R3.4 | vault apps | Built: app-host empties both slots and locks the capstone slot; app-db drops and remakes the student's database (through app-host) |
| R3.5 | DNS packs | Built: dns-gate deletes zones at/under `<user>.<parent>` and their names in shared zones, then re-creates `DNS_GATE_RESET_RECORDS` (cert-autorenewal sets its two seeded A records); cert-autorenewal's webroot moved to `account.d`, with a `reset.d` that removes the old site. Shared-repo records stay by decision (2026-10-03) |
| R3.6 | achievements | Built and live: `achievements-progress` (forgets seeds, watches, half-done two-step checks, Sensei activity) and optional `achievements-score` |
| R4.1 | Docs | Done: `engine/README.md` "Reset a student", `workshops/README.md`, dns-gate and openbao READMEs |
| R4.2 | Live pass per workshop | The [Now](#now) table |

### Achievements

An optional layer over the labs (`ACHIEVEMENTS_ENABLED`): toasts on every student page, a class leaderboard, a
goal-only challenge per lab, a capstone, and a certificate at the end. Rule: **ask before editing any `engine/`
file**. Done (RELEASES): phases 0-2 (design and catalogs, catalog core, engine workspace and widgets, score service
and toasts), 4 (challenges), 5 (cheat tiers and names), 7 (Sensei), 8 (toast surfaces). Phase 9 is built and live on
git-fundamentals and dns-as-code ([N3](#n3-94-class-sized-run)). Design, decisions and working notes:
[Reference](#achievements-design).

| ID | Work | Effort | Description |
|---|---|---|---|
| Phase 6 | Certificate: one decision left | S | Certificate, badge PNG and name dialog are done; one decision is left |
| Phase 9 | Class-sized run | M | Built and live on all packs, cloud-policy-as-code included (RELEASES); only the class-sized run is left ([N3](#n3-94-class-sized-run)) |
| — | Browser look | S | Not looked at in a browser yet: a red negative score (board, widget, `/admin`) and a negative toast in VS Code; the badge PNG download, capstone badge tier and a typed certificate name; a real student's stale-branch roster PR |
| — | Widget resize: browser check | S | Fixed 2026-10-02, not seen in a browser: the landing page's widget frame should have its full height on first load (`toast.js` asks the widget to report again once it listens) |
| — | Hidden-tab toasts: browser check | S | Built 2026-10-02, not seen in a browser: with the landing page open in a background tab, an unlock in the VS Code terminal pops up in VS Code (`toast.js` skips polling while `document.hidden`), and the landing page shows queued toasts when it comes to the front |

### `dojo` CLI follow-ups

C1-C4 shipped 2026-10-01 (see RELEASES).

| ID | Work | Effort | Description |
|---|---|---|---|
| C5 | Untested paths | S | Everything else passed on macOS (podman) and Docker (RELEASES). Left, for the user out of band: `CORP_CA_BUNDLE` for the first-run wheel download behind TLS inspection, and the error without it (C5-guide.md step 2). Steps: [`C5-guide.md`](C5-guide.md). (The flaky allocator test first seen here is fixed: see RELEASES.) |

### Remediation leftovers

None are Critical or Important.

| ID | Work | Effort | Description |
|---|---|---|---|
| FIND-11 | PowerDNS keys | — | Partial, accepted (2026-10-03): per-student DNS keys and the gate's ownership checks are in; PowerDNS's own key stays a one-way hash of `GATEWAY_TOKEN`, which students never see and which already opens the whole lab |
| FIND-17 | Unseal share | — | Partial, accepted (D9): the single unseal share stays on the setup volume |
| FIND-15 | dojo-cloud socket | — | Accepted, no work: socket `0660 root:cloud`; privileged DinD stays |
| FIND-19 | Plaintext backends | — | Accepted, no work: plaintext to OpenBao and Postgres, documented |
| — | Not exercised in P4/P5 | M | 300 app-db connections · the app-host shim on 443 (base URL was plain `http://localhost:8080`) · a real-browser "Release unused" |

## Manual checks

Browser passes only the user can do.

| Check | Effort | Description |
|---|---|---|
| [Modules browser pass](#modules-browser-pass) | M | Was MODULES-PLAN T3.4: every workshop as a student and as the facilitator (checklist below) |
| tofu-basics T9.9 (browser pass) | M | Labs 0-3 on a rebuilt image (including HCL highlighting in code-server) and labs 4-10 with the portal clicked, not called through the API: Add tag, Save tags, Delete dialog, Browse (to the deployed `dojo/hello` site), Quota tile, Refresh now, and the attention tile reading `code: message` (25a7176, offline-tested only). Facilitator: `/admin` Slides and Dojo Cloud tabs render in their iframes; Terminal, VS Code and Forgejo tabs still fine |
| tofu-basics T9.4 (human dry run, 3-5 people) | L | Run them through Track A only or A + B (about 103 min for both by the lab README's estimates). Note every point of confusion, time the walkthrough against the slide deck's talk timings (guesses so far), then fix labs, slides and README. `workshops/tofu-basics/FACILITATOR.md` says the first real class doubles as this dry run |
| vault-fundamentals | S-M | A person walking labs 7-9 in the UI (the tests make the UI's secret steps with the same API calls), the Runners panel's look beyond screenshots, and "Release unused" in a real browser. The rest of the P4/P5 browser pass was done by the user 2026-09-29 |
| UI changes, weekend of 2026-09-26 | S | The `/admin` sidebar at desktop width and under 700 px, and Mermaid diagrams in the lab reader, light and dark |

### Modules browser pass

For each workshop: `./dojo stop`, `./dojo <workshop>`, open the base URL as a student and in a private window as
the facilitator.

**Common checks**

| Area | Expect |
|---|---|
| Student landing page | Cards each open (VS Code, Terminal, Forgejo, Slides plus the workshop's own) |
| `/admin` | Roster, VS Code, Terminal, Forgejo and Slides plus the workshop's tab, each loading in its iframe |
| Status strip | Forgejo, Terminals and Slides Ready plus the workshop's own |
| Terminal | `whoami` gives `studentNN`; the workshop's tools run |
| Teardown | `./dojo stop` finishes cleanly |

**Per workshop**

| Workshop | Check |
|---|---|
| git-fundamentals | Lab 1, clone, branch, push, open a PR |
| dns-as-code | `dnscontrol version`; push a branch and open a PR; Actions shows **DNS Preview** green; merge and **DNS Apply** goes green; `dig` shows the record |
| cert-autorenewal | **Site Inspector** card and tab; after Lab 2 step 6 a student's visit shows `http://` → 301 → `https://` with a verified certificate, the second visit is upgraded by HSTS; the facilitator's tab can visit any student's name |
| tofu-basics | **Dojo Cloud** card and tab; the portal opens on the student's subscription; the facilitator's tab shows the progress view; after a Track B `apply` the resource shows in both |

This per-workshop table predates three packs and still needs rows for **vault-fundamentals** (its own browser notes are
in [Manual checks](#manual-checks) above), **dojo-introduction** and **cloud-policy-as-code** before the pass is complete.

## Later

### Smoke run

| Check | Stack | Where it stands |
|---|---|---|
| Split smoke run (parked 2026-10-03) | `smoke.sh cloud-policy-as-code --split each --timeout 60` | First run 2026-10-03: labs 2, 4-7 and 12 ok in 9-18 min. Failed: 3, 9, 10 in lab-prep (provider "Plugin did not respond": the 320 pids cap was hit 333 times; the pack now sets `WEB_TERMINAL_PIDS_LIMIT=1024`); 0-1 (retest.sh killed the bot mid lab 0 apply, leaving a state lock lab-prep 0 never clears: a range starting at 0 should only be watched, not parked and re-prepped); 8 and 11 (pr.yml red: a lab-prep gap. From Lab 8, CI plans the fork's `main` against the cloud, and `lab-prep` pushed the rebuilt state to `main` only from Lab 12, so CI saw the whole policy as drift. Fixed (PR #10): push it from Lab 8. Rerun alone with the fix: labs 8 and 11 PASS). When picked up: a watch-only mode in `retest.sh` for a range starting at 0, then `./dojo stop` (image rebuild for lab-prep and the caps) and rerun the split |

### vault-fundamentals follow-ups

| Work | Effort | Description |
|---|---|---|
| Policy as code for OpenBao | L | Namespace policies in a git repo, changed by PR and applied by CI with drift shown when someone edits in the UI; OpenTofu `vault` provider building on tofu-basics, or `bao policy write` in CI; a lab or its own workshop |
| OpenBao PKI for cert-autorenewal | M | Use OpenBao's PKI engine as the CA in `cert-autorenewal` |
| Mirrored actions in Forgejo | M | Mirror a small pinned set of actions (checkout, a vault-login action) into Forgejo at setup so labs can show `uses:` as companies do |
| Lab 11 restart login | S | Lab 11 should show a restart logging in again (lab 10 ends on that promise) |

### tofu-basics follow-ups

| Work | Effort | Description |
|---|---|---|
| `dcloud` CLI for students | M | `login`, `group list`, `container list/show/logs`; not `dojo`, which is the facilitator's platform CLI |
| CI `plan` on pull requests | M-L | Via Forgejo Actions; needs runner network design like dns-as-code's `runner_net` |
| More Azure-shaped resources | M-L | Virtual network, storage account, if the ARM facade extends cheaply |
| Remote state backend simulation | M | Simulate a remote state backend |
| Stretch labs 11-12 | L | Only if wanted |

### tofu-basics known limits

| Work | Effort | Description |
|---|---|---|
| One container per group | — | Only one container per group and only `dojo/hello:*` images (by design) |
| LRO | M | `Azure-AsyncOperation` is not implemented |
| arm64 | M | Untested: checksums pinned per arch, only amd64 built |
| 20+ students | — | Out of scope; 15 is this box's ceiling |
| T9.8 isolation on real Docker | M | **Deferred:** re-test isolation on real Docker before any non-podman delivery (the privileged-DinD risk is materially higher there); this machine has no Docker |

### Achievements shell hook limits (accepted)

| Work | Effort | Description |
|---|---|---|
| Chained-line exit codes | — | The hook sees only the line's exit code, so in a chained line a failure is credited only where it is provable (the last pipeline of the last list; see `matcher._segment_exits`): `a; git push; echo $?` can't earn `f-rejected` |
| Command text and hand-posted events | — | The hook sends the text of every command to the service (kept nowhere, only matched), and a student can post their own shell events by hand, which earns only what typing the command would |

### Not verified since `f977209` (code-server memory cut)

| Work | Effort | Description |
|---|---|---|
| tofu-basics e2e | S | `tests/e2e.sh` on the new web-terminal image |
| Capacity "Left out N" | S | `./dojo capacity` printing "Left out N" for a closed tab (dry-run only) |

### Tech to revisit

| Tech | Why parked | Revisit when |
|---|---|---|
| [Keyorix](https://github.com/keyorixhq/keyorix) | Lightweight, self-hosted, AGPL secrets manager (EU-compliance/NIS2 framing, air-gap friendly, two-binary deploy) evaluated 2026-10-05 against OpenBao for the vault lab. Deliberately skips Vault's PKI/dynamic-secrets/auth-method breadth for operational simplicity, so it's not a fit for `secrets-workshop-plan`'s teaching surface — and at ~20 GitHub stars it's too early to build any lab on. Positioning (self-hosted, EU-compliant, air-gapped, fully open source) is attractive and worth a second look once the project has real adoption | It picks up meaningfully more stars/contributors/production users, or a second project with the same positioning (self-hosted + AGPL/OSS + EU-compliance framing) appears and is more mature |
| [Infisical](https://infisical.com/) | Considered as a more mature open-source alternative to Keyorix for a possible "lightweight secrets management" lab (pre-Vault, no dynamic secrets/PKI needed). Its OSS edition's team/org features sit behind commercial billing, which cuts against this platform's preference for fully open, self-hostable tooling | A fully-open tier covers team/org features, or the gap stops mattering for how the platform would use it |

## Housekeeping

| Work | Effort | Description |
|---|---|---|
| Take-home handouts and PowerPoint decks | M | Parked: `handouts/` (lab handouts, starter repos, deck export script), the `.githooks` pre-commit and the CI `handouts` checks were all deleted because they had drifted from the labs. Recover from git history if wanted again |
| Reconcile the two Zellij branches | S | The Zellij-flavor work is committed twice: `fb4d399` on `feat/zellij-terminal` and `cc189e3` on `feat/zellij-terminal-flavor`, identical patch-id on different bases. Pick the branch that goes forward, delete the other, and make sure whichever lands carries the RELEASES entry (already written) |

## Reference

Settled material the work items above point to. Not work items.

### Student reset decisions

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

**Answered by the user (2026-10-01)**

| ID | Answer |
|---|---|
| Q1 | No "reset and release" for now; it can be a second Roster item later |
| Q3 | Shared DNS zone: use the `<author>-...` record naming Sensei's approve mode already enforces; a reset removes the records named after the student |
| Q4 | Accept code-server's browser UI state (cosmetic) |
| Q5 | Shared org repo: close the student's open PRs and delete their branches; leave comments and merged history alone |
| Q6 | Forgejo re-provision: two API calls from the allocator (no bootstrap image needed mid-class) |
| Q7 | Facilitator only (as R7) |

### Achievements design

**Working notes.** Tests: `cd modules/achievements/service && python3 -B -m unittest test_server test_service`;
catalog: `cd ../catalog && python3 -B -m unittest test_catalog`. Logins: class `student` / `student` (POST form on
`/login`, then enter a name); facilitator `admin` / `admin` locally. Post a test event from inside the service
container (`podman exec workshop_achievements python3 ...`, sign with `guards.sign(GATEWAY_TOKEN, user, event, ts,
nonce)`; a nonce can only be used once).

#### Decisions (all settled; IDs are stable, refer to them in commits)

| ID | Area | Decision |
|---|---|---|
| A0 | Toggle | `ACHIEVEMENTS_ENABLED` in `.env`; off means no module, no toasts, no leaderboard, nothing extra loaded |
| A1 | Toasts | Two student modes over the same routes: *split mode* (today's pages, Chrome split screen still works) and opt-in *workspace mode* (`/workspace`, tabbed like `/admin`, portal button, remembered per browser). Toasts appear in the workspace shell (all tabs); portal, lab reader and slides through a same-origin `<script src>`; VS Code through a small bundled code-server extension; Forgejo through its `custom/header` template. No gateway body rewriting. The terminal gets the unlock echoed in colour. Surfaces we can't wire (OpenBao UI etc.) use queued toasts. The landing page shows score and the last 5-10 unlocks |
| A2 | Engine edits | Everything else lives in `modules/achievements/`, the packs and `workshops/assets/`. The engine gets: (1) `dojo` adds `achievements` to the module list when the toggle is on (about 10 lines) and warns if the workshop has no catalog; (2) `render_extensions.py` + `server.py`: a generic `widgets` manifest key (a same-origin `src` framed on the student's landing page: score, completion %, Workshop-complete banner, last 10 unlocks; fixed-template like cards, no raw HTML), the portal's "Open workspace" button and `/workspace`; (3) `engine/presentation/engine.js`: one script tag so slides show toasts; (4) docs in `engine/README.md` and `workshops/README.md`. **No** engine change expected for the shell hook and colour echo, `dojo-check`, student identity, the Forgejo webhook and toast template, the VS Code extension, or the lab reader |
| A3 | Checking | Students run only a thin `dojo-check N` client (no answers in it). The service holds the catalog and checks with its own credentials on networks students can't reach, so a pass can't be posted by hand. Identity: `dojo-check` sends the student's own Forgejo token and the service asks Forgejo who it is (no new token file, no change to `provision-account.sh`). Verifiers (state, for challenges) and event adapters (activity, for milestones) are shipped by the modules that own a backend (A22) |
| A4 | Points | Defaults, settable in `.env` (so `stop` can read them; never `${VAR:?}` in a fragment): milestone 10, funny 0, challenge 100, capstone 300, first blood +25 (capstone +50), class-clear +10 for everyone once the whole class has cleared a challenge. Each hint costs `ACHIEVEMENTS_HINT_PERCENT` (default 25) of the challenge's points, `floor(points * pct / 100)`; after 2 hints the student may reveal the answer and scores 0 for it (it still counts as completed). Score never drops below 0 from hints. Points are awarded once per unlock. First blood, class-clear and the cheater penalty are each switchable |
| A5 | Kinds | *Milestones* fire when the student does something; *challenges* are goal-only and checked by outcome. **One capstone per workshop**, worth more, with a badge tier |
| A6 | Completion (A15) | Based on milestones tagged `core` only, at `ACHIEVEMENTS_COMPLETION_PERCENT` of them (default 80). **Every lab is mandatory**, so every lab milestone is `core`; challenges, capstone and funny unlocks are bonuses and never count. The student's home page shows a running completion percentage and, at completion, a **Workshop complete** banner. |
| A7 | Cheating (A14) | Each fires once per student, none worth more than -1: hand-posted event -1 ("Nice Try, Hackerman"); edited `dojo-check` (client hash mismatch) -1; another student's identity headers -1 ("Identity Crisis"); button masher (rate limit) 0 but shows; poking another student's space: ladder "Oops, you bumped into your neighbour" (0) -> "Curiosity Killed the Cat" (0) -> a related follow-up worth -1 if they keep at it. Honest mistakes must not trip the penalty tiers (thresholds 1/3/8 strikes). These unlocks are shared across workshops and live with the module |
| A8 | Export | Printable HTML `/certificate` (landscape print CSS, browser "Print to PDF", no PDF library). Page 1 the certificate (display name, workshop, class date, points, rank, facilitator signature line from `.env` or blank); page 2 the achievement summary (every unlock with date, challenges cleared with or without hints, any cheater tiers). The certificate is issued on **completion**, not the capstone; the capstone makes it fancier. Also a **badge PNG** drawn client-side on a `<canvas>` (no Credly branding), one design per workshop, two tiers (completion; capstone with stars). Facilitator can override completion in `/admin` |
| A9 | Board | Whole class shown, no top-N. Toasts are only ever for the student's own unlocks (a class-clear bonus arrives as an ordinary personal toast). Sorted by points, ties by who got there first. Facilitator awards and resets change the score directly and are logged. Facilitator sees everything (`/admin` tab): can award manually, reset scores, see the log of check runs (who, when, pass or fail, hints used) |
| A13 | Queue | An unlock is shown once, on the first toast-capable surface that picks it up; the landing page list is the permanent record. The terminal echo does not count as delivered. More than 5 queued collapse into one toast ("You unlocked 6 achievements") linking to the landing page |
| A16 | Names | Export name flow: a dialog asks what to put on it: their current display name, or a typed name or email (offers the part before the `@`). Real names and emails stay on the student's own pages and downloads, stored only in the module volume (wiped by `stop`), never in `/admin`. **Anonymous board** (`ACHIEVEMENTS_ANONYMOUS`): each student gets a unique funny generated name (WildCrab, SpeedyTurtle) for the run, sees "you" highlighted, others can't tell who is who; the facilitator's `/admin` view shows the real mapping |
| A17 | Catalog format | **Modular data, see below.** Supersedes the earlier single `achievements.json` |
| A18 | Challenge seeding | On demand, per student: a **Start challenge** button in the lab and `dojo-challenge start N` create the student's own challenge repo `{user}/challenge-repo` (student has write access) with seeded commits, branches and per-student values, and clone it into `~/lab`. **Reset** (`dojo-challenge reset N`, also a button) deletes and re-creates it, unlimited times. Hints already used stay counted; points are earned once (only the first clear scores, hints only ever cost) |
| A19 | Sensei bot | Auto-merges the Lab 1 roster PR only (challenge PRs stay the student's own, so bot comments never give hints). Switchable on its own. Reviews each roster PR against catalog rules (allowed files, YAML parses, the student's entry present, nothing else deleted); a good PR is merged through the Forgejo API with a friendly comment, a bad one gets a review comment and is not merged. `/admin` tab lists every PR (auto-merged, waiting, failing and why, minutes stuck) with "merge anyway" and "comment". Stale roster branches are merged with `main` by the bot |
| A20 | **Isolation rules** | Every challenge and capstone: (1) writes only to a space keyed on `{user}`; (2) verifies only that space; (3) depends on no other student (a seeded bot or the facilitator is allowed, only where truly required); (4) changes no shared config (CA lifetime, quota, policy, branch protection, shared zones); (5) has a per-student seed created when opened; (6) is independent of the other challenges (a pass is recorded when checked and never undone by later clean-up). The catalog validator enforces what it can (every challenge declares `space`, every verify assertion is `{user}`-templated, no `peer` dependency unless `facilitator: true`). Full text in `workshops/git-fundamentals/ACHIEVEMENTS.md` |
| A21 | Modular catalog | See "Catalog layout" below |
| A22 | Extension points | Anything that talks to a backend is a **module-owned plug-in**, so a new workshop or module adds achievements without touching the service: verifier verbs, event adapters and seed builders are declared in the owning module's `achievements/` folder |
| A23 | Test approach | Unit tests first for every pure piece (loader, points, queue, names); a live `--test` demo-bot pass per phase; a class-sized concurrency pass (bots doing the same challenge at once, nobody's check affected by anyone else's) before any pack is called done |
| A24 | vault capstone slot | A second app slot per student, `{user}-capstone`, unlocked by `dojo-challenge start capstone`; the lab app keeps running |
| A25 | Challenge repo | One public repo `{user}/challenge-repo` under each student's account for every challenge; only its owner can push |
| A26 | dns-as-code review PR | Sensei only *opens* the `dns-bot` review PR (`SENSEI_SEED`), never approves or merges it |
| A27 | Scope of a score | Individuals only: people may work together, but the lab and the achievements are each student's own |
| A28 | Storage and reset | State lives in a named module volume: it survives restarts within a class and `./dojo stop` removes it. The facilitator's student reset (see [Student reset](#student-reset)) can clear or keep that student's achievements, their choice at reset time |
| A29 | Branching | `feat/achievements` was cut from `feat/front-door` (both front-door and remediation reached `main` in PR #4, 2026-09-29). The student workspace page is built first (phase 1b) because it is useful with achievements off |
| A30 | Funny unlocks and the Moments table | **Funny unlocks are worth 0 points** (`ACHIEVEMENTS_FUNNY_POINTS`, default 0, only the person launching the lab can raise it) so they never help a score; they just call you out. Each student's landing page has its own **Moments** table, shown only once they have unlocked one: title, the joke, what they did to earn it (the catalog's `when`) and when. It is private to that student (not on the leaderboard, not in anyone else's view), appears in the certificate's summary page, and the facilitator's `/admin` view lists a student's moments too. A funny event still toasts (5 s, no points shown). **Cheating still subtracts** (A7: -1 at most). The catalog validator refuses a positive `points` on a funny unlock or a cheat. |

#### Catalog layout (A17/A21)

Goal: edit one achievement, one lab or one challenge later without touching the rest, and without code changes for a
reworded joke, a changed point value or a new milestone.

```text
workshops/<name>/achievements/
  catalog.json          # workshop id, title, badge art, completion percent (optional override), lab order
  labs/lab1.json ...    # one file per lab: its milestones
  funny.json            # workshop-specific funny unlocks
  challenges/c1.json .. # one file per challenge: goal, hints, answer, space, seed, verify
  capstone.json
  seeds/                # files the seed builders copy (repo skeleton, zone file, tf starter)
modules/achievements/catalog/shared.json     # cheating tiers, cross-workshop funny unlocks
modules/<module>/achievements/verifiers.json # verb names, arguments and the check the module implements
modules/<module>/achievements/events.json    # event adapters the module ships (audit streams, webhooks)
```

- **An item** is `{id, title, joke, points?, core?, when, match?}`. `when` is the human text shown in the review
  markdown; `match` is the structured trigger (`{"source":"shell","cmd":"git commit","exit":0}`, or
  `{"source":"forgejo","event":"pull_request","action":"opened"}`). An item with no `match` is listed but never fires,
  and the validator says so as a warning (an error for a pack with `require_match`).
- **`id` is forever.** Never reused or renamed once a class may have earned it; an item is removed by setting
  `"retired": true` (kept for scoring history, hidden from new classes). A student's earned unlocks are keyed by id,
  so editing the catalog mid-class is safe: new ids appear, retired ones keep their points.
- **Points** come from the kind's default (A4) unless the item sets `points`. `core` is only valid on milestones.
- **Validation at start**, like `extensions.json`: unknown fields, duplicate ids, missing goal/hints/answer, a challenge
  without `space` or with an un-templated assertion, an unknown verifier verb (checked against the modules in this run),
  a `match` source no listed module provides. An error stops the run; warnings print.
- **`ACHIEVEMENTS.md` is generated** by `modules/achievements/catalog/render_md.py` from this data, and a unit test
  fails when the committed markdown is stale. Edit the JSON, never the markdown.
- **Reload:** the catalog is read at service start; the facilitator's `/admin` tab has a "Reload catalog" button, so
  a joke or a point change during a class needs no restart and no `stop`.
- `dojo-introduction` is a tour, not a workshop: no achievements.

#### Per-workshop challenge design (isolation applied, 2026-09-29)

Full text is in each `ACHIEVEMENTS.md`.

| Workshop | Where challenges run | Seeds and extras | Facilitator needed? |
|---|---|---|---|
| git-fundamentals | `{user}/challenge-repo`, a seeded fork of `training/sample-training-repo`; merging into its `main` is safe | Per-student fork, planted commits for C2, conflicting branches and a bad commit for the capstone, the linked `{role}`/`{role_typo}` pair and `{target_line}` lists | No |
| dns-as-code | Student's own zone `{user}.dojo.test` and its repo, never `dojo.test` | Doubled-hostname seed (C1), a pushed "good plus bad record" commit (capstone), `10.20.0.{n}` per student, a `dns-bot` PR opened by Sensei for `d3-review` (A26) | No (peer review only in Lab 3, with the `dns-bot` fallback) |
| cert-autorenewal | Student's own vhost dir `/srv/webroot/{user}/` and names under `{user}.certs.dojo.test` (the DNS gate's per-student key already scopes this) | Wildcard A record `*.{user}.certs.dojo.test` to `demo-app`; two extra vhosts made by the student | No |
| tofu-basics | Student's private Dojo Cloud subscription; own folder `~/challenges/cN` with own state; resources tagged `challenge=cN`; every site name has `{user}` (site labels are class-unique) | Starter `main.tf` for C2 (5 names), empty capstone folder, repo `{user}/site-factory`. Capstone is **two** sites (quota is 2 container groups) | No |
| vault-fundamentals | Student's namespace `students/{user}`, database `app_{user}`, own fork and own slot; new role names (`buddy-{user}`, `c2-app`, `capstone-*`) | `buddy-{user}` identity and two secrets, starter `capstone/` folder. The capstone gets a second app slot, `{user}-capstone` (A24) | No |

#### Detection sources

| Source | Catches |
|---|---|
| Forgejo system webhook | push, branch, PR opened or merged, review, tag (with the username) |
| Shell hook (zsh `preexec`/`precmd`) | commands, exit codes, branch, and output through the tmux pane (`out_regex`) |
| Adapters and the `verify` sweep (`openbao-audit`, `cloud-api` events, the CA, Forgejo state) | "the secret exists", "plan is clean", failure unlocks like "First 403" |
| Lab reader page events | opened or finished lab N (weakest source, not used) |

Vault values are HMACed in the audit log, so only path and operation are usable. Challenges check the **outcome**, not
the command. Approximations are written into each item's `when`.

**Test plan (A12).** Unit tests for every pure piece; live `--test` bot runs per pack asserting on the leaderboard
API; a concurrency run (several bots solving the same challenge at once, no one's state changing another's result);
browser screenshots of toasts on every surface, split and workspace modes, the certificate and badge; and, by the
user, a real class or 3-5 person dry run, the tone of the jokes and the printed certificate.
