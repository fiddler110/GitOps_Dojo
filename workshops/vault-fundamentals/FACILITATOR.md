# vault-fundamentals — facilitator guide

For the person running the session. The technical reference is [`README.md`](README.md); the design and
history are in [`VAULT-FUNDAMENTALS-PLAN.md`](../../docs/archive/VAULT-FUNDAMENTALS-PLAN.md); the deck's
speaker notes carry the talking points. This guide is the practical part: before, during, after, and what
to do when something breaks.

**Honest status:** the longest and most advanced course — fourteen labs (0-13, about 3½ hours) on a real
OpenBao. Run end to end with the demo bots (`--test` walks labs 0-11) and the student-reset live pass, not
yet with a room. The timings below are estimates. Do the rehearsal, and budget a longer first build.

## The session at a glance (about 3½ hours of labs)

Fourteen labs, 0-13. There is far more here than one lunch slot; it is built to be split or to run as a
half-day. A rough shape:

| Block | Labs | What |
| ----- | ---- | ---- |
| Talk | — | Secrets out of code/git/pipelines/servers; identity and short-lived credentials over long-lived passwords |
| Foundations | 0-3 | Sign in by identity, leaks in git, encrypt on your own machine (`pass`/`sops`), KV secrets and policies |
| Your namespace | 4-7 | Your own namespace, secrets in code and in git |
| CI and platform | 8-9 | CI that logs in with its own identity (a fork + Forgejo Actions), deploys with a platform identity |
| Dynamic and drill | 10-13 | Dynamic database logins, an incident drill, and the capstone |

**Prerequisite:** git-fundamentals (stated), and it leans on dns-as-code's PR/CI ideas for Labs 8-9.
**Every lab is mandatory, in order.** For a shorter session, the natural cut is after Lab 7 (KV, policies,
namespaces) or after Lab 9 (CI + platform identity); the dynamic-secrets and incident-drill labs are the
advanced tail.

**Lab 8 forks** (`FORGEJO_FORK_WORKFLOW=1`): each student forks the team repo and works in the fork, and
CI runs on the single-use runner pool. The demo bots do the same.

**The capstone** gets each student a second app slot, `<user>-capstone`, while the lab app keeps running.

## Before the session

**A day ahead**

1. `cd engine && ./run.sh setup` if there is no `engine/.env`. Set `PUBLIC_BASE_URL`, `GATEWAY_TOKEN`,
   `STUDENT_COUNT`.
2. **Rootful Podman on macOS only:** `engine/.env` must carry `RUNNER_POOL_SECURITY_OPT_1=unmask=/proc/*`
   and `RUNNER_POOL_SECURITY_OPT_2=label=type:container_engine_t`, or neither the runner pool nor the app
   host starts (`unshare: mount /proc failed`). `./run.sh setup --default --force` overwrites `.env`, so
   re-add them. On Docker / rootless Linux, leave them unset. Also give `openbao-setup` more than 64m of
   memory — it needs it to provision every namespace. (Details in `modules/runner-pool/README.md`.)
3. **No password to announce** — each terminal is signed in with the student's own token. **Password** on
   the Roster tile shows it if needed.
4. `./run.sh vault-fundamentals`. The first build is the longest of the series (OpenBao, `app-host`,
   `app-db`, the runner pool, and a terminal image with `sops`, `gitleaks`, `pass`, `psql`, `hvac`). Open
   `/admin` and wait for **Forgejo**, **Terminals**, **Slides**, the **runner pool**, and the vault to go
   green; `openbao-setup` provisions namespaces and seed secrets per student, which takes a while.
5. **Size the machine:** `./run.sh capacity vault-fundamentals --students 30` — it counts OpenBao,
   `app-host`, `app-db` and the runner pool on top of the terminals.
6. **Rehearse as a student** in a private window: Labs 0-1 (identity sign-in, a git leak), then jump to
   Lab 8 (fork + CI) so you have seen a runner job go green, and the capstone slot come up. Then
   `./run.sh stop` and start clean.
7. Skim the deck with speaker notes on.

**On the day, 15 minutes before**

- Start the stack; confirm `/`, `/slides`, the **My App** card, and `/admin` with its vault tabs.
- Keep `/admin` on a second screen.

## During the session

**What you can see.** `/admin`, besides the engine's tabs, has:

| Tab | What |
| --- | ---- |
| **Vault** | the OpenBao UI, signed in as the facilitator |
| **Audit** | every request, filterable by student, operation, path and accessor (values are HMACed) |
| **Runners** | the single-use CI pool: Auto / Manual, − / + |
| **Apps** | every `app-host` slot and its log |

- **Say it first:** CI runners are single-use (Labs 8-9), so a job queues behind the pool. If everyone
  hits CI at once, raise the runner count (Runners tab, +). A job that "hangs" is usually waiting for a
  free runner.
- **Lagging student:** `lab-prep <N>` brings them to the start of lab N; safe to re-run.
- **Audit tab** is the teaching aid for the "what did I just do" question: filter by the student and you
  can see their path and operation (not the secret value — those are HMACed).
- **Lab 11 is an incident drill** — expect deliberate breakage and questions; that is the lab.

**Security shortcuts stated to the class** (slide "What today's vault cuts short", from the threat-model
remediation): **one unseal-key share** on the `openbao_setup` volume, so the vault unseals itself after a
restart. That is a lab convenience, not production practice — say so.

**Updating content mid-session.** Slides and labs are bind-mounted; edits to `content/slides/` show
immediately, a new lab file reaches `~/lab` on the next terminal restart, an edited file is never
overwritten.

## When something breaks

| Symptom | Likely cause and fix |
| ------- | -------------------- |
| Runner pool / app host won't start on macOS | The two `RUNNER_POOL_SECURITY_OPT_*` vars are missing from `engine/.env` (a `setup --force` wiped them). Re-add and restart |
| `openbao-setup` fails or namespaces missing | It needs more than 64m; raise its memory. Check `./run.sh logs openbao-setup \| tail -40` |
| Vault "sealed" after a restart | It should self-unseal from the share on `openbao_setup`. If it didn't, `./run.sh logs openbao \| tail`; a restart of the setup service re-runs unseal |
| CI job stuck "queued" | No free runner — single-use pool. Raise the count in the **Runners** tab |
| Lab 8 push goes to the team repo | The student cloned the team repo, not their fork. `git remote -v`; the lab has them fork first |
| App won't deploy / slot stuck | **Apps** tab shows each slot and its log. A student reset drops and remakes their database and empties both slots |
| `git push` asks for a password | Token missing (`ls -l ~/.git-credentials`). **Password** on the Roster tile as a stop-gap |
| One student's terminal wedged | Roster → **Release**; **Reset** returns them to stack-start (namespace re-seeded, database remade, slots emptied), keeping the seat |

## After the session

- `./run.sh stop` wipes everything — containers and volumes, the vault with them, every app slot and
  database, all accounts.
- Note anything that confused the room or a wrong timing in `ROADMAP.md` (Manual checks) and fix the lab.
