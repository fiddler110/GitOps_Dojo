# Lab 4 — `dnsctl.py`, the CLI Wrapper

**Part 2.** Lab 3 did every step by hand: edit the file, run `dnscontrol preview` yourself, `git add`/`commit`/`push` yourself, open the PR in the browser yourself. `scripts/dnsctl.py` is a wrapper script that automates that whole loop into one command per step — same file, same gates, same PR review and CI in between. See `docs/dnsctl-cli.md` in the repo for the full command reference.

Work in your clone of the shared repo, starting from `main` with a clean working tree:

```sh
cd ~/lab/dns-as-code
git checkout main
git pull
git status   # should be clean — finish or discard anything from Lab 3 first
```

> **Starting here?** This lab needs the shared repo cloned to `~/lab/dns-as-code`. Run `lab-prep 4` to set that up; it's safe to run even if you did the earlier labs.

---

## 1. Check your setup

```sh
python3 scripts/dnsctl.py doctor
```

`doctor` checks that `dnscontrol` is on `PATH`, that `creds.json` names the PowerDNS API, that the API answers, and that git hooks are enabled. This is the first thing to run in any DNS-as-code repo, including a real one.

Every check should say `[ok]` except one `[warn]`: git hooks aren't enabled yet. Git never turns on hooks from a repo you cloned, because a hook runs code on your machine, so each person enables them once per clone. Fix it:

```sh
python3 scripts/dnsctl.py setup
python3 scripts/dnsctl.py doctor   # all [ok] now
```

`setup` enables `.githooks` (read them in `.githooks/`: a lint and secret check before every commit, and a `dnscontrol preview` check before anything is pushed to `main`) and creates `.env` from `.env.example`. `.env` is for optional personal settings and is never committed; nothing in this lab needs it.

`setup` also adds a shortcut to `~/.zshrc_aliases` (your own alias file, loaded by every new terminal): `dnsc` means `python3 scripts/dnsctl.py`. Load it into this terminal and try it:

```sh
source ~/.zshrc_aliases
dnsc doctor
```

The rest of this lab spells out the full command so it's clear what runs; `dnsc` works anywhere it says `python3 scripts/dnsctl.py`, from any folder.

---

## 2. Add a record with the wizard

Use a different name than your Lab 3 record, with your username in it:

```sh
python3 scripts/dnsctl.py record add $USER-api.dojo.test
```

It asks for a record type and a value, shows the exact line it will add to `dnsconfig.js`, then offers to preview and submit. Answer its prompts like this:

| Prompt | Answer | Why |
| --- | --- | --- |
| `Record type (A, CNAME, MX, TXT) [CNAME]` | **A** | Maps the name to an IPv4 address, like your Lab 3 record. Don't just press Enter: the default is CNAME. |
| `IPv4 address for $USER-api.dojo.test` | **203.0.113.40** | A documentation address, like the rest of the zone. |
| `Add it? [Y/n]` | **y** | Writes `A("$USER-api", "203.0.113.40")` into `dnsconfig.js`. Say no here and nothing changes. |
| ``Run `dnscontrol preview` now to verify? [Y/n]`` | **n** | You'll run it yourself in step 3. |
| `Open a pull request for this change now? [y/N]` | **n** | You'll run `submit` yourself in step 3. |

The last two are shortcuts for the next step; skipping them just lets you run each one on its own. Confirm the record is in your file, uncommitted:

```sh
git diff dnsconfig.js   # one added line: your record
```

If the diff is empty, you answered no to `Add it?`. Run the `record add` command again.

---

## 3. Preview and submit

### 3a. Preview

```sh
python3 scripts/dnsctl.py preview
```

This is the same `dnscontrol preview` you ran by hand in Lab 3. It compares `dnsconfig.js` with the live zone and lists what a push would change. The first few lines are dnscontrol reading the zone. The part that matters is at the end:

