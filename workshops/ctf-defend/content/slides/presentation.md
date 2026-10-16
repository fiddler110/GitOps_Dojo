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

1. The incident: three apps, one clock
2. The loop: detect, triage, contain, fix, verify
3. Your tools
4. Shipping a fix the normal way
5. Hands-on lab

---

## The incident

Every other CTF session has you attacking. This one flips it.

Three apps are live on **your own slot**: `customer-portal` (high),
`policy-bypass` (medium), `leaky-config` (low).

Each is attacked on its own timer, in an order that differs per student.
Unfixed breaches pile up. You choose what to work on first.

---

## The loop

1. **Detect**: find it in the evidence
2. **Triage**: which target, how bad, what first
3. **Contain**: stop the bleeding
4. **Fix**: in source, by pull request
5. **Verify**: prove it, don't believe it

---

## Your tools

- `git`, an editor, `python3`, `curl`
- the **SIEM** panel: a different signal per target, with noise
- `dojo check`: runs the attack against your live slot

```sh
dojo check                  # all three
dojo check policy-bypass    # one
```

`contained` means blocked **and** still usable.

---

## Your repos

```sh
cd ~/lab
git clone http://git-server:3000/$USER/customer-portal.git
```

One repo per app, all yours. What lands on `main` is what runs.

Read each `README.md` first: it says what the platform provides.

---

## Shipping a fix

```sh
git checkout -b fix-<target>
git push -u origin fix-<target>
```

The PR gate runs the attack against your branch and one normal request (advisory: it never blocks the merge).
Merge, and your slot redeploys.

---

## If you get stuck

1. Re-read the briefing and each README.
2. Use the app, then read the source.
3. Run `dojo check` often.
4. Ask. Hints are in the lab, in order.

---

<!-- _class: lead -->
<!-- _paginate: false -->

# Your turn

## Open the Labs tab, or `~/lab/README.md` in the terminal

<p class="nav">Next: <a href="lab-index.md">Labs &rarr;</a></p>
