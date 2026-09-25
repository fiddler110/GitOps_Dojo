---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/cheat-sheet.css');
footer: '[&larr; Hub](index.md) &nbsp;|&nbsp; DNS as Code | Cheat Sheet'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# Cheat Sheet

## Every command from Labs 1-5, in one place

Keep this open in a split pane or another tab while you work — you don't
need to memorize any of it.

<p class="nav">Full detail: <code>~/lab/cheat-sheet.md</code> in your terminal.</p>

---

## The everyday workflow

```text
edit dnsconfig.js → preview → branch/commit/push → PR → CI comment → merge → CI applies → verify
```

| Step | Command | What it means |
| ---- | ------- | -------------- |
| Preview | <span class="command">dnscontrol preview</span> | Dry-run diff. Changes nothing — run before every commit. |
| Branch/commit/push | <span class="command">git checkout -b</span> / `add` / `commit` / `push` | Same mechanics as Git Fundamentals. |
| Pull request | *(Forgejo)* | CI posts the `preview` diff as a comment. |
| Merge | *(Forgejo)* | CI runs `dnscontrol push` for real. |
| Verify | <span class="command">dig @dns-server &lt;name&gt; &lt;type&gt; +short</span> | Confirm the live record matches. |

---

## Record types

```js
A("name", "203.0.113.30"),        // IPv4. "@" = bare apex domain.
CNAME("name", "dojo.test."),      // alias — target needs a TRAILING DOT
MX("@", 10, "mail.dojo.test."),   // mail routing — priority, then target
TXT("name", "some text value"),   // SPF/DKIM/DMARC/verification
```

- `203.0.113.0/24` is documentation-only space (RFC 5737) — safe to use here.
- **CNAME can't coexist** with any other record on the same name.
- Missing trailing dot on `CNAME`/`MX` targets is the #1 mistake.

---

## Reading a `preview` diff

- **CREATE** — in `dnsconfig.js`, not yet in PowerDNS.
- **DELETE** — in PowerDNS, no longer in `dnsconfig.js`.
- **Editing a record** shows as a **paired DELETE + CREATE** — dnscontrol
  diffs by exact match, not in-place update. Expected, not a bug.

> Always read the whole diff before committing or merging.

---

## `dig` quick reference

```sh
dig @dns-server <name> A +short        # A record
dig @dns-server <name> CNAME +short    # CNAME record
dig @dns-server dojo.test MX +short    # MX records
dig @dns-server <name> TXT +short      # TXT record(s)
```

`@dns-server` points `dig` at this lab's PowerDNS directly, since
`dojo.test` isn't publicly resolvable.

---

## `dnsctl.py` — local commands

<div class="two-column small">

| Command | Does |
| --- | --- |
| `doctor` | Checks setup is sane. Run first. |
| `setup` | One-time: hooks + `.env`. |
| `preview` | Dry-run diff. |
| `push` | Applies the diff. |
| `record add <name>` | Wizard to add a record. |
| `record edit <name>` | Change a record in place. |
| `record remove <name>` | Remove a record. |
| `record list [name]` | List current records. |
| `lint` | Offline sanity checks. |
| `show` | Table/CSV/Markdown export. |

</div>

---

## `dnsctl.py` — PR lifecycle

| Command | Does |
| --- | --- |
| `begin [desc]` | Sync `main`, check drift, create a branch. |
| `submit "<msg>"` | Commit, push, open a PR. |
| `status` | Your open PRs + CI status. |
| `review <PR#>` | Show diff + preview comment. |
| `merge <PR#>` | Merge once checks pass. |
| `history` | Merges to `main` touching `dnsconfig.js`. |
| `rollback <PR#\|commit>` | Revert via a *new* PR. |
| `validate [target]` | Confirm apply succeeded. |

---

## Common scenarios

**"CNAME target needs a name ending in a dot"**
Add the trailing dot: `dojo.test` → `dojo.test.`

**"preview shows a DELETE + CREATE I didn't expect"**
Normal for an edit — confirm both halves are the record you meant.

**"push rejected... remote contains work"**
`git pull`, resolve any conflict, push again.

**"I want to undo a merged change"**
`dnsctl.py rollback <PR#>` — never hand-edit it back.

---

## Merge conflicts

```text
<<<<<<< HEAD
your current branch's version
=======
the incoming branch's version
>>>>>>> other-branch
```

Resolve by hand, delete the markers, then:

```sh
git add dnsconfig.js
git commit
```

**Always re-run `dnscontrol preview` after resolving** — git only checks
for leftover markers, not whether the file is still valid.

---

## Glossary

<div class="two-column small">

- **Zone:** DNS records for one domain — `dojo.test`.
- **Record:** one entry (A, CNAME, MX, TXT...).
- **`dnsconfig.js`:** the source of truth.
- **`preview`:** dry-run diff. Changes nothing.
- **`push`:** applies the diff for real.
- **Correction:** one CREATE/DELETE line of a diff (an edit shows as a paired DELETE + CREATE, not an in-place MODIFY).
- **TTL:** how long a resolver may cache a record.
- **PR:** a reviewed proposal to merge a branch.
- **DNS Preview / DNS Apply:** the two CI checks.

</div>

---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# When to ask for help

- Before merging a PR whose diff you don't fully understand.
- During a merge conflict — normal, not a mistake.
- If `preview` errors and the message isn't obvious.
- If you think a merged change is wrong — ask about `rollback`, don't hand-edit it back.

<p class="nav"><a href="index.md">&larr; Back to hub</a> &middot; <a href="labs.md">&larr; Lab overview</a> &middot; <a href="presentation.md">&larr; Deck</a></p>
