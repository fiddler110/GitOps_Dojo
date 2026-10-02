# tofu-basics — facilitator guide

For the person running the session. The technical reference is [`README.md`](README.md); the deck's
speaker notes carry the talking points. This guide is the practical part: before, during, after, and
what to do when something breaks.

**Honest status:** nobody has run this with a room yet. The lab commands were run live one student at a
time; a 30-student class, and the timings below that aren't the labs' own estimates, are untested (TOFU-BASICS-PLAN.md
T9.3, T9.4). Do the rehearsal below.

## The session at a glance (about 2¼ hours)

| Block | Minutes | What |
| ----- | ------- | ---- |
| Talk, parts 1-3 | ~20 | Why IaC, OpenTofu vs Terraform, building blocks, file map, the lifecycle. *A guess until a dry run.* |
| **Track A**, Labs 0-3 | ~37 | 5 + 12 + 12 + 8. Offline sandbox, zero risk |
| Dojo Cloud tour | ~10 | Part 4 of the deck: the Azure vocabulary, the portal, policy and drift, before anyone deploys |
| **Track B**, Labs 4-10 | ~66 | 8 + 10 + 12 + 8 + 12 + 8 + 8 |
| Recap and questions | ~5 | Ask each table what surprised them (usual answers: apply is slow, `plan` didn't catch a policy error, drift) |

Lab times are the estimates in `content/lab/README.md`. **In a 2-hour slot**, drop Lab 9 (Lab 10 copes
with or without its extra containers) and/or the optional last section of Lab 8. **Track A alone** is
about an hour with the talk, and is the right choice if the cloud misbehaves.

Rules that hold the labs together: keep the order, and **nobody destroys anything before Lab 10**, because
Labs 6-9 build on Lab 5's deployment. Lab 9 half-applies on purpose (that is the quota error); make sure
people finish its clean-up section before Lab 10.

## Before the session

**A day ahead**

1. `cd engine && ./run.sh setup` if there is no `engine/.env`. It must contain `PUBLIC_BASE_URL` (what
   students will type, including the port if it isn't 80/443) and `GATEWAY_TOKEN`. Set `STUDENT_COUNT`.
2. **Student password:** nothing to announce. Each student's terminal is signed in to Forgejo with their own
   token (`~/.git-credentials` for git, `~/.netrc` for Lab 0's `curl --netrc` fork), so no lab asks for a password.
   If you ever need one, **Password** on the student's Roster tile shows it.
3. Build and start: `./run.sh tofu-basics`. The first build takes several minutes (the terminal image is
   about 1.1 GB, `cloud-host` about 370 MB). Open `/admin` and check the **service status strip** at the top right: **Forgejo**,
   **Terminals**, **Slides** and **Dojo Cloud** should all be green (Ready). On a warm start they turned green
   after about 5, 30, 36 and 66 s in the live test. **Terminals is the slowest, about a minute or more**,
   because the terminal container is creating every student account: yellow there is normal, not a fault. `docker ps` /
   `podman ps` should show the containers healthy too.
4. **Size the machine.** Name the workshop, so the calculator counts `cloud-host` (3 GB), `cloud-api` and the
   other module services too (about 6.5 GB besides the terminals):

   ```sh
   ./run.sh capacity tofu-basics --students 30
   ```

   Those are the ceilings the dojo-cloud module sets (`CLOUD_HOST_MEM_LIMIT` 3g, `CLOUD_API_MEM_LIMIT` 256m), not
   measured use. Measured so far: `cloud-host` about 58 MB and `cloud-api` about 13 MB idle. Memory with 60
   running containers has **not** been measured; expected well under 1 GB, since the hello image is tiny.
   If you change the two limits in `.env`, change `6400` to match.
5. **Rehearse as a student.** Open the landing page in a private window: you get a real student account,
   the same experience the room will have. Do Labs 0-1, then Labs 4-5, and open the portal. Check that the
   site link works and that your deployment appears on **Class progress** in your facilitator window. Then
   `./run.sh stop` and start clean. (Your facilitator workspace never takes a student slot, so it does
   not tell you what students see.)
6. Skim the deck once with its speaker notes on.

**On the day, 15 minutes before**

- Start the stack, then confirm `/` (landing page shows a **Dojo Cloud** card), `/slides`, and `/admin`.
- Open `/admin`: the strip should be all green, and the **Dojo Cloud** tab is the class progress board. Keep
  it on a second screen.
- The portal's **Class view** shows everyone's sites read-only; students can browse each other's.

## During the session

**What you can see.** `/admin` has tabs for the roster (live view of every student's terminal), VS Code,
Terminal, Forgejo, Slides and **Dojo Cloud**. In the portal (Home, facilitator only) there is a
**Facilitator panel** with the whole-class overview, the write-actions switch and **Purge subscription**.
The **Class progress** page shows one tile per student:

| Stage | Meaning |
| ----- | ------- |
| Not started | no resource group, container or activity yet |
| In progress | something exists or was tried, but no running container yet. An apply that is part-way sits here, because the resource group appears before the container does |
| Running | all their container groups are Running |
| Needs attention | their latest operation failed, or a container is Terminated. The tile shows `code: message`, so a policy error is readable without asking |

Sort by *needs attention first* during Labs 5-6. Lab 6 makes people fail on purpose, so a wall of red
tiles then is expected, not an outage. Tell the room that before they start.

**Service status strip** (top right of `/admin`; facilitator only, students never see service health).
One chip per service with a dot and a word, and the reason on hover:

| Chip | Meaning |
| ---- | ------- |
| Green, **Ready** | last check succeeded |
| Yellow, **Starting** | not up yet (up to 5 minutes after the stack started), or it was up in the last 30 s and just dropped (a restart) |
| Red, **Down** | not up after the grace period, or gone for more than 30 s. Hover for the reason |

The services are **Forgejo**, **Terminals**, **Slides** and **Dojo Cloud**. Dojo Cloud is green only when the
cloud host is answering, both hello images are loaded and the control plane has synced with the host. Track A
and everything else work while it is yellow or red.
**When Dojo Cloud turns green** after a late start, tell the room: a terminal shell picks up its cloud
credentials when it starts, so anyone whose `env` shows no `ARM_` lines in Lab 4 opens a **new terminal tab**.
(Credentials are available as soon as `cloud-api` is up, even while the cloud host is still down, so this only
matters if `cloud-api` itself started after the student's shell did.)
While it is not green, `apply` and the portal's delete and tag buttons answer `ServiceUnavailable` (a clean 503
that changes nothing); `plan` and reading still work.

**Timing notes**

- **`apply` takes about 35 s** (resource group ~20 s, container group ~13 s). "Still creating…" is normal.
  Say so before Lab 5 or half the room will interrupt.
- **Have Lab 5 applied in two or three waves rather than all at once.** Reason, not measurement: a deploy
  holds a control-plane lock for about 3 s while Docker creates the container, so 30 simultaneous applies
  queue behind each other (TOFU-BASICS-PLAN.md T9.7). If a tile stays *In progress* for more than a couple of
  minutes, that is the first thing to suspect. Watch the first class and tell us what you saw.
- Check in at about 15 minutes into Track A. Lab 2 is where `~` and `-/+` first appear together.

**Drift (Lab 7).** Students delete their container in the portal, then `plan`. If the portal has no
**Delete** button for them, the write-actions switch is off: turn it on. You can turn it off again after
Lab 7 if people are clicking around.

## When something breaks

| Symptom | Likely cause and fix |
| ------- | -------------------- |
| `Error: a resource with the ID … already exists … needs to be imported` | The student lost `terraform.tfstate` (deleted it, or is in another folder). **Purge their subscription** (portal Home, Facilitator panel), then they run `terraform apply` again. Check `cd ~/lab/tofu-basics` first: it is often the wrong folder |
| `apply` fails with `DnsNameLabelInUse` | Site names are `<workload>-<env>-<owner>` and must be unique across the class, so another student already has that name. Have the student check `echo $TF_VAR_owner` is their own username |
| `unexpected status 409 ... ServiceUnavailable: Dojo Cloud is not ready / unavailable ...` on `apply` or `destroy`, or the portal's delete / tag buttons fail | Dojo Cloud is not ready (cloud host still starting, or down). Check the strip. The message says nothing was changed, so it is safe to retry once **Dojo Cloud** is green |
| `QuotaExceeded` | In Lab 9 this is the lesson. Anywhere else, the student has 2 groups already: they destroy one, or you Purge |
| `unexpected status 409 ... Conflict: Another operation on this container group is in progress ...` | Two operations hit the same container group at once (a double-click, or a portal delete during an `apply`). Nothing was changed. Wait a few seconds and retry. A similar 409 says the names are "too close to another of your container groups": the two would share a Docker container name, so rename one |
| `RequestDisallowedByPolicy`, `InvalidImage`, `InvalidResourceRequest`, … | The student broke a rule. The message says which and lists what is allowed. Expected in Lab 6 |
| No `ARM_` variables (`env` shows none), or `curl: (60) SSL certificate problem` | Credentials attach when a shell starts. A new terminal tab fixes it. If not, the broker is not running: `docker logs workshop_terminal --tail 50`, and as a last resort `docker restart workshop_terminal` (untested for this case; it drops every student's shell) |
| Portal card or page won't open | Back to the landing page, click **Dojo Cloud**. A 404 on `/cloud/` means the stack was started for another workshop |
| Portal shows stale data | It polls every ~3 s. **Refresh now** |
| Lab 0's `curl` fork prints `401` / `Unauthorized` | The student left out `--netrc`, or their token is missing (`ls -l ~/.netrc` in their terminal; the terminal's log has a `forgejo-token:` line). `repository is already forked` is not an error: they did it before |
| `git push` rejected, or it goes to `iac-team/tofu-basics` | The student cloned the team repo instead of their fork. `git remote set-url origin http://git-server:3000/<student>/tofu-basics.git` in the repo, then push again |
| `git push` asks for a password | The token is missing from `~/.git-credentials` (check with `ls -l`; the terminal's log has a `forgejo-token:` line). As a stop-gap, **Password** on their Roster tile shows the Forgejo password to type |
| The `url` output or portal link is missing the port | Dev box with a non-default port: `PUBLIC_BASE_URL` has no port. The labs already say `<class-address>` |
| Every apply fails or hangs | Check the Dojo Cloud chip first (red: hover for the reason). Then `docker ps`: is `workshop_cloud_host` up? `docker logs workshop_cloud_api --tail 50`. If the control plane is broken, **fall back to Track A** (below) and fix it in the break |
| One student's terminal is wedged | `/admin` roster, **Release** on their tile; their next visit reassigns an account (the same one if it is still free) |

**Restarting parts.** `docker restart workshop_cloud_api` is safe mid-session: state lives in a volume and
survives (verified). **Restarting `workshop_cloud_host`** (verified live on podman) is survivable: student
containers restart by themselves, so no student has to do anything. Expect the Dojo Cloud chip to go yellow,
then red for a few seconds, then green, and the students' sites to answer again about **10 to 15 seconds** after
the restart. If you stopped or killed it by hand, start it again with `podman start workshop_cloud_host` (a hand stop
is not restarted automatically; a crash is). `cloud-api` needs no restart. Still, avoid doing it in the middle of Track B if you can. Do not `podman rm -f` the control plane while the terminal is up:
the terminal depends on it and the removal fails silently. The terminal and `cloud-api` no longer wait for
Dojo Cloud to be healthy, so a broken cloud at stack start still leaves the lab, the terminals and Track A
working; only Track B waits (verified live with a host that could not start).

**While the host is down, nothing freezes.** `terraform plan` finishes in a few seconds and says `No changes`,
and any `apply` or `destroy` that needs the host fails within about 3 seconds with a message that says what to
do (`unexpected status 409 ... ServiceUnavailable: Dojo Cloud is unavailable: the cloud host is not answering.
Nothing was changed. Wait a minute and run the command again, or tell your facilitator.`). Students just re-run it
once the chip is green. Nothing is half-applied: resource-group changes are refused too, so the run fails on its
first request. The portal's delete and tag buttons fail immediately and change nothing, and the
portal shows the container as `Unknown` after 10 s. Verified live.

**Fallback to Track A.** Track A needs no cloud: the terminal's credential step silently does nothing when
the control plane is absent, and the providers are mirrored in the image. If Track B cannot be fixed in the
room, finish on Track A and the recap. Dojo Cloud state is intentionally ephemeral, so after a control-plane
reset some students may need a Purge.

**Updating content mid-session.** Slide and lab files are bind-mounted: edits to `slides/` show up
immediately. A new file in `lab/` reaches students' `~/lab` on their next terminal restart, and a file a
student has already edited is never overwritten (`engine/README.md`, "Update workshop content mid-session").

## After the session

- `./run.sh stop` wipes everything: the volumes (including `cloud-host`'s Docker data), every deployed container,
  all state. Nothing is kept. Verified live, including after a hard kill of `cloud-host`: no containers, volumes,
  networks or stray processes left behind.
- If you learned something (a lab step that confused people, a timing that was wrong, a failure not in the
  table above), write it into `ROADMAP.md` (Manual checks) and fix the lab. The first real class is also the dry run
  (TOFU-BASICS-PLAN.md T9.4): note where people got stuck, how long each block really took, and whether the 30-student
  apply behaved.
