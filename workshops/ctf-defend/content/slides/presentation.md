---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/presentation.css');
footer: '[&larr; Hub](index.md) &nbsp;|&nbsp; CTF-5: Defend'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# CTF-5: Defend

## Patch it with git: a live incident on your own app, defended with a PR, a CI gate and a redeploy.

**Talk + hands-on lab**

<!--
Speaker notes: this is the one CTF-series session that isn't about breaking
in -- it's about being on the other side of one. The deck never names the
bug or shows the payload; the lab is where that's found, by reading the
app's own source. Don't volunteer it from the stage. If someone's stuck,
point them back at app.py and the exploit check, not at the fix.
-->

---

## Today

1. The incident: what's different about this session
2. Your copy, your repo, your pipeline
3. Finding it, and proving it
4. Shipping the fix the normal way
5. Watching it land
6. Hands-on lab

---

## The incident

Every other CTF session has you attacking something. This one flips it:
**`customer-portal`**, a small internal lookup tool, is already running on
your own slot, and InfoSec has opened an incident against it.

The **SIEM** panel on your landing page shows what they're seeing in
real time -- recon, then probing, then a live attack -- the same clock every
other session's attacker swarm runs on, now pointed at your app instead of a
stranger's.

Your job isn't to exploit it. It's to find out what's wrong, fix the
**source**, and ship the fix before the clock gets there.

---

## Your copy, your repo

Unlike the attack-ladder sessions, this one starts with a `git clone`:

```sh
cd ~/lab
git clone http://git-server:3000/$USER/customer-portal.git
```

This is **your** repo -- not a shared seed, not read-only. Whatever lands on
its `main` branch is what's actually running on your target. Push a fix, and
the pipeline redeploys your own slot, nobody else's.

---

## Finding it

Nobody is going to point at a line of code. Work it the way you would at a
job:

- Use the app the way a customer would, then the way someone probing it
  would.
- Read the source once you have a theory -- it's the same code you cloned,
  not a black box.
- Trust what the app actually returns over what you assume it does.

---

## Proving it

The same check the pipeline runs on your pull request is one you can run
yourself, any time, against your own slot:

```sh
python3 exploit/dump.py --url http://<your-slot-address>
```

Exit `0` means still vulnerable. Exit `1` means patched. This is how you'll
know your fix is real before you ever open a PR.

---

## Shipping the fix

The normal way -- because that's the point:

```sh
git checkout -b fix-search
# edit app.py
git add app.py
git commit -m "Fix the customer lookup"
git push -u origin fix-search
```

Open a pull request in Forgejo. The Actions tab runs the exploit check
against *your branch*. **It can only merge once that check comes back
clean** -- a CI gate, not a suggestion anyone can wave through.

---

## Watching it land

Merge, and the pipeline rebuilds the image and redeploys your slot in
place -- no extra step, no asking the facilitator.

Re-run the exploit check against your redeployed slot and confirm it now
exits `1`. Check SIEM again: your status should flip from under
attack to contained. That flip is the actual lesson -- a fix that ships
closes the incident, not just the ticket.

---

## If you get stuck

1. **Re-read the briefing and the lab.** It names what the app does, never
   what's wrong with it.
2. **Use the app, then read the source.** The bug behaves oddly before it
   reads oddly.
3. **Run the exploit check often.** It's the fastest way to know whether a
   theory is right, with no need to guess.
4. **Ask.** A facilitator would rather talk you through where to look than
   watch the clock win.

---

<!-- _class: lead -->
<!-- _paginate: false -->

# Your turn

## Open the Labs tab, or `~/lab/README.md` in the terminal

<p class="nav">Next: <a href="lab-index.md">Labs &rarr;</a></p>
