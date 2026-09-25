# Making a DNS change

The day-to-day workflow for adding, editing, or removing a record in
`dojo.test`. For record syntax, see [record-types.md](record-types.md).

## The workflow

```sh
git checkout main
git pull
git checkout -b add-$USER-app

# edit dnsconfig.js

dnscontrol preview      # sanity-check the diff BEFORE pushing anything

git add dnsconfig.js
git commit -m "Add $USER-app.dojo.test"
git push -u origin add-$USER-app
```

`main` is protected, so you always push a branch. `dnscontrol push` from
here is refused for `dojo.test`: CI applies it after the merge.

Then, in the browser:

1. Click **Open Forgejo** on the workshop landing page (opens signed in as
   you) and open a pull request from your branch.
2. **Read the diff carefully.** Within a few seconds, a "DNS Preview"
   comment appears on the PR with the exact `dnscontrol preview` diff —
   CI running the same command you already ran locally, on your branch
   merged into the current `main` (`.forgejo/workflows/dns-preview.yml`). Confirm it shows only the
   record(s) you intended to change — nothing else. If it shows unrelated
   deletions, something is wrong with your edit (a missing comma, a
   duplicated block) — fix it before merging.
3. Get it reviewed: someone other than you reads the diff and the
   preview comment and approves the PR. `main` needs one approval and a
   passing DNS Preview check before the merge button works.
4. Merge the pull request. This triggers
   `.forgejo/workflows/dns-apply.yml`, which runs `dnscontrol push` for
   you — you don't need to run it yourself. Give it a few seconds.
5. Back in the terminal: pull `main` and verify the record is live:
   ```sh
   git checkout main
   git pull
   dig @dns-server $USER-app.dojo.test A +short
   ```
6. Run `dnscontrol preview` one more time — it should report zero
   corrections, confirming PowerDNS now matches `dnsconfig.js` exactly
   (CI already applied it; this just confirms it from the terminal).

## Adding a new record

Add a new line inside the `D("dojo.test", ...)` block, near other records
of the same type (keeps the file scannable). Example — adding an A record:

```js
A("student07-app", "203.0.113.30"),   // your username, so it's unique
```

See [record-types.md](record-types.md) for the full set of record types
and their arguments.

## Editing an existing record

Find the line for that record and change its value/TTL in place.
`preview` shows it as one `MODIFY` correction, old value → new value.

## Removing a record

Delete the line from `dnsconfig.js`. `preview` will show a `DELETE`
correction for it — confirm it's the only thing that shows up before
merging.

## Common mistakes to avoid

- **Forgetting the trailing dot** on CNAME/MX targets (`dojo.test` vs
  `dojo.test.`). dnscontrol catches this as a config error at `preview`
  time, but always double-check.
- **Editing `dnsconfig.js` without running `preview` first.** The whole
  point of DNS-as-Code is seeing the diff before it happens — always run
  it locally before opening a PR, and always read the diff again before
  merging.
- **Merging a PR whose diff looks unexpected.** If you don't understand
  every line, don't merge — ask, or investigate first.
