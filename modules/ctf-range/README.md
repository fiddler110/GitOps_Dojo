# ctf-range module

The reusable runtime for the CTF workshop series (see
`docs/CTF-WORKSHOP-PLAN.md`). The range holds the vulnerable **targets**, the
`ctf_net` network they live on, the `ctf-flags` submission service, the extra
terminal tools, and — for CTF-5 — the attacker swarm, SOC feed and wall of
shame (the wall's plumbing is built; the swarm/feed that should drive it is
not — see "Wall of shame" below). Each CTF session is a thin workshop pack
(`workshops/ctf-*`) that lists `MODULES="ctf-range ..."`, names which targets
it enables, and ships its own labs and slides.

> **Status: scaffold.** Built so far: **target 14 `customer-portal`** (CTF-5's
> app-code defend target, decision CTF-D25) with its informational **SAST
> stage** (CWE-89, CTF-S17/D23/D24) and its **defend pipeline** (the S6 scan +
> exploit-gate on PR, rebuild→redeploy on merge); the **range control
> plane** — the boxed `ctf-host` Docker-in-Docker daemon and its one client
> `ctf-controller` (CTF-D21 / spike S14), which owns the per-student target
> slots and performs the live redeploy-in-place the pipeline calls; the
> **in-lab registry + `ctf-builder`** (spike S6's remaining half):
> `defend-main.yml` POSTs a ref to `ctf-builder`, which clones the student's
> own repo itself, builds and pushes it via `ctf-host`'s socket under the
> slot's own tag, then the same job POSTs `ctf-controller`'s `/redeploy` to
> swap the running slot in place; and now the **`ctf-flags` submission
> service** (§5 — a student's own HMAC flag, verified against the same seed
> `ctf-controller` renders slots with, credits the achievement through the
> usual signed adapter path) plus the **per-uid target reachability wiring**
> (spikes CTF-S2/S3): `web-terminal` joins `ctf_net`, and
> `terminal/start.d/50-ctf-range.sh` restricts each student's uid to exactly
> their own slot's published port on `ctf-host`. No SNAT is needed — CTF-D21's
> boxed `ctf-host` (one address, one port per slot, `--icc=false`) made the
> plan's original per-target-network/SNAT sketch moot; see that hook's header
> comment. Also now: the **wall of shame**'s event source, storage and page
> (§8.12) — `modules/achievements`' `store.wall_rows()` and
> `GET /achievements/wall`, driven entirely by `ctf`/`dump_success` events,
> LIVE while they keep arriving for a (student, target), DISCONNECTED once
> they stop, dropped once quiet long enough to age off. **Nothing posts that
> event yet except a manual stand-in**
> (`modules/ctf-range/tools/simulate-dump.py`) — the real attacker-bot
> persona swarm and SOC feed it should be driven by (§8.2-8.11) are a
> separate, larger task, not built; see "Wall of shame" below. Also now: the
> **offensive tool suite** (plan §9) in `terminal/Dockerfile` — `nmap`/`ncat`,
> `tcpdump`/`tshark`, `sqlmap`, `jq`, `john`, `dnsutils`/`dnsrecon`, `httpie`,
> `whois`, plus `ffuf` and `opa` (sha256-pinned static binaries) and a small
> generic wordlist subset. Also now: the **Lab Info library content**
> (plan §9, CTF-D16, phase CTF-P2b) — a Linux/shell primer plus one primer
> per tool above (`terminal/content/lab-info/`), each covering mechanics
> only (what the tool is, its common flags, reading its output, a worked
> example against a toy/neutral target) and never a lab-specific payload,
> answer or hint. Baked into the image at `/etc/skel/lab-info`, so every
> account `provision-account.sh` creates — student, bot, or a reset
> rebuilding a home — gets its own `~/lab-info` copy for free, with no
> engine change; the facilitator gets one at `/root/lab-info` directly. Also
> now: that same content read in the browser — `compose.yml`'s
> `ctf-lab-info` (stock Caddy, `file_server`, mounting `terminal/content/lab-info`
> read-only) plus this module's `extensions.json` (a "Lab Info" card,
> `/admin` tab, and `gate: "shared"` route — one copy, identical for every
> student). Also now: the **CTF-1 to CTF-4 start/stop toggle + queue** (plan
> §4 "Student-controlled targets, one live per slot", decision CTF-D20) — a
> new `AttackManager` in `ctf-controller/controller.py`, separate from the
> always-on CTF-5 reconcile loop above: a FIFO start/reset queue (at most
> `CTF_ATTACK_MAX_CONCURRENT` jobs at once), a per-student state machine
> (stopped/queued/starting/live/error), and a time-based idle auto-stop
> (`CTF_ATTACK_IDLE_SECONDS` — a documented simplification; the controller
> has no visibility into a target's actual traffic). Fully generic over
> `CTF_ATTACK_TARGETS` (`module.env`), which defaults to empty — the real
> target-1..4 images are CTF-S8, not built yet — so wiring one in is a
> config change, never a code change. The card itself
> (`ctf-controller/static/`, `extensions.json`'s `"ctf-attack"` id) is a
> small page `ctf-controller` serves directly behind the gateway's
> `identity` gate, polling `GET attack/status` and driving
> `POST attack/{start,stop,reset}`. Do not wire a workshop to this
> module expecting a full range, and note
> `ctf-builder`/`ctf-controller`'s `runner_net` reachability only does
> anything once a workshop pack also lists `runner-pool` in `MODULES` (see
> "Range control plane" below) — no such pack exists yet.

## Layout

- `module.env` — module defaults a `workshop.env` overrides (the pattern every
  module follows; see `modules/runner-pool/module.env`).
- `compose.yml` — layered onto `engine/docker-compose.yml` by `engine/run.sh`
  when a `workshop.env` lists `ctf-range` in `MODULES`. Relative paths resolve
  against `engine/`, **not** this folder. Defines the `ctf_net` target
  network (now carrying `ctf-host` and `web-terminal` — the only address a
  student's terminal may reach at all), a single dev instance of target 14,
  `ctf-flags` on `workshop_lab`, and the control plane (`ctf-host`,
  `ctf-controller`, `registry`, `ctf-builder`) split across the internal
  `ctf_ops` network and (for `ctf-builder` and `ctf-controller`) the
  `runner_net` network that `modules/runner-pool` owns — see "Range control
  plane" below for which service sits on which network, and why. The
  `web-terminal` fragment here adds only `ctf_net` and uses the **map** form
  (`ctf_net: {}`) because the base service's own `networks:` is map-form,
  for the `terminal_ingress` alias (`engine/docker-compose.yml`) — mixing
  list and map fails `up` under podman-compose (CLAUDE.md).
- `targets/<name>/` — one self-contained vulnerable target per directory. Each
  builds to its own image and carries its own README, flaw and reference
  exploit. `targets/customer-portal/` is target 14.
- `ctf-host/` — the boxed privileged Docker-in-Docker daemon that holds the
  target slots. The `cloud-host` pattern from `dojo-cloud`: `internal`-only,
  publishes nothing, reachable only over a unix socket shared with the
  controller. The target image is baked in at build and imported offline at
  start. **Privileged is acceptable only because of this boxing** (§6).
- `ctf-controller/` — the single, unprivileged client of `ctf-host` (stdlib
  Python). Its whole reach is `docker_api.Executor` (pull / create / start /
  stop / rm — never build). It reconciles one always-on slot per student
  (CTF-5 model) and serves `POST /redeploy`, the live tail of the S6 loop that
  `defend-main.yml` calls. `flags.py` renders the §5 per-slot flag; the seed
  lives only here, never in a target. A second class, `AttackManager`, is the
  CTF-1 to CTF-4 toggle (CTF-D20): its own queue/state machine, its own slot
  name and port range, nothing shared with reconcile() except the executor.
  Its `/attack/*` HTTP paths are gateway-identity-gated (`GATEWAY_TOKEN` +
  `X-Auth-User`, `dojo_http.py` — the `SHARED=` copy in `module.env`), a
  different scheme from `/redeploy`'s Bearer control token, and reachable
  because this service is now also on `workshop_lab` (compose.yml). Its page
  shell lives in `static/`. Unit tests in `ctf-controller/tests/`.
- `ctf-builder/` — the single, unprivileged client that may ask `ctf-host` to
  **build** (stdlib Python; spike S6). The only thing `ctf-controller`
  deliberately never does — see `ctf-controller/docker_api.py`'s docstring.
  Clones the student's own repo itself from `git-server`, builds it
  server-side via `ctf-host`'s Engine API `/build`, and pushes it under the
  slot's own tag via the same API — never accepts a tar, build context or
  Dockerfile from its caller. Serves `POST /build` on `runner_net` only
  (never `ctf_ops`). Unit tests in `ctf-builder/tests/`.
- `registry` (compose service, no own folder — the stock `registry:2` image,
  pinned by digest) — the in-lab image registry `ctf-builder` pushes to and
  `ctf-host`'s `dockerd` pulls from. Internal-only, `ctf_ops` only, no
  published port, no auth (never reachable from a student or the internet).
- `ctf-flags/` — the flag submission service (plan §5; stdlib Python).
  Verifies a submitted flag against the same per-slot HMAC `ctf-controller`
  renders slots with (own copy of the tiny `flags.py`, deliberately not
  shared — see its header), then credits the achievement over the same
  signed `/api/adapter` path `dns-gate`/`cloud-api`/`openbao-audit` use. On
  `workshop_lab`, reachable directly by every student's terminal — `user` is
  self-asserted (whoever's uid the CLI ran as), which is fine here because
  the real secret is the flag value, not the identity claim (see the
  service's header). Unit tests in `ctf-flags/tests/`.
- `terminal/` — this module's link in the terminal build chain
  (`engine/run.sh`). Ships `dojo-flag` (the CLI for `ctf-flags`),
  `start.d/50-ctf-range.sh` (the per-uid firewall hook, spikes CTF-S2/S3),
  and the offensive tool suite (plan §9): apt-installed `nmap`/`ncat`,
  `tcpdump`/`tshark`, `sqlmap`, `jq`, `john`, `dnsutils`/`dnsrecon`,
  `httpie`, `whois` (apt's own signature check is the trust basis, same as
  every other apt install in this repo); sha256-pinned static binaries
  `ffuf` (content discovery) and `opa` (policy evaluation, for target 9);
  `wordlist-common.txt`, a short generic path/name list with nothing
  lab-specific in it; and `content/lab-info/` (plan §9, CTF-D16, CTF-P2b),
  the Linux/shell primer plus one primer per tool above, baked into
  `/etc/skel/lab-info` so every account gets its own `~/lab-info` for free.
  One shared image for every session (CTF-D16: the Lab Info library, and so
  the tools it documents, is the same regardless of which targets a pack
  enables).
- `lab-info/Caddyfile` — config for `compose.yml`'s `ctf-lab-info` service: a
  stock Caddy `file_server` over the same `terminal/content/lab-info`
  directory, so a student can read the library in the browser (this
  module's `extensions.json` card/route/admin tab) as well as at
  `~/lab-info` in the terminal or VS Code.

## Range control plane (CTF-D21 / spike S14, build/push half spike S6)

```
runner_net (modules/runner-pool):
  defend-main.yml job ──POST /build─────▶ ctf-builder
  (runs in the pool)  ──POST /redeploy───▶ ctf-controller (dual-homed, below)

ctf_ops (this module):
  allocator / admin ──GET /slots────────▶ ctf-controller ──▶ ctf-host (dind) ──▶ registry
                                                                  ▲  (pull on redeploy,
  ctf-builder is NOT on ctf_ops — it reaches ctf-host ────────────┘   push on build)
  over the SAME shared socket volume (not a network hop)
```

`ctf-controller` never speaks to the host daemon except pull/create/start/
stop/rm and never builds an image; it pulls an allow-listed tag (base, or what
the in-lab registry serves) and recreates a slot **under the same name and
published port**, so a patched image replaces the running one in place
without moving its address. Verified live (podman, `STUDENT_COUNT=2`): base
import → one hardened slot per student each with its own §5 flag → exploit
dumps the flag from a managed slot → `/redeploy` recreates the slot from a
parameterized image (~0.5 s) → the same port now returns **zero rows, no
flag** (CTF-D19 green) while an un-redeployed slot still leaks, proving the
swap is in-place and per-slot.

`ctf-builder` is the only thing allowed to ask `ctf-host` to **build**,
answering the open half of spike S6 (a build+push capability reachable from a
plain CI process with no socket of its own). It shares `ctf-host`'s socket
exactly as `ctf-controller` does (same volume, same socket gid), but is a
member of `runner_net` only — never `ctf_ops` — so the only thing that can
ever reach its `/build` endpoint is a Forgejo Actions job in the runner pool.
It never accepts a tar, build context or Dockerfile from its caller: it
clones the student's own repo itself (from `git-server`, also on
`runner_net`), tars that clone, and builds+pushes through `ctf-host`'s Engine
API under one fixed tag (the slot's own name under the approved registry
prefix) — the narrowing is "one approved output", the mirror image of
`ctf-controller`'s "one approved input" allow-list.

**Design choice — a separate `ctf-builder`, not a second `ctf-host`
listener.** Considered instead: have `ctf-host` itself expose the Engine
API's `/build` on a second network interface facing `runner_net`, skipping a
new service. Rejected: that would put the privileged dind box itself on a
network a CI job can reach, growing its blast radius to the whole Engine API
(not just `/build`) and mixing concerns into the one container that already
carries the most dangerous capability in the range. A small, unprivileged,
stdlib-Python shim that clones+tars itself and only ever calls `/build` then
`/images/*/push` is strictly narrower, costs one more small container, and
keeps `ctf-host` exactly as boxed as `ctf-controller` already trusts it to be.

**Why `ctf-controller` is on both `ctf_ops` and `runner_net`, but
`ctf-builder` only on `runner_net`.** `defend-main.yml` needs to call both
services directly, and `ctf-builder` has no reason to ever talk to
`ctf-controller` (the CI job sequences build-then-redeploy itself, as two
separately authenticated calls) — so only `ctf-controller` needs the second
network. Widening `ctf-controller`'s reachability doesn't widen its
capability: every mutating route still fails closed on the same
constant-time control-token check (`_authed`) regardless of which network a
request arrives on, and `ctf-builder` holds a **different** token
(`CTF_BUILD_TOKEN`, not `CTF_CONTROL_TOKEN`) so a leaked build credential can
never redeploy a slot.

## Targets

| # | Name | Tier | Built | Notes |
|---|------|------|-------|-------|
| 14 | `customer-portal` | Hard | ✅ app + SAST + pipeline | CTF-5 app-code defend target (CTF-D25): SQL injection dumps a plaintext SQLite `customers` table; fix is to parameterize the query. Ships the CWE-89 SAST (informational) and the `.forgejo/workflows/` defend pipeline (CTF-D19 gate on PR; redeploy on merge needs `ctf-controller`). |

Targets 0–13 (the attack ladder, §7.3) are not built yet.

## Wall of shame (§8.12)

Built, as a minimal vertical slice — the plumbing a real attacker-bot swarm
will eventually drive, exercised today only by a manual stand-in:

- **Event source** (`modules/achievements`): a `ctf`/`dump_success` adapter
  event (`catalog.py`, `matcher.py`, alongside the existing `flag_solved`).
  `{source: "ctf", event: "dump_success", user, challenge}`, HMAC-signed over
  `/api/adapter` like every other module's events (dns-gate, cloud-api,
  openbao-audit).
- **Storage** (`store.py`'s `wall_rows()`): in-memory only (deliberately —
  it's a rolling "is the attacker still connected right now" signal, not a
  record worth a restart keeping), keyed by `(user, challenge)`. **LIVE**
  while fresh `dump_success` events keep arriving (`WALL_LIVE_WINDOW`, 90s);
  **DISCONNECTED** once they stop (the moment a patch lands and the next
  probe comes back empty — the same signal MTTP already counts); dropped
  entirely once quiet past `WALL_MAX_AGE` (30 min) — "ages off".
- **Page** (`GET /achievements/wall`, `GET /achievements/api/wall`): a plain
  table, same visibility tier as the leaderboard's `/api/board` (any
  signed-in caller sees the whole class, not just their own row). Not yet
  its own gate="shared" projector route per CTF-D18 — piggybacking on
  achievements' existing identity-gated mount was the pragmatic choice here,
  since giving it a dedicated route in `ctf-range`'s own `extensions.json`
  would make this module hard-depend on `achievements` always being in
  `MODULES`, which `workshops/ctf-defend-test` (and maybe other packs)
  deliberately isn't. Revisit once a real pack wires both modules together.
- **What posts the event today:** nothing automatic.
  `modules/ctf-range/tools/simulate-dump.py` signs and posts one manually,
  for exercising/demoing the above before the real source exists.
- **Not built:** the attacker-bot persona swarm and the SOC event feed
  (plan §8.2-8.11) that are supposed to post `dump_success` for real; the
  cyber map; the per-pack `CTF_WALL_OF_SHAME` render toggle (the flag exists
  in `module.env` but nothing reads it yet — the wall always renders when
  there's data); row payloads richer than `(user, challenge)` (e.g. a row
  count, CTF-D17's bonus cleartext-storage flaw).

## Safety (holds for every target — §6)

- Targets only ever live on `ctf_net`: no route to the internet, the gateway,
  Forgejo or `workshop_lab`.
- Every target is built from original, minimal source in this repo. Public-CVE
  software, when a target needs it, is pinned by digest and never reachable
  from outside `ctf_net`.
- All lab data is synthetic and derived from the student's in-lab handle — no
  real PII, ever (CTF-P2b review rule).
