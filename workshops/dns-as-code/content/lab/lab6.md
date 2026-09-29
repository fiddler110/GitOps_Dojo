# Lab 6 — Merge Conflicts in `dnsconfig.js`

**Part 2.** What happens when git can't automatically combine two changes to the same DNS record — and why that's a bigger deal here than in a roster file.

This lab creates its own throwaway local branches and never pushes them, so it's safe to run regardless of what you did in the other labs and won't interfere with anyone else's work.

```sh
cd ~/lab/dns-as-code
git checkout main
git pull
```

> **Starting here?** This lab needs the shared repo cloned to `~/lab/dns-as-code`. Run `lab-prep 6` to set that up; it's safe to run even if you did the earlier labs.

---

## Part A — Causing and resolving a conflict

A conflict happens when two branches change the *same line* in different ways. Normally that's two different people; here, you'll play both parts yourself so you can see it end to end without needing a partner.

```sh
git checkout main
git checkout -b conflict-a
```

Edit `dnsconfig.js` and change the `www` record's IP:

```js
A("www", "203.0.113.40"),
```

```sh
git add dnsconfig.js
git commit -m "conflict-a: repoint www"
git checkout main
git checkout -b conflict-b
```

Now, on this second branch, edit **the same line** to a different value:

```js
A("www", "203.0.113.50"),
```

```sh
git add dnsconfig.js
git commit -m "conflict-b: repoint www"
```

Now try to bring both changes together:

```sh
git merge conflict-a
```

Git stops and reports a conflict. Look at the file:

```sh
batcat dnsconfig.js
```

You'll see something like:

```js
A("www", "203.0.113.50"),
```

wrapped in git's markers:

```text
<<<<<<< HEAD
	A("www", "203.0.113.50"),
=======
	A("www", "203.0.113.40"),
>>>>>>> conflict-a
```

- Everything between `<<<<<<< HEAD` and `=======` is your current branch's version.
- Everything between `=======` and `>>>>>>> conflict-a` is the incoming branch's version.

**Resolve it:** decide which value to keep (or a third one entirely), and delete the `<<<<<<<`/`=======`/`>>>>>>>` markers yourself — git won't do this part for you. For example, keep just:

```js
A("www", "203.0.113.40"),
```

---

## Part B — Don't just commit: preview first

This is the one step that has no equivalent in a plain git conflict, and it's the important part of this lab. Before finishing the merge, run:

```sh
dnscontrol preview
```

Git's conflict resolution only checked that the file has no leftover `<<<<<<<`/`=======`/`>>>>>>>` markers — it has no idea whether the JavaScript is still syntactically valid, whether you left a stray comma, or whether you accidentally kept *both* lines instead of picking one (which would leave two `A` records with the same name — legal DNS, almost never what you meant). `preview` is what actually tells you the resolved file makes sense. Confirm it shows a clean, expected diff before you go any further.

**Rule of thumb: always run `dnscontrol preview` after resolving any conflict in `dnsconfig.js`, before you commit the merge — not just here, in a real repo too.** A bad resolution that looks fine to git can still be wrong DNS.

Now finish the merge:

```sh
git add dnsconfig.js
git commit
```

Git pre-fills a merge commit message — accepting the default is fine.

If you ever want to back out of a conflict entirely and start over:

```sh
git merge --abort
```

(No need to run that now — your merge is already resolved.)

Clean up — none of this was ever pushed, so deleting the branches is all that's needed:

```sh
git checkout main
git branch -D conflict-a conflict-b
```

---

## Why this is higher-stakes than it looks

A merge conflict in a roster file, resolved wrong, means someone's job title is momentarily incorrect. A merge conflict in `dnsconfig.js`, resolved wrong, can silently point a real hostname at the wrong IP, or drop an `MX`/`TXT` record that mail delivery depended on — and git will happily let you commit that, because the *markers* were removed correctly even if the *content* is wrong. Four things stand between a bad resolution and production DNS in a real setup like this one:

- **You, previewing locally** before you push — Part B, above.
- **The `pre-push` git hook** (`.githooks/pre-push`, enabled by `dnsctl.py setup` in [lab4.md](lab4.md)) — runs `dnscontrol preview` automatically before anything reaches `main` from your machine, and blocks the push if it fails.
- **CI's "DNS Preview" check** — previews the PR merged into `main` and posts the diff for a human to actually read before merging. Branch protection won't let a PR merge until it passes.
- **A reviewer** — someone other than the author has to approve the PR, reading the same diff and preview.

None of those replace reading the diff yourself — they're a safety net, not a substitute for understanding what you just resolved.

---

## Recap

- **Conflict:** git marks `<<<<<<<`/`=======`/`>>>>>>>` around the disputed lines; resolve by hand, then `git add` + `git commit`. `git merge --abort` bails out entirely if needed.
- **Always `dnscontrol preview` after resolving, before committing the merge** — git validates the markers are gone; only `preview` validates the DNS is still correct.
- **Undoing an already-merged change:** don't hand-edit it back — `dnsctl.py rollback` (or plain `git revert`), covered in [lab5.md](lab5.md).

You've now covered DNS as code in your own zone (Labs 1-2), the change process on a shared zone (Lab 3), automating it (Lab 4), investigating and rolling back history (Lab 5), and resolving conflicts safely (this lab). See [README.md](README.md) for the quick reference, and [cheat-sheet.md](cheat-sheet.md) for the full command list.