```text
******************** Domain: dojo.test
1 correction (powerdns)
#1: ± BATCHED CHANGE/CREATEs for dojo.test
+ CREATE studentXX-api.dojo.test A 203.0.113.40 ttl=300
Done. 1 corrections.
```

Check it before going on:

| Look for | Means |
| --- | --- |
| `1 correction` and one `+ CREATE` line with your name and `203.0.113.40` | Your record, and nothing else, would be added. Go on to 3b. |
| More than one correction, or a line that isn't yours | Something else in your file differs from the live zone. Run `git diff dnsconfig.js` and undo anything that isn't your record. |
| `0 corrections` | Your record isn't in the file (see the end of step 2), or it's already live. |
| An error instead of a list | `dnsconfig.js` has a syntax problem. Fix it and run `preview` again. |

Preview changes nothing: it only reads.

### 3b. Submit

```sh
python3 scripts/dnsctl.py submit "Add $USER-api.dojo.test"
```

The text in quotes becomes the commit message and the PR title. `submit` does Lab 3's manual steps for you, but it shows you each one first and asks twice before changing anything.

**The check.** It runs the same preview as 3a again, under a `Check: dnscontrol preview` heading, then asks:

```text
Does the diff above look correct? [y/N]:
```

Type **y** if it shows only your record. The default is **no**, so just pressing Enter stops here and nothing is committed.

**The plan.** Next it lists exactly what it's about to do, with the git command behind each step:

```text
Plan: submit will now
  1. Create branch 'dns/add-studentxx-api-dojo-test' from 'main'
       $ git checkout -b dns/add-studentxx-api-dojo-test
  2. Stage dnsconfig.js
       $ git add dnsconfig.js
  3. Commit it as "Add studentXX-api.dojo.test" (the pre-commit hook lints it first)
       $ git commit -m ...
  4. Push 'dns/add-studentxx-api-dojo-test' to Forgejo
       $ git push -u origin dns/add-studentxx-api-dojo-test
  5. Open a pull request from 'dns/add-studentxx-api-dojo-test' into 'main'

Run these steps? [y/N]:
```

