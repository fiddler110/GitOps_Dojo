# CTF workshop: spike answers and decisions log

Split out of [`CTF-WORKSHOP-PLAN.md`](CTF-WORKSHOP-PLAN.md) on 2026-10-05 to keep that file lighter to read. Same
status as the plan it came from: **not archived**, owned by whoever is driving the CTF build, live and append-only —
new spikes get answered here, new decisions get logged here, neither gets rewritten. Spike IDs (`CTF-S1`...) and
decision IDs (`CTF-D1`...) that the plan refers to live in this file. Where a spike or decision below says
"section N" or "section N.M", that's a section number in `CTF-WORKSHOP-PLAN.md`, not in this file.

---

## Spike answers

Run 2026-10-04 on macOS, Podman 6.1.3 (rootful `applehv` machine, netavark 1.17.2), podman-compose 1.6.0. **Docker
and rootless Podman were not available, so every "works on both runtimes" claim below is Podman-rootful only and
still needs a Linux/Docker pass (CTF-P4).** Throwaway test scripts were not kept. Status key: **proven** (ran it),
**read** (settled from the repo's code), **open** (needs a decision or a live number).

| Spike | Status | One-line answer |
|---|---|---|
| S1 | proven + read | No existing step emits compose, and `deploy.replicas` is ignored. Don't generate N services; let the controller own the containers (S14) |
| S2 | proven | Firewall *inside each target* isolates targets from each other, with no network tricks. Per-target networks also work to 160 |
| S3 | proven | Owner-matched `OUTPUT` plus source-matched `INPUT` gives the return path and isolates listeners. Rules need re-applying at container start |
| S4 | read | A `ctf` event source is about 6 one-line edits in 2 files plus tests; a verifier plugin needs none but polls |
| S5 | read | All three GitOps targets live in Forgejo, `runner-pool` and OpenBao on `workshop_lab`, not in a `ctf_net` slot; only small additions needed |
| S6 | **built and proven end to end, no known open items** | Registry-based rebuild/redeploy works with no `docker.sock` anywhere; PR gate proven live (Run B); both offline-rebuild blockers (`FROM` resolution, Run C; `pip install`, Run D) fixed and live-verified; real number: **83s** push-to-redeployed (Run D, 2026-10-05). Both optimization follow-ups (startup-time regression, start-order race) fixed and live-verified in Run E |
| S7 | proven | The old box builds only after two fixes and runs hardened at about 13 MB |
| S8 | open | Not run; see below |
| S9 | open | Numbers are proposals; only a live class settles them |
| S10 | read | Poll every 4-5 s, the engine-wide pattern |
| S11 | read | A map is its own facilitator-gated route, not a `widgets` entry |
| S12 | read | Spool directory in a volume the terminal never mounts, as `runner-pool` does |
| S13 | proven in part | CPU budget for the 5-10s ramp floor is fine (well under 1 core); curve shape, attention-split and top-10 formula still open, see below |
| S14 | **built** (CTF-5 scope), was proven in part | The host-socket proxy has no precedent and is the riskiest piece; a boxed Docker-in-Docker host works and matches `dojo-cloud`. `ctf-host` + `ctf-controller` now built and verified live (see the S14 "Built" note); warm figures and the CTF-1 to CTF-4 toggle/queue remain |
| S15 | read + open | Code-server is lazy per the README (about 260 MB when open); terminal-only cost is in S16. Hiding the VS Code tab is untested |
| S16 | proven in part | tmux + yazi + micro is about 23 MB per student; adding Zellij adds 40-50 MB. Watcher attach unconfirmed |
| S17 | open | Not run; see below |

### S1, N targets from `STUDENT_COUNT`

- `engine/dojo/stack.py:extra_files` returns a static list: each module's `compose.yml` in `MODULES` order, then the
  overlay. The only generating step is `_render_extensions` in `start.py`, and it renders `extensions.json` into
  `.generated/`, never compose. So no existing step can emit a compose fragment.
- `deploy.replicas: 3` under podman-compose 1.6.0 started **one** container. Replicas and `--scale` are not an option,
  because `run.sh` doesn't pass a scale flag.
- A fleet container (one container, N target processes) gives up per-slot addresses and per-target hardening.
- **Answer:** don't make Compose own the fleet. D20 already needs a controller that starts and stops slots, so the
  controller creates the slot containers itself, from `STUDENT_COUNT`, when it starts. This needs no engine change,
  so CTF-D15 does not trigger. It makes S14 the load-bearing spike.

### S2, target-to-target isolation

- Baseline on one internal bridge: container A reaches B on TCP and ICMP. Isolation does not come for free.
- **Firewall inside the target (recommended).** The target's entrypoint runs with `NET_ADMIN`, sets `INPUT` and `OUTPUT`
  to `DROP`, accepts loopback and only the terminal's address, then `exec`s the service through
  `setpriv --bounding-set=-all --inh-caps=-all --ambient-caps=-all`. Result: terminal to target worked, sibling
  target to target timed out on TCP and ICMP, and the service's `CapEff` and `CapBnd` were all zero, so even a root
  shell in the target cannot flush the rules. Needs `iptables` and `util-linux` (real `setpriv`; busybox's has no
  `--bounding-set`) in the target image, which must be built with network access, since `ctf_net` has none. Works
  with any runtime that honours `cap_add`.
- **Per-target networks.** 160 `--internal` /29 networks were created in 13 s, one container attached to all 160
  started instantly (161 interfaces), and removal took 16 s. It works, but joining the terminal to N networks at
  compose time is exactly the generated-fragment problem S1 rules out. Keep as a fallback.
- **`enable_icc=false`.** netavark's `network create` offers no ICC option, so it isn't available under Podman. The
  nested Docker option (S14) does use `dockerd --icc=false` and blocked lateral traffic (rc=1; the baseline for that
  exact pair was not re-run).
- Not tested: rootless Podman, Docker, and the terminal joining 160 networks.

### S3, listener return path

Mock terminal with `NET_ADMIN`, two uids (ranges 4010-4019 and 4020-4029), two targets, one service on 9000:

- Target 1 reached uid 1's listener on 4011; target 2 could not (`INPUT` is `-i <ctf if> -s <target> --dport <range>`).
- Target 1 could not reach a service on port 9000 on the terminal.
- uid 2 could not reach uid 1's listener over `127.0.0.1` or over the terminal's own `ctf_net` address; uid 1 reached
  its own over loopback. The rules are one owner-matched `OUTPUT` chain, evaluated for local delivery too.
- Packet counters showed uid 1's traffic to its own target hit the `ACCEPT` rule and to the other target hit the
  `DROP` rule. (Wall-clock timings of a refused versus dropped connect were unusable: even root took about 3 s here,
  which looks like a harness quirk. Use counters, not timings, in the isolation tests.)
- **Rules do not survive a container restart** (`OUTPUT` policy was back to `ACCEPT`). Apply them from
  `start.d/50-ctf-range.sh`, as `DOJO_ISOLATION` is applied by the entrypoint. A student reset does not touch them,
  since they live in the container's netns, not in the student's account.
- **Residual risk:** iptables cannot stop another uid *binding* a classmate's listener port first, which would sabotage
  that classmate's `ncat`. The test for it was inconclusive. It is self-contained (no data exposed), so accept it and
  say so in the labs, or reserve ports at start.

### S4, achievements `ctf` source

- **Event source (recommended).** Add `ctf` to `ADAPTER_SOURCES`, `ADAPTER_EVENTS` and `MATCH_FIELDS` in
  `modules/achievements/catalog/catalog.py`, and to `ADAPTER_EVENTS` plus the tuple at `matcher.py:428` and the
  dispatch table at `matcher.py:450`, with tests. No new field is needed: send `{source:"ctf", event:"flag", user,
  reason:"<challenge>", op:"user|root"}` and match with the existing `reason`/`op` text fields. Posting uses
  `modules/_shared/adapter_client.py` as the other modules do. This touches the achievements module only.
- **No core change (fallback).** A plugin in a folder named in `ACHIEVEMENTS_PLUGIN_DIRS`
  (`verifiers.json` plus a Python file with `VERBS`) adding a `flag_solved` verb that asks `ctf-flags`, used by
  `verify` milestones. Cost: it is state-polled (`ACHIEVEMENTS_STATE_SECONDS`, default 20, at most 40 backend checks
  per pass), so with about 28 milestones per student at 40 students the unlock latency is **unmeasured** and may be
  minutes. Fine for correctness, poor for a live leaderboard.
- Verbs alone can cover validity (the service checks the flag), but not immediacy.

**Built and unit-tested (2026-10-05):** the `ctf` source already existed (`flag_solved`,
`dump_success`); added a sibling `soc` source for the attacker-swarm alerts proper (§8.2) -
`recon`/`probe`/`exploit_attempt`/`contained`, severity derived from `event` in store.py
(`SOC_SEVERITY`), never trusted as a free-text field from the poster. A student's own feed
(`/achievements/soc`, `GET /api/soc`) and the facilitator's room-wide one
(`/achievements-admin/soc`) are both built, each a bounded in-memory deque (not persisted,
same treatment as the wall of shame's `ctf_dumps`). 342 achievements tests pass.

### S5, GitOps targets

All three run on `workshop_lab` services the terminal can already reach; none belongs in a `ctf_net` slot, and
`ctf_net` must still never reach Forgejo (section 6).

- `git-secrets` (built 2026-10-06): the sketch above (reusing the achievements `forgejo-repo` seed builder and
  `history_absent` verb) wasn't what got built — those are for achievements' graded PR-challenge flow, and
  `git-secrets` is a flag-submission CTF target with no PR to grade, so pulling in the achievements module as a
  dependency would have been the wrong shape. Built instead as a small, self-contained module-level hook,
  `modules/ctf-range/terminal/start.d/55-git-secrets.sh` (a no-op unless the pack's `CTF_ATTACK_TARGETS` lists
  `git-secrets`): plain `git init`/commit/push, two commits (token added, then "cleaned up" out of the tree but not
  the history), using the same curl+netrc Forgejo-admin idiom `90-ctf-defend-test.sh` already established. The
  "second target the recovered token opens" is `modules/ctf-range/targets/git-secrets/` — a tiny, deliberately
  bug-free, token-gated `/deploy/trigger` — wired into the normal attack-ladder catalog, not a separate mechanism.
  One piece of new *generic* controller plumbing this needed: `AttackManager._env_for` (`ctf-controller/controller.py`)
  now renders a second per-(user, target) secret, `CTF_TARGET_TOKEN`, using the same `flags.render` derivation as
  `CTF_FLAG` with its own challenge tag — every other target ignores it, only `git-secrets` reads it, and the
  provisioning hook recomputes the identical value independently (same two-copies idiom as every flag render in
  this range), so the target container still never holds `STUDENT_PASSWORD_SEED`. Live-verified end to end
  (`docs/CTF-WORKSHOP-PLAN.md`'s checkpoint has the detail).
- `runner-escape` (built 2026-10-06): `runner-pool` already gives single-use runners with a per-job user and PID
  namespace, and "expected to fail" needs no new image, only a seed repo and workflow. Built exactly that way:
  `workshops/ctf-defend-test/compose/terminal/start.d/96-runner-escape.sh` seeds each student a `<user>/ci-pipeline`
  repo (a benign CI workflow on `main` + a `CTF_FLAG` Actions secret the workflow never reads), this-pack-only
  (needs `runner-pool` in `MODULES`, same scoping reasoning as `tfstate-treasure` needing `openbao`). The foothold:
  Forgejo's `pull_request` runs the **PR branch's** workflow version, so a same-repo PR editing
  `.forgejo/workflows/ci.yml` runs attacker-chosen code on a shared runner with `secrets.CTF_FLAG` in scope — the
  single-tenant equivalent of a fork PR. **This settled the open `pull_request_target` spike risk** (T0.3,
  `docs/archive/REMEDIATION-PLAN.md`, left inconclusive 2026-09-28): the target never needs `pull_request_target`
  (the mode T0.3 couldn't settle) — plain `pull_request` with same-repo secrets is sufficient *and* proven reliable
  (this build + `defend-pr.yml`'s existing live use). **Design pivot caught live:** the auto-issued Actions
  `GITHUB_TOKEN` (40 chars, present on every job) is blocked by the branch pre-receive hook from pushing to any
  branch here, so exfil is through a **PR comment** (base64, marker-prefixed), not a file write — the smallest
  reliable channel the token has. The escalation (plan row 10: "read another job's leftover state") **fails by
  design** and that is the lesson: the probe step saw its own per-job user only, another runner's home
  `drwx------`/unreadable, and only its own process tree under `ps aux`. Zero controller/ctf-flags/engine code;
  new files are the hook, the target `README.md` + `exploit/solve.py`, plus one line in the pack terminal
  Dockerfile. Live-verified end to end, both students, distinct flags, `dojo-flag submit` accept + cross-student
  reject — `docs/CTF-WORKSHOP-PLAN.md`'s checkpoint has the full detail. Concurrency is still capped (`RUNNER_MAX`,
  default `ceil(STUDENT_COUNT/3)`), so 40 students share about 14 runners; that class-size risk belongs in CTF-P4.
- `tfstate-treasure` (built 2026-10-06): the sketch above (a credential under the student's own `students/<user>`
  namespace) wasn't what got built, once it was clear the student already has `sudo` there by `vault-fundamentals`'
  `student` policy -- stashing the flag anywhere inside a namespace the student already administers isn't a
  challenge. Built instead with **no student/tenancy policy at all** in `ctf-defend-test` (first pack to add
  `openbao` to `MODULES` without also adding a `10-tenancy.sh`-style hook): a student's SSO/CLI OpenBao login gets
  zero capability, and the only way to `secret/data/tfstate-treasure/<user>` (root namespace) is an AppRole
  `role_id`/`secret_id` leaked via a committed `terraform.tfstate` in the student's own `<user>/infra-state`
  Forgejo repo (`workshops/ctf-defend-test/compose/terminal/start.d/95-tfstate-treasure.sh`, same curl+netrc idiom
  as `git-secrets`). The Vault side
  (`workshops/ctf-defend-test/compose/openbao-setup.d/{provisioner.hcl,60-tfstate-treasure.sh}`) writes the policy,
  role and flag with the provisioner token, same shape as `vault-fundamentals`'s `10-tenancy.sh`. Both hooks derive
  the flag and the role/secret id independently from `STUDENT_PASSWORD_SEED` (two copies, not shared code, same
  idiom as `git-secrets`'s `CTF_TARGET_TOKEN`) -- except `openbao-setup` runs in the openbao module's own Alpine
  image, confirmed to have **no python3 or openssl**, so that hook's HMAC-SHA256 is done by hand with
  `sha256sum`/`printf`/`od`, checked against RFC 4231's test vector and `flags.py`'s own output for a real seed
  before being trusted. Live-verified end to end, including that a student's own identity 403s on the flag path
  with no AppRole login, and that OpenBao's always-on file audit device (`modules/openbao/config.hcl`) records
  both the AppRole login and the secret read -- the debrief's "find the breach after the fact" claim, proven.

### S6, defend loop

Run 2026-10-04 (scratchpad, not kept). Constraint found while reading S14: with no host socket, "a student's
patched source reaches a running target" must go through the same controller, which then needs a **build**
capability (build the image from the student's pushed branch), the most dangerous call of all.

Built and ran the recommended direction with a stand-in registry on a local network (not the real `runner-pool`
pipeline or `ctf_ops`):

1. A CI step (standing in for the Forgejo job) builds "student source" and pushes it to the registry under an
   approved name:tag.
2. The controller's entire capability is pull-by-name, then stop/rm/run — no Dockerfile, no build context, no
   `docker.sock`, ever. This confirms the S14 finding that the controller itself stays unprivileged.
3. Recreating under the **same** slot name is what makes "patch stops the live bot" true: the bot's next probe
   hits the new container because the address/name didn't move, not because anything redirects it.
4. Pull + stop + rm + run measured about 10.5 s end to end against a cold local registry.

**Answer:** the direction holds; adopt it (no change to the recommendation). **Not measured (at the time):** the real
`runner-pool`/Forgejo registry path, and a warm-registry number — 10.5 s is a cold-registry upper bound, not a
real figure. This recreate time has to be shorter than the gap between two bot attempts (S9's dwell/retry
numbers), or a patch can land between attempts and still read as having missed the window; re-measure for real
before CTF-P6 and check it against whatever S9 settles on.

**Built (2026-10-05).** The build/push half above is no longer a stand-in: `modules/ctf-range/ctf-builder/` (stdlib
Python, same shape as `ctf-controller`) is the one thing allowed to ask `ctf-host` to build. It clones the student's
own repo itself (from `git-server`, never a tar/context handed to it by the caller), tars that clone, and
builds+pushes through `ctf-host`'s Engine API under one fixed tag — the slot's own name under the approved registry
prefix (`docker_build.image_tag_for`, mirroring `ctf-controller`'s `allowed_image`). `modules/ctf-range/compose.yml`
adds the in-lab `registry` (`registry:2`, pinned by digest, `ctf_ops`-only, no published port, no auth) and
`ctf-builder` itself (member of `runner_net` only — never `ctf_ops` — so only a Forgejo Actions job in the runner
pool can ever reach its `/build`; it shares `ctf-host`'s socket over the same volume `ctf-controller` already
uses, group_add, not network). `ctf-controller` is now additionally on `runner_net` so `defend-main.yml` can POST
`/redeploy` to it directly too — widening reachability only, since every mutating route still fails closed on its
own control-token check regardless of which network the call arrives on, and `ctf-builder` holds a **separate**
token (`CTF_BUILD_TOKEN` ≠ `CTF_CONTROL_TOKEN`). `defend-main.yml` now makes both real calls instead of the old
commented-out buildah/curl lines (see modules/ctf-range/README.md's "Range control plane" for the full design
writeup, including why a separate `ctf-builder` was chosen over a second network interface on `ctf-host` itself).
26 new unit tests (`ctf-builder/tests/`): pure argv/tagging/stream-parsing functions, auth rejection, bad-ref/bad-user
rejection (git option-injection patterns like `--upload-pack=...` are refused before any subprocess runs), and an
oversized request body — plus the existing 30 `ctf-controller` tests still pass unchanged.

**Run A (2026-10-05, live, kept only as this note).** Brought up `ctf-host` + the in-lab `registry` + `ctf-builder`
in isolation (a throwaway compose file in scratchpad, not the real `ctf_ops`/`runner_net`, and not through
`git-server` — no Forgejo in this isolated check) and drove `ctf-builder`'s own `docker_build.Executor` directly
(standing in for its `/build` handler, which only adds the clone step): built a trivial one-layer image
(`FROM scratch` + one file) via `ctf-host`'s Engine API `/build`, pushed it to the registry as
`registry:5000/ctf-customer-portal:student01` — exactly the tag `ctf-controller`'s `allowed_image` accepts — then,
from `ctf-host`'s own dockerd (the same client `ctf-controller.pull()` drives), deleted the local copy and pulled
the tag back from the registry and confirmed the file inside matched. This is the missing proof: build → push →
pull round-trips through the in-lab registry with **no `docker.sock` ever handed to a caller** — `ctf-builder`'s
only reach is the Engine API, same shape as `ctf-controller`'s. Timed (trivial image, not the real app, so this is
a mechanism/overhead floor, not the real build time): build 3.95 s + push 2.60 s ≈ 6.55 s, then a pull of that same
(already-local-layer) tag back at 0.97 s. **Not tested live:** `ctf-builder` cloning a real student repo from a real
`git-server` (no Forgejo instance stood up for this check — `gitref.py`'s argv/validation are unit-tested, but the
actual `git clone`/`checkout` subprocess calls against Forgejo are not), the real `customer-portal` app image's
build time (bigger than the trivial test image — a Python base plus `pip install`), and the two services' real
network placement (`runner_net`/dual-homed `ctf-controller`) — this check used a single flat test network instead,
since no `runner-pool` module/workshop exists yet to test against. `podman-compose -f modules/ctf-range/compose.yml
config` (run from `engine/`) was also checked: it renders with no structural errors, `ctf-builder` on `runner_net`
only, `ctf-controller` on both `ctf_ops` and `runner_net`, and all new volumes/services present.

**Run B (2026-10-05, live, on the real stack).** Built `workshops/ctf-defend-test/` — a new, minimal, uncommitted,
facilitator-only harness pack (`MODULES="ctf-range runner-pool"`, `STUDENT_COUNT=2`; explicitly not a real lesson,
not the CTF-5 pack) to run the actual S6 loop through the real `./run.sh`, `runner_net` and a real seeded Forgejo
repo per student, instead of the isolated check in Run A. `--dry-run` passed; the stack came up with both slots
reconciled and the pre-patch SQLi exploit dumping real rows against a live slot through `ctf-host`. The real PR-gate
half of the loop is now proven, not stubbed: cloned a student's seeded repo, applied the real parameterized-query
fix, pushed, opened a PR via Forgejo's API, `defend-pr.yml`'s gate re-ran the exploit and went **green in 6 s**,
merged. The merge → rebuild half then hit a real blocker (next paragraph), so no end-to-end build-time number came
out of Run B. Two small real bugs found and fixed live (not stubs, not hypothetical): `ctf-builder/gitref.py`'s
`checkout_argv()` put the ref after `--`, so git read every real commit as a pathspec and failed on all of them
(fixed: ref before `--`, matching unit test corrected, 26/26 still pass); `runner-pool/pool/Dockerfile` was missing
`py3-flask`, which `defend-pr.yml`'s own comment already said the image needed to run the app for the exploit
re-run. Also found: each student needs their **own** `<student>/customer-portal` repo, not the shared
`FORGEJO_ORG`/`FORGEJO_REPO`, because `defend-main.yml` keys the slot off `github.repository_owner` — provisioned
via a new `start.d` hook in the test pack (per-student repo creation, Actions secrets, and the `CTF_FLAG` secret
computed to match `ctf-controller`'s own HMAC exactly, verified against the live controller's rendered value).

**The merge→rebuild blocker Run B exposed:** `ctf-host`'s `import_target()` only ever `docker import`s a flattened,
single-layer snapshot of the pre-built target as `ctf-customer-portal:base` — it never loads the actual upstream
base image (`python:3.12-slim@sha256:0210...`) into the inner dockerd. So `ctf-builder`'s real `docker build` of the
patched source (Engine API, `pull=0` — CTF-D24's offline posture) can't resolve its own `FROM` line, and fails with
`dial tcp ... no such host`. Not fixable as a one-line patch without either breaking the offline posture or adding
real base-image-seeding — scoped as a redesign rather than patched in place.

**Run C (2026-10-05, live, the base-image fix).** Fixed by fetching the base image at `ctf-host`'s own image BUILD
time (network available then, same as the target's own `pip install`) and loading it into the inner dockerd at
container start — never at lab runtime (`modules/ctf-range/ctf-host/Dockerfile`, `entrypoint.sh`). **A real gotcha,
verified live, not assumed:** a plain `docker-archive` + `docker image load` does NOT satisfy a `FROM
image@sha256:<digest>` pin when that digest is a multi-arch index digest (the normal case for a Hub pin) —
`docker-archive` flattens to one platform, producing a different content digest; `docker tag`/`ctr images tag`
aliasing can't fake a sha256 match either. Fix: `skopeo copy --multi-arch all docker://... oci-archive:...` with an
explicit destination name, so `docker image load` registers it at the real index digest. Verified inside `ctf-host`:
`docker image inspect python:3.12-slim@sha256:0210...` resolves to that exact Id, and a real `docker build
--network=none` with that `FROM` line succeeds with zero network calls. **Trade-off found, not yet fixed:** fetching
all 16 platform variants costs ~370 MB at build time (fine) but makes `docker image load` take **~3 min at every
`ctf-host` container start** (confirmed: ~1 min before this fix, ~3:02 after) — a real lab-startup-time regression;
trimming to the index + amd64-only variant is the obvious follow-up, not done yet.

With that fix, Run C's rebuild got past the original `FROM`-resolution failure entirely (confirmed in the build log:
no more "no such host" for the base image) — then hit a **second, different, pre-existing** offline-posture gap one
step later: `pip install -r requirements.txt` inside the rebuild has no route to PyPI either (`ctf_ops` is
`internal: true`, by design), so the app's own dependencies (Flask, etc.) can't be fetched during a rebuild. Stopped
here rather than attempting a second redesign in the same pass, per this session's own token-budget rule. **Still
no real end-to-end build+push+redeploy wall-clock number** — the thing S6 has needed since 2026-10-04 — because the
rebuild still doesn't complete.

**Scoped (2026-10-05, design): the pip-install-offline fix.** Same family as the base-image fix — fetch at
`ctf-host`'s own image build time (network available then), load it into the inner dockerd at container start,
resolve offline at rebuild time. Two shapes considered:

- *A build-time-only package mirror* (devpi/pypiserver as a new always-on service on `ctf_ops`). Rejected: a new
  service, a new thing to pin/patch/monitor, and network surface to justify under CTF-D24 — bought for a capability
  (students pulling arbitrary new packages mid-challenge) this target doesn't need. `requirements.txt` isn't part of
  the SQLi fix; students edit `app.py`'s query logic, not their dependency list.
- *Vendor the deps into a custom locally-tagged base image* (chosen, built). A new `portal-deps` stage in
  `ctf-host/Dockerfile` (`FROM python:3.12-slim@<digest>` → `COPY requirements.txt` → `pip install`), its rootfs
  `docker import`-ed into a local tag at container start (`entrypoint.sh`'s `import_portal_deps_base()`, same
  mechanism as the existing `import_target()` — no skopeo needed here, since this is a locally-built image, not a
  Hub pull, so there's no multi-arch index digest to match). `targets/customer-portal/Dockerfile`'s `FROM` now
  points at that baked tag instead of installing Flask itself.

**Run D (2026-10-05, live, built and verified end to end).** Built as scoped above, with one real naming wrinkle not
in the design: the tag needed a `gitopsdojo/` prefix (`gitopsdojo/ctf-customer-portal-base:pinned`) so
`engine/scripts/check-pins.sh` (which exempts this project's own images) doesn't flag it as an unpinned external
image. **DESIGN CHANGE FROM BRIEF, found live:** `modules/ctf-range/compose.yml` also has a standalone dev-convenience
`customer-portal` service that builds the same Dockerfile directly on the *outer* host engine (real network, no
access to the tag that only ever exists inside `ctf-host`'s *inner*, offline dockerd) — this broke `./run.sh` outright
(`short-name ... did not resolve`). Fixed with the project's existing `ARG BASE=... / FROM ${BASE}` convention: a
`deps` stage mirroring `portal-deps` was added directly to `targets/customer-portal/Dockerfile`, defaulted to the
real local tag via `ARG BASE`, with the dev-path compose service overriding `args: [BASE=deps]` — the default
(offline, in-lab) path never builds that stage, so it costs nothing there.

Verified live, not just reasoned about: `check-pins.sh` passes; the full `workshops/ctf-defend-test/` stack started
clean; `docker image ls` inside `ctf-host`'s inner dockerd showed the new tag with Flask 3.0.3 actually importable
inside it; a real student (`student01`, real Forgejo account, real git push) patched the SQLi, and Forgejo Actions'
`defend-main.yml` ran `ctf-builder`'s build+push and `ctf-controller`'s redeploy for real — **past the `pip install`
step that failed in Run C** — confirmed functionally by curling the redeployed slot (SQLi payload now returns
`{"results":[]}`) against the still-vulnerable control slot (`student02`, unpatched, still leaks rows). Stack
stopped afterward, nothing committed.

**The real number, finally (S6 has needed this since 2026-10-04): 83 seconds**, push to redeploy-done, from
Forgejo's own run timestamps (`14:56:15` → `14:57:38`) — build+push took 73s of that, redeploy the remaining 9s.

One design trade-off still worth naming: `requirements.txt` changing would require a new `portal-deps`/`deps` image
rebuild of `ctf-host` itself, same as any other base-image bump — fine for this target, a real constraint if a
future target wants students adding dependencies as their fix.

**Run E (2026-10-05, live, both follow-ups from Run D closed).**

- *Start-order race, fixed inline (no live-stack re-run needed — compose-only change).* `ctf-host`'s healthcheck
  now checks for both baked images (`ctf-customer-portal:base` AND `gitopsdojo/ctf-customer-portal-base:pinned`,
  Run D's), and `ctf-controller`/`ctf-builder` now `depends_on: ctf-host: condition: service_healthy` instead of
  `service_started`. Closes the window where a build request could reach `ctf-builder` before `ctf-host` finished
  importing either image.
- *The ~3-minute startup regression, fixed and live-verified.* `base-image-fetch`'s single `skopeo copy --multi-arch
  all` (all 16 platforms, needed only to preserve the exact index digest) is replaced with a hand-merged OCI layout:
  `skopeo copy --multi-arch index-only` (the real multi-arch `index.json`, unmodified bytes, so the digest is
  untouched) merged with `skopeo copy --multi-arch system` (amd64-only manifest + blobs) — same index, same digest,
  but blob data for only the one platform that ever actually gets loaded. **Verified live, not assumed:** rebuilt
  the real `base-image-fetch` stage (not a standalone replica) with `podman build --target base-image-fetch`,
  extracted its output tar, loaded it into a scratch `docker:29.8.1-dind` container (same engine version as the
  real stage) — `docker image inspect python:3.12-slim` reports the exact original index digest
  (`sha256:02108f5d...`) unchanged, and `docker build --network=none` with that `FROM` pin still resolves with zero
  network calls, same correctness bar Run C used. Real measured numbers (this standalone dind, not the full
  compose stack — nothing about the load mechanism differs, so this is the real cost): archive size 384MB → 46MB;
  `docker image load` wall-clock ~58s → ~6–17s. The full `workshops/ctf-defend-test/` stack wasn't re-run end to end
  after this change (not needed — `entrypoint.sh`'s load step and the tar's path/format are unchanged; only the
  stage that produces the tar's *contents* changed, and that was verified directly).

**One caveat carried forward, not widened in scope:** the index digest `sha256:02108f5d...` now appears four times
by hand in `ctf-host/Dockerfile` (two `FROM` lines, two `skopeo copy` invocations) plus once in
`targets/customer-portal/Dockerfile` — the same manual-sync risk the file's own comment already flags for RV25's
`check-tool-pins.sh`; still not wired in, still a known follow-up, not this run's job.

With Run E, S6 has no known open items: PR gate proven (Run B), both offline-rebuild blockers fixed (Runs C/D), and
both optimization follow-ups closed (Run E).

### S7, the old SQLi box

Built and ran it in `scratchpad/s7`, as written, then hardened:

1. `docker-php-ext-install sqlite3` **fails** the build (the official image already bundles `sqlite3`, `pdo_sqlite`;
   confirmed with `php -m`). Delete the whole `RUN apt-get ...` step; nothing else needs installing.
2. The `/var/lib/lists` typo is real (`/var/lib/apt/lists`), moot once step 1 is deleted.
3. Hardened run works: `--read-only --cap-drop ALL --no-new-privileges --pids-limit 100 --memory 128m`, `tmpfs` on
   `/var/run/apache2`, `/var/lock/apache2`, `/var/log/apache2` (and `/tmp`), `USER www-data`, and Apache moved to
   port 8081 (it cannot bind 80 without `NET_BIND_SERVICE`; with `cap_drop ALL` and root it also fails with `AH00072`).
   Root Apache would additionally need `SETUID`/`SETGID`, so run as `www-data`.
4. `flag.txt` at `640 root:www-data` is readable by the Apache worker; the SQLi (`admin'--`) returned the flag.
5. Idle memory was 12.75 MB. Per-student flags: the read-only root means the flag must arrive by env or a tmpfs file
   written at start, not baked into the image. Not yet built.

### S8, the new targets

**Defend-set split (from section 8's session table).** Of the original seven new targets, only **9 `policy-bypass`**
is in the CTF-5 defend set; 2, 3, 6, 7, 12, 13 are attack-only, so only 9 needs a student-patchable source tree
(and it's Rego on the existing policy engine, not app code). An **eighth new target, 14 `customer-portal`**, is
added as CTF-5's dedicated **app-code** defend target (CTF-D25).

Suggested minimal builds, unproven unless noted:

- **2 `weak-auth-portal`, 7 `ssrf-fetcher`, 12 `api-mass-assignment`, 13 `api-bfla`:** plain Flask. Target 13's safe
  proof is a `HEAD`/`OPTIONS` on the destructive route that returns 200 vs 403 without running it.
- **3 `cert-trust-bypass`:** a small nginx/openssl front that accepts a cert it should reject.
- **9 `policy-bypass`:** Rego on the existing policy engine; dual-use (attacked in CTF-4, defended in CTF-5), with a
  default-allow fallthrough that still passes `opa test`. **Built 2026-10-06, attack side only** (CTF-5's defend
  wiring is separate, future work). The "existing policy engine" turned out to be `policy_engine.py` in
  `modules/dojo-cloud/cloud-api/` — a real, stdlib-only, data-driven rule evaluator, not JSON/Rego but structurally
  the same Azure-Policy-like grammar (`if`/`allOf`/`not`, deny/audit effects). Vendored it **verbatim** into
  `modules/ctf-range/targets/policy-bypass/` rather than reimplementing it independently, since it's deterministic
  logic, not a secret — the two-copies idiom every flag/token derivation elsewhere in this range uses exists to
  catch secret drift, which doesn't apply here. The "logic gap" built: the deny policy on a protected resource
  group checks `tags['provisioned-by']` on the WRITE REQUEST ITSELF, not anything about the caller — so a student
  self-reports that tag and the deny never fires. No `opa test`-style fallthrough was needed; the self-reported-tag
  mistake alone was enough and is a cleaner single idea for a lab debrief. Live-verified end to end (gateway →
  firewall → `ctf-host`, both students, isolation, decoy port, flag submission) — see `CTF-WORKSHOP-PLAN.md`'s
  checkpoint for the full detail.
- **6 `dns-resolver-cve`:** CVE chosen — **uClibc / uClibc-ng ≤ 1.0.40, CVE-2022-30295** (predictable DNS
  transaction IDs), after two earlier picks were rejected. First was the 2017 dnsmasq heap overflow
  (CVE-2017-14491): a 2-byte overflow → reliable RCE is fragile and breaks on any libc/heap/base-image change —
  wrong for a lab rebuilt for years. Second was the Dnspooq cache-poisoning set (dnsmasq < 2.83,
  CVE-2020-25684/25685/25686): built and measured, but it reduces to **guess-and-retry** (off-path poisoning is a
  TXID brute-force by nature), which is not "stable," and it needed a withholding-upstream contrivance to remove the
  race. CVE-2022-30295 removes the guess at the source: uClibc's stub resolver assigns **monotonically increasing
  TXIDs** and uses a **static source port 53**, defeating both randomizations, so an off-path attacker who sees one
  lookup can **predict** the next TXID and land a *single* spoofed reply. Why it fits the target-6 criteria:
    - *Deterministic, not a retry loop.* Predict the next TXID (the counter is monotonic), spoof one reply from the
      nameserver's IP:53 to the agent's port 53 — it is accepted. No brute force, no race-removal contrivance. This
      is the "more stable than guess-and-retry" the design called for.
    - *Rootless — verified (2026-10-04, see "Target 6 DNS poisoning build").* The one open risk was whether an
      off-path attacker can put a spoofed-source frame on the bridge under **rootless** Podman (the range's runtime,
      CTF-D21). Tested on a rootless netavark bridge: a container with only `--cap-add NET_RAW` emitted frames with a
      forged source IP and a sibling received them with that source intact. So the spoofing the attack needs works
      rootless; no rootful path required.
    - *Buildable from source, pin-and-bump fix.* uClibc-ng builds from source; the target's internal agent is linked
      against a pinned ≤ 1.0.40 and the fix is bumping uClibc-ng past 1.0.40 — the "update the pin, don't just set
      one" lesson for `dns-as-code`. Preserves A06 (real CVE in an outdated component) and the DNS theme: the
      *resolver* here is the libc stub the app trusts.
    - *The foothold chain (the trusted internal service).* Target 6 runs, in its one container, a small **internal
      agent** (linked against vulnerable uClibc-ng) that every few seconds resolves `vault.svc.internal` and checks
      in to it, sending a service token (an `Authorization` header / JSON credential). The attacker predicts the
      TXID and spoofs the answer → the agent connects to the attacker and hands over the token = **flag 1** (the
      captured token, or a flag embedded in the check-in). The attacker replays the token against the real internal
      endpoint (`/admin`/`/secret`) = **flag 2** on the same host. A stub resolver doesn't cache, so this is
      per-lookup answer spoofing — but each lookup is deterministically winnable, so the next agent cycle delivers.
      Lesson: a service that trusts DNS to find its backend hands its credentials to whoever controls resolution.
    - *Containable.* The vulnerable component only mis-resolves names the attacker forges from inside the range;
      drifting onto a shared network would not make it attack anything outbound.
    - *Build feasibility confirmed (2026-10-04, see "Run C" below).* A pinned prebuilt Bootlin uClibc-ng toolchain
      (uClibc-ng 1.0.39, in the vulnerable range) compiled a static agent that resolves through the uClibc stub, so
      the build is cheap (pin a tarball, compile static) — not a from-scratch buildroot. Left for CTF-P5: confirm
      the stub's monotonic TXID is predictable end-to-end, and wire the agent check-in → flag-1 → flag-2 chain.
- **14 `customer-portal` (NEW, CTF-5 defend-only, decided SQLite — CTF-D25):** a small Python/Flask app over a
  **plaintext SQLite** file (one container per slot, no sidecar DB — cheapest and consistent with one-target-per-slot).
  The DB seeds a `customers` table of synthetic rows referencing the student's handle plus a secret row = the flag.
  Vuln: SQL injection in a login/search field; the exploit dumps the table ("data stolen") and posts the rows to the
  wall of shame (8.12). Fix: parameterize the query. Gate (CTF-D19): the exploit re-run dumps nothing →
  green. Deploy: merge to main asks `ctf-builder` to build+push and `ctf-controller` to recreate the slot in place
  (S6, now built end-to-end: see S6's 2026-10-05 note). SAST (this fixes S17's app-side tool): a pinned, no-network
  Python SAST for CWE-89, informational only (CTF-D23/D24). Still open: running the full PR → scan → merge → redeploy
  loop against a real `runner-pool` and a real `git-server` clone (this was proven with a trivial stand-in build and
  a direct, non-cloned context — see S6), and the real app image's build time (bigger than the trivial test image).

### Target 6 DNS poisoning build (2026-10-04)

Two runs. Run A (rootful) explored dnsmasq cache poisoning and proved the forge mechanism; it exposed that off-path
poisoning is guess-and-retry, so target 6 was **re-chosen** to CVE-2022-30295 (uClibc predictable TXID) for
determinism. Run B (rootless) verified the one open risk of that choice — spoofing under the range's actual runtime.

**Run B — rootless spoofing (the deciding test).** On a **rootless** netavark bridge (`core` user, Podman 5.8.1,
`rootless=true`), an attacker container with only `--cap-add NET_RAW` sent `AF_PACKET` frames carrying a forged
source IP; a sibling listener received them reporting that forged source (`RECV src=10.99.9.10` while the attacker's
real IP was `10.99.9.30`). **So off-path source spoofing works rootless — no rootful path needed**, which is what
makes the predictable-TXID attack viable as the range runs it. Torn down after.

**Run A — dnsmasq PoC (rootful; kept as mechanism evidence).** Three containers (victim resolver, controlled
upstream, off-path attacker on one `/24`), scratchpad only. Proven:
- **dnsmasq 2.82 builds from source** in Alpine with just `gcc`/`make` (`curl` the 2.82 tarball, `make`, copy the
  binary); no awkward deps. Confirms the "build from source, pin, bump to fix" shape.
- **Fixed source port.** `--query-port=35353` made every forwarded query leave from `:35353`; the upstream logged
  it. So the off-path attacker knows the port — no port entropy.
- **No race.** With the upstream withholding answers, lookups for `svc.internal` just time out — nothing competes
  with a forged reply.
- **Off-path spoofing traverses the bridge.** The attacker container (CAP_NET_RAW), via both scapy and an
  `AF_PACKET` raw sender, emitted UDP frames with `src=`the upstream's IP; a listener on the victim received them
  with that spoofed source intact. netavark's default bridge does **not** anti-spoof.
- **Acceptance + cache + persistence.** A spoofed reply from the upstream IP to `:35353` whose DNS id matched the
  pending query's TXID was accepted by dnsmasq 2.82, cached with the attacker's TTL (86400), and every later lookup
  returned the attacker's IP. dnsmasq logged `reply svc.internal is <attacker>`.

**Why this forced the re-choice.** In Run A, flooding the *correct* (known) TXID poisoned every time, but a *blind*
full-16-bit sweep did **not** reliably land — non-matching replies from the expected server+port appear to disturb
the pending forward. So Dnspooq off-path poisoning is **guess-and-retry per query** (the birthday approach), which is
reliable-ish but not "stable," and it leaned on a withholding-upstream contrivance to remove the race. That is why
target 6 moved to **CVE-2022-30295**: uClibc's monotonic TXID + static source port 53 let the attacker *predict*
the id and land one spoofed reply — deterministic, and (per Run B) rootless. Run A still stands as proof that a
spoofed reply with the matching TXID from the expected source is accepted and used, which is the same acceptance the
uClibc attack relies on.

**Run C — uClibc build feasibility (2026-10-04, rootless).** The one worry about the CVE-2022-30295 choice was build
cost (linking an agent against an old uClibc normally implies a buildroot/OpenWRT toolchain). Resolved: **Bootlin
ships pinned, prebuilt uClibc-ng cross-toolchains** as single tarballs. Used `x86-64--uclibc--stable-2021.11-5`
(117 MB, one download + `tar xj`), whose `summary.csv` confirms **uClibc-ng 1.0.39** — within the vulnerable
≤ 1.0.40 range (fixed in 1.0.41). Its gcc compiled a small `getaddrinfo` agent **statically**, and the resulting
x86-64 binary resolved names through the uClibc stub (`example.com → 172.66.147.243`, `one.one.one.one → 1.0.0.1`).
So the build is cheap and low-maintenance: pin the toolchain tarball URL + sha256, compile the agent static, done —
no from-scratch buildroot, and a static binary is stable across base-image bumps. (The toolchains are x86-64-hosted,
which matches the x86-64 deployment target; the aarch64 dev machine just builds inside an x86-64 container.)

**Run D — TXID empirical check + target build (2026-10-06, settled).** The last open item from Run C — "confirm
the 1.0.39 stub emits a predictable monotonic TXID end-to-end" — ran: a tiny static agent cross-compiled by the
pinned Bootlin `x86-64--uclibc--stable-2021.11-5` toolchain made 20 consecutive `getaddrinfo` calls against a
Python UDP logger on 127.0.0.1:53 (rootless Podman, `--dns=127.0.0.1`). Observed TXIDs: **2, 3, 4, 5, …, 21** —
strictly +1 each query. CVE confirmed empirically. Source ports were **kernel-ephemeral** (33837, 50108, 41837,
44112, 50559, 52063, 55632, 43701, 33631, 37390, …), **not** static :53 as the earlier plan draft and some
writeups claimed — only the TXID is predictable in 1.0.39 built this way; `target 6 README.md` and the lab's
own `/observations` endpoint carry that correction honestly. For an off-path attacker in the real world this means
the attack is not single-packet-deterministic as the plan supposed; the lab is modelled on in-container loopback
(see below), where the DNS answerer, agent and spoofer share one address space, so the port correction doesn't
change what the student sees — just what the write-up claims it would do over a real bridge.

With that settled, **target 6 is now built** (end to end, cold-stack live-verified 2026-10-06, same session). The
image is a `python:3.12-slim` runtime (Flask + the static uClibc agent + an in-process UDP DNS answerer on
127.0.0.1:5353 + a "real vault" TCP receiver on 127.0.0.1:9000 + an "attacker's receiver" on 127.0.0.2:9000 + the
standard decoy :2222), baked into `ctf-host` as a new build stage pair (`dns-resolver-cve-agent-build` and
`dns-resolver-cve`) and imported as `ctf-dns-resolver-cve:base`. The uClibc stub cannot bind the privileged :53
under this range's `CapDrop ALL` + non-root + `ReadonlyRootfs`, so the agent sets `_res.nsaddr_list[0]` to
`127.0.0.1:5353` after `res_init()` — bypassing `/etc/resolv.conf` and letting an unprivileged answerer serve the
query without weakening `ctf-controller/docker_api.py`'s central hardening for one target. The exfil/replay chain
runs as spec'd: observe TXID via `/observations`, predict `last+1`, arm `/spoof`, agent's next cycle lands at the
attacker's receiver (which captures the carried `CTF_TARGET_TOKEN` = flag 1), replay the token at `/admin` for
flag 2 (`CTF_FLAG`). Both flags HMAC-derived per student, both accepted by `dojo-flag submit`, cross-student
submissions correctly rejected. 58 engine + 54 controller tests pass unchanged.

**One deliberate deviation from the plan draft.** The plan imagined a cross-slot off-path attacker observing a
sibling's lookup across `ctf_net`. The range's inner dockerd runs with `--icc=false` and a DOCKER-USER drop on
NEW outbound (`ctf-host/entrypoint.sh`) — a slot cannot reach another slot across the inner bridge at all, so a
cross-slot off-path attack is architecturally impossible here. The CVE itself (predictable TXID, kernel-ephemeral
source port) stays real and observable; the mechanical staging is in-process on loopback inside the one slot
container. The teaching holds: a service that trusts DNS to find its backend hands its credentials to whoever
controls resolution; the fix is to update the resolver pin past uClibc-ng 1.0.41, not merely to pin one. Target
README.md and `app.py`'s module docstring both state this topology trade honestly.

Not covered yet: Docker as a runtime (the range targets rootless Podman).

### S9, persona swarm numbers

Proposals only (nothing here has been run): 5 personas fixed per student, per-persona delay 30-180 s, dwell 8 minutes
at base delay before any ramp (D18), and the bot stops at the wall-clock end with the debrief showing any breach still
open (so an unfinished fix is part of the lesson). Bot isolation is the S12 answer. These need one real class
(CTF-P7) to tune, so S9 stays open.

**Built as these defaults (2026-10-05):** `modules/ctf-range/attacker-bot/personas.py` -
`default_personas()` gives 5 (one `benign`, §8.6, the rest round-robin across the real styles),
`DELAY_MIN/MAX` 30/180s, `DWELL_SECONDS` 8 min, `RAMP_WINDOW` 10 min, `RAMP_FLOOR` 7.5s (CTF-D18's
pacing line). 20 unit tests against a fake clock/rng; the numbers themselves are still untuned
by a real class, so S9 stays open in that sense - this just records where the knobs live.

### S10, live SOC feed

Poll. Every existing live UI in the engine does: `achievements` board, widget and admin poll every 5 s, its toast every
4 s, the Runners panel every 2.5 s. A 4-5 s poll gives "new alert within a few seconds" with nothing new to build.

**Built (2026-10-05):** `modules/ctf-range/soc-feed/feed.py` polls every 4s (`POLL_SECONDS`) -
the achievements-side pages poll on the same cadence family (student card 4s, admin tab 4s).
soc-feed itself reads each bot's full stdout log each pass rather than tracking a byte offset
(simple and exactly correct at a session's log volume - a few hundred short lines per bot).

### S11, the cyber map

`widgets` entries are same-origin pages framed at the top of each **student's** landing page, with a size of small,
medium or large. Technically a page can render persistently inside one, but a room-wide projector view is a facilitator
screen, so as D18 says: its own route (gate `facilitator`) plus an `/admin` tab with the same `id`. Fake-origin
weighting lives in the event payload from `soc-feed`, not in the page, so it can be tuned without a front-end change.

### S12, facilitator to bot channel

The terminal and the students sit on `ctf_net` and `workshop_lab`, so a bot cannot rely on either for secrecy. Use the
`runner-pool` shape: the controller (reachable only by the allocator or the facilitator-gated admin tab, checking
`X-Gateway-Token` and `X-Auth-User`) writes a small file into a named volume that only the bot mounts, and the bot
polls it (`runner-pool`'s controller drops configs in `/spool/start/`). No listener on the bot at all. This is infrequent
enough for a file. The bots themselves must not be on a network a student's rule permits; student `OUTPUT` rules drop
everything in the `ctf_net` subnet except the own target, which covers a bot placed there.

**The other direction (bot -> soc-feed) is built the mirror-image way (2026-10-05):** rather than
a bot writing to a spool file, soc-feed reads the bot's own container logs over the SAME shared
ctf-host socket ctf-controller/ctf-builder already use (a new read-only `docker_logs.Reader`,
list + logs only, never create/start/stop/remove) - no listener on the bot, no network the bot
needs to reach achievements directly, matching this spike's "no listener on the bot at all."
Still open: the facilitator-to-bot inject/hint-probe channel (§8.5) itself is not built yet.

### S13, the ramp and weighting functions

Scope per section 11: the ramp curve shape, the attention-split formula across up to four open targets, and the
cheap top-10-under-siege computation, plus the CPU-budget check for the proposed 5-10 s ramp floor.

**CPU budget: proven, synthetic (2026-10-04).** The real CTF workshop and its persona-swarm driver don't exist in the repo yet
(CTF-P4), so this couldn't be a `--test N` run against it — the engine's existing `--test` bots are the unrelated
git-fundamentals demo bots (CLAUDE.md: "bots only exercise git"). Stood in a throwaway driver instead (scratchpad,
not kept): 160 `asyncio` persona loops, each sleeping a random 5-10 s then issuing one HTTP GET, round-robined
across 10 lightweight target containers, run for 75 s inside the Podman VM (8 vCPU, matching `podman machine
inspect`).

- The driver itself (160 concurrent loops) cost 2.5-3.1% of **one** core throughout the run — the sleeping/scheduling
  overhead of 160 personas is negligible on any machine this workshop would run on.
- Each target container held steady at about 0.3% CPU and 11.8 MB RAM under its share of probe traffic (roughly
  2 req/s each, consistent with 16 personas/target at a 7.5 s average delay) — in line with S14's existing ~12.75 MB
  idle figure, so probing adds almost nothing on top.
- Extrapolated to 160 targets: about 0.3% x 160 ≈ 48% of one core and about 1.9 GB RAM for the targets, plus well
  under one core for the driver — comfortably inside an 8-vCPU budget with headroom for everything else running.
- Caveat: this used trivial Python HTTP targets, not the real CTF-4/5 app images, and a synthetic driver, not the
  real persona-swarm code (S9, still open and needs CTF-P7). The *rate* and *concurrency* shape is validated; the
  per-target cost will shift once real (heavier) target images replace this stand-in — re-check then, not before
  CTF-P6.

**Curve shape, attention-split formula, top-10 computation: still open.** These are design choices, not numbers that
need a live class — they can be settled on paper (or with the same synthetic harness) without CTF-P7.

### S14, student-controlled targets: the controller and its socket

**Do not build the label-restricted host-socket proxy.** Findings:

- Nothing in this repo mounts the host `docker.sock` (`engine/docker-compose.yml` says "no docker.sock"; `dojo-cloud`
  boxes a privileged Docker-in-Docker daemon on an internal network instead). A proxy would be the first such
  exposure, and the host socket is root on the host.
- Recreate means the **create** call, and a proxy cannot judge a create body by container label alone: a body with
  `Privileged` or a host bind mount would pass a label filter and give a controller compromise full host control.
  Filtering start/stop/restart by name is easy; filtering create safely means validating the body against an
  allow-list, which is bespoke security code.
- **Boxed `ctf-host` (recommended).** A privileged `docker:dind` container on an internal network, the controller its
  only client over a unix socket in a shared volume, exactly as `cloud-host`/`cloud-api`. Tested with
  `docker:29.8.1-dind`, `dockerd --icc=false`:
  - IP aliases on the host's `eth0` (one per slot), with inner targets published on that alias: a probe on the
    outer network reached each slot's service on its own address (TARGET-A, TARGET-B).
  - Reverse shell: a target reached a listener on the outer network (`REVSHELL-LISTENER`).
  - Lateral target to target: blocked under `--icc=false` (rc=1).
  - The inner bridge address was not routable from the outer network (rc=1).
  - Restart of a target took 261 ms and kept the slot address and port; so Reset is fast.
- **Source address (proven rootless, 2026-10-04).** Inner targets are masqueraded to the host's one address by
  default, which would break "`INPUT` only from target-NN". A per-target `iptables -t nat -I POSTROUTING -s <inner ip>
  -d <ctf_net> -j SNAT --to-source <slot ip>` inside `ctf-host` fixes it: counters on the terminal side showed 5
  packets from the host's address before the rule and 5 from the slot address after it. The inner address stays
  stable across a restart, so the rule can be written once per slot.

- **Not measured:** cold-start time at 40 students (needs the real CTF-4 images), queue concurrency of about 10, the
  idle timeout, and the worst-case wait when all 40 press Start. Only the trivial 261 ms restart exists.
- A nested Docker daemon also changes S1 for the better: the controller can `docker run` 160 containers from its own
  loop. CTF-5's 160 always-on targets need a memory figure for the nested daemon (it ran at 12.75 MB per Apache target
  plus the daemon itself; the daemon's own overhead was not measured).

**Built (2026-10-04).** `modules/ctf-range/ctf-host/` (the boxed dind, the `cloud-host` pattern: patched to drop the
tcp listener, `--icc=false`, DROP new outbound from slots, target image baked in and imported offline at start) and
`modules/ctf-range/ctf-controller/` (stdlib Python; `docker_api.Executor` is the whole reach into ctf-host — a
fixed-template create with read-only root, tmpfs-only writable paths, `CapDrop: ALL`, `no-new-privileges`, an image
allow-list, and never a build; `flags.py` renders the §5 per-slot flag with the seed kept controller-side;
`controller.py` reconciles one always-on slot per student and serves `GET /slots` + `POST /redeploy` behind a
control token). Wired into `compose.yml` on the internal `ctf_ops` network, controller `group_add`'d into the
socket group exactly as cloud-api is for cloud-host. 30 unit tests (`ctf-controller/tests/`). Verified live under
podman (`STUDENT_COUNT=2`): import → a hardened slot per student with its own flag → exploit dumps the flag from a
managed slot → `/redeploy` recreates the slot in place from a parameterized image in ~0.5 s (the stand-in for a
registry pull; still offline) → the same published port returns no flag (CTF-D19 green) while an un-redeployed slot
still leaks. **Still open:** the warm figures S14 already lists (cold-start at 40 students, queue concurrency, idle
timeout); the CTF-1 to CTF-4 start/stop toggle, queue and per-uid SNAT are a later step, not needed for CTF-5. The
registry/CI push half of S6 is no longer open — see S6's 2026-10-05 "Built" note below.

### S15, terminal footprint

- **Read (`engine/README.md`, Capacity):** code-server is spawned lazily on the first `/ide` visit and released on
  Release or after the idle timeout, at about 260 MB per student with a session open (about 200 MB of that is the
  extension host, pty host and language servers; the engine already trimmed it from about 480 MB). A student who never
  opens `/ide` should never pay for it.
- **Open:** whether anything else starts code-server eagerly; whether a pack can hide the VS Code tab (the workspace
  page is allocator-served, so possibly not without an engine change, which would be its own proposal); and how
  CTF-5 sizes for IDE use. Measure with `./run.sh capacity` and a `--test` bot when the stack is next up.

### S16, the CTF terminal workspace: first measurements

A throwaway bake-off on 2026-10-04 (rootless Podman, Debian bookworm, arm64; scripts not kept): 5 users each
running a file browser (`yazi` 26.9.1) and an editor (`micro` 2.0.11) in a 200x50 pty, sampled 75 s in with
simulated keystrokes. Per student:

| Setup | PSS | Anonymous (private) |
|---|---|---|
| tmux 3.3a + yazi + micro | 23 MB | 18 MB |
| tmux + Zellij 0.45.1, tab and status bars | 74 MB | 62 MB |
| tmux + Zellij, no bars (plain layout) | 65 MB | 53 MB |
| tmux + Zellij `no-web` build, bars | 76 MB | 65 MB |

- The tmux server is about 1 MB per student; `yazi` and `micro` are about 10 MB each.
- Zellij adds roughly 40-50 MB per student whatever the layout, and the `no-web` build saves nothing. That is over
  the 30 MB threshold agreed for choosing it. It is still about 3.5x lighter than code-server (260 MB); tmux is about
  11x lighter.
- `zellij web --start` is a separate process of about 4 MB per student. A non-loopback bind without a certificate is
  refused ("Cannot bind to non-loopback IP ... without an SSL certificate"). A read-only token is documented as able to
  "only attach to existing sessions as watcher", which would suit the facilitator tile. I created the token but did
  **not** get a watcher attach to show a screen in this harness, so that is **unconfirmed**.
- **Not measured:** a real ttyd client, hours of runtime (one report has Zellij growing over days), a second tab,
  the facilitator mirror, and x86_64. Downloads used (arm64): `zellij-aarch64-unknown-linux-musl.tar.gz` sha256
  `05f0802afadd53f8db9514e7cae53c9ae8432fed1b35b8294aa816ee3044a16b`, `yazi-aarch64-unknown-linux-musl.zip` sha256
  `dd569daecaae914185f295634109295ccd25c1b42b02eb89a74f651970024f2e`.
- **Built and run in the real engine (2026-10-04, git-fundamentals, `--test 3 --fast`):** the facilitator roster shows
  the three bots through `zellij watch` (no VS Code tab); a student's ttyd creates the `dojo` layout with the shell in
  `~/lab`; `/start/ide` answers 404. Two things the prototype hid: Zellij shows a **First Run Setup Wizard** over the
  layout unless `ZELLIJ_CONFIG_DIR=/etc/zellij` is set for every `su -` command (done through `/etc/zsh/zshenv`), and
  background sessions (`attach --create-background`) ignore the layout, so bots run Zellij inside a detached tmux pty.
  Not yet checked: a student reconnect while the tile is open, hours of runtime, and the browser keys.
  Follow-up the same day: the side pane changed from `yazi` (a three-column browser that needed `file`) to a read-only
  `dojo-sidebar` listing that follows the shell's directory through a zsh `chpwd` hook, and `file` is installed. A
  pty test showed that `su -c` starts the command in a new session, so later browser-window resizes never reach the
  program: Zellij stayed at its first size (99 columns after resizing to 160). `su --pty` relays them (169 columns), so
  the Zellij terminal and watch commands use it. The tmux flavor goes through the same plain `su -c` and shows the same
  stuck size in the same test; that flavor was left unchanged.
- **Provisional reading:** tmux with a friendly status line, mouse mode and a popup cheat sheet meets the efficiency
  goal. Zellij costs about three times as much and needs either nesting inside tmux (which keeps the existing
  `tmux attach -r` watch tiles) or an engine change to keep the facilitator view. Decide after the remaining checks
  in section 11.

### S17, a SAST/SCA scan step

Not run. User decision (2026-10-04): the scan is informational only, never a CI gate — only the exploit re-check
(S6) decides red/yellow/green (CTF-D19) — but its findings should surface as a pointer toward the flaw, the way a
real team's pipeline output would.

**Offline posture decided (CTF-D24, 2026-10-04).** Both tools are self-contained: baked into the `runner-pool`
runner image with a pinned ruleset/vulnerability-DB snapshot at build time, never fetched at run time — matching
the engine's "nothing reaches outward except `gateway`" network model and CTF-D16's pinned-version precedent. A
pull-through-proxy/mirror approach was considered and rejected: it adds a new always-on service for no real benefit
here, since the targets are a closed, deliberately-planted set of flaws, not a moving target. The goal is
recognizing *this lab's* known-embedded vulnerabilities (SQLi, hardcoded creds, intentionally outdated dependency
versions, etc.) with a frozen ruleset/DB chosen to cover them — not currency against newly-disclosed CVEs, which
this focused, disconnected instance has no need for and should not depend on.

**Built for target 14 (2026-10-04).** The app-side CWE-89 SAST is implemented as
`modules/ctf-range/targets/customer-portal/sast/scan.py`: pinned, stdlib-only `ast` analysis (the single
`DOJO-PY-SQLI` rule is the frozen ruleset), no network, informational (exits 0 even with findings; `--strict` for a
human spot-check). It flags `cursor.execute(<dynamic SQL>)` — resolving one level of `sql = ... ; execute(sql)`
indirection — and clears once the query is parameterized. Wired into the defend pipeline as the non-gating scan step
(`.forgejo/workflows/defend-pr.yml`); when `runner-pool` is wired it travels baked into the runner image (CTF-D24).

Still open: concrete tool choice for the **other-language / non-app scanners on targets 8-11** (a no-network SAST
whose default/OSS ruleset covers common injection/secrets patterns, e.g. Semgrep, plus an SCA tool that runs fully
offline against a vendored advisory DB, e.g. `grype`/`pip-audit` in offline mode, snapshotted once to cover the
specific outdated packages the lab deliberately ships); whether findings show unconditionally every run or sit
behind the two-hint ladder (section 9), given a scan finding is more specific than today's hints; where they render
(status strip versus SOC feed); and the smallest way to add the stage to `runner-pool`'s job.

### What this changes in the plan

1. Decided (CTF-D21): the boxed Docker-in-Docker `ctf-host` replaces the host-socket proxy; section 4 is updated.
   The S14 tests ran on rootful Podman, and **were repeated rootless with the same results** (see "Rootless re-run").
2. S1 is solved by the controller creating containers, so CTF-D15 (engine change) does not apply.
3. S6's direction is confirmed and now **built**: `ctf-builder` + the in-lab registry (registry-based
   rebuild/redeploy, no `docker.sock` ever handed to a caller), with the build→push→pull round trip verified live
   (2026-10-05, see S6). What remains is running it against the real `runner-pool` pipeline and a real `git-server`
   clone, and a warm-registry number for the real app image (not the trivial test image), needed before CTF-P6. The
   rootless re-run and SNAT are done (see "Rootless re-run").
4. S13's CPU-budget question is answered (synthetic swarm, well under an 8-vCPU budget); its curve-shape,
   attention-split and top-10 formula are open design choices, not blocked on a live class. Open until a live
   class: S9 and the cold-start/queue numbers in S14.
5. Target 14 `customer-portal` (CTF-D25) is **built**: the vulnerable app, seed, image, exploit/gate, the CWE-89
   SAST, and the defend pipeline (`.forgejo/workflows/`). The CTF-D19 gate (SAST + exploit re-run on PR) is wired
   and verified; the merge-side build→push→*live* redeploy is now also wired for real in `defend-main.yml`
   (`ctf-builder` + `ctf-controller`, S6) and build→push→pull was verified live against the boxed `ctf-host`
   (CTF-D21) and the in-lab registry; what remains for the **full** loop is running it against a real `git-server`
   clone and the real `runner-pool`.
   S8's `dns-resolver-cve` is now chosen (uClibc / uClibc-ng ≤ 1.0.40 / CVE-2022-30295, predictable TXID —
   deterministic; rootless spoofing verified and the uClibc build confirmed cheap via a pinned Bootlin toolchain; see "Target 6 DNS poisoning build"), leaving only an end-to-end TXID-predictability check and the internal-agent flag wiring at CTF-P5. S17's app-side tool
   is now **built** (`sast/scan.py`, a pinned, no-network Python SAST for CWE-89, by target 14); its remaining open
   piece is only the IaC/secret scanners for targets 8-11.

### Rootless re-run (2026-10-04)

Repeated S2, S3 and S14 as the unprivileged `core` user in the same machine: rootless Podman 5.8.1, netavark, own
storage (the rootful stack was untouched). Note the machine's Podman is 5.8.1 for `core` and 6.1.3 on the Mac client.

- **S2** (in-target firewall): identical. Terminal to target worked, sibling to target failed, caps all zero.
- **S3** (return path, owner and source rules): identical on every line; the mock terminal needs only `NET_ADMIN`.
- **S14** (boxed `ctf-host`): a **privileged `docker:dind` container works rootless** (overlayfs storage, up in about 1 s).
  Alias addresses, published ports on an alias, the reverse path, `--icc=false` lateral blocking, no route to the inner
  address, 187 ms restart that keeps slot address and port, and per-target SNAT all behaved as in the rootful run.
  This also settles the earlier SNAT question.
- **Still not covered:** Docker (as a runtime), the macOS-native rootless path (the check ran inside the Podman
  machine's Linux VM, which is how the Mac setup runs it anyway), the lateral test has no no-`icc=false` control
  (it was blocked, but I did not show it would pass without the flag), and the cold-start and queue numbers at 40.
- A leftover `localhost/s2base` image (alpine plus iptables) remains in `core`'s storage; harmless.

## Decisions so far

- **CTF-D1 (user, 2026-10-03):** Isolation is **N static targets, one per slot**, with per-uid firewall rules in the
  terminal; no `docker.sock`, no engine change.
- **CTF-D2 (user, 2026-10-03):** Flavor is **both, as a ladder**: classic boot2root warm-ups, then GitOps-flavored
  attack paths.
- **CTF-D3 (user, 2026-10-03):** Flags are validated through the **achievements module with per-student flags**. No
  CTFd.
- **CTF-D4 (user, 2026-10-03):** Scope is a **multi-session series**, not a single session. "Attack-Defend" is
  included as the final session (CTF-5).
- **CTF-D5:** The range is a **module** (`ctf-range`) and each session a thin workshop pack, per the repo rule that
  anything a second workshop would want becomes a module.
- **CTF-D6:** Targets are **original builds** inspired by the HTB techniques, not copies of HTB machines, and
  **Linux only**.
- **CTF-D7 (user, 2026-10-03):** The ladder is **not capped at ten**. It grew to fourteen targets so the OWASP Top
  10 (2021), the OWASP API Security Top 10 (2023), and every workshop with an attackable concept each get their
  own target instead of sharing one to hit a round number.
- **CTF-D8 (user, 2026-10-03):** CTF-5 (defend) gets a **live attacker bot per student plus a simulated SOC/SIEM
  alert feed, with the bot as 4-6 randomly-timed personas and a room-wide synthetic "cyber map" dashboard**
  (section 8.1-8.4), to create real-time pressure during the session instead of relying on the CI
  gate alone. The CI gate (pipeline rebuilds, re-runs the exploit, PR passes only if it now fails) stays as the
  actual proof that a fix works; the bot and feed are the pressure layered on top of it, not a replacement for it.
- **CTF-D9 (user, 2026-10-03):** CTF-5 additionally gets: a facilitator-fired **hint probe** (a short,
  non-exploiting burst at the vulnerable area, firing on one student, a group, or everyone at once, each with
  independent random timing so it reads as a wide sweep — section 8.5), a facilitator **inject** control for a
  real extra attempt, a **benign persona** for triage practice (8.6), an optional **second latent vulnerability**
  per target (8.7), a **mean-time-to-patch** figure shown with the map (8.8), and an **auto-built incident
  summary** for the debrief (8.9).
- **CTF-D10 (user, 2026-10-03):** Each CTF-5 target carries a **red/yellow/green status** (never breached, breached
  then fixed, breached and still open), one-way (green → red → yellow, never back to green), shown per student
  and room-wide, with **points attached to the status at session end** rather than only to whether the flag was
  ever recovered (section 8.10). This replaces the earlier "no points lost either way" framing in 8.4.
- **CTF-D11 (user, 2026-10-03):** CTF-5's traffic **ramps and pivots** (8.11): probe frequency and the
  probe-versus-real-exploit mix both climb the longer a target's been in its escalating phase, and the swarm's
  attention concentrates on whichever of the student's four targets is closest to exploitation, shifting away
  once a target resolves. The cyber map (8.3) gets a **"Top 10 under siege" list** of the hottest
  (student, target) pairs in the room right now, driven by the same heat calculation.
- **CTF-D12 (user, 2026-10-03):** Five sessions: CTF-1 access and identity (0, 2, 1, 3), CTF-2 server-side trust and
  APIs (4, 7, 12, 13), CTF-3 secrets and misconfiguration (5, 8, 11), CTF-4 trusting the wrong thing (6, 9, 10),
  CTF-5 defend (8-11, unsplit, needs CTF-3 and CTF-4 first). Packs: `ctf-access`, `ctf-server-trust`, `ctf-secrets`,
  `ctf-trust`, `ctf-defend`.
- **CTF-D13 (user, 2026-10-03):** The leaderboard is public in CTF-1 to CTF-4. In CTF-5 the "Top 10 under siege"
  list is anonymized ("target type + anonymous id").
- **CTF-D14 (user, 2026-10-03):** Design and test for about **40 students**. CTF-5 then needs 160 targets (four per
  student), which spike S2 must prove.
- **CTF-D15 (user, 2026-10-03):** If generating N targets needs an engine change (S1), it is proposed as a
  **separate change**, not designed around.
- **CTF-D16 (user, 2026-10-03):** Students need a Linux/`nmap` primer. A shared **Lab Info** library (section 9)
  ships in every pack: tool primers with neutral examples, no lab-specific payloads, identical across sessions so it
  can't hint at what a lab needs.
- **CTF-D17 (user, 2026-10-03):** Each defend target carries a **bonus second flaw** that bots probe but never
  exploit, scored separately and never affecting the status light (8.7).
- **CTF-D19 (user, 2026-10-03):** Defend scoring is **units**: green 2 / yellow 1 / red 0, bonus +1 (gated on the
  main fix), times one configurable multiplier into achievements points. This replaces the 10/5/0 and +3 guesses.
- **CTF-D18 (user, 2026-10-03):** Bot delay is held at a base value X until dwell ends, then shrinks as the target
  nears exploitation (8.11). Adopted defaults: no extra retry penalty; flatter
  region-level origin mix; one projector route for the cyber map; facilitator-only hint probes; linear 10 min ramp;
  top-10 always up to ten entries from hot pairs. Bot-pacing numbers still come from spike S9.
- **CTF-D20 (user, 2026-10-03):** In CTF-1 to CTF-4 the student controls their targets from landing-page cards: free
  order, **one live at a time**, Start/Stop, a per-target **Reset** to the starting state, and a flag box under
  each card. The card shows the slot IP only and never the ports, and targets may expose several ports (some
  decoys) so `nmap` is useful. CTF-5 is exempt (all four targets always live). Needs a `ctf-controller` (spike S14).

- **CTF-D21 (user, 2026-10-04):** The range runs its targets in a **boxed Docker-in-Docker `ctf-host`** driven by a
  `ctf-controller`, not behind a host-socket proxy. Rootless Podman is the preferred runtime, so nothing may need the
  host's container socket. Supersedes the socket-proxy wording in CTF-D20's implementation note (spike S14).

- **CTF-D22 (user, 2026-10-04):** No VPN or SSH access path: students stay in the browser. CTF packs get a
  **terminal-native workspace** from one shared terminal link: a file browser, an editor and a shell in one ttyd
  window, plus a status line (target, flags, hints), with every CTF tool installed once so it is not rebuilt per
  session. VS Code stays lazy and opt-in, and CTF-5 may still want it. The multiplexer (tmux or Zellij) is chosen by the
  S16 bake-off, with the facilitator's read-only view of each student kept either way, and resource footprint a
  first-order criterion (S15).

- **CTF-D23 (user, 2026-10-04):** CTF-5's pipeline (spike CTF-S6) gets a SAST/SCA scan stage. It is **informational,
  not a gate** — only the exploit re-check decides red/yellow/green (CTF-D19) — but its findings point the student
  toward the flaw, the way a real team's pipeline output would (spike CTF-S17).

- **CTF-D24 (user, 2026-10-04):** CTF-S17's SAST and SCA tools are **self-contained**: baked into the `runner-pool`
  runner image with a pinned ruleset/vulnerability-DB snapshot at build time, never reaching outward at run time
  (matching the engine's network model and CTF-D16's pinned-version precedent). They only need to catch this lab's
  own deliberately-planted flaws, not track newly-disclosed CVEs — this is a closed, disconnected instance, not a
  moving target, so DB currency is a non-goal.

- **CTF-D23 (user, 2026-10-04):** The students' terminal becomes a selectable **Zellij flavor**: `TERMINAL_FLAVOR=zellij`
  in `engine/.env` or a workshop's `workshop.env` (the latter wins) builds `gitopsdojo/zellij-terminal:base` on top of
  `web-terminal:base` and runs a Zellij session (a read-only listing of the shell's directory, the shell, editor `micro`) instead of VS Code and tmux,
  with `zellij watch` for the facilitator tile. One shared `workspace-control.py` with a flavor flag; labs reworded
  flavor-neutrally. This is the engine change CTF-D15 called for; it ships first for `git-fundamentals` (branch
  `feat/zellij-terminal`), and the CTF packs set the flavor in their own `workshop.env`.

- **CTF-D25 (user, 2026-10-04):** CTF-5 gains a dedicated **app-code** defend target, **14 `customer-portal`** — a
  Python/Flask app over a **plaintext SQLite** DB with a SQL injection that dumps a table of synthetic customer
  records referencing the student. It is the full GitOps payoff: fix the query, open a PR, the pipeline scans
  (CTF-D23/D24) and re-runs the exploit as the gate (CTF-D19), then **merging to main rebuilds the image and the
  controller redeploys it in place** (spike S6), replacing the running app. A successful dump is posted to a
  room-wide **wall of shame** on its own projector route (8.12, a sibling of the cyber map); each entry shows a
  **LIVE → DISCONNECTED** connection state that flips the moment the redeployed fix makes the next dump fail. The
  wall's wiring is built unconditionally, but its visibility in the lab is a per-pack toggle
  (`CTF_WALL_OF_SHAME=on|off` in `workshop.env`, default on for `ctf-defend`). Once the student
  patches and redeploys, the dump fails and their entry is marked contained. All records are synthetic, referencing
  only the in-lab student handle — no real PII, ever. Plaintext at rest is deliberate scenario design that makes the
  dump legible; the **graded fix is the SQL injection**, with cleartext storage available as a CTF-D17 bonus flaw.
  Decided SQLite (one container per slot, no sidecar DB). This target is defend-only — never attacked in an earlier
  session — so CTF-5's prerequisites are unchanged, and it fixes S17's app-side tool to a pinned, no-network Python
  SAST for CWE-89 (CTF-D24). It makes CTF-5 **five** always-live defend targets per student (200 at 40 students),
  which S2/S15 capacity must now size for.

- **CTF-D26 (user, 2026-10-05; built 2026-10-06):** `ctf-host`'s Dockerfile baked every attack-ladder target
  unconditionally into one shared image used by every workshop pack, regardless of which targets that pack's own
  `CTF_ATTACK_TARGETS` actually lists — a single-session pack paid the build time and the startup import cost for
  targets it would never expose. **Built as decided**: `ctf-host/Dockerfile` now has a shared `range-base` stage
  (dind + the dnsmasq/sed fixes + `entrypoint.sh`, nothing pack-specific) and three named final stages FROM it —
  `ctf-host` (the default, full catalog — what `workshop.env` defaults still build, so `workshops/ctf-defend-test`'s
  shared harness is unaffected), `ctf-host-ctf1` (CTF-1's 4 targets only) and `ctf-host-ctf2` (CTF-2's 4 targets
  only). `entrypoint.sh`'s `import_target`/`import_portal_deps_base`/`import_attack_target` each guard on their own
  rootfs directory existing (`[ -d "$rootfs" ] || return 0`) so a pack-scoped image's start never tries to import
  something it never baked in. `compose.yml`'s `ctf-host` service now takes its build `target`, its `image` tag,
  and its healthcheck's expected-image list from three new `module.env` vars (`CTF_HOST_BUILD_TARGET`,
  `CTF_HOST_IMAGE`, `CTF_HOST_EXPECTED_IMAGES`), defaulting to today's full-catalog behavior. **Live-verified**:
  `podman build --target ctf-host-ctf1`/`ctf-host-ctf2` each only build `range-base` plus their own 4 target
  stages (confirmed from the build log — `portal`/`portal-deps`/`base-image-fetch` and the other pack's stages
  never execute); full catalog = 1.89GB, each scoped image ≈ 900MB (roughly half, as expected with no
  customer-portal/ctf-builder plumbing and only 4 of 9 targets). All engine + ctf-range unit suites still pass, and
  a cold `./run.sh ctf-defend-test` start still imports and serves its full 9-target catalog (now including
  `leaky-config`, CTF-S8 below) with no regression. CTF-1/CTF-2 don't have real session packs yet (see the plan's
  checkpoint) — the mechanism is ready and proven; the next real pack just sets the three vars instead of building
  a one-off Dockerfile fork.
