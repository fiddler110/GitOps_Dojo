# CTF Defend Test

**This is a facilitator test harness, not a real workshop.** It exists to exercise the S6 defend loop
(PR fix -> gate goes green -> merge -> live redeploy -> exploit returns nothing) against the real stack.
It is not the CTF-5 session pack (no attacker bots, SOC feed or wall of shame -- those aren't built yet).

## What you'll do

| Lab | Topic | Time |
| --- | ----- | ---- |
| [lab1.md](lab1.md) | Fix the SQL injection in your own `customer-portal` repo and watch the defend pipeline redeploy it | ~15 min |

Open any lab file with:

```sh
glow lab1.md   # or: nano lab1.md, batcat lab1.md
```

The same files are in the browser too: the Labs tab, or the Slides hub's "Labs" page.
