# cert-autorenewal — facilitator guide

For the person running the session. The technical reference is [`README.md`](README.md); the deck's
speaker notes carry the talking points. This guide is the practical part: before, during, after, and
what to do when something breaks.

**Honest status:** run end to end with the demo bots and the student-reset live pass, not yet with a room.
The per-lab times below are the labs' own estimates (`content/lab/README.md`). Do the rehearsal. The
certificates students issue are real X.509 certs from a real ACME CA (`step-ca`), actually serving HTTPS
on a shared `demo-app`.

## The session at a glance (about 1¾ hours)

| Block | Minutes | What |
| ----- | ------- | ---- |
| Talk | ~20 | Why certs expire, ACME, http-01 vs dns-01, renewal as automation not a reminder. *A guess until a dry run.* |
| Lab 1 | ~10 | Trusting the CA: bootstrap, inspect the root cert |
| Lab 2 | ~25 | Issue and install a certificate with `certbot` (the core lab) |
| Lab 3 | ~15 | The same task with `acme.sh` — comparing ACME clients |
| Lab 4 | ~15 | Automating renewal, and watching it actually fire |
| Lab 5 | ~15 | The dns-01 challenge, against real DNS records the student writes |
| Recap | ~5 | What surprised them (usual: HSTS, the renewal cron, dns-01's TXT dance) |

**Builds lightly on dns-as-code** (Lab 5's dns-01 drives the same PowerDNS API `dnscontrol` wraps there),
but otherwise stands alone. **Every lab is mandatory, in order.** In a shorter slot, Labs 1-2 are the core
(trust the CA, issue and install); Lab 5 (dns-01) is the one to drop first.

**The shared location.** Unlike the other packs, a student's work also lives in a **shared** path,
`/srv/webroot/<user>/`, because that is what `demo-app` serves. Each student's subdirectory is theirs
alone; the DNS gate's per-student key scopes names under `<user>.certs.dojo.test` the same way.

**Site Inspector** (card and `/admin` tab, `/inspect`) visits a site like a browser and shows the redirect
chain, the certificate and HSTS step by step. The facilitator's tab can inspect any student's name; a
student's own card shows theirs. After Lab 2 a student's visit should show `http://` → 301 → `https://`
with a verified certificate, and a second visit upgraded by HSTS.

## Before the session

**A day ahead**

1. `./run.sh setup` if there is no `.env`. Set `PUBLIC_BASE_URL`, `GATEWAY_TOKEN`,
   `STUDENT_COUNT`.
2. **No password to announce** — each terminal is signed in with the student's own token. **Password** on
   the Roster tile shows it if needed.
3. `./run.sh cert-autorenewal`. The first build takes several minutes (the terminal image carries `step`,
   `certbot` and `acme.sh`; `step-ca`, `demo-app` and PowerDNS start alongside). Open `/admin` and wait for
   **Forgejo**, **Terminals**, **Slides**, **Site Inspector**, the **DNS Zones** view and the gate to go
   green. Terminals (account creation) is the slowest; yellow there is normal.
4. **Size the machine:** `./run.sh capacity cert-autorenewal --students 30` — it counts `step-ca`,
   `demo-app` and PowerDNS on top of the terminals.
5. **Rehearse as a student** in a private window: Labs 1-2 at least — trust the CA, issue with `certbot`,
   then open **Site Inspector** and confirm the `http → 301 → https` chain with a verified cert. If you have
   time, Lab 5's dns-01 so you have seen the TXT records appear and clear on `/dns`. Then `./run.sh stop`
   and start clean.
6. Skim the deck with speaker notes on.

**On the day, 15 minutes before**

- Start the stack; confirm `/` (a **Site Inspector** card), `/slides`, `/inspect`, `/dns` and `/admin`
  (strip all green).
- Keep `/admin` on a second screen; the **Site Inspector** tab lets you check any student's site, and the
  **DNS Zones** tab shows the `_acme-challenge` TXT records during dns-01.

## During the session

**What you can see.** `/admin` tabs: Roster, VS Code, Terminal, Forgejo, Slides, **Site Inspector** and
**DNS Zones**.

- **Say it first:** `step-ca` is on port 9443 on purpose — the terminal's per-account firewall drops
  9000-9099, so the CA sits just outside it. If a student's ACME call to a 90xx port times out silently,
  that is the firewall, not the CA.
- **Lab 4 renewal** installs a crontab; a student who re-runs it can end up with duplicates. A **Reset**
  removes the crontab and re-seeds their two DNS records.
- **Lab 5 (dns-01)** writes real TXT records; watch them appear and clear on the `/dns` page. A stale
  `_acme-challenge` record from an interrupted run is the usual cause of a failed re-issue.
- **Lagging student:** `lab-prep <N>` brings them to the start of lab N; safe to re-run.

**Updating content mid-session.** Slides and labs are bind-mounted; edits to `content/slides/` show
immediately, a new lab file reaches `~/lab` on the next terminal restart, an edited file is never
overwritten.

## When something breaks

| Symptom | Likely cause and fix |
| ------- | -------------------- |
| ACME call times out with no error | The client is hitting a port in 9000-9099 (terminal firewall). `step-ca` is 9443; check the client's CA URL |
| `certbot`/`acme.sh` fails to verify (http-01) | `demo-app` isn't serving the student's webroot yet, or the A record is wrong. Confirm `<user>.certs.dojo.test` on `/dns` and that files are under `/srv/webroot/<user>/` |
| dns-01 fails to verify | A leftover `_acme-challenge.<user>.certs.dojo.test` TXT from a previous run. Check `/dns`; a **Reset** re-seeds clean records |
| Site Inspector shows no cert / plain http | The student hasn't issued or installed yet (Lab 2), or installed to the wrong vhost dir |
| Renewal cron doesn't fire | Lab 4 — check the crontab is installed and the timer reachable; a duplicate crontab from a re-run is common. A **Reset** clears it |
| `git push` asks for a password | Token missing (`ls -l ~/.git-credentials`). **Password** on the Roster tile as a stop-gap |
| One student's terminal wedged | Roster → **Release**; **Reset** returns them to stack-start (crontab gone, two seeded records back), keeping the seat |

## After the session

- `./run.sh stop` wipes everything — containers, volumes, the CA's data, every issued cert, the webroot,
  PowerDNS data, every account.
- Note anything that confused the room or a wrong timing in `ROADMAP.md` (Manual checks) and fix the lab.
