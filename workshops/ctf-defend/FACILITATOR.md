# CTF-5: Defend — facilitator guide

For the person running the session. The technical reference is [`README.md`](README.md); the deck's
speaker notes carry the talking points. This guide is the practical part: before, during, after, and
what to do when something breaks.

**Honest status:** the range, the three defend targets, the checker and the defend pipeline, the
attacker-bot swarm and SOC feed are built (the three-target conversion has not had a live class run yet) (see `docs/CTF-WORKSHOP-PLAN.md`, `RELEASES.md`). This
pack's own content (this guide, the deck, the cheat sheet) was finished alongside a content audit of
the whole CTF series and has not yet had its own live rehearsal in a room. Do the rehearsal below before
a class.

## The session at a glance (about 2 hours)

| Block | Minutes | What |
| ----- | ------- | ---- |
| Talk | ~15 | Three apps on fire, the loop, `dojo-check`, the PR gate and `INCIDENT.md` |
| Lab 1 | ~90 | Incident triage: detect, triage, contain, fix, verify, on all three targets |
| Recap | ~15 | Order of work vs the room's; the per-target debriefs; the capstone for early finishers |

**One lab, three targets, always on.** There is no Attack Range card and no start/stop/reset: `customer-portal`
(high), `policy-bypass` (medium) and `leaky-config` (low) run on every student's slot from the moment the stack
comes up. Each student has **three own Forgejo repos** (`<student>/<target>`, provisioned by
`compose/terminal/start.d/90-ctf-defend.sh`), and what they push to `main` is what runs on that slot. The attack
order differs per student (six permutations dealt from a seed; set `CTF_SCHEDULE_SEED` to reproduce a run) and each
target starts on a stagger (`CTF_TARGET_STAGGER`), so breaches pile up. Class size is at most 20.

**The loop is the lesson**: detect, triage, contain, fix, verify. `dojo-check` runs the attack against a live slot
and one legitimate request, so a student sees `exploitable`, `contained`, `broke-normal-use` or `unreachable`
per target. The PR gate runs the same checks and also needs an `INCIDENT.md` with `What was hit`, `How I
know` and `Impact` (presence only; read a few in the recap, the content is the triage).

**The clock is a facilitator action, not automatic.** The attacker-bot swarm (SOC' green → yellow
→ red countdown) sits idle until you press **Start Attack Swarm** on the SOC `/admin` tab. Nothing
attacks anyone's slot before that. Default timings are ~8 minutes of recon (green) then ~10 minutes
ramping to a real exploit attempt (red) — `CTF_SOC_DWELL_SECONDS`/`CTF_SOC_RAMP_SECONDS` in
`modules/ctf-range/module.env` if you want more runway for a first-time room. (`./dojo ctf-defend --test`
runs the whole timeline at a tenth: 48s of recon, 60s of ramp; `CTF_TIME_SCALE=1` keeps the real clock.)

**The SOC is one screen.** The **SOC (whole room)** tab shows the cyber map (world view plus a Canada inset),
the live alert feed and the incident summary together, sized for the projector. Students do not get this page: their **SIEM** card shows only their own breach banner (red the moment their target is breached, green "Contained" with the time to patch once fixed), their own request log (repeated identical breach lines collapse to one line with an `xN` count) and their own incident summary. No map, no other students' events. The facilitator bar
above them has Start/Re-arm, Inject / Hint probe, and a student picker: choosing a student fills the
incident summary and lets you correct that student's map point (a city name or `lat,lon,Label`).
Students' points come from a city-level lookup of where they connect from (optional DB-IP database,
`modules/achievements/tools/fetch_geoip.sh`; no addresses are stored or shown) or, on a LAN or WSL,
sit around `CTF_HOME_REGION` (default Toronto).

**Don't name the bugs from the stage.** The deck describes the apps and the pipeline, never a flaw. Students find
each one in its own signal and source. If someone is stuck, point at `dojo-check` and the lab's hints for that
target, in order; never at a line number.

## Before the session

**A day ahead**

1. `./dojo setup` if there is no `.env`. Set `PUBLIC_BASE_URL`, `GATEWAY_TOKEN`, `STUDENT_COUNT`,
   `FORGEJO_ADMIN_USER`/`FORGEJO_ADMIN_PASSWORD` (required — `90-ctf-defend.sh` provisions each
   student's repo through Forgejo's admin API and skips a student silently if these are missing).
2. `CTF_BUILD_TOKEN`/`CTF_CONTROL_TOKEN` in `workshop.env` are already derived from `GATEWAY_TOKEN` —
   nothing to generate by hand here, unlike CTF-1's pack.
3. `./dojo ctf-defend`. Open `/admin` and wait for **Forgejo**, **Terminals**, **Slides** and
   **SOC** to go green. Confirm the `attacker-bot` container is up (idle) — `podman ps`.
4. **Size the machine:** `./dojo capacity ctf-defend --students 30` if you expect a full room — the
   range's `ctf-host`/`ctf-controller` plus the `attacker-bot` swarm sit alongside the terminals.
