# Facilitator run-of-show: Dojo Introduction

About 45 minutes: a 10-minute look at the slides, then click around. Nothing here has to be completed.

## Before you start (5 minutes, ahead of time)

```bash
./run.sh dojo-introduction --test 5     # 5 demo students that walk the tool tour: a busy Roster, Audit, Runners
```

- The first start builds the terminal image (it downloads the tools and the OpenTofu provider mirror); later starts are quick.
- Open two browser profiles: one signed in as the **facilitator** at `/admin`, one as a **student** at `/`.
- In the student profile, open the **Vault** card once and click **Authorize** when Forgejo asks. It only asks the first time.
- Wait until the status strip in `/admin` is all green.

## The slides (10 minutes)

**Slides** on the hub, then **Platform tour**. Nine slides; the point of each:

1. **Title.** "One lab platform, one URL."
2. **One URL, nothing to install.** What a student gets, what you get.
3. **The whole picture.** Only the gateway has a port; everything else is internal.
4. **Every request is checked.** Identity is set by the gateway, never by the client.
5. **Three layers.** Engine, modules, workshops; a new workshop is mostly content.
6. **One terminal with every tool.** No internet, no `docker.sock`, tools baked in.
7. **What is in the box.** The five workshops; open the **Workshop library** from the link.
8. **What you can click through.** Your map for the rest of the session.
9. **Running it.** `./run.sh <workshop>`.

## The click-through (30 minutes)

| Minutes | As | Do | Say |
| ------- | -- | -- | --- |
| 5 | student | Landing page: type a name; open **VS Code**, open `~/lab/tools-tour.md` | Everyone gets their own account, terminal and editor from one URL. |
| 3 | facilitator | `/admin` **Roster**: click a tile to watch a terminal; point at the status strip | You see everyone, and can watch anyone. **Release** frees a slot. |
| 5 | student | Terminal: clone `dojo-tour`, push a branch (tour section 2) | Forgejo is the git server; a push starts a pipeline. |
| 2 | facilitator | **Runners** tab while the pipeline runs | One runner per job, deleted afterwards: yellow while busy, replaced by a fresh green one. |
| 5 | student | **Vault** card (signed in with Forgejo); in the terminal `bao kv get secret/students/$USER/welcome` | Your Forgejo login is your vault identity; your namespace is yours alone. |
| 2 | facilitator | **Audit** tab | Every vault request, by student and path. |
| 5 | student | **DNS Zones**; in `~/lab/my-zone` run `dnscontrol preview`, then `push` | DNS is declared in git and pushed; the page shows it live. |
| 3 | facilitator | **DNS Admin**: edit one of the student's records; the student runs `dnscontrol preview` | The dashboard edit shows up as drift, and the next `push` undoes it. |
| 3 | student | `step ca health ...`, `certbot --version` (tour section 5) | A real ACME CA with short-lived certificates, so renewal can be watched in minutes. |
| 3 | student | `tofu init`, `tofu apply` in `~/lab/dojo-tour/cloud`; then the **Dojo Cloud** card | An Azure-inspired training cloud: the real `azurerm` provider, your own credentials, a policy layer. |
| 2 | either | **Workshop Library** card | Each workshop has its slides, labs and cheat sheet; this is where a class would start. |

## What is not running here

Say this before someone asks:

- **No Apps tab or My App card.** vault-fundamentals' `app-host` and `app-db` (labs 11-13: deploying from CI with a
  platform identity, and dynamic database logins) are left out. Run `./run.sh vault-fundamentals` to show them.
- **No shared `dojo.test` zone, CI preview or protected `main`.** dns-as-code's review flow needs `forgejo-runner`, which can't
  run beside the runner pool. Each student's own `<user>.dojo.test` zone works. Run `./run.sh dns-as-code` for the review flow.
- **No labs to finish.** The tour is a set of commands. The real labs are in the library, one workshop at a time.

## If something is off

- **A tab is blank or red in the status strip:** wait 30 seconds after a start; the vault and cloud take longest.
- **Forgejo asks "Authorize" in the Vault card:** click it; it only asks once.
- **`tofu apply` says the cloud isn't ready:** the Dojo Cloud light in the status strip is still amber; retry in a minute.
- **Start over:** `./run.sh stop` removes every container and volume, so do it only when you are done.
