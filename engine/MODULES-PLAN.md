# Workshop extensions and modules: plan

| | |
|---|---|
| Branch | `feat/workshop-modules` (from `main` at a840252, 2026-09-24) |
| Overall status | **M3 in progress: docs (T3.1) and the vault plan (T3.2) done; the user is running the browser pass (T3.4, checklist in §7). PR (T3.3) only when asked.** |
| Related | `workshops/vault-fundamentals/PLAN.md` §8.1 and §13 (where this idea started; vault is paused and will build on this) |

## 0. HOW TO RESUME (read this first)

1. Read this whole file once.
2. `git status` and `git log --oneline -20`. Every finished task records its commit SHA next to its checkbox in §7.
   If a box is ticked but the SHA is not in `git log`, treat the task as **not done**.
3. Check §1 (decisions) and §8 (open questions). Don't start work that depends on an open question.
4. **Ask the user before moving from one phase to the next** (M0 → M1 → M2 → M3), and **before editing any
   `engine/` file** other than this plan.
5. Find the first `[ ]` or `[~]` task in §7. Run the **Verify** line of the previous finished task first.
6. Work the task. When done: tick it, add the commit SHA, append a dated entry to §10.

Resume prompt:

```
Read engine/MODULES-PLAN.md fully and follow its "HOW TO RESUME" section. Ask me before a new phase,
before editing engine/ files, and about anything in section 8.
```

---

## 1. Decisions

| # | Decision | Set by |
|---|----------|--------|
| M1 | The plan lives in `engine/MODULES-PLAN.md`. | user, 2026-09-24 |
| M2 | Manifests are **JSON files**. | user, 2026-09-24 |
| M3 | This branch builds **both layers**: extensions (front door) and modules (reusable services + tools). | user, 2026-09-24 |
| M4 | Carried over from vault S14/S17: no new per-workshop flags; once proven, **every workshop moves onto the mechanism** and `DEMO_APP_ENABLED` / `CLOUD_ENABLED` are deleted. | user, 2026-09-23 |
| M5 | Gates are **fixed templates owned by the engine**. A manifest picks a gate by name and fills in checked values; it can never supply raw Caddy config, HTML or SVG. | proposed |
| M6 | What `run.sh` needs in bash stays in env files (`MODULES=` in `workshop.env`, settings in `module.env`); what the engine renders goes in JSON (`extensions.json`). No JSON parsing in bash. | proposed |
| M7 | A module is found **by convention**, not by config: top-level `modules/<name>/{module.env, extensions.json, compose.yml, terminal/Dockerfile, start.d/}`, each optional. | user (folder), 2026-09-24 |
| M8 | Terminal tools stack by **chained builds**: every tools Dockerfile starts `ARG BASE` / `FROM ${BASE}`; `run.sh` builds base → module … → workshop. | proposed |
| M11 | Terminal start-up work goes in **`/etc/dojo/start.d/*.sh` hooks** run by the base web-terminal entrypoint (engine edit, M2); no more per-workshop `ENTRYPOINT` wrappers. | user, 2026-09-24 |
| M10 | The facilitator gets **their own demo site** (a vhost under the demo zone), not student01's. | user, 2026-09-24 |
| M9 | The manifest is checked and rendered **before anything starts**, by a one-shot run of the allocator image (it already has Python; the host has no Python prerequisite). A bad manifest stops `./run.sh` with a clear error. | proposed |

## 2. Problem: where workshops edit the engine today

