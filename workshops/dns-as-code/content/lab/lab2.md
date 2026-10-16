# Lab 2 — Drift, and Undoing Your Own Changes

**Part 1.** DNS as code only works if the file stays the source of truth. In real life someone eventually "just fixes it in the dashboard". This lab shows what `dnscontrol` does about that, and how to undo a change you've already pushed. Still in your own zone:

```sh
cd ~/lab/my-zone
dnscontrol preview   # start from 0 corrections; if not, finish Lab 1 first
```

> **Starting here?** This lab needs your zone pushed to the server (Lab 1 step 3). Run `dojo prep 2` to set that up; it's safe to run even if you did the earlier labs.

---

## Part A — Someone changes the zone behind your back

**The idea.** `dnscontrol` treats `dnsconfig.js` as the truth and makes the live zone match it. If anyone changes the zone another way (a web dashboard, a script, a colleague "just fixing it"), the live zone and the code disagree. That difference is **drift**, and `preview` reports it as a correction. You have two choices when you see it:

1. **Keep it:** add the record to `dnsconfig.js` and commit it, so the code describes reality again.
2. **Undo it:** push, and the record disappears.

You'll play the colleague with a dashboard. The `curl` below calls the PowerDNS API directly, the way a web dashboard would, and adds a `hotfix` record that isn't in `dnsconfig.js`.

**Your turn:**

Before you run it, predict: will `dig` see the record? What will `dnscontrol preview` want to do about it?

```sh
curl -s -X PATCH \
  -H "X-API-Key: $DNS_API_KEY" -H "Content-Type: application/json" \
  "http://dns-api:8081/api/v1/servers/localhost/zones/$USER.dojo.test." \
  -d '{"rrsets":[{"name":"hotfix.'"$USER"'.dojo.test.","type":"A","ttl":300,"changetype":"REPLACE","records":[{"content":"203.0.113.99","disabled":false}]}]}'
dig @dns-server hotfix.$USER.dojo.test A +short
dnscontrol preview
```

<!-- dojo-reveal: Results of the curl, dig and preview -->

- The record is live (`dig` prints `203.0.113.99`), and the DNS Zones tab highlights it.
- `preview` wants to `- DELETE` the `hotfix` record. That is **drift**: the live zone no longer matches the code, and the code wins.

<!-- /dojo-reveal -->

Take choice 2. Before you run it, predict what `dig` returns afterwards.

```sh
dnscontrol push
dig @dns-server hotfix.$USER.dojo.test A +short
```

<!-- dojo-reveal: Results of push and dig -->

- `dig` prints nothing: the record is gone.
- The lesson: a dashboard edit survives only until the next push. In Part 2, the facilitator can do the same thing to the shared zone from the DNS Admin dashboard, and the next merged change quietly removes it. In a real team that's why dashboard access gets taken away once a zone is managed as code.

<!-- /dojo-reveal -->

---

## Part B — Undo a change you've already pushed

**The idea.** To undo something already pushed, don't hand-edit the old value back. `git revert` adds a **new commit** that is the inverse of an earlier one, so the history still shows what happened and when. That matters more once the history is shared: Lab 5 does the same thing in the shared zone, through a pull request.

```text
git revert --no-edit <commit>
```

First make a change you'll regret: open `dnsconfig.js` in your editor and point `www` somewhere wrong.

```js
	A("www", "203.0.113.66"),
```

**Your turn:**

Predict: after the commit, is the bad address live? After the revert, what will `preview` show?

```sh
dnscontrol preview
dnscontrol push
git commit -am "Move www to the new server"
git log --oneline
git revert --no-edit HEAD
git log --oneline      # a new commit that undoes the last one
dnscontrol preview
dnscontrol push
dig @dns-server www.$USER.dojo.test A +short
```

<!-- dojo-reveal: Results of the push, revert and second push -->

- The first `preview` and `push` make the wrong address live, and it's committed.
- The revert adds a second commit; nothing was erased.
- The second `preview` shows `± MODIFY www` back to `203.0.113.10`, and `dig` returns that address after the push.

<!-- /dojo-reveal -->

---

## Recap

- **Drift** is any difference between the live zone and the code. `preview` shows it, and `push` removes it.
- A change made outside the code survives only until the next push, unless someone adds it to the code.
- Undo a pushed change with `git revert` and another push, not by hand.

**Next:** [lab3.md](lab3.md), the first Part 2 lab: the shared zone.

---

## Challenge c1 (bonus)

Only when your class has achievements on (you see a score on your landing page). A challenge is a goal with no steps, in
a repo of your own, for extra points. Start it in the terminal:

```sh
dojo challenge start c1
cd ~/lab/challenge-typo
```

That makes your own repo `$USER/challenge-typo`, clones it to `~/lab/challenge-typo` and shows your brief. The brief is
saved as `~/challenge-c1.md` with your own names filled in; read it again any time with `glow ~/challenge-c1.md`. When you think
it's done:

```sh
dojo check c1
```

A wrong answer costs nothing. `dojo check hint c1` gives a hint for part of the points (hints already used stay used).

**Start over.** `dojo challenge reset c1` deletes `~/lab/challenge-typo` (including any uncommitted work),
builds a fresh copy and clones it, as often as you like. Note that this challenge pushes to your own zone `$USER.dojo.test`, the same one `~/lab/my-zone` pushes to: whichever you push last wins.

## The Typo

A copy of your zone that `dnscontrol` refuses to push: one record points at the wrong hostname. Find it and fix it
without touching any other record, then push.

**End result (what the check looks for)**

- Work in your own repo `<you>/challenge-typo`, and push to your own zone `<you>.dojo.test`.
- The bad record is now a CNAME to `www.<you>.dojo.test.`, and the bad target is gone.
- Every other record is untouched: the apex A, `www` and `mail` are as seeded.

