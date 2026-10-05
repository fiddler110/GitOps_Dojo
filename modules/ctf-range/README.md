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
> exploit-gate on PR, rebuild→redeploy on merge); and the **range control
> plane** — the boxed `ctf-host` Docker-in-Docker daemon and its one client
> `ctf-controller` (CTF-D21 / spike S14), which owns the per-student target
> slots and performs the live redeploy-in-place the pipeline calls. The
> `ctf-flags` submission service (§5 — the controller renders flags inline for
> now), the in-lab **registry** + CI build that `defend-main.yml` pushes to
> (spike S6), the firewall/isolation hooks and SNAT (spikes CTF-S2/S3), the
> CTF-1 to CTF-4 start/stop toggle + queue (CTF-D20), and the CTF-5 live bots /
> SOC feed / **wall of shame** (§8) are **not built yet**. Do not wire a
> workshop to this module expecting a full range.

## Layout

- `module.env` — module defaults a `workshop.env` overrides (the pattern every
  module follows; see `modules/runner-pool/module.env`).
- `compose.yml` — layered onto `engine/docker-compose.yml` by `engine/run.sh`
  when a `workshop.env` lists `ctf-range` in `MODULES`. Relative paths resolve
  against `engine/`, **not** this folder. Defines the `ctf_net` target network,
  a single dev instance of target 14, and the control plane (`ctf-host` +
  `ctf-controller`) on the internal `ctf_ops` network.
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

## Range control plane (CTF-D21 / spike S14)

```
defend pipeline (merge) ─POST /redeploy─▶ ctf-controller ─unix socket─▶ ctf-host (dind)
allocator / admin      ─GET  /slots────▶   (ctf_ops)                     └─ slot per student
```

The controller never speaks to the host daemon and never builds an image; it
pulls an allow-listed tag (base, or what the in-lab registry serves) and
recreates a slot **under the same name and published port**, so a patched image
replaces the running one in place without moving its address. Verified live
(podman, `STUDENT_COUNT=2`): base import → one hardened slot per student each
with its own §5 flag → exploit dumps the flag from a managed slot → `/redeploy`
recreates the slot from a parameterized image (~0.5 s) → the same port now
returns **zero rows, no flag** (CTF-D19 green) while an un-redeployed slot still
leaks, proving the swap is in-place and per-slot.

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
