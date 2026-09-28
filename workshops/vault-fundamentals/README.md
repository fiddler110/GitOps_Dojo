# vault-fundamentals — Vault Fundamentals Lab

How to use a vault well: get secrets out of code, git, pipelines and servers, and replace long-lived secrets with
identity and short-lived credentials. Fourteen labs (0-13, about 3½ hours) on a real OpenBao, after a talk
(`content/slides/presentation.md`). Prerequisite: `git-fundamentals`. The design, decisions and history are in
[`PLAN.md`](PLAN.md).

## Running it

```bash
./run.sh vault-fundamentals             # the class
./run.sh vault-fundamentals --test 20   # plus 20 demo bots that walk labs 0-11
./run.sh stop                           # removes every container and volume, the vault with them
```

The facilitator's `/admin` has, besides the engine's tabs: **Vault** (the UI, signed in as the facilitator),
**Audit** (every request, filterable by student, operation, path and accessor), **Runners** (the single-use CI
pool, Auto / Manual, − / +) and **Apps** (every app-host slot and its log).

## What's in this folder

| Path | What it is |
| ---- | ---------- |
| `workshop.env` | Names, `MODULES="openbao runner-pool"`, the overlay, `FORGEJO_FORK_WORKFLOW=1` (bots fork, as lab 8 does). |
| `extensions.json` | The **My App** card, the `/admin` **Apps** tab, the `/apps` route and its status check. |
| `compose/` | The overlay: `app-host` (the deploy platform, `apphost.py`), `app-db` (Postgres), the `openbao-setup.d/` hooks (namespaces, CI and platform auth, per student and bot), the terminal's extra tools (sops, gitleaks, pass, psql, hvac). |
| `content/` | Slides, labs 0-13 and the cheat sheet, the seed repo, and `bots/steps.sh` (demo bots). |
| `tests/` | Below. |

The vault itself (`openbao`, SSO, CLI login, `openbao-audit` and the Audit tab) is `modules/openbao/`; the runners
and their panel are `modules/runner-pool/`.

## Tests

With the stack up, from the repo root, `bash workshops/vault-fundamentals/tests/e2e.sh` runs everything in order
and prints one line per area (`--list` says what each proves, `--only` / `--skip` pick areas):
unit tests, `tenancy.sh`, `cli_login.sh`, `lab_2.sh`, `labs_5_7.sh`, `labs_8_9.sh`, `lab_10.sh`, `labs_11_13.sh`, `pool.sh`, the Audit tab's
API, the demo bots, and the browser checks (`sso_browser.py`, `p4_browser.py`, `p5_browser.py` in Playwright's
image). `--load MIN` also watches a `--test` class of bots for `MIN` minutes and writes `stats.csv`, `queue.csv` and
`report.txt` (peak memory and CPU per container, runner queue, apps running). Each lab script resets its own
student's work first, so a run can be repeated.

## Sizing

Memory limits per container (the engine's own services come on top):

| Container | Limit | Setting |
| --------- | ----- | ------- |
| `openbao` | 512 MiB | `OPENBAO_MEM_LIMIT` |
| `runner-pool` (every CI job runs here) | 2 GiB | `RUNNER_POOL_MEM_LIMIT` |
| `app-host` (every student's app) | 1 GiB | `APP_HOST_MEM_LIMIT` |
| `app-db` | 512 MiB | `APP_DB_MEM_LIMIT` |
| `openbao-audit`, `runner-controller`, the shims, `openbao-setup` | 64-128 MiB each | |

Measured for 20 students (T5.6, `e2e.sh --load` with `--test 20`): *to be filled in by the live pass.*
