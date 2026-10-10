# achievements module

Optional leaderboard, "achievement unlocked" toasts, end-of-lab challenges and a certificate over a workshop's labs.

**Status.** In progress; see "Achievements" in `ROADMAP.md`. Built: the catalog (loader, validator, markdown
generator, editor), the service with its event API, points, hints and `/admin` tab, the shell and Forgejo event
sources, and challenges (phase 4: `dojo-check`, `dojo-challenge start/reset`, the Forgejo verifiers and seed builder,
with git-fundamentals c1 and c2 specified). Not built yet: the capstone's seed and verbs, cheat tiers, the certificate,
Sensei and the VS Code/Forgejo toast surfaces. Only git-fundamentals has `match` rules and challenge verifiers so far.

## The catalog

A workshop keeps its achievements as small data files beside its labs, so one joke, one lab or one challenge can be
edited without touching the rest:

```text
workshops/<name>/achievements/
  catalog.json          workshop id, title, intro text, lab list
  labs/lab1.json ...    one file per lab: its milestones
  funny.json            the workshop's funny unlocks
  challenges/c1.json .. one file per challenge
  capstone.json
  seeds/                (later) files the seed builders copy
modules/achievements/catalog/shared.json   cheating tiers and cross-workshop unlocks
```

- **Item** (a milestone or a funny unlock): `id`, `title`, `joke`, `when` (text for humans), `core` (milestones only),
  optional `points` (else the kind's default: milestone 10, funny 0, challenge 100, capstone 300), optional `note`,
  `retired`, `enabled`, and `match`, the structured trigger (`{"source": "shell", "cmd": "git commit", "exit": 0}`).
  An empty `match` produces a warning (the item is listed but never fires), or an error in a workshop whose
  `catalog.json` sets `"require_match": true` (git-fundamentals does).
- **`match` fields** (full list in `catalog/catalog.py`, matched by `service/matcher.py`). `shell`: `cmd` (the
  command's first words, a string or a list), `flags` / `flags_none`, `regex` (on the command segment, redirects
  kept), `exit` (a code, a list, `"nonzero"` or `"any"`), `branch` / `branch_before` (`"HEAD"` when detached),
  `in_repo`, `merging`, `merging_after`, `out_regex` (searched in the last lines the command printed, read from
  the pane -- tmux or Zellij, see "Shell output" below; matched and dropped). `forgejo`: `event` (push, create, delete, fork, pull_request,
  pull_request_review), `action` (opened, merged, approved, ...), `ref_type`, `branch`, `tag`, `repo` (`{user}`
  allowed). `branch_not` and similar negate. `{"any": [...]}` fires on any one. `{"source": "service"}` marks
  items the service fires itself (the cheating tiers). Every source takes `requires` / `requires_not` (ids the
  student must / must not hold) and `count`. `cloud`, `bao`, `ca`: events the owning module posts (see "Adapter
  events" below). `verify`: a state milestone, `{"source": "verify", "verify": [{"verb": ...}]}`: the service runs
  those verbs (the same ones challenges use) for each student every `ACHIEVEMENTS_STATE_SECONDS` (default 20) and
  unlocks it the first time they all pass.
- **Challenge and capstone:** `id` (`c1`, `c2`, ..., or `capstone`), `title`, `after`, `space` (the student's own space,
  must contain `{user}`), `goal`, `seed`, `verify_text`, `verify` (structured assertions, each mentioning `{user}`),
  exactly two `hints`, `answer`, `isolation` (how it avoids other students), `facilitator` (true only when a
  facilitator step is truly required), and `badge_tier: "capstone"` on the capstone.
- **Ids are forever.** Never rename or reuse one that a class may have earned. Retire it with `"retired": true`: it
  keeps its points for anyone who earned it and disappears for new classes.
- **On and off.** `"enabled": false` (any item, challenge or capstone; absent means on) switches an item off: it never
  fires, students never see it, and it counts toward neither completion nor any score, including points already
  earned from it (unlike `retired`). Switching it back on restores those unlocks. A toast still queued for it when it
  is switched off is dropped (never shown, even after it is switched back on); the landing page list is the record.
  `ACHIEVEMENTS.md` marks it `(off)`.
- **The isolation rules** ("Rules for challenges and capstones" in every generated `ACHIEVEMENTS.md`, source
  `catalog/rules.md`) are enforced where they can be: a challenge without a per-student `space`, or with a `verify`
  assertion that never mentions `{user}`, is an error.

## Tools

Run from `modules/achievements/catalog/` (stdlib only, no stack needed):

| Command | What it does |
|---|---|
| `python3 -B render_md.py --all` | Regenerate every workshop's `ACHIEVEMENTS.md` from its JSON (the markdown is a review copy; never edit it) |
| `python3 -B render_md.py --all --check` | Exit 1 if a generated file is stale (the unit tests run this) |
| `python3 -B render_md.py workshops/<name>` | One workshop |
| `python3 -B -m unittest test_catalog` | The unit tests |

To change an achievement: edit its JSON, run `render_md.py --all`, commit both. Or use the editor below.

## The catalog editor (`editor/`)

`modules/achievements/edit.sh <workshop|all>` starts a local page (stdlib Python, `127.0.0.1` only, `PORT=8099` by
default, no stack or network) with every item of that workshop plus `shared.json` in one table, grouped by workshop
and lab: an on/off switch per row, per-workshop **All on / All off** (only the rows the current search and filter show), search and a filter (on, off, changed).
Title, joke, when, points, core, and a challenge's goal, hints and answer are editable; `id` and `match` are read-only.
Edits stay in the page (changed rows highlighted, a warning before leaving) until **Save**, which checks every edit,
runs the catalog validator over the result (refusing the lot with its error list), writes only the changed JSON files
in the house format (2-space indent, key order kept, so the diff is just the edited lines) and regenerates
`ACHIEVEMENTS.md`. A file changed on disk since the page loaded is refused: **Reload**. Tests:
`python3 -B -m unittest test_editor` from `editor/` (they work on a temporary copy).

## Service logic (`service/`)

Pure Python, tested without containers: `python3 -B -m unittest test_service` from `service/`.
`ledger.py` holds scoring, hints, bonuses, cheats, the Moments table and the toast queue;
`names.py` the anonymous board names; `guards.py` event signing, replay protection and the
button-masher rate limit. Every unlock kind toasts, funny and cheating ones included.

## The service (`service/server.py`)

Runs on the allocator image (stdlib Python), added by `dojo` when `ACHIEVEMENTS_ENABLED=1`.
`store.py` wraps the ledger with one lock and writes `state.json` to the `achievements_data`
volume after every change. Routes: student pages and API under `/achievements` (identity
gate), the facilitator tab under `/achievements-admin`. An event is `{user, event, ts, nonce,
sig}` signed with the service's gateway token; a forged one is charged (-1, "Nice Try,
Hackerman") only to a caller the gateway identified, never to the user named in the body.
Tests: `python3 -B -m unittest test_service test_server test_geo` from `service/`.
The ctf-defend SOC (facilitator `/achievements-admin/soc`, tab "SOC (whole room)": live alerts, cyber map with a Canada inset, incident summary on one 16:9 page;
`/map` and `/incident` redirect to it). Students get a separate, per-caller **SIEM** page (`/achievements/soc`, `soc.html`): a breach banner (red while their target is breached, "Contained" with time to patch after, slim "Monitoring" before), their own request log and incident summary only; no map or room tables, and the server filters every row to the caller. Repeated identical breach request lines collapse into one row with `count`/`first_at` and the latest time (`x37` badge). The SOC places each student by a coarse, city-level region from the forwarded
client address (`geo.py`, optional offline DB-IP database from `tools/fetch_geoip.sh`, else `CTF_HOME_REGION`;
the address itself is never stored or shown), and honours `CTF_TIME_SCALE` for its countdown. Details:
`modules/ctf-range/README.md`.
The live-alerts panel is a SIEM request log: `soc`/`ctf` adapter events may carry `method`, `query`, `status`,
`bytes`, `rows_returned`, `ua`, `tag` and `klass`; `store.py`'s `_present()` filters them per caller on the
server (`CTF_SIEM_DETAIL` = full | paths | off, default full; until the student's own target is breached even
`full` shows only method, path, status and tag; the facilitator and the room's map arcs are handled separately).
Tests: `test_siem.py`.
Sensei's two reads (`GET /api/sensei/activity`: per-student command times and failure counts, no command text; and
`/api/sensei/progress?user=`: a student's core milestones by lab) need the `X-Sensei-Key` header equal to `SENSEI_KEY`
(compose passes Sensei's gateway token to both); unset, they answer 403.
`static/toast.js` shows toasts on any same-origin page (`<script src="/achievements/toast.js"
data-surface="portal">`); loading it on engine pages is open question A31 in ROADMAP.md.

## The terminal (`terminal/`)

`dojo-check` (status, `hint ID`, `reveal ID`, `ID`) is one stdlib script with no answers in it.
It sends the student's own Forgejo token (from `~/.git-credentials`), which the service confirms
with Forgejo, plus its own sha256: the service hashes the same file, so an edited copy costs -1
("cheat-client") and a mutating call without the shipped client is refused the same way.
Identity headers next to a token that belong to someone else cost -1 ("cheat-identity").
A prompt hook in `/etc/zsh/zshrc` runs `dojo-check --echo` at most every 5 s and prints new
unlocks in colour once; the echo never marks an unlock delivered, so the browser still toasts it.
`dojo-check ID` asks the service to check a challenge; `dojo-challenge start|reset ID` (a link to
the same file, so the hash matches) builds the student's own challenge repo and clones it into
`~/lab`.

## Challenges: verifiers and seed builders (`achievements/`, `service/challenges.py`)

A module that owns a backend declares its checks in `achievements/verifiers.json` (verb names, what
each checks, the Python file with `VERBS` and `BUILDERS`); this module ships the Forgejo/git ones
(`achievements/forgejo.py`). `service/challenges.py` loads them (plus any folder in
`ACHIEVEMENTS_PLUGIN_DIRS`), fills `{user}` and the per-student values of the challenge's
`seed_plan` (`workshops/<name>/achievements/seeds/`, each value picked by a hash of the user name;
keys grouped in the plan's `linked` share one pick, e.g. a role and its misspelling),
refuses any assertion or seed whose `repo` isn't `{user}/...`, and runs them with the service's
own Forgejo admin login (no login: `dojo-check ID` answers 501). A pass is recorded once, never
undone, and scores the usual points minus hints; a wrong answer costs nothing (only the masher
limit applies); Forgejo being down is "try again" (503), not a wrong answer. `POST /api/challenge`
`{challenge, action: start|reset}` builds the repo (start leaves an existing one alone, reset
deletes and re-creates it; hints and points are untouched) and returns the goal with the
student's values filled in. Check runs are logged for the facilitator (`/api/state` `checks`).
A challenge with `"watch": true` is checked over time, not once (cert-autorenewal `c2`: the site renews itself for
20 minutes): a failing `dojo-check ID` puts it on the student's watch list (kept in `state.json`), and the state sweep
re-runs its verifiers every `ACHIEVEMENTS_STATE_SECONDS` until they pass, then scores it like a check (logged with
`watched: true`). The verb keeps its own progress (`served_renews` in memory, so a restart starts the window again).
Tests: `service/test_challenges.py` against the in-memory `service/fake_forgejo.py`.

**Lab buttons.** A lab adds a Start/Reset box for a challenge with one marker line, where the
challenge's section ends: `<!-- dojo-challenge: c1 -->` (or `capstone`). Editors and Forgejo hide
the comment; the lab reader (`workshops/assets/lab-reader.js`) shows the box only to a student
when this module is on (`/achievements/api/me` lists that challenge), calls `POST
/achievements/api/challenge` through the gateway, and tells the student to run `dojo-challenge
start ID` to clone the repo into `~/lab`. With achievements off, or for the facilitator, nothing shows.

**Shell events.** `dojo-achievements.zsh` (sourced from `/etc/zsh/zshrc`) records each command in `preexec` and, in
`precmd`, sends it with its exit status, the branch before and after, and whether a merge was in progress before and
after, through `dojo-check --shell` (`POST /api/shell`), in the background so the prompt never waits. The fields go in
that process's environment, not its arguments, so `ps` doesn't show them to other students. Every command is sent;
the service matches it against the catalog and keeps none of the text. `/api/shell` accepts only the terminal (Forgejo
token plus the shipped client); a burst over 40 commands in 10 s is dropped without the masher penalty (a pasted lab
block is not cheating). A student can still post their own shell events by hand: that only earns what typing the
command would.

**Shell output.** The hook also reads back the last 40 lines a command printed and sends the last 4000 characters as
`out`, so an item can match an error message with `out_regex` -- only ever used by a workshop's optional "funny"
easter-egg catalog, never a core/challenge milestone. Under tmux (the web/VS Code flavor) it reads an exact range
from the pane (`#{history_size}` and `#{cursor_y}` before and after the command). Under Zellij (`TERMINAL_FLAVOR=
zellij`, which has no code-server and so no `tmux` either) it instead dumps the current viewport
(`zellij action dump-screen`), since Zellij's CLI has no range query -- good enough for an optional easter egg,
though output taller than the viewport is simply missed. Either way it is matched and dropped, never stored. A
full-screen program (vim, less) or a `clear` leaves nothing to read.

**Adapter events.** A module that owns a backend posts what happened, signed with `ACHIEVEMENTS_ADAPTER_SECRET`
(HMAC-SHA256 of the raw body, header `X-Adapter-Signature`) to `POST /api/adapter`, best effort and never slowing the
backend: `dns-gate` (`source: dns`), `cloud-api` (`cloud`), `openbao-audit` (`bao`, the student read from the
namespace `students/<user>`). The body is `{source, event, user, ...}` with the optional fields `reason`, `mount`,
`role`, `op`, `path`, `ok`, `root`, `status`; the vocabulary per source is in `catalog/catalog.py`. A body from an
unknown source or event, or without a user, is ignored. All three send through `modules/_shared/adapter_client.py`: one
bounded queue and one worker thread per service, so a burst never starts extra threads, and a full queue drops events
rather than wait (a lost event is a missed unlock, never a slow request).

**State milestones.** `service/store.py` `sweep_state` gives each student's `verify` milestones a turn at most once
per `ACHIEVEMENTS_STATE_SECONDS` and at most 40 backend checks per pass, outside the lock; a backend that is down
skips the student until the next pass. Use them where nothing posts an event ("the app serves a new certificate").

**Forgejo events.** At start the service registers a Forgejo system webhook (as `FORGEJO_ADMIN_USER`, retried
until Forgejo is up; it lists and removes old ones through the admin API but creates the hook through the admin web
form, because Forgejo 16's `POST /api/v1/admin/hooks` only makes a *default* hook, copied into repos created later) pointing at `http://achievements:8080/api/forgejo`, with a secret derived from its gateway
token. Deliveries without a valid `X-Forgejo-Signature` are refused. `compose.yml` adds `achievements` to git-server's
`[webhook] ALLOWED_HOST_LIST`. The credited user is the pusher, the PR author (a merge by the facilitator credits the
author) or the reviewer; the facilitator and the Forgejo admin never score. Tests: `test_matcher` replays recorded lab
sequences and real Forgejo 16 deliveries (`service/testdata/`; a review arrives as `X-Forgejo-Event:
pull_request_approved` with `X-Forgejo-Event-Type: pull_request_review_approved`).
