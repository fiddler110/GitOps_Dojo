# GitOps Dojo

A lunch-and-learn training platform: students get a browser-only lab (VS Code, terminal, Forgejo git server,
slides) from one URL, and a facilitator runs it with `./run.sh <workshop>`. `README.md` is the tour; this file is
the rules and the non-obvious facts. If they disagree, the code wins, then the README.

## Layout

- `engine/`: the shared runtime (Caddy `gateway`, `allocator`, `web-terminal`, Forgejo, Marp slides), run by `engine/run.sh`.
  The repo-root `run.sh` just forwards to it.
- `workshops/<name>/`: a self-contained workshop pack: `workshop.env`, `content/` (slides, lab, seed repo) and, only if
  needed, `MODULES=` (in `workshop.env`), `extensions.json` (cards, `/admin` tabs, routes, status checks),
  `compose/docker-compose.override.yml` (extra services) and `compose/terminal/Dockerfile` (extra tools).
  Packs: `git-fundamentals`, `dns-as-code`, `cert-autorenewal`, `tofu-basics`; `vault-fundamentals` (in progress) lives
  on its own branch.
- `modules/<name>/`: reusable pieces a workshop lists in `MODULES="a b"`: `module.env`, `compose.yml`,
  `extensions.json`, `terminal/Dockerfile`, `README.md`, each optional. Now: `forgejo-runner` (dns-as-code),
  `dojo-cloud` (tofu-basics), `dns-ui` (dns-as-code, cert-autorenewal), `openbao` and `runner-pool` (vault-fundamentals, on its branch).
- `workshops/README.md` is the author's guide (adding a workshop, `extensions.json` reference, writing a module).
  `engine/README.md` covers routing, auth, rendering and operations.

## Running things

- `./run.sh setup` (first time), `./run.sh list`, `./run.sh modules`, `./run.sh <workshop>` (add `--test` for demo
  bots, `--dry-run` to preview and check manifests), `./run.sh stop`.
- This machine is **WSL2 on the user's desktop** (not a laptop); the everyday stack is `http://localhost:8080`. Say
  "locally" when reporting where something was tested.
- This machine has **podman + podman-compose only, no docker**. Always build and start through `./run.sh`: a plain
  `podman build` drops the image HEALTHCHECK. Run `./run.sh stop` before restarting after image changes. `stop` wipes
  every volume, so don't run it while the user may be testing in a browser; ask first.
- `./run.sh list` skips workshop folders without a `workshop.env`.
- `content/slides/lab/*.md.txt` are git-ignored copies of `content/lab/*.md` that `run.sh` makes at start (the lab
  reader serves them). After editing a lab on a running stack, `cp` it there too; never edit the copies.
- **No browser on this machine.** For screenshots or overflow checks use
  `mcr.microsoft.com/playwright/python:v1.55.0-noble` with `--network host`; it needs
  `pip install --break-system-packages playwright==1.55.0` inside first. Slides are open at `http://localhost:8080/slides/<file>.md#<n>`.

## Rules that are easy to get wrong

- **The base engine stays workshop-agnostic.** A workshop or module changes runtime behaviour through its own
  `extensions.json`, `compose.yml`/overlay and terminal Dockerfile, never by editing `engine/` and never with a new
  per-workshop flag (`DEMO_APP_ENABLED` and `CLOUD_ENABLED` were deleted). **Ask the user before editing any `engine/`
  file**, docs included.
- **The facilitator has access to every part of an active workshop.** Whatever a student can reach, the facilitator can
  reach from the `/admin` workspace (Roster, VS Code, Terminal, Forgejo, Slides, plus any `admin_tabs` from manifests).
  A manifest card without an `/admin` tab of the same `id` makes `run.sh` print a warning. Check identity, permissions
  and iframe framing actually work for the facilitator.
- **Manifests.** Gates are fixed templates in `engine/allocator/render_extensions.py`: `shared`, `identity`,
  `facilitator`. A manifest never supplies raw Caddy config or HTML; the renderer rejects collisions with engine paths
  and upstreams that aren't services in this run, and a bad manifest stops the start.
- **Compose fragments** (overlays and module `compose.yml`): relative paths resolve against `engine/`. Don't set
  `image:` on `web-terminal`; `run.sh` passes the terminal image as `WEB_TERMINAL_IMAGE`. On engine services use the
  **list form** of `networks:` (mixing list and map fails at `up` under podman-compose) and list only what you add
  (lists append). Name every volume, including paths an image declares as `VOLUME`, or `./run.sh stop` leaves it.
  `./run.sh stop` (`teardown.sh`) loads only `engine/.env`, not `workshop.env`/`module.env`: never write
  `${VAR:?}` in a fragment for a variable those files set, or `stop` aborts before removing anything.