These are the commands you typed yourself in Lab 3. You started on `main`, so it names a branch after your message. (If you're already on a branch, step 1 says it will use that one.) Type **y** to run them. Again, Enter means no, and your change stays uncommitted in `dnsconfig.js`.

**The steps.** Each step prints a `[n/5]` heading, then that command's own output:

| Heading | What you'll see under it | What you do |
| --- | --- | --- |
| `[1/5] Create branch ...` | `Switched to a new branch 'dns/add-studentxx-api-dojo-test'` | Nothing |
| `[2/5] Stage dnsconfig.js` | `Staged: dnsconfig.js`. Only that file goes into the commit. | Nothing |
| `[3/5] Commit it as ...` | `pre-commit: ... running 'dnsctl lint'...`, `[ok] lint passed`, then the commit line with its short hash | Nothing. If lint fails, the commit is blocked: fix the file and run `submit` again. |
| `[4/5] Push ... to Forgejo` | `* [new branch] dns/add-studentxx-api-dojo-test -> ...` | Nothing: git signs in with your token, as in Lab 3. |
| `[5/5] Open a pull request ...` | `Pull request opened: <link>` and `Your PR number is <n>.` | Note the **number**: it's your `<PR#>` for steps 4 to 6. |

It ends with a `Done` heading and the next commands, with your PR number already filled in. Afterwards you're left on the new branch, not `main`. Open the link to see the PR in Forgejo if you want to.

If `submit` stops partway:

- `error: no local changes to commit`: your record isn't in `dnsconfig.js`. Go back to step 2.
- `Aborted.`: you didn't type `y` at one of the two questions. Nothing was committed, so run `submit` again.
- `git push` fails at `[4/5]`: the commit is already made, so running `submit` again would say there's nothing to commit. Fix the problem (usually the login), push with the `git push -u origin ...` command it prints, then open the PR in the Forgejo web page as in Lab 3.

---

## 4. Check status and review

### 4a. Status

```sh
python3 scripts/dnsctl.py status
```

`status` lists every open pull request on the repo, yours and your classmates', with the state of its **DNS Preview** check. That check is the CI job that ran `dnscontrol preview` on your PR as soon as `submit` opened it, the same one you watched in Lab 3. It only reads; nothing changes.

```text
#7: Add studentXX-api.dojo.test
    branch: dns/add-studentxx-api-dojo-test
    DNS Preview: SUCCESS
    http://localhost:8080/git/dns-team/dns-as-code/pulls/7
```

Find the line with your PR number and read its `DNS Preview` state:

| `DNS Preview:` shows | Means | What you do |
| --- | --- | --- |
| `no DNS Preview check found yet` | CI hasn't picked up the PR yet. It's a real background job, not instant. | Wait a few seconds and run `status` again. |
| `PENDING` | The check is running. | Wait and run `status` again. |
| `SUCCESS` | `dnscontrol preview` ran cleanly against your change. | Go on to 4b. |
| `FAILURE` or `ERROR` | The preview failed, so `main` won't accept this PR. | Run `review` (4b) to see why, fix `dnsconfig.js` on your branch, then commit and push again. The check runs again on every push. |

`No open pull requests.` means yours isn't open: it was already merged, or `submit` didn't get as far as `[5/5]`.

### 4b. Review

```sh
python3 scripts/dnsctl.py review <PR#>
```

`review` shows two things, each under a `===` heading. It only reads, so you can review any PR, not only your own.

```text
=== dnsconfig.js diff for PR #7 ===
diff --git a/dnsconfig.js b/dnsconfig.js
...
 	TXT("_dmarc", "v=DMARC1; p=reject; sp=reject; adkim=s; aspf=s;"),
+	A("studentXX-api", "203.0.113.40"),
 );

=== DNS Preview comment for PR #7 ===
### dnscontrol preview
...
******************** Domain: dojo.test
1 correction (powerdns)
#1: ± BATCHED CHANGE/CREATEs for dojo.test
+ CREATE studentXX-api.dojo.test A 203.0.113.40 ttl=300
Done. 1 corrections.
```

| Section | What it is | What to check |
| --- | --- | --- |
| `dnsconfig.js diff` | The change to the file: what's in the PR. Lines starting `+` are added, `-` removed. | Exactly one `+` line, your record. |
| `DNS Preview comment` | The comment CI posted on the PR: what the change would do to the live zone. | `1 correction` and one `+ CREATE` line matching the diff. |

The diff is what the PR *says*; the preview is what it would *do*. A reviewer checks that they agree. If the second part says `No DNS Preview comment yet - the check may still be running.`, wait a few seconds and run `review` again.

---

## 5. Get it approved

`main` needs one approval from someone other than the PR's author, so you can't approve your own. Try it to see what happens:

```sh
python3 scripts/dnsctl.py approve <your-PR#>
```

```text
You can't approve your own pull request. main needs one approval from someone else: ask a teammate to run
  python3 scripts/dnsctl.py approve <PR#>
...
```

Nothing changed. Swap with a neighbour instead (or, with nobody free, run `sensei review` for a pull request to review with `review` and `approve` below: once you have reviewed someone else's, Sensei approves yours within a few seconds, or `sensei approve --force` to skip the wait): tell each other your PR numbers (or find theirs with `status`), then review their PR the way you reviewed your own in 4b:

```sh
python3 scripts/dnsctl.py review <their-PR#>
```

Approve it only if the diff adds just their record and the preview shows the one matching `+ CREATE`. If it doesn't, tell them what's wrong rather than approving.

```sh
python3 scripts/dnsctl.py approve <their-PR#>
```

```text
Approved pull request #8
```

That's the same approval as the **Approve** button in the Forgejo web page, which works too, as in Lab 3. To add a note to the approval, pass `--body "Looks good"`.

Once your neighbour (or Sensei) has approved yours, open your PR link from `status` and you'll see their approval on it.

---

## 6. Merge and validate

### 6a. Merge

Once your PR's check shows `SUCCESS` and a neighbour has approved it:

```sh
python3 scripts/dnsctl.py merge <PR#>
```

`merge` does these in order:

1. **Checks the PR is open and its DNS Preview check passed.** If the check failed or is still running, it stops with `error: DNS Preview check has not succeeded`: go back to step 4. If there's no check yet, it prints a warning and carries on, but Forgejo will refuse the merge until there is one.
2. **Says what merging will do, then asks you to type `MERGE`:**

   ```text
   PR #7: "Add studentXX-api.dojo.test"
   Merging triggers the 'DNS Apply' CI job, which applies this change to the live zone(s) managed here (dojo.test).
   Type "MERGE" to continue, anything else to abort:
   ```

   It asks for the whole word, not `y`, because this is the step that changes live DNS. Type **MERGE** (capitals). Anything else prints `Aborted.` and nothing happens.
3. **Merges the PR into `main` and deletes its branch on Forgejo**, then prints:

   ```text
   Merged pull request #7
   Merged. Run 'python3 scripts/dnsctl.py validate 7' to confirm 'DNS Apply' succeeded and live state matches dnsconfig.js, or watch the Actions tab yourself.
   ```

The merge itself doesn't touch DNS. It starts the **DNS Apply** CI job, which runs `dnscontrol push` from `main` a few seconds later. You don't run `dnscontrol push` yourself on this track. (`dnsctl.py push` exists, but from your terminal the lab's PowerDNS API refuses it for `dojo.test`, as in Lab 3.)

If you see `error: PR #7 was not merged`, Forgejo refused: usually there's no approval yet, or the check hasn't passed. `merge --force` skips dnsctl's own check but not Forgejo's, so it won't help.

### 6b. Validate

```sh
python3 scripts/dnsctl.py validate <PR#>
```

`validate` answers "is my change actually live?" It needs a clean working tree, because it:

1. **Switches you to `main` and pulls it** (`Switching from 'dns/add-studentxx-api-dojo-test' to 'main' ...`), so it compares against what was merged. You're left on `main` afterwards, ready for the next change.
2. **Finds the DNS Apply run for your merge** (`Found run 12 - waiting for it to complete...`) and waits for it to finish, up to 5 minutes.
3. **Runs `dnscontrol preview` again** and expects `0 corrections`: the live zone now matches `dnsconfig.js` exactly.

```text
Validating commit 5ef2a6f1...
Looking for the 'DNS Apply' workflow run for this commit...
Found run 12 - waiting for it to complete...

'DNS Apply' succeeded. Confirming the live zone matches dnsconfig.js...
******************** Domain: dojo.test
Done. 0 corrections.

Validated: commit 5ef2a6f1 is live and the zone matches dnsconfig.js exactly.
```

| If it says | Means | What you do |
| --- | --- | --- |
| `error: you have uncommitted changes` | Something in your clone isn't committed. | Commit, stash or discard it (`git status` shows what), then run `validate` again. |
| `error: 'DNS Apply' run ... did not succeed - see <link>` | CI couldn't push the change to DNS. | Open the link to read the job's log, and tell the facilitator. |
| `error: 'DNS Apply' succeeded but the live zone still doesn't match` | Usually a classmate merged just after you and their apply hasn't finished. | Wait a few seconds and run `validate` again. |
| `error: no 'DNS Apply' run found` | It gave up waiting for the run to start. | Check the **Actions** tab in Forgejo, then run `validate` again. |

`merge --wait <PR#>` does 6a and 6b in one go. `validate` with no number checks the latest commit on `main`.

Finally, ask DNS yourself, as in Lab 3:

```sh
dig @dns-server $USER-api.dojo.test A +short   # 203.0.113.40
```

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
