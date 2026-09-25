# DNS as Code — workshop zone

`dnsconfig.js` is the source of truth for `dojo.test`'s DNS records.
[dnscontrol](https://docs.dnscontrol.org/) reads it and talks to the
`dns-server` (PowerDNS) container on your behalf — you never edit records
by hand anywhere else.

This is a trimmed-down teaching copy of a real pattern used in production —
the only real gap is the DNS provider itself: a lab-only PowerDNS
container here instead of a real one. Everything else is genuinely
wired up, including CI and the gates around it:

- `.forgejo/workflows/dns-preview.yml` previews every pull request merged
  into `main` and posts the `dnscontrol preview` diff as a PR comment and
  a required **DNS Preview** check.
- `main` is protected: no direct pushes, and a PR merges only with a
  passing DNS Preview check and one approval from someone other than the
  author.
- `dns-apply.yml` applies `main` on every merge. It's the only thing
  allowed to change `dojo.test`: a `dnscontrol push` from your own
  terminal gets `403`. Run `dnscontrol preview` locally as often as you
  like; it only reads.

- [`docs/record-types.md`](docs/record-types.md) — syntax for each record
  type used below (A, CNAME, MX, TXT).
- [`docs/making-changes.md`](docs/making-changes.md) — the day-to-day
  workflow for adding/editing/removing a record, by hand with plain git.
- [`docs/dnsctl-cli.md`](docs/dnsctl-cli.md) — `scripts/dnsctl.py`, the
  same CLI wrapper a real dns-as-code repo ships, pointed at this lab's
  zone. Automates the same workflow behind one command per step.

Follow along in `~/lab/README.md` inside your terminal for the actual lab
steps.
