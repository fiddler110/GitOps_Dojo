# Workshops

Each subfolder here is a self-contained **workshop pack**: content plus
(optionally) whatever's different about how it runs. The shared runtime
lives in [`../engine/`](../engine/) and stays untouched no matter how many
workshops exist — see [`engine/README.md`](../engine/README.md) for what it
runs and how requests are routed.

## Available workshops

| Workshop | What it teaches | Run it |
| -------- | ---------------- | ------ |
| [`git-fundamentals/`](git-fundamentals/) | Core git workflow: clone, branch, commit, push, PR | `cd ../engine && ./run.sh git-fundamentals` |
| [`dns-as-code/`](dns-as-code/) | Managing DNS records via git + dnscontrol, building on Session 1 | `cd ../engine && ./run.sh dns-as-code` |
| [`cert-autorenewal/`](cert-autorenewal/) | Automated TLS certificate issuance/renewal via ACME (step-ca, certbot, acme.sh) | `cd ../engine && ./run.sh cert-autorenewal` |
| [`tofu-basics/`](tofu-basics/) | OpenTofu/Terraform basics: `init`/`plan`/`apply`/`destroy` and repo layout (`terraform` runs OpenTofu) | `cd ../engine && ./run.sh tofu-basics` |

`./run.sh list` (from `engine/`) prints this same list from each
workshop's `workshop.env`.

## How workshop selection works

```sh
cd engine
cp .env.example .env       # first time only — account/secret settings, shared by every workshop
./run.sh <workshop-name>
```

`run.sh`:

1. Loads `engine/.env` (`TTYD_*`, `STUDENT_*`, `FACILITATOR_*`,
   `FORGEJO_ADMIN_*`, `PUBLIC_BASE_URL`, ports — the same regardless of
   which workshop runs).
2. Loads `workshops/<name>/workshop.env` (workshop identity: content dir,
   Forgejo org/repo, and an optional Compose overlay) — these override
   `.env` where they overlap, so `workshop.env` is always the source of
   truth for its own workshop.
3. Builds the base `web-terminal` image and tags it
   `gitopsdojo/web-terminal:base` (plus the workshop's own terminal image and
   the allocator/gateway/presentation images), so a workshop's own terminal Dockerfile
   (if it has one) can extend the base instead of duplicating its package
   list — but only rebuilds whichever of those actually changed since the
   last build, reusing the existing local image otherwise.
4. Runs `docker compose -f docker-compose.yml [-f <overlay>] up -d`.

## Two kinds of workshop

**Content-only** (like `git-fundamentals`): a `workshop.env` with an empty
`COMPOSE_OVERLAY` and a `content/` folder (slides, lab instructions, seed
repo). Uses the engine exactly as-is — no new services, no different
terminal image. This is the common case; reach for it first.

**Content + infrastructure** (like `dns-as-code`): everything above, plus
a `compose/` folder holding a Compose override file that layers extra
services or a different terminal image on top of the base engine. Reach
for this only when the lab genuinely needs different tooling in the
terminal or a different backend to interact with (a database, a DNS
server, etc.) — not for anything content/slides alone can express.

## Adding a new workshop

1. `mkdir -p workshops/<name>/content/{slides,lab,sample-repo}`
2. Write `content/slides/presentation.md` (Marp — copy an existing deck's
   frontmatter/style block for visual consistency), `content/lab/README.md`
   (seeded into every student's `~/lab`), and `content/sample-repo/`
   (seeded into Forgejo by the `bootstrap` service — same mechanism for
   every workshop, nothing to configure).
3. Write `workshop.env`:
   ```sh
   WORKSHOP_NAME=<display name>
   WORKSHOP_CONTENT_DIR=../workshops/<name>/content
   FORGEJO_ORG=<org name>
   FORGEJO_REPO=<repo name>
   COMPOSE_OVERLAY=
   ```
   Paths are relative to `engine/`, not to the workshop folder — Compose
   resolves every relative path in a multi-file `-f ... -f ...` merge
   relative to the *base* file's directory (`engine/docker-compose.yml`'s),
   regardless of which file declares the path. This trips people up — see
   the comment at the top of `dns-as-code/compose/docker-compose.override.yml`
   for a worked example.
4. If (and only if) the lab needs different tooling or an extra service:
   add `compose/docker-compose.override.yml` (and a `compose/terminal/`
   Dockerfile if the terminal itself needs different packages — `FROM
   gitopsdojo/web-terminal:base` to inherit the shared account-provisioning
   entrypoint instead of duplicating it), and point `COMPOSE_OVERLAY` at
   it. If you add a `compose/terminal/` override, also give the
   `web-terminal:` block in your override file its own
   `image: gitopsdojo/web-terminal:<name>` line — without it, Compose
   inherits the base file's `image: gitopsdojo/web-terminal:base` and tags
   your workshop-specific build as `:base` too, clobbering the shared base
   image every time this workshop runs (see `engine/run.sh`, which skips
   rebuilding an image whose source hasn't changed and depends on `:base`
   only ever meaning the plain, un-augmented image). `dns-as-code` and
   `cert-autorenewal` are worked examples. A workshop image that sets its own
   `HEALTHCHECK` *replaces* the inherited one, so either omit it or use exactly
   `HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 CMD web-terminal-healthcheck`
   (the base image's script, which sends the `X-Control-Token` header). Do not copy a `wget` line:
   a bare `wget` gets a 403 and the container shows `unhealthy` for its whole life.
   Keep any service a student terminal must reach **off TCP ports 9000-9099 and
   9500-9899**: the terminal's per-account firewall (`DOJO_ISOLATION` in
   `engine/web-terminal/entrypoint.sh`) drops those for every non-root account,
   on any host, and the symptom is a silent timeout. `cert-autorenewal`'s
   step-ca uses 9443 for this reason.
5. Optional: write `content/bots/steps.sh` so `./run.sh <name> --test` bots
   work through *your* labs instead of the default git-fundamentals ones (see
   `engine/README.md`'s "Demo bots" section and `workshops/tofu-basics/content/bots/steps.sh`).
6. Add a row to the table above.
7. Run it locally end to end (`./run.sh <name>` from `engine/`) before
   trusting it for a live session.

Nothing about adding a workshop this way ever requires editing
`engine/docker-compose.yml`, the base `web-terminal` image, or the
gateway — those stay identical across every workshop by construction.
