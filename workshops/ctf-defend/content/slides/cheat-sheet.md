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

## The loop

**Detect** -> **Triage** -> **Contain** -> **Fix** -> **Verify**

Three apps, one clock. Work the worst, best-evidenced one first.

---

## Clone your repos

```sh
cd ~/lab
git clone http://git-server:3000/$USER/customer-portal.git
git clone http://git-server:3000/$USER/policy-bypass.git
git clone http://git-server:3000/$USER/leaky-config.git
```

---

## Check your slots

```sh
dojo-check                  # all three
dojo-check leaky-config     # one
```

`contained` = blocked and still usable. `broke-normal-use` = you broke it.

---

## Branch, fix, PR

```sh
git checkout -b fix-<target>
# edit, and write INCIDENT.md
git add -A && git commit -m "Fix <target>"
git push -u origin fix-<target>
```

`INCIDENT.md`: *What was hit*, *How I know*, *Impact*.

---

## After merge

Merge redeploys that slot in place. Run `dojo-check <target>`, then
watch the SIEM go from under attack to contained.
