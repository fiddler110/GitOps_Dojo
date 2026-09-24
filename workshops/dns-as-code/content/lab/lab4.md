# Lab 4 — `dnsctl.py`, the CLI Wrapper

**Optional. Part 2.** Lab 3 did every step by hand: edit the file, run `dnscontrol preview` yourself, `git add`/`commit`/`push` yourself, open the PR in the browser yourself. `scripts/dnsctl.py` is the real production wrapper script that automates that whole loop into one command per step — same file, same gates, same PR review and CI in between. See `docs/dnsctl-cli.md` in the repo for the full command reference and why some of its output still says "Cloudflare."

Work in your clone of the shared repo, starting from `main` with a clean working tree:

```sh
cd ~/lab/dns-as-code
git checkout main
git pull
git status   # should be clean — finish or discard anything from Lab 3 first
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

Use a different name than your Lab 3 record, with your username in it:

```sh
python3 scripts/dnsctl.py record add $USER-api.dojo.test
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
python3 scripts/dnsctl.py submit "Add $USER-api.dojo.test"
```

`submit` previews once more, commits, pushes a branch (creating one automatically since you started on `main`), and opens the PR for you — four manual steps from Lab 3 in one command. The first time it needs to talk to Forgejo, it'll prompt for your Forgejo username/password (same as your `git push` login) and cache it for the rest of this terminal session.

---

## 4. Check status and review

```sh
python3 scripts/dnsctl.py status                 # your open PR + check status
python3 scripts/dnsctl.py review <PR#>            # the diff, from the terminal
```

`status`/`review` should show a "DNS Preview" check — CI already ran `dnscontrol preview` on your PR and posted its own comment, exactly like Lab 3. If the check genuinely isn't showing up yet, it's a real background job, not instant — give it a few seconds and re-run `status`.

---

## 5. Get it approved

`main` still needs one approval from someone other than you. Swap with a neighbour: each of you reviews the other's PR from the terminal and approves it if the diff and preview show only their record:

```sh
python3 scripts/dnsctl.py review <their-PR#>
python3 scripts/dnsctl.py approve <their-PR#>
```

Or approve in the Forgejo web page, as in Lab 3.

---

## 6. Merge and validate

Once the check is passing and the PR is approved:

```sh
python3 scripts/dnsctl.py merge <PR#>
python3 scripts/dnsctl.py validate <PR#>
dig @dns-server $USER-api.dojo.test A +short
```

`validate` waits for CI's "DNS Apply" run to finish and then confirms live state matches `dnsconfig.js`. You don't run `dnscontrol push` yourself on this track; CI does it on merge. (`dnsctl.py push` exists, but from your terminal the lab's PowerDNS API refuses it for `dojo.test`, as in Lab 3. `merge --force` skips dnsctl's own check, but Forgejo still won't merge without a passing check and an approval.)

---

## Recap

You just did everything Lab 3 did by hand, in a handful of named commands instead of a dozen raw ones — same file, same PR review, same CI in between:

| Manual step | `dnsctl.py` equivalent |
| --- | --- |
| Edit `dnsconfig.js` | `record add` / `record edit` / `record remove` |
| `dnscontrol preview` | `preview` |
| `git add`/`commit`/`push` + open PR | `submit "<message>"` |
| Check the PR / CI comment | `status`, `review <PR#>` |
| Approve someone else's PR | `approve <PR#>` |
| Merge in Forgejo | `merge <PR#>` |
| Confirm it's live | `validate <PR#>` |

**Next:** [lab5.md](lab5.md) — using `dnsctl.py history` and `rollback` to investigate and safely undo a merged change (your Lab 3 PR is a good target).
