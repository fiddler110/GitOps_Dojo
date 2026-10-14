# Lab 1: Defend customer-portal

By the end of this lab you'll have found and fixed a live incident in your own
running app, shipped the fix the normal way — branch, PR, review, merge — and
watched the deploy happen because you merged, not because you asked anyone to.

---

## 1. The briefing

`customer-portal` is a small internal lookup tool: search customers by name,
or log in as one. It's already running — your copy, on your own slot, nobody
else's. InfoSec has opened an incident against it. The SIEM panel on
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

If you're stuck, work these in order. They point at where to look, not at the
answer.

> **Hint 1.** Look at the SIEM panel's request log. Out of all the paths the
> swarm touches, which one gets hit far more than the rest, and with what in
> its query string?

> **Hint 2.** Find the line in `app.py` that handles that path. Follow the
> value the visitor sends from the request to wherever it's finally used. What
> is it joined to, and by what means?

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

Check the SIEM panel again: your status should flip from under attack
to contained.

---

## 6. Debrief

You can read this once your status is green or yellow.

The bug was a query built by pasting visitor input into the SQL text, so the
database couldn't tell the data from the instruction. The fix is a
parameterised query: the statement is fixed, the value travels separately. A
gate that re-runs the real exploit is what proved your fix worked, not your
reading of the diff.

Three things worth taking away:

- **Status and time.** Compare your time to contain with the room's on the
  SOC summary. The bug was equally easy to fix for everyone; what differed was
  how quickly you read the log and got to the right line.
- **The merge is the deploy.** Nothing was pushed to the server by hand. The
  pipeline rebuilt the image from `main`, so the repo is the source of truth
  for what's running. That is the GitOps point.
- **Think about what the dump contained.** If the table held cleartext
  passwords, a fixed query stops new dumps but not the damage already done.
  What should be stored instead, and what would you have to do about the
  accounts that were exposed?
