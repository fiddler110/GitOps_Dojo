# Core concepts

The platform is small once these ideas are clear. Everything else in the repo is an instance of one of them.

## 1. A class is a stack

`./dojo <workshop>` builds images and brings up **one Compose stack** for one class on one machine (a desktop,
a laptop or a VM). `./dojo stop` deletes the stack **and every volume**: accounts, repositories, student homes,
CA keys, DNS zones. Nothing survives, by design. Each class starts clean, and a mistake costs nothing.

## 2. The engine is workshop-agnostic

`engine/` is the shared runtime. It never knows which workshop is running. It provides:

| Service | Job |
|---|---|
| `gateway` | Caddy. The only published port. TLS, sign-in, routing, identity headers |
| `allocator` | Hands each browser a student account (a *slot*), serves the landing page, `/workspace` and the facilitator's `/admin` |
| `web-terminal` | One container holding every student's VS Code (code-server) and terminal (ttyd + tmux or Zellij), one Linux user each |
| `git-server` | Forgejo: repositories, pull requests, review, Actions |
| `bootstrap` | One-shot: creates the Forgejo admin, org, seed repo, student accounts |
| `presentation` | Marp: serves the slide decks and lab text |

Adding a workshop never means editing the engine. A workshop *adds to* the engine through files it owns.

## 3. A workshop is a pack

A **workshop pack** is a folder under `workshops/<name>/`:

| Piece | Purpose |
|---|---|
| `workshop.env` | Identity and wiring: display name, order, duration, Forgejo org/repo, `MODULES`, optional overlay |
| `content/` | `slides/` (Marp decks), `lab/` (the guides students follow), `sample-repo/` (seeded into Forgejo) |
| `MODULES="a b"` | Reusable building blocks the workshop opts into |
| `compose/docker-compose.override.yml` | Extra services only this workshop needs |
| `compose/terminal/Dockerfile` | Extra tools in the student terminal |
| `extensions.json` | Landing cards, `/admin` tabs, gateway routes and status checks |
| `FACILITATOR.md`, `README.md` | The run-of-show and the technical reference |

Three kinds, from simplest: **content-only** (git-fundamentals), **content plus modules** (tofu-basics),
**content plus its own infrastructure** (cert-autorenewal). Reach for the simplest that works; if two workshops
want the same extra service, it becomes a module.

## 4. A module is a reusable pack of services and tools

`modules/<name>/` holds any of: `module.env` (defaults), `compose.yml` (services), `extensions.json` (front
door), `terminal/Dockerfile` (tools), `README.md`. A workshop lists modules in `MODULES="runner-pool dojo-cloud"`.
The module brings its services, terminal tools, landing card, `/admin` tab and routes together. See
[Modules](modules.md).

## 5. Extensions: the front door

