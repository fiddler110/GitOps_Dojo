# Workshop extensions and modules: plan

| | |
|---|---|
| Branch | `feat/workshop-modules` (from `main` at a840252, 2026-09-24) |
| Overall status | **M1 in progress (user go-ahead 2026-09-24).** |
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
- [ ] **T1.3** Caddyfile `import`; gate templates.
- [ ] **T1.4** Allocator: cards, admin tabs, status checks and `/auth-check?route=` from the manifest.
- [ ] **T1.5** tofu-basics → `extensions.json`; delete `CLOUD_ENABLED`. Real-stack test incl. facilitator tab.
- [ ] **T1.6** cert-autorenewal → `extensions.json` (`/demo` with `host`); delete `DEMO_APP_*`. Real-stack test.
- [ ] **T1.7** git-fundamentals and dns-as-code: start, confirm nothing changed. Spoofed-header test on each gate.

### M2: modules

- [ ] **T2.1** `run.sh`: `MODULES`, `module.env`, multi `-f`, `.last-overlay` list + `teardown.sh`.
- [ ] **T2.2** `WEB_TERMINAL_IMAGE` + chained terminal builds; drop `image:` lines from overlays.
- [ ] **T2.3** Extract `forgejo-runner` from dns-as-code. Real-stack test of dns-as-code's CI lab.
- [ ] **T2.4** Extract `dojo-cloud` from tofu-basics. Real-stack test of tofu-basics (Track A and Dojo Cloud).
- [ ] **T2.5** All four workshops start, `./run.sh stop` cleans up every module's volumes.

### M3: docs and hand-over

- [ ] **T3.1** `workshops/README.md` (adding a workshop, using and writing modules), `engine/README.md` (gates,
  rendering), root `README.md` tables.
- [ ] **T3.2** Update `workshops/vault-fundamentals/PLAN.md`: P0.5 is replaced by this; openbao becomes a module.
- [ ] **T3.3** PR to `main` (only when the user asks).

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
