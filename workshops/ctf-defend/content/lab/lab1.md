# Lab 1: Defend customer-portal

By the end of this lab you'll have found and fixed a live incident in your own
running app, shipped the fix the normal way — branch, PR, review, merge — and
watched the deploy happen because you merged, not because you asked anyone to.

---

## 1. The briefing

`customer-portal` is a small internal lookup tool: search customers by name,
or log in as one. It's already running — your copy, on your own slot, nobody
else's. InfoSec has opened an incident against it. The SOC Alerts panel on
your landing page shows what they're seeing in real time; the facilitator
will start the clock when the room's ready.

Your job: find out what's wrong, fix the **source**, and ship it before it
gets worse. Nobody is going to tell you where the bug is — that's the point
of an incident, not a scavenger hunt. Work the way you would at a job: read
the code, try the obvious things, check what the app actually returns.

---

## 2. Clone your repo

```sh
cd ~/lab
git clone http://git-server:3000/$USER/customer-portal.git
cd customer-portal
```

This is **your** copy of the app's source — not a shared seed, not read-only.
Whatever you push to `main` is what's actually running on your target.

---

## 3. Poke at the running app

Your slot's address is on the landing page card. Try the search box, try
logging in, try something it probably didn't expect. Read `app.py` once
you've got a theory — it's the same source you just cloned.

```sh
# the same check the PR gate will run on your fix
python3 exploit/dump.py --url http://<your-slot-address>
```

Exit `0` means it's still vulnerable; `1` means patched. Right now it should
say `0`.

---

## 4. Branch, fix, push, PR

```sh
git checkout -b fix-search
# edit app.py
git add app.py
git commit -m "Fix the customer lookup"
git push -u origin fix-search
```

Open a pull request in Forgejo. Watch the Actions tab: the PR gate scans your
change and re-runs the same exploit check above against your branch. **It can
only merge once that check comes back clean** — that's the real gate, not a
suggestion.

---

## 5. Merge, and watch it deploy

Merge the PR. `defend-main.yml` rebuilds the image and redeploys your slot in
place — no extra step, no asking the facilitator. Re-run the exploit check
against your (now redeployed) slot and confirm it exits `1`.

Check the SOC Alerts panel again: your status should flip from under attack
to contained.
