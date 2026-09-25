# tofu-basics — OpenTofu Basics Lab

A ~2¼ hour session on the Terraform-style workflow (`init` → `plan` → `apply` → `destroy`) and how an
IaC repo is laid out, using **OpenTofu**. Students can type `terraform` and get `tofu`: the commands
and HCL are identical. For anyone who has done (or knows) [Git Fundamentals](../git-fundamentals/).

```sh
cd engine && ./run.sh tofu-basics
```

- **Track A — Sandbox** (offline, no cloud, ~37 min): `random_pet`, `local_file`, `terraform_data`.
  Labs 0-3. Can be delivered on its own.
- **Track B — Dojo Cloud** (~66 min): deploy a real container through the real `azurerm` provider into
  an Azure-*inspired* practice cloud with a portal, policy and quotas. Labs 4-10.

**Running it as the facilitator? Read [`FACILITATOR.md`](FACILITATOR.md)**: pre-flight checklist,
run-of-show, what to watch during the session, and how to fix the common failures. This file is the
technical reference. Design, decisions, task list and progress log: [`PLAN.md`](PLAN.md).

## Running it

```sh
cd engine
./run.sh setup            # first time only: creates engine/.env
./run.sh tofu-basics      # build (first time: several minutes) and start
./run.sh stop             # stop and wipe everything, including all deployed containers
```

- `engine/.env` must set `PUBLIC_BASE_URL` and `GATEWAY_TOKEN`; the dojo-cloud module refuses to start without them.
- Always start through `./run.sh`. A plain `podman build` / `docker build` drops the image HEALTHCHECK.
- After changing any image source, run `./run.sh stop` first: Compose does not recreate a running
  container when its image was rebuilt.
- Only the amd64 images have been built and run. The arm64 checksums are pinned but untested.

## What's in this folder

| Path | What it is |
| ---- | ---------- |
| `content/slides/` | Marp deck: `presentation.md`, `labs.md`, `cheat-sheet.md`, and the `index.md` hub |
| `content/lab/` | `README.md` + `lab0.md`-`lab10.md` + `cheat-sheet.md`, seeded into each student's `~/lab` |
| `content/sample-repo/` | The starter repo, seeded into Forgejo as `iac-team/tofu-basics` (`*.tf` files + `sandbox/`) |
| `workshop.env` | `MODULES="dojo-cloud"` brings in Dojo Cloud from `modules/dojo-cloud/` |
| `compose/terminal/` | Student terminal image: OpenTofu, `terraform` symlink, offline provider mirror |
| `modules/dojo-cloud/` (repo root) | Dojo Cloud: `cloud-api` (ARM-style API, policy, executor, portal SPA, unit tests), `cloud-host` (Docker-in-Docker host plus the `dojo/hello` image), the terminal's credential broker, and the card, `/admin` tab, `/cloud` route and status check (`extensions.json`) |
| `FACILITATOR.md` | Facilitator guide |
| `PLAN.md` | Design, decisions, task list, session log |

There are no engine settings for this workshop: the landing-page card, `/cloud` route, the facilitator's
**Dojo Cloud** tab in `/admin` and the status-strip entry all come from `modules/dojo-cloud/extensions.json`
(see `engine/MODULES-PLAN.md`). Two engine
features are on for every workshop: each student's landing page shows their **Forgejo password**, and `/admin`
shows the status strip. See `engine/README.md`.

## Architecture

```text
student terminal --HTTPS, ARM API--> cloud-api --docker.sock (shared volume)--> cloud-host
(workshop_lab)                       (both networks)                            (cloud_net only)
   tofu + azurerm, no internet        auth, policy, executor,                    privileged dind, no ports,
                                      portal, /cloud/site proxy                  no internet, no student route
```

| Service | Role |
| ------- | ---- |
| `web-terminal` (`:tofu-basics`) | Each student's shell, VS Code and `tofu`. Providers come from a read-only mirror in the image, so `tofu init` works with no internet. A root-owned broker hands each shell that user's own `ARM_*` credentials, identified by the kernel (`SO_PEERCRED`), never by anything the student sends. |
| `cloud-api` | Answers the metadata, token and ARM endpoints that `azurerm` expects; enforces policy and quota; turns an approved request into a fixed-template container on `cloud-host`; serves the portal at `/cloud/` and student sites at `/cloud/site/<label>/`. Reached as `management.dojo.cloud` over a private CA. |
| `cloud-host` | `docker:dind`. Runs the students' `dojo/hello` containers. Images are baked in, so nothing is pulled at lab time. |

