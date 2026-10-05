# ctf-range module

The reusable runtime for the CTF workshop series (see
`docs/CTF-WORKSHOP-PLAN.md`). The range holds the vulnerable **targets**, the
`ctf_net` network they live on, the `ctf-flags` submission service, the extra
terminal tools, and — for CTF-5 — the attacker swarm, SOC feed and wall of
shame. Each CTF session is a thin workshop pack (`workshops/ctf-*`) that lists
`MODULES="ctf-range ..."`, names which targets it enables, and ships its own
labs and slides.

> **Status: scaffold.** Built so far: **target 14 `customer-portal`** (CTF-5's
> app-code defend target, decision CTF-D25) with its informational **SAST
> stage** (CWE-89, CTF-S17/D23/D24) and its **defend pipeline** (the S6 scan +
> exploit-gate on PR, rebuild→redeploy on merge); the **range control
> plane** — the boxed `ctf-host` Docker-in-Docker daemon and its one client
> `ctf-controller` (CTF-D21 / spike S14), which owns the per-student target
> slots and performs the live redeploy-in-place the pipeline calls; and now
> the **in-lab registry + `ctf-builder`** (spike S6's remaining half):
> `defend-main.yml` POSTs a ref to `ctf-builder`, which clones the student's
> own repo itself, builds and pushes it via `ctf-host`'s socket under the
> slot's own tag, then the same job POSTs `ctf-controller`'s `/redeploy` to
> swap the running slot in place. The `ctf-flags` submission service (§5 —
> the controller renders flags inline for now), the firewall/isolation hooks
> and SNAT (spikes CTF-S2/S3), the CTF-1 to CTF-4 start/stop toggle + queue
> (CTF-D20), and the CTF-5 live bots / SOC feed / **wall of shame** (§8) are
> **not built yet**. Do not wire a workshop to this module expecting a full
> range, and note `ctf-builder`/`ctf-controller`'s `runner_net` reachability
> only does anything once a workshop pack also lists `runner-pool` in
> `MODULES` (see "Range control plane" below) — no such pack exists yet.

## Layout

- `module.env` — module defaults a `workshop.env` overrides (the pattern every
  module follows; see `modules/runner-pool/module.env`).
- `compose.yml` — layered onto `engine/docker-compose.yml` by `engine/run.sh`
  when a `workshop.env` lists `ctf-range` in `MODULES`. Relative paths resolve
  against `engine/`, **not** this folder. Defines the `ctf_net` target
  network, a single dev instance of target 14, and the control plane
  (`ctf-host`, `ctf-controller`, `registry`, `ctf-builder`) split across the
  internal `ctf_ops` network and (for `ctf-builder` and `ctf-controller`) the
  `runner_net` network that `modules/runner-pool` owns — see "Range control
  plane" below for which service sits on which network, and why.
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
  lives only here, never in a target. Unit tests in `ctf-controller/tests/`.
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

## Safety (holds for every target — §6)

- Targets only ever live on `ctf_net`: no route to the internet, the gateway,
  Forgejo or `workshop_lab`.
- Every target is built from original, minimal source in this repo. Public-CVE
  software, when a target needs it, is pinned by digest and never reachable
  from outside `ctf_net`.
- All lab data is synthetic and derived from the student's in-lab handle — no
  real PII, ever (CTF-P2b review rule).
