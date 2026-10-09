# CTF-1: Access and Identity — facilitator guide

For the person running the session. The technical reference is [`README.md`](README.md); the deck's
speaker notes carry the talking points. This guide is the practical part: before, during, after, and
what to do when something breaks.

**Honest status:** built on `feat/zellij-terminal`, not yet live-verified as its own pack. The four
targets themselves (`sqli-login`, `weak-auth-portal`, `idor-pcap`, `cert-trust-bypass`) were already
built and live-verified against the real gateway/firewall/`ctf-controller` path on the shared
`ctf-defend-test` test harness (`docs/CTF-WORKSHOP-PLAN.md`'s checkpoint) — what's new and unproven here
is this pack's own `CTF_HOST_BUILD_TARGET=ctf-host-ctf1` scoping and its content. Do the rehearsal below
before a room.

## The session at a glance (about 150 minutes)

| Block | Minutes | What |
| ----- | ------- | ---- |
| Talk | ~20 | The scenario, rules of engagement, the Attack Range card, scanning before guessing |
| Lab 1 | ~25 | `sqli-login` — auth-bypass SQL injection |
| Lab 2 | ~25 | `weak-auth-portal` — a derivable password-reset token |
| Lab 3 | ~30 | `idor-pcap` — IDOR + credential reuse |
| Lab 4 | ~30 | `cert-trust-bypass` — a client-cert check with no chain or expiry verification |
| Recap | ~10 | What surprised them; point out the exploit guides for anyone who didn't finish |

**No lab depends on another.** Students can do them in any order and start fresh from the **Attack
Range** card each time — there is no `lab-prep <N>` here because there's nothing sequential to catch up
on. In a shorter slot, drop Lab 4 first (it's the newest and leans on `cert-autorenewal` ideas a room
without that session hasn't seen yet).

**One target live per student, by design (CTF-D20).** Starting a target stops whatever was live; this
caps the room at one attack container per student regardless of how many targets exist. Flags are
per-student HMACs, so a student who moves on and comes back can always re-derive and resubmit the same
flag later — nothing about restarting or resetting a target changes what the correct flag is.

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
3. `./dojo ctf-access`. First build takes a few minutes longer than most packs: `ctf-host` builds its
   `ctf-host-ctf1` stage (the 4-target image, not the full 14-target catalog — CTF-D26) on top of
   `docker:dind`. Open `/admin` and wait for **Forgejo**, **Terminals**, **Slides** and **Attack Range**
   to go green.
4. **Size the machine:** `./dojo capacity ctf-access --students 30` if you expect a full room — the
   range adds `ctf-host`/`ctf-controller` on top of the terminals; see `module.env`'s
   `CTF_HOST_MEM_LIMIT`/`CTF_CONTROLLER_MEM_LIMIT`.
5. **Rehearse as a student** in a private window: run the lab's own `nmap -sV -p- <ip>` command at least
   once and confirm the **recon-versions**/**recon-full-sweep** achievements fire (toast or the student's
   achievements page), then start each of the four targets from the Attack Range card, solve each with the
   lab's hints alone (or the exploit guide, to confirm it's accurate), submit the flag, and confirm its
   milestone (`l1-flag`..`l4-flag`) lands on the leaderboard. **The Attack Range card itself still shows no
   solved state** (stopped/queued/starting/live only) -- the achievements leaderboard is where "solved"
   actually shows up in this pack, not the card or `/admin`'s Attack Range tab. The recon milestones are
   the one piece not yet live-verified (static catalog validation passed; the shell match itself hasn't
   been proven against a real session) -- this rehearsal is where that gets checked. Then `./dojo stop`
   and start clean.
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
- **Decoy ports are decoys.** `idor-pcap`'s FTP decoy even accepts the leaked credential and still says
  "Login incorrect" — that dead end is intentional, not a bug report waiting to happen.
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
| `nmap` on the slot IP times out entirely | The per-uid firewall rule may not have landed yet (a known race on a very slow first boot, `50-ctf-range.sh` retries up to 180s) — wait and retry before assuming the target is broken |
| A target never goes healthy after Start | `ctf-host`'s own healthcheck retry budget; give it a minute before treating it as stuck, especially right after `./dojo ctf-access` first starts |
| Student reused a classmate's target | Shouldn't be reachable at all — the firewall only permits a student's own slot IP; report this as a real bug, not a lab mistake |
| One student's terminal wedged | Roster → **Release**; **Reset** on the Attack Range tab returns their current target to its clean image (their flag, if already submitted, still verifies the same way after) |

## After the session

- `./dojo stop` wipes everything — containers, volumes, every student's slot, every account.
- Note anything that confused the room or a wrong timing in `ROADMAP.md` and fix the lab.
