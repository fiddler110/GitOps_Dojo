# `dnsctl.py` — the CLI wrapper

`scripts/dnsctl.py` is the same script a real dns-as-code repo ships —
copied in unmodified except for two constants (`CREDKEY`/`ZONES`, pointed
at this practice repo's `dojo.test` PowerDNS zone instead of the upstream
template's Cloudflare zones) and one small addition: it picks between the
GitHub CLI (`gh`) and a Forgejo API client (`scripts/dnsctl_lib/forgejo.py`)
automatically, based on your `origin` remote. Once this repo lives on
`github.com`, it uses `gh` — see [making-changes.md](making-changes.md).
Python 3 standard library only — no `pip install` needed.

```sh
python3 scripts/dnsctl.py <command> [options]
```

## Local commands — no forge CLI needed

| Command | Does |
| --- | --- |
| `doctor` | Checks dnscontrol is on PATH, creds.json/.env are set up, git hooks are enabled. Run this first. |
| `setup` | One-time: enables `.githooks`, creates `.env` from `.env.example`. |
| `preview` | `dnscontrol preview` — the dry-run diff. Changes nothing. |
| `push` | `dnscontrol push` — applies the diff. Prompts for confirmation. |
| `record add <name>` | Interactive wizard to add a record — shows the exact line before writing it. |
| `record edit <name>` | Change an existing record's value/priority/TTL in place. |
| `record remove <name>` | Remove a record, with disambiguation if more than one matches. |
| `record list` | List records currently in `dnsconfig.js`. |
| `record update-ip <old> <new>` | Bulk-replace an IP across every `A` record pointing at it. |
| `lint` | Fast offline sanity checks (duplicate lines, missing trailing dots, CNAME conflicts) — no network call. |
| `show` | Table/CSV/Markdown view of every record across all managed zones. |

Example:

```sh
python3 scripts/dnsctl.py record add yourname.dojo.test --type A --value 203.0.113.30 --yes
python3 scripts/dnsctl.py preview
python3 scripts/dnsctl.py push
```

`record prune-acme` / `record sync-acme` also exist (ACME/`_acme-challenge`
TXT record housekeeping) but aren't exercised here — `dojo.test` has none.

## Commands that need `gh` (once you're on GitHub)

`submit`, `status`, `review`, `approve`, `merge`, `rollback`, `validate`,
and `begin` all talk to whatever's hosting this repo — opening/listing/
merging pull requests, checking CI status. Install the
[GitHub CLI](https://cli.github.com/) and run `gh auth login` once, then:

```sh
python3 scripts/dnsctl.py submit "Add A record for yourname"   # commit, push, open a PR
python3 scripts/dnsctl.py status                                # list open PRs + check status
python3 scripts/dnsctl.py review <PR#>                           # diff (no preview comment unless you wired up CI)
python3 scripts/dnsctl.py merge <PR#>                             # merge once checks pass, or --force to skip waiting
```

**`merge`/`validate` normally wait on a passing "DNS Preview"/"DNS Apply"
CI status.** Without a CI workflow wired up against this local stack (see
`../01-local-powerdns-stack.md` and `../advanced-github-actions/` for the
optional advanced setup), those checks will never appear — use
`merge --force`, and run `dnscontrol push` by hand afterward instead of
`validate`. This mirrors exactly what
[making-changes.md](making-changes.md) describes for the plain-git path.

## Why some of this still says "Cloudflare"

This is the real script, not a rewrite — the record wizard's "Proxy through
Cloudflare (orange cloud)?" prompt, the `CLOUDFLARE_API_TOKEN` environment
variable name, and references to "live Cloudflare state" throughout its
output are all inherited as-is. None of it is wired to anything here
(PowerDNS doesn't have a proxy concept — answer `n`), but leaving it
visible is deliberate: it's a fast way to see, concretely, what "a wrapper
written against one specific provider" costs when you point it somewhere
else. If you later do the real-domain + Cloudflare path
(`../02-cloudflare-domain-setup.md`), all of this suddenly applies for
real, unmodified.
