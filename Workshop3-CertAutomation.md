# Workshop 3: Certificate Autorenewal Lab (`cert-autorenewal`)

## Why

Teams here manage certificates through Venafi. This workshop teaches the
underlying protocol and automation pattern Venafi (and every other
enterprise CA) sits on top of — ACME issuance, challenge/response,
short-lived certs, scheduled renewal, zero-downtime reload — using an
open-source, self-hosted stack with **no ties to any corporate service**.
The goal is that a team member who's done this lab understands *what
Venafi is automating for them* and could reason about or replace it with
open tooling if needed.

Staged delivery, per the existing workshop pattern: this document plans the
**lab/infrastructure** first. Slides (`content/slides/presentation.md`) get
built next, once this scaffold runs end-to-end. Hands-on student access
comes last.

## Research grounding (from this repo, not assumptions)

- **Per-student isolation precedent**: `engine/web-terminal/workspace-control.py:27-43,89-155`
  spawns one process per student *inside a single shared container*,
  distinguished only by Linux account + a formulaic port
  (`BASE_PORT + student_number`). There is no precedent anywhere in this
  repo for one backend instance per student.
- **`dns-as-code`'s isolation model** (`workshops/dns-as-code/`): a single
  shared PowerDNS instance; each student "owns" a DNS label in one shared
  zone file, enforced socially via git branch/PR, not infrastructure. This
  is the template this workshop follows for `demo-app` ownership.
- **Why per-student *services* aren't the answer here**: giving each
  student their own reachable backend would mean extending
  `engine/gateway/Caddyfile`'s `forward_auth` → `X-Upstream-Port` dynamic
  routing to a new service type — an `engine/` change. Both `CLAUDE.md` and
  `workshops/README.md` explicitly flag "workshop needs to touch `engine/`"
  as a signal to reconsider the design, since workshops are supposed to be
  addable without ever editing the shared runtime.
