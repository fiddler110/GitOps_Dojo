# CTF-5: Defend

The fifth and final session in the CTF series (`docs/CTF-WORKSHOP-PLAN.md`): a live incident on the
student's own app, defended with a PR, a CI gate and a redeploy -- the only session where students patch
instead of attack. See the plan's section 8 for how this session fits with CTF-1 through CTF-4.

## Running it

```sh
./dojo ctf-defend --dry-run    # what would build and start; checks manifests and image pins
./dojo ctf-defend              # then open http://localhost:8080
```

## The targets, this session

Three live targets per student at once (the "Defend lab redesign" in the plan), attacked in a per-student
order on a stagger, so unfixed breaches pile up and the student has to triage.

| Target | Severity (weight) | Signal in the SIEM | The flaw |
|---|---|---|---|
| `customer-portal` | high (3) | request log | SQL injection in the customer search |
| `policy-bypass` | medium (2) | audit log | a policy that trusts a tag the requester wrote about themselves |
| `leaky-config` | low (1) | file-access + auth log | an unauthenticated log read, then reuse of the credential it shows |

Each student gets **three own Forgejo repos** (named for the target, app source only, no exploit script) that
drive a redeploy of that slot on merge. The attacks are run by the platform's checker (`dojo check` and the PR
gate), whose scripts students cannot read. Target source: `modules/ctf-range/targets/<target>/`; the seeded
copies live in `content/sample-repos/<target>/` (refresh them with `content/sync-sample-repos.sh`).

## Why this pack exists on top of `ctf-range` and `runner-pool`

`ctf-range` supplies the target, the firewall and the per-student slot (`ctf-host`/`ctf-controller`);
`runner-pool` supplies the Forgejo Actions runner the defend pipeline's PR gate and merge-redeploy jobs
need (`.forgejo/workflows/defend-pr.yml`, `defend-main.yml` in `content/sample-repos/_common/`). This is the only
CTF pack that lists `runner-pool` purely for its own students' pipelines, not for the range control plane
(`ctf-trust-chain` also lists it, but for `runner-escape`'s target, not the student's own CI).

This pack also runs the **attacker-bot swarm and SOC feed** (plan §8.2-8.11): one container for the whole
room, idle until the facilitator presses **Start Attack Swarm** on the SOC `/admin` tab, then
driving the green → yellow → red clock against every student's slot at once. No other CTF pack runs it
live by default -- see `compose/docker-compose.override.yml`'s header comment.

## What's here

- [`workshop.env`](workshop.env): identity, `MODULES="ctf-range runner-pool"`, `FORGEJO_REPO=customer-portal`,
  `CTF_DEFEND_TARGETS` / `CTF_PORT_STRIDE` / `CTF_TARGET_STAGGER`, and `CTF_BUILD_TOKEN`/`CTF_CONTROL_TOKEN` derived from this install's `GATEWAY_TOKEN` (never a literal
  secret in the repo). No `CTF_ATTACK_TARGETS` -- this session doesn't use the student-controlled ladder.
- [`content/slides/`](content/slides/): the hub, a briefing deck covering the incident framing and the
  clone/fix/PR/merge flow **without naming the bug**, the lab overview, and a cheat sheet of the session's
  own git/exploit-check commands (tool mechanics live in the module's **Lab Info** card instead).
- [`content/lab/`](content/lab/lab1.md): one lab as incident triage -- briefing, the detect/triage/contain/fix/verify
  loop, the toolset (`git`, editor, `python3`, `curl`, the SIEM, `dojo check`), a nudge-only hint ladder per
  target, and a per-target plus overall debrief. Every fact a student needs is discoverable without a hint.
- [`content/sample-repos/`](content/sample-repos/): the three target repos' source and the shared workflows
  (`_common/`), which `compose/terminal/start.d/90-ctf-defend.sh` provisions per student into Forgejo
  (`<student>/<target>`), Actions secrets included. `content/sample-repo/` is the engine's master seed
  (a copy of `customer-portal`).
- [`compose/`](compose/): the per-student repo/secrets provisioning hook, the terminal link, and the
  overlay that adds the room-wide `attacker-bot` service (moved here from `modules/ctf-range` -- see its
  header comment).
- [`achievements/`](achievements/): milestones on each target's PR lifecycle and the SOC feed's containment
  signal, funny unlocks on the swarm's recon/exploit/dump events, and a capstone (`achievements/capstone.json`)
  for closing the second, un-gated injection point in `customer-portal`'s `/login`.

## Scoring

`CTF_SCORE_FACTOR` (default 5 points per unit): per target green 2 units, yellow 1, red 0, times the target's
weight (3 / 2 / 1). Time to contain and MTTP are displayed, not scored. The bonus second flaw (CTF-D17) and
`CTF_BONUS_FLAWS` are gone.

## Facilitator view

The `/admin` workspace's **SOC** tab is this session's equivalent of CTF-1 through CTF-4's Attack
Range tab: it shows the room-wide swarm clock and is where the facilitator starts it. There is no
start/stop/reset per student -- the targets are always on. Per-student order and start offsets come from
the controller's `GET /schedule`.

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