What happens on `tofu apply`: the provider fetches metadata, gets a token, then `PUT`s a resource group
and a container group. `cloud-api` maps the token to the student's subscription, checks that the path
matches it, runs the policy checks, and asks `cloud-host` for a container built from a fixed template.
Apply takes about 35 s, mostly the provider's own poll ticks. `cloud-api` answers instantly.

**Start-up order.** Nothing waits for Dojo Cloud to be healthy: `cloud-api` starts as soon as `cloud-host`
has started, and the terminal as soon as `cloud-api` has started (`service_started`, not `service_healthy`),
so the lab and Track A come up even if the cloud is slow or broken. `cloud-api` listens at once and answers
`GET /readyz` (unauthenticated; it reveals only ready / starting / unavailable) with 200 when `cloud-host`'s
Docker answers, both hello images are loaded and its start-up reconcile has finished, otherwise 503. The
facilitator's status strip shows that as green, yellow or red. Until it is ready, `cloud-api` refuses
writes (PUT / PATCH / DELETE of container groups, portal delete and tag edits) with an ARM-shaped `503
ServiceUnavailable`, before changing any state; reads keep working. In the terminal, a background loop in
the module's start.d hook (`terminal/start.d/50-dojo-cloud.sh`) waits with no time limit for the cloud's CA and signing key and then writes the
trust bundle; the broker gives a shell no credentials until that bundle exists. A shell captures its
`ARM_*` variables when it starts, and the broker only hands them out once `cloud-api` has created its CA and
key, so **a shell opened before that needs a new terminal tab** (Lab 4 says so). Credentials do not depend on
`cloud-host`: with `cloud-api` up and the host down, a new shell has them and `apply` is what waits.

The Azure vocabulary students see (tenant, subscription, resource group, container group, resource ID,
tags, policy, quota, activity log, `ARM_*` variables) is described in `PLAN.md` §6. "Dojo Cloud" is
Azure-*inspired*: no Microsoft names, logos or artwork, and the portal footer says it is not affiliated
with Microsoft.

## Policy and quota

Everything a student can deploy is bounded by `modules/dojo-cloud/cloud-api/policy.py`. Each rule is a lesson in Lab 6.

| Rule | Error the student sees |
| ---- | ---------------------- |
| Region must be `canadacentral` or `canadaeast` | `RequestDisallowedByPolicy` ("Allowed locations") |
| Tags `owner` and `env` required | `RequestDisallowedByPolicy` ("Require tag …") |
| Names start with `rg-` / `ci-`, lowercase, digits, hyphens | `InvalidResourceGroupName`, `InvalidContainerGroupName` |
| Images: `dojo/hello:1.0`, `dojo/hello:2.0` only | `InvalidImage` |
| Between 0.05 and 0.25 vCPU, and between 0.03125 and 0.125 GB, per container (Docker reads a limit of 0 as unlimited, so there is a floor as well as a ceiling) | `InvalidResourceRequest` |
| Port 80 only, one container per group, no command override | `InvalidRequestContent` |
| At most 2 container groups per subscription | `QuotaExceeded` |
| DNS name label required and unique across the class | `DnsNameLabelInUse` |

### Changing them

- **Change a limit** (regions, quota, size): edit the constants at the top of `policy.py`. **Lab 9 depends
  on the quota:** Lab 5's container plus a two-instance `for_each` is three groups, which is what trips the
  limit of 2. Raising it to 3 breaks the lab.
- **Add a rule:** add a check to `policy.py` (pure functions, no I/O), add a test in
  `modules/dojo-cloud/cloud-api/test_policy_auth.py`, and run the tests. If students will hit it, add it to a lab,
  and paste the error text from a real run: the labs contain real output, not invented output.