- **step-ca constraint**: unlike Pebble (the Let's Encrypt *test* ACME
  server, which supports overriding the http-01/tls-alpn-01 validation
  ports for exactly this kind of multi-tenant test scenario), Smallstep's
  `step-ca` validates `http-01` against the **standard port 80** on the
  target hostname with no override. Combined with the user's explicit
  choice of a **single shared step-ca** (more realistic "call a central
  CA" story, less overhead than per-student CAs), this means every
  student's challenge target must be independently *addressable* — by
  hostname, not by port — on a service `step-ca` can reach on port 80.
- **Workshops can't currently depend on each other**: `run.sh <name>` loads
  exactly one workshop's Compose overlay at a time. There's no mechanism for
  this workshop to reuse `dns-as-code`'s *running* PowerDNS container — so
  the `dns-01` capstone requires **bundling this workshop's own PowerDNS
  instance** (same image/pattern as `dns-as-code`, for skill continuity;
  a separate instance, not a shared one).

## Decisions made with the user

1. **Shared `step-ca`** for the whole class (not per-student CAs) — more
   production-realistic, lower overhead.
2. **Per-student isolation lives at the web-app/vhost level**, not the CA
   level: each student gets "their own" site on a shared `demo-app`
   container, addressed by their own hostname, config, docroot, and cert —
   structurally isolated (separate files, separate DNS name) even though
   the container and CA are shared.
3. **`dns-01` is an optional capstone lab**, validated against a PowerDNS
   instance bundled with *this* workshop (not literally shared with
   `dns-as-code`, since workshops don't run concurrently today).

## Architecture

### New shared services (`workshops/cert-autorenewal/compose/docker-compose.override.yml`)

Modeled directly on `workshops/dns-as-code/compose/docker-compose.override.yml`
(same top-of-file comment about Compose resolving every relative path from
`engine/docker-compose.yml`'s directory, not the overlay's own directory —
the documented gotcha in `workshops/README.md`).

- **`dns-server`** — PowerDNS, same image/config approach as `dns-as-code`.
  Serves a zone (e.g. `certs.dojo.test`) for two purposes:
  1. Resolving `studentNN.certs.dojo.test` → the `demo-app` container, so
     `step-ca` can reach the right vhost for `http-01` validation. Seeded
     with records for every student at bootstrap (`STUDENT_COUNT`-driven,
     same loop pattern `bootstrap` already uses for Forgejo accounts), so
     the lab works standalone without requiring a DNS-editing step first.
  2. The `dns-01` capstone (TXT record challenge against this same server).
- **`step-ca`** — official `smallstep/step-ca` image, ACME provisioner
  enabled. Provisioner claims set a **short cert lifetime**
  (`defaultTLSCertDuration`/max in the 5–10 minute range) so automated
  renewal is actually observable within a lab session rather than weeks
  later — this is the single most important config choice for making Lab 4
  ("automate renewal") land experientially instead of theoretically.
  Root cert gets bootstrapped into each student's trust store in Lab 1
  (`step ca bootstrap`) — the direct analog of trusting an org's Venafi-
  issued root.
- **`demo-app`** — one shared nginx container. Isolation via **per-student
  vhost ownership** on a shared named volume (e.g. `cert_lab_webroot`),
  mounted into both `web-terminal` (student-writable subdirectory
  `studentNN/`, chowned like home directories already are — same boundary
  students already trust) and `demo-app` (`conf.d/*.conf` + docroots read
  from that volume). A student can only ever touch their own subdirectory.
  A lightweight watcher (`inotifywait`/`entr` loop → `nginx -s reload`)
  inside `demo-app` picks up new/changed vhosts and certs automatically —
  no `docker.sock`, no cross-container exec granted to students, consistent
  with the allocator's existing no-docker.sock design principle.

  **Open implementation detail (decide at build time, not a design
  question)**: exact reload-watcher mechanism (inotify script vs. an nginx
  module), and whether DNS records are fully pre-seeded vs. partially
  written by students as a lab step.

### Terminal image overlay (`compose/terminal/Dockerfile`)

`FROM gitopsdojo/web-terminal:base`, same technique as `dns-as-code`'s
pinned `dnscontrol` binary (arch-aware download + sha256 verification).
Adds: `step` CLI (Smallstep, pinned release), `certbot`, `acme.sh`,
`openssl`, `dig`/`dnsutils`, `jq`, `cron` (if not already in the base
image — needed for the renewal-automation lab).

### No `engine/` changes

No new Caddyfile routes, no allocator changes, no per-student port
formula extension. All ACME traffic is container-to-container
(`web-terminal` → `step-ca` ACME directory; `step-ca` → `demo-app` for
challenge validation). Student verification is via
`curl -vk https://studentNN.certs.dojo.test` / `openssl s_client` /
`openssl x509 -noout -dates`, run from their own terminal — no gateway
routing needed.

## Lab progression (`content/lab/`)

Mirrors `dns-as-code`'s numbered-labs + cheat-sheet structure
(`content/lab/README.md` as menu with a required/optional table).

1. **Lab 1 — Trust the CA** *(required)*: `step ca bootstrap` against the
   shared `step-ca`; inspect the root cert; understand why a client must
   trust a private CA before ACME issuance works — the direct parallel to
   trusting an org's Venafi-issued root.
2. **Lab 2 — Issue & install with certbot** *(required)*: `certbot certonly`
   (webroot pointed at the student's own `demo-app` subdirectory), http-01
   against `studentNN.certs.dojo.test`, install into their own nginx vhost,
   verify with `curl`/`openssl s_client`. Certbot chosen as the primary
   client because it's the most industry-standard, most transferable skill.
3. **Lab 3 — Same task with acme.sh** *(optional)*: same outcome, different
   client — makes the point that ACME is a protocol, not a specific tool,
   and acme.sh's shell-script transparency shows the raw
   account/order/challenge/finalize exchange more directly than certbot
   does.
4. **Lab 4 — Automate renewal** *(required — this is the workshop's stated
   goal)*: cron entry (or systemd-timer style), a deploy-hook/`--reload-cmd`
   that reloads nginx, and — thanks to the short cert lifetime configured
   on `step-ca` — an actual automated renewal that fires and is observable
   within the lab window.
5. **Lab 5 — Capstone: dns-01** *(optional)*: same issuance, but validated
   via a TXT record against the bundled PowerDNS instead of exposing a web
   server for http-01. Ties back to `dns-as-code` skills for students who
   completed that workshop too.

`content/sample-repo/` seeds each student's Forgejo repo with their own
nginx vhost template + a renewal-script skeleton (the cert-workshop analog
of `dnsconfig.js`/`dnsctl.py` in `dns-as-code`) — git stays the source of
truth for "what's deployed," even though the workflow itself is manual-CLI
rather than CI-applied (matching the user's "manual CLI lab" choice over
full git-driven automation).

## Files to create

Following `workshops/README.md`'s "Adding a new workshop" steps:

- `workshops/cert-autorenewal/workshop.env`
- `workshops/cert-autorenewal/compose/docker-compose.override.yml`
- `workshops/cert-autorenewal/compose/terminal/Dockerfile`
- `workshops/cert-autorenewal/compose/demo-app/` (nginx base config +
  reload-watcher script/entrypoint)
- `workshops/cert-autorenewal/compose/dns-server/` (zone seed, matching
  whatever mechanism `dns-as-code` uses)
- `workshops/cert-autorenewal/content/lab/{README.md,lab1..lab5.md,cheat-sheet.md}`
- `workshops/cert-autorenewal/content/sample-repo/` (vhost template,
  renewal-script skeleton, repo README)
- `workshops/cert-autorenewal/content/slides/presentation.md` (next phase —
  reuse `dns-as-code`'s Marp frontmatter/style block for visual
  consistency; not drafted in this phase)
- Row added to `workshops/README.md`'s workshop table
- `infra/corp-dev/gdojo-cc/workshops/cert-autorenewal.tfvars` (Azure
  delivery — copy an existing `.tfvars`, adjust per `workshops/README.md`
  step 7)

## Verification plan

1. `cd engine && ./run.sh cert-autorenewal` — all services
   (`dns-server`, `step-ca`, `demo-app`, `web-terminal`) come up healthy.
2. Walk Labs 1–4 end to end as `student01`: bootstrap trust, issue via
   certbot, issue via acme.sh, confirm a cron-triggered renewal actually
   fires within the lab's short cert lifetime and nginx reloads without
   downtime.
3. Repeat as `student02` concurrently — confirm no collisions: distinct
   DNS name, distinct vhost/docroot/cert files, `demo-app`'s reload watcher
   handles both independently.
4. Run Lab 5 (dns-01) against the bundled PowerDNS and confirm it validates
   without needing `demo-app` reachable on port 80.
5. `./run.sh stop` and re-run clean, confirming no leftover-state
   assumptions — matches the "nothing persists" principle in `CLAUDE.md`.

---

*Next step: scaffold the files above so the workshop runs end-to-end, then
build `content/slides/presentation.md`, then open it up for hands-on
access.*
