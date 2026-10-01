# Roadmap

The single list of open work. Finished work moves to [`RELEASES.md`](RELEASES.md). The old per-feature plans
(design, decisions, task logs) are frozen in [`docs/archive/`](docs/archive/); read them for the why, but don't
update them. When you finish an item: delete it here and add a line to RELEASES.md.

Last updated: 2026-10-01 (roadmap review) · Working branch: `feat/achievements`, stacked on `feat/front-door`, which
is stacked on `feat/remediation`; nothing has reached `main` since PR #3.

| Section | What it holds |
|---|---|
| [Priorities](#priorities-decided-2026-10-01) | The order of work, decided at the 2026-10-01 review |
| [Now](#now) | Home demo dry run, merges, phase 9 live checks |
| [Next](#next) | Student reset; achievements leftovers and reference; `run.sh` CLI; remediation leftovers |
| [Manual checks](#manual-checks-the-user-in-a-browser) | Browser passes only the user can do |
| [Later](#later) | Follow-ups and known limits |
| [Housekeeping](#housekeeping) | Repo hygiene |

## Priorities (decided 2026-10-01)

1. **Commit the working tree** (the user stages and commits; `git add -A` is off limits). About 48 files on
   `feat/achievements` are uncommitted: the vault capstone slot (A24), the cert `c2` watch, Sensei activity saved in
   `state.json`, the chained-command matcher, the slimmed dojo-introduction. A demo from an uncommitted tree can't be
   reproduced.
2. **Home demo dry run** (Now §1).
3. **Merge `feat/remediation` + `feat/front-door` to `main`** (Now §2), then a toggle-off regression run and merge
   `feat/achievements` early; phase 9 live checks carry on from `main`.
4. **Phase 9 live checks** (Now §3): cert-autorenewal, tofu-basics, vault-fundamentals, then the class-sized run.
5. **Student reset**, starting with the R0 spikes (Next). Q1-Q7 are answered, so nothing blocks it.
6. **Phase 10 sweep** and the remaining polish (dojo-introduction `--test 5`, Caddy log redaction).

The user's own browser checks (Manual checks) fit in around these; tofu-basics T9.4/T9.9 are the oldest.

## Now

### 1. Home demo dry run (`--env home`, https://dojo.macleodtech.ca, VPN only)

Nothing in the Sensei support desk (`sensei ask|why|hand|inbox|check`, Raised hands and Stuck radar cards; built
2026-10-01, unit-tested and smoke-tested over HTTP) has run live. Use dns-as-code (the most exercised pack) with
`ACHIEVEMENTS_ENABLED=1`. Before the guest arrives, do one dry run yourself as `student01`, in this order, and stop on
the first failure:

1. `./run.sh dns-as-code --dry-run --env home`, then start it; `podman ps` shows `workshop_sensei` and
   `workshop_achievements` healthy.
2. In the terminal: `sensei help`, `sensei ask "how do I undo a push"`, then `git push` to `main` and `sensei why`.
   Also `sensei why` after `dnscontrol preview` with a missing dot. `sensei ask` must find nothing under a challenge
   heading.
3. `sensei hand "demo"`: the card appears in the Sensei tab and its "Their screen" text is really the last screen;
   reply there; `sensei inbox` shows it. Check the 3-open and 20 s limits.
4. Run `dnscontrol preview` a few steps, then `sensei check`: your done steps match what the board says.
5. Repeat one failing command 5 times: the Stuck radar shows you as `failing` within ~10 s. Idle 15 min shows `quiet`
   (`SENSEI_STUCK_MINUTES=1` in `workshop.env` makes `stalled` quick to see). Restart the achievements service: the
   radar keeps its state (saved at most every 30 s).
6. Lab 3 with `sensei review`, `sensei approve`, `sensei approve --force`, then merge and `dig`.
7. From the student terminal, `curl http://achievements:8080/api/sensei/activity` must answer 403.
8. The Sensei and Achievements tabs load for the facilitator (iframe framing over the home Caddy), and toasts still
   appear through https. This is also front-door's first `--env home` run behind the proxy.

Soft spots: with `--test` bots running, `testuser*` accounts show up in the radar and the board. Sensei never speaks
first at a student's prompt (facilitator-only nudges, by design). Have `./run.sh stop` ready; it wipes volumes (ask
first if anyone else is using the machine). When the dry run passes, add the support desk to `RELEASES.md`.

### 2. Merges to `main` (ask before pushing or opening a PR)

| # | Item | Detail | Status |
|---|---|---|---|
| M1 | `feat/remediation` + `feat/front-door` | One PR of front-door (it contains remediation: 65 + 2 commits). Both built and live-tested locally; see RELEASES "Unreleased" | Ready |
| M2 | `feat/achievements` with the toggle off | After M1. One regression run with `ACHIEVEMENTS_ENABLED` unset (git-fundamentals `--test`: no achievements or sensei container, no toasts or widget, `/workspace` still works) plus `--dry-run` of every pack, then a PR. Phase 9 checks continue on `main` | After M1 and the demo |

### 3. Phase 9 live checks (order matters)

Everything in 9a is unit-tested only. Run one stack at a time (`podman ps` first; ask before `./run.sh stop`, it
wipes volumes). Order goes from smallest blast radius to largest, so a core defect shows up on the cheapest pack.
Each step: start with `--test`, wait for the bots, then compare fired items against the pack's `ACHIEVEMENTS.md`.
Done and in `RELEASES.md`: rebuild, git-fundamentals regression, dns-as-code (2026-10-01).

0. **dns-as-code leftovers** (all unit-tested): one more `--test 3` on the final bot steps (Lab 1 "opposite mistake"
   for `f-dot2`, `dns_catch_up` before each push, Sensei's `conflicts` status and criss-cross rule), reading the bot
   logs for stray errors. As a student in the browser: `sensei help|status|review|approve [--force]`, the Lab 3 text
   (fresh `git pull` before branching, the DELETE-in-preview box), a long output and `clear` through the readback,
   and `lab-prep 5`. Much of this overlaps the demo dry run; tick it there. Optional: bots close their own abandoned
   PRs (round-1 PRs #5/#6 stayed open with conflicts).
1. **cert-autorenewal (`ca` adapter + `verify` sweep).** `ca` events reach `/api/adapter` (order_issued,
   order_failed), `served_changed`/`served_expired` verifiers, and the sweep's first real backend use. Restart the
   service once and note the `c4-installs`/`c4-watch` baseline reset (known). Expect all but `f-ratelimit`. `c2` is a
   20-minute watch (`served_renews`, `"watch": true`): run `dojo-check c2` once with Lab 4's cron in place and see it
   clear on its own.
2. **tofu-basics (`cloud` adapter).** `cloud-api` events (portal/site request, policy/quota denied, container
   create/update/delete/replace) reaching the service; credentials/secret wired through compose. Watch the known
   approximations: `site_request` credits the owner, `t8-inplace` fires early, `t9-foreach` reads `extra[...]`. Check
   the added Sensei container against the 15-student ceiling.
3. **vault-fundamentals (`bao` adapter, heaviest).** Audit tailer posts (login, request, wrapping) and `repo_secret`.
   Check `role` (first non-default policy) and the 404 guess; `v13-recover` only proves the app answers. `f-paste`
   stays facilitator-awarded. Capstone slot (A24, unit-tested only): **My App** shows `{user}-capstone` locked, then
   unlocked within ~10 s of `dojo-challenge start capstone`; a push to `main` of `{user}/capstone` (Actions on in that
   new repo?) deploys there while the lab app keeps running; the app logs in as `slot:{user}-capstone`.
   **Challenges in the labs (all packs, built 2026-10-01, unit-tested only):** every workshop's labs now end the right
   lab with a `## Challenge ...` / `## Capstone ...` section and its `<!-- dojo-challenge: ID -->` box, and each lab
   README lists them. On each pack's run: the box appears only with achievements on; Start builds the repo and the
   status names `~/lab/<repo>`; Reset is hidden on cert-autorenewal (no repo; Start just shows the goal);
   `shop.<user>.certs.dojo.test` and `www`/`api` under the student resolve (new per-student wildcard in the cert DNS
   seed); dns-as-code c1, c2 and capstone each get their own repo (`challenge-typo`, `-cutover`, `-badpush`); Sensei
   `ask` never returns a challenge section; then solve one per pack, `dojo-check`, and Reset.
4. **Class-sized concurrency run (last).** On dns-as-code or git-fundamentals with ~20 bots: shell hook latency,
   state sweep budget (`gap=20`, `budget=40`), no dropped events, `/admin` leaderboard and toasts still responsive.
   Also recheck the **facilitator VS Code tab "unknown error"** (seen once under load, a retry fixed it, not
   reproduced at 10 bots) with the `/auth-check` logging from remediation T1.4; sizing for 20-35 students is
   extrapolated from 10 bots until this run.

Log failures per step here; when a pack passes, delete its step, add a line to `RELEASES.md`, and fix the item
`when` text for any approximation that proved wrong.

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

**Answered by the user (2026-10-01)**

| ID | Answer |
|---|---|
| Q1 | No "reset and release" for now; it can be a second Roster item later |
| Q3 | Shared DNS zone: use the `<author>-...` record naming Sensei's approve mode already enforces; a reset removes the records named after the student |
| Q4 | Accept code-server's browser UI state (cosmetic) |
| Q5 | Shared org repo: close the student's open PRs and delete their branches; leave comments and merged history alone |
| Q6 | Forgejo re-provision: two API calls from the allocator (no bootstrap image needed mid-class) |
| Q7 | Facilitator only (as R7) |

**Phases**

| Phase | Scope | Tasks |
|---|---|---|
| **R0 spikes** | Throwaway, no engine edits kept | R0.1 list every student-owned file after doing all labs of one workshop · R0.2 Forgejo purge and recreate by hand via the admin API, record what survives · R0.3 manual reset of one vault-fundamentals student (namespace delete plus tenancy hooks) and rerun labs · R0.4 time each step (target under 30 s) |
| **R1 engine core** | Engine reset machinery | R1.1 done (7172d9b) · R1.2 `account.d`/`reset.d` hook runner and `POST /reset/<user>` in `workspace-control.py` · R1.3 Forgejo teardown and re-provision (per Q6) · R1.4 allocator `POST /admin/reset/<sid>` with worker thread, fence and `reset` in the sessions API · R1.5 Roster UI (Reset item, confirm dialog, progress, Retry) · R1.6 tests in `engine/allocator/tests/` (auth, fence, idempotency, bot reset) and a live check |
| **R2 hook contract** | How hooks are declared and called | `resets` in `render_extensions.py` (with tests) · `RESET_TOKEN` in `env-setup.sh` and compose · the allocator calls service hooks with a per-hook timeout and results |
| **R3 adoption** | Modules and workshops reset their own state | `dojo-cloud` (reset endpoint on cloud-api, reuse `_purge`; live check on tofu-basics) · `openbao` plus vault tenancy/CI/platform via `openbao-reset` (R9) · `runner-pool` and `forgejo-runner` · vault `app-host` (both slots; the capstone slot locks again) and `app-db` · dns-ui, dns-as-code, cert-autorenewal per Q3 (move any per-account `start.d` work to `account.d`) · achievements: clear or keep the student's score (A28) |
| **R4 docs and live pass** | Documentation and verification | `engine/README.md` "Facilitator operations" · `workshops/README.md` hook contract · module READMEs · per workshop: break a student on purpose, reset, redo the first labs as them while a second student carries on |

### Achievements (leaderboard, pop-ups, challenges, certificate)

An optional layer over the labs (`ACHIEVEMENTS_ENABLED`): toasts on every student page, a class leaderboard, a
goal-only challenge per lab, a capstone, and a certificate at the end. Rule: **ask before editing any `engine/`
file**. Phases 0-8 are done (RELEASES); phase 9 is built and live on git-fundamentals and dns-as-code (Now §3).

#### Phases

| # | Phase | Status |
|---|---|---|
| 0-2 | Design and catalogs, catalog core, engine workspace and widgets, score service and toasts | done |
| 3 | Event sources (shell hook, Forgejo system webhook, matcher) | done, one check left (below) |
| 4 | Challenges (`dojo-check ID`, `dojo-challenge`, verifiers, seeds, capstone, lab-page buttons) | done |
| 5 | Cheat tiers and names (poking-a-neighbour strikes) | done |
| 6 | Certificate, badge PNG, name dialog | done, one decision left (below) |
| 7 | Sensei (roster auto-merge, `/admin` PR tab, dns-as-code review PR seed) | done |
| 8 | Toast surfaces (VS Code extension, Forgejo header) | done |
| 9 | Other four packs: `match`, adapters, verifiers, seeds (9a build done 2026-10-01) | live checks: Now §3 |
| 10 | Sweep: overflow screenshots, re-check lab time totals (git-fundamentals about 55 min, dns-as-code about 92, cert-autorenewal about 75) | todo |

#### Leftovers

| Item | Detail |
|---|---|
| **Decision: certificate variables** | `ACHIEVEMENTS_SIGNATURE` / `ACHIEVEMENTS_CLASS_DATE` are in the module `compose.yml` but not in `engine/.env.example`; adding them is an engine edit and needs the user's OK |
| Phase 3: zsh hook | Not run with a prompt framework (oh-my-zsh, powerlevel10k) in the real terminal image |
| Not looked at in a browser | A red negative score (board, widget, `/admin`) and a negative toast in VS Code; the badge PNG download, capstone badge tier and a typed certificate name; a real student's stale-branch roster PR |
| Known quirks | Round 1's `git reset --hard HEAD~1` fails with "unknown revision" in `bot-runner.sh` (engine; round 2 succeeds) · a signed event whose user doesn't exist burns its nonce · `lab0.md.txt` 404s in the git-fundamentals lab reader (harmless probe) · the widget only resizes once `toast.js` has loaded |

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
| A2 | Engine edits | Everything else lives in `modules/achievements/`, the packs and `workshops/assets/`. The engine gets: (1) `engine/run.sh` adds `achievements` to the module list when the toggle is on (about 10 lines) and warns if the workshop has no catalog; (2) `render_extensions.py` + `server.py`: a generic `widgets` manifest key (a same-origin `src` framed on the student's landing page: score, completion %, Workshop-complete banner, last 10 unlocks; fixed-template like cards, no raw HTML), the portal's "Open workspace" button and `/workspace`; (3) `engine/presentation/engine.js`: one script tag so slides show toasts; (4) docs in `engine/README.md` and `workshops/README.md`. **No** engine change expected for the shell hook and colour echo, `dojo-check`, student identity, the Forgejo webhook and toast template, the VS Code extension, or the lab reader |
| A3 | Checking | Students run only a thin `dojo-check N` client (no answers in it). The service holds the catalog and checks with its own credentials on networks students can't reach, so a pass can't be posted by hand. Identity: `dojo-check` sends the student's own Forgejo token and the service asks Forgejo who it is (no new token file, no change to `provision-account.sh`). Verifiers (state, for challenges) and event adapters (activity, for milestones) are shipped by the modules that own a backend (A22) |
| A4 | Points | Defaults, settable in `engine/.env` (so `stop` can read them; never `${VAR:?}` in a fragment): milestone 10, funny 0, challenge 100, capstone 300, first blood +25 (capstone +50), class-clear +10 for everyone once the whole class has cleared a challenge. Each hint costs `ACHIEVEMENTS_HINT_PERCENT` (default 25) of the challenge's points, `floor(points * pct / 100)`; after 2 hints the student may reveal the answer and scores 0 for it (it still counts as completed). Score never drops below 0 from hints. Points are awarded once per unlock. First blood, class-clear and the cheater penalty are each switchable |
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
| A28 | Storage and reset | State lives in a named module volume: it survives restarts within a class and `./run.sh stop` removes it. The facilitator's student reset (see Student reset above) can clear or keep that student's achievements, their choice at reset time |
| A29 | Branching | `feat/achievements` was cut from `feat/front-door` (main lacks the front-door and remediation work this builds on). The student workspace page is built first (phase 1b) because it is useful with achievements off |
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

### `run.sh` CLI follow-ups (C1-C4 shipped 2026-10-01, see RELEASES)

| # | Item | Detail | Status |
|---|---|---|---|
| C5 | Untested paths | Docker instead of podman (only podman here); macOS's system Python 3.9 (click 8.1.8 and rich 15 support it, not run); `CORP_CA_BUNDLE` for the first-run wheel download behind TLS inspection; zsh completion in a real interactive shell (tested with stubbed zsh built-ins) | Needs a Mac / Docker host |

### Remediation leftovers (none Critical or Important)

| Item | Type | Detail |
|---|---|---|
| FIND-11 | Partial | PowerDNS keys are still derived from the shared token |
| FIND-17 | Partial | The single unseal share stays on the setup volume (accepted, D9) |
| FIND-15 | Accepted, no work | dojo-cloud socket `0660 root:cloud`; privileged DinD stays |
| FIND-19 | Accepted, no work | Plaintext to OpenBao and Postgres, documented |
| Not exercised in P4/P5 | Untested | 300 app-db connections · the app-host shim on 443 (base URL was plain `http://localhost:8080`) · a real-browser "Release unused" |
| `dojo-introduction` live check | Untested | Not re-run since P4, and slimmed to Forgejo + CI, DNS and Dojo Cloud (2026-10-01): run `./run.sh dojo-introduction --test 5` once and walk FACILITATOR.md. (git-fundamentals and dns-as-code were re-run live 2026-10-01; cert-autorenewal `--test 1` passed after P4) |
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
| **tofu-basics follow-ups** | `dcloud` CLI for students (`login`, `group list`, `container list/show/logs`; not `dojo`, which is the facilitator's platform CLI) · CI `plan` on pull requests via Forgejo Actions (needs runner network design like dns-as-code's `runner_net`) · more Azure-shaped resources (virtual network, storage account) if the ARM facade extends cheaply · remote state backend simulation · stretch labs 11-12 only if wanted |
| **tofu-basics known limits** | Only one container per group and only `dojo/hello:*` images (by design) · LRO (`Azure-AsyncOperation`) not implemented · arm64 untested (checksums pinned per arch, only amd64 built) · 20+ students out of scope (15 is this box's ceiling) · **T9.8 deferred:** re-test isolation on real Docker before any non-podman delivery (the privileged-DinD risk is materially higher there); this machine has no Docker |
| **Achievements shell hook limits (accepted)** | The hook sees only the line's exit code, so in a chained line a failure is credited only where it is provable (the last pipeline of the last list; see `matcher._segment_exits`): `a; git push; echo $?` can't earn `f-rejected`. The hook sends the text of every command to the service (kept nowhere, only matched), and a student can post their own shell events by hand, which earns only what typing the command would |
| **Not verified since `f977209`** (code-server memory cut) | tofu-basics `tests/e2e.sh` on the new web-terminal image · `./run.sh capacity` printing "Left out N" for a closed tab (dry-run only) |

## Housekeeping

| Item | Detail |
|---|---|
| Take-home handouts and PowerPoint decks | Parked: `handouts/` (lab handouts, starter repos, deck export script), the `.githooks` pre-commit and the CI `handouts` checks were all deleted because they had drifted from the labs. Recover from git history if wanted again |
| Stale plan references | Many code comments and READMEs cite plan sections (`PLAN.md §5.5`, `MODULES-PLAN.md §4.2`, `engine/student-reset.md`). The files now live in `docs/archive/` under new names (`TOFU-BASICS-PLAN.md`, `VAULT-FUNDAMENTALS-PLAN.md`, `MODULES-PLAN.md`, `STUDENT-RESET-PLAN.md`, `REMEDIATION-PLAN.md`). Outside `engine/` done 2026-10-01 (the rest already point at the archive names, and every cited section exists). Comments in `engine/` were left alone (engine edits need approval); reword them when next touched |
