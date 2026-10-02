# Workshops

Each subfolder here is a self-contained **workshop pack**: content plus
(optionally) whatever's different about how it runs. The shared runtime
lives in [`../engine/`](../engine/) and stays untouched no matter how many
workshops exist — see [`engine/README.md`](../engine/README.md) for what it
runs and how requests are routed. Reusable services and tools that more than
one workshop can use live in [`../modules/`](../modules/).

## Available workshops

| # | Workshop | What it teaches | Modules | Run it |
| - | -------- | ---------------- | ------- | ------ |
| 0 | [`dojo-introduction/`](dojo-introduction/) | A show-and-tell of the platform, not a lab: a platform-tour deck, one page linking every workshop's slides and labs, and Forgejo, runners, DNS and Dojo Cloud running at once | `runner-pool`, `dojo-cloud`, `dns-ui`, `dns-gate`, `sensei` | `./run.sh dojo-introduction` |
| 1 | [`git-fundamentals/`](git-fundamentals/) | Core git workflow: clone, branch, commit, push, PR | — | `./run.sh git-fundamentals` |
| 2 | [`dns-as-code/`](dns-as-code/) | Managing DNS records via git + dnscontrol, building on Session 1 | `runner-pool`, `dns-ui`, `dns-gate` | `./run.sh dns-as-code` |
| 3 | [`cert-autorenewal/`](cert-autorenewal/) | Automated TLS certificate issuance/renewal via ACME (step-ca, certbot, acme.sh) | `dns-ui`, `dns-gate` | `./run.sh cert-autorenewal` |
| 4 | [`tofu-basics/`](tofu-basics/) | OpenTofu/Terraform basics: `init`/`plan`/`apply`/`destroy` and repo layout (`terraform` runs OpenTofu) | `dojo-cloud` | `./run.sh tofu-basics` |
| 5 | [`vault-fundamentals/`](vault-fundamentals/) | *(in progress)* Secrets management with OpenBao: signing in by identity, leaks in git, secrets encrypted on your own machine (`pass`), KV secrets and policies, your own namespace, secrets in code and in git, CI that logs in with its own identity, deploys with a platform identity, dynamic database logins and an incident drill (labs 0-13) | `openbao`, `runner-pool` | `./run.sh vault-fundamentals` |

### Learning path

The numbers are the order to teach them in. `0` is the showcase for facilitators and visitors, not a course.
`1` to `5` build on each other; a later workshop assumes the earlier ones' ideas, not their files.

| # | Workshop | Builds on |
| - | -------- | --------- |
| 0 | `dojo-introduction` | Nothing. A tour of the platform and every workshop; no student learning goals. |
| 1 | `git-fundamentals` | Nothing. Clone, branch, commit, push, pull request, undo, stash, history, conflicts. |
| 2 | `dns-as-code` | 1: the same git flow, now with CI. First look at declarative config, preview vs apply, drift, and a pull request that runs a pipeline. |
| 3 | `cert-autorenewal` | 2 (lightly): its dns-01 capstone drives the PowerDNS API that `dnscontrol` wraps in workshop 2. Otherwise stands alone: ACME, `certbot`, `acme.sh`, renewal automation. |
| 4 | `tofu-basics` | 1 for the git steps, and 2 for the ideas of declarative config, plan before apply and drift, taken further with state, `for_each`, policy and quotas on a real provider. |
| 5 | `vault-fundamentals` | 1 (stated prerequisite). Also leans on 2's pull request and CI pipeline ideas for the Forgejo Actions labs; the longest and most advanced course. |

`./run.sh list` prints this same list from each workshop's `workshop.env`;
`./run.sh modules` lists the modules and which workshops use them.

## How workshop selection works

```sh
./run.sh setup             # first time only: writes engine/.env (accounts, secrets), shared by every workshop
./run.sh <workshop-name>
```

`run.sh` (the root one forwards to `engine/run.sh`):

