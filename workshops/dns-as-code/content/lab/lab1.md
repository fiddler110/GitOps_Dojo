# Lab 1 — Your Own Zone

**Required. Part 1.** By the end of this lab you'll have created your own DNS zone from a config file, checked it's really live with `dig`, and added, changed and removed records, catching a mistake before it reached the server. Everything here happens in **your own zone**, `<your-username>.dojo.test`: nobody else's config touches it, so experiment freely.

---

## 1. Look around

Your zone's repo is already set up for you:

```sh
cd ~/lab/my-zone
ls
batcat dnsconfig.js
git log --oneline
```

- `dnsconfig.js` is the whole zone, as code. The `D("studentXX.dojo.test", ...)` block (with your username) lists every record in it. `A("www", "203.0.113.10")` means "`www.studentXX.dojo.test` has the address `203.0.113.10`": names inside the block are relative to the zone, and `@` means the zone itself.
- The `SOA` and `NAMESERVER` lines are bookkeeping every zone needs. Leave them alone.
- `creds.json` tells `dnscontrol` where the PowerDNS API is and which key to use.
- It's a git repo with one commit and no remote: your history stays on your machine.

`203.0.113.0/24` is IETF-reserved "documentation" address space (RFC 5737), so none of these addresses can ever be real.

---

## 2. Preview

```sh
dnscontrol preview
```

`preview` compares `dnsconfig.js` with what PowerDNS is serving right now and prints the difference. It changes nothing. Your zone doesn't exist on the server yet, so all it can say is that the zone **will be created** when you push.

---

## 3. Push, then check it's live

```sh
dnscontrol push
```

This time `dnscontrol` creates the zone and every record in it. Don't trust the exit code alone. Ask the DNS server:

```sh
dig @dns-server www.$USER.dojo.test A +short
dig @dns-server $USER.dojo.test TXT +short
```

`$USER` is your username, so these ask for `www.studentXX.dojo.test` and so on. `@dns-server` asks the lab's PowerDNS directly.

Now preview again:

```sh
dnscontrol preview
```

It reports **0 corrections**: the server matches the file exactly. That's the loop for every change: **edit → preview → push → verify → preview again**.

Open the **DNS Zones** card from the workshop landing page. Your zone is listed with its records, next to your classmates' zones and the shared `dojo.test`.

---

## 4. Add records

Open `dnsconfig.js` and add these lines inside the `D(...)` block, after the `TXT` line (`studentXX` is your username; the lab reader fills it in for you):

```js
	A("app", "203.0.113.30"),
	CNAME("docs", "www.studentXX.dojo.test."),
	MX("@", 10, "mail.studentXX.dojo.test."),
	A("mail", "203.0.113.20"),
```

- `A` maps a name to an IPv4 address.
- `CNAME` makes a name an alias of another name. Targets are full names ending in a dot.
- `MX` says which server receives mail for the zone, with a priority (lower wins).

See `docs/record-types.md` in `my-zone`, or the [cheat sheet](cheat-sheet.md), for more record types.

Pick whichever editor suits you:

- **VS Code:** open `my-zone/dnsconfig.js` from the file explorer, edit, and save with `Ctrl+S` (`Cmd+S` on a Mac).
- **nano:** `nano dnsconfig.js`, edit, then `Ctrl+O`, `Enter`, `Ctrl+X` to save and exit.

Then:

```sh
dnscontrol preview
```

You should see four `+ CREATE` lines, one per new record, under a `± BATCHED CHANGE/CREATEs` heading (dnscontrol sends them in one API call). If you see a `MODIFY` or `DELETE` too, you edited more than you meant to. Push it and check:

```sh
dnscontrol push
dig @dns-server app.$USER.dojo.test A +short
dig @dns-server docs.$USER.dojo.test A +short   # follows the CNAME to www
dig @dns-server $USER.dojo.test MX +short
```

Glance at the DNS Zones tab: the new records are highlighted.

---

## 5. Change a record

Change the `app` address from `.30` to `.31`:

```js
	A("app", "203.0.113.31"),
```

```sh
dnscontrol preview
```

An edit shows as one `± MODIFY` line with the old and new values. Push it and `dig` it again.

---

## 6. Remove a record

Delete the `CNAME("docs", ...)` line entirely, then:

```sh
dnscontrol preview
```

A lone `- DELETE`. Removing a line from the file removes the record from the server: `dnscontrol` makes the zone match the file exactly, including what's *not* in it. Push it, and `dig @dns-server docs.$USER.dojo.test A +short` now returns nothing.

Save this state in git, so you can always get back to it:

```sh
git diff                 # what changed since the first commit
git add dnsconfig.js
git commit -m "Add app, mail and MX records"
```

---

## 7. The trailing-dot mistake

The most common mistake in `dnsconfig.js` is a `CNAME` or `MX` target without its trailing dot. Make it on purpose:

```js
	CNAME("broken", "www.studentXX.dojo.test"),   // no trailing dot, on purpose
```

```sh
dnscontrol preview
```

`dnscontrol` refuses the file with an error that names the record and says the target `must end with a (.)`. Nothing reached PowerDNS. Catching it at preview costs nothing; catching it after it's live costs an outage.

Throw the experiment away with git:

```sh
git restore dnsconfig.js   # back to your last commit
dnscontrol preview         # 0 corrections again
```

`git restore` discards uncommitted edits, so `preview` and `restore` together let you try anything safely: nothing is real until you `push`.

---

## Checkpoint

Before moving on, be ready to show or say:

- `dig` output for a record you added, straight from `dns-server`.
- What `± MODIFY`, `+ CREATE` and `- DELETE` in a preview each mean.
- Why removing a line from `dnsconfig.js` removes the record from the server.

**Next:** [lab2.md](lab2.md) (optional) covers what happens when someone changes your zone outside the code. Or go straight to [lab3.md](lab3.md), the required Part 2 lab: the shared zone, where you can't push at all.
