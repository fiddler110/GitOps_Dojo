# DNS as Code — Session 3

A 45-60 minute session: managing DNS records via git + pull requests
(`dnscontrol`), for anyone who's already been through
[Git Fundamentals](../git-fundamentals/). Same clone/branch/commit/push/PR
muscle memory, applied to a `dnsconfig.js` file instead of a roster.

Adapted from a real internal `dns-as-code-template` pattern (dnscontrol +
Cloudflare, with GitHub Actions CI) — trimmed down for a self-contained
lab: PowerDNS instead of a real DNS provider, Forgejo Actions instead of
GitHub Actions (the `runner-pool` module), no GitHub-specific tooling
(`dnsctl_lib/forgejo.py` stands in for the GitHub CLI). See
[dnscontrol.org](https://docs.dnscontrol.org/) for the underlying tool's
full docs.

## Running the local lab

```sh
cd ../../engine
cp .env.example .env    # first time only — account/secret settings, skip if already done
./run.sh dns-as-code
```

This workshop's `workshop.env` points `run.sh` at a
[Compose overlay](compose/docker-compose.override.yml) that adds a
PowerDNS container (`dns-server`), swaps in a terminal image with
`dnscontrol` + `dig` preinstalled, and lists three modules
(`MODULES` in `workshop.env`): `runner-pool` turns on Forgejo Actions with
single-use runners so the sample repo's `.forgejo/workflows/` actually
execute, `dns-ui` adds the DNS Zones page, and `dns-gate` puts the `dns-api`
gate in front of PowerDNS (see **Who may change what** below) — everything else
(gateway, Forgejo itself, slides, account provisioning) is the same
shared engine [git-fundamentals](../git-fundamentals/) uses. See
[`workshops/README.md`](../README.md) for how that selection mechanism
works.

Workshop content you can edit per-session, with no script/compose changes
required:

- [`content/slides/presentation.md`](content/slides/presentation.md) — the deck
- [`content/lab/README.md`](content/lab/README.md) — instructions seeded into every student's `~/lab`
- [`content/sample-repo/`](content/sample-repo/) — seeded into Forgejo as `dns-team/dns-as-code` by the `bootstrap` service, including its `.forgejo/workflows/`

Only touch [`compose/`](compose/) if you need different tooling in the
terminal, a different backend than PowerDNS, or to change the CI
pipeline's job tools (`JOB_TOOLS` in the overlay) — see the comments in
[`compose/docker-compose.override.yml`](compose/docker-compose.override.yml) and
[`compose/terminal/Dockerfile`](compose/terminal/Dockerfile) first. The workflow files themselves
live in `content/sample-repo/.forgejo/workflows/`, alongside the rest of
the seeded repo content.

## Who may change what

The `dns-gate` module's `dns-api` is the only way to the PowerDNS API
(PowerDNS's own key is derived in `workshop.env` and never reaches a
terminal or a job). `X-API-Key` carries one of:

- **Each account's own key** (`$DNS_API_KEY`, written `0600` to
  `~/.config/dojo/dns-api-key` at start): changes only that account's
  `<user>.dojo.test`. `creds.json` says `"apiKey": "$DNS_API_KEY"`, so the
  shared repo holds no secret.
- **The job's Forgejo Actions ID token** (`dns-apply.yml`,
  `enable-openid-connect: true`): changes `dojo.test` only when Forgejo
  signed it for a push to `main` of `dns-team/dns-as-code`. A PR that edits
  a workflow, a feature branch or a fork gets `403`, whatever it runs.
- **The read key** `workshop-not-a-secret` (the preview job): reads only.

Branch protection on `main` (`compose/gates/protect-main.sh`: the DNS
Preview check and one approval) keeps an edited workflow from reaching
`main` unreviewed.

## What's intentionally simplified vs. a production setup

- **PowerDNS, not a real DNS provider.** Ephemeral, internal-only,
  reset on every teardown — matches this whole engine's "nothing persists"
  design. `dnsconfig.js`'s `dojo.test` zone uses the IETF-reserved `.test`
  TLD so it can never collide with a real domain.
- **CI is real, via Forgejo Actions.** `content/sample-repo/.forgejo/workflows/`
  has two workflows: `dns-preview.yml` (runs `dnscontrol preview` on every
  PR, posts the diff as a comment, sets a "DNS Preview" commit status) and
  `dns-apply.yml` (runs `dnscontrol push` on merge to `main`, sets a "DNS
  Apply" status). They run on the `runner-pool` module's single-use
  runners: each job gets a fresh runner that is deleted afterwards, so no
  job finds another's files. Jobs run as processes in the pool container
  (a `host` label, not the Docker executor), so no `docker.sock` is mounted
  anywhere in this stack; that's also why `dnscontrol` (copied from the
  terminal image) and `git`/`curl`/`jq` are preinstalled there rather than
  pulled per-job. Both workflows do their own `git clone` instead of
  `uses: actions/checkout@...`, since this instance's Actions network is
  internal-only (no reachable actions registry).
- **`dnsctl.py` is the real script, lightly adapted.** `content/sample-repo/scripts/`
  ships the actual production CLI wrapper (`dnsctl.py` + `dnsctl_lib/`),
  changed only to point at this lab's PowerDNS zone (`CREDKEY`/`ZONES`) and
  to route its PR/CI operations through a small Forgejo API client
  (`dnsctl_lib/forgejo.py`) instead of the GitHub CLI when the remote isn't
  GitHub — see `procutil.detect_forge()`. `gh` itself is untouched and still
  used as-is against a real GitHub remote; the two coexist. Everything else
  Cloudflare-flavored in its output (the record wizard's proxy prompt, the
  `CLOUDFLARE_API_TOKEN` env var name) is left unmodified on purpose — see
  `docs/dnsctl-cli.md` in the sample repo for why. `merge`/`validate` now
  find a real "DNS Preview"/"DNS Apply" status to check, same as they
  would against a GitHub repo with CI configured.
- **Smoke-tested end to end** (`./run.sh dns-as-code` on podman, both
  tracks) — three real bugs turned up and got fixed in the process:
  the runner's `host` label had a stray `://` (forgejo-runner rejects
  arguments on the `host` scheme — only `docker`/`lxc` take one), the
  `DNS Preview` comment's marker text didn't match dnsctl.py's own
  `"dnscontrol preview"` substring filter (fixed to mirror the upstream
  template's exact marker, and made update-in-place instead of spamming a
  new comment per push), and `forgejo.py`'s PR state mapping didn't
  distinguish "merged" from "closed" (Forgejo's REST API has no MERGED
  state like GitHub's GraphQL API does — it's `state: closed` +
  `merged: true` as separate fields). All three confirmed fixed by
  re-running the affected `dnsctl.py` commands (`review`, `validate`)
  against the live stack afterward.

## Delivery notes

- Run through the whole lab yourself once before facilitating — confirm
  `dnscontrol push` + `dig @dns-server` actually work end to end in your
  environment, and specifically confirm the CI path: open a test PR,
  confirm `dns-preview.yml` posts a comment and sets a status, merge it,
  confirm `dns-apply.yml` runs and the record goes live. The Runners tab
  in `/admin`, `podman logs workshop_runner_pool` and
  `podman logs workshop_dns_api` (one line per refused or allowed zone
  change) are the first places to look if it doesn't.
- Reuses the git workflow from Session 1 — don't re-teach branching/PRs
  from scratch, just point back to it.
- Keep the talk light on new git mechanics; the new material is
  `dnsconfig.js` syntax and the preview/push loop.
