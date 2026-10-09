# Authoring guide

How to add a workshop, write its content, wire in modules, write a new module, and test what you built. The golden
rule: **the base engine stays workshop-agnostic.** A workshop or module changes runtime behaviour through its own
`extensions.json`, Compose fragments and terminal Dockerfile, never by editing `engine/` and never with a new
per-workshop engine flag. (If you believe the engine needs a change, ask the maintainer first, docs included.)

## 1. Decide what kind of pack

| Kind | When | Example |
|---|---|---|
| **Content-only** | The default terminal image and Forgejo are enough | `git-fundamentals` |
| **Content + modules** | A module already provides the services/tools | `tofu-basics` (`dojo-cloud`) |
| **Content + own infrastructure** | The lab needs a service no module provides | `cert-autorenewal` |

Reach for the simplest. If a second workshop would want the same extra service, make it a module.

## 2. Create the pack

```sh
./dojo new-workshop my-lab --title "My Lab" --description "One sentence for the login page." \
    --modules "sensei" --order 8 --duration "~2 h"        # add --terminal for a tools Dockerfile
./dojo my-lab --dry-run                                   # checks manifests, pins and compose
./dojo my-lab                                             # it starts as scaffolded
```

The scaffold copies `workshops/assets/template/` with TODOs: `workshop.env`, README, the slide hub (`index.md`), deck
(`presentation.md`), labs index (`lab-index.md`), lab overview (`labs.md`), cheat sheet, a first lab and a sample repo,
already wired to the shared themes in `workshops/assets/themes/`.

### Pack anatomy

| Path | Required | What |
|---|---|---|
| `workshop.env` | **yes** | Identity and wiring (below) |
| `README.md` | **yes** | Technical reference: what it teaches, how to run, what is in the folder |
| `FACILITATOR.md` | **yes** | Run-of-show: before/during/after/troubleshooting; "Honest status" and a timing table |
| `content/slides/presentation.md` | **yes** | The Marp deck |
| `content/lab/README.md` | **yes** | Lab overview, seeded into every `~/lab` |
| `content/sample-repo/` | **yes** | Seeded into Forgejo as `FORGEJO_ORG/FORGEJO_REPO` |
| `content/lab/cheat-sheet.md` | no | Condensed command reference |
| `compose/docker-compose.override.yml` | no | Extra services, via `COMPOSE_OVERLAY` |
| `compose/terminal/Dockerfile` | no | Extra tools, found by convention |
| `compose/terminal/start.d/`, `account.d/`, `reset.d/`, `lab-prep` | no | Start hooks, per-account setup, student-reset hooks, late-joiner helper |
| `extensions.json` | no | Cards, `/admin` tabs, routes, status checks (section 4) |
| `content/bots/steps.sh` | no | Demo-bot steps for this workshop |
| `achievements/` + `ACHIEVEMENTS.md` | no | Achievement catalog |
| `sensei/answers.json`, `patterns.json` | no | Pack-specific Sensei answers and error patterns |
| `tests/` | no | Scripted lab tests |

### `workshop.env`

```sh
WORKSHOP_NAME="My Lab"                      # shown on the login page
WORKSHOP_DESCRIPTION="One sentence."        # shown on the login page
WORKSHOP_ORDER=8                            # place in the learning path (0 = showcase)
WORKSHOP_DURATION="~2 h"                    # keep in step with FACILITATOR.md
WORKSHOP_CONTENT_DIR=../workshops/my-lab/content   # relative to engine/, NOT the pack
FORGEJO_ORG=my-team
FORGEJO_REPO=my-lab
MODULES="runner-pool sensei"
COMPOSE_OVERLAY=../workshops/my-lab/compose/docker-compose.override.yml
TERMINAL_FLAVOR=                            # optional "zellij"; wins over dojo.toml
FORGEJO_FORK_WORKFLOW=1                     # optional: each student forks the team repo
```

`workshop.env` is shell: derive per-run secrets with `$(printf '...%s' "${GATEWAY_TOKEN:?}" | sha256sum | cut -c1-40)`.
**Compose resolves every relative path in a multi-file merge against the base file's directory (`engine/`)**, whichever
file declares it; this trips people up.

