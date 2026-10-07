# CTF-4: Trusting the Wrong Thing

The fourth session in the CTF series (`docs/CTF-WORKSHOP-PLAN.md`): two Medium/Hard, self-contained
attack targets from the `ctf-range` module's ladder, grouped by what gets trusted that shouldn't be --
a component, and a rule. See the plan's section 8 for how this session fits with CTF-1 through CTF-5.

## Running it

```sh
./run.sh ctf-trust-chain --dry-run    # what would build and start; checks manifests and image pins
./run.sh ctf-trust-chain              # then open http://localhost:8080
./run.sh ctf-trust-chain --test 2 --fast   # demo bots, one round, no pacing (CLAUDE.md)
```

## The ladder, this session

| Target id | Lab | What it teaches |
|---|---|---|
| `dns-resolver-cve` | 1 | A real CVE (CVE-2022-30295) in a pinned old DNS resolver -- the resolver itself is an attack surface (A06), ties `dns-as-code` |
| `policy-bypass` | 2 | An authorization rule with no bug, just the wrong logic -- the policy compiles and passes its tests and is still wrong (A04), ties `cloud-policy-as-code` |

Target source, images and reference solve scripts: `modules/ctf-range/targets/<id>/`. This pack only
*wires* them (which two, and which image tag each builds into `ctf-host`) -- never rebuilds the images
themselves (students attack, never patch them; CTF-5's `customer-portal` is the only target that rebuilds
on a merge).

**A planned third lab, not yet built.** Target 10 `runner-escape` ("a workflow in a fork runs
attacker-controlled code on a shared runner") belongs on this session's ladder per the plan but has no
image yet (plan section 8: "no container slot" shape, like `tfstate-treasure`). It needs `runner-pool` in
`MODULES=` and the pack's own start hook (the way `workshops/ctf-defend-test` does it, same scoping
reasoning as `tfstate-treasure` needing `openbao`). Adding it later means: add `runner-pool` to `MODULES`,
write `compose/terminal/start.d/96-runner-escape.sh`, add a third row to `content/lab/` and
`content/slides/labs.md`, and a third achievement milestone -- no change to this pack's existing two labs.

## Why this pack exists on top of `ctf-range`

`ctf-range` is the reusable module (targets, firewall, the flag service, terminal tools, `ctf-host`/
`ctf-controller`); every CTF session lists it in `MODULES=`. Per CTF-D26, `ctf-range`'s own
`module.env` defaults build the **full** 14-target catalog into `ctf-host` -- fine for
`workshops/ctf-defend-test`'s shared facilitator harness, wasteful for a real single-session pack that
only exposes 2. This pack overrides three vars to scope the image to just its own two targets:

```sh
CTF_HOST_BUILD_TARGET=ctf-host-ctf4      # ctf-host/Dockerfile's named stage for this session
CTF_HOST_IMAGE=gitopsdojo/ctf-host:ctf4  # a distinct tag, so building this pack never clobbers another's cache
CTF_HOST_EXPECTED_IMAGES=...             # the subset that stage actually bakes in
CTF_ATTACK_TARGETS=dns-resolver-cve=...,policy-bypass=...
```

See `modules/ctf-range/module.env`'s own comment on these vars, and `ctf-host/Dockerfile`'s `ctf-host-ctf4`
stage, for the mechanics.

## What's here

- [`workshop.env`](workshop.env): identity, `MODULES="ctf-range"`, the CTF-D26 scoping vars above, and
  `CTF_CONTROL_TOKEN` (dev value; generate a real one for a live class).
- [`content/slides/`](content/slides/): the hub, a briefing deck that sets the scenario and the rules of
  engagement **without naming either target's specific bug**, the labs index/overview, and a session-mechanics
  cheat sheet (tool mechanics live in the module's **Lab Info** card instead).
- [`content/lab/`](content/lab/): `lab1.md`-`lab2.md`, one per target, each guiding toward the technique
  with two rounds of hints before pointing at that target's own `exploit-guide/<id>.md` -- the full
  spoiler walkthrough, deliberately not linked from the browser nav (`run.sh` only syncs `content/lab/*.md`
  into the browsable lab reader, not the `exploit-guide/` subfolder, so it's reachable from a terminal
  `cat`/`glow` but not one click away). `dns-resolver-cve` is two flags (a captured credential, then a
  replayed one) -- the lab walks both.
- [`content/sample-repo/`](content/sample-repo/): seeded into Forgejo as `training/ctf-trust-chain`, but
  **not used by any lab** -- CTF-4 has no git exercise. It just mirrors the engagement brief for anyone who
  wants it in git form.
- [`achievements/`](achievements/): a minimal catalog, engine-level (gated by `ACHIEVEMENTS_ENABLED` plus
  this folder existing -- not a `MODULES=` entry). Two process milestones (`recon-versions`, matched on
  `nmap -sV`; `recon-full-sweep`, matched on `nmap -p-`) reward scanning properly before attacking, and one
  core milestone per flag (`l1-flag-token`, `l1-flag` for `dns-resolver-cve`'s two flags; `l2-flag` for
  `policy-bypass`), each matched on the `ctf`/`flag_solved` adapter event `ctf-flags` already posts with
  `challenge=<target-id>` -- no new plumbing needed, the achievements module already supports this exact
  event shape (see `ctf-access`'s own README for the precedent).

## Facilitator view

The `/admin` workspace's **Attack Range** tab shows every student's slot state and lets you stop/reset
one; it does not itself show solved state -- that's the achievements leaderboard's job. There is no
attacker-bot swarm or SOC feed in CTF-1/CTF-4 -- that's CTF-5 only.

## Status

Built by porting the `ctf-access` (CTF-1) pack's structure to targets 6 and 9, following
`docs/CTF-WORKSHOP-PLAN.md` section 8. The two targets themselves (`dns-resolver-cve`, `policy-bypass`)
and `ctf-host`'s `ctf-host-ctf4` stage already existed and were previously built; only this pack's own
scoping and content are new here. Not yet live-verified as its own pack -- rehearse before a room
(see `FACILITATOR.md`).