A workshop or module declares what a user can *see and reach* in an `extensions.json` manifest: landing **cards**,
`/admin` **tabs**, gateway **routes**, **status checks**, framed **widgets**, page **scripts** and student-**reset**
hooks. The engine validates the manifest, renders it through fixed templates (a manifest can never inject raw
Caddy config or HTML), and refuses to start on a bad one. See [Authoring](authoring.md#4-the-extensionsjson-manifest).

## 6. Gates: who may reach a route

Every route a manifest declares uses one of three fixed gates:

| Gate | Who gets through | What the upstream receives |
|---|---|---|
| `shared` | anyone signed in with the class login | no identity at all |
| `identity` | a browser holding a student slot, or the facilitator | `X-Auth-User` and `X-Gateway-Token`, both set by Caddy |
| `facilitator` | the facilitator only (students get 403) | the same pair |

A service behind `identity` or `facilitator` **must still verify `X-Gateway-Token`**, because students can reach
it directly on the lab network and only the token proves a request came through Caddy.

## 7. Slots: how identity works for a class

The class signs in with one shared login (shown on a slide). That proves "member of the class", not *which*
student. The allocator then assigns the first free `studentNN` to the browser and binds it with a cookie. That slot
is the student's identity everywhere: their Linux user, Forgejo account, ports, cloud subscription, DNS zone,
vault namespace. The facilitator has a separate login and never consumes a slot.

## 8. One terminal container, many Linux users

All students share one `web-terminal` container and one network namespace, so **a source IP never identifies a
student**. Separation is done by the kernel: a Linux uid each, `0700` homes, per-uid `iptables` rules on the
workspace ports, a PID namespace each, and root-owned brokers that learn the caller's uid through
`SO_PEERCRED`. See [Security](security.md).

## 9. Student terminals are offline

No internet, no `docker.sock`. Every tool is **baked into the image**, version-pinned and sha256-verified per
architecture. The terminal image is a **chain**: `:base` → each module's `terminal/` → the workshop's
`compose/terminal/`. Anything a lab needs at runtime is either in the image or a service inside the stack.

## 10. Real tools, real services

Labs use real tools against real services: Forgejo with real pull requests and Actions, PowerDNS with
`dnscontrol`, `step-ca` for ACME, OpenBao for secrets, the real `azurerm` Terraform provider talking to
**Dojo Cloud** (an Azure-*inspired* practice cloud, with no Microsoft names or branding). Failures are lessons,
not incidents, because everything belongs to the lab.

## 11. Settings in layers

`dojo.toml` (committed defaults) < `dojo.local.toml` (this machine, plus profiles) < `.env` (secrets) < a profile
(`--env NAME`) < the workshop's `workshop.env`. `./dojo config <workshop> KEY` shows which layer won. See
[Configuration](configuration.md).

## 12. Optional layers on top of a lab

| Layer | What it adds |
|---|---|
| **Sensei** | Offline helper: reviews and merges practice pull requests, `sensei ask` and `sensei why` in the terminal |
| **Achievements** | Points, toasts, leaderboard, per-lab challenges, certificate; on by default for workshops with a catalog |
| **Demo bots** (`--test`) | Simulated students that run the labs for real; for rehearsal, demos and load tests |
| **Student reset** | Put one student back to start without disturbing the class |
| **Access code** (`--pass`) | An extra page in front of the whole site |

## Glossary

| Term | Meaning |
|---|---|
| **Allocator** | Service that assigns slots, serves the landing page, `/workspace`, `/admin` and the auth checks |
| **Bot** | A simulated student (`testuser1..N`) started by `--test` |
| **Bootstrap** | The one-shot container that seeds Forgejo |
| **Card** | A tile on the student landing page (and a tab in `/workspace`) |
| **Class login** | The shared username and password (`TTYD_USERNAME`/`TTYD_PASSWORD`) |
| **Compose overlay** | A workshop's extra Compose file, layered on the engine's |
| **Dojo Cloud** | The Azure-inspired training cloud from the `dojo-cloud` module |
| **Facilitator** | The person running the class; has `/admin`, sudo in the terminal, no slot |
| **Flavor** | Terminal type: `code-server` (VS Code + tmux) or `zellij` (terminal only) |
| **Forgejo** | The git server (a Gitea fork) |
| **Gate** | One of `shared`, `identity`, `facilitator` |
| **Gateway token** | Secret that proves a request passed through Caddy; each upstream gets its own derived token |
| **Lab** | One numbered exercise in `content/lab/` |
| **Manifest** | A workshop's or module's `extensions.json` |
| **Module** | Reusable services and tools under `modules/` |
| **Overlay** | See *Compose overlay* |
| **Pack** | A workshop folder |
| **Profile** | A named settings set selected with `--env NAME` |
| **Roster** | The `/admin` tab showing live student tiles |
| **Runner pool** | Single-use Forgejo Actions runners |
| **Slot** | A `studentNN` account held by one browser |
| **Start hook** | Script in `/etc/dojo/start.d/` run as root when the terminal container starts |
| **Watch tile** | The facilitator's read-only view of one student's terminal |
