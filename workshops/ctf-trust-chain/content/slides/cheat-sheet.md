---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/cheat-sheet.css');
footer: '[&larr; Hub](index.md) &nbsp;|&nbsp; CTF-4: Trusting the Wrong Thing | Cheat Sheet'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# Cheat Sheet

## Session mechanics, not tool tutorials

For tool mechanics (`nmap`, `curl`, `openssl`, `jq`, ...) see the **Lab Info** card -- this page is just
the commands specific to running this session.

---

## The Attack Range card

```text
Start   -- boot the target you picked; stops whichever one was live
Stop    -- tear your slot down
Reset   -- return the current target to its untouched state
```

Only one target is live in your slot at a time. The card shows your slot's **IP only** -- find the ports
yourself.

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

`<target-id>` is the short name on the card: `dns-resolver-cve` (two separate submissions --
`dns-resolver-cve-token` for the captured credential, `dns-resolver-cve` for the replay), `policy-bypass`.

---

## Generic request tools

```sh
curl -s http://<ip>:5000/<path>                                  # GET
curl -s -X POST http://<ip>:5000/<path> -H 'Content-Type: application/json' -d '{"k":"v"}'
curl -s -X POST http://<ip>:5000/<path> -H "Authorization: Bearer <token>" -d '{}'
```
