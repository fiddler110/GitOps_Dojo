# CTF-3: Secrets and Misconfiguration — facilitator guide

For the person running the session. The technical reference is [`README.md`](README.md); the deck's
speaker notes carry the talking points. This guide is the practical part: before, during, after, and
what to do when something breaks.

**Honest status:** content and manifest built from `workshops/ctf-access`'s structure on
`feat/ctf-refinement`, **not yet live-verified as its own pack**. The two targets themselves
(`leaky-config`, `git-secrets`) were already built and live-verified against the real
gateway/firewall/`ctf-controller` path on the range's shared full-catalog image
(`docs/CTF-WORKSHOP-PLAN.md`'s checkpoint, `CTF-SPIKES.md` S8) — what's new and unproven here is this
pack's own `CTF_HOST_BUILD_TARGET=ctf-host-ctf3` scoping and its content. Only `--dry-run` has been run
against this pack so far. Do a full rehearsal below before a room.

## The session at a glance (about 115 minutes)

| Block | Minutes | What |
| ----- | ------- | ---- |
| Talk | ~15 | The scenario, rules of engagement, the Attack Range card, scanning before guessing |
| Lab 1 | ~35 | `leaky-config` — an exposed admin log leaks a credential, reused on a second endpoint |
| Lab 2 | ~45 | `git-secrets` — a deploy token "cleaned up" from a file, still live in git history |
| Lab 3 | ~35 | `tfstate-treasure` — a committed `terraform.tfstate` leaks a vault AppRole login; debrief in the Vault Audit tab |
| Recap | ~20 | What surprised them; the "deleting is not revoking" lesson; point out the exploit guides for anyone who didn't finish |

**No lab depends on another.** Students can do them in any order and start fresh from the **Attack
Range** card each time — there is no `lab-prep <N>` here because there's nothing sequential to catch up
on. `git-secrets` runs longer in practice than `leaky-config`: reading `git log -p` output and finding the
right commit takes most rooms longer than reading one log file, budget accordingly.

**Lab 3 needs OpenBao.** `openbao` is in `MODULES`, and this pack's hooks (`compose/terminal/start.d/95-tfstate-treasure.sh`, `compose/openbao-setup.d/60-tfstate-treasure.sh`) seed each student's `infra-state` repo and the AppRole behind it. No student policy is attached to a student's own vault login, so the leaked AppRole is the only way in. The debrief is the facilitator's **Vault Audit** tab: the role login and the read, per student.

**One target live per student, by design (CTF-D20).** Starting a target stops whatever was live; this
caps the room at one attack container per student regardless of how many targets exist. Flags are
per-student HMACs, so a student who moves on and comes back can always re-derive and resubmit the same
flag later — nothing about restarting or resetting a target changes what the correct flag is.

**`git-secrets` needs its own per-student repo to exist before the lab makes sense.** The terminal hook
`modules/ctf-range/terminal/start.d/55-git-secrets.sh` seeds each student's `<user>/internal-tools` repo
in Forgejo at container start (a no-op for any other pack; it only acts when `git-secrets` is in
`CTF_ATTACK_TARGETS`, which this pack's `workshop.env` sets). If a student's repo is missing, check
Forgejo came up before the terminal container finished its `start.d` pass — a known race on a very slow
first boot; the hook retries on a bounded wait, but a terminal container that started before Forgejo's
admin API was ready can still miss it.

**Don't volunteer hints from the stage.** The slides deliberately never name a specific bug, and each
lab already has two rounds of hints built in, closer to an answer each time. If someone's stuck, ask
*where they've looked*, not *what the bug is* — and remind them the exploit guide exists before telling
them what's in it.

## Before the session

**A day ahead**

1. `./dojo setup` if there is no `.env`. Set `PUBLIC_BASE_URL`, `GATEWAY_TOKEN`,
   `STUDENT_COUNT`.
2. Generate a real `CTF_CONTROL_TOKEN` for `workshop.env` (the committed value is a dev placeholder) —
   it gates the Attack Range's start/stop/reset API.
3. `./dojo ctf-secrets-config`. First build takes a few minutes longer than most packs: `ctf-host` builds
   its `ctf-host-ctf3` stage (the 2-target image, not the full 14-target catalog — CTF-D26) on top of
   `docker:dind`. Open `/admin` and wait for **Forgejo**, **Terminals**, **Slides** and **Attack Range**
   to go green.
4. **Size the machine:** `./dojo capacity ctf-secrets-config --students 30` if you expect a full room —
   the range adds `ctf-host`/`ctf-controller` on top of the terminals; see `module.env`'s
   `CTF_HOST_MEM_LIMIT`/`CTF_CONTROLLER_MEM_LIMIT`.
5. **Rehearse as a student** in a private window: run `nmap -sV -p- <ip>` at least once and confirm the
   **recon-versions**/**recon-full-sweep** achievements fire (toast or the student's achievements page),
   then start each of the two targets from the Attack Range card, solve each with the lab's hints alone
   (or the exploit guide, to confirm it's accurate), submit the flag, and confirm its milestone
   (`l1-flag`, `l2-flag`) lands on the leaderboard. For `git-secrets`, confirm your own seeded
   `<student>/internal-tools` repo exists in Forgejo and that `git log -p` on `deploy.sh` actually shows
   the token in the earlier commit. **The Attack Range card itself still shows no solved state**
   (stopped/queued/starting/live only) -- the achievements leaderboard is where "solved" actually shows up
   in this pack. Then `./dojo stop` and start clean.
6. Skim the deck with speaker notes on.

**On the day, 15 minutes before**

- Start the stack; confirm `/` (landing cards, including **Attack Range**), `/slides` and `/admin`
  all green.
- Keep `/admin`'s **Attack Range** tab on a second screen: it shows every student's slot state (stopped,
  queued, starting, live) and lets you stop or reset one. For who's solved what, check the achievements
  leaderboard instead — the Attack Range tab itself has no solved column.

## During the session

**What you can see.** `/admin` tabs: Roster, VS Code, Terminal, Forgejo, Slides, **Lab Info**, **Attack
Range**.

- **Scanning is the first real step, not filler.** A student who skips straight to the real port and
  guesses will stall; nudge them back to `nmap -sV -p-` on their slot IP.
- **Decoy ports are decoys.** Both targets publish a decoy SSH listener on container port 2222 that
  accepts nothing real — that dead end is intentional, not a bug report waiting to happen.
- **`leaky-config` has a deliberate red herring.** `ops-dashboard.conf.bak` looks like a leaked secret (a
  DB connection string) but unlocks nothing; the real leak is one `WARN` line in `app.log`. A student
  fixated on the `.bak` file has found the decoy, not the bug — point them back at the log, not at the
  answer.
- **`git-secrets` has no bug in the running app at all.** If a student starts fuzzing the target's own
  HTTP endpoints looking for a flaw, that's a sign they've missed the point — the whole foothold is in
  Forgejo's git history, not in `ctf_net`. Redirect them to their own `internal-tools` repo.
- **A queued start.** If the whole room clicks Start together, requests queue (`CTF_ATTACK_MAX_CONCURRENT`
  in the module); the card shows "queued, position N" — tell students this is normal, not stuck.
- **Lagging student:** there's no `lab-prep` to fast-forward with (no sequential state to catch up on) —
  point them at whichever lab's hints they want and let them start that target directly.

**Updating content mid-session.** Slides and labs are bind-mounted; edits to `content/slides/` show
immediately, an edited lab file reaches `~/lab` on the next terminal restart, never overwriting a
student's own work.

## When something breaks

| Symptom | Likely cause and fix |
| ------- | -------------------- |
| Attack Range card won't start a target | Check `/admin`'s Attack Range tab for a queue backlog or an error state; `CTF_CONTROL_TOKEN` mismatch fails closed with no mutation, not a crash |
| A solved flag won't resubmit / shows wrong | Flags are per-student HMACs — a flag copied from a classmate will never verify; confirm the student is submitting their own |
| A student's `internal-tools` repo is missing or empty | Forgejo's admin API likely wasn't ready when `55-git-secrets.sh` ran at terminal start; restart that student's terminal (Roster → Release, or `./dojo restart web-terminal`) so the hook retries |
| `nmap` on the slot IP times out entirely | The per-uid firewall rule may not have landed yet (a known race on a very slow first boot, `50-ctf-range.sh` retries up to 180s) — wait and retry before assuming the target is broken |
| A target never goes healthy after Start | `ctf-host`'s own healthcheck retry budget; give it a minute before treating it as stuck, especially right after `./dojo ctf-secrets-config` first starts |
| Student reused a classmate's target | Shouldn't be reachable at all — the firewall only permits a student's own slot IP; report this as a real bug, not a lab mistake |
| One student's terminal wedged | Roster → **Release**; **Reset** on the Attack Range tab returns their current target to its clean image (their flag, if already submitted, still verifies the same way after) |

## After the session

- `./dojo stop` wipes everything — containers, volumes, every student's slot, every account.
- Note anything that confused the room or a wrong timing in `ROADMAP.md` and fix the lab.
- If `tfstate-treasure` gets built, this is the pack to extend: add it to `CTF_ATTACK_TARGETS` and
  `CTF_HOST_EXPECTED_IMAGES`, add `lab3.md` + its exploit guide + `l3-flag`, and update the timing above.