- **Terminal images chain**: `:base` → each module's `terminal/` → the workshop's `compose/terminal/`. Every tools
  Dockerfile starts `ARG BASE=gitopsdojo/web-terminal:base` / `FROM ${BASE}` and doesn't set `ENTRYPOINT`. Start-up
  work goes in `/etc/dojo/start.d/NN-name.sh` hooks (modules `50-`, workshops `90-`; root, after accounts exist).
- **Student terminals have no internet and no docker.sock.** Tools are baked into the image, version-pinned and
  sha256-verified per architecture. All students share one network namespace, so a source IP never identifies a student.
- **Trust model.** Identity headers (`X-Auth-User`) count only alongside `X-Gateway-Token`, and only Caddy sets both
  (`header_up` replaces client values). Anything students can reach on `workshop_lab` directly must check the token.
- **Student-controlled strings are shown to the whole class.** Render them with `textContent` only, never `innerHTML`,
  and keep the strict CSP (no inline script or style).
- **Never call Docker while holding a shared lock**, and keep one Docker list call per request (cached ~2 s); the
  portal is polled every ~3 s by every student.
- **Slides and code colouring.** Marp pages (presentation, cheat-sheet, labs index) use highlight.js with extra
  grammars in `engine/presentation/engine.js` (hcl/terraform, bash/sh with commands and flags, gitignore, cron); the
  lab reader uses Prism (`workshops/assets/lab-reader.js`). Always tag code fences with a language (`text` for output).
  Keep each slide within 16:9; check for overflow with a screenshot, not by eye in the source.
- Branding: "Dojo Cloud" is Azure-*inspired*. No Microsoft names, logos or trademarks.

## Git and working style

- Work happens on feature branches. The working tree often holds the user's own unrelated uncommitted edits: never
  `git add -A` or `git commit -a`; stage only your own files or hunks, and leave theirs.
- To change another branch's files without switching (e.g. the vault plan), use a temporary `git worktree` beside
  the repo and remove it afterwards.
- Do not push without being asked. Commit messages describe why; use the attribution the harness gives you.
- `CLAUDE.md` is git-ignored on purpose (`.gitignore`). It is a local file, not part of any commit.
- Don't leave `__pycache__` behind (use `python3 -B`); it is ignored but it clutters `engine/`.
- Verify by running it: real stack, real browser, real provider. Say what was and wasn't tested, and report failures
  with their output. Don't call something done that you only reasoned about.
- Keep the main context small and token use low: do small edits inline; hand only heavy or noisy work (builds, live
  stack tests, wide searches) to sub-agents with short briefs.

## Workshop modules (merged to `main`, PR #2)

`engine/MODULES-PLAN.md` holds the decisions (M1-M11) and history. Only the user's browser pass (T3.4, checklist in
its §7) is still open. Home LAN hosting: `./run.sh <workshop> --env home` loads `engine/.env.home` (git-ignored) and
serves https://dojo.macleodtech.ca through the user's home-lab Caddy (`GATEWAY_LISTEN=http://:8080`).
**Known bug on `main`:** with `MODULES` set, `run.sh` re-read `.env` but not `.env.<name>` after the module
defaults, so `--env home` lost its `PUBLIC_BASE_URL` for workshops with modules. Fixed (user-approved) in a24d0e7 on
`feat/vault-fundamentals` only; `main` gets it when that branch merges (or cherry-pick it if needed sooner).

## vault-fundamentals (current, `feat/vault-fundamentals`)

`workshops/vault-fundamentals/PLAN.md` on that branch is the single source of truth: design, decisions (S1-S32), the
task checklist with commit SHAs, and a session log. Read its "HOW TO RESUME" section first, keep it updated, and
**ask the user before moving from one phase to the next.** The decisions in its §1 were set by the user; no need to
raise them again. It uses a real OpenBao (no Azure Key Vault emulation, just a comparison slide), per-student
namespaces plus a shared templated policy, single-use autoscaled Forgejo runners with an `/admin` Runners panel, and an
`app-host` deploy target. Its old P0.5 ("workshop extensions") and P6 were replaced by `feat/workshop-modules` (S25):
merged in (8c71f83). P0-P2 are done (OpenBao is `modules/openbao/`, 2.7.0; labs 0-6 verified 2026-09-25). **P3 is
done** (2026-09-25, live pass T3.9 all PASS locally): the `runner-pool` module (pool supervisor, controller, Runners
panel) and labs 7-8; tests `modules/runner-pool/tests/pool.sh`, `tests/labs_7_8.sh`. **P4 is done** (2026-09-25, pushed): `app-host`,
`app-db`, `openbao-audit`, labs 9-11; tests `tests/labs_9_11.sh`, `tests/p4_browser.py`. **P5 content is built** (T5.1-T5.5, 2026-09-25); next is T5.6, the long live pass with `--test 20` and `tests/e2e.sh --load`. Stack volumes are prefixed `engine_`. The plan's §0 "Where we stopped" lists the next steps. There is no stash.

tofu-basics is merged to `main` (PR #1). Its `PLAN.md` still holds its history; only manual checks remain (T9.4
human dry-run, T9.9 browser pass).
