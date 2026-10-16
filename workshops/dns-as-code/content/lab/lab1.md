# Lab 1 — Your Own Zone

**Part 1.** By the end of this lab you'll have created your own DNS zone from a config file, checked it's really live with `dig`, and added, changed and removed records, catching a mistake before it reached the server. Everything here happens in **your own zone**, `<your-username>.dojo.test`: nobody else's config touches it, so experiment freely.

---

## 1. Look around

Your zone's repo is already set up for you. Before you open anything, here is what's in it:

- `dnsconfig.js` is the whole zone, as code. The `D("studentXX.dojo.test", ...)` block (with your username) lists every record in it. `A("www", "203.0.113.10")` means "`www.studentXX.dojo.test` has the address `203.0.113.10`": names inside the block are relative to the zone, and `@` means the zone itself.
- The `SOA` and `NAMESERVER` lines are bookkeeping every zone needs. Leave them alone.
- `creds.json` tells `dnscontrol` where the PowerDNS API is and which key to use: `$DNS_API_KEY`, your own key, which your terminal sets for you. It changes only your zone, so the file itself holds no secret.
- It's a git repo with one commit and no remote: your history stays on your machine.

`203.0.113.0/24` is IETF-reserved "documentation" address space (RFC 5737), so none of these addresses can ever be real.

**Your turn:**

Before you run it, predict: how many commits will `git log` show, and which records do you expect to see in `dnsconfig.js`?

```sh
cd ~/lab/my-zone
ls
batcat dnsconfig.js
git log --oneline
```

<!-- dojo-reveal: Results of looking around the repo -->

- You see `dnsconfig.js`, `creds.json` and friends, the zone's records in the `D(...)` block, and one commit.

<!-- /dojo-reveal -->

---

## 2. Preview

`dnscontrol preview` compares `dnsconfig.js` with what PowerDNS is serving right now and prints the difference. It changes nothing.

```text
dnscontrol preview
```

**Your turn:**

Your zone doesn't exist on the server yet. Before you run it, predict: what can `preview` possibly say?

```sh
dnscontrol preview
```

<!-- dojo-reveal: Results of dnscontrol preview -->

- It reports that the zone **will be created** when you push, and nothing has changed on the server.

<!-- /dojo-reveal -->

---

## 3. Push, then check it's live

`dnscontrol push` applies the difference that `preview` showed. Don't trust its exit code alone: ask the DNS server directly with `dig`.

```text
dig @<server> <name> <type> +short
```

`$USER` is your username, so the commands below ask for `www.studentXX.dojo.test` and so on. `@dns-server` asks the lab's PowerDNS directly. After the push, a second `preview` should report **0 corrections**: the server matches the file exactly. That's the loop for every change: **edit → preview → push → verify → preview again**.

**Your turn:**

Before you run it, predict: what will each `dig` print, and how many corrections will the final `preview` report?

```sh
dnscontrol push
dig @dns-server www.$USER.dojo.test A +short
dig @dns-server $USER.dojo.test TXT +short
dnscontrol preview
```

<!-- dojo-reveal: Results of dnscontrol push -->

- This time `dnscontrol` creates the zone and every record in it.
- The `dig` commands return the address and TXT value from your file.
- The last `preview` reports **0 corrections**.

<!-- /dojo-reveal -->

Open the **DNS Zones** card from the workshop landing page. Your zone is listed with its records, next to your classmates' zones and the shared `dojo.test`.

---

## 4. Add records

You'll add four records. Here is what each type means:

- `A` maps a name to an IPv4 address.
- `CNAME` makes a name an alias of another name. Targets are full names ending in a dot.
- `MX` says which server receives mail for the zone, with a priority (lower wins).

See `docs/record-types.md` in `my-zone`, or the [cheat sheet](cheat-sheet.md), for more record types.

Open `my-zone/dnsconfig.js` in your editor (VS Code: file explorer, save with `Ctrl+S` / `Cmd+S`; or `nano dnsconfig.js`, then `Ctrl+O`, `Enter`, `Ctrl+X`) and add these lines inside the `D(...)` block, after the `TXT` line (`studentXX` is your username; the lab reader fills it in for you):

```js
	A("app", "203.0.113.30"),
	CNAME("docs", "www.studentXX.dojo.test."),
	MX("@", 10, "mail.studentXX.dojo.test."),
	A("mail", "203.0.113.20"),
```

**Your turn:**

Before you run it, predict: how many changes will `preview` list, and of what kind?

```sh
dnscontrol preview
```

<!-- dojo-reveal: Results of dnscontrol preview -->

