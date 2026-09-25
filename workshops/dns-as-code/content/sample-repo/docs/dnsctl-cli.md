# `dnsctl.py` — the CLI wrapper

`scripts/dnsctl.py` wraps this repo's whole change loop (edit, preview,
commit, pull request, review, merge, confirm) into one command per step.
It is set up for this repo: `dnscontrol` with the PowerDNS provider in
`creds.json`, and pull requests on Forgejo. It picks between a Forgejo API
client (`scripts/dnsctl_lib/forgejo.py`) and the GitHub CLI (`gh`)
automatically, based on your `origin` remote — see
[making-changes.md](making-changes.md) for why that matters here. Python 3
standard library only — no `pip install` needed.

```sh
python3 scripts/dnsctl.py <command> [options]
```

## Local commands — no forge CLI needed

| Command | Does |
| --- | --- |
| `doctor` | Checks dnscontrol is on PATH, `creds.json` is complete, the PowerDNS API answers, and git hooks are enabled. Run this first. |
| `setup` | One-time: enables `.githooks`, creates the optional `.env` from `.env.example`, and adds a `dnsc` alias to `~/.zshrc_aliases` if that file exists. |
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
python3 scripts/dnsctl.py record add $USER-api.dojo.test --type A --value 203.0.113.30 --yes
python3 scripts/dnsctl.py preview
```

`push` works too, but in this lab only CI may change `dojo.test`, so from
your terminal the PowerDNS API answers it with `403`. Changes go through
`submit` and a reviewed merge instead.

`record prune-acme` / `record sync-acme` also exist (ACME/`_acme-challenge`
TXT record housekeeping) but aren't exercised in this lab — `dojo.test`
has none.

## Commands that need a forge CLI

`submit`, `status`, `review`, `approve`, `merge`, `rollback`, `validate`,
and `begin` all talk to whatever's hosting this repo — opening/listing/
merging pull requests, checking CI status. Against a GitHub remote that's
`gh`; against this lab's Forgejo (`git-server`), it's
`scripts/dnsctl_lib/forgejo.py` instead, chosen automatically per
`procutil.detect_forge()`. Same commands either way:

```sh
python3 scripts/dnsctl.py submit "Add $USER-api.dojo.test"    # commit, push, open a PR
python3 scripts/dnsctl.py status                                # list open PRs + check status
python3 scripts/dnsctl.py review <PR#>                           # diff + preview comment
python3 scripts/dnsctl.py approve <PR#>                           # approve someone else's PR
python3 scripts/dnsctl.py merge <PR#>                             # merge once checks pass and it's approved
```

The Forgejo commands log in with the same username and password as
`git push`, asked for through git itself: if git already remembers your
login from an earlier push, you won't be asked again, and if you're asked
now, your next `git push` won't ask either. dnsctl never writes the
password to disk. To use an access token instead, set `FORGEJO_TOKEN` in
`.env`.

`merge`/`validate` check for a passing "DNS Preview"/"DNS Apply" CI
status before proceeding — this lab actually has that wired up:
`.forgejo/workflows/dns-preview.yml` runs on every PR (posts the diff as
a comment, sets the "DNS Preview" status `merge` looks for) and
`.forgejo/workflows/dns-apply.yml` runs on merge to `main` (applies the
change for real, sets "DNS Apply" — what `validate`/`merge --wait` poll
for). If a status genuinely isn't showing up yet, give it a few seconds —
it's a real background job, not instant.

## No secrets of its own

Nothing here needs a secret beyond what's already in the repo:
`dnscontrol` reads the PowerDNS API URL and key from `creds.json` (a lab
key: your terminal can read `dojo.test` but only CI may change it), and
the Forgejo commands reuse your git login. `.env` is optional and
git-ignored; the `pre-commit` hook refuses to commit it.

In a real repo `creds.json` would reference environment variables
(`"apiKey": "$PDNS_API_KEY"`) and the write key would live only in CI's
secrets. Same script, same commands.
