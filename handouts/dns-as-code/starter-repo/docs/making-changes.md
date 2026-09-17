# Making a DNS change

The day-to-day workflow for adding, editing, or removing a record in
`dojo.test`. For record syntax, see [record-types.md](record-types.md).

## The workflow

```sh
git checkout main
git pull
git checkout -b add-yourname-record

# edit dnsconfig.js

dnscontrol preview      # sanity-check the diff BEFORE pushing anything

git add dnsconfig.js
git commit -m "Add A record for yourname"
git push -u origin add-yourname-record
```

Then, in the browser:

1. Go to your repo on `github.com` — GitHub will usually show a banner
   offering to open a pull request for the branch you just pushed. Open
   one into `main`.
2. **Read the diff carefully.** There's no CI wired up against a
   laptop-local PowerDNS container (a GitHub-hosted runner can't reach
   `127.0.0.1` on your machine), so unlike the live workshop, nothing
   posts a "DNS Preview" comment automatically here — the `dnscontrol
   preview` output you already read locally *is* your review. Re-run it
   if it's been more than a few minutes since you last checked.
3. Merge the pull request yourself (**Squash and merge** or **Merge pull
   request** both work fine for solo practice).
4. Back in the terminal: pull `main` and apply the change for real —
   this is the one step CI did for you in the workshop, so now you run it
   by hand:
   ```sh
   git checkout main
   git pull
   dnscontrol push
   ```
5. Verify the record is live:
   ```sh
   dig @127.0.0.1 -p 5353 dojo.test A +short
   ```
6. Run `dnscontrol preview` one more time — it should report zero
   corrections, confirming PowerDNS now matches `dnsconfig.js` exactly.

See `../01-local-powerdns-stack.md` in the handout for how to wire up
real GitHub Actions CI against this stack, if you want the full
merge-triggers-apply experience later.

## Adding a new record

Add a new line inside the `D("dojo.test", ...)` block, near other records
of the same type (keeps the file scannable). Example — adding an A record:

```js
A("yourname", "203.0.113.30"),
```

See [record-types.md](record-types.md) for the full set of record types
and their arguments.

## Editing an existing record

Find the line for that record and change its value/TTL in place.
dnscontrol diffs by exact match, so `preview` will show it as a paired
`DELETE` (old value) + `CREATE` (new value) — that's expected, not a sign
of a problem.

## Removing a record

Delete the line from `dnsconfig.js`. `preview` will show a `DELETE`
correction for it — confirm it's the only thing that shows up before
merging.

## Common mistakes to avoid

- **Forgetting the trailing dot** on CNAME/MX targets (`dojo.test` vs
  `dojo.test.`). dnscontrol usually catches this as a config error at
  `preview` time, but always double-check.
- **Editing `dnsconfig.js` without running `preview` first.** The whole
  point of DNS-as-Code is seeing the diff before it happens — always run
  it locally before opening a PR, and always read the diff again before
  merging.
- **Merging a PR whose diff looks unexpected.** If you don't understand
  every line, don't merge — investigate first.
- **Forgetting to run `dnscontrol push` after merging.** Without CI
  wired up (see above), merging the PR only updates `dnsconfig.js` on
  `main` — it does *not* touch PowerDNS by itself.
