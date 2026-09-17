# Lab 3 — `dnsctl.py`, the CLI Wrapper

**Optional.** Labs 1 and 2 did every step by hand: edit the file, run `dnscontrol preview` yourself, `git add`/`commit`/`push` yourself, open the PR in the browser yourself. `scripts/dnsctl.py` is the real production wrapper script that automates that whole loop into one command per step — same file, same guarantee, same PR review and CI in between. See `docs/dnsctl-cli.md` in the repo for the full command reference and why some of its output still says "Cloudflare."

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

`doctor` checks that `dnscontrol` is on `PATH`, that `.env`/`creds.json` are set up, and that git hooks are enabled. This is the first thing to run in any DNS-as-code repo, including a real one.

It'll flag a missing `.env` — fix it:

```sh
python3 scripts/dnsctl.py setup
python3 scripts/dnsctl.py doctor   # should be clean now
```

`setup` creates `.env` from `.env.example` and enables `.githooks` (the same `pre-commit`/`pre-push` hooks you can read about in `.githooks/` — a lint check before every commit, and a `dnscontrol preview` check before anything pushes to `main` locally).

---

## 2. Add a record with the wizard

Use a different name than your Lab 1/2 record, e.g. `yourname2`:

```sh
python3 scripts/dnsctl.py record add yourname2.dojo.test
```

It'll ask for a record type and value, then a `Proxy through Cloudflare (orange cloud)?` question for `A`/`CNAME` records — **answer `n`**. That prompt is real, unmodified production-script code; it's Cloudflare-specific and meaningless against this lab's PowerDNS backend. `docs/dnsctl-cli.md` explains why it's left in rather than patched out.

After you confirm, it'll offer to preview and submit right there — say no for now, you'll do those as separate steps next so you can see each one.

---

## 3. Preview and submit

```sh
python3 scripts/dnsctl.py preview
```

Same `dnscontrol preview` you've been running by hand — confirm the diff shows only your new record.

```sh
python3 scripts/dnsctl.py submit "Add A record for yourname2"
```

`submit` previews once more, commits, pushes a branch (creating one automatically since you started on `main`), and opens the PR for you — four manual steps from Lab 1 in one command. The first time it needs to talk to Forgejo, it'll prompt for your Forgejo username/password (same as your `git push` login) and cache it for the rest of this terminal session.

---

## 4. Check status and review

```sh
python3 scripts/dnsctl.py status                 # your open PR + check status
python3 scripts/dnsctl.py review <PR#>            # the diff, from the terminal
```

`status`/`review` should show a "DNS Preview" check — CI already ran `dnscontrol preview` on your PR and posted its own comment, exactly like Labs 1 and 2. If the check genuinely isn't showing up yet, it's a real background job, not instant — give it a few seconds and re-run `status`.

---

## 5. Merge and validate

Once the check is passing:

```sh
python3 scripts/dnsctl.py merge <PR#>
python3 scripts/dnsctl.py validate <PR#>
dig @dns-server yourname2.dojo.test A +short
```

`validate` waits for CI's "DNS Apply" run to finish and then confirms live state matches `dnsconfig.js` — you don't run `dnscontrol push` yourself at all on this track; CI does it on merge, same as a real production repo. (`merge --force` skips waiting on the check if you'd rather not wait for it.)

---

## Recap

You just did everything Labs 1-2 did by hand, in a handful of named commands instead of a dozen raw ones — same file, same PR review, same CI in between:

| Manual step | `dnsctl.py` equivalent |
| --- | --- |
| Edit `dnsconfig.js` | `record add` / `record edit` / `record remove` |
| `dnscontrol preview` | `preview` |
| `git add`/`commit`/`push` + open PR | `submit "<message>"` |
| Check the PR / CI comment | `status`, `review <PR#>` |
| Merge in Forgejo | `merge <PR#>` |
| Confirm it's live | `validate <PR#>` |

**Next:** [lab4.md](lab4.md) — using `dnsctl.py history` and `rollback` to investigate and safely undo a merged change (your Lab 1 PR is a good target).
