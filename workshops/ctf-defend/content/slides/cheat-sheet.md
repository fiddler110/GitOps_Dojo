---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/cheat-sheet.css');
footer: '[&larr; Hub](index.md) &nbsp;|&nbsp; CTF-5: Defend | Cheat Sheet'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# Cheat Sheet

## Every command from the lab, in one place

Keep this open in a split pane or another tab while you work.

---

## Clone your repo

```sh
cd ~/lab
git clone http://git-server:3000/$USER/customer-portal.git
cd customer-portal
```

Your copy, not a shared seed. Whatever you push to `main` is what runs on
your slot.

---

## Check your own theory

```sh
# the same check the PR gate runs against your branch
python3 exploit/dump.py --url http://<your-slot-address>
```

Exit `0` -- still vulnerable. Exit `1` -- patched. Run it as often as you
like; it never costs you anything.

---

## Branch, fix, push, PR

```sh
git checkout -b fix-search
# edit app.py
git add app.py
git commit -m "Fix the customer lookup"
git push -u origin fix-search
```

Open the PR in Forgejo, then watch the Actions tab -- it reruns the exploit
check against your branch and blocks the merge until it comes back clean.

---

## After merge

Merging rebuilds the image and redeploys your slot in place -- no extra
step. Re-run the exploit check against your slot to confirm `1`, then check
the SOC Alerts panel for the flip from under attack to contained.
