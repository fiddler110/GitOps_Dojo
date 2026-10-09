# CTF-5: Defend — facilitator guide

For the person running the session. The technical reference is [`README.md`](README.md); the deck's
speaker notes carry the talking points. This guide is the practical part: before, during, after, and
what to do when something breaks.

**Honest status:** the range, target 14 (`customer-portal`), its SAST stage and defend pipeline, the
attacker-bot swarm and SOC feed are all built (see `docs/CTF-WORKSHOP-PLAN.md`, `RELEASES.md`). This
pack's own content (this guide, the deck, the cheat sheet) was finished alongside a content audit of
the whole CTF series and has not yet had its own live rehearsal in a room. Do the rehearsal below before
a class.

## The session at a glance (about 2 hours)

| Block | Minutes | What |
| ----- | ------- | ---- |
| Talk | ~15 | The incident framing, the clone-and-fix flow, the exploit check, the PR gate |
| Lab 1 | ~90 | `customer-portal` — find the SQL injection, branch, PR, merge, watch it redeploy |
| Recap | ~15 | What the SOC Alerts clock showed; point at the capstone for anyone who finishes early |

**One lab, one target, always on.** Unlike CTF-1 through CTF-4, there is no Attack Range card and no
start/stop/reset — `customer-portal` is already running on every student's slot from the moment the
stack comes up (CTF-D20/D25: the "always-on, one app-code target" model, not the student-controlled
ladder). Each student has their **own Forgejo repo** (`<student>/customer-portal`, provisioned by
`compose/terminal/start.d/90-ctf-defend.sh`), not a shared seed — what they push to `main` is what's
actually running on their slot.

**The clock is a facilitator action, not automatic.** The attacker-bot swarm (SOC Alerts' green → yellow
→ red countdown) sits idle until you press **Start Attack Swarm** on the SOC Alerts `/admin` tab. Nothing
attacks anyone's slot before that. Default timings are ~8 minutes of recon (green) then ~10 minutes
ramping to a real exploit attempt (red) — `CTF_SOC_DWELL_SECONDS`/`CTF_SOC_RAMP_SECONDS` in
`modules/ctf-range/module.env` if you want more runway for a first-time room.

**Don't name the bug from the stage.** The deck describes the app and the pipeline, never the SQL
injection itself — students find it by using the app and reading `app.py`, the same file they already
have in their cloned repo. If someone's stuck, point them at the exploit check
(`python3 exploit/dump.py --url ...`, the same one the PR gate runs) and at re-reading the source, not at
the line number.

## Before the session

**A day ahead**

1. `./dojo setup` if there is no `.env`. Set `PUBLIC_BASE_URL`, `GATEWAY_TOKEN`, `STUDENT_COUNT`,
   `FORGEJO_ADMIN_USER`/`FORGEJO_ADMIN_PASSWORD` (required — `90-ctf-defend.sh` provisions each
   student's repo through Forgejo's admin API and skips a student silently if these are missing).
2. `CTF_BUILD_TOKEN`/`CTF_CONTROL_TOKEN` in `workshop.env` are already derived from `GATEWAY_TOKEN` —
   nothing to generate by hand here, unlike CTF-1's pack.
3. `./dojo ctf-defend`. Open `/admin` and wait for **Forgejo**, **Terminals**, **Slides** and
   **SOC Alerts** to go green. Confirm the `attacker-bot` container is up (idle) — `podman ps`.
4. **Size the machine:** `./dojo capacity ctf-defend --students 30` if you expect a full room — the
   range's `ctf-host`/`ctf-controller` plus the `attacker-bot` swarm sit alongside the terminals.
5. **Rehearse as a student** in a private window: clone your own `customer-portal`, confirm
   `python3 exploit/dump.py --url <your-slot>` exits `0`, fix `app.py`'s `/search` query, PR it, watch
   the PR gate's Actions run block a bad fix and pass a good one, merge, confirm the exploit check now
   exits `1` against the redeployed slot, and check the `m-opened`/`m-shipped`/`m-contained`
   achievements land. Then try the capstone (`app.py`'s `/login` has the same bug) to confirm the
   second fix verifies too. `./dojo stop` and start clean afterward.
6. Skim the deck with speaker notes on.

**On the day, 15 minutes before**

- Start the stack; confirm `/` (landing cards, including **SOC Alerts**), `/slides` and `/admin` all
  green.
- Keep `/admin`'s **SOC Alerts** tab on a second screen — it's where you press **Start Attack Swarm**
  and where you watch the whole room's status at a glance.

## During the session

**What you can see.** `/admin` tabs: Roster, VS Code, Terminal, Forgejo, Slides, **SOC Alerts**.

- **Press Start Attack Swarm once the room has cloned their repos and read the briefing** — not before.
  Starting it too early just burns the green/recon window while people are still reading the deck.
- **The exploit check is the fastest way to confirm a theory.** A student can run it as many times as
  they like against their own slot; nudge anyone guessing blind back toward it.
- **The PR gate is the real judge.** If a "fix" merges without the Actions check passing, something's
  wrong with the pipeline, not the lesson — report it, don't wave it through.
- **Lagging student:** there's no `lab-prep` to fast-forward with — one lab, no sequence. If someone's
  stuck well past the hint in `app.py`'s commented-out safe example, that's the point to intervene
  directly.
- **Early finisher:** point them at the capstone achievement (`achievements/capstone.json`) — the same
  bug lives in `/login` too, and the PR gate only ever re-tests `/search`.

**Updating content mid-session.** Slides and labs are bind-mounted; edits to `content/slides/` show
immediately, an edited lab file reaches `~/lab` on the next terminal restart, never overwriting a
student's own work.

## When something breaks

| Symptom | Likely cause and fix |
| ------- | -------------------- |
| A student has no `customer-portal` repo in Forgejo | `90-ctf-defend.sh` skips silently if `FORGEJO_ADMIN_USER`/`PASSWORD` weren't set before start, or if Forgejo wasn't up yet when the terminal booted; check the terminal container's start-up log for `[ctf-defend]` lines |
| PR gate never runs / stays pending | Confirm the repo's Actions secrets (`CTF_BUILD_TOKEN`, `CTF_CONTROL_TOKEN`) exist — the same provisioning hook sets them; a student who force-pushed over the initial seed may have lost them |
| Merge doesn't redeploy the slot | `defend-main.yml` calls `ctf-controller`'s `/redeploy`; check `/admin`'s SOC Alerts tab and `ctf-controller` logs for a rejected control token |
| SOC Alerts shows nothing after pressing Start | Confirm `attacker-bot` is actually running (`podman ps`) — it's idle-but-present before the press, not absent |
| Exploit check errors instead of exiting 0/1 | Exit code 2 means it couldn't reach the target at all — check the slot address on the landing card, not the app |
| One student's terminal wedged | Roster → **Release**; their Forgejo repo and running slot are untouched by a terminal release |

## After the session

- `./dojo stop` wipes everything — containers, volumes, every student's slot and repo, every account.
- Note anything that confused the room or a wrong timing in `ROADMAP.md` and fix the lab.
