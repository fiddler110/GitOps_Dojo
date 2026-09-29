# Lab 2 — Drift, and Undoing Your Own Changes

**Optional. Part 1.** DNS as code only works if the file stays the source of truth. In real life someone eventually "just fixes it in the dashboard". This lab shows what `dnscontrol` does about that, and how to undo a change you've already pushed. Still in your own zone:

```sh
cd ~/lab/my-zone
dnscontrol preview   # start from 0 corrections; if not, finish Lab 1 first
```

> **Starting here?** This lab needs your zone pushed to the server (Lab 1 step 3). Run `lab-prep 2` to set that up; it's safe to run even if you did the earlier labs.

---

## Part A — Someone changes the zone behind your back

Play the colleague with a dashboard. This `curl` calls the PowerDNS API directly, the way a web dashboard would, and adds a `hotfix` record that isn't in `dnsconfig.js`:

```sh
curl -s -X PATCH \
  -H "X-API-Key: $DNS_API_KEY" -H "Content-Type: application/json" \
  "http://dns-api:8081/api/v1/servers/localhost/zones/$USER.dojo.test." \
  -d '{"rrsets":[{"name":"hotfix.'"$USER"'.dojo.test.","type":"A","ttl":300,"changetype":"REPLACE","records":[{"content":"203.0.113.99","disabled":false}]}]}'
dig @dns-server hotfix.$USER.dojo.test A +short
```

The record is live, and the DNS Zones tab highlights it. Now ask `dnscontrol`:

```sh
dnscontrol preview
```

It wants to `- DELETE` the `hotfix` record. That is **drift**: the live zone no longer matches the code, and the code wins. You have two choices:

1. **Keep it:** add `A("hotfix", "203.0.113.99"),` to `dnsconfig.js` and commit it, so the code describes reality again.
2. **Undo it:** push, and the record disappears.

Take choice 2:

```sh
dnscontrol push
dig @dns-server hotfix.$USER.dojo.test A +short   # nothing
```

The lesson: a dashboard edit survives only until the next push. In Part 2, the facilitator can do the same thing to the shared zone from the DNS Admin dashboard, and the next merged change quietly removes it. In a real team that's why dashboard access gets taken away once a zone is managed as code.

---

## Part B — Undo a change you've already pushed

Make a change you'll regret: point `www` somewhere wrong.

```js
	A("www", "203.0.113.66"),
```

```sh
dnscontrol preview
dnscontrol push
git commit -am "Move www to the new server"
```

It's live and committed. To undo it, don't hand-edit the old value back. Let git make the inverse change:

```sh
git log --oneline
git revert --no-edit HEAD
git log --oneline      # a new commit that undoes the last one; nothing was erased
dnscontrol preview     # ± MODIFY www back to 203.0.113.10
dnscontrol push
dig @dns-server www.$USER.dojo.test A +short
```

`git revert` adds a new commit, so the history still shows what happened and when. That matters more once the history is shared: Lab 5 does the same thing in the shared zone, through a pull request.

---

## Recap

- **Drift** is any difference between the live zone and the code. `preview` shows it, and `push` removes it.
- A change made outside the code survives only until the next push, unless someone adds it to the code.
- Undo a pushed change with `git revert` and another push, not by hand.

**Next:** [lab3.md](lab3.md), the required Part 2 lab: the shared zone.
