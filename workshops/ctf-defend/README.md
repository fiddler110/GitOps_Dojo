# CTF-5: Defend

The fifth and final session in the CTF series (`docs/CTF-WORKSHOP-PLAN.md`): a live incident on the
student's own app, defended with a PR, a CI gate and a redeploy -- the only session where students patch
instead of attack. See the plan's section 8 for how this session fits with CTF-1 through CTF-4.

## Running it

```sh
./dojo ctf-defend --dry-run    # what would build and start; checks manifests and image pins
./dojo ctf-defend              # then open http://localhost:8080
```

## The target, this session

| Target | What it teaches |
|---|---|
| `customer-portal` (target 14) | A SQL injection in a customer-lookup endpoint, found by reading the app's own source, fixed with a parameterized query, shipped through a PR that a CI gate re-tests before letting it merge (A03; the capstone closes the second, un-gated injection point in the same file) |

Unlike CTF-1 through CTF-4, there is no student-controlled attack ladder: `customer-portal` is always on,
one copy per student, and each student gets their **own Forgejo repo** (not a shared seed) that drives a
real redeploy on merge. Target source, the reference exploit/gate script and the SAST stage:
`modules/ctf-range/targets/customer-portal/`.

## Why this pack exists on top of `ctf-range` and `runner-pool`

`ctf-range` supplies the target, the firewall and the per-student slot (`ctf-host`/`ctf-controller`);
`runner-pool` supplies the Forgejo Actions runner the defend pipeline's PR gate and merge-redeploy jobs
need (`.forgejo/workflows/defend-pr.yml`, `defend-main.yml` in `content/sample-repo/`). This is the only
CTF pack that lists `runner-pool` purely for its own students' pipelines, not for the range control plane
(`ctf-trust-chain` also lists it, but for `runner-escape`'s target, not the student's own CI).

This pack also runs the **attacker-bot swarm and SOC feed** (plan §8.2-8.11): one container for the whole
room, idle until the facilitator presses **Start Attack Swarm** on the SOC Alerts `/admin` tab, then
driving the green → yellow → red clock against every student's slot at once. No other CTF pack runs it
live by default -- see `compose/docker-compose.override.yml`'s header comment.

## What's here

- [`workshop.env`](workshop.env): identity, `MODULES="ctf-range runner-pool"`, `FORGEJO_REPO=customer-portal`,
  and `CTF_BUILD_TOKEN`/`CTF_CONTROL_TOKEN` derived from this install's `GATEWAY_TOKEN` (never a literal
  secret in the repo). No `CTF_ATTACK_TARGETS` -- this session doesn't use the student-controlled ladder.
- [`content/slides/`](content/slides/): the hub, a briefing deck covering the incident framing and the
  clone/fix/PR/merge flow **without naming the bug**, the lab overview, and a cheat sheet of the session's
  own git/exploit-check commands (tool mechanics live in the module's **Lab Info** card instead).
- [`content/lab/`](content/lab/lab1.md): one lab -- clone your own repo, find the SQL injection by using
  the app and reading `app.py`, run the same exploit check the PR gate runs, fix it, PR it, merge it, watch
  the redeploy. No hint ladder here (unlike CTF-1 through CTF-4): the "stuck" path is the exploit check and
  the app's own source, not a spoiler file -- see `FACILITATOR.md`.
- [`content/sample-repo/`](content/sample-repo/): `customer-portal`'s source -- the exact repo
  `compose/terminal/start.d/90-ctf-defend.sh` provisions per student into Forgejo
  (`<student>/customer-portal`), Actions secrets included.
- [`compose/`](compose/): the per-student repo/secrets provisioning hook, the terminal link, and the
  overlay that adds the room-wide `attacker-bot` service (moved here from `modules/ctf-range` -- see its
  header comment).
- [`achievements/`](achievements/): milestones on the student's own Forgejo PR lifecycle
  (`m-opened`/`m-shipped`) and the SOC feed's own containment signal (`m-contained`), funny unlocks on the
  swarm's recon/exploit/dump events, and a capstone (`achievements/capstone.json`) for closing the second,
  un-gated injection point in `/login`.

## Bonus second flaw (toggle)

`CTF_BONUS_FLAWS=on|off` in `workshop.env` (default **on**; override in `.env` or the shell, e.g.
`CTF_BONUS_FLAWS=off ./dojo ctf-defend`). On, each defend target also carries a smaller flaw the bots never
exploit and the PR gate never blocks on: today `customer-portal`'s customer passwords are stored as typed,
`content/bonus/` is laid over the clean seed repo, the swarm's ordinary probes include data-at-rest paths,
and a hidden-until-found "Second Look" challenge (`achievements/challenges/c1.json`, two hints and an
answer) is worth one more scoring unit. Off, none of that exists: the repo is seeded clean, there is no
bonus CI step and no bonus points, and no lab or slide mentions a bonus (they never do; the bonus lives in
the repo overlay and the achievements challenge). Targets 8-11 are not part of this pack yet, so they have no
bonus here.

Scoring (`CTF_SCORE_FACTOR`, default 5 points per unit): green 2 units, yellow 1, red 0, plus 1 per bonus
fixed once the main fix is on `main`: 10/5/0 and +5. Achievements items `d-patched`, `d-unbreached`, `c1`.

## Facilitator view

The `/admin` workspace's **SOC Alerts** tab is this session's equivalent of CTF-1 through CTF-4's Attack
Range tab: it shows the room-wide swarm clock and is where the facilitator starts it. There is no
start/stop/reset per student -- the target is always on.

## Status

The range, target 14, its SAST stage, the defend pipeline and the attacker-bot swarm/SOC feed are built
and documented in `docs/CTF-WORKSHOP-PLAN.md`/`RELEASES.md`. This pack's own content (this file,
`FACILITATOR.md`, the deck, the cheat sheet) was written during a content audit of the whole CTF series
and has not yet had its own live rehearsal in a room -- `./dojo ctf-defend --dry-run` has been run, but no
live stack start. Rehearse before a class (see `FACILITATOR.md`).

## Wall of shame

`CTF_WALL_OF_SHAME=on|off` in `workshop.env` (default `on`) controls whether the room-wide wall of breached
students is drawn (landing-page widget at `/ctf-wall/` and a facilitator `/admin` tab). Off hides the display only;
events, status light, MTTP and incident summary are unaffected. Details: `modules/ctf-range/README.md`.