## 3. Write the content

### Labs (`content/lab/labN.md`)

- Each lab is self-contained, with a goal, numbered steps, expected output, checkpoints, and a **"You see | Cause / fix"**
  table whose first cell is the backticked message (Sensei's `why` derives its error table from these).
- **Always tag code fences with a language** (`bash`, `sh`, `hcl`, `yaml`, `text` for output). The lab reader uses
  Prism (`workshops/assets/lab-reader.js`); Marp pages use highlight.js with extra grammars (hcl/terraform, bash/sh with
  commands and flags, gitignore, cron) in `engine/presentation/engine.js`.
- Use `studentXX` for the student's account in commands; the reader substitutes the real name.
- Inside the terminal use `git-server:3000`, never `localhost`.
- **Never put challenge answers in a lab.** Sensei skips headings that name a challenge, but that is a backstop.
- A lab that ends with an achievements challenge can end its section with `<!-- dojo-challenge: c1 -->` (or
  `capstone`); the lab reader shows Start/Reset buttons only when the achievements module is on.
- List every lab in `content/lab/README.md` **and** `content/slides/lab-index.md`.
- A late-joiner helper: put `lab-prep` in `compose/terminal/` and keep its header table in step with the labs.
- After editing a lab on a running stack, copy it to `content/slides/lab/<name>.md.txt`; those copies are git-ignored
  and regenerated at start, so never edit them as source.

### Slides (Marp)

- Decks use the shared theme (`@import url('assets/themes/presentation.css')` and siblings for hub, cheat-sheet,
  labs). Pages: `index.md` (hub), `presentation.md`, `lab-index.md`, `labs.md`, `cheat-sheet.md`.
- **Keep each slide inside 16:9.** Check overflow with a real render, not by eye:
  `workshops/assets/slide-overflow.sh <workshop> [page.md ...]` (needs the stack up; uses Playwright in a container;
  there is no browser on the dev machine).
- Slides are served at `/slides/<file>.md#<n>` behind the class login.
- Speaker notes carry the talking points; the facilitator guide carries logistics.

### Sample repo

`content/sample-repo/` is pushed to Forgejo by `bootstrap` only if the repo is empty. Keep it small and meaningful;
for CI-driven packs include the workflow files (`.forgejo/workflows/`).

## 4. The `extensions.json` manifest

Declare landing cards, `/admin` tabs, widgets, scripts, routes, status checks and reset hooks here. The engine
validates it and renders fixed templates; a manifest never supplies raw Caddy or HTML.

```json
{
  "version": 1,
  "cards": [
    { "id": "inspect", "label": "Site Inspector", "desc": "Visit your site like a browser.",
      "href": "/inspect/", "icon": "key" }
  ],
  "admin_tabs": [ { "id": "inspect", "label": "Site Inspector", "src": "/inspect/" } ],
  "routes": [
    { "id": "inspect", "path": "/inspect", "upstream": "site-inspector:8080", "gate": "identity",
      "strip_prefix": true }
  ],
  "status_checks": [ { "label": "Site Inspector", "url": "http://site-inspector:8080/healthz" } ]
}
```

| Key | Fields |
|---|---|
| `cards` | `id`, `label` (≤40), `desc` (≤120, optional), `href` (same-origin, starts with `/`), `icon` ∈ `code terminal git slides rocket cloud key dns` |
| `admin_tabs` | `id`, `label`, `src` (same-origin); framed in `/admin` |
| `widgets` | `id`, `src`, `size` (`small`/`medium`/`large`); a page framed above the student's landing cards. Serve it through a `routes` entry |
| `scripts` | `id`, `src`; loaded by every student page (landing, `/workspace`, slides, lab reader) via `/workspace/extra.js`, passing `data-surface`. Do nothing when running in a same-site frame |
| `routes` | `id`, `path` (`/name` serves `/name` and `/name/*`), `upstream` (`service:port` in this run), `gate`, `strip_prefix` (default false), `host` (upstream `Host`; `{user}` is the caller's account; not allowed on `shared`) |
| `status_checks` | `label`, `url` (`http(s)://service[:port]/path`); green when it answers 200 |
| `resets` | `id`, `label` (≤40), `upstream`, `path` (contains `{user}` once), `timeout` (1-120 s, default 30), `optional` (checkbox, off by default) |

**Gates**: `shared` (anyone past the class login, no identity forwarded), `identity` (a slot holder or the facilitator),
`facilitator` (facilitator only). For the last two the upstream receives `X-Auth-User` and its own `X-Gateway-Token`.
**The service must verify the token**: students can reach it directly.

**Rules that stop a start**: missing `"version": 1`; unknown key or field; an `id` not matching
`^[a-z][a-z0-9-]{0,30}$`, repeated within a kind, or reusing a built-in tab id (`roster ide term forgejo slides`);
a `host` on a `shared` route; a `path` overlapping another route or an engine path (`/`, `/admin`, `/git`, `/ide`,
`/term`, `/slides`, `/assign`, `/auth-check*`, `/forgejo-login`); an upstream not in this run; an off-site or
scheme-relative link. `${NAME}` expands from `workshop.env`/`module.env`; an unset name is an error.

**Warning (not an error)**: a card with no `/admin` tab of the same `id`. The facilitator must reach whatever a
student can. Cards also become tabs in the student `/workspace`, so the card's page must allow framing by the same origin.

**Student reset hooks**: when the facilitator resets a student the allocator calls each `resets` entry twice, in
manifest order, `POST <upstream><path>?phase=teardown` (before the Forgejo account is deleted) and `?phase=provision`
(after the terminal is set up again). Answer `200 {"ok": true, "detail": "..."}`; anything else stops the reset, and
the facilitator can Retry, so both phases must be idempotent. Verify `X-Dojo-Reset-Token` in constant time against
`RESET_TOKEN` (your fragment passes `RESET_TOKEN=${RESET_TOKEN_<SERVICE>:-}`, service upper-cased, `-` and `.` as `_`).
Per-student state inside the terminal uses `account.d`/`reset.d` hooks instead.

## 5. Adding infrastructure to a pack

Only if no module provides it.

**Extra services** (`compose/docker-compose.override.yml`):

- Do **not** set `image:` on `web-terminal`; `dojo` passes the final terminal image as `WEB_TERMINAL_IMAGE`.
- On engine services use the **list form** of `networks:` and list only what you add (lists append). Mixing list and
  map fails at `up` under podman-compose. `web-terminal` is the exception: it uses map form, so add `net: {}`.
- **Name every volume**, including paths an image declares as `VOLUME`, or `./dojo stop` leaves one behind. Check with
  `podman image inspect <img> --format '{{json .Config.Volumes}}'`.
- **Pin every external image by digest**, tag in front: `docker.io/library/alpine:3.20@sha256:<index digest>`. `--dry-run` fails otherwise.
- Never join `terminal_ingress` or use `web-terminal-ingress`; `dojo` refuses a fragment that mentions it.
- Avoid `${VAR:?}` for a variable that only `workshop.env`/`module.env` sets: `./dojo stop` loads only the operator
  files and would abort before removing anything.
- Keep any service a student terminal must reach **off TCP 9000-9099 and 9500-9899**.
- Services behind `identity`/`facilitator` check `X-Gateway-Token`; render student-supplied strings with `textContent`
  only and keep the strict CSP (no inline script or style).
- Never call the container engine while holding a shared lock; keep one list call per request (cached ~2 s).

**Extra terminal tools** (`compose/terminal/Dockerfile`):

```dockerfile
ARG BASE=gitopsdojo/web-terminal:base
FROM ${BASE}
# pin each tool's version and sha256 per architecture; the terminal has no internet at lab time
```

Do not set `ENTRYPOINT`. A `HEALTHCHECK` is inherited; restate it only as
`HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 CMD web-terminal-healthcheck`. Start-up work
goes in `/etc/dojo/start.d/90-<name>.sh` (workshops `90-`, modules `50-`; run as root after accounts exist; a failing
hook stops the container).

## 6. Writing a module

```text
modules/<name>/
  README.md  module.env  compose.yml  extensions.json  terminal/Dockerfile
```

- `README.md`'s first line after the heading is the one-line summary `./dojo modules` shows.
- `module.env`: defaults a workshop may override; `SHARED="<context>/<file> ..."` lists shared helper files to copy in
  (read as written: no `$(...)`).
- `compose.yml`: same rules as an overlay. Extending an engine service merges: `environment` per key (later wins),
  `volumes`/`networks`/`depends_on` append. A workshop can swap a module service's image from its overlay by
  overriding `build.context` or `build.args` (see `workshops/dns-as-code/compose/docker-compose.override.yml`).
- A service whose terminal needs its credential should follow the **broker pattern**: a root-owned unix-socket
  broker that reads the caller's uid with `SO_PEERCRED` (see `dojo-cloud`, `openbao`).
- Use `modules/_shared/dojo_http.py` for identity checks and security headers, and `adapter_client.py` to report
  events to achievements.
- Tell achievements what happened with signed adapter events rather than coupling to it.
- Document the settings in `module.env` comments and the README. Add the module to the tables in
  [Modules](modules.md).

## 7. Demo bots and tests

### Bots

`content/bots/steps.sh` defines step functions and `STEPS` per `$PERSONA` (`expert`, `intermediate`, `novice`).
`bot-runner.sh` sources it after defining its helpers (`run_cmd`, `narrate`, `think`, `orient`, `branch_name`,
`api_curl`) and generic steps (`step_ensure_clone`, `step_sync_main`, `step_lab1_push_and_pr`, `step_wrap_round`). The
file is mounted read-only at `/opt/workshop-content`. Steps must be **safe to re-run from the top** and return non-zero
on failure (the runner retries with backoff). For fork workshops set `FORGEJO_FORK_WORKFLOW=1`.

### Checking a pack

| Check | Command |
|---|---|
| Static (no start) | `./dojo <name> --dry-run`: manifests, pins, compose, achievements catalog |
| Fast bots | `./dojo <name> --test 3 --fast`, wait for `~/.dojo-bot-done` markers (not log settling) |
| Bot smoke test | `workshops/assets/smoke.sh <name> [--bots N] [--split each]`: runs the fast bots, then checks the achievements ledger (`fired.py`) for missing core milestones |
| Re-run one lab | `workshops/assets/retest.sh <name> <lab> [--only | --to LAST]` |
| Slide overflow | `workshops/assets/slide-overflow.sh <name>` |
| Scripted lab tests | `tests/lab_N.sh` sourcing `workshops/assets/test-lib.sh` (helpers `as`, `ok`, `has`, `lacks`, `denied`, `check`, `absent`, `api`, `job_logs`, `new_logs`, `md_blocks`, `md_line`, `md_range`; end with `finish`). `sh workshops/assets/test-lib-selftest.sh` checks the library offline |

Always use the **fast** bots for checks; plain `--test` is for demos. Stop the stack when you are done testing.

## 8. Achievements for a pack

Add `workshops/<name>/achievements/` (`catalog.json`, `labs/lab1.json`..., `funny.json`, `challenges/`, `capstone.json`,
`seeds/`). The validator runs at start. Rules: every challenge needs a per-student `space` containing `{user}`; every
verify assertion must mention `{user}`; exactly two hints; ids are permanent. Regenerate the review copy with
`python3 -B modules/achievements/catalog/render_md.py --all`, or edit with `modules/achievements/edit.sh <name>`.

## 9. Definition of done for a workshop

- `./dojo <name> --dry-run` is clean (manifests, pins).
- It runs end to end, including the facilitator's `/admin` view, and `--test --fast` bots finish.
- Every card has a matching `/admin` tab.
- Slides pass the overflow check; every code fence has a language.
- `FACILITATOR.md` has timings, a rehearsal checklist and an honest status; `WORKSHOP_DURATION` matches it.
- Rows added to [`workshops/README.md`](../workshops/README.md) and [Workshop catalog](workshops.md).
- Anything left undone is in `ROADMAP.md`.
