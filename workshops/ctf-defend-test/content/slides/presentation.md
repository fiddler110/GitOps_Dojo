---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/presentation.css');
footer: '[&larr; Hub](index.md) &nbsp;|&nbsp; CTF Defend Test'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# CTF Defend Test

## S6 proof harness for the defend-pipeline loop (target 14, customer-portal) -- NOT the CTF-5 session pack.

**Talk + hands-on lab**

<!--
Speaker notes go in HTML comments like this one.
-->

---

## Today

1. This is a facilitator test harness, not a real lesson
2. The S6 loop: PR fix -> gate green -> merge -> live redeploy -> exploit returns nothing
3. One lab, one target: `customer-portal`'s SQL injection
4. Hands-on lab

---

## The loop

```text
student fixes app.py --> PR --> defend-pr.yml re-runs the exploit (gate)
   --> merge to main --> defend-main.yml rebuilds + redeploys the live slot
   --> the same exploit against the live slot now returns nothing
```

---

<!-- _class: lead -->
<!-- _paginate: false -->

# Your turn

## Open the Labs tab, or `~/lab/README.md` in the terminal

<p class="nav">Next: <a href="lab-index.md">Labs &rarr;</a></p>
