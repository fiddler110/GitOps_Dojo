# Roadmap

The single list of open work. Finished work moves to [`RELEASES.md`](RELEASES.md). The old per-feature plans
(design, decisions, task logs) are frozen in [`docs/archive/`](docs/archive/); read them for the why, but don't
update them. When you finish an item: delete it here and add a line to RELEASES.md.

Last updated: 2026-09-29 (evening) · Working branch: `feat/achievements` (`feat/remediation` still holds the unmerged remediation work; see Now #1)

| Section | What it holds |
|---|---|
| [Up next](#up-next-achievements-resume-here) | Where the achievements work stands and what to do first |
| [Now](#now) | Merge, plus checks that need a real run |
| [Next](#next) | Student reset; achievements (decisions, catalog layout, phases); remediation leftovers |
| [Manual checks](#manual-checks-the-user-in-a-browser) | Browser passes only the user can do |
| [Later](#later) | Follow-ups and known limits |
| [Housekeeping](#housekeeping) | Repo hygiene |

## Up next (achievements: resume here)

### Sensei as a support desk (built 2026-10-01, unit-tested and smoke-tested over HTTP, nothing live)

`sensei ask|why|hand|inbox|check` ship in every workshop (`sensei` is now in each `MODULES=`); the Sensei tab has a
Raised hands card and a Stuck radar card (needs the scoreboard). Live check, in a browser terminal: `sensei ask "how do
I undo a push"`, break something and run `sensei why` (git push to main, `dnscontrol preview` with a missing dot, a
tofu error from the labs' tables), `sensei hand "..."` then answer it in the tab and read `sensei inbox`; check the
tab's "Their screen" text really is the last screen, the 3-open and 20 s limits, and that nothing under a challenge
heading can be found. Phase 2, also live-unchecked: `sensei check` (done/missing against the real catalog, after a few
bot steps) and the radar (a test user repeating a failing command 5 times shows `failing`; one idle 15 min shows
`quiet`; `SENSEI_STUCK_MINUTES=1` makes `stalled` quick to see), and that `GET /api/sensei/*` answers 403 without the
key from a student terminal. Facilitator-only nudges: Sensei never speaks first at a student's prompt. Not built:
activity survives only in memory (a restart of the achievements service empties the radar until students type again).

### Phase 9 live checks: start here (order matters)

Everything in 9a is unit-tested only. Run one stack at a time (`podman ps` first; ask before `./run.sh stop`, it
wipes volumes). Order goes from smallest blast radius to largest, so a core defect shows up on the cheapest pack.
Each step: start with `--test`, wait for the bots, then compare fired items against the pack's `ACHIEVEMENTS.md`.

Done and in `RELEASES.md`: rebuild, git-fundamentals regression, dns-as-code (2026-10-01, locally). Left over from
dns-as-code, not yet run live (all unit-tested, nothing else needs the stack for it):

- **Run a dns-as-code `--test 3` once more** on the final bot steps (Lab 1 "opposite mistake" for `f-dot2`, `dns_catch_up`
  before each push, Sensei's `conflicts` status and criss-cross rule) and read the bot logs for stray errors.
- **As a student in the browser:** `sensei help|status|review|approve [--force]` (the module's `terminal/` layer is
  in the image, nobody has typed it yet), the Lab 3 text (fresh `git pull` before branching, the DELETE-in-preview
  box), a long output and `clear` through the readback, and `lab-prep 5`.
- **Optional:** bots close their own abandoned PRs (round-1 PRs #5/#6 stayed open with conflicts).

1. **cert-autorenewal (`ca` adapter + `verify` sweep).** Check `ca` events reach `/api/adapter` (order_issued,
   order_failed), `served_changed`/`served_expired` verifiers, and the sweep's first real backend use. Restart the
   service once and note the `c4-installs`/`c4-watch` baseline reset (known). Expect all but `f-ratelimit`, `c2`.
2. **tofu-basics (`cloud` adapter).** `cloud-api` events (portal/site request, policy/quota denied, container
   create/update/delete/replace) reaching the service; credentials/secret wired through compose. Watch the known
   approximations: `site_request` credits the owner, `t8-inplace` fires early, `t9-foreach` reads `extra[...]`.
3. **vault-fundamentals (`bao` adapter, heaviest).** Audit tailer posts (login, request, wrapping) and `repo_secret`.
   Check `role` (first non-default policy) and the 404 guess; `v13-recover` only proves the app answers. `f-paste`
   stays facilitator-awarded.
4. **Class-sized concurrency run (last).** On dns-as-code or git-fundamentals with ~20 bots: shell hook latency,
   state sweep budget (`gap=20`, `budget=40`), no dropped events, `/admin` leaderboard and toasts still responsive.

Log failures per step in this section; when a pack passes, delete its step, move 9a's line to `RELEASES.md`, and
fix the item `when` text for any approximation that proved wrong.

Branch `feat/achievements` (cut from `feat/front-door`), commits unpushed. Last updated 2026-09-29.
Phases 0, 1a, 1b and 2 (2a logic, 2b service, 2c toasts and terminal) are built and verified locally on
git-fundamentals. Details of each are in the phase table below.

**What works today:** catalog and validator, toggle, `/workspace`, the `widgets` and `scripts` manifest keys, the score
service (points, hints, bonuses, cheats, Moments, leaderboard, facilitator tab), toasts on the portal, workspace, slides
and lab reader, the terminal colour echo, `dojo-check status|hint|reveal` with Forgejo-token identity and a client-hash
check. 90 module tests, 88 allocator tests and the catalog tests pass.

**Phase 3 is built for git-fundamentals and was run live (2026-09-30, locally, `--test` bots).** The shell hook,
`POST /api/shell`, the self-registering Forgejo system webhook (`POST /api/forgejo`), the matcher and every
git-fundamentals `match` exist. On the live stack the bots' shell events and real webhook deliveries unlocked 22 of the
29 items with no cheat or stray unlock (see "Phase 3 live checks"). The live run found and fixed two defects: Forgejo
16's `POST /api/v1/admin/hooks` makes a *default* hook, not a system one (now created through the admin web form), and
reviews arrive as `X-Forgejo-Event: pull_request_approved` (now read from `X-Forgejo-Event-Type`). 131 service tests
(19 matcher tests, including recorded Forgejo 16 deliveries), 52 catalog and 16 editor tests pass. Also missing:

| Not done | Why it is open | Phase |
|---|---|---|
| Rest of the phase 3 live checks | Checked by hand 2026-09-30 in a real terminal: `f-wrongdir f-main f-amend f-detached l1-cleanup f-force f-rejected` all fire and toast (`f-rejected` on a real rejected push, exit 1, in Moments with a toast). Still open: the hook with a prompt framework, see "Phase 3 live checks" below | 3 |
| The capstone | c1, c2, `dojo-check ID` and `dojo-challenge start/reset` are built and passed their live test (2026-09-30); the capstone has no seed or verify yet (validator warns) | 4 |
| Certificate, badge PNG, export-name dialog | Not started | 6 |
| Sensei bot and its `/admin` tab | Not started (A19, A26 open) | 7 |
| Other four workshops' `match` items, verifiers and seeds | Catalogs are written; nothing wired | 9 |
| Moments table in the certificate summary and the class-sized concurrency run | Depend on phases 6 and 4 | 6, 9 |

**Phase 4 live test: done** (2026-09-30, locally, two students, all checks passed, see the phase table). The
capstone and the lab-page Start/Reset buttons are done too (see the row). Earlier note, kept for context: **phase 4 for git-fundamentals** (the phase 3 live test, step 4, is done except the manual zsh check). Reason: it is the one pack whose catalog is
fully drafted, and it makes the whole thing demonstrable end to end (do Lab 1 in the terminal, watch toasts and the
board move) before any other workshop is touched. Suggested order:

1. **Shell hook (built).** In `modules/achievements/terminal/`, add a zsh `preexec`/`precmd` hook that records each command,
   its exit code and the current branch, and sends it (through `dojo-check`, so it carries the Forgejo token and client
   hash) to a new `POST /api/shell` on the service. Keep it non-blocking and rate-limited (the masher cheat exists).
2. **Forgejo webhook (built).** A system webhook to the service for push, branch, PR opened and merged, review and tag, with
   the username. The service must verify the webhook (shared secret) since the lab network can reach it.
3. **Matching (built).** Turn each git-fundamentals item's `match` from empty into a structured trigger, add the matcher to
   the service (source `shell` or `forgejo`, plus fields), and make the validator refuse an empty `match` for a
   workshop that opts in. Unit-test the matcher against recorded event sequences before any live run.
4. **Live test with `--test` bots:** the bots run the labs, so assert on the leaderboard API that their milestones
   unlock and the funny ones fire. Then phase 4 (verifier runner, `dojo-challenge start/reset`, first two challenges).

**Phase 3 live checks (what the unit tests could not prove)**
- Verified live (2026-09-30, locally, git-fundamentals `--test`): the service registers a real *system* hook
  (`is_system_webhook=1`, one hook after restarts) and `ALLOWED_HOST_LIST=achievements` lets it deliver (no need for
  `private`). Real payloads match the matcher: `pusher.login`, `ref`/`ref_type`, `pull_request.user.login`,
  `base.ref`, `action: closed` + `merged: true`; recorded in `service/testdata/forgejo16-deliveries.json`. A review
  is `X-Forgejo-Event: pull_request_approved` / `-Type: pull_request_review_approved` (fixed). Deliveries for the
  admin (seed push, reviews) score nothing, as intended.
- Verified live: the bots' `bot.d` hook makes each bot a `dojo-git` token and its commands reach `/api/shell`; the
  facilitator's `/achievements-admin/api/state` through the gateway showed the bots' milestones, 0 cheats, 0 forged.
- Fired on the live run: `l1-clone l1-branch l1-diff l1-commit l1-push l1-pr l1-merged l1-prune l2-restore
  l2-unstage l2-ignore l3-stash l3-pop l4-log l4-show l4-blame l4-compare l5-conflict l5-resolved l5-revert l5-reset
  f-nothing` (the bots' deliberate forgotten `git add`). `l1-merged` needed a facilitator merge (done by API; most bot
  PRs conflict on the roster). Not fired, because the bots never do it: `l1-cleanup` (bots delete with `-D`),
  `f-wrongdir`, `f-main`, `f-detached`, `f-amend`, `f-force`, `f-rejected` (the bots' failing `git push` exits 128,
  not 1). Checked by hand afterwards (2026-09-30, `student01` in the browser terminal): all seven fire, with toasts
  and Moments rows. The bots' 128 was the missing push destination, not a rejection.
- Still unchecked: the zsh hook in the real terminal image through ttyd/tmux (tested only in a plain zsh with a fake
  `dojo-check`), and with a prompt framework. Bot quirk seen: round 1's `git reset --hard HEAD~1` fails with
  "unknown revision" in `bot-runner.sh` (engine; round 2 succeeded).
- Matches that are approximations: `l1-diff` fires on any `git diff`/`git status` in a repo (no "after an edit");
  `f-nothing` is `git commit` exit 1 (also an aborted editor); `f-rejected` is `git push` exit 1 (no output is seen);
  `f-wrongdir` is a git command exit 128 outside a work tree; `l2-ignore` needs a shell redirect or `git add .gitignore`
  (an edit in VS Code alone doesn't fire); `git log -1` in Lab 1 already unlocks `l4-log`.

- **Known limits of the shell hook (accepted for now):** a command is matched on the line as typed, and the exit code
  is the last command's. So a line of chained commands (`a; git push; echo $?`, or a pasted lab block on one line)
  is matched on its first word and reports only the last exit code: `git push` inside a chain can miss `f-rejected`,
  `f-nothing` and any other exit-code match. Pasted multi-line blocks run line by line and are fine. Also: the hook
  sends the text of every command to the service (kept nowhere, only matched), and a student can post their own
  shell events by hand, which earns only what typing the command would. Fix if it matters: split chains on
  `;`, `&&` and `||` in the matcher and treat the exit code as unknown for all but the last part.

**Decisions waiting on you:** A25 is decided (`{user}/challenge-repo` under each student's account, one repo for
every challenge; built that way in phase 4). A26 (does Sensei seed the `dns-bot` PR) before phase 7. A24 is only needed in phase 9.

**How to pick this up tomorrow**
- The stack is probably still up on `localhost:8080` (git-fundamentals with achievements on, `student01` holding test
  data). To restart cleanly: `./run.sh stop`, then `ACHIEVEMENTS_ENABLED=1 ./run.sh git-fundamentals` (about 90 s; run it
  in the background and watch the log). Set `ACHIEVEMENTS_ENABLED=1` in `engine/.env` to stop typing it.
- Tests: `cd modules/achievements/service && python3 -B -m unittest test_server test_service`; catalog:
  `cd ../catalog && python3 -B -m unittest test_catalog`; engine: `cd engine/allocator && python3 -B -m unittest discover -s tests`.
- Logins: class `student` / `student` (POST form on `/login`, then enter a name); facilitator `admin` / `admin`.
  Post a test event from inside the service container (`podman exec workshop_achievements python3 ...`, sign with
  `guards.sign(GATEWAY_TOKEN, user, event, ts, nonce)`; a nonce can only be used once). Browser checks use the
  Playwright image from CLAUDE.md with `--network host`.
- Known quirks: a signed event whose user doesn't exist burns its nonce; `lab0.md.txt` 404s in the lab reader (it
  probes for a Lab 0 git-fundamentals doesn't have; harmless); the widget only resizes once `toast.js` has loaded.
- Commits so far on the branch: `33fd04a` roadmap and design, `1571477` catalog core, `b85e154` workspace and toggle,
  `033e812` funny 0 points, `24fd11a` pure logic, `c0f7945` service, `e4018ca` engine `scripts` key, `19abadb` toasts,
  terminal and identity. Ask before pushing or merging.

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

### Achievements (leaderboard, pop-ups, challenges, certificate)

Status: **design decided and the five catalogs reviewed and accepted (2026-09-29); building starts at phase 1.** Branch
`feat/achievements`. Catalogs: `workshops/<name>/ACHIEVEMENTS.md` (review copies, to be generated from data, see A21).
Rule: **ask before editing any `engine/` file**. The engine edits in A2 are approved in principle; still tell the user
before each phase touches them.

Idea: an optional layer over the labs. When a student does something (pushes code, creates a secret), a small
"achievement unlocked" toast appears on whatever student page is open, and points land on a class leaderboard. Each lab
ends with a **challenge** that gives a goal and no steps. At the end a student can export a summary and a certificate.

#### Decisions (all settled; IDs are stable, refer to them in commits)

| ID | Area | Decision |
|---|---|---|
| A0 | Toggle | `ACHIEVEMENTS_ENABLED` in `.env`; off means no module, no toasts, no leaderboard, nothing extra loaded |
| A1 | Toasts | Two student modes over the same routes: *split mode* (today's pages, Chrome split screen still works) and opt-in *workspace mode* (`/workspace`, tabbed like `/admin`, portal button, remembered per browser). Toasts appear in the workspace shell (all tabs); portal, lab reader and slides through a same-origin `<script src>`; VS Code through a small bundled code-server extension; Forgejo through its `custom/header` template. No gateway body rewriting. The terminal gets the unlock echoed in colour. Surfaces we can't wire (OpenBao UI etc.) use queued toasts. The landing page shows score and the last 5-10 unlocks |
| A2 | Engine edits | Everything else lives in `modules/achievements/`, the packs and `workshops/assets/`. The engine gets: (1) `engine/run.sh` adds `achievements` to the module list when the toggle is on (about 10 lines) and warns if the workshop has no catalog; (2) `render_extensions.py` + `server.py`: a generic `widgets` manifest key (a same-origin `src` framed on the student's landing page: score, completion %, Workshop-complete banner, last 10 unlocks; fixed-template like cards, no raw HTML), the portal's "Open workspace" button and `/workspace`; (3) `engine/presentation/engine.js`: one script tag so slides show toasts; (4) docs in `engine/README.md` and `workshops/README.md`. **No** engine change expected for the shell hook and colour echo, `dojo-check`, student identity, the Forgejo webhook and toast template, the VS Code extension, or the lab reader |
| A3 | Checking | Students run only a thin `dojo-check N` client (no answers in it). The service holds the catalog and checks with its own credentials on networks students can't reach, so a pass can't be posted by hand. Identity: `dojo-check` sends the student's own Forgejo token and the service asks Forgejo who it is (no new token file, no change to `provision-account.sh`). Verifiers (state, for challenges) and event adapters (activity, for milestones) are shipped by the modules that own a backend (A22) |
| A4 | Points | Defaults, settable in `engine/.env` (so `stop` can read them; never `${VAR:?}` in a fragment): milestone 10, funny 0, challenge 100, capstone 300, first blood +25 (capstone +50), class-clear +10 for everyone once the whole class has cleared a challenge. Each hint costs `ACHIEVEMENTS_HINT_PERCENT` (default 25) of the challenge's points, `floor(points * pct / 100)`; after 2 hints the student may reveal the answer and scores 0 for it (it still counts as completed). Score never drops below 0 from hints. Points are awarded once per unlock. First blood, class-clear and the cheater penalty are each switchable |
| A5 | Kinds | *Milestones* fire when the student does something; *challenges* are goal-only and checked by outcome. **One capstone per workshop**, worth more, with a badge tier |
| A6 | Completion (A15) | Based on milestones tagged `core` only, at `ACHIEVEMENTS_COMPLETION_PERCENT` of them (default 80). **Every lab is mandatory**, so every lab milestone is `core`; challenges, capstone and funny unlocks are bonuses and never count. The student's home page shows a running completion percentage and, at completion, a **Workshop complete** banner. |
| A7 | Cheating (A14) | Each fires once per student, none worth more than -1: hand-posted event -1 ("Nice Try, Hackerman"); edited `dojo-check` (client hash mismatch) -1; another student's identity headers -1 ("Identity Crisis"); button masher (rate limit) 0 but shows; poking another student's space: ladder "Oops, you bumped into your neighbour" (0) -> "Curiosity Killed the Cat" (0) -> a related follow-up worth -1 if they keep at it. Honest mistakes must not trip the penalty tiers (thresholds set at build). These unlocks are shared across workshops and live with the module |
| A8 | Export | Printable HTML `/certificate` (landscape print CSS, browser "Print to PDF", no PDF library). Page 1 the certificate (display name, workshop, class date, points, rank, facilitator signature line from `.env` or blank); page 2 the achievement summary (every unlock with date, challenges cleared with or without hints, any cheater tiers). The certificate is issued on **completion**, not the capstone; the capstone makes it fancier. Also a **badge PNG** drawn client-side on a `<canvas>` (no Credly branding), one design per workshop, two tiers (completion; capstone with stars). Facilitator can override completion in `/admin` |
| A9 | Board | Whole class shown, no top-N. Toasts are only ever for the student's own unlocks (a class-clear bonus arrives as an ordinary personal toast). Sorted by points, ties by who got there first. Facilitator awards and resets change the score directly and are logged. Facilitator sees everything (`/admin` tab): can award manually, reset scores, see the log of check runs (who, when, pass or fail, hints used) |
| A13 | Queue | An unlock is shown once, on the first toast-capable surface that picks it up; the landing page list is the permanent record. The terminal echo does not count as delivered. More than 5 queued collapse into one toast ("You unlocked 6 achievements") linking to the landing page |
| A16 | Names | Export name flow: a dialog asks what to put on it: their current display name, or a typed name or email (offers the part before the `@`). Real names and emails stay on the student's own pages and downloads, stored only in the module volume (wiped by `stop`), never in `/admin`. **Anonymous board** (`ACHIEVEMENTS_ANONYMOUS`): each student gets a unique funny generated name (WildCrab, SpeedyTurtle) for the run, sees "you" highlighted, others can't tell who is who; the facilitator's `/admin` view shows the real mapping |
| A17 | Catalog format | **Modular data, see below.** Supersedes the earlier single `achievements.json` |
| A18 | Challenge seeding | On demand, per student: a **Start challenge** button in the lab and `dojo-challenge start N` create the student's own challenge repo `{user}/challenge-repo` (student has write access) with seeded commits, branches and per-student values, and clone it into `~/lab`. **Reset** (`dojo-challenge reset N`, also a button) deletes and re-creates it, unlimited times. Hints already used stay counted; points are earned once (only the first clear scores, hints only ever cost) |
| A19 | Sensei bot | Auto-merges the Lab 1 roster PR only (challenge PRs stay the student's own, so bot comments never give hints). Switchable on its own. Reviews each roster PR against catalog rules (allowed files, YAML parses, the student's entry present, nothing else deleted); a good PR is merged through the Forgejo API with a friendly comment, a bad one gets a review comment and is not merged. `/admin` tab lists every PR (auto-merged, waiting, failing and why, minutes stuck) with "merge anyway" and "comment". **Check first:** PRs that all append to `roster/team.yaml` conflict, so the bot must handle a stale branch (update-branch call, or a comment telling the student to update) |
| A20 | **Isolation rules** | Every challenge and capstone: (1) writes only to a space keyed on `{user}`; (2) verifies only that space; (3) depends on no other student (a seeded bot or the facilitator is allowed, only where truly required); (4) changes no shared config (CA lifetime, quota, policy, branch protection, shared zones); (5) has a per-student seed created when opened; (6) is independent of the other challenges (a pass is recorded when checked and never undone by later clean-up). The catalog validator enforces what it can (every challenge declares `space`, every verify assertion is `{user}`-templated, no `peer` dependency unless `facilitator: true`). Full text in `workshops/git-fundamentals/ACHIEVEMENTS.md` |
| A21 | Modular catalog | See "Catalog layout" below |
| A22 | Extension points | Anything that talks to a backend is a **module-owned plug-in**, so a new workshop or module adds achievements without touching the service: verifier verbs, event adapters and seed builders are declared in the owning module's `achievements/` folder |
| A23 | Test approach | Unit tests first for every pure piece (loader, points, queue, names); a live `--test` demo-bot pass per phase; a class-sized concurrency pass (bots doing the same challenge at once, nobody's check affected by anyone else's) before any pack is called done |
| A27 | Scope of a score | Individuals only: people may work together, but the lab and the achievements are each student's own |
| A28 | Storage and reset | State lives in a named module volume: it survives restarts within a class and `./run.sh stop` removes it. The facilitator's student reset (see Student reset above) can clear or keep that student's achievements, their choice at reset time |
| A29 | Branching | `feat/achievements` was cut from `feat/front-door` (main lacks the front-door and remediation work this builds on). The student workspace page is built first (phase 1b) because it is useful with achievements off |
| A30 | Funny unlocks and the Moments table | **Funny unlocks are worth 0 points** (`ACHIEVEMENTS_FUNNY_POINTS`, default 0, only the person launching the lab can raise it) so they never help a score; they just call you out. Each student's landing page has its own **Moments** table, shown only once they have unlocked one: title, the joke, what they did to earn it (the catalog's `when`) and when. It is private to that student (not on the leaderboard, not in anyone else's view), appears in the certificate's summary page, and the facilitator's `/admin` view lists a student's moments too. A funny event still toasts (5 s, no points shown). **Cheating still subtracts** (A7: -1 at most). The catalog validator refuses a positive `points` on a funny unlock or a cheat. |

#### Catalog layout (A17/A21, decided)

Goal: edit one achievement, one lab or one challenge later without touching the rest, and without code changes for a
reworded joke, a changed point value or a new milestone.

```
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
  `{"source":"forgejo","event":"pull_request","action":"opened"}`) and may be empty until that pack's event source is
  built (phase 3+). An item with no `match` is listed but never fires, and the validator says so as a warning.
- **`id` is forever.** Never reused or renamed once a class may have earned it; an item is removed by setting
  `"retired": true` (kept for scoring history, hidden from new classes). A student's earned unlocks are keyed by id,
  so editing the catalog mid-class is safe: new ids appear, retired ones keep their points.
- **Points** come from the kind's default (A4) unless the item sets `points`. `core` is only valid on milestones.
- **Validation at start**, like `extensions.json`: unknown fields, duplicate ids, missing goal/hints/answer, a challenge
  without `space` or with an un-templated assertion, an unknown verifier verb (checked against the modules in this run),
  a `match` source no listed module provides. An error stops the run; warnings print.
- **`ACHIEVEMENTS.md` is generated** by `modules/achievements/catalog/render_md.py` from this data (same tables as the
  reviewed drafts), and a unit test fails when the committed markdown is stale. The five accepted markdown drafts
  are converted once by a script into this layout (text into `when`, `match` left empty), then only the JSON is edited.
- **Reload:** the catalog is read at service start; the facilitator's `/admin` tab has a "Reload catalog" button, so
  a joke or a point change during a class needs no restart and no `stop`.
- `dojo-introduction` is a tour, not a workshop: no achievements.

#### Per-workshop challenge design (isolation applied, 2026-09-29)

Full text is in each `ACHIEVEMENTS.md`. What each pack needs built (seeds and verifiers), later phases:

| Workshop | Where challenges run | Seeds and extras to build | Facilitator needed? |
|---|---|---|---|
| git-fundamentals | `{user}/challenge-repo`, a seeded fork of `training/sample-training-repo`; merging into its `main` is safe | Per-student fork, planted commits for C2, conflicting branches and a bad commit for the capstone, the linked `{role}`/`{role_typo}` pair and `{target_line}` lists | No |
| dns-as-code | Student's own zone `{user}.dojo.test` and its repo, never `dojo.test` | Doubled-hostname seed (C1), a pushed "good plus bad record" commit (capstone), `10.20.0.{n}` per student, a `dns-bot` PR opened by setup for `d3-review` | No (peer review only in Lab 3, with the `dns-bot` fallback) |
| cert-autorenewal | Student's own vhost dir `/srv/webroot/{user}/` and names under `{user}.certs.dojo.test` (the DNS gate's per-student key already scopes this) | Wildcard A record `*.{user}.certs.dojo.test` to `demo-app`; two extra vhosts made by the student | No |
| tofu-basics | Student's private Dojo Cloud subscription; own folder `~/challenges/cN` with own state; resources tagged `challenge=cN`; every site name has `{user}` (site labels are class-unique) | Starter `main.tf` for C2 (5 names), empty capstone folder, repo `{user}/site-factory`. Capstone is **two** sites (quota is 2 container groups) | No |
| vault-fundamentals | Student's namespace `students/{user}`, database `app_{user}`, own fork and own slot; new role names (`buddy-{user}`, `c2-app`, `capstone-*`) | `buddy-{user}` identity and two secrets, starter `capstone/` folder. The capstone reuses the student's one slot (replaces the lab app); a second slot per student would be a new `app-host` feature | No |

#### Phases (each testable and committed on its own)

Status: `todo`, `doing`, `done`. Do them in order; the numbers are stable.

| # | Phase | Scope | Status |
|---|---|---|---|
| 0 | Design and catalogs | Design (A0-A23), five catalogs drafted, reviewed, isolation rules applied, committed | done |
| 1a | Catalog core (no engine) | `modules/achievements/catalog/`: schema, loader, validator, `render_md.py`, the conversion script, unit tests. The five accepted drafts are converted into `workshops/<name>/achievements/` (175 milestone and funny ids preserved, 35 unit tests); `ACHIEVEMENTS.md` is now generated, edit the JSON | done |
| 1b | Engine: workspace and widgets | `widgets` manifest key, `/workspace` page, portal "Open workspace" button, `run.sh` toggle and catalog warning, docs. Useful with achievements off. Built 2026-09-30 (engine edits approved by the user): `render_extensions.py` `widgets` key and reserved `/workspace`, `server.py` `/workspace` page with its assets and the landing "Open workspace" card, `run.sh` `ACHIEVEMENTS_ENABLED` toggle with catalog validation (`modules/achievements/catalog/validate.py`), `.env.example`, both READMEs; 81 allocator unit tests pass. Live on git-fundamentals (locally): HTTP and redirects, the five tabs with lazy iframes, remembered workspace and split mode (also with blocked storage), no CSP violations on first load, the 600 px stacked layout and `/admin` all pass. Not exercised: a real `widgets` entry (arrives with phase 2's landing widget) | done |
| 2 | Module core | Service (stdlib Python on the allocator image, like `openbao-audit`), named volume, event API, identity from the Forgejo token, points and hint math, queue, anonymous names, leaderboard page, `/admin` tab (log, award, reset, reload catalog), landing widget with completion % and the private Moments table (A30), toast script for portal, workspace and lab reader. **2a done (pure logic, `modules/achievements/service/`: `ledger.py` points, hints, bonuses, cheats, Moments, toast queue, leaderboard; `names.py`; `guards.py` event signing and rate limit; 50 unit tests; every unlock kind toasts, funny and cheats included).** **2b done (2026-09-29, locally):** `service/server.py` and `store.py` (module `compose.yml`, `extensions.json` with card, `/admin` tab, `widgets` entry and two routes, named volume `achievements_data`, persisted state), signed event API, hint/reveal API, `/api/me`, leaderboard page, landing widget with Moments, facilitator tab (award, reset, reload catalog), `toast.js`; 76 module unit tests; live on git-fundamentals through the gateway: identity, widget, moments, toasts, board, admin tab, forged events charged only to an identified caller. **2c done (2026-09-29, locally, engine edits approved):** the generic `scripts` manifest key (A31) and its loader `/workspace/extra.js`, included by the landing page, `/workspace`, slides (`engine.js`) and the lab reader; toasts verified on the portal, workspace shell, a slide page and the lab reader (a framed page leaves them to the top page, and the widget frame resizes to its content); the terminal colour echo (`dojo-check --echo` from a prompt hook, once per unlock, never marks it delivered); `dojo-check` (status, hint, reveal) authenticated by the student's own Forgejo token confirmed with Forgejo, with a client-hash check (edited client -1, someone else's identity headers -1); the point and switch variables in `engine/.env.example`. Still to do in later phases: toasts in VS Code and Forgejo, `dojo-check ID` verifiers | in progress |
| 3 | Event sources | Shell hook (zsh `preexec`/`precmd` in the module's terminal image, exit codes and branch logged; the colour echo is already built in 2c), Forgejo webhook; git-fundamentals milestones and funny unlocks get their `match`. **Built 2026-09-30, run live the same day (locally, `--test` bots; 22 of 29 items fired, see Up next):** `terminal/dojo-achievements.zsh` + `dojo-check --shell` -> `POST /api/shell` (token + client hash, 40/10 s burst limit without the masher); `service/webhook.py` (HMAC check, self-registration as a system hook through the admin web form, allow-list in `compose.yml`) -> `POST /api/forgejo`; `service/matcher.py` (shell segments, flags, regex, exit, branch and merge state; Forgejo normalisation crediting pusher, PR author, reviewer); the `match` schema check in `catalog.py`, `require_match` opt-in (git-fundamentals on, cheats marked `{"source": "service"}`); all 29 git-fundamentals items matched. Left: the zsh hook in a real browser terminal and the 7 items the bots never trigger (manual) | doing |
| 4 | Challenges | `dojo-check`, `dojo-challenge start/reset`, verifier runner, seed builders, hints and forfeit, first blood, class-clear. **Built for git-fundamentals c1 and c2 (2026-09-30), unit-tested, and run live the same day (locally, real Forgejo, two students, no bots, 37 of 37 scripted checks passed, no fixes needed):** start creates a public student-owned `{user}/challenge-repo` with 7 seed commits cloned into `~/lab`, own role misspelled; a wrong PR fails for free; a hint takes 25; the right PR pays 75 + 25 first blood; reset re-creates the repo (admin delete) while the pass, points and hint count stay, and a second check scores nothing; c2 wrong hash fails, the right one pays 100 + 25; student02 clears c1 on its own seed through a merged PR (+100, class-clear +10 to both); a token with another student's X-Auth-User is answered as the token's owner, a check without the client hash gets 403, a bare X-Auth-User without the gateway token is refused, and a student can't push into a classmate's repo; `/achievements-admin/api/state` lists every check run with hints and points. Built: `modules/achievements/achievements/verifiers.json` + `forgejo.py` (8 Forgejo/git verbs: `repo_exists`, `branch_exists`, `pr_exists`, `pr_files`, `pr_file_contains`, `file_contains`, `no_direct_push`, `answer_names_commit`; seed builder `forgejo-repo`), `service/challenges.py` (plug-in loader, `{user}`/per-student value templating, isolation guard: every `repo` must be `{user}/...`), `store.check` / `store.challenge_space` (I/O outside the lock, pass recorded once, wrong answer free, Forgejo down = 503, check log in the `/admin` tab), `POST /api/check` and `POST /api/challenge`, `dojo-check ID` and `dojo-challenge start/reset ID` (a symlink to `dojo-check`, clones into `~/lab/challenge-repo`), catalog `seed_plan` field with validation, seed plan `workshops/git-fundamentals/achievements/seeds/challenge-repo.json` (**A25 decided:** one public repo `{user}/challenge-repo` under each student's account for every challenge; public so classmates and the facilitator can look, only its owner can push). **c1 design (decided):** the roster lists the student as `name: {user}` with their own role misspelled; the fix restores the right spelling. `role` and `role_typo` are a per-student pair (seed plan `linked`, validated by the catalog), and the check wants the right role on the student's entry and the typo gone, all `{user}`-templated (A20). 33 tests in `service/test_challenges.py` against `service/fake_forgejo.py` (isolation, idempotent start, reset x3, wrong answers, hint then pass, reveal, pass survives reset, class-clear with concurrent checks). Confirmed on real Forgejo: first contents-API commit into an empty repo, `git/commits/{sha}.diff`, `dates` (the culprit commit is 14 days old), admin delete. Note: class-clear counts the students the service has seen, so an idle seat never blocks it. **Capstone "The Great Merge" (built and run live 2026-09-30, locally, real Forgejo, 17 of 17 scripted checks):** the same seed plan now adds `CHANGELOG.md` on `main`, `feature-a` and `feature-b` each appending a per-student line (`feature_a`/`feature_b` values) to its end, and a "Make deploys faster" commit on `feature-b` that sets `timeout_seconds: 0`; verify = merged PR into `main` (any head: `pr_exists` `head` is now optional), both lines on `main`, no conflict-marker line, new verb `commit_reverted` (the bad commit is in `main`'s history and a later commit reverts it, by git's "This reverts commit <sha>" or its `Revert "..."` subject), `timeout_seconds: 30` back, `no_direct_push`. Live: reset builds the branches, a feature-a-only merge fails for free naming `CHANGELOG.md`, conflict + resolve + `git revert` + PR merge passes for 300, reset re-creates the repo with the pass and points kept and a second check scores nothing. 10 new unit tests (wrong answers: unmerged, markers, one line, no revert, hand edit instead of revert, bad commit dropped, direct push, a neighbour's lines; c1/c2 still pass after it), catalog and editor tests, validator 0 warnings. **Lab-page buttons (built):** a `<!-- dojo-challenge: ID -->` line in a lab (end of lab1 c1, lab4 c2, lab5 capstone) becomes a Start/Reset box in the lab reader for a student when `/achievements/api/me` lists that challenge, nothing otherwise Capstone built and run live (17 of 17 checks, 2026-09-30, locally); the lab-page buttons passed a Playwright run (button, Start 200, Reset 200 "Rebuilt", nothing when achievements is off or no marker). Still open: the wider class-sized concurrency run (phase 9), and the capstone and challenges for the other four workshops | done |
| 5 | Cheat tiers and names | A7 ladder, anonymous names, negative scores in red. **Decided 2026-09-30:** "poking a neighbour" is detected from all three sources: shell commands naming another student (matched from the shell hook against the class seat names), Forgejo writes against another student's repo (webhook/API, only what Forgejo lets through), and repeated 403s at the service on another student's challenge space. Thresholds count per student over the whole class and never reset: 1 strike = "bumped" (0), 3 = "curious" (0), 8 = "persistent" (-1). Honest slips must stay at the 0-point tiers. Model split: Opus for the detectors and ledger, Sonnet for text and docs. **Built 2026-09-30, unit-tested only (6 new tests in `test_server.PokingTests`, 178 service tests pass; not run live yet):** `Store._strike` keeps a per-student `strikes` count in the ledger state (survives restart) and unlocks `cheat-bump`/`cheat-curious`/`cheat-persistent` at 1/3/8 (`STRIKE_TIERS`); three detectors: a shell command naming another *registered* student as a whole word (`name_in`, one strike per command; idle seats the service has not seen are not caught), a Forgejo event whose repo owner is another student (the facilitator is exempt), and `Store.probe` on `/api/check` and `/api/challenge` (a hand-made body with `user`/`repo`/`space` naming a neighbour gets 403; `dojo-check` never sends those). Negative scores are red on the widget, board and `/admin` (`.neg`). **Run live 2026-10-01 (locally, git-fundamentals `--test`, `student01` pokes `student02`, all passed, no fixes needed):** a shell `ls /home/student02` gave `cheat-bump` (+0); a fork PR into `student02/challenge-repo` (a Forgejo issue is not a subscribed event, so no strike) made strike 2; one hand-made `/api/check` body naming `student02` got 403 and strike 3 = `cheat-curious`; seven more 403s reached 10 strikes and `cheat-persistent` (score 20 to 19). `student02` stayed at 0 strikes and no cheats; the three bots (`testuser1-3`, 12 min, 36 unlocks between them) had 0 strikes and 0 cheats. Not checked: the red negative score in a browser (nobody went below 0) | done |
| 6 | Certificate | `/certificate`, badge PNG, export name dialog. **Built 2026-09-30, unit-tested only (180 service tests; no browser look yet):** `GET /achievements/certificate` (page 1 the certificate, page 2 the summary with unlocks, hints used, Moments and cheat tiers; landscape print CSS), `GET api/certificate` (`Store.certificate`, no name in it), the name dialog (board name or a typed name/email with the part before `@` offered; kept in this browser's localStorage only, never sent), `badge.js` canvas badge (hue from the workshop name, capstone tier adds a ring colour and stars) with a PNG download, signature and date from `ACHIEVEMENTS_SIGNATURE` / `ACHIEVEMENTS_CLASS_DATE` (in `compose.yml`; **not yet in `engine/.env.example`, needs your OK**), the facilitator override (`/admin` Mark complete / Undo complete, logged), and an "Open it" link in the completion banner. **Live 2026-10-01 (locally, Playwright):** student02 marked complete by the facilitator, certificate and summary table render with real unlocks, print gives 2 pages. Not looked at: the badge PNG download, the capstone badge tier, a typed name | done |
| 7 | Sensei | Auto-merge bot and its `/admin` PR tab (A19). **Built 2026-09-30 as its own module `modules/sensei` (git-fundamentals lists it in `MODULES=`), unit-tested only (19 tests, real `git` against a fake Forgejo; `--dry-run` passes):** `roster.py` review rules, `bot.py` (5 s poll of open PRs into `main`; bad PR = one comment, no merge; good PR merged by API; stale branch = real `git merge main` pushed to the student's branch, roster conflict resolved by keeping `main`'s file and appending their entry, so their commit stays in history), `server.py` + `/admin` Sensei tab (statuses, minutes stuck, Merge anyway, Comment, Look now, Pause), own `Dockerfile` (allocator + git), acts as the Forgejo admin account. **Decided:** one bot service with per-workshop rules (A26 decided: Sensei only *opens* the dns-as-code review PR, never approves or merges it: `modules/sensei/seed.py`, config `SENSEI_SEED` in dns-as-code's `workshop.env`, unit-tested; lab 3 names it). A PR that does not match is commented on and flagged for the facilitator (`needs-review`, first in the tab); lab 1 text now names Sensei. **Live 2026-10-01 (git-fundamentals `--test`):** all 25 bot roster PRs (several stale) passed the format check and were auto-merged; a malformed PR got `needs-review` with the line-1 reason. Not run: a real student's stale-branch PR, the dns-as-code seed; `l1-merged` is now core (the bot-merge workaround is gone) | done |
| 8 | Toast surfaces | VS Code extension and Forgejo template (the slides, lab reader, portal and workspace surfaces were built in 2c through the `scripts` key). **Built 2026-09-30, not run live:** `modules/achievements/terminal/vscode/` (plain-JS extension polling `/api/toasts?surface=vscode` with the student's own Forgejo token, packed as a .vsix and installed by the terminal Dockerfile; `node --check` and the pack step verified, the image build not) and `forgejo/header.tmpl` (loads `toast.js`, mounted read-only into `git-server` by the module compose; untested: whether Forgejo's start-up chown tolerates the nested mount, whether `/data/gitea/templates/custom/` is the custom path). **Run live 2026-10-01 (locally, Playwright, only that one surface open per run, since the first tab to poll takes the toast):** a `git stash` unlock showed "Hide the Evidence +10" as a VS Code notification, and a `git log` unlock showed "Historian +10" as a toast on a Forgejo repo page. The image build, the `.vsix` install (`gitopsdojo.dojo-achievements-1.0.0` is in `/opt/code-server-extensions`), the `custom/header.tmpl` path and the nested mount all work, no fixes needed. Not checked: a negative (red) toast in VS Code | done |
| 9 | Other packs, one at a time | dns-as-code, cert-autorenewal, tofu-basics, vault-fundamentals: add `match` to each item, ship the module's verifiers and event adapters and the seeds above, then live-test (`--test` bots plus a concurrency run) | todo |
| 9a | Phase 9 build (2026-10-01, unit-tested only, nothing live) | Core: generic `cloud`/`bao`/`ca` adapter events (`/api/adapter`), `verify` state milestones (service sweep every `ACHIEVEMENTS_STATE_SECONDS`), `requires_not`, Forgejo `fork`, shell `out_regex` (the zsh hook reads each command's output from the tmux pane), and the validator now checks verb names inside the container. Producers: `cloud-api` `events.py`, `openbao-audit` `events.py`. New verbs: certs `served_changed`/`served_expired`, `plugins/secrets` `repo_secret`. Matched: dns-as-code 29/29 (0 warnings), tofu-basics all, vault-fundamentals all but `f-paste` (facilitator awards it), cert-autorenewal all but `f-ratelimit` (step-ca has no rate limit) plus the `c2` challenge has no verify. **Live check todo (git-fundamentals and dns-as-code done 2026-10-01):** each pack's `--test` bot run asserting its items fire, the tmux output capture in the real terminal image, `cloud`/`bao` events reaching the service, the state sweep against real backends, and a class-sized concurrency run. Approximations are in each item's `when` | built, live check todo |
| 10 | Sweep | Overflow screenshots, re-check lab time totals (git-fundamentals about 55 min, dns-as-code about 92, cert-autorenewal about 75) | todo |

**Mandatory labs (decided and swept 2026-09-29 in git-fundamentals, dns-as-code, cert-autorenewal, vault-fundamentals).**
No lab is optional in any workshop; the "Required?" columns and "optional" wording are gone from lab intros, READMEs,
`slides/labs.md`, `slides/presentation.md` and `lab-index.md`. Left alone on purpose: step-level optional sections,
`tofu-basics` (Track A / Track B: both mandatory for achievements, but its optional end of lab 8 is a facilitator
choice) and `git-fundamentals/delivery-azure-devops/` (a different course). Still to do is phase 10.

**Detection sources (for phase 3+)**

| Source | Catches |
|---|---|
| Forgejo system webhook | push, branch, PR opened or merged, review, tag (with the username) |
| Shell hook (zsh `preexec`/`precmd`, base terminal image) | commands and exit codes |
| Service state or audit (`openbao-audit`, tofu state, `dns-gate` lines, Dojo Cloud Activity log, CA log) | "the secret exists", "plan is clean", failure unlocks like "First 403" |
| Lab reader page events | opened or finished lab N (weakest source) |

Vault values are HMACed in the audit log, so only path and operation are usable; there is a small delay; the service
needs its own read-only facilitator-level access. Challenges check the **outcome**, not the command.

**Test plan (A12, approved).**
- **Unit tests** (stdlib `unittest`, no stack): points and hint math (`floor`, forfeit after 2, never below 0),
  once-only scoring, queue collapse above 5, anonymous names unique, forged and unsigned events rejected, catalog
  loading and validation, generated markdown not stale, completion at 80%.
- **Live, with `--test` demo bots:** the bots run the labs, so their commands should unlock milestones; assert on
  the leaderboard API. A scripted solver does each challenge, plus a wrong answer, a hint, a reveal and a reset.
  Sensei: a good PR merges, a bad one gets a comment, a stale branch is handled. Toggle off: nothing extra loads.
  `./run.sh stop` removes the volume. About 15 students polling: one cached read per request, no locks held over I/O.
- **Concurrency (A20):** several bots solve the same challenge at the same moment; every one passes independently and
  no one's state changes another's result.
- **Browser (Playwright image, per CLAUDE.md):** toast on portal, lab reader, slides, workspace, VS Code, Forgejo;
  split and workspace modes; certificate print layout and badge PNG as screenshots; landing widget.
- **By the user:** a real class or 3-5 person dry run, tone of the jokes, and the printed certificate.

**Open questions**

| # | Question |
|---|---|
| A24 | vault-fundamentals capstone slot: keep reusing the student's one slot (replaces the lab app, default) or add a second slot per student in `app-host` |
| A26 | Should the Sensei bot (phase 7) also seed the `dns-bot` PR for dns-as-code `d3-review`, or a separate setup step |

### Remediation leftovers (none Critical or Important)

| Item | Type | Detail |
|---|---|---|
| FIND-11 | Partial | PowerDNS keys are still derived from the shared token |
| FIND-17 | Partial | The single unseal share stays on the setup volume (accepted, D9) |
| FIND-15 | Accepted, no work | dojo-cloud socket `0660 root:cloud`; privileged DinD stays |
| FIND-19 | Accepted, no work | Plaintext to OpenBao and Postgres, documented |
| Not exercised in P4/P5 | Untested | 300 app-db connections · the app-host shim on 443 (base URL was plain `http://localhost:8080`) · a real-browser "Release unused" |
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
| Take-home handouts and PowerPoint decks | Parked: `handouts/` (lab handouts, starter repos, deck export script), the `.githooks` pre-commit and the CI `handouts` checks were all deleted because they had drifted from the labs. Recover from git history if wanted again | Parked |
| Stale plan references | Many code comments and READMEs cite plan sections (`PLAN.md §5.5`, `MODULES-PLAN.md §4.2`, `engine/student-reset.md`). The files now live in `docs/archive/` under new names (`TOFU-BASICS-PLAN.md`, `VAULT-FUNDAMENTALS-PLAN.md`, `MODULES-PLAN.md`, `STUDENT-RESET-PLAN.md`, `REMEDIATION-PLAN.md`). Comments in `engine/` were left alone (engine edits need approval); reword them when next touched |
