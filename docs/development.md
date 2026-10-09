# Development guide

For people changing GitOps Dojo itself: the engine, the CLI, modules and workshops. Day-to-day rules live in
`CLAUDE.md` (a local, git-ignored file for the maintainer's AI assistant); the durable ones are collected here.
**If any document disagrees with the code, the code wins.**

## 1. Repository layout

```text
├── dojo                      # The command (Python launcher; ./run.sh is a retired forwarding stub)
├── setup.sh, setup.ps1       # Host prerequisites (Linux/macOS; Windows via WSL2)
├── dojo.toml                 # Committed non-secret defaults (sections; [profiles.NAME.*])
├── dojo.local.toml           # Git-ignored: this machine + profiles
├── .env, .env.example        # Secrets (git-ignored / template)
├── engine/
│   ├── docker-compose.yml    # The six base services
│   ├── dojo/                 # The CLI: Click + Rich (cli, start, stop, build, config, doctor, status, monitor, ...)
│   │   └── tests/            # CLI unit tests
│   ├── allocator/            # Slots, auth, landing, /admin; render_extensions.py; tests/
│   ├── gateway/              # Caddyfile + entrypoint
│   ├── web-terminal/         # :core image: entrypoint, workspace-control.py, provisioning, bots
│   ├── web-terminal-vscode/  # code-server leaf
│   ├── zellij-terminal/      # Zellij leaf
│   ├── git-server/           # bootstrap.sh, dojo-secret.sh
│   ├── presentation/         # Marp engine (engine.js grammars)
│   ├── scripts/              # env-setup, capacity-calc, check-pins, check-tool-pins, teardown, lib.sh, alias-setup
│   └── completions/          # bash/zsh
├── modules/                  # achievements, ctf-range, dns-gate, dns-ui, dojo-cloud, openbao, runner-pool, sensei, _shared
├── workshops/
│   ├── <pack>/               # workshop.env, content/, compose/, extensions.json, FACILITATOR.md ...
│   └── assets/               # Themes, lab-reader, template/, test-lib.sh, smoke.sh, retest.sh, slide-overflow.sh
├── docs/                     # These pages; archive/ holds frozen plans; CTF and policy plans
├── .github/                  # ci.yml, scripts/unit-tests.sh, scripts/dry-runs.sh
├── ROADMAP.md, RELEASES.md   # Open work; what shipped
└── assets/branding/
```

State and generated output (git-ignored): `engine/.build-state/`, `engine/.generated/`, `engine/.cache/`,
`workshops/*/content/slides/lab/`, `modules/*/**/_shared/`, and `.cache/` (one-time pulls such as the ctf-host inner
image store that `stop` would otherwise wipe).

## 2. Setup for development

- A container engine (podman + podman-compose preferred, or docker with compose) and Python 3.9+.
- `./dojo setup --default` for a throwaway local `.env`; `./dojo doctor`.
- The CLI's dependencies unpack from hash-pinned wheels on first run; no pip or venv.
- **No browser is assumed.** For screenshots or overflow checks use the Playwright container
  `mcr.microsoft.com/playwright/python:v1.55.0-noble` with `--network host`, after `pip install
  --break-system-packages playwright==1.55.0` inside. Slides need a login first: the `/login` form sets a
  `dojo_login` cookie (not Basic Auth); for curl, `curl -c jar --data-urlencode username=... --data-urlencode
  password=... localhost:8080/login`, then `-b jar`.

## 3. Tests

| Suite | Command (repo root) |
|---|---|
| All unit tests, as CI runs them (~2.5 min) | `sh .github/scripts/unit-tests.sh` |
| Every workshop's dry run (~45 s) | `sh .github/scripts/dry-runs.sh` |
| CLI | `PYTHONPATH=engine:$(echo engine/.cache/pylib-*) python3 -B -m unittest discover -s engine/dojo/tests -t engine` |
| Allocator (imports siblings by plain name, so run from its folder) | `cd engine/allocator && python3 -B -m unittest discover -s tests` |
| A module's service | `cd modules/<m>/<svc> && python3 -B -m unittest discover -p 'test_*.py'` (each folder with `test_*.py` is picked up automatically) |
| Shell test-library self-test | `sh workshops/assets/test-lib-selftest.sh` |
| Achievements catalog | `cd modules/achievements/catalog && python3 -B -m unittest test_catalog`; `render_md.py --all --check` fails on stale generated markdown |
| Live-stack checks | `workshops/assets/smoke.sh <pack>`, `retest.sh`, `slide-overflow.sh`; a pack's `tests/lab_N.sh`; `modules/*/tests/*.sh` |

Always run Python with `-B` so no `__pycache__` is left in `engine/`.

CI (`.github/workflows/ci.yml`) runs the unit tests and the dry runs on pull requests into `main` (or by hand), not on
every push.

### Verify by running it

A change is done when it is **verified against a real stack**, not only reasoned about. Say what was and was not
tested, and where ("locally": a WSL2 desktop with podman). Report failures with their output. Every stack test with
bots uses `--test [N] --fast` and waits on the `~/.dojo-bot-done` markers. When a live test finishes, run
`./dojo stop` unless someone still needs the stack in a browser.

## 4. Engine rules that are easy to get wrong

- **Keep the engine workshop-agnostic.** No new per-workshop flags (`DEMO_APP_ENABLED` and `CLOUD_ENABLED` were
  deleted). Ask before editing any file under `engine/`, docs included.
- **The facilitator reaches every part of an active workshop.** Each card needs an `/admin` tab with the same `id`.
  Check identity, permissions and iframe framing for the facilitator.
- **Manifests**: gates are fixed templates in `engine/allocator/render_extensions.py`; no raw Caddy or HTML; collisions
  with engine paths and unknown upstreams are rejected; a bad manifest stops the start.
- **Compose fragments**: relative paths against `engine/`; no `image:` on `web-terminal`; list-form `networks:` on engine
  services and list only what you add; name every volume; no `${VAR:?}` for variables only `workshop.env`/`module.env`
  set (`stop` would abort).
- **Terminal images chain** `:core` → leaf → modules → workshop; every tools Dockerfile begins `ARG BASE` / `FROM
  ${BASE}`; no `ENTRYPOINT`; start-up work in `/etc/dojo/start.d/NN-name.sh`.
- **Student terminals have no internet and no docker.sock.** Tools baked in, pinned, sha256-verified per architecture.
- **Trust model**: identity headers count only alongside `X-Gateway-Token`, and only Caddy sets both. Anything students
  reach directly on `workshop_lab` must check the token.
- **Student-controlled strings are shown to the whole class**: `textContent` only, strict CSP.
- **Never call the container engine while holding a shared lock**; one list call per request, cached ~2 s; the portal is
  polled every ~3 s by every student.
- **Slides and colouring**: tag fences with a language (`text` for output); keep each slide within 16:9 and prove it
  with a screenshot.
- **Branding**: "Dojo Cloud" is Azure-*inspired*. No Microsoft names, logos or trademarks.
- **Don't over-harden**: this is an ephemeral workshop lab; residual findings are acceptable.

## 5. Git and working style

- Work on **feature branches**, cut per batch of work. `main` is the integration branch; PRs are merged and pushed only
  when asked.
- The working tree may hold unrelated uncommitted edits. Never `git add -A` or `git commit -a`; stage only your own files.
- To change another branch's files without switching, use a temporary `git worktree` beside the repo and remove it
  afterwards. A worktree shares image tags and containers with the main tree, so only one builder at a time (the run
  lock enforces it).
- Commit messages describe **why**. Search with ripgrep (`rg`).
- `CLAUDE.md` is git-ignored on purpose; do not commit it.

## 6. Tracking work

- `ROADMAP.md` is the single list of open work, including manual checks outstanding per workshop.
- `RELEASES.md` records what shipped, newest first. When something is done **and verified**, delete it from the
  roadmap and add a release line.
- Frozen plans in `docs/archive/` (modules M1-M11, tofu-basics S1-S39, vault D1-D18, remediation R1-R10, student reset)
  are for reading the decisions; never update them. New tasks go in the roadmap.
- Live plans: `CTF-WORKSHOP-PLAN.md` and `CTF-SPIKES.md` (decisions CTF-D1..D26, spikes CTF-S1..S17) and
  `CLOUD-POLICY-AS-CODE-PLAN.md`.

## 7. Keeping the docs current

| When you change... | Update |
|---|---|
| A CLI command or flag | [CLI reference](cli-reference.md), `engine/README.md`, shell completion needs no change |
| A setting | `engine/dojo/config.py` `SCHEMA`, `dojo.toml` comments, [Configuration](configuration.md) |
| Routing, gates, networks | [Architecture](architecture.md), [Security](security.md), `engine/README.md` |
| A workshop (labs, services, duration) | Its README and `FACILITATOR.md`, `workshop.env`, [Workshop catalog](workshops.md), `workshops/README.md` |
| A module | Its README, [Modules](modules.md) |
| `extensions.json` rules | [Authoring](authoring.md#4-the-extensionsjson-manifest), `workshops/README.md` |
| Student-visible behaviour | [Student guide](student-guide.md) |
| Facilitator-visible behaviour | [Facilitator guide](facilitator-guide.md), the pack's `FACILITATOR.md` |
