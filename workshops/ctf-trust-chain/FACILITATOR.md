# CTF-4: Trusting the Wrong Thing — facilitator guide

For the person running the session. The technical reference is [`README.md`](README.md); the deck's
speaker notes carry the talking points. This guide is the practical part: before, during, after, and
what to do when something breaks.

**Honest status:** both targets (`dns-resolver-cve`, `policy-bypass`) were already built and
live-verified against the real gateway/firewall/`ctf-controller` path on the shared `ctf-defend-test`
test harness (`docs/CTF-WORKSHOP-PLAN.md`'s checkpoint) and `ctf-host`'s `ctf-host-ctf4` stage already
exists. What's new and unproven here is this pack's own content and `CTF_HOST_BUILD_TARGET=ctf-host-ctf4`
scoping as a standalone pack. Do the rehearsal below before a room.

## The session at a glance (about 115 minutes)

| Block | Minutes | What |
| ----- | ------- | ---- |
| Talk | ~20 | The scenario, rules of engagement, the Attack Range card, scanning before guessing |
| Lab 1 | ~45 | `dns-resolver-cve` — a real CVE in a pinned old DNS resolver; two flags, a captured credential then a replay |
| Lab 2 | ~40 | `policy-bypass` — a policy with no bug, just the wrong rule |
| Recap | ~10 | What surprised them; point out the exploit guides for anyone who didn't finish; mention the planned `runner-escape` third lab |

**No lab depends on another.** Students can do them in any order and start fresh from the **Attack
Range** card each time — there is no `lab-prep <N>` here because there's nothing sequential to catch up
on.

**Lab 1 has two flags, and that trips people up.** The first flag is a captured service token (land the
spoof, poll `/captured`); the second needs that token **replayed** at `/admin` as a Bearer token. Tell the
room up front there are two `dojo-flag submit` calls for this one target, not one — the lab text makes
this explicit but it's easy to stop after the first flag and think you're done.

**Don't volunteer hints from the stage.** The slides deliberately never name a specific bug, and each
lab already has two rounds of hints built in, closer to an answer each time. If someone's stuck, ask
*where they've looked*, not *what the bug is* — and remind them the exploit guide exists before telling
them what's in it.

**A third lab is planned, not built.** Target 10 `runner-escape` belongs on this session's ladder per the
plan but has no image yet and needs `runner-pool` in `MODULES=` plus a dedicated start hook. Don't
promise it to a room until it exists; mention it only as "a future session" if asked.

## Before the session

**A day ahead**

1. `./run.sh setup` if there is no `.env`. Set `PUBLIC_BASE_URL`, `GATEWAY_TOKEN`,
   `STUDENT_COUNT`.
2. Generate a real `CTF_CONTROL_TOKEN` for `workshop.env` (the committed value is a dev placeholder) —
   it gates the Attack Range's start/stop/reset API.
3. `./run.sh ctf-trust-chain`. First build takes a few minutes longer than most packs: `ctf-host` builds
   its `ctf-host-ctf4` stage (the 2-target image, not the full 14-target catalog — CTF-D26) on top of
   `docker:dind`. Open `/admin` and wait for **Forgejo**, **Terminals**, **Slides** and **Attack Range**
   to go green.
4. **Size the machine:** `./run.sh capacity ctf-trust-chain --students 30` if you expect a full room — the
   range adds `ctf-host`/`ctf-controller` on top of the terminals; see `module.env`'s
   `CTF_HOST_MEM_LIMIT`/`CTF_CONTROLLER_MEM_LIMIT`.
5. **Rehearse as a student** in a private window: run the lab's own `nmap -sV -p- <ip>` command at least
   once and confirm the **recon-versions**/**recon-full-sweep** achievements fire (toast or the student's
   achievements page), then start each of the two targets from the Attack Range card, solve each with
   the lab's hints alone (or the exploit guide, to confirm it's accurate) — for `dns-resolver-cve`, submit
   **both** flags — and confirm each milestone lands on the leaderboard. **The Attack Range card itself
   still shows no solved state** (stopped/queued/starting/live only) -- the achievements leaderboard is
   where "solved" actually shows up in this pack. The recon milestones and the `dns-resolver-cve`
   two-flag chain in particular are the pieces not yet live-verified for this pack specifically — this
   rehearsal is where that gets checked. Then `./run.sh stop` and start clean.
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
- **Decoy ports are decoys.** Both targets publish a decoy SSH listener on 2222 alongside the real app —
  that dead end is intentional, not a bug report waiting to happen.
- **`dns-resolver-cve`'s agent cycles on its own.** Students sometimes think they need to trigger the
  lookup themselves; the agent runs on a timer, so arming `/spoof` and then polling `/captured` for up to
  a cycle or two is the normal flow, not a sign something's broken.
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
| `dns-resolver-cve`'s `/spoof` never lands | The predicted TXID may be off by more than one cycle (the agent moved on); re-`GET /observations` for the latest TXID and re-arm `/spoof` with that + 1 |
| `nmap` on the slot IP times out entirely | The per-uid firewall rule may not have landed yet (a known race on a very slow first boot, `50-ctf-range.sh` retries up to 180s) — wait and retry before assuming the target is broken |
| A target never goes healthy after Start | `ctf-host`'s own healthcheck retry budget; give it a minute before treating it as stuck, especially right after `./run.sh ctf-trust-chain` first starts |
| Student reused a classmate's target | Shouldn't be reachable at all — the firewall only permits a student's own slot IP; report this as a real bug, not a lab mistake |
| One student's terminal wedged | Roster → **Release**; **Reset** on the Attack Range tab returns their current target to its clean image (their flag, if already submitted, still verifies the same way after) |

## After the session

- `./run.sh stop` wipes everything — containers, volumes, every student's slot, every account.
- Note anything that confused the room or a wrong timing in `ROADMAP.md` and fix the lab.