5. **Rehearse as a student** in a private window: clone all three repos, run `dojo-check` (all
   `exploitable`), fix each, PR it with and without `INCIDENT.md`, watch the gate block a bad fix and pass a
   good one, merge, confirm `dojo-check` says `contained`, and check the per-target milestones land. Then try
   the capstone (`customer-portal`'s `/login` has the same bug). `./dojo stop` and start clean afterward.
   Run `content/sync-sample-repos.sh` first if a target's source changed.
6. Skim the deck with speaker notes on.

**On the day, 15 minutes before**

- Start the stack; confirm `/` (landing cards, including **SIEM**), `/slides` and `/admin` all
  green.
- Keep `/admin`'s **SOC** tab on a second screen — it's where you press **Start Attack Swarm**
  and where you watch the whole room's status at a glance.

## During the session

**What you can see.** `/admin` tabs: Roster, VS Code, Terminal, Forgejo, Slides, **SOC**, **Wall of Shame** (when on).

- **Press Start Attack Swarm once the room has cloned their repos and read the briefing** — not before.
  Starting it too early just burns the green/recon window while people are still reading the deck.
- **`dojo-check` is the fastest way to confirm a theory** (lightly rate limited). It says whether, never how.
- **Triage is visible.** On the SOC tab, watch who works the high-severity target first and who is
  still on the quiet one while a breach sits unattended.
- **The PR gate is the real judge.** If a "fix" merges without the Actions check passing, something's
  wrong with the pipeline, not the lesson — report it, don't wave it through.
- **Lagging student:** there's no `lab-prep` to fast-forward with — one lab, no sequence. If someone's
  stuck well past the second hint for a target, that's the point to intervene directly.
- **Early finisher:** point them at the capstone achievement (`achievements/capstone.json`) — the same
  bug lives in `customer-portal`'s `/login` too, and the gate only re-tests `/search`.

**Updating content mid-session.** Slides and labs are bind-mounted; edits to `content/slides/` show
immediately, an edited lab file reaches `~/lab` on the next terminal restart, never overwriting a
student's own work.

## The wall of shame (on by default)

A projector-friendly list of breached students: **LIVE** while the swarm's dumps keep landing, **DISCONNECTED
(contained)** once a patched redeploy makes them fail, then it ages off (`CTF_WALL_AGE_OFF_SECONDS`, 5 min).
It is the **Wall of Shame** `/admin` tab and a widget on the landing page. Set `CTF_WALL_OF_SHAME=off` in
`workshop.env` (or `dojo.local.toml` / `--env`) for a quieter or smaller room: only the display goes; the status
light, MTTP and incident summary keep working. Data is synthetic and derived from lab handles only.

## The SIEM request log (`CTF_SIEM_DETAIL`, default full)

The SOC page's feed is a SIEM-style **request log**: one line per event with the time, attacker country
code, method, path, status, size and a detection tag (`scanner`, `SQL meta-characters in parameter q`,
`sensitive file requested`, `bulk data egress`, ...). Click a line (or Tab to it and press Enter) for its full
record as JSON. Three traffic classes mix in: background internet scanning, probing of the app, and the real
exploit. The tag names the class of attack, never the fix.

Spoiler control is enforced by the server, per student. While a student's own target is unbreached they see
only method, path, status and tag; once it is breached, their lines also show the payload, response size,
rows returned and user-agent (including earlier lines), which is the material for the debrief: "what did the
exploit actually look like in the logs, and which earlier lines were the warning?". You always see the full
record on your room view. Set `CTF_SIEM_DETAIL` in `.env` or the shell: `paths` never unlocks payload and
size (a harder class), `off` restores the plain alert table. `off` restores the plain alert table. Each target shows a different signal (request log, audit log, file-access
and auth log), grouped by target with its severity; benign traffic (about 15%) is mixed in. The Attack Range
/admin tab does not appear in this pack; the Range Controller status check covers the controller.

**Debrief notes.** `policy-bypass`: the fix trusts the platform-set `X-Caller-Role`, never the body tag, and a
header is only as trustworthy as the proxy that sets it. `leaky-config`: the credential already exposed is burned;
rotation is operational. `customer-portal`: a fixed query does not undo what was dumped.

## When something breaks

| Symptom | Likely cause and fix |
| ------- | -------------------- |
| A student is missing one of the three repos in Forgejo | `90-ctf-defend.sh` skips silently if `FORGEJO_ADMIN_USER`/`PASSWORD` weren't set before start, or if Forgejo wasn't up yet when the terminal booted; check the terminal container's start-up log for `[ctf-defend]` lines |
| PR gate never runs / stays pending | Confirm the repo's Actions secrets (`CTF_BUILD_TOKEN`, `CTF_CONTROL_TOKEN`) exist — the same provisioning hook sets them; a student who force-pushed over the initial seed may have lost them |
| Merge doesn't redeploy the slot | `defend-main.yml` calls `ctf-controller`'s `/redeploy`; check `/admin`'s SOC tab and `ctf-controller` logs for a rejected control token |
| SOC shows nothing after pressing Start | Confirm `attacker-bot` is actually running (`podman ps`) — it's idle-but-present before the press, not absent |
| `dojo-check` says `unreachable` | The checker could not reach that slot: check `ctf-checker` and `ctf-controller` are up and the slot exists (`/slots`) |
| One student's terminal wedged | Roster → **Release**; their Forgejo repo and running slot are untouched by a terminal release |

## After the session

- `./dojo stop` wipes everything — containers, volumes, every student's slot and repo, every account.
- Note anything that confused the room or a wrong timing in `ROADMAP.md` and fix the lab.
