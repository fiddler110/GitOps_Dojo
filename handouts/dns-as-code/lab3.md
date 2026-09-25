# Lab 3 — `dnsctl.py`, the CLI Wrapper

**Optional.** Labs 1 and 2 did every step by hand: edit the file, run
`dnscontrol preview` yourself, `git add`/`commit`/`push` yourself, open
the PR in the browser yourself. `scripts/dnsctl.py` is the real
production wrapper script that automates that whole loop into one command
per step — same file, same guarantee. See `docs/dnsctl-cli.md` in your
repo for the full command reference and why some of its output still says
"Cloudflare."

Make sure you've run `gh auth login` once (see
[00-github-setup.md](00-github-setup.md)) — `dnsctl.py` detects your
`origin` remote is `github.com` and uses the `gh` CLI automatically for
every PR-related command below.

Start from `main` with a clean working tree:

```sh
git checkout main
git pull
git status   # should be clean — finish or discard anything from Lab 2 first
```

---

## 1. Check your setup

```sh
python3 scripts/dnsctl.py doctor
```

`doctor` checks that `dnscontrol` is on `PATH`, that `.env`/`creds.json`
are set up, and that git hooks are enabled. This is the first thing to
run in any DNS-as-code repo, including a real one.

It'll flag a missing `.env` — fix it:

```sh
python3 scripts/dnsctl.py setup
python3 scripts/dnsctl.py doctor   # should be clean now
```

`setup` creates `.env` from `.env.example` and enables `.githooks` (the
same `pre-commit`/`pre-push` hooks you can read about in `.githooks/` —
a lint check before every commit, and a `dnscontrol preview` check before
anything pushes to `main` locally).

---

## 2. Add a record with the wizard

Use a different name than your Lab 1/2 record, e.g. `yourname2`:

```sh
python3 scripts/dnsctl.py record add yourname2.dojo.test
```

It'll ask for a record type and value, then a `Proxy through Cloudflare
(orange cloud)?` question for `A`/`CNAME` records — **answer `n`**. That
prompt is real, unmodified production-script code; it's Cloudflare-
specific and meaningless against this local PowerDNS backend. (Doing the
real-domain path from
[02-cloudflare-domain-setup.md](02-cloudflare-domain-setup.md) instead?
This prompt genuinely matters there — see that guide.)
`docs/dnsctl-cli.md` explains more.

After you confirm, it'll offer to preview and submit right there — say
no for now, you'll do those as separate steps next so you can see each
one.

---

## 3. Preview and submit

```sh
python3 scripts/dnsctl.py preview
```

Same `dnscontrol preview` you've been running by hand — confirm the diff
shows only your new record.

```sh
python3 scripts/dnsctl.py submit "Add A record for yourname2"
```

`submit` previews once more, commits, pushes a branch (creating one
automatically since you started on `main`), and opens the PR for you —
four manual steps from Lab 1 in one command. The first time it needs to
talk to GitHub it uses your cached `gh auth login` session — no extra
prompt.

---

## 4. Check status and review

```sh
python3 scripts/dnsctl.py status                 # your open PR + check status
python3 scripts/dnsctl.py review <PR#>            # the diff, from the terminal
```

Unlike the workshop, `status`/`review` won't show a "DNS Preview" check
here — there's no CI wired up against a laptop-local PowerDNS container
(see [01-local-powerdns-stack.md](01-local-powerdns-stack.md)). The diff
itself is still exactly what you'd review.

---

## 5. Merge and apply

```sh
python3 scripts/dnsctl.py merge <PR#> --force
```

`--force` skips waiting on a CI check that will never appear here (there
isn't one — see above). This mirrors real usage: `merge` without
`--force` is the right call whenever CI *is* wired up (the real-domain
path, or the advanced self-hosted-runner setup, both have it).

Since there's no CI to run `dnscontrol push` for you either, do it by
hand — this is the one step the workshop's CI did automatically that you
now do yourself:

```sh
git checkout main
git pull
dnscontrol push
dig @127.0.0.1 -p 5353 yourname2.dojo.test A +short
```

---

## Recap

You just did everything Labs 1-2 did by hand, in a handful of named
commands instead of a dozen raw ones:

| Manual step | `dnsctl.py` equivalent |
| --- | --- |
| Edit `dnsconfig.js` | `record add` / `record edit` / `record remove` |
| `dnscontrol preview` | `preview` |
| `git add`/`commit`/`push` + open PR | `submit "<message>"` |
| Check the PR | `status`, `review <PR#>` |
| Merge in GitHub | `merge <PR#>` (`--force` without CI wired up) |
| Apply for real | `dnscontrol push` by hand (or automatic, if CI is wired up) |

**Next:** [lab4.md](lab4.md) — using `dnsctl.py history` and `rollback`
to investigate and safely undo a merged change (your Lab 1 PR is a good
target).
