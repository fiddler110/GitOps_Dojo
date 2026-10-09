# Facilitator guide

For whoever runs a class. This page is the platform-level run-of-show; every workshop also has its own
`workshops/<name>/FACILITATOR.md` with the session timing, what to say, per-lab traps and workshop-specific
troubleshooting. Read the platform pages here first, then the pack's.

## 1. What you control

| You can | How |
|---|---|
| Start and stop a class | `./dojo <workshop>`, `./dojo stop` |
| See every student live | `/admin` → **Roster**: a tile per held slot with a read-only view of their terminal |
| Do anything a student can | `/admin` tabs: **VS Code**, **Terminal**, **Forgejo**, **Slides**, plus the tabs the workshop adds. You never take a student slot |
| Help one student | Watch their tile, open the shared Forgejo, or **Release**/**Reset** them |
| Change content live | Edit `slides/` and `lab/` under the workshop's `content/`; no rebuild |
| Rehearse alone | `--test` demo bots |

**The facilitator can reach every part of an active workshop.** Whatever a student card shows, the matching `/admin`
tab exists (the start prints a warning if a pack forgets one). Your terminal runs as `FACILITATOR_USERNAME` with
`sudo` and sees every process.

## 2. Before the class

### A week or a day ahead

1. **First-time machine?** `./setup.sh` (or `.\setup.ps1` on Windows) installs podman and prerequisites after asking;
   `./dojo doctor` checks the machine.
2. **Create real credentials:** `./dojo setup`. It generates unique passwords and offers to size the machine. For a
   throwaway rehearsal, `./dojo setup --default` uses easy fixed ones (loopback only).
3. **Choose where it runs and the URL**: see [Configuration → Deployment scenarios](configuration.md#deployment-scenarios).
   A cloud VM needs its DNS label set before the first start so Caddy can get a certificate.
4. **Size it:** `./dojo capacity <workshop> --students N` on the target machine. Raise `student_count` in
   `dojo.toml` to at least the class size.
5. **Build ahead:** `./dojo <workshop> --build-only` (or just start it). First builds take several minutes; CTF packs
   build a Docker-in-Docker host and take longer.
6. **Rehearse as a student.** Start it, open the address in a **private window** to get a real student slot (your
   facilitator session never shows what students see), do Lab 1, check `/admin`, then `./dojo stop` and start clean.
   Run `./dojo <workshop> --test --fast` to confirm the labs still work end to end after any change.
7. Read the pack's `FACILITATOR.md` and skim the deck with speaker notes on.
8. Pick a class sign-in. `./dojo setup --rotate-class` makes a fresh class password; restart to apply it.

### On the day, 15 minutes before

1. `./dojo <workshop>` and wait for the table to settle.
2. Open `/admin` and check the **status strip** (bottom of the sidebar, or a row on a narrow screen): every chip
   green (**Ready**). Yellow (**Starting**) is normal for the first minute, especially Terminals, which creates every
   account.
3. Open the landing page `/` and `/slides` once as yourself.
4. Put the class address and sign-in on the first slide. Put `/admin` on a second screen.
5. Optional: `./dojo <workshop> --pass CODE` to put an access-code page in front of the site while people arrive.

## 3. During the class

### The `/admin` workspace

| Tab | What it gives you |
|---|---|
| **Roster** | Live tiles: account, name, IP, status dot (green = a process for that account is really running), a read-only terminal view, and the **Release**, **Reset** and **Password** buttons |
| **VS Code**, **Terminal** | Your own session (lazy-loaded, kept alive across tab switches) |
| **Forgejo** | Signed in as the machine admin; review and merge students' pull requests |
| **Slides** | The deck and lab text, with your login |
| Workshop tabs | Whatever the pack and its modules add (see below) |

Plus a **service status strip**: one chip per service (Forgejo, terminals, slides, and anything a manifest declares).
Hover for the reason. Students never see service health.

### Workshop-specific tabs you may see

| Tab | From | Use |
|---|---|---|
| **Sensei** | sensei | Every roster/practice PR with status and why, **Merge anyway**, **Comment**, raised hands with a reply box, and the stuck radar (`failing`, `stalled`, `quiet`) |
| **Runners** | runner-pool | A light per CI runner (green ready, yellow running with the repo, red failed/offline/stuck), Auto/Manual, − / + |
| **Dojo Cloud** | dojo-cloud | The cloud portal, and the class-progress board |
| **DNS Zones**, **DNS Admin** | dns-ui | Live records; PowerDNS-Admin for making a "dashboard edit" that the next `dnscontrol push` reverts |
| **Vault**, **Audit**, **Apps** | openbao, vault-fundamentals | The vault UI signed in as you; every vault request filterable by student/op/path; each deploy slot and its log |
| **Site Inspector** | cert-autorenewal | The students' certificate-inspecting browser |
| **Workshop Library** | dojo-introduction | Every workshop's slides and labs |
| **Achievements** | achievements | The class's scores and unlocks, and the log of challenge checks |
| **Attack Range** | ctf-range | Per-student target state; in CTF-5 the room-wide SOC feed and its green/yellow/red countdown |

### Helping people

| Situation | Do |
|---|---|
| Someone is lost | Click their roster tile: you see their screen. Ask *where they looked*, not what the bug is |
| A terminal is wedged | **Release**: kills their VS Code/terminal and frees the slot; their next visit reassigns |
| A student wrecked their repo or state | **Reset**: back to stack-start, seat kept (see below) |
| They forgot something about git auth | `git push` asking for a password means the token is missing; stop-gap: **Password** on their tile |
| Late joiner | `lab-prep N` in their terminal (where the pack provides it) |
| Class is full but seats are held by wanderers | **Release unused** above the grid frees slots older than 2 minutes with no running process |
| Many people hitting "try again in N seconds" | The slot-assignment rate limit (10 at once, then 20/min) is smoothing a rush; a class of 30 is in within about a minute |

### Release versus Reset

| | **Release** | **Reset** |
|---|---|---|
| Stops VS Code and terminal | yes | yes |
| Keeps the student's home, repo and cloud state | **yes** | **no**: returns to stack-start |
| Frees the seat | yes (next visit reassigns) | no: keeps the seat |
| Confirmation | one click | type the account id |

Reset tears down, in order: their processes; each module's state through its reset hook (cloud subscription, DNS
zones and names, busy CI runners, vault namespace and app slots, challenge progress); their Forgejo open PRs and
branches, then the account with its repos and forks, recreated with the same password; and the terminal (home,
crontab, tmp, then re-provision with a fresh token). Optional steps (for example clearing achievements and score) appear
as checkboxes, off by default. A failed step stops the reset and shows its error; **Retry** reruns everything (each
step is safe to repeat). Shared history and comments in the org repo stay, as do DNS records added to a CI-managed
zone through the shared repo.

### Updating content mid-session

Slides and labs are bind-mounted: slide edits show immediately. A **new** lab file reaches homes on the next terminal
restart (`./dojo restart web-terminal`); files students already edited are never overwritten. Lab copies for the
browser reader: after editing a lab on a running stack, copy it to `content/slides/lab/<name>.md.txt` too (the
`*.md.txt` files are generated at start and git-ignored; do not edit them directly in the repo).

Rebuilding is only needed when an image's Dockerfile, the Caddyfile, `entrypoint.sh` or `.env` changes. Re-running
`./dojo <workshop>` detects that and rebuilds only what changed. After changing an image, run `./dojo stop` first.

### Achievements, if switched on

Students get toasts, a leaderboard and bonus challenges. You get an **Achievements** tab. Switch them off for a
session that should not score anyone with `general.achievements = false` in `dojo.local.toml`. Challenge authors:
a challenge is a goal with no steps, so do not coach it from the stage.

### Demo bots

`./dojo <workshop> --test [N] [--fast]` adds simulated students. Use them to rehearse solo, demo the dashboard, or
load-test a machine before a class. Without `--fast` the bots type at human speed with three personas: the expert
does every lab each round; the intermediate gets through the middle labs; the novice stays in the early ones and makes
frequent mistakes. Releasing a bot is safe: its supervisor restarts it and it resumes where it was. Stop bots by
setting `bots.count = 0` and restarting without `--test`. **Never use plain `--test` for a check**: it is paced for
demos. See [Authoring → bots](authoring.md#7-demo-bots-and-tests) for pack-specific steps.

## 4. After the class

1. Copy out anything worth keeping (pull request text, the roster file, scores) by hand. There is **no archive step**.
2. `./dojo stop`. It deletes every container and **every volume**: homes, Forgejo, accounts, CA keys, DNS zones.
   `./dojo stop --dry-run` shows exactly what first. To clean up automatically: `echo "cd $(pwd) && ./dojo stop" | at now + 4 hours`.
3. On a VM, deallocate or delete the VM: the cleanest end of all.
4. Note what confused people (a lab step, a timing, a failure not in the table) in `ROADMAP.md` and fix the lab.

Starting a **different** workshop over a running one is refused. Run `./dojo stop` first; otherwise the old one's
extra services and volumes stay behind.

## 5. Running several classes back to back

- Same workshop, new class: `./dojo restart --clean` (stop then fresh start), or just `stop` and start.
- Same running stack, new people, keep homes: delete the slot table and restart the allocator (see
  [Operations](operations.md#between-back-to-back-sessions)).
- A shared machine: check what is running first with `./dojo status`. One stack at a time per machine (the run lock).

## 6. Quick reference card

```sh
./dojo doctor <workshop>          # will it start here?
./dojo capacity <workshop> --students 30
./dojo <workshop> --dry-run       # what would build/start; validates manifests
./dojo <workshop>                 # go
./dojo status                     # health and who is signed in
./dojo logs web-terminal -n 80    # when a student's terminal misbehaves
./dojo restart web-terminal       # recreate one service, keep volumes
./dojo stop                       # end of class: wipes everything
```

Class sign-in: `TTYD_USERNAME` / `TTYD_PASSWORD` (`./dojo config <workshop> TTYD_USERNAME`).
Facilitator sign-in: `FACILITATOR_USERNAME` / `FACILITATOR_PASSWORD`, which opens `/admin`.
