# runner-pool module

Single-use Forgejo Actions runners for every repo, autoscaled, with a Runners panel in `/admin`.

Add it with `MODULES="runner-pool"` in a `workshop.env`. Built for `vault-fundamentals`, whose plan
(`docs/archive/VAULT-FUNDAMENTALS-PLAN.md` §6) has the design. Each runner takes **one job** and is then deleted with
everything the job left behind, so no job (a student's own or anyone else's) ever finds another's files or processes:
the way GitHub's Actions Runner Controller works. Don't list it together with `forgejo-runner` (a long-lived runner
for one repo): both turn on Actions and define `runner_net`.

| Part | What it does |
|---|---|
| `compose.yml` | Turns on Actions in `git-server` (new forks included: Forgejo makes forks with Actions off by default) and puts it on the internal `runner_net`. Adds `runner-pool` (the runners, on `runner_net` only), `runner-pool-shim` (Caddy in the pool's network namespace) and `runner-controller` (on `workshop_lab` only), and their named volumes. |
| `pool/Dockerfile` | `forgejo-runner:13` plus what the supervisor needs (`util-linux`, `shadow`, Python, `tini`) and what most steps call (`bash`, `curl`, `jq`, `git`). A workshop adds tools with the build arg `JOB_TOOLS` in its overlay (e.g. `"bao sops"`): they are copied from the terminal image `run.sh` has just built (`TOOLS_IMAGE`), so jobs run the students' own pinned binaries. They must be static binaries (this image is Alpine). |
| `pool/supervise.py` | The supervisor, with no network listener. For each config the controller drops in `/spool/start/`, it creates a Linux user of the runner's name (home `0700`, umask 077, its own `TMPDIR`) and runs `forgejo-runner one-job --wait` as that user inside its own user + PID namespace, with `prlimit` caps. When the runner exits it kills what the user left running, deletes its files in `/tmp`, `/var/tmp` and `/dev/shm`, and removes the user with its home (one `useradd`/`userdel` at a time). `/spool/stop/<name>` stops an idle runner; a busy one is never stopped. It writes each runner's state to `/spool/state.json` every second. Jobs run in this container (the `host` label). |
| `shim/Caddyfile` | Answers for `PUBLIC_BASE_URL` inside the pool: Forgejo gives jobs its public URL for git and for the Actions ID token, and malforms the token URL under `/git/` (`/git//gitapi/...`). The shim sends both to `git-server`. On an `https://` name it serves with its own CA, which the supervisor adds to the pool's trust store before starting any runner. |
| `controller/controller.py` | Stdlib Python on the allocator's image. Holds the Forgejo admin login (the pool never sees it). Every 3 s it reads the runners and waiting jobs from the admin API and the supervisor's state, deletes registrations whose runner is gone (Forgejo shows a dead runner as idle for a while), and in **Auto** keeps `RUNNER_MIN_IDLE` runners ready plus one per waiting job, up to the max, removing an idle one above that after `RUNNER_IDLE_TIMEOUT`. Three failed starts within a minute pause Auto's starts for a minute. **Manual** does nothing by itself. Every class starts in Auto. |
| `controller/panel.*` | The Runners panel: a light per runner (green ready, yellow running a job with the repo, red failed / offline in Forgejo / stuck past `RUNNER_JOB_TIMEOUT`), − / + (in Auto they move the warm-idle minimum; in Manual they add a runner or remove an idle one; at the max, + raises the max too), Auto / Manual, jobs waiting, min, max with its own − / + (the facilitator's call: 1 up to 24, or `RUNNER_MAX` if higher, since every runner shares `RUNNER_POOL_MEM_LIMIT`; lowering it in Auto removes the idle runners above it at once, never a busy one), recent problems. Strict CSP, no inline script or style, every string set with `textContent`. |
| `extensions.json` | The `/admin` tab **Runners** and the `/runners` route on the `facilitator` gate (prefix stripped); the status-strip check on `/healthz`, which is 200 while the controller's loop reaches Forgejo. No landing card: students see their runs in Forgejo. |
| `tests/test_controller.py` | Unit tests for the controller against a fake Forgejo and spool: `python3 -B -m unittest discover -s modules/runner-pool/tests -p 'test_*.py'`. |
| `tests/pool.sh` | On the real stack: the warm pool, two concurrent jobs that can't see each other, clean-up, a burst up to the max, panel access and CSRF, Manual − / +. `sh modules/runner-pool/tests/pool.sh`. |

**The controller checks every request itself**, because anything on `workshop_lab` can reach it: `X-Gateway-Token`
must match and `X-Auth-User` must be `FACILITATOR_USERNAME`. POSTs also need `X-Requested-With: dojo-runners`, which a
cross-site form can't send and a cross-site `fetch` can't send without a CORS preflight it never answers. Requests are
served from the loop's snapshot, never with a Forgejo call of their own.

**Why a process pool and not containers:** the stack has no container-engine socket anywhere, and this keeps it that
way. The pool is one container that drops every capability except the six its supervisor uses (CHOWN, DAC_OVERRIDE, FOWNER, SETUID, SETGID, KILL) and sets `no-new-privileges`; the ID-token shim keeps only NET_BIND_SERVICE. Podman's default seccomp profile still applies. Its weak point is that runners
running at the same moment share a kernel and a filesystem; users, namespaces and umask keep them apart, and each is
thrown away after one job. Hosts that block unprivileged user namespaces (e.g. Ubuntu 24.04's AppArmor
`kernel.apparmor_restrict_unprivileged_userns=1`) stop the runners from starting: they turn red on the panel.

**Rootful Podman with SELinux (e.g. Podman on macOS)** stops them too (`unshare: mount /proc failed`): the runtime masks
parts of `/proc`, and SELinux denies the mount. Both must be lifted, only for the pool, by setting
`RUNNER_POOL_SECURITY_OPT_1=unmask=/proc/*` and `RUNNER_POOL_SECURITY_OPT_2=label=type:container_engine_t` in
`engine/.env` (gitignored, so per machine). Unset, they default to `no-new-privileges=true` and bare `no-new-privileges` (Compose rejects two equal items), so nothing changes. Docker
doesn't accept `unmask=`; leave them unset there.

**Settings** (`module.env`; set them in `workshop.env` or `engine/.env`): `RUNNER_MIN_IDLE` (2), `RUNNER_MAX` (empty:
`ceil(STUDENT_COUNT / 3)`, 2 to 12), `RUNNER_IDLE_TIMEOUT` (120 s), `RUNNER_JOB_TIMEOUT` (900 s), `RUNNER_LABELS`
(`host:host`), `RUNNER_POOL_MEM_LIMIT` (2g) and `RUNNER_POOL_PIDS` (2048) for the whole pool, and per runner process
`RUNNER_NPROC` (256), `RUNNER_NOFILE` (1024) and `RUNNER_AS` (address space in bytes, empty for none).

**A workshop using it** lists it in `MODULES`, names its job tools and puts on `runner_net` whatever its jobs may call,
from its overlay (list form: lists append):

```yaml
services:
  openbao:
    networks:
      - runner_net
  runner-pool:
    build:
      args:
        JOB_TOOLS: "bao sops"
```

Jobs use `runs-on: host`. The runners serve every repo on the instance, so students can run workflows in their own
forks.

## Controller credentials (FIND-16, T5.2c/d)

`runner-token-init` is a one-shot service that signs in once with the Forgejo admin login and writes a
`write:admin` token (`runner-controller`) to the `runner_controller_token` volume; `runner-controller` mounts it
read-only and no longer gets `FORGEJO_ADMIN_PASSWORD` (it re-reads the file on every call, and shows "waiting"
until it exists). A leaked controller environment now yields a revocable token, not the admin login.
The token is still admin-scoped: Forgejo's runner endpoints accept no narrower scope.

Compose `secrets:` under podman-compose (evaluated from docs and existing behaviour only, not run here):
1. podman-compose supports file-based `secrets:` (bind-mounted at `/run/secrets/<name>`) but not `environment:`
   secrets, and support for `mode`/`uid`/`gid` varies by version.
2. That needs a host file holding the value, i.e. another plaintext copy beside `engine/.env`, and `./run.sh stop`
   would have to delete it; the named volume above is wiped with the rest.
3. Not adopted: revisit if the engine gains a secrets directory. Needs a live check on this machine's version.
