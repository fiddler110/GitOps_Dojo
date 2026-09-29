# Roadmap

The single list of open work. Finished work moves to [`RELEASES.md`](RELEASES.md). The old per-feature plans
(design, decisions, task logs) are frozen in [`docs/archive/`](docs/archive/); read them for the why, but don't
update them. When you finish an item: delete it here and add a line to RELEASES.md.

Last updated: 2026-09-29 · Working branch: `feat/remediation` (from `main` after PR #3, 3a59106)

| Section | What it holds |
|---|---|
| [Now](#now) | Merge, plus checks that need a real run |
| [Next](#next) | Student reset; achievements; remediation leftovers |
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

### Achievements (leaderboard, pop-ups, challenges, certificate)

Status: **design decided (2026-09-29), nothing built.** Open: A10 (review the five draft catalogs, one `workshops/<name>/ACHIEVEMENTS.md` each). Rule: **ask before editing any `engine/` file**.

Idea: an optional layer over the labs. When a student does something (pushes code, creates a secret), a small
"achievement unlocked" toast appears on whatever student page is open, and points land on a class leaderboard. Each lab
ends with a **challenge** that gives a goal and no steps. At the end a student can export a summary and a certificate.

**Decided so far**

- **Toggle in `.env`** (e.g. `ACHIEVEMENTS_ENABLED`); off means no module, no toasts, no leaderboard.
- **Built as `modules/achievements/`** (service, compose, `extensions.json` with a `/leaderboard` card and an `/admin`
  tab) so `engine/` stays workshop-agnostic. Each workshop carries its own `achievements.json` catalog (id, title, joke,
  points, trigger).
- **Two kinds of unlock:** small *milestones* (fire when the student does something) and *challenges* (end of a lab, goal
  only, no steps, checked by outcome).
- **Challenge hints:** hints cost points. After 2 hints the student may reveal the answer but **forfeits all points for
  that challenge**.
- **One capstone challenge per workshop**, worth more, with a title or badge on the leaderboard.
- **Export at the end:** a per-student summary of achievements plus a "certificate of completion".
- **Toasts (A1, decided 2026-09-29).** Two student modes over the same routes: *split mode* (today's separate
  pages, so Chrome split screen still works) and an opt-in *workspace mode* (`/workspace`, tabbed like `/admin`, with a
  portal button, remembered per browser). Toast placement: workspace shell (covers all tabs); portal, lab reader and
  slides via a same-origin `<script src>`; VS Code via a small bundled code-server extension (native notification);
  Forgejo via its custom `extra_head` template. No gateway body rewriting. The terminal gets the achievement echoed in
  colour. Surfaces we can't wire (OpenBao UI etc.) get **queued toasts**: an unlock is held per student until they open
  a page that supports toasts, then it shows. The landing page shows the student's score and last 5-10 unlocks.
- **Queue rules (A13, decided).** An unlock is shown once, on the first toast-capable surface that picks it up; the
  landing page list is always the permanent record. The terminal echo is a bonus and does not count as delivered. If
  more than 5 are queued they collapse into one toast ("You unlocked 6 achievements") linking to the landing page.
- **Facilitator sees everything** on the board (`/admin` tab), can award manually and reset scores.

**Checking (A3, decided).** Students only ever run a thin `dojo-check N` client (it holds no answers). The achievements
service holds the catalog and does the checking with its own credentials on networks students can't reach, so a pass
cannot be posted by hand. Identity is a per-student token file (mode 0600, owned by that account, made at provisioning
like the Forgejo token). Modular pieces shipped by the modules that own a backend:
- **Verifiers** (state, for challenges): a fixed set of verbs such as forgejo `branch_exists`, `pr_merged`,
  `file_contains`; openbao `secret_exists`, `policy_attached`; dojo-cloud `resource_state`. Challenges in the catalog are
  declarative assertions with `{user}` templating, not code. A named custom check script inside a verifier is an
  escape hatch, discouraged.
- **Event adapters** (activity, for milestones): follow existing audit streams (`openbao-audit`, `dns-gate` JSON lines,
  the gateway's audit lines, Forgejo webhook) and turn lines into events. Covers third-party UIs like the OpenBao UI,
  and enables funny failure unlocks ("First 403", "Denied 5 times in a row"). Limits: vault values are HMACed (path and
  operation only), a small delay, and the service needs its own read-only facilitator-level access.
- The `/admin` tab keeps a log of check runs (who, when, pass or fail, hints used).

**Points (A4, decided).** Defaults, all settable in `.env` (`engine/.env`, so `stop` can read them; never `${VAR:?}`
in a fragment): milestone 10, funny/failure unlock 5, challenge 100, capstone 300, first blood +25 (capstone +50),
class-clear +10 for everyone once the whole class has cleared a challenge. Each hint costs `ACHIEVEMENTS_HINT_PERCENT` (default 25, so a
facilitator can be mean with 50) of the challenge's points, **rounded down** (`floor(points * pct / 100)`, so the
student keeps the larger value; the score never goes below 0 from hints); after 2 hints the student may reveal the
answer and scores 0 for it (it still counts as completed for the certificate). Points are awarded once per unlock.
First blood, class-clear and the cheater penalty are each switchable in `.env`, so the person launching the lab mixes
and matches. Scores: positive unlocks green, zero neutral, negative red; the score may go negative.

**Cheating (A14, decided).** Each fires once per student; none is worth more than -1.
| Behaviour | Signal | Points |
|---|---|---|
| Posting to the achievements service by hand | Service rejects the forged/unsigned event | -1 ("Nice Try, Hackerman") |
| Editing or replacing `dojo-check` | Client hash sent with each check doesn't match | -1 |
| Using another student's identity headers | Gateway/service token mismatch | -1 ("Identity Crisis") |
| Button masher | Rate limit hit on `dojo-check` | 0, still shows |
| Poking another student's namespace or paths | A refused request into someone else's space | ladder: "Oops, you bumped into your neighbour" (0, looks accidental) -> "Curiosity Killed the Cat" (0, deliberate/repeated) -> a related follow-up comment worth -1 if they keep at it |

Honest mistakes must not trigger the penalty tiers (thresholds for bump vs cat vs repeat are set at build time). Leaderboard sorts by points, ties by who got there
first. Facilitator awards and resets change the score directly and are logged.

**Detection (proposed)**

| Source | Catches |
|---|---|
| Forgejo system webhook | push, branch, PR opened or merged, tag (username comes with the event) |
| Shell hook (zsh `preexec`/`precmd` in the base terminal image) | commands run and their exit code |
| Service state or audit (OpenBao audit log, tofu state, DNS) | "the secret exists", "plan is clean" |
| Lab reader page events | opened or finished lab N (weakest source) |

Challenges check the **outcome**, not the command. Proposed: a `dojo-check N` terminal command runs the workshop's check
script as the student and reports a pass to the service. Task parameters can derive from the username (branch or secret
path) so a neighbour's answer fails.

**Student workspace page (own item, built first).** `/workspace` for students: VS Code, Terminal, Forgejo, Slides,
Labs (and Leaderboard when achievements are on) as iframe tabs, reusing the facilitator page's lazy-load approach; a
portal button opens it; split mode stays as is. Useful without achievements. Edits `engine/allocator/server.py`: ask first.

**Also decided.** Individuals only (people may work together, the lab and achievements are each student's own).
Facilitator's student reset can clear or keep that student's achievements (their choice at reset time). Storage is a
named module volume: survives restarts within a class, removed by `./run.sh stop`.

**Export (A8, decided).** A printable HTML page at `/certificate` (landscape print stylesheet, students use the
browser's "Print to PDF"; no PDF library). Page 1 is the certificate: display name, workshop, class date (the day the
stack started), points and rank, a facilitator signature line (name from `.env`, or blank to hand-sign). Page 2 is the
achievement summary (every unlock with date, challenges cleared with or without hints, any cheater tiers, for the
laugh). **The certificate is issued on lab completion, not the capstone**; clearing the capstone makes it fancier
(stars, capstone title). The summary is available any time. Also a **badge PNG** (Credly-style, but no Credly
branding): the student's name, the workshop, points; drawn client-side on a `<canvas>` (no server dependency) so it
works as a profile picture. **Names:** the student types a display name or uses their work email; the facilitator does
not set names. Facilitator can override completion in `/admin` for someone who ran out of time.

**Completion, names, badge (A15/A16, decided).** Completion is based on **milestones only**, never on challenges or the
capstone (those are optional fun for big points and bragging rights). Milestones tagged `core` in the catalog are the
ones you hit by following the lab's steps; the certificate is issued at `ACHIEVEMENTS_COMPLETION_PERCENT` of them
(default 80). The capstone only makes the certificate fancier. **Export name flow:** when a student
opens export, a dialog asks what to put on it: accept their current display name, or type a name or an email; for an
email it offers the part before the `@` as the name or lets them enter their own. Real names and emails stay on the
student's own pages and downloads, and are stored only in the module volume (wiped by `stop`), never in `/admin`.
**Anonymous board** (`ACHIEVEMENTS_ANONYMOUS`, on or off per class): each student gets a funny generated name
(WildCrab, SpeedyTurtle), unique within the class and kept for the run; they're told their own name, the board shows
"you" highlighted, other students can't tell who is who. The facilitator's `/admin` view shows the real mapping.
**Badge art:** one design per workshop, two tiers (completion; capstone with stars), drawn client-side.

**Board (A9, decided).** The whole class is shown (no top-N). Toasts are only ever for the student's own unlocks, never
for someone else's; a class-clear bonus arrives as an ordinary personal toast for everyone. The catalog for each
workshop lives in its own folder as `ACHIEVEMENTS.md` (review draft first; `git-fundamentals` drafted, other packs to
follow).

**All labs mandatory (decided).** No lab is optional any more, in any workshop; challenges and the capstone stay
optional. Completion is 80% of all lab milestones (`core`). At completion the student's home page shows a **Workshop
complete** banner, and before that a running **completion percentage**.

**Mandatory labs sweep (done 2026-09-29 in git-fundamentals, dns-as-code, cert-autorenewal, vault-fundamentals).** The
"Required?" columns, "optional" wording, "any order" and "required path" text are gone from lab intros, lab READMEs,
`slides/labs.md`, `slides/presentation.md` and `lab-index.md`; vault lab 12 is a normal lab; cert lab 5 is now "The
dns-01 challenge" (not "capstone", so that word means only the achievements bonus). Left alone on purpose: step-level
optional sections, `tofu-basics` (its Track A / Track B split and the optional end of lab 8 are facilitator choices,
decide separately) and `git-fundamentals/delivery-azure-devops/` (a different Azure DevOps course). Still to do:
rebuild the `handouts/` decks that embed the changed slides, check the changed slide tables for overflow in a
screenshot, and re-check time totals (git-fundamentals about 55 min, dns-as-code about 92, cert-autorenewal about 75).

**Catalog format (A17, decided).** `workshops/<name>/achievements.json` is the source, validated at start like
`extensions.json` (a bad one stops the run). `ACHIEVEMENTS.md` is generated from it by a small script in the module, and
a unit test fails when the committed markdown is stale. Until the loader exists (phase 2), catalogs are hand-written
markdown drafts for review, then converted. `dojo-introduction` is a tour, not a workshop: no achievements.

**Challenge seeding (A18, decided).** On demand, per student: a **Start challenge** button in the lab and a
`dojo-challenge start N` command make the student's own challenge repo (student has write access) with seeded commits,
branches and per-student values, and clone it into `~/lab`. **Reset** (`dojo-challenge reset N`, also a button) deletes
and re-creates the repo and re-clones it, unlimited times. Hints already used stay counted, and points are earned once:
a student may redo a challenge as often as they like for the experience, but only the first clear scores and hints
only ever cost.

**Engine edits (A2, approved 2026-09-29; still tell the user before each phase touches them).** Everything else is in
`modules/achievements/`, the workshop packs and `workshops/assets/`.
1. `engine/run.sh`: when `ACHIEVEMENTS_ENABLED=1`, add `achievements` to the module list (about 10 lines), and warn
   if the workshop has no catalog.
2. `engine/allocator/render_extensions.py` + `server.py`: a generic **`widgets`** manifest key (a same-origin `src`
   framed on the student's landing page: score, completion %, Workshop-complete banner, last 10 unlocks; the same
   fixed-template idea as cards, no raw HTML). Also the portal's "Open workspace" button and the `/workspace` page.
3. `engine/presentation/engine.js`: one script tag so slides can show toasts (needed for split-screen use).
4. Docs: `engine/README.md` and `workshops/README.md` (the `widgets` key, the toggle).
Expected **no** engine change for: the shell hook and colour echo and `dojo-check` (module terminal Dockerfile plus a
`start.d` hook; verify at build that zsh has a drop-in point, else one line in the base `zshrc`); student identity
(`dojo-check` sends the student's own Forgejo token, the service asks Forgejo who it is, so no new token file and no
change to `provision-account.sh`); the Forgejo webhook and toast template (module setup and a volume); the VS Code
extension (module terminal Dockerfile); the lab reader (`workshops/assets/`).

**Rollout (A11, approved).** Branch `feat/achievements`, cut from `feat/front-door` (main lacks the front-door and remediation work this builds on). Phases, each testable and committed on its own:
1. Engine: `widgets` key, `/workspace`, portal button, run.sh toggle (useful with achievements off).
2. Module core: service, volume, event API, Forgejo-token identity, catalog loader, leaderboard page, `/admin` tab,
   landing widget with completion %, toast script in portal, workspace and lab reader.
3. Event sources: shell hook, terminal colour echo, Forgejo webhook; git-fundamentals milestones and funny unlocks.
4. Challenges: `dojo-check`, verifiers, seeding, reset, hints and forfeit, points rules, first blood, class-clear.
5. Cheat tiers, anonymous names, negative scores in red.
6. Certificate, badge PNG, export name dialog.
7. Sensei auto-merge and its `/admin` PR tab.
8. Toasts in VS Code (extension), Forgejo (template) and slides.
9. Other packs one at a time (dns-as-code, cert-autorenewal, tofu-basics, vault-fundamentals, dojo-introduction),
   then the sweep removing "optional" wording from labs, slides and READMEs.

**Test plan (A12, approved).**
- **Unit tests** (stdlib `unittest`, no stack, like the other modules): points and hint math (`floor`, forfeit after
  2, never below 0), once-only scoring, queue collapse above 5, anonymous names unique, forged and unsigned events
  rejected, catalog parsing, completion at 80%.
- **Live, with `--test` demo bots:** the bots already run the labs, so their commands should unlock milestones;
  assert on the leaderboard API. A scripted solver does each challenge, plus a wrong answer, a hint, a reveal and a
  reset. Sensei: a good PR merges, a bad one gets a comment, a stale branch is handled. Toggle off: nothing extra loads.
  `./run.sh stop` removes the volume. About 15 students polling: one cached read per request, no locks held over I/O.
- **Browser (Playwright image, per CLAUDE.md):** toast on portal, lab reader, slides, workspace, VS Code, Forgejo;
  split mode and workspace mode; certificate print layout and badge PNG as screenshots; landing widget.
- **By the user:** a real class or 3-5 person dry run, tone of the jokes, and the printed certificate.

**Auto-merge (A19, decided).** The Sensei bot handles the Lab 1 roster PR only; challenge PRs stay the student's own
(they merge them in their own repo, and the checks accept the outcome open or merged), so bot comments never give free
hints. Design: a "Sensei" bot (switchable in `.env` on its own) reviews each roster PR against catalog rules (only allowed files, YAML
parses, the student's entry is present, nothing else deleted). A good PR is merged through the Forgejo API with a
friendly comment; a bad one gets a review comment saying what to fix and is not merged. The facilitator's `/admin` tab
lists every PR (auto-merged, waiting, failing and why, minutes stuck) with "merge anyway" and "comment" buttons.
**Check first:** PRs that all append to `roster/team.yaml` conflict with each other, so the bot must handle a stale
branch (Forgejo's update-branch call, or a comment telling the student to update).

**Open decisions**

| # | Question |
|---|---|
| A10 | Review the five draft catalogs (`workshops/{git-fundamentals,dns-as-code,cert-autorenewal,tofu-basics,vault-fundamentals}/ACHIEVEMENTS.md`). Their C2s and capstones need seed data; tofu-basics: tracks A and B are both mandatory (decided); vault-fundamentals stays at ~1040 points (decided, not trimmed). `dojo-introduction` is excluded |

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
