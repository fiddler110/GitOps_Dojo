# CTF-3: Secrets and Misconfiguration

The third session in the CTF series (`docs/CTF-WORKSHOP-PLAN.md`): two medium/hard, self-contained attack
targets from the `ctf-range` module's ladder, grouped by how the exploit works -- leaked credentials and
how far they reach. See the plan's section 8 for how this session fits with CTF-1, CTF-2, CTF-4 and CTF-5.

## Running it

```sh
./dojo ctf-secrets-config --dry-run    # what would build and start; checks manifests and image pins
./dojo ctf-secrets-config              # then open http://localhost:8080
./dojo ctf-secrets-config --test 2 --fast   # demo bots, one round, no pacing (CLAUDE.md)
```

## The ladder, this session

| Target id | Lab | What it teaches |
|---|---|---|
| `leaky-config` | 1 | An ops admin panel exposes a debug log and a stale config backup; the log leaks a service credential reused on a second endpoint (A05) |
| `git-secrets` | 2 | A deploy token committed, then "cleaned up" in a later commit -- still live in git history, not revoked (ties `git-fundamentals`) |

Target source, images and reference solve scripts: `modules/ctf-range/targets/<id>/`. This pack only
*wires* them (which two, and which image tag each builds into `ctf-host`) -- never rebuilds the images
themselves (students attack, never patch them; CTF-5's `customer-portal` is the only target that rebuilds
on a merge).

**A planned third lab, not yet built:** row 11, `tfstate-treasure` (ties `tofu-basics` +
`vault-fundamentals` -- a committed `terraform.tfstate` leaking an AppRole credential into a Vault path).
Per the plan it belongs in this session, but it has no target image yet. It is deliberately **not** in
`CTF_ATTACK_TARGETS` or `CTF_HOST_EXPECTED_IMAGES` above -- adding it is future work, not a missing wire-up
in this pack. See `docs/CTF-WORKSHOP-PLAN.md` row 11 and `FACILITATOR.md`'s note.

## Why this pack exists on top of `ctf-range`

`ctf-range` is the reusable module (targets, firewall, the flag service, terminal tools, `ctf-host`/
`ctf-controller`); every CTF session lists it in `MODULES=`. Per CTF-D26, `ctf-range`'s own
`module.env` defaults build the **full** 14-target catalog into `ctf-host` -- fine for
`workshops/ctf-defend-test`'s shared facilitator harness, wasteful for a real single-session pack that
only exposes 2. This pack overrides three vars to scope the image to just its own two targets:

```sh
CTF_HOST_BUILD_TARGET=ctf-host-ctf3      # ctf-host/Dockerfile's named stage for this session
CTF_HOST_IMAGE=gitopsdojo/ctf-host:ctf3  # a distinct tag, so building this pack never clobbers another's cache
CTF_HOST_EXPECTED_IMAGES=...             # the subset that stage actually bakes in
CTF_ATTACK_TARGETS=leaky-config=...,git-secrets=...
```

See `modules/ctf-range/module.env`'s own comment on these vars, and `ctf-host/Dockerfile`'s `ctf-host-ctf3`
stage, for the mechanics.

## What's here

- [`workshop.env`](workshop.env): identity, `MODULES="ctf-range"`, the CTF-D26 scoping vars above, and
  `CTF_CONTROL_TOKEN` (dev value; generate a real one for a live class).
- [`content/slides/`](content/slides/): the hub, a briefing deck that sets the scenario and the rules of
  engagement **without naming any target's specific bug**, the labs index/overview, and a session-mechanics
  cheat sheet (tool mechanics live in the module's **Lab Info** card instead).
- [`content/lab/`](content/lab/): `lab1.md`-`lab2.md`, one per target, each guiding toward the technique
  with two rounds of hints before pointing at that target's own `exploit-guide/<id>.md` -- the full
  spoiler walkthrough, deliberately not linked from the browser nav (`dojo` only syncs `content/lab/*.md`
  into the browsable lab reader, not the `exploit-guide/` subfolder, so it's reachable from a terminal
  `cat`/`glow` but not one click away).
- [`content/sample-repo/`](content/sample-repo/): seeded into Forgejo as `training/ctf-secrets-config`,
  separate from each student's own per-student `internal-tools` repo that `git-secrets`'s own terminal hook
  provisions (`modules/ctf-range/terminal/start.d/55-git-secrets.sh`) -- this one just mirrors the
  engagement brief for anyone who wants it in git form.
- [`achievements/`](achievements/): a minimal catalog, engine-level (gated by `ACHIEVEMENTS_ENABLED` plus
  this folder existing -- not a `MODULES=` entry). Two process milestones (`recon-versions`, matched on
  `nmap -sV`; `recon-full-sweep`, matched on `nmap -p-`) reward scanning properly before attacking, and one
  core milestone per target (`l1-flag`, `l2-flag`), each matched on the `ctf`/`flag_solved` adapter event
  `ctf-flags` already posts with `challenge=<target-id>` -- no new plumbing needed, same shape `ctf-access`
  already uses.

## Facilitator view

The `/admin` workspace's **Attack Range** tab shows every student's slot state and lets you stop/reset
one; it does not itself show solved state (see below) -- that's the achievements leaderboard's job. There
is no attacker-bot swarm or SOC feed in CTF-1/CTF-2/CTF-3 -- that's CTF-5 only.

## Status

Built from `workshops/ctf-access`'s structure on `feat/ctf-refinement`, content and manifest only --
**not yet live-verified as its own pack**. `leaky-config` and `git-secrets` were already proven against the
real gateway/firewall/`ctf-controller` path on the shared `ctf-defend-test` harness
(`docs/CTF-WORKSHOP-PLAN.md`'s checkpoint, `CTF-SPIKES.md` S8). What's new and unproven here is this pack's
own `CTF_HOST_BUILD_TARGET=ctf-host-ctf3` scoping and its content; `./dojo ctf-secrets-config --dry-run`
has been run, but no live stack start. Rehearse before a room (see `FACILITATOR.md`).