| Workshop need | Hard-coded in |
|---|---|
| A route (`/demo`, `/cloud`) | a handle block per workshop, `engine/gateway/Caddyfile` (`@demo`, `@cloud`) |
| A landing card | `if DEMO_APP_ENABLED / CLOUD_ENABLED`, `engine/allocator/server.py` (tools list) |
| A facilitator `/admin` tab | `CLOUD_TAB_PLACEHOLDER` / `CLOUD_PANEL_PLACEHOLDER` swaps, `server.py` |
| Identity for its service | a branch per tool in `/auth-check` (`X-Demo-Host`, `X-Cloud-User`) |
| Settings | env pass-through per flag, `engine/docker-compose.yml` (allocator) |
| Extra services | exactly one `COMPOSE_OVERLAY` per workshop, `engine/run.sh` |
| Terminal tools | one Dockerfile per workshop; overlay must set `image: gitopsdojo/web-terminal:<name>` or it clobbers `:base` |

Already generic, and the pattern to copy: `STATUS_CHECKS=Label=URL` (the pack declares, the engine renders).

Out of scope: `FORGEJO_FORK_WORKFLOW` (a bot behaviour switch, not front door). Revisit only if a module needs it.

## 3. Layer 1: extensions (front door)

### 3.1 `extensions.json` (workshop folder or module folder, same format)

```json
{
  "cards": [
    { "id": "cloud", "label": "Dojo Cloud", "desc": "The portal for the resources you deploy.",
      "href": "/cloud/", "icon": "cloud" }
  ],
  "admin_tabs": [
    { "id": "cloud", "label": "Dojo Cloud", "src": "/cloud/#/progress" }
  ],
  "routes": [
    { "id": "cloud", "path": "/cloud", "upstream": "cloud-api:8080", "gate": "identity",
      "strip_prefix": false }
  ],
  "status_checks": [
    { "label": "Dojo Cloud", "url": "http://cloud-api:8080/readyz" }
  ]
}
```

Rules checked at render time (any failure stops the start):
- `id`: `^[a-z][a-z0-9-]{0,30}$`, unique per kind across all merged manifests.
- `path`: `^/[a-z][a-z0-9-]*$`; must not equal or sit under an engine path: `/admin /git /ide /term /slides /auth-check
  /auth-check-watch /forgejo-login /static` and anything else the allocator serves (list kept in the renderer). No two
  routes may overlap.
- `upstream`: `<service>:<port>`, service must be in `compose config --services` for this run, port 1-65535.
- `href` / `src`: same-origin, start with `/`, no `//`, no scheme.
- `icon`: a name from the engine's fixed set (`code terminal git slides rocket cloud`, plus any we add, e.g. `key`).
- `label` / `desc`: plain text, length-capped; rendered with escaping (cards) / `textContent` (tabs).
- Facilitator rule (CLAUDE.md): a card with no admin tab of the same `id` is a **warning** printed by `run.sh`.
- `status_checks.url`: `http(s)://` to a stack service (the allocator already validates this form).

### 3.2 Gates (engine-owned templates)

| Gate | Who gets through | Upstream receives | Replaces |
|---|---|---|---|
| `shared` | anyone past the shared login | `Authorization` stripped | the `/git` pattern |
| `identity` | a browser holding a student or facilitator slot (`/auth-check?route=<id>`) | `X-Auth-User` + `X-Gateway-Token` (set by Caddy, never the client) | `@cloud` + `X-Cloud-User` |
| `facilitator` | the facilitator only (allocator answers 403 otherwise) | same as `identity` | new; for runner panels etc. |

Per-route options (all checked): `strip_prefix` (bool), `host` (upstream `Host` header template; only placeholder
`{user}`, the rest must be a DNS name). `/demo` becomes
`{ "gate": "identity", "strip_prefix": true, "host": "{user}.certs.dojo.test" }` (see Q2 for the facilitator case).

### 3.3 Rendering and wiring

