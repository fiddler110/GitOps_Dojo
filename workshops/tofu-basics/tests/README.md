# tofu-basics: end-to-end and load tests

Committed, re-runnable scripts that drive a **running** tofu-basics stack the way a student does, and check what
the labs promise. They cover PLAN tasks T9.1, T9.6, the driver half of T9.3, and the live security checks (T9.2, T9.8).

## Run sheet: the 15-student class on the 9.9 GB dev box

**Status (2026-09-21):** run live on the 9.9 GB dev box: `e2e.sh` (all areas incl. restart) 292 checks, 0 failed; `load.sh` at 5, 10 and 15 students all PASS (`apply` p95 51 / 69 / 76 s, peak memory at 15: terminal 1.2 GB, cloud-host 0.16 GB, no OOM). Not tried: 20 or more students (`STUDENT_COUNT=20` here). Stop at the first surprise; the cleanup is safe to rerun.

```sh
cd engine && ./run.sh stop && ./run.sh tofu-basics                # STUDENT_COUNT=20 in engine/.env already covers 15
# 1. Is the stack healthy? /admin shows the Dojo Cloud chip green. Note free memory:  free -m
workshops/tofu-basics/tests/selftest/run.sh                       # optional: the harness itself, offline (about 1 minute)
# 2. One student, everything (about 15 minutes). Fix anything that fails before going on.
workshops/tofu-basics/tests/e2e.sh --only track_b,policy,curl_ca,security
workshops/tofu-basics/tests/e2e.sh                                # then all areas (add --with-restart for the restart test)
# 3. Load, in waves. In a second terminal watch memory:  podman stats --no-stream   (or: watch -n5 free -m)
workshops/tofu-basics/tests/load.sh --students 5  --wave-size 5
workshops/tofu-basics/tests/load.sh --students 10 --wave-size 5
workshops/tofu-basics/tests/load.sh --students 15 --wave-size 5   # M4 as redefined: 15, not 30
```

**Stop and do not scale up if:** free memory on the host drops below about 1.5 GB, the report shows `oom_kill` or a container restart,
any step fails, `apply` p95 is over 120 s, or the portal p95 is over 2 s. Say so in PLAN.md with the largest N that passed.
Each run leaves its report in `$TMPDIR/tofu-basics-load.*/report.txt`. If a run dies, `tests/load.sh --cleanup-only --students 15` empties the clouds.
Both scripts refuse to start (and touch nothing) if a student's subscription is not empty; `--purge-first` is the way to override that.

**What 15 students prove:** the Dojo Cloud side (ARM, the lock fix from T9.7, `cloud-host`, the portal) under 15 concurrent real `tofu`
runs. They do not prove the class experience: no IDE, no browser and no Forgejo traffic beyond the clone. A real class of 15 with every IDE
open needs about 19 GB by `./run.sh capacity`, which this machine does not have.

```sh
cd engine && ./run.sh tofu-basics                       # the stack must be up, and Dojo Cloud green on /admin
workshops/tofu-basics/tests/e2e.sh                      # one student, Labs 0-10 + policy + curl (about 15 min, an estimate)
workshops/tofu-basics/tests/e2e.sh --with-restart       # also restart workshop_cloud_host (+1 min)
workshops/tofu-basics/tests/load.sh --students 10 --wave-size 5     # a gentle first load run
workshops/tofu-basics/tests/load.sh                     # 30 students at once (read the memory warning below)
workshops/tofu-basics/tests/e2e.sh --dry-run            # any script: print the commands, touch nothing
```

Host needs: bash 5, python3 (run as `python3 -B`, no bytecode left behind), `podman` or `docker`. No other tools, no
`jq`, no `shellcheck` requirement. Nothing is installed anywhere. The **safety rules**: they destroy things in one (e2e) or
N (load) students' clouds, so point them at a test stack, not at a class in progress.

## Files

