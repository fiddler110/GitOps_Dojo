# Lab 5 — Investigating & Rolling Back History

**Part 2.** "Who changed this, when, and how do I undo it safely?" — the tools for answering that without hand-editing `dnsconfig.js` back to what it used to be. This lab uses `dnsctl.py`, so run [lab4.md](lab4.md)'s setup steps first if you haven't (`python3 scripts/dnsctl.py doctor` should be clean). You'll also need a merged PR to work with — Lab 3's is exactly right; grab its PR number if you wrote it down.

```sh
cd ~/lab/dns-as-code
git checkout main
git pull
git status   # should be clean
```

> **Starting here?** This lab rolls back your Lab 3 record, so it needs that pull request merged. `lab-prep 5` clones the repo and opens the pull request; someone else still has to approve it before you merge it: a neighbour, or Sensei (`sensei approve`, once you have reviewed a pull request that isn't yours: Lab 3 step 6; `sensei approve --force` skips the wait). Safe to run even if you did the earlier labs.

---

## 1. Browse DNS history

```sh
python3 scripts/dnsctl.py history
```

This lists every merge to `main` that touched `dnsconfig.js`, newest first, with the commit, date, and PR number — a filtered `git log` purpose-built for this repo. The raw-git equivalent, if you ever need it without the wrapper:

```sh
git log --oneline -- dnsconfig.js
git show <commit-hash>              # exactly what one commit changed
```

Find your Lab 3 PR in the list (the one that added your `A` record).

---

## 2. Roll it back

```sh
python3 scripts/dnsctl.py rollback <your-lab3-pr-number>
```

Read what happens carefully — this is worth understanding, not just running:

1. It creates a **new branch** and runs `git revert` on your original commit — a new commit that undoes the change, not a rewrite of history.
2. It runs `dnscontrol preview` automatically and shows you the diff, then asks you to confirm it looks like the exact inverse of the original change.
3. Once you confirm, it pushes the branch and **opens a new PR** — rollback never touches `main` directly, same as every other change to the shared zone.

This is the DNS-as-code equivalent of `git revert` from Git Fundamentals: undo by adding a new commit, never by rewriting something that might already be shared. `dnsctl.py rollback` is that pattern, wired specifically for `dnsconfig.js`.

---

## 3. Review and merge the rollback PR

Same lifecycle as every other change so far, approval included: a rollback is a change to production like any other, so someone else reviews it too.

```sh
python3 scripts/dnsctl.py status
python3 scripts/dnsctl.py review <rollback-PR#>
# a neighbour (or the facilitator, or Sensei once you have reviewed someone else's) approves: python3 scripts/dnsctl.py approve <rollback-PR#>
python3 scripts/dnsctl.py merge <rollback-PR#>
```

---

## 4. Confirm it's actually gone

```sh
python3 scripts/dnsctl.py validate <rollback-PR#>
dig @dns-server $USER-app.dojo.test A +short   # should return nothing now
```

`validate` waits for the "DNS Apply" CI run and confirms live PowerDNS matches `dnsconfig.js` — same command you used in Lab 4, working just as well on a rollback as on a forward change.

---

## 5. (Optional) Bring it back

If you want your record back for later labs, just repeat Lab 3 or Lab 4's "add a record" flow again — there's nothing special about a rolled-back record that stops you from re-adding it:

```sh
python3 scripts/dnsctl.py record add $USER-app.dojo.test --type A --value 203.0.113.30
python3 scripts/dnsctl.py submit "Re-add $USER-app"
```

---

## Recap

- `dnsctl.py history` (or `git log -- dnsconfig.js`) shows what's changed and when.
- `dnsctl.py rollback <PR#>` undoes a merged change via a **new** PR with an inverse diff — never a rewrite of `main`. It's the DNS-flavored version of `git revert`.
- `dnsctl.py validate` is how you confirm a change — forward or backward — actually reached live PowerDNS, instead of trusting CI's word for it.

**Next:** [lab6.md](lab6.md) — resolving a merge conflict in `dnsconfig.js`.
