# Lab 5 — Investigating & Rolling Back History

**Part 2.** "Who changed this, when, and how do I undo it safely?" — the tools for answering that without hand-editing `dnsconfig.js` back to what it used to be. This lab uses `dnsctl.py`, so run [lab4.md](lab4.md)'s setup steps first if you haven't (`python3 scripts/dnsctl.py doctor` should be clean). You'll also need a merged PR to work with — Lab 3's is exactly right; grab its PR number if you wrote it down.

```sh
cd ~/lab/dns-as-code
git checkout main
git pull
git status   # should be clean
```

> **Starting here?** This lab rolls back your Lab 3 record, so it needs that pull request merged. `dojo prep 5` clones the repo and opens the pull request; someone else still has to approve it before you merge it: a neighbour, or Sensei (`dojo sensei approve`, once you have reviewed a pull request that isn't yours: Lab 3 step 6; `dojo sensei approve --force` skips the wait). Safe to run even if you did the earlier labs.

---

## 1. Browse DNS history

`dnsctl.py history` lists every merge to `main` that touched `dnsconfig.js`, newest first, with the commit, date, and PR number: a filtered `git log` purpose-built for this repo. The raw-git equivalent, if you ever need it without the wrapper:

```text
git log --oneline -- dnsconfig.js
git show <commit-hash>              # exactly what one commit changed
```

**Your turn:**

Before you run it, predict: which entry is your Lab 3 PR, and where in the list will it sit?

```sh
python3 scripts/dnsctl.py history
git log --oneline -- dnsconfig.js
```

<!-- dojo-reveal: Results of history -->

- Find your Lab 3 PR in the list (the one that added your `A` record). The raw `git log` shows the same commits.

<!-- /dojo-reveal -->

---

## 2. Roll it back

`dnsctl.py rollback <PR#>` is worth understanding, not just running. It:

1. Creates a **new branch** and runs `git revert` on your original commit: a new commit that undoes the change, not a rewrite of history.
2. Runs `dnscontrol preview` automatically and shows you the diff, then asks you to confirm it looks like the exact inverse of the original change.
3. Once you confirm, pushes the branch and **opens a new PR**. Rollback never touches `main` directly, same as every other change to the shared zone.

This is the DNS-as-code equivalent of `git revert` from Git Fundamentals: undo by adding a new commit, never by rewriting something that might already be shared. `dnsctl.py rollback` is that pattern, wired specifically for `dnsconfig.js`.

```text
python3 scripts/dnsctl.py rollback <PR#>
```

**Your turn:**

Before you run it, predict: what should the preview diff look like compared with your original change?

```sh
python3 scripts/dnsctl.py rollback <your-lab3-pr-number>
```

<!-- dojo-reveal: Results of rollback -->

- The preview shows a single `- DELETE` for your record: the exact inverse of your Lab 3 `+ CREATE`.
- After you confirm, a new rollback PR opens.

<!-- /dojo-reveal -->

**If it stops with `CONFLICT (content): Merge conflict in dnsconfig.js`:** a classmate's record was merged on the line next to yours, so git can't tell which lines to keep. Open `dnsconfig.js` in your editor, delete only **your** record and the three marker lines (`<<<<<<<`, `=======`, `>>>>>>>`), and leave theirs. Then finish the rollback by hand, as the error message says:

```sh
git add dnsconfig.js
python3 scripts/dnsctl.py preview      # one DELETE: your record, nothing else
python3 scripts/dnsctl.py submit "Revert: my Lab 3 record"
```

You're still on the `dns/revert-...` branch, so `submit` commits there and opens the rollback PR. Lab 6 goes into conflicts properly.

---

## 3. Review and merge the rollback PR

Same lifecycle as every other change so far, approval included: a rollback is a change to production like any other, so someone else reviews it too.

**Your turn:**

```sh
python3 scripts/dnsctl.py status
python3 scripts/dnsctl.py review <rollback-PR#>
# a neighbour (or the facilitator, or Sensei once you have reviewed someone else's) approves: python3 scripts/dnsctl.py approve <rollback-PR#>
python3 scripts/dnsctl.py merge <rollback-PR#>
```

---

## 4. Confirm it's actually gone

`validate` waits for the "DNS Apply" CI run and confirms live PowerDNS matches `dnsconfig.js`: the same command you used in Lab 4, working just as well on a rollback as on a forward change.

**Your turn:**

Before you run it, predict: what will `dig` print now?

```sh
python3 scripts/dnsctl.py validate <rollback-PR#>
dig @dns-server $USER-app.dojo.test A +short
```

<!-- dojo-reveal: Results of validate and dig -->

- `validate` reports the zone matches `dnsconfig.js`, and `dig` returns nothing now.

<!-- /dojo-reveal -->

---

## 5. (Optional) Bring it back

If you want your record back for later labs, just repeat Lab 3 or Lab 4's "add a record" flow again. There's nothing special about a rolled-back record that stops you from re-adding it:

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

---

## Challenge c2 (bonus)

Only when your class has achievements on (you see a score on your landing page). A challenge is a goal with no steps, in
a repo of your own, for extra points. Start it in the terminal:

```sh
dojo challenge start c2
cd ~/lab/challenge-cutover
```

That makes your own repo `$USER/challenge-cutover`, clones it to `~/lab/challenge-cutover` and shows your brief. The brief is
saved as `~/challenge-c2.md` with your own names filled in; read it again any time with `glow ~/challenge-c2.md`. When you think
it's done:

```sh
dojo check c2
```

A wrong answer costs nothing. `dojo check hint c2` gives a hint for part of the points (hints already used stay used).

**Start over.** `dojo challenge reset c2` deletes `~/lab/challenge-cutover` (including any uncommitted work),
builds a fresh copy and clones it, as often as you like. Note that this challenge pushes to your own zone `$USER.dojo.test`, the same one `~/lab/my-zone` pushes to: whichever you push last wins.

## The Cutover

`app` is moving to a new server, and `www` should stop being a separate address and become an alias of `app`. Do it in
one commit, with no other change to the zone.

**End result (what the check looks for)**

- Work in your own repo `<you>/challenge-cutover`, and push to your own zone `<you>.dojo.test`.
- `app` is an A record at the new server's address given in your brief.
- `www` is a CNAME to `app.<you>.dojo.test.` and no longer an A record.
- Nothing else changed: the apex A and `mail` are as seeded.