1. Loads `engine/.env` (`TTYD_*`, `STUDENT_*`, `FACILITATOR_*`,
   `FORGEJO_ADMIN_*`, `PUBLIC_BASE_URL`, ports — the same regardless of
   which workshop runs).
2. Reads `MODULES` from `workshops/<name>/workshop.env`, sources each
   module's `module.env` (its defaults), then `.env` and `workshop.env` again,
   so the workshop always has the last word on any setting.
3. Checks and renders every `extensions.json` (each module's, then the
   workshop's) into `engine/.generated/`. A bad manifest stops the start
   here, before anything runs.
4. Builds the images that changed since the last run. The terminal is a chain:
   `gitopsdojo/web-terminal:base` → one link per module with a `terminal/`
   folder (`:<workshop>.<module>`) → the workshop's own `compose/terminal/`
   (`:<workshop>`). The last link is the image the stack runs.
5. Runs `compose -f docker-compose.yml [-f modules/<m>/compose.yml ...] [-f <overlay>] up -d`
   and records that file list in `engine/.build-state/current.json`, so
   `./run.sh stop` tears down exactly what was started.

## Three kinds of workshop

**Content-only** (like `git-fundamentals`): a `workshop.env` and a
`content/` folder (slides, lab instructions, seed repo). Uses the engine
exactly as-is. This is the common case; reach for it first.

**Content + modules** (like `tofu-basics`): the same, plus
`MODULES="..."` in `workshop.env`. The module brings its services, terminal
tools, landing card, `/admin` tab and routes. Reach for this when a module
already does what the lab needs.

**Content + own infrastructure** (like `cert-autorenewal`, and `dns-as-code`
on top of a module): a `compose/` folder with a Compose overlay for extra
services, a `compose/terminal/` Dockerfile for extra tools, and an
`extensions.json` for any front door they need. Reach for this only when the
lab genuinely needs something no module provides. If a second workshop would
want the same thing, make it a module instead.

## Adding a new workshop

1. `mkdir -p workshops/<name>/content/{slides,lab,sample-repo}`
2. Write `content/slides/presentation.md` (Marp — copy an existing deck's
   frontmatter/style block for visual consistency), `content/lab/README.md`
   (seeded into every student's `~/lab`), and `content/sample-repo/`
   (seeded into Forgejo by the `bootstrap` service — same mechanism for
   every workshop, nothing to configure). A lab with an achievements
   challenge can end that section with `<!-- dojo-challenge: c1 -->` (or
   `capstone`): the lab reader turns it into Start/Reset buttons when the
   `achievements` module is on, and shows nothing otherwise (see
   `modules/achievements/README.md`).
3. Write `workshop.env`:
   ```sh
   WORKSHOP_NAME=<display name>
   WORKSHOP_DESCRIPTION="<one sentence, shown on the login page>"
   WORKSHOP_ORDER=<n>    # place in the learning path (0 = showcase); ./run.sh list sorts by it
   WORKSHOP_CONTENT_DIR=../workshops/<name>/content
   FORGEJO_ORG=<org name>
   FORGEJO_REPO=<repo name>
   MODULES=""            # e.g. "forgejo-runner dojo-cloud"; see ./run.sh modules
   COMPOSE_OVERLAY=      # only if step 4 adds one
   ```
   Paths are relative to `engine/`, not to the workshop folder — Compose
   resolves every relative path in a multi-file `-f ... -f ...` merge
   relative to the *base* file's directory (`engine/docker-compose.yml`'s),
   regardless of which file declares the path. This trips people up — see
   the comment at the top of `dns-as-code/compose/docker-compose.override.yml`
   for a worked example.
4. If (and only if) the lab needs something no module provides:
   - **Extra services:** `compose/docker-compose.override.yml`, pointed at by
     `COMPOSE_OVERLAY`. Don't set `image:` on `web-terminal` there: `run.sh`
     picks the terminal image (`WEB_TERMINAL_IMAGE`).
   - **Extra terminal tools:** `compose/terminal/Dockerfile`, found by
     convention (no setting). Start it with
     ```dockerfile
     ARG BASE=gitopsdojo/web-terminal:base
     FROM ${BASE}
     ```
     so it stacks on top of any module's tools. Pin every tool's version and
     check its sha256 per architecture (students have no internet). Don't set
     `ENTRYPOINT`. A `HEALTHCHECK` is inherited; if you restate it, use exactly
     `HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 CMD web-terminal-healthcheck`
     (the base image's script, which sends the `X-Control-Token` header). Do not
     copy a `wget` line: a bare `wget` gets a 403 and the container shows
     `unhealthy` for its whole life.
   - **Start-up work in the terminal** (background jobs, files that need the
     student accounts to exist): copy a script to
     `/etc/dojo/start.d/90-<name>.sh`. The base entrypoint runs every hook as
     root, in name order (modules use `50-`), after the accounts exist; a
     failing hook stops the container. See
     `cert-autorenewal/compose/terminal/start.d/`.
   - **A student-facing web tool:** `extensions.json` in the workshop folder
     (see [Front door](#front-door-extensionsjson) below).

   Keep any service a student terminal must reach **off TCP ports 9000-9099 and
   9500-9899**: the terminal's per-account firewall (`DOJO_ISOLATION` in
   `engine/web-terminal/entrypoint.sh`) drops those for every non-root account,
   on any host, and the symptom is a silent timeout. `cert-autorenewal`'s
   step-ca uses 9443 for this reason. When adding a service, run
   `podman image inspect <img> --format '{{json .Config.Volumes}}'` and give
   every declared path a named volume, or each start leaves an anonymous
   volume behind that `./run.sh stop` can't find.
   Pin every external image (`FROM` and `image:`) by digest, keeping the tag
   in front for people: `docker.io/library/alpine:3.20@sha256:<index digest>`.
   `--dry-run` fails otherwise (`engine/scripts/check-pins.sh`).
5. Optional: write `content/bots/steps.sh` so `./run.sh <name> --test` bots
   work through *your* labs instead of the default git-fundamentals ones (see
   `engine/README.md`'s "Demo bots" section and `workshops/tofu-basics/content/bots/steps.sh`).
6. Add a row to the table above.
7. `./run.sh <name> --dry-run` shows what would build and start and checks the
   manifests and image pins. Then run it locally end to end, including the facilitator's
   `/admin` view, before trusting it for a live session.
8. Optional: scripted lab tests in `tests/`, run from the repo root against the running stack.
   Source `workshops/assets/test-lib.sh` (POSIX sh) for the shared helpers: run commands in a
   student's login shell (`as`, `ok`, `has`, `lacks`, `denied`), check captured output
   (`check`, `absent`), the Forgejo admin `api`, Actions job logs (`job_logs`, `new_logs`), and
   the labs' own commands (`md_blocks`, `md_line`, `md_range`), so a test follows its lab. End
   with `finish`. `workshops/vault-fundamentals/tests/lab_8.sh` is a short example.
   `sh workshops/assets/test-lib-selftest.sh` checks the library offline (CI runs it).

Nothing about adding a workshop this way ever requires editing
`engine/docker-compose.yml`, the base `web-terminal` image, the allocator
or the gateway.

## Sensei help in your workshop

List the `sensei` module in `MODULES=` (the shipped workshops all do) and students get `sensei ask|why|hand|inbox`.
`ask` searches your `content/lab/*.md`; `why` explains the last error on screen, with a table it derives from any
"You see | Cause / fix" table in your labs (the first cell is the backticked message). Add
`workshops/<name>/sensei/patterns.json` for errors the labs don't tabulate (format in `modules/sensei/README.md`).
Labs must never hold challenge answers; Sensei skips headings that name a challenge, but that is a backstop.

## Front door: `extensions.json`

A workshop or module declares its landing cards, facilitator `/admin` tabs,
landing-page widgets, gateway routes and status checks in an `extensions.json`. The engine checks
it and renders it through fixed templates; a manifest never supplies raw
Caddy config or HTML. `cert-autorenewal/extensions.json`:

```json
{
  "version": 1,
  "cards": [
    { "id": "inspect", "label": "Site Inspector", "desc": "Visit your site like a browser: redirects, certificate, HSTS and headers, step by step.",
      "href": "/inspect/", "icon": "key" }
  ],
  "admin_tabs": [
    { "id": "inspect", "label": "Site Inspector", "src": "/inspect/" }
  ],
  "routes": [
    { "id": "inspect", "path": "/inspect", "upstream": "site-inspector:8080", "gate": "identity",
      "strip_prefix": true }
  ],
  "status_checks": [
    { "label": "Site Inspector", "url": "http://site-inspector:8080/healthz" }
  ]
}
```

| Key | Fields |
|---|---|
| `cards` | `id`, `label` (≤40), `desc` (≤120, optional), `href` (same-origin, starts with `/`), `icon`: one of `code terminal git slides rocket cloud key dns` |
| `admin_tabs` | `id`, `label`, `src` (same-origin); framed in the facilitator's `/admin` page |
| `widgets` | `id`, `src` (same-origin), `size` (`small`, `medium` or `large`, default `small`); a page framed at the top of the student's landing page, above the cards. It is a page you also serve through a `routes` entry, so it has its own gate and identity |
| `scripts` | `id`, `src` (same-origin path); a script every student page loads (landing, `/workspace`, slides, lab reader) through one loader, `/workspace/extra.js`, which passes the page's name as `data-surface`. A script that finds itself in a frame of the same site should do nothing, so the top page owns it |
| `routes` | `id`, `path` (`/name`, serves `/name` and `/name/*`), `upstream` (`service:port`, must be a service in this run), `gate`, `strip_prefix` (default `false`), `host` (upstream `Host`; `{user}` stands for the caller's account) |
| `status_checks` | `label`, `url` (`http(s)://service[:port]/path`); green in the `/admin` status strip when it answers 200 |
| `resets` | `id`, `label` (≤40, listed in the Roster's Reset dialog), `upstream` (`service:port` in this run), `path` (contains `{user}` once), `timeout` (1-120 s, default 30); a student reset hook, see below |

**Student reset hooks.** When the facilitator resets one student from the Roster, the allocator calls each `resets`
entry twice, in manifest order: `POST <upstream><path>?phase=teardown` before the student's Forgejo account is deleted,
and `?phase=provision` after the terminal is set up again. `{user}` is the student's account (`studentNN` or a bot).
Answer `200` with `{"ok": true, "detail": "short text"}`; anything else fails that step and stops the reset (the
facilitator can Retry, so both phases must be safe to run again). The request carries `X-Dojo-Reset-Token`: compare it,
in constant time, with `RESET_TOKEN`, which your compose fragment passes in as `RESET_TOKEN=${RESET_TOKEN_<SERVICE>:-}`
(service name upper-cased, `-` and `.` as `_`). The token is your service's own, so it can't reset anything elsewhere,
and since students can reach your service on `workshop_lab`, an endpoint that skips the check lets any student wipe
any other. Per-student state inside the terminal uses `/etc/dojo/account.d` and `reset.d` hooks instead.

**Student workspace.** Every student can open `/workspace`, the tabbed version of the landing page: Labs, VS Code,
Terminal, Forgejo and Slides, then one tab per `cards` entry (framing that card's `href`). A card therefore needs no
extra manifest field to appear there, but its page must allow being framed by the same origin (the `/admin` tab for
the same card already needs that). Its `/` counterpart, *split mode*, is unchanged; a student's choice is remembered in
their browser.

**Gates** pick who gets through a route:

| Gate | Who | The upstream receives |
|---|---|---|
| `shared` | anyone past the shared login | no identity (`Authorization`, `X-Auth-User`, `X-Gateway-Token` stripped) |
| `identity` | a browser holding a student slot, or the facilitator | `X-Auth-User: <account>` and `X-Gateway-Token`, both set by Caddy |
| `facilitator` | the facilitator only (403 for students) | same as `identity` |

The service behind an `identity` or `facilitator` route must still check
`X-Gateway-Token` against `GATEWAY_TOKEN`: students can reach it directly on
`workshop_lab`, and only the token proves the request came through the gateway.

Rules that stop a start: a missing `"version": 1`; an unknown key or field;
an `id` that is not `^[a-z][a-z0-9-]{0,30}$`, repeats one of the same kind in
another manifest, or (for a tab) reuses a built-in tab (`roster ide term forgejo slides`);
a `host` on a `shared` route;
a `path` that overlaps another route or an engine path (`/`, `/admin`, `/git`,
`/ide`, `/term`, `/slides`, `/assign`, `/auth-check*`, `/forgejo-login`); an
upstream service that is not in this run; an off-site or scheme-relative link.
`${NAME}` expands from `workshop.env` / `module.env`; an unset name is an error.
A card with no `/admin` tab of the same `id` prints a **warning**: whatever a
student can reach, the facilitator must be able to reach too.

## Writing a module

A module is a folder under `modules/` that more than one workshop can list in
`MODULES`. Every part is optional and found by name:

```
modules/<name>/
  README.md           # first line after the heading: a one-line summary (./run.sh modules shows it)
  module.env          # settings with defaults; workshop.env overrides them
  compose.yml         # services, volumes, networks; may extend engine services
  extensions.json     # cards, /admin tabs, routes, status checks (format above)
  terminal/Dockerfile # ARG BASE / FROM ${BASE}; hooks as /etc/dojo/start.d/50-<name>.sh
```

Rules for `compose.yml`:

- Relative paths resolve against `engine/`, as in an overlay.
- Extending an engine service (say `git-server` or `web-terminal`) merges:
  `environment` per key, later file wins; `volumes`, `networks` and
  `depends_on` **append**, so list only what you add.
- Use the **list form** of `networks:` on any engine service
  (`networks: [runner_net]`). The engine uses list form, and mixing list and
  map for one service fails at `up` under podman-compose (not at `config`).
  Pinned addresses belong on the module's own services only. The exception is
  `web-terminal`, which uses the map form (for its `terminal_ingress` alias):
  to add a network there, use the map form too (`runner_net: {}`).
- Never join `terminal_ingress` or use `web-terminal-ingress`. It is the
  gateway's private path to the students' IDE and terminal ports, which answer
  nowhere else (remediation T2.2a); `run.sh` refuses a fragment that mentions
  it. A module service that needs the terminal reaches it on `workshop_lab`,
  like the allocator does.
- Name every volume, including paths an image declares as `VOLUME`, so
  `./run.sh stop` removes them.
- A workshop can swap a module service's image from its overlay by overriding
  `build.context` (later file wins); see `modules/forgejo-runner/README.md`.

Shared helpers: a file several module services need (say `dojo_http.py`) has one
copy in `modules/_shared/`. A module lists the ones it uses in its `module.env`
as `SHARED="<context>/<file> ..."` (e.g. `SHARED="gate/dojo_http.py"`), and each
start copies them into `<context>/_shared/` before building. Those folders are
git-ignored and rebuilt every start (never edit a copy), so the Dockerfile does
`COPY _shared/dojo_http.py ...`. `SHARED` is read from that module's own
`module.env` as written: no `$(...)`, and a workshop can't override it.

Existing modules: [`dojo-cloud`](../modules/dojo-cloud/), [`dns-gate`](../modules/dns-gate/),
[`dns-ui`](../modules/dns-ui/), [`openbao`](../modules/openbao/), [`runner-pool`](../modules/runner-pool/) and
[`forgejo-runner`](../modules/forgejo-runner/) (a long-lived runner for one repo; no workshop uses it since
dns-as-code moved to `runner-pool`).