- You see four `+ CREATE` lines, one per new record, under a `± BATCHED CHANGE/CREATEs` heading (dnscontrol sends them in one API call).
- If you see a `MODIFY` or `DELETE` too, you edited more than you meant to.

<!-- /dojo-reveal -->

Push it and check. Predict first: what will the `docs` lookup return, given it's a CNAME?

```sh
dnscontrol push
dig @dns-server app.$USER.dojo.test A +short
dig @dns-server docs.$USER.dojo.test A +short   # follows the CNAME to www
dig @dns-server $USER.dojo.test MX +short
```

<!-- dojo-reveal: Results of dnscontrol push -->

- `docs` answers with `www`'s address, because the CNAME is followed.
- Glance at the DNS Zones tab: the new records are highlighted.

<!-- /dojo-reveal -->

---

## 5. Change a record

Editing a value in place is the simplest change: `dnscontrol` sees one record whose content differs and reports a single `± MODIFY` line with the old and new values.

In `dnsconfig.js`, change the `app` address from `.30` to `.31`:

```js
	A("app", "203.0.113.31"),
```

**Your turn:**

Before you run it, predict: will `preview` show a `CREATE`, a `MODIFY` or a `DELETE`?

```sh
dnscontrol preview
```

<!-- dojo-reveal: Results of dnscontrol preview -->

- One `± MODIFY` line with the old and new values. Push it and `dig` it again.

<!-- /dojo-reveal -->

---

## 6. Remove a record

`dnscontrol` makes the zone match the file exactly, including what's *not* in it. So removing a line from the file removes the record from the server.

In `dnsconfig.js`, delete the `CNAME("docs", ...)` line entirely.

**Your turn:**

Before you run it, predict: what will `preview` show, and what will `dig` return for `docs` after the push?

```sh
dnscontrol preview
```

<!-- dojo-reveal: Results of dnscontrol preview -->

- A lone `- DELETE`.

<!-- /dojo-reveal -->

Push it, and check:

```sh
dnscontrol push
dig @dns-server docs.$USER.dojo.test A +short
```

<!-- dojo-reveal: Results of dnscontrol push -->

- `dig` now returns nothing.

<!-- /dojo-reveal -->

Save this state in git, so you can always get back to it:

```sh
git diff                 # what changed since the first commit
git add dnsconfig.js
git commit -m "Add app, mail and MX records"
```

---

## 7. The trailing-dot mistake

The most common mistake in `dnsconfig.js` is a `CNAME` or `MX` target without its trailing dot. Catching it at preview costs nothing; catching it after it's live costs an outage.

Open `dnsconfig.js` and make the mistake on purpose, adding this line:

```js
	CNAME("broken", "www.studentXX.dojo.test"),   // no trailing dot, on purpose
```

**Your turn:**

Before you run it, predict: will `preview` create the record, or refuse?

```sh
dnscontrol preview
```

<!-- dojo-reveal: Results of dnscontrol preview -->

- `dnscontrol` refuses the file with an error that names the record and says the target `must end with a (.)`. Nothing reached PowerDNS.

<!-- /dojo-reveal -->

Throw the experiment away with git. `git restore` discards uncommitted edits, so `preview` and `restore` together let you try anything safely: nothing is real until you `push`.

```sh
git restore dnsconfig.js   # back to your last commit
dnscontrol preview         # 0 corrections again
```

Its cousin is the opposite mistake: a record **name** that already contains the zone. Inside `studentXX.dojo.test`, a name is relative to the zone, so writing the whole hostname gets the zone added a second time. Add this line to `dnsconfig.js`:

```js
	A("www.studentXX.dojo.test", "203.0.113.55"),   // the label should just be "www"
```

**Your turn:**

Predict what the error will say, then run:

```sh
dnscontrol preview
```

<!-- dojo-reveal: Results of dnscontrol preview -->

- The error shows `www.studentXX.dojo.test.studentXX.dojo.test.` and says it repeats the domain.

<!-- /dojo-reveal -->

Throw this one away too:

```sh
git restore dnsconfig.js
```

---

## Checkpoint

Before moving on, be ready to show or say:

- `dig` output for a record you added, straight from `dns-server`.
- What `± MODIFY`, `+ CREATE` and `- DELETE` in a preview each mean.
- Why removing a line from `dnsconfig.js` removes the record from the server.

**Next:** [lab2.md](lab2.md) covers what happens when someone changes your zone outside the code. After that, Part 2 ([lab3.md](lab3.md)) is the shared zone, where you can't push at all.
