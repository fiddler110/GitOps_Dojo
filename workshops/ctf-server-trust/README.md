# CTF-2: Server-side Trust and APIs

The second session in the CTF series (`docs/CTF-WORKSHOP-PLAN.md`): four medium/hard-tier, self-contained
attack targets from the `ctf-range` module's ladder, grouped by how the exploit works -- the server
trusting input or the caller a little too much. See the plan's section 8 for how this session fits with
CTF-1 and CTF-3 through CTF-5.

## Running it

```sh
./dojo ctf-server-trust --dry-run    # what would build and start; checks manifests and image pins
./dojo ctf-server-trust              # then open http://localhost:8080
./dojo ctf-server-trust --test 2 --fast   # demo bots, one round, no pacing (CLAUDE.md)
```

## The ladder, this session

| Target id | Lab | What it teaches |
|---|---|---|
| `ping-tool` | 1 | OS command injection in a "network diagnostics" page (A03) |
| `ssrf-fetcher` | 2 | Server-side request forgery against an internal-only endpoint (A10 / SSRF) |
| `api-mass-assignment` | 3 | A `PATCH` that binds the whole request body, `role` included (API3 BOPLA) |
| `api-bfla` | 4 | An admin route that checks the token is valid, never that it's a facilitator (API5 BFLA) |

Target source, images and reference solve scripts: `modules/ctf-range/targets/<id>/`. This pack only
*wires* them (which four, and which image tag each builds into `ctf-host`) -- never rebuilds the images
themselves (students attack, never patch them; CTF-5's `customer-portal` is the only target that rebuilds
on a merge).

## Why this pack exists on top of `ctf-range`

`ctf-range` is the reusable module (targets, firewall, the flag service, terminal tools, `ctf-host`/
`ctf-controller`); every CTF session lists it in `MODULES=`. Per CTF-D26, `ctf-range`'s own
`module.env` defaults build the **full** 14-target catalog into `ctf-host` -- fine for
the module default's full catalog, wasteful for a real single-session pack that
only exposes 4. This pack overrides three vars to scope the image to just its own four targets:

```sh
CTF_HOST_BUILD_TARGET=ctf-host-ctf2      # ctf-host/Dockerfile's named stage for this session
CTF_HOST_IMAGE=gitopsdojo/ctf-host:ctf2  # a distinct tag, so building this pack never clobbers another's cache
CTF_HOST_EXPECTED_IMAGES=...             # the subset that stage actually bakes in
CTF_ATTACK_TARGETS=ping-tool=...,ssrf-fetcher=...,api-mass-assignment=...,api-bfla=...
```

See `modules/ctf-range/module.env`'s own comment on these vars, and `ctf-host/Dockerfile`'s `ctf-host-ctf2`
stage, for the mechanics.

## What's here

- [`workshop.env`](workshop.env): identity, `MODULES="ctf-range"`, the CTF-D26 scoping vars above, and
  `CTF_CONTROL_TOKEN` (dev value; generate a real one for a live class).
- [`content/slides/`](content/slides/): the hub, a briefing deck that sets the scenario and the rules of
  engagement **without naming any target's specific bug**, the labs index/overview, and a session-mechanics
  cheat sheet (tool mechanics live in the module's **Lab Info** card instead).
- [`content/lab/`](content/lab/): `lab1.md`-`lab4.md`, one per target, each guiding toward the technique
  with two rounds of hints before pointing at that target's own `exploit-guide/<id>.md` -- the full
  spoiler walkthrough, deliberately not linked from the browser nav (`dojo` only syncs `content/lab/*.md`
  into the browsable lab reader, not the `exploit-guide/` subfolder, so it's reachable from a terminal
  `cat`/`glow` but not one click away).
- [`content/sample-repo/`](content/sample-repo/): seeded into Forgejo as `training/ctf-server-trust`, but
  **not used by any lab** -- CTF-2 has no git exercise. It just mirrors the engagement brief for anyone who
  wants it in git form.
- [`achievements/`](achievements/): a minimal catalog, engine-level (gated by `ACHIEVEMENTS_ENABLED` plus
  this folder existing -- not a `MODULES=` entry). Two process milestones (`recon-versions`, matched on
  `nmap -sV`; `recon-full-sweep`, matched on `nmap -p-`) reward scanning properly before attacking, and one
  core milestone per target (`l1-flag`..`l4-flag`), each matched on the `ctf`/`flag_solved` adapter event
  `ctf-flags` already posts with `challenge=<target-id>` -- no new plumbing needed, the achievements module
  already supports this exact event shape. This is what gives students a leaderboard/points confirmation
  beyond `dojo-flag submit`'s own CLI response.

## Facilitator view

The `/admin` workspace's **Attack Range** tab shows every student's slot state and lets you stop/reset
one; it does not itself show solved state (see below) -- that's the achievements leaderboard's job. There
is no attacker-bot swarm or SOC feed in CTF-1/CTF-2 -- that's CTF-5 only.

## Status

Content and wiring only -- not yet live-verified as its own pack. The four targets themselves
(`ping-tool`, `ssrf-fetcher`, `api-mass-assignment`, `api-bfla`) were already built and have reference
solve scripts under `modules/ctf-range/targets/<id>/exploit/solve.py`, proven against the shared
range's shared full-catalog image (plan checkpoint). This pack's own `CTF_HOST_BUILD_TARGET=
ctf-host-ctf2` scoping and its content are new and unproven as a pack -- rehearse before a room (see
`FACILITATOR.md`).

**Known gap, same as CTF-1:** the achievements catalog below gives each flag its own milestone but hasn't
been live-verified end to end on this pack (the recon milestones' shell match in particular -- confirm a
plain `nmap -sV -p- <ip>` actually fires `recon-versions`/`recon-full-sweep` on a real run before trusting
this for a class).
