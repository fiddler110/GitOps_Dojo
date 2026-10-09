---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/cheat-sheet.css');
footer: '[&larr; Hub](index.md) &nbsp;|&nbsp; CTF-3: Secrets and Misconfiguration | Cheat Sheet'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# Cheat Sheet

## Session mechanics, not tool tutorials

For tool mechanics (`nmap`, `curl`, `git`, ...) see the **Lab Info** card -- this page is just the commands
specific to running this session.

---

## The Attack Range card

```text
Start   -- boot the target you picked; stops whichever one was live
Stop    -- tear your slot down
Reset   -- return the current target to its untouched state
```

Only one target is live in your slot at a time. The card shows your slot's **IP only** -- find the ports
yourself. (Labs 2 and 3 have no Attack Range target of their own -- they use your Forgejo repos and the vault.)

---

## Scan first, every time

```sh
nmap -sV -p- <your-slot-ip>
```

Expect more than one open port. Some are decoys -- that's by design, not a bug in the range.

---

## Submit a flag

```sh
dojo-flag submit <target-id> '<flag>'
```

`<target-id>` is the short name on the card: `leaky-config`, `git-secrets`.

---

## Reading git history

```sh
git log --oneline            # find the commit that "cleaned up" a file
git log -p -- deploy.sh      # the full diff history of one file, not just its current contents
git show <commit>             # one commit's full diff
```

Deleting or editing a file in a later commit does not remove what an earlier commit held.

---

## Generic request tools

```sh
curl -s http://<ip>:5000/<path>                              # plain GET
curl -s -u 'user:pass' http://<ip>:5000/<path>                # HTTP Basic Auth
curl -s -X POST http://<ip>:5000/<path> -d "field=value"      # form POST
curl -s -X POST http://<ip>:5000/<path> -H 'X-Deploy-Token: <token>'  # header-carried token
```
