# dojo-introduction: Dojo Introduction

A show-and-tell of the whole GitOps Dojo, for a facilitator to click through as a student and as the facilitator. It
is not a lab: nothing has to be completed. Every capability is running at once.

```bash
./run.sh dojo-introduction
./run.sh stop
```

## What you get

| Where | What |
| ----- | ---- |
| **Slides** (hub) | *Platform tour* (how it is built, the flows, the modules), *Workshop library* and *Tool tour* |
| **Workshop Library** (card and `/admin` tab) | One page linking each workshop's own `index.md` (its presentation, labs and cheat sheet), served under `/slides/w/<name>/` |
| **Forgejo** | The `dojo-team/dojo-tour` repository, with Actions on |
| **Vault** card, **Audit** and **Runners** tabs | OpenBao (sign in with Forgejo), its audit log, and the single-use CI runner pool |
| **DNS Zones** card, **DNS Admin** tab | PowerDNS with the `certs.dojo.test` zone and each account's own `<user>.dojo.test` (`~/lab/my-zone`, pushed with `dnscontrol` through `dns-api`), the live viewer and PowerDNS-Admin |
| **Dojo Cloud** card | The training cloud's portal; `tofu` in the terminal talks to it |
| **VS Code / Terminal** | One image with the tools of all four workshops: `bao`, `sops`, `gitleaks`, `pass`, `dnscontrol`, `dig`, `step`, `certbot`, `acme.sh`, `tofu` |

`content/lab/tools-tour.md` (seeded to `~/lab`) has a few commands per capability.

## How it is put together

- `MODULES="openbao runner-pool dojo-cloud dns-ui"`. `forgejo-runner` is not listed: it can't run beside `runner-pool`.
- `compose/docker-compose.override.yml` reuses the other packs' sources (cert-autorenewal's PowerDNS seed, step-ca
  and demo site; vault-fundamentals' namespace and CI hooks, mounted file by file) and mounts each workshop's
  `content/slides` under the presentation service at `/slides/w/<name>/`.
- `compose/terminal/Dockerfile` repeats the other packs' tool pins (dnscontrol, step, sops, gitleaks, tofu and its
  provider mirror). When one of those changes there, change it here too.
- `engine/run.sh` makes the git-ignored `lab/*.md.txt` copies for every pack, not only the running one, so the
  library's lab links work on a fresh clone.

## Left out on purpose

- vault-fundamentals' `app-host` and `app-db` (labs 11-13): no **Apps** tab or **My App** card, and no dynamic database logins.
- dns-as-code's shared `dojo.test` zone, its CI preview and branch protection (they need `forgejo-runner`, which can't run
  beside `runner-pool`). `dns-api` is here with an empty `CI_HOSTS`, so `dojo.test` itself is refused for everyone and only
  each account's own zone is writable.

Their slides and labs are in the library; to run those flows, start that workshop.

## Demo bots

`./run.sh dojo-introduction --test 5` adds bots that walk the tool tour (`content/bots/steps.sh`): a push and pipeline, vault
reads and writes, a `dnscontrol` push, the CA and (the expert bot) an OpenTofu apply on Dojo Cloud. It fills the Roster,
Audit, Runners and DNS Zones tabs.

## Keeping the tool pins in step

`./check-pins-sync.sh` fails if a tool version or checksum in `compose/terminal/Dockerfile` differs from the workshop
Dockerfile it was copied from. Run it after changing any pin.

See [`FACILITATOR.md`](FACILITATOR.md) for a run-of-show.