- `run.sh` merges manifests (modules in `MODULES` order, then the workshop's own) and runs
  `allocator image: python3 -B render_extensions.py` with the merged input and the service list.
- Output to `engine/.generated/` (git-ignored): `extensions.caddy` and `extensions.json` (normalised).
- **Gateway:** the Caddyfile gets one `import /etc/caddy/extensions/*.caddy` inside the shared-gate `handle`, before
  the catch-all. `.generated/` is bind-mounted read-only. No workshop → an empty file, so the import always matches.
- **Allocator:** reads `extensions.json` (bind-mounted read-only) at start for cards, admin tabs and status checks;
  `/auth-check?route=<id>` looks the route up and applies its gate. `CLOUD_*`/`DEMO_APP_*` code paths are deleted.
- `STATUS_CHECKS` env keeps working during migration, then is removed in favour of the manifest.

## 4. Layer 2: modules

### 4.1 Layout

```
modules/<name>/
  module.env          # settings with defaults (e.g. DEMO_APP_ZONE=certs.dojo.test); workshop.env overrides
  extensions.json     # same format as §3.1
  compose.yml         # services/volumes/networks; relative paths resolve against engine/ (as overlays do today)
  terminal/Dockerfile # ARG BASE / FROM ${BASE}; pinned, sha256-verified tools
  README.md           # what it provides, which settings, which workshops use it
```

`modules/` is outside `workshops/`, so `./run.sh list` never sees it. A `./run.sh modules` listing is nice-to-have.

### 4.2 Using modules

`workshop.env`: `MODULES="forgejo-runner dojo-cloud"`. `run.sh` then:
1. sources each `module.env`, then `workshop.env` again (workshop wins);
2. compose files: `docker-compose.yml`, each module's `compose.yml`, then the workshop's `COMPOSE_OVERLAY`;
3. records the whole `-f` list (not one overlay) in `.last-overlay` for `teardown.sh`;
4. builds the terminal chain: `:base` → `:<workshop>-m1` → … → `:<workshop>`, each salted with its parent's image ID
   (generalises today's `build_salt` trick); skipped links cost nothing;
5. passes the final tag through `WEB_TERMINAL_IMAGE`, and `docker-compose.yml` uses
   `image: ${WEB_TERMINAL_IMAGE:-gitopsdojo/web-terminal:base}`. This removes the "overlay must set `image:`" trap.
6. overlay-build change detection (`compose_overlay_build_if_changed`) runs per module directory too.

### 4.3 First modules (candidates)

| Module | From | Why first |
|---|---|---|
| `forgejo-runner` | dns-as-code (`runner-setup`, `forgejo-runner`, `runner_net`) | dns-as-code and vault both need CI runners |
| `dojo-cloud` | tofu-basics (`cloud-api`, `cloud-host`, `/cloud` route, card, tab) | proves a module with a front door; vault tie-in |
| `openbao` | vault spike | vault is then built on modules from day one (after this branch) |

`demo-app`/`step-ca`/`dns-seed` stay in cert-autorenewal's overlay (only one user); its `/demo` moves to its
`extensions.json`.

## 5. Risks to check first (M0)

1. **podman-compose 1.5.0 merging** of several `-f` files: list-form `environment:`, `volumes:`, `networks:` and
   `depends_on` on the same service (web-terminal, allocator) from two fragments. Docker Compose merges these;
   podman-compose has differed before. Decides whether modules may touch shared services or must only add their own.
2. **Caddy `import` of a glob** inside a nested `handle`, and a bind-mounted snippet under rootless podman (SELinux
   label / WSL paths).
3. **Chained builds** with `ARG BASE` + `FROM ${BASE}` through `build_if_changed`, keeping the HEALTHCHECK (a plain
   `podman build` drops it; see CLAUDE.md), and `TARGETARCH` still passed.
4. **Two sources for web-terminal's environment**: tofu-basics sets env and volumes on it; a module may too.
5. **Render step on a fresh machine**: the allocator image must exist before rendering (build order in `run.sh`).

## 6. Security notes

- The trust model does not change: identity headers only with `X-Gateway-Token`, set by Caddy with `header_up`.
  Generated Caddy uses the same `header_up` lines as today's `@cloud`; a test asserts a client-sent `X-Auth-User`
  is overwritten on every gate.
- A manifest is repo content, not student input, but it is still validated as if hostile (§3.1): it is the only
  thing standing between a pack and the gateway config.
- Card and tab text is escaped / `textContent`; icons come from a fixed set; strict CSP stays.
- `facilitator` gate is enforced by the allocator, not by path position, and tested with a student session.

## 7. Tasks

Legend: `[ ]` todo, `[~]` in progress, `[x]` done (SHA). Each task says how to verify it.

### M0: spikes (throwaway, in the scratchpad; no engine edits kept)

- [x] **T0.1** (findings in §9) podman-compose merge test (§5.1, §5.4) with two tiny fragments on a scratch project.
  Verify: `podman-compose -f a.yml -f b.yml config` output recorded in §9.
- [x] **T0.2** (findings in §9) Caddy glob import + bind mount (§5.2) with the `caddy:2-alpine` image in the scratchpad.
  Verify: request to an imported route answers; empty snippet still starts.
- [x] **T0.3** (findings in §9) Chained terminal build (§5.3) with two dummy tool layers on `web-terminal:base`.
  Verify: final image has both tools and `podman inspect` shows the HEALTHCHECK.
- [x] **T0.4** Write findings into §9, update §3/§4 if anything changed. **Ask before M1.**

### M1: extensions (engine edits; ask before each)

- [x] **T1.1** (SHA below) `render_extensions.py` (+ unit tests for every rule in §3.1, run in the allocator image).
  Verify: `podman run --rm --network none -v ./engine/allocator:/src:ro -w /src gitopsdojo/allocator:local python3 -B -m unittest discover -s tests` (31 pass).
- [x] **T1.2** (SHA below) `run.sh`: merge + render + `.generated/`; `docker-compose.yml` bind mounts; `.gitignore`.
  Verify: `./run.sh git-fundamentals --dry-run` prints `extensions: 0 manifest(s) ...`; a manifest with an unknown
  upstream makes it exit 1 with `rejected`. The renderer is mounted from source (not baked into the image) so dry runs
  check with current rules; rootless podman needs no `--user` (docker gets `--user uid:gid`).
- [x] **T1.3** (SHA below) Caddyfile `import`; gate templates (in the renderer, T1.1).
  Verify: `caddy adapt` of the real Caddyfile in the gateway image, with an empty and a 4-route snippet. Note: Caddy
  re-sorts path-matched `handle`s, so correctness relies on the renderer's no-overlap rule, not on position.
- [x] **T1.4** (SHA below) Allocator: cards, admin tabs, status checks and `/auth-check?route=` from the manifest.
  Verify (standalone allocator container, sample manifest): identity route 303 without a session, 200 with
  `X-Dojo-User`/`X-Dojo-Host` for a student and the facilitator; facilitator gate 403 for a student; shared/unknown
  route 404; no token 403; card, `/admin` tab + panel and status entry rendered. Live-stack test is T1.5.
- [x] **T1.5** (b0d1915) tofu-basics → `extensions.json`; delete `CLOUD_ENABLED`. Real-stack test incl. facilitator tab.
  Verify: `scratchpad t15.sh`-style checks (11/11: card, cloud-api sees student/facilitator via `/cloud/api/me`,
  forged `X-Auth-User`/`X-Dojo-User`/`X-Gateway-Token` ignored, 303 without session, 401 without login, `/admin` tab
  frames `/cloud/#/progress`, status strip `Dojo Cloud=green`) and `bash workshops/tofu-basics/tests/e2e.sh --only
  security,track_b` (157 passed, 0 failed). Not done: a real-browser pass (no headless browser on this machine).
- [x] **T1.6** (958b675) cert-autorenewal → `extensions.json` (`/demo` with `host`); delete `DEMO_APP_*`. Real-stack test.
  Also M10 (facilitator's own site: DNS record + webroot) and a new `/admin` Demo Site tab (there was none).
  Verify: live checks 8/8 (card; student and facilitator each see their own `<user>.certs.dojo.test` after lab 2's
  vhost steps; forged `X-Dojo-Host`/`X-Dojo-User` ignored; 303 without session; `/admin` tab frames `/demo/`), and
  lab 3's `acme.sh --issue` as the facilitator succeeds (HTTP-01 through their own site).
- [x] **T1.7** (findings in §10) git-fundamentals and dns-as-code: start, confirm nothing changed. Spoofed-header test on each gate.
  Verify: git-fundamentals with a temporary 2-route manifest (not committed) to `presentation:8080`: `shared` 200
  logged in / 401 not; `facilitator` 200 facilitator, 403 student, 403 student with forged `X-Auth-User`/`X-Dojo-User`,
  303 no session. dns-as-code (no manifest): `0 manifest(s)`, the 4 built-in cards, 5 built-in tabs, 3 status entries,
  IDE 200, `dnscontrol v5.0.4`, runner up. `identity` was spoof-tested in T1.5/T1.6.

### M2: modules

- [x] **T2.1** `run.sh`: `MODULES`, `module.env`, multi `-f`, `.last-overlay` list + `teardown.sh`. 63d002f
- [x] **T2.2** `WEB_TERMINAL_IMAGE` + chained terminal builds; drop `image:` lines from overlays. 63d002f, b28fc2b
- [x] **T2.2b** (M11) `/etc/dojo/start.d/*.sh` hook runner; cert-autorenewal and dojo-cloud wrappers become hooks. 63d002f, b28fc2b
- [x] **T2.3** Extract `forgejo-runner` from dns-as-code. Real-stack test of dns-as-code's CI lab. b28fc2b
- [x] **T2.4** Extract `dojo-cloud` from tofu-basics. Real-stack test of tofu-basics (Track A and Dojo Cloud). b28fc2b
- [x] **T2.5** All four workshops start, `./run.sh stop` cleans up every module's volumes. (test only)

### M3: docs and hand-over

- [x] **T3.1** `workshops/README.md` (adding a workshop, using and writing modules), `engine/README.md` (gates,
  rendering), root `README.md` tables. e3ee3b9. Also `./run.sh modules` (user asked, 2026-09-24). 816c333
- [x] **T3.2** Update `workshops/vault-fundamentals/PLAN.md`: P0.5 is replaced by this; openbao becomes a module.
  fbac73e **on `feat/vault-fundamentals`** (not this branch). Its draft `openbao` and Runners manifests pass the
  renderer.
- [ ] **T3.4** Browser pass by the user, per workshop (checklist below). Findings go in §10.
- [ ] **T3.3** PR to `main` (only when the user asks).

### T3.4 browser checklist (done by the user)

For each workshop: `./run.sh stop`, then `./run.sh <workshop>`. Open `PUBLIC_BASE_URL` in one browser as a student
and in a private window as the facilitator. Everything below comes from this branch's changes. The labs themselves
were tested live in M1/M2.

**Every workshop**
- [ ] Student landing page: VS Code, Terminal, Forgejo and Slides cards, plus the workshop's own card (below). Each
  opens.
- [ ] Facilitator lands on `/admin`: Roster, VS Code, Terminal, Forgejo and Slides tabs, plus the workshop's own tab.
  Each loads inside the page (no "refused to connect" frame).
- [ ] Status strip: Forgejo, Terminals and Slides are **Ready**, plus the workshop's own check.
- [ ] The student's terminal: `whoami` gives `studentNN`, and the workshop's tools run (below).

| Workshop | Extra card / tab | Extra status chip | Check in the browser |
|---|---|---|---|
| git-fundamentals | none | none | Lab 1: clone, branch, push, open a PR in Forgejo. |
| dns-as-code | none | none | `dnscontrol version` in the terminal. Push a branch and open a PR: Forgejo's Actions tab shows **DNS Preview** green; merge it and **DNS Apply** goes green; `dig` shows the new record. |
| cert-autorenewal | **Demo Site** card and tab | none | After lab 2's vhost steps, the student's card shows their own `studentNN.certs.dojo.test` site, and the facilitator's tab shows **their own** site (`admin.certs.dojo.test` here), not a student's. |
| tofu-basics | **Dojo Cloud** card and tab | **Dojo Cloud** | The student's card opens the portal on their own subscription. The facilitator's tab opens the progress view. After a Track B `terraform apply`, the resource shows up in the student's portal and in the facilitator's progress view. |

**After each:** `./run.sh stop` finishes without errors (the stack's volumes and networks were already checked
from the CLI in M2).

## 8. Open questions

- ~~Q1~~ Answered (M7): top-level `modules/`.
- ~~Q2~~ Answered (M10): the facilitator gets their own demo site.
- ~~Q3~~ Answered by T0.1: modules **may** extend engine services (env, volumes, networks, depends_on all merge),
  provided they follow the network-form rule in §9.
- ~~Q4~~ Answered (M11): yes. Terminal start-up hooks (§9 T0.3 finding): add a small `/etc/dojo/start.d/*.sh` hook runner to the base
  web-terminal entrypoint (engine edit; no hooks = no change), replacing the per-workshop `ENTRYPOINT` wrappers?

## 9. Findings

All run on 2026-09-24 in the session scratchpad with podman 5.7.0 / podman-compose 1.5.0, on separate project
names beside the running vault spike stack (untouched).

**T0.1 podman-compose merging: PASS, with one rule.**
- Four files (`base`, two modules, one in a sub-folder) changing the same service: `environment` merges per key
  (later file wins, list and map forms can be mixed), `volumes` and `depends_on` append (list and map `depends_on`
  mix fine), module-only services/volumes/networks are added. Confirmed at runtime (`env`, mounts, a pinned
  `ipv4_address` on a module network), and `down -v` left no volumes or networks.
- Relative paths in any fragment resolve against the **first** file's folder (`engine/`), same as today.
- **Rule:** `networks:` on one service must use the **same form in every file**. List + map fails at `up` (not at
  `config`): `ValueError: can't merge value of [networks] of type <class 'list'> and <class 'dict'>`. The engine uses
  list form, so a module adding a network to an engine service uses list form; pinned IPs only on the module's own
  services. The renderer/`run.sh` should catch this before `up` (a check over the merged files), since `config`
  alone does not.

**T0.2 Caddy import: PASS.**
- `import /etc/caddy/extensions/*.caddy` inside the shared-gate `handle`, before the catch-all `handle`, from a
  read-only bind mount (`:ro,Z`) under rootless podman: the imported route answers, basic auth still applies (401
  without it), other paths still reach the catch-all.
- No matching file and an empty file both only log a warning (`No files matching import glob pattern`,
  `Import file is empty`). Caddy still starts. We'll still always write the file so the log stays clean.
- `{$GATEWAY_TOKEN}` expands inside the imported snippet, and `header_up` overwrote a client's forged
  `X-Auth-User: facilitator` / `X-Gateway-Token: forged` with the real values.
- The gateway image bakes the Caddyfile in (`COPY`), so the snippet dir needs a bind mount on `gateway` in
  `docker-compose.yml`.

**T0.3 chained terminal builds: PASS.**
- `ARG BASE` / `FROM ${BASE}` chain base → m1 → m2 → workshop with `BUILDAH_FORMAT=docker` (as `run.sh` sets):
  every tool present, `TARGETARCH` reaches each link (`amd64`), HEALTHCHECK is **inherited** without restating
  it, ENTRYPOINT stays the base's. A missing `BASE` fails loudly (`no FROM statement found`). An unchanged
  rebuild takes ~3 s (cache).
- **Finding:** cert-autorenewal and tofu-basics each replace `ENTRYPOINT` with a wrapper that starts background jobs
  and then `exec`s `/usr/local/bin/web-terminal-entrypoint`. Two modules doing that would override each other.
  Proposed fix (Q4): the base entrypoint runs `/etc/dojo/start.d/*.sh` in order before its own work, and modules
  drop a hook there instead of wrapping.

## 10. Session log

### 2026-09-24: branch and plan
- vault-fundamentals paused; its T0.4 Caddyfile spike is in `git stash` ("vault-fundamentals T0.4 spike ...").
- Branch `feat/workshop-modules` from `main`. Mapped every per-workshop engine touch point (§2).
- User decisions M1-M3. Proposed M5-M9 and the task list; waiting for review.

### 2026-09-24: M0 spikes
- User: facilitator gets their own demo site (M10); run M0 before deciding Q1.
- T0.1-T0.3 pass (§9). New rule: same `networks:` form per service across files. New Q4: entrypoint hooks.

### 2026-09-24: M1 extensions
- User: modules go in top-level `modules/` (M7); `start.d` hooks approved (M11); go for M1.
- T1.1 renderer + 31 unit tests; T1.2 `run.sh` render step + mounts; T1.3 Caddyfile `import`; T1.4 allocator.
- T1.5 tofu-basics and T1.6 cert-autorenewal moved onto `extensions.json`; `CLOUD_ENABLED`, `DEMO_APP_ENABLED`,
  `DEMO_APP_ZONE` (engine side), `X-Cloud-User`, `X-Demo-Host` and the `@cloud`/`@demo` Caddy blocks are gone.
  cert-autorenewal gained an `/admin` Demo Site tab (it had none) and the facilitator's own demo site (M10).
- The paused vault spike stack was stopped from `feat/vault-fundamentals` (user's choice) so `.last-overlay`'s
  OpenBao overlay was torn down properly; its volumes are gone, so resuming vault means a fresh init.
- Worth knowing:
  - Rootless podman: a one-shot container writing into `engine/` must **not** get `--user <uid>` (maps to a subuid
    that can't write); container root is already the caller. Docker gets `--user uid:gid` (`run_once` in `run.sh`).
  - Caddy re-sorts path-matched `handle` blocks; the renderer's no-overlap rule is what keeps routing correct.
  - Inside a `handle`, Caddy orders `request_header` after `forward_auth`; the template wraps the gate in `route {}`
    so client copies of `X-Dojo-*` are stripped **before** `forward_auth` copies the real ones in.
  - `workshops/tofu-basics/tests/e2e.sh` is mode 644 in git: run it with `bash`.
  - This machine's facilitator username is `admin` (not the `root` default), which is why M10's site is
    `admin.certs.dojo.test` here.
  - Not done in M1: a real-browser pass (no headless browser here) and docs (M3).

### 2026-09-24: M2 modules
- User: go for M2; also asked to re-check dns-as-code on M1 code (live: 4 cards, 5 admin tabs, 3 green checks, no
  extension routes; same as `main`).
- T2.1/T2.2/M11 (63d002f): `MODULES` in `workshop.env`; `module.env` sourced first, then `.env` and `workshop.env` again
  (workshop wins); `-f` order engine, modules, overlay; `.last-overlay` is one file per line (old one-line files
  still work); build detection hashes every module dir plus the overlay dir together; module manifests render as
  `50-NN-module-<name>.json` before the workshop's `90-...`; `${VAR}` may name `module.env` keys too. Terminal chain
  tags are `gitopsdojo/web-terminal:<workshop>.<module>` then `:<workshop>`. Hooks run after accounts exist, as
  root, in name order (modules `50-`, workshops `90-`); a failing hook stops the container.
- T2.3/T2.4 (b28fc2b): `modules/forgejo-runner/` and `modules/dojo-cloud/`, each with a README. tofu-basics has no
  overlay left. Container names and image tags of dojo-cloud kept (tests use them); the runner's became
  `workshop_runner` / `workshop_runner_setup`, volume `runner_config`.
- Live results: dns-as-code DNS Apply (seed push) and DNS Preview (a real PR) both `success` on the module runner;
  tofu-basics full `e2e.sh` 284 passed / 0 failed (track_a, track_b, policy, curl_ca, security), card, `/cloud`
  gate (200 / 303), admin tab and green status from the module; cert-autorenewal hook ran, cron up, webroots owned
  per account, `/demo` gives student01, student02 and the facilitator their own site, forged `X-Dojo-Host`
  ignored, `acme.sh --issue` as the facilitator works; git-fundamentals runs on `:base`, cards/tabs unchanged.
  `./run.sh stop` left no named volumes, networks or containers after each.
- Worth knowing:
  - A module that extends an engine service's list (`networks`, `volumes`) should list only what it adds: lists
    append, so repeating `workshop_lab` duplicates it.
  - A module's service image can be swapped per workshop by overriding `build.context` in the overlay (later file
    wins); used for the runner's job tools instead of chaining a second image family.
  - Fixed after M2: every dns-as-code start left one anonymous volume (also on `main`). Cause: the runner image
    declares `VOLUME /data` and nothing mounted it; the module now mounts a named `runner_data` volume there, which
    `./run.sh stop` removes (verified: unnamed-volume count unchanged across a start/stop). When adding a service,
    check `podman image inspect <img> --format '{{json .Config.Volumes}}'` and name every declared path.
  - Still not done: a real-browser pass; docs (M3); `./run.sh list` doesn't show modules (nice-to-have).

### 2026-09-24: M3 docs
- User: go for M3; OK to edit `engine/README.md`; vault plan update committed on its own branch; add
  `./run.sh modules`; a browser checklist in this plan (§7, T3.4). The user runs the browser pass (T3.4).
- 816c333 `./run.sh modules` (summary = first plain line of each module README; "used by" from `MODULES=`).
- e3ee3b9 docs: `workshops/README.md` rewritten (three kinds of workshop, `extensions.json` reference, writing a
  module), `engine/README.md` (routing row, extensions and module wiring replace "Workshop hooks", ops notes on
  `.last-overlay` and `WEB_TERMINAL_IMAGE`), root `README.md` (layout, summary table, Dojo Cloud paragraph).
- fbac73e on `feat/vault-fundamentals`: P0.5/P6 struck (S25), `openbao` module split and draft manifests (§8.1).
- The user's first browser look (git-fundamentals): slides 11 and 17 overflowed (fixed; screenshot check finds no
  other overflow in its presentation, cheat-sheet, labs and index pages); code in Marp pages was nearly uncoloured
  (highlight.js bash marks no commands or flags): `engine/presentation/engine.js` now colours commands and flags and
  adds gitignore and cron (user approved the engine edit). Lab 1 and its handout: roster edit is VS Code, nano or
  `cat`; vim removed. Local `CLAUDE.md` rewritten for extensions/modules.
- tmux guide (git-fundamentals, dns-as-code) rewritten: `Ctrl+b` callout, real key presses (`Shift+5`, `Shift+'`),
  mouse, vi copy mode. User confirmed in a browser: Shift-drag copies to the system clipboard, and `Ctrl+b` reaches
  tmux in the VS Code terminal panel (code-server doesn't keep it for the sidebar).
- Teardown warned `StopSignal SIGTERM failed to stop container ... resorting to SIGKILL` for terminal, presentation
  and allocator (10 s each). Cause: PID 1 was python/node with no SIGTERM handler, which the kernel ignores for PID 1.
  `init: true` on those three services (engine/docker-compose.yml, user approved): `podman stop` 13.2 s → ~3 s each;
  a real dns-as-code `./run.sh stop` printed no warnings.
