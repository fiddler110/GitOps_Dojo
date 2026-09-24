# Lab 4 — Investigating & Rolling Back History

**Optional.** "Who changed this, when, and how do I undo it safely?" — the tools for answering that without hand-editing `dnsconfig.js` back to what it used to be. This lab uses `dnsctl.py`, so run [lab3.md](lab3.md)'s setup steps first if you haven't (`python3 scripts/dnsctl.py doctor` should be clean). You'll also need a merged PR to work with — Lab 1's is exactly right; grab its PR number if you wrote it down.

```sh
git checkout main
git pull
git status   # should be clean
```

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

Find your Lab 1 PR in the list (the one that added your `A` record).

---

## 2. Roll it back

```sh
python3 scripts/dnsctl.py rollback <your-lab1-pr-number>
```

Read what happens carefully — this is worth understanding, not just running:

1. It creates a **new branch** and runs `git revert` on your original commit — a new commit that undoes the change, not a rewrite of history.
2. It runs `dnscontrol preview` automatically and shows you the diff, then asks you to confirm it looks like the exact inverse of the original change.
3. Once you confirm, it pushes the branch and **opens a new PR** — rollback never touches `main` directly, same as every other change in this system.

This is the DNS-as-code equivalent of `git revert` from Git Fundamentals: undo by adding a new commit, never by rewriting something that might already be shared. `dnsctl.py rollback` is that pattern, wired specifically for `dnsconfig.js`.

---

## 3. Review and merge the rollback PR

Same lifecycle as every other change so far:

```sh
python3 scripts/dnsctl.py status
python3 scripts/dnsctl.py review <rollback-PR#>
python3 scripts/dnsctl.py merge <rollback-PR#>
```

---

## 4. Confirm it's actually gone

```sh
python3 scripts/dnsctl.py validate <rollback-PR#>
dig @dns-server yourname.dojo.test A +short   # should return nothing now
```

`validate` waits for the "DNS Apply" CI run and confirms live PowerDNS matches `dnsconfig.js` — same command you used in Lab 3, working just as well on a rollback as on a forward change.

---

## 5. (Optional) Bring it back

If you want your record back for later labs, just repeat Lab 1 or Lab 3's "add a record" flow again — there's nothing special about a rolled-back record that stops you from re-adding it:

```sh
python3 scripts/dnsctl.py record add yourname.dojo.test --type A --value 203.0.113.30
python3 scripts/dnsctl.py submit "Re-add A record for yourname"
```

---

## Recap

- `dnsctl.py history` (or `git log -- dnsconfig.js`) shows what's changed and when.
- `dnsctl.py rollback <PR#>` undoes a merged change via a **new** PR with an inverse diff — never a rewrite of `main`. It's the DNS-flavored version of `git revert`.
- `dnsctl.py validate` is how you confirm a change — forward or backward — actually reached live PowerDNS, instead of trusting CI's word for it.

**Next:** [lab5.md](lab5.md) — resolving a merge conflict in `dnsconfig.js`.
