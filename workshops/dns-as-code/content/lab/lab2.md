# Lab 2 — Editing, Removing & Catching Mistakes Before You Commit

**Optional.** Lab 1 only ever *added* a record. Real changes also edit and remove them — and this lab covers the single most common mistake in `dnsconfig.js`, and how to catch it before it ever reaches a commit.

Do this from your `dns-as-code` clone, starting on `main` with your Lab 1 record already merged:

```sh
git checkout main
git pull
```

---

## Part A — Edit your own record

Open `dnsconfig.js` and change the IP on the `A` record you added in Lab 1:

```js
A("yourname", "203.0.113.31"),   // was .30
```

Run a preview *before* touching git:

```sh
dnscontrol preview
```

Look closely at the output. You'll see **two corrections**, not one — a `DELETE` for the old `203.0.113.30` value and a `CREATE` for the new `203.0.113.31` value. dnscontrol diffs by exact match; it has no concept of "modify a record in place," only "remove the old line, add the new one." That's expected every time you edit an existing record's value — not a sign something's wrong, as long as both halves point at the record you actually meant to change.

---

## Part B — Try an idea, then discard it (uncommitted)

Add a scratch record you're not sure you want to keep — a `TXT` record on your name:

```js
TXT("yourname-scratch", "just testing"),
```

```sh
dnscontrol preview
```

You'll now see three corrections: your Part A edit, plus a `CREATE` for this new `TXT` record. Decide you don't want it after all. Since nothing is staged or committed yet, you can throw it away the same way you would in Git Fundamentals:

```sh
git diff dnsconfig.js       # see exactly what's uncommitted right now
git restore dnsconfig.js    # discard ALL uncommitted changes to this file — careful, this also undoes Part A
```

That undid *both* Part A and Part B, since both were uncommitted edits to the same file. Redo Part A's IP change now (`203.0.113.31`, same as above) — you'll need it for Part C.

The lesson: `dnscontrol preview` is safe to run against half-finished edits as often as you like. Nothing is real until you `push`, and nothing is even committed until you `git commit` — use that freedom to try things and back out cleanly.

---

## Part C — Add, then remove, and see a DELETE on its own

Branch first, same as Lab 1 — everything from here happens off `main`, never on it:

```sh
git checkout -b edit-yourname-record
```

Add the `TXT` scratch record again, and this time commit it:

```sh
git add dnsconfig.js
git commit -m "Add yourname A record IP change + scratch TXT record"
```

Now delete the `TXT` line from `dnsconfig.js` entirely (leave your IP-edited `A` record in place) and preview again:

```sh
dnscontrol preview
```

This time you'll see a lone `DELETE` for the `TXT` record — the mirror image of the `CREATE` you saw when you added it. Removing a record from `dnsconfig.js` is always a `DELETE`, whether you commit it as a separate step (like here) or never let it reach a commit at all (like Part B).

Commit and push both changes:

```sh
git add dnsconfig.js
git commit -m "Remove scratch TXT record"
git push -u origin edit-yourname-record
```

Open a pull request the same way as Lab 1 (**Open Forgejo** from the landing page). Confirm the "DNS Preview" comment shows only the IP `DELETE`+`CREATE` pair — the scratch `TXT` record should be invisible, since it never survived past your local history: two commits landed, but they net out to one clean change. Merge it, then confirm:

```sh
git checkout main
git pull
dig @dns-server yourname.dojo.test A +short   # should show .31
```

---

## Part D — The trailing-dot mistake

This is the single most common mistake in `dnsconfig.js`: a `CNAME` or `MX` target that's missing its trailing dot. Reproduce it on purpose, locally, without ever committing it.

Add this line near the existing `CNAME("app", ...)` record:

```js
CNAME("yourname-broken", "dojo.test"),   // missing the trailing dot — on purpose
```

```sh
dnscontrol preview
```

dnscontrol catches this as a **config error**, not a silent bad record — read the message; it's specific about the missing dot. This is exactly why Lab 1 and Part A both told you to preview *before* committing: catching this locally costs you nothing, while catching it after a merge means rolling back (Lab 4).

Fix it and confirm it now previews cleanly as a real correction:

```js
CNAME("yourname-broken", "dojo.test."),   // fixed
```

```sh
dnscontrol preview
```

Then throw the whole experiment away — you don't need this record for anything else:

```sh
git restore dnsconfig.js
git status   # confirm clean
```

---

## Recap

- Editing a record's value always previews as a paired `DELETE` + `CREATE` — dnscontrol has no in-place "modify."
- Removing a record previews as a lone `DELETE`.
- Nothing is real until `dnscontrol push`; nothing is even committed until `git commit` — use `dnscontrol preview` and `git restore` freely while you're still deciding.
- A missing trailing dot on a `CNAME`/`MX` target is the most common mistake here — `preview` catches it as a config error before it ever touches PowerDNS or a commit.

**Next:** [lab3.md](lab3.md) — the same workflow, automated with `dnsctl.py`.