| File | What it is |
| ---- | ---------- |
| `lib.sh` | Shared helpers: `as_student`, assertions that print PASS/FAIL with evidence, the portal API helper, the always-run cleanup |
| `e2e.sh` | Entry point: one student, the areas below, a summary, non-zero exit on any FAIL |
| `e2e/10_track_a.sh` ... `60_security.sh` | One script per area (each also runs on its own; it hands over to `e2e.sh --only <area>`) |
| `load.sh` | N students at once, per-step timings, resource sampling, thresholds, cleanup |
| `helpers/` | `cloud_http.py` (portal request, runs inside cloud-api), `poller.py` (portal pollers, same), `sec_arm.py` (cross-tenant and token-forgery probes, runs in a student's shell), `stats_csv.py`, `jq.py` (tiny JSON reader), `report.py` (load report) |
| `selftest/` | Offline self-test of these scripts against a fake container CLI and a mock portal (see the end) |

## How the scripts drive the stack

- **A student** is the Linux account `student01`..`NN` inside the container `workshop_terminal`. `as_student` runs one command
  there as that user through a login `zsh` (`podman exec -u student01 ... zsh -lc "<command>"`): `/etc/zsh/zshenv` then asks the
  credential broker for that user's `ARM_*`, `TF_VAR_*`, `SSL_CERT_FILE` and `CURL_CA_BUNDLE`, the same path a real terminal takes
  (the broker identifies the caller by `SO_PEERCRED`, so it really is that user). The command string is passed as a single argument.
  Every command runs under `timeout` (in the container and on the host).
- **The portal API and `/readyz`** are called from **inside the `workshop_cloud_api` container** against `127.0.0.1:8080`, by
  `helpers/cloud_http.py` (fed to `python3 -` over stdin). That container already has `GATEWAY_TOKEN` in its environment, and the
  portal API trusts `X-Auth-User` only together with that token (PLAN 5.6), so the helper sends both. This is the least fragile
  route: no gateway URL, no session cookie, no basic-auth password, and **the scripts never read, pass or log the token**. It
  acts as a student (`X-Auth-User: student01`) for that student's view and as `@facilitator` (`$FACILITATOR_USERNAME` of that
  container, `admin` here, not `root`) for the class overview and Purge. The price: **Caddy and the allocator's session logic are
  not exercised** (that was P5's job).
- **Sites** are fetched from the terminal as `curl http://cloud-api:8080/cloud/site/<label>/`, the class URL path the labs use
  (Lab 5's troubleshooting box). The `url` output itself is checked as a string against `TF_VAR_portal_base_url`.
- **Secrets** are masked in everything the scripts print or log (`dojo~...` client secrets, JWTs, `X-Gateway-Token`,
  `password=`, `token=` and similar). Nothing they run prints a secret in the first place; the mask is a second layer.
- **Run directory:** `$TMPDIR/tofu-basics-e2e.XXXXXX` (or `-load.`), created per run and the only host directory written to.
  `session.log` has every command with its output, `results.tsv` every check, `logs/` one file per command. It is kept
  (small); delete it by hand. A dry run removes its own.
- **In the container** everything happens under `/home/<student>/e2e-<runid>/` (or `load-<runid>/`), never the student's real
  `~/lab`. The only `rm -rf` in the scripts targets a path that matches `/home/<user>/(e2e|load)-<6 chars>` exactly.

## e2e.sh

```text
--student N|NAME   default 1 (student01). The student's subscription must be EMPTY at the start (or use --purge-first)
--only A,B / --skip A,B
--with-restart     include the restart area
--ready-bound S    restart: /readyz must be 200 within S seconds of the restart (default 45)
--site-bound S     restart: the site must answer within S seconds (default 60)
--policy-max S     policy: a refused apply must fail within S seconds (default 30)
--keep             do not destroy or delete anything at the end
--no-purge         cleanup never uses the facilitator Purge
--dry-run
```

Exit status: 0 all checks passed; 1 a check failed (or cleanup found leftovers); 2 could not run (stack down, no such account,
subscription not empty). A failed check never stops the run; an area that cannot continue (say, no starter repo) is aborted and
the next one runs. **Cleanup always runs** (also on Ctrl-C and on errors): `terraform destroy` in every directory the run
registered, then the portal's class view must show nothing owned by the student, else that is a FAIL and the facilitator Purge
empties it anyway (unless `--no-purge`), and the container work directory is removed. If `cloud-host` was left stopped, the
cleanup starts it first.

| Area | Proves |
| ---- | ------ |
| `track_a` | Labs 0-3 in a fresh Forgejo clone: `terraform` is OpenTofu (link to `tofu`); offline `init` from the mirror, the lock file untouched; `validate`; `plan` (3 to add); `apply` (with the approval prompt, once); the greeting file; a clean second plan; the `learner` edit gives `~` on `terraform_data` and `-/+` on `local_file` and leaves `random_pet` alone; outputs and `state list`; `-replace` chains through the dependency; the `pet_words` validation message; `plan -destroy`; `destroy`; what is left behind (state file with `"resources": []`, backup, `.terraform/`); `git status` shows only the tfvars edit |
| `track_b` | Labs 4-10, the T9.6 lifecycle: credentials in the environment and the subscription equal to the portal's; `init` offline with the lock file untouched and a tiny `.terraform`; a `plan` with no state never touches the activity log; `apply` (2 added, timing), the portal (1 RG, 1 container `Running`, quota 1/2, activity events, Logs startup line); the site through `/cloud/site/<label>/`; Lab 6's own three mistakes (missing tag: plan fine, apply refused with the lab's text, nothing changed; region: caught by the starter's validation; 2 vCPU: old container destroyed, then `InvalidResourceRequest`, site gone, recovery by `git checkout` + `apply`); Lab 7 drift through the portal API (tag edit shows as `~`, portal delete shows `has been deleted` and `+ create`, `apply` restores, the activity log says `(portal)`); Lab 8 (tag = in-place on both resources with no destroy, message and image = `-/+` with `# forces replacement`, `-replace=`, `create_before_destroy` fails harmlessly); Lab 9 (a third container group is refused with `QuotaExceeded` and the policy message, one extra survives, quota 2/2, the code is fixed to match); Lab 10 (`destroy`, portal empty and quota 0/2, site gone, state file and backup left behind, `git status` lists only tracked edits). The labs' own `sed` lines and Lab 9's heredoc are **read out of `content/lab/*.md`** and run as written |
| `policy` | Every rule in `policy.py`, refused by the real cloud through the real provider, with the message text: missing `owner` / `env` tag, region, `rg-` / `ci-` prefixes, image, oversize CPU and memory, port; each refusal is an error, is fast, leaves the tofu state empty, creates nothing in the portal and adds a `Failed` event to the activity log. Uses throw-away configs without variable validation, so the request really reaches the cloud |
| `curl_ca` | Lab 4: `curl https://management.dojo.cloud/metadata/endpoints...` works without `-k` as a student; the bundle variables are set; without them curl fails with 60 (the Lab 4 troubleshooting row); with `-k` it answers |
| `security` | What a curious student can and cannot do, as `student01` with `student02` as the victim. **ARM:** own login works; another student's subscription is 403 for read and write (also for an id that does not exist); no, garbage, payload-swapped (facilitator), unsigned (`alg none`) and wrong-key tokens are 401; wrong, empty and borrowed client secrets are refused. **Portal API:** a forged `X-Auth-User` (alone, or with an empty, wrong or guessed `X-Gateway-Token`) is 401 for `/me`, `/admin/progress` and `/admin/purge`; the student's environment and every readable `/proc/*/environ` lack `GATEWAY_TOKEN`. **Secrets:** not root, signing key unreadable, no sudo, no `docker.sock`; the broker gives a student their own subscription and a non-roster user nothing. **cloud-host:** not on the student network, the terminal not on the cloud network, no published ports, nothing answers from a student shell, no TCP listener for dockerd. **Student containers (T9.8):** the bridge has `enable_icc=false`; with two throw-away probe containers (`secchk-a`, `secchk-b`, removed before and after) A cannot reach B while cloud-host itself can (the control), and A cannot reach the Docker API through the bridge gateway or `cloud-api`; every deployed container has no privileges, no capabilities, `no-new-privileges`, no mounts, and non-zero memory, CPU and pids limits (skipped with a note if nothing is deployed, so run it after `track_b` or with `--keep`). The one write it attempts, a PUT into the other student's subscription, must be refused |
| `restart` | (`--with-restart`) after `restart workshop_cloud_host`: `/readyz` is 200 within the bound, the deployed container is back by itself within its bound, the portal shows it `Running`, `plan` says `No changes`, no container group was re-created, and `destroy` still works |

The time bounds in the restart area come from PLAN T8.10 (`/readyz` back after 9-13 s, site after 8-12 s, plain stop 5.5-6.5 s)
with slack, counted from the moment the restart is issued. `podman kill` (a hand stop) does **not** restart the host by
itself; the area uses `restart`.

## load.sh

```text
--students N          default 30. Refuses (exit 2, says why) if workshop_terminal has fewer accounts than N
--wave-size K         start K at a time (default 0 = all at once); --wave-gap S between waves (default 20)
--pollers P           class-overview portal pollers (default 3), every 3 s, plus the facilitator's progress board and /readyz
--sample-interval S   container samples every S seconds (default 2)
--max-failures 0  --max-p95-apply 120  --max-portal-p95-ms 2000  --max-readyz-failures 0     (the thresholds)
--step-timeout 600  --run-timeout 1800
--purge-first / --no-purge / --keep / --cleanup-only / --dry-run
```

Each student, as their own account and concurrently: `clone` the starter repo, `init`, `apply` (2 resources), `site` (poll
until the page answers), `tag_apply` (the Lab 8 tag edit, an in-place update), `destroy`. A failed step skips the rest except
`destroy`. One CSV row per student per step: `steps.csv` (`user,step,start_ms,ms,rc,ok`). Beside it, for the whole run:
`stats.csv` (`podman stats` of `workshop_cloud_host`, `workshop_cloud_api`, `workshop_terminal`, about every 2 s), `portal.csv`
(latency and status of the class overview, the progress board and `/readyz`, polled from inside cloud-api), and before/after
OOM and restart facts. The report (`report.txt`, also printed) gives p50/p95/max per step, each failure with the tail of its
output, peak memory per container (against its limit, and the kernel's `memory.peak`), the portal latencies, the flow wall time,
and a verdict per threshold: failed steps, p95 of `apply`, p95 of the class overview, `/readyz` non-200 samples, and "no
container OOM-killed / restarted and no process inside OOM-killed". Cleanup then destroys everything (8 at a time) and asserts
the portal is empty for all N; leftovers are a FAIL and are purged.

`--keep` skips cleanup (deployments stay; students' `~/load-*` stay). Empty them later with
`tests/load.sh --cleanup-only --students N`, which also works after a crash.

**Memory warning.** N students at once means N `tofu` processes, each with an `azurerm` provider process (over 200 MB on
disk, size in memory unmeasured), inside the ONE container `workshop_terminal` (its default limit is 4 GB, `WEB_TERMINAL_MEM_LIMIT`).
The dev box this was written on has about 9.9 GB and 8 CPUs. 30 at once may not fit: a process killed by the kernel's OOM killer
shows up as a failed step, and the report flags `oom_kill` and container restarts. Start with `--students 10 --wave-size 5`, read
the peak memory, then scale up. The script prints its own guess (about 250 MB per student, unmeasured) and warns if that exceeds
the terminal's limit or 70% of the host. It also stresses `cloud-host` (60 containers if every apply lands), whose 3 GB
ceiling is exactly what T9.3 is meant to measure.

**Accounts.** `engine/.env` on this box says `STUDENT_COUNT=20`, so `--students 30` is refused with instructions (raise
`STUDENT_COUNT`, `./run.sh stop`, start again). The `testuserN` demo-bot accounts are not used.

**What the load numbers are and are not.** The portal is polled through cloud-api's plain-HTTP port, so its latency excludes
Caddy and the allocator. The load is real `tofu` + real `azurerm` against the real control plane, so `apply` latency includes the
provider's own poll ticks (about 35 s alone). Forgejo takes N concurrent clones at the start, which the class would do too but is
not measured.

## What these scripts cannot prove

- **They have run against one stack only:** rootless podman on the 9.9 GB dev box, 2026-09-21 (281 + 11 e2e checks, load at 5/10/15). Not docker proper, not arm64, not 20+ students.
- The gateway: Caddy routing, `forward_auth`, the browser session, the `/admin` tabs, and the portal or labs in a **real browser**
  (T9.9). Portal actions are driven through the API, not by clicking.
- Real people (T9.4), other workshops (T9.5), arm64, docker proper (only what `CONTAINER_CLI=docker` happens to get right; nothing here
  was run with it; T9.8 must be repeated on the Azure VM's dockerd before a delivery there). The gateway's own header handling is not part of the
  `security` area either: it talks to cloud-api directly, so Caddy's `header_up` is not exercised.
- `git push` (it needs the Forgejo password and would write to the shared repo): Labs 3 and 10's push step is not run.
- The Lab 6 "optional" scratch-copy of the region test is replaced by the `policy` area (same cloud message, other route).
- The precise timings: they are bounds with slack, not measurements. `apply` ~35 s, `destroy` ~35 s, replace ~27 s, in-place ~1-2 s come from the labs.

## Assumptions to check first if something fails oddly

1. Container names are the defaults (`workshop_terminal`, `workshop_cloud_api`, `workshop_cloud_host`), else set the environment variables.
2. The starter repo was seeded into Forgejo as `iac-team/tofu-basics` (from `workshop.env`). If the clone fails, e2e falls back to a copy of
   `content/sample-repo` and says so; the load test has no fallback (its `clone` step just fails).
3. `podman exec -u <user> ... zsh -lc` gives the shell the same `ARM_*` variables as a real terminal (`zshenv` -> `dojo-env` -> broker), and
   plain-text (`-no-color`) tofu output matches the labs' text after whitespace is collapsed (checks ignore line breaks and runs of spaces).
4. The portal API accepts `X-Auth-User` + the container's `GATEWAY_TOKEN` on `127.0.0.1:8080`; `python3` exists in the cloud-api image (it is Python).
5. `podman stats --format json` has the keys `name`, `mem_usage`, `cpu_percent`, `pids` (checked on podman 5.7 here); `docker` gets `{{json .}}` instead.
6. Activity-log operation names (`Create/Update container group`, `Delete container group (portal)`, ...) are those in `server.py`; the tests match them exactly.
7. The Lab 6 sed lines and the Lab 8/9 commands are found in the lab files by their first characters; if a lab is reworded the test says which line it cannot find.
8. `memory.peak` / `memory.events` exist in the containers' cgroup (cgroup v2); if not, those two facts are just omitted.
9. Timing checks (`apply` under 120 s, refusals under 30 s) are generous bounds for one student; under load use `load.sh`.

## Selftest

`selftest/run.sh` runs these scripts against `selftest/mock/`: a fake `podman` that executes "student" commands locally with a fake
`terraform`/`git`/`curl` and forwards the portal helpers to a mock of the portal API. It proves the harness logic (argument
handling, control flow, CSV and report, thresholds, the cleanup and purge path, refusal when there are too few accounts, the
assertion helpers, secret masking). It proves **nothing** about the stack or the labs.