- **Add an image:** add it to `ALLOWED_IMAGES` in `policy.py`, and make `cloud-host` import it
  (`modules/dojo-cloud/cloud-host/entrypoint.sh`, `import_hello` for another version of hello; a different app needs
  its root filesystem baked into `modules/dojo-cloud/cloud-host/Dockerfile`). The executor still forces port 80 and no
  command. Update the labs that name `1.0` and `2.0` (Lab 6 and Lab 8's `validation` block).
- After any change under `compose/` or `modules/dojo-cloud/`, `./run.sh stop` and start again. `run.sh` notices the changes.

## Security model, in short

Assume 30 curious students who each have a shell. Full table in `PLAN.md` §7.

- **Students never speak Docker.** They speak ARM to `cloud-api`, which builds the container from a fixed
  template: allow-listed image, memory/CPU/pids caps, all capabilities dropped, `no-new-privileges`, no
  mounts, no host networking, and `--icc=false` so containers should not reach each other. The template
  is unit-tested; the network isolation has not been probed live yet (`PLAN.md` T9.8).
- **`cloud-host` is unreachable except through `cloud-api`:** an `internal: true` network (no internet), no
  published ports, no TCP listener (the unauthenticated `tcp://…:2375` listener that `docker:dind` opens is
  removed at build time, and the build fails if that stops working), a unix socket on a volume shared only
  with `cloud-api`.
- **Identity:** a student's credentials come from the broker by Linux uid; a token for one subscription is
  refused (`403`) on another's path; the signing key is root-only. The portal API trusts `X-Auth-User` only
  together with `X-Gateway-Token`, which only Caddy sets (students can reach `cloud-api:8080` directly).
- **Student text is shown to the whole class** (names, tags, `MESSAGE`). The portal renders it with
  `textContent` under a strict CSP, and sites are served with CSP `sandbox`.
- **Accepted risk:** `cloud-host` is a privileged container. It is boxed in as above, and no student-controlled
  path reaches the Docker API, but a privileged container is still a privileged container. It has been
  tested only under **rootless podman**, where "privileged" is weaker than under Docker. Re-review under
  Docker before delivering there (`PLAN.md` T9.8).

## Resetting things

| To… | Do |
| --- | -- |
| Wipe everything between classes | `./run.sh stop` (removes all volumes, including `cloud-host`'s Docker data, so all deployments, state and portal history). Verified live: after a normal stop, and after `podman kill workshop_cloud_host` then stop, no containers, volumes, networks or stray processes remained |
| Empty one student's cloud (they lost `terraform.tfstate`) | Portal **Home → Facilitator panel → Purge subscription** |
| Stop students deleting things in the portal | Same panel, **Portal write actions** switch (OpenTofu is unaffected) |
| Restart the control plane only | `docker restart workshop_cloud_api` (`podman restart` on podman). State lives in a volume and survives; verified with a real deployment |
| Restart the container host only | `docker restart workshop_cloud_host`. Student containers use restart policy `unless-stopped`, so they **come back by themselves**: in the live test the site answered again about 10-15 s after the restart, `plan` said `No changes`, and no student did anything. The strip goes yellow, then red for a few seconds, then green. No `cloud-api` restart is needed. If you stop or `kill` the host by hand, start it again with `docker start workshop_cloud_host`: a hand stop is not restarted automatically (a crash is) |

## Tests

Offline, host Python only, no containers:

```sh
cd ../../modules/dojo-cloud/cloud-api && python3 -B -m unittest test_portal_api test_executor test_policy_auth test_readiness   # 131 tests
cd .. && python3 -B -m unittest test_parity                                                                     #   5 tests
```

`test_parity` checks that the terminal's broker and `cloud-api` agree on how a username maps to credentials.
There is no committed end-to-end or load test yet (`PLAN.md` T9.1, T9.3, T9.6). Note that `--test` demo
bots only exercise git, not OpenTofu.

## Known limits

- **A cloud-host outage fails fast, not slowly.** While the host is down, container-group reads answer from the stored
  record, so `plan` finishes in a few seconds (`No changes`), and writes fail within about 3 s with HTTP 409 and the text
  "Dojo Cloud is unavailable: ... Nothing was changed. Wait a minute and run the command again, or tell your facilitator."
  (the provider does not retry a 409; it prints the JSON with its own `\"` escapes). Resource-group writes are refused too, so an
  `apply` fails on its first request and changes nothing; only a host that dies between two requests of one `apply` leaves it half done (re-run it). The
  portal shows a container as `Unknown` once the host has been unreachable for 10 s.
- **Not load-tested.** Never run with 30 students applying at once. `cloud-api` holds one lock across the
  Docker calls in an apply, which stalled the portal about 3.3 s per deploy in a single-student measurement
  (`PLAN.md` T9.7). See `FACILITATOR.md` for how to run Lab 5 with that in mind.
- **Not dry-run with people**, and the portal and Labs 4-10 have had no real-browser pass by a human (T9.4, T9.9).
- One container per group, `dojo/hello` images only, port 80 only, by design.
- Error messages say `tofu` even when a student typed `terraform`; that is expected (Lab 0 says so).
- On a dev box whose gateway is on a non-default port, the `url` output and portal link omit the port
  (they come from `PUBLIC_BASE_URL`), so the labs say `<class-address>`.
- The private CA's certificates last 30 days and are regenerated only when the files are missing; only
  matters for a machine left up for more than a month.
