# ctf-range module

The reusable runtime for the CTF workshop series (see
`docs/CTF-WORKSHOP-PLAN.md`). The range holds the vulnerable **targets**, the
`ctf_net` network they live on, the `ctf-flags` submission service, the extra
terminal tools, and — for CTF-5 — the attacker swarm, SOC feed and wall of
shame. Each CTF session is a thin workshop pack (`workshops/ctf-*`) that lists
`MODULES="ctf-range ..."`, names which targets it enables, and ships its own
labs and slides.

> **Status: scaffold.** Only **target 14 `customer-portal`** (CTF-5's app-code
> defend target, decision CTF-D25) is built so far. The per-slot target
> fan-out (spike CTF-S1), the `ctf-flags` service (§5), the `ctf-controller`
> (spike S14), the firewall/isolation hooks (spikes CTF-S2/S3) and the CTF-5
> live bots / SOC feed / wall of shame (§8) are **not built yet**. Do not wire
> a workshop to this module expecting a full range.

## Layout

- `module.env` — module defaults a `workshop.env` overrides (the pattern every
  module follows; see `modules/runner-pool/module.env`).
- `compose.yml` — layered onto `engine/docker-compose.yml` by `engine/run.sh`
  when a `workshop.env` lists `ctf-range` in `MODULES`. Relative paths resolve
  against `engine/`, **not** this folder. Today it defines the `ctf_net`
  network and a single dev instance of target 14; the `STUDENT_COUNT`-driven
  fleet is spike CTF-S1.
- `targets/<name>/` — one self-contained vulnerable target per directory. Each
  builds to its own image and carries its own README, flaw and reference
  exploit. `targets/customer-portal/` is target 14.

## Targets

| # | Name | Tier | Built | Notes |
|---|------|------|-------|-------|
| 14 | `customer-portal` | Hard | ✅ scaffold | CTF-5 app-code defend target (CTF-D25): SQL injection dumps a plaintext SQLite `customers` table; fix is to parameterize the query. |

Targets 0–13 (the attack ladder, §7.3) are not built yet.

## Safety (holds for every target — §6)

- Targets only ever live on `ctf_net`: no route to the internet, the gateway,
  Forgejo or `workshop_lab`.
- Every target is built from original, minimal source in this repo. Public-CVE
  software, when a target needs it, is pinned by digest and never reachable
  from outside `ctf_net`.
- All lab data is synthetic and derived from the student's in-lab handle — no
  real PII, ever (CTF-P2b review rule).
