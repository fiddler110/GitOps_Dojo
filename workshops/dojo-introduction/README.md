# dojo-introduction: Dojo Introduction

A show-and-tell of the GitOps Dojo, for a facilitator to click through as a student and as the facilitator. It is not
a lab: nothing has to be completed. Forgejo with CI, DNS as code and Dojo Cloud are running at once.

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
| **Runners** tab | The single-use CI runner pool |
| **DNS Zones** card, **DNS Admin** tab | PowerDNS with each account's own `<user>.dojo.test` (`~/lab/my-zone`, pushed with `dnscontrol` through `dns-api`), the live viewer and PowerDNS-Admin |
| **Dojo Cloud** card | The training cloud's portal; `tofu` in the terminal talks to it |
| **VS Code / Terminal** | One image with the tools of dns-as-code and tofu-basics: `dnscontrol`, `dig`, `tofu` |

`content/lab/tools-tour.md` (seeded to `~/lab`) has a few commands per capability.

## How it is put together

- `MODULES="runner-pool dojo-cloud dns-ui dns-gate sensei"`.
- `compose/docker-compose.override.yml` adds PowerDNS, mounts dns-as-code's `90-my-zone.sh` hook, and mounts each
  workshop's `content/slides` under the presentation service at `/slides/w/<name>/`.
- `compose/terminal/Dockerfile` repeats dns-as-code's and tofu-basics' tool pins (dnscontrol, tofu and its provider
  mirror). When one of those changes there, change it here too.
- `engine/run.sh` makes the git-ignored `lab/*.md.txt` copies for every pack, not only the running one, so the
  library's lab links work on a fresh clone.

## Left out on purpose

- The vault (vault-fundamentals: OpenBao, its **Vault** card and **Audit** tab, `sops`, `gitleaks`) and the certificate
  lab (cert-autorenewal: step-ca, the demo site, `certbot`, `acme.sh`). They made the tour heavy to start and to show.
- dns-as-code's shared `dojo.test` zone, its CI preview and branch protection. `dns-api` (the `dns-gate` module) is here
  with no CI repo, so `dojo.test` itself is refused for everyone; each account's own key writes only its own zone.

Their slides and labs are in the library; to run those flows, start that workshop.

## Demo bots

`./run.sh dojo-introduction --test 5` adds bots that walk the tool tour (`content/bots/steps.sh`): a push and pipeline, a `dnscontrol`
push and (the expert bot) an OpenTofu apply on Dojo Cloud. It fills the Roster, Runners and DNS Zones tabs.

## Keeping the tool pins in step

This pack's terminal image is assembled from two others': dnscontrol from `dns-as-code`, OpenTofu and its provider
mirror from `tofu-basics`. Two checks keep the copies honest, and CI runs both (`.github/scripts/dry-runs.sh`):

- `engine/scripts/check-tool-pins.sh` (repo-wide, run by every `./run.sh <workshop> --dry-run`) fails if a tool
  version shared by two Dockerfiles disagrees, or if the per-arch checksums under a shared version disagree.
- `./check-pins-sync.sh` covers what that cannot see: the files copied byte-for-byte from `tofu-basics`
  (`mirror.tf`, `unpack-mirror.py`, `tofurc`, `disable-tofu-ls.py`).

Run both after changing any pin, and bump every copy of a shared pin together.

See [`FACILITATOR.md`](FACILITATOR.md) for a run-of-show.
