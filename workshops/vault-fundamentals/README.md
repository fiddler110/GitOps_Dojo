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

`app-host` runs as root inside its container but drops all capabilities except those `useradd`, `su` and the slots' files need, and sets `no-new-privileges`. NET_ADMIN (for the slots' egress allowlist) is held only at start: `compose/app-host/start.sh` runs `apphost.py --isolate-only`, then `setpriv` removes NET_ADMIN and SETPCAP before the platform starts. A restart re-runs the allowlist. Podman's default seccomp profile applies.

The vault itself (`openbao`, SSO, CLI login, `openbao-audit` and the Audit tab) is `modules/openbao/`; the runners
and their panel are `modules/runner-pool/`.

## Security shortcuts (accepted)

Decided in the threat-model remediation (`threat-model-20260926-154208/REMEDIATION-PLAN.md`, D9, D11), and stated
to the class on the slide "What today's vault cuts short":

- **One unseal key share**, on the `openbao_setup` volume, so the vault unseals itself after a restart. Whoever has
  that volume (host access) can unseal it and make a root token. Production uses auto-unseal (a KMS or HSM) or shares
  held by several people. No root or provisioner token is kept: each start makes a temporary root from the key,
  provisions with a short-lived token and revokes both (`modules/openbao/README.md`).
- **Plain HTTP on the lab networks** to OpenBao and to `app-db` (FIND-19): secrets cross `workshop_lab` and
  `runner_net` unencrypted. Only the stack's own containers are on them.
- **`hmac_accessor = false`** in the audit device (`modules/openbao/config.hcl`): the Audit tab and `bao-audit`
  filter by token accessor. An accessor can look up or revoke a token only with a policy that allows it, and tokens
  and secret values stay hashed in the log.

## Tests

With the stack up, from the repo root, `bash workshops/vault-fundamentals/tests/e2e.sh` runs everything in order
and prints one line per area (`--list` says what each proves, `--only` / `--skip` pick areas):
unit tests, `tenancy.sh`, `cli_login.sh`, `setup_tokens.sh`, `lab_2.sh`, `labs_5_7.sh`, `labs_8_9.sh`, `lab_10.sh`, `labs_11_13.sh`, `pool.sh`, the Audit tab's
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

Measured (T5.6, 2026-09-28, locally on a WSL2 desktop, 8 vCPU / 14 GiB): `--test 10`, the full `e2e.sh` (every lab
script as one student, the browser checks) and then `e2e.sh --load 15` with the bots doing labs 0-11, sampled every
15-30 s with `podman stats`:

| | Peak |
| - | ---- |
| Whole stack (sum of the `workshop_*` containers) | 2.0 GiB (1.9 GiB in the bots-only load window) |
| `web-terminal` (every student's shell) | 0.9 GiB during the lab scripts, 0.65 GiB bots-only; up to 42 % of a core |
| `forge` | 0.44 GiB, 33 % of a core |
| `app-host` (5 apps running) | 0.24 GiB |
| `runner-pool` (2 runners alive, up to 5 jobs waiting briefly) | 0.16 GiB |
| `openbao`, `app-db` | 0.14 GiB, 0.09 GiB; CPU a few % |
| CPU, all containers together | under 0.9 of a core |

Nothing restarted and no container came near its limit. For 20-35 students, extrapolating: `web-terminal` grows
with shells (roughly 50-60 MiB per active student, estimated from 10 bots), the rest barely; budget about 4 GiB and 4
cores, and watch the runner queue on the Runners panel (the queue was back to 0 at the end of the run).
