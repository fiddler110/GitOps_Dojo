# CTF-1: Access and Identity

The first session in the CTF series (`docs/CTF-WORKSHOP-PLAN.md`): four low-tier, self-contained attack
targets from the `ctf-range` module's ladder, grouped by how the exploit works -- getting in when auth or
access checks are weak. See the plan's section 8 for how this session fits with CTF-2 through CTF-5.

## Running it

```sh
./dojo ctf-access --dry-run    # what would build and start; checks manifests and image pins
./dojo ctf-access              # then open http://localhost:8080
./dojo ctf-access --test 2 --fast   # demo bots, one round, no pacing (CLAUDE.md)
```

## The ladder, this session

| Target id | Lab | What it teaches |
|---|---|---|
| `sqli-login` | 1 | SQL injection login bypass (A03) |
| `weak-auth-portal` | 2 | A derivable, time-based password-reset token (A07) |
| `idor-pcap` | 3 | IDOR + credential reuse (A01 / API1 BOLA) |
| `cert-trust-bypass` | 4 | A client-cert check that never verifies the chain or expiry (A02), ties `cert-autorenewal` |

Target source, images and reference solve scripts: `modules/ctf-range/targets/<id>/`. This pack only
*wires* them (which four, and which image tag each builds into `ctf-host`) -- never rebuilds the images
themselves (students attack, never patch them; CTF-5's `customer-portal` is the only target that rebuilds
on a merge).

## Why this pack exists on top of `ctf-range`

`ctf-range` is the reusable module (targets, firewall, the flag service, terminal tools, `ctf-host`/
`ctf-controller`); every CTF session lists it in `MODULES=`. Per CTF-D26, `ctf-range`'s own
`module.env` defaults build the **full** 14-target catalog into `ctf-host` -- fine for
`workshops/ctf-defend-test`'s shared facilitator harness, wasteful for a real single-session pack that
only exposes 4. This pack overrides three vars to scope the image to just its own four targets:

```sh
CTF_HOST_BUILD_TARGET=ctf-host-ctf1      # ctf-host/Dockerfile's named stage for this session
CTF_HOST_IMAGE=gitopsdojo/ctf-host:ctf1  # a distinct tag, so building this pack never clobbers another's cache
CTF_HOST_EXPECTED_IMAGES=...             # the subset that stage actually bakes in
CTF_ATTACK_TARGETS=sqli-login=...,weak-auth-portal=...,idor-pcap=...,cert-trust-bypass=...
```

See `modules/ctf-range/module.env`'s own comment on these vars, and `ctf-host/Dockerfile`'s `ctf-host-ctf1`
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
- [`content/sample-repo/`](content/sample-repo/): seeded into Forgejo as `training/ctf-access`, but **not
  used by any lab** -- CTF-1 has no git exercise. It just mirrors the engagement brief for anyone who wants
  it in git form.
- [`achievements/`](achievements/): a minimal catalog, engine-level (gated by `ACHIEVEMENTS_ENABLED` plus
  this folder existing -- not a `MODULES=` entry). Two process milestones (`recon-versions`, matched on
  `nmap -sV`; `recon-full-sweep`, matched on `nmap -p-`) reward scanning properly before attacking, and one
  core milestone per target (`l1-flag`..`l4-flag`), each matched on the `ctf`/`flag_solved` adapter event
  `ctf-flags` already posts with `challenge=<target-id>` -- no new plumbing needed, the achievements module
  already supports this exact event shape (`modules/achievements/service/test_adapter_sources.py`'s own
  fixture uses `sqli-login`). This is what gives students a leaderboard/points confirmation beyond
  `dojo-flag submit`'s own CLI response; see "Known gap, closed" below.

## Facilitator view

The `/admin` workspace's **Attack Range** tab shows every student's slot state and lets you stop/reset
one; it does not itself show solved state (see below) -- that's the achievements leaderboard's job. There
is no attacker-bot swarm or SOC feed in CTF-1/CTF-2 -- that's CTF-5 only.

## Status

Built on `feat/zellij-terminal`, live-verified 2026-10-06: a cold `./dojo ctf-access` start, claimed a
student slot through the real `/assign` flow, started `sqli-login` through the real `/ctf-attack`
gateway route, solved it from inside the student's own terminal account (not a standalone `podman run`),
and submitted the flag through `dojo-flag submit`. The other three targets were already proven against
the same gateway/firewall/`ctf-controller` path on the shared `ctf-defend-test` harness
(`docs/CTF-WORKSHOP-PLAN.md`'s checkpoint); only this pack's own scoping and content were new here.

Found and fixed in that pass: `CTF_HOST_EXPECTED_IMAGES` needs to be a quoted value in any `workshop.env`
that overrides it (an unquoted multi-word shell assignment silently never persists) -- both this pack's
and `modules/ctf-range/module.env`'s own default now quote it.

**Known gap, closed:** the live test found no "solved" indicator anywhere except `dojo-flag submit`'s own
CLI response. `achievements/` (above) now gives each flag its own milestone and the room its usual
leaderboard/points/toast feedback -- validated statically with the engine's own
`modules/achievements/catalog/validate.py` (6 milestones, 4 core, 0 warnings) but **not yet live-verified
end to end** (the recon milestones' shell match in particular -- confirm a plain
`nmap -sV -p- <ip>` actually fires `recon-versions`/`recon-full-sweep` on a real run before trusting this
for a class).
