# dns-as-code — facilitator guide

For the person running the session. The technical reference is [`README.md`](README.md); the deck's
speaker notes carry the talking points. This guide is the practical part: before, during, after, and
what to do when something breaks.

**Honest status:** run end to end with the demo bots, not yet with a room. The per-lab times below are the
labs' own estimates (`content/lab/README.md`). Do the rehearsal. This pack adds the most moving parts of
the early series — PowerDNS, a CI runner pool and the DNS gate — so give the first build time.

## The session at a glance (about 2 hours)

| Block | Minutes | What |
| ----- | ------- | ---- |
| Talk | ~20 | DNS as declarative config, preview vs apply, drift, the change process. *A guess until a dry run.* |
| **Part 1** (your own zone), Labs 1-2 | ~30 | 20 + 10. `<user>.dojo.test`, pushed by the student themselves |
| **Part 2** (the shared zone), Labs 3-6 | ~70 | The company way: branch → PR → CI preview → review → CI apply, then `dnsctl.py`, history and rollback |
| Recap | ~5 | What surprised them (usual: only CI may touch `dojo.test`; the preview comment) |

**Prerequisite:** git-fundamentals — this is the same clone/branch/commit/push/PR muscle memory applied to
`dnsconfig.js`. **Every lab is mandatory, in order.** The two halves matter: Part 1 is a zone the student
owns and pushes directly; Part 2 is the shared `dojo.test`, which **only CI** can change (a `dnscontrol
push` from a terminal is refused, and nobody can push to `main`).

**Who may change what** (worth saying out loud before Part 2): each student's own key changes only names
under `<user>.dojo.test`; the shared `dojo.test` changes only from the DNS Apply CI job, after a reviewed
merge. This is enforced by the `dns-gate` module, not by trust.

**Sensei** opens one practice PR (`dns-bot/add-status`) into the class repo so everyone has something to
review in Lab 3; it never approves or merges it. In approve mode it approves a PR that adds or removes one
of the author's **own** records — the demo bots' at once, a student's once they have reviewed someone
else's. The `/admin` Sensei tab lists these.

## Before the session

**A day ahead**

1. `./dojo setup` if there is no `.env`. Set `PUBLIC_BASE_URL`, `GATEWAY_TOKEN`,
   `STUDENT_COUNT`.
2. **No password to announce** — each terminal is signed in with the student's own token. **Password** on
   the Roster tile shows it if ever needed.
3. `./dojo dns-as-code`. The first build takes several minutes (the terminal image carries `dnscontrol`
   + `dig`). Open `/admin` and wait for **Forgejo**, **Terminals**, **Slides**, the **DNS Zones** view and
   the **runner pool** to go green. Terminals (account creation) is the slowest; yellow there is normal.
4. **Size the machine:** `./dojo capacity dns-as-code --students 30` — it counts PowerDNS, the runner
   pool and the gate on top of the terminals.
5. **Rehearse as a student** in a private window: Part 1 (push to your own zone, see it on `/dns`), then
   Lab 3 end to end — open a PR, watch **DNS Preview** go green, get it reviewed/merged, watch **DNS
   Apply** go green, and `dig` the record. Then `./dojo stop` and start clean.
6. Skim the deck with speaker notes on.

**On the day, 15 minutes before**

- Start the stack; confirm `/` (a **DNS Zones** card), `/slides`, `/dns` (the read-only zones page) and
  `/admin` (strip all green, including the runner pool).
- Keep `/admin` on a second screen; the **DNS Zones** tab shows what PowerDNS actually serves.

## During the session

**What you can see.** `/admin` tabs: Roster, VS Code, Terminal, Forgejo, Slides, **DNS Zones** and
**Sensei**. CI jobs (DNS Preview on a PR, DNS Apply on merge) run on the runner pool — the Runners control
is in `/admin`.

- **Say it first:** CI takes a little while; a PR is mergeable only once **DNS Preview** is green, and the
  record only appears after **DNS Apply** is green on `main`. Students often `dig` too early.
- **Lagging student:** `lab-prep <N>` brings them to the start of lab N; safe to re-run.
- Lab 3 needs a review by someone else before merge (`DNS_REQUIRED_APPROVALS=1`). If the room is small or
  uneven, the `dns-bot` PR gives everyone one PR to review; you can also approve as the facilitator.

**Updating content mid-session.** Slides and labs are bind-mounted; edits to `content/slides/` show
immediately, a new lab file reaches `~/lab` on the next terminal restart, and an edited file is never
overwritten.

## When something breaks

| Symptom | Likely cause and fix |
| ------- | -------------------- |
| `dnscontrol push` to `dojo.test` is refused | Correct: the shared zone is CI-only. Only `<user>.dojo.test` is pushable from a terminal |
| **DNS Preview** / **DNS Apply** job red | Open the job log (Forgejo Actions or `/admin`). A real syntax error in `dnsconfig.js` is the lesson; a runner-pool stall shows in `./dojo logs runner-pool \| tail -40` |
| `dig` shows nothing after a merge | DNS Apply may still be running or red; check Actions. Then confirm on the `/dns` page before `dig` |
| PR won't merge | Preview must be green and it needs one review. The `dns-bot` PR is there for the review step |
| `git push` asks for a password / goes to the team repo | Token missing (`ls -l ~/.git-credentials`) or wrong remote (`git remote -v`). **Password** on the Roster tile as a stop-gap |
| One student's terminal wedged | Roster → **Release**; **Reset** returns them to stack-start and re-seeds their zone records, keeping the seat (a reset leaves shared-zone records they merged alone, by design) |

## After the session

- `./dojo stop` wipes everything — containers, volumes, PowerDNS data, every repo and account.
- Note anything that confused the room or a wrong timing in `ROADMAP.md` (Manual checks) and fix the lab.
