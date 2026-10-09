# cert-autorenewal — Certificate Autorenewal Lab

The mechanics behind automated TLS certificate issuance and renewal — the open-source, protocol-level
version of what a tool like Venafi automates for you at work. Five labs (0 is the talk; labs 1-5, about
80 minutes) against a real ACME CA (`step-ca`) and a real shared web app (`demo-app`): the certificates
students issue are real X.509 certs, actually installed, actually serving HTTPS. Prerequisite:
`git-fundamentals`; leans lightly on `dns-as-code` for the dns-01 lab. The facilitator guide is
[`FACILITATOR.md`](FACILITATOR.md).

## Running it

```bash
./dojo cert-autorenewal            # the class
./dojo cert-autorenewal --test 3   # plus 3 demo bots that walk the labs
./dojo stop                        # removes every container and volume, the CA and issued certs with them
```

`dojo` picks this workshop's identity and overlay from [`workshop.env`](workshop.env) — see
[`workshops/README.md`](../README.md) for how workshop selection works. First-time account/secret setup is
`./dojo setup` (shared by every workshop).

The facilitator's `/admin` has, besides the engine's tabs: **Site Inspector** (visit any student's site
like a browser — redirects, certificate, HSTS and headers) and the **DNS Zones** view (each student's A
record, and the `_acme-challenge` TXT records appearing and clearing during dns-01).

## What's in this folder

| Path | What it is |
| ---- | ---------- |
| `workshop.env` | Names, `MODULES="dns-ui dns-gate sensei"`, the overlay, the shared zone `certs.dojo.test`, the achievements `certs` verb settings. |
| `extensions.json` | The **Site Inspector** card, the `/admin` **Site Inspector** tab, and the `/inspect` route. |
| `compose/` | The overlay: `step-ca` (the ACME CA, on port 9443), `demo-app` (nginx, one vhost per student from `/srv/webroot/<user>/`), `dns-seed` (seeds each account's A records), `site-inspector` (the browser-like checker), and the terminal's extra tools (`step`, `certbot`, `acme.sh`) plus its `account.d` / `start.d` / `reset.d` / `lab-prep` hooks. |
| `content/` | Slides, labs 0-5 and the cheat sheet, the seed repo, and `bots/` (demo bots). |
| `achievements/` | The catalog: labs, challenges, capstone, funny unlocks and seeds (loaded when `ACHIEVEMENTS_ENABLED`). See [`ACHIEVEMENTS.md`](ACHIEVEMENTS.md). |

## Who may change what

The class shares the zone `certs.dojo.test`. Each account holds its own DNS key (`$DNS_API_KEY`) and may
change only names under `<user>.certs.dojo.test` — its A record and, during dns-01, its `_acme-challenge`
TXT record. This is enforced by the `dns-gate` module (`dns-api`, the only path to the PowerDNS API), not
by trust. PowerDNS's own key is derived from this install's `GATEWAY_TOKEN`, so it is never in the repo and
students never see it.

`step-ca` listens on **9443** on purpose: the terminal's per-account firewall (`DOJO_ISOLATION`) drops TCP
9000-9099 for every non-root account, so the CA sits just outside that range. An ACME call to a 90xx port
times out silently — that is the firewall, not the CA.

## Security shortcuts (accepted)

Lab conveniences, stated to the class, not production practice:

- **A shared `demo-app`** serves every student's vhost from one nginx, so a student's webroot
  (`/srv/webroot/<user>/`) is reachable by the app, not private like a home directory.
- **The lab CA (`step-ca`) is trusted by the terminal image** so clients validate without flags; its root
  is handed out in Lab 1 rather than pre-installed everywhere a browser would check.

## More

- Student-facing walkthrough: [`content/lab/README.md`](content/lab/README.md), seeded into every
  student's `~/lab`.
- Full facilitator setup, account provisioning and troubleshooting: [`FACILITATOR.md`](FACILITATOR.md) and
  [`engine/README.md`](../../engine/README.md).
- The DNS gate and zones page: [`modules/dns-gate/README.md`](../../modules/dns-gate/README.md),
  [`modules/dns-ui/README.md`](../../modules/dns-ui/README.md).
