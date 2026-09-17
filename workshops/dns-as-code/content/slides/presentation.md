---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/presentation.css');
footer: '[&larr; Hub](index.md) &nbsp;|&nbsp; DNS as Code | Engineering & IT Operations'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# DNS as Code

## Managing DNS records the way we manage everything else

Builds on Git Fundamentals — same workflow, a new kind of file

**Talk + hands-on lab**

<!--
Assumes the room already did the Git Fundamentals session (or already
knows clone/branch/commit/push/PR). This is that same muscle memory
applied to a system most attendees currently change by clicking around a
web console.
-->

---

## Today

1. Why DNS changes deserve the same rigor as code — and why the file
   always wins
2. What dnscontrol does
3. Reading `dnsconfig.js`
4. The change workflow, two ways: raw git, then the `dnsctl.py` wrapper
5. Hands-on practice

> Same loop as last session. Different file, same discipline.

---

<!-- _class: section-title -->

# Part 1

## Why DNS-as-Code

---

## The core idea

> Whatever's committed in `dnsconfig.js` **is** the DNS configuration —
> not a description of it, the actual, enforced state.

- `dnscontrol push` makes live DNS match the file **exactly**: additions,
  edits, and **removals** — anything live but not declared in the file
  gets deleted
- There's no reconciliation the other direction. Click a record into
  existence in the provider's dashboard, and the next `push` deletes it —
  nothing "remembers" a manual edit, because the file was never updated
  to say it should exist
- This isn't a DNS-specific idea — it's the same guarantee Terraform,
  Kubernetes, or any GitOps tool gives you for its own kind of file

This is the one thing worth landing before anything else: the dashboard
isn't a second way to make changes anymore. It's not a way to make
changes at all.

<!--
This reframes the whole session: everything that follows (preview/push,
PRs, dnsctl.py) is just tooling built on top of this one guarantee. Worth
pausing on questions here if the room has them — this is the idea that
makes "why review every diff" and "why did my dashboard click disappear"
both make sense later.
-->

---

## How DNS usually gets changed

<div class="two-column">

- Someone opens a provider's web dashboard
- Clicks around, changes a record
- No review, no diff, no history of *why*
- "Who changed the MX record last Tuesday?" — nobody knows
- A typo in an A record takes down a service with zero warning

</div>

> The dashboard *is* the audit log — and it's not a very good one.

---

## What changes with DNS-as-Code

- Records live in a file (`dnsconfig.js`), in a git repo
- Every change is a **pull request** — reviewed before it's live
- `dnscontrol preview` shows the **exact diff** before anything happens
- `git log` becomes a real audit trail: who, when, why (commit message)
- Rolling back a mistake is `git revert`, not "does anyone remember what
  it used to say?"
- A well-intentioned dashboard fix doesn't survive the next `push` either
  — the fix has to go through the file, or it isn't real

<!--
This is the same case made for infrastructure-as-code generally, applied
to DNS specifically — DNS is infrastructure, and it's usually the
least-reviewed part of it.
-->

---

<!-- _class: section-title -->

# Part 2

## What dnscontrol does

---

## dnscontrol, in one sentence

> A CLI that reads a config file describing what DNS records **should**
> exist, compares it to what **actually** exists, and shows or applies the
> difference.

```text
dnsconfig.js  --preview-->  "here's what would change"
dnsconfig.js  --push------->  makes it actually change
```

It doesn't matter which DNS provider is behind it — Cloudflare, Route53,
PowerDNS (what this lab uses) — the workflow is identical.

---

## Two commands you'll use constantly

```sh
dnscontrol preview
```
Dry run. Shows the diff. **Changes nothing.** Always run this first.

```sh
dnscontrol push
```
Applies the diff. Normally happens via CI after a PR merges — not run by
hand. This lab has that CI wired up for real, so once you're past today's
initial bootstrap step you'll mostly watch it happen instead of typing
this yourself.

---

<!-- _class: section-title -->

# Part 3

## Reading `dnsconfig.js`

---

## The shape of the file

```js
var PDNS = NewDnsProvider("powerdns", { "zone_kind": "Native" });
var REG = NewRegistrar("none");

D("dojo.test", REG,
	DnsProvider(PDNS),
	DefaultTTL(300),

	A("@", "203.0.113.10"),
	A("www", "203.0.113.10"),
	CNAME("app", "dojo.test."),
	MX("@", 10, "mail.dojo.test."),
	TXT("@", "v=spf1 -all"),
);
```

One `D("<zone>", ...)` block per domain. Records inside are plain
JavaScript function calls — no special syntax to learn beyond "find the
right block, add/edit/remove a line."

---

## Record types you'll see today

| Type | Purpose | Example |
| ---- | ------- | ------- |
| `A` | name → IPv4 address | `A("www", "203.0.113.10")` |
| `CNAME` | alias → another hostname | `CNAME("app", "dojo.test.")` |
| `MX` | mail routing, with priority | `MX("@", 10, "mail.dojo.test.")` |
| `TXT` | arbitrary text (SPF/DKIM/verification) | `TXT("@", "v=spf1 -all")` |

<p class="small">`"@"` means the bare apex domain. CNAME/MX targets need a
trailing dot — the most common mistake, and one <code>preview</code>
usually catches for you.</p>

---

<!-- _class: section-title -->

# Part 4

## The change workflow — Track A: raw git

---

## Track A: git + dnscontrol by hand

<div class="flow">
<span><b>1</b><br>branch</span>
<span>→</span>
<span><b>2</b><br>edit<br><small>dnsconfig.js</small></span>
<span>→</span>
<span><b>3</b><br>preview<br><small>local diff</small></span>
<span>→</span>
<span><b>4</b><br>PR<br><small>Forgejo</small></span>
<span>→</span>
<span><b>5</b><br>merge</span>
<span>→</span>
<span><b>6</b><br>push<br><small>CI applies it</small></span>
</div>

Exactly the same shape as last session's git workflow — the only new step
is `dnscontrol preview` before you ever push a branch. Step 6 happens
without you: merging triggers CI, which runs `push` for you (see the next
slide) — today's bootstrap step, applying the zone's starting records
before any PR exists, is the one time you'll type `dnscontrol push`
yourself.

---

## Why review the diff twice

1. **Locally**, before opening the PR — catch your own mistakes first,
   for free, before anyone else has to look at them.
2. **On the PR**, before merging — a second set of eyes on something that
   can take down email or a whole domain if it's wrong.

> If the diff shows anything you don't expect, stop. Don't merge a diff
> you don't fully understand.

---

## CI is watching too

This lab has real CI on the sample repo (Forgejo Actions, not GitHub
Actions — same idea):

- **`DNS Preview`** — runs on every PR, posts the exact `dnscontrol
  preview` diff as a comment, sets a pass/fail check
- **`DNS Apply`** — runs on merge to `main`, runs `dnscontrol push` for
  real

Step 1's local preview and CI's preview comment should always agree — if
they don't, something changed between your last local preview and the
PR's current head. CI is the same guarantee from Part 1 enforcing itself
automatically, not a separate system to trust instead.

---

<!-- _class: section-title -->

# Part 5

## The change workflow — Track B: the `dnsctl.py` wrapper

---

## Same steps, one command each

```sh
dnsctl.py record add yourname.dojo.test --type A --value 203.0.113.30
dnsctl.py preview
dnsctl.py submit "Add A record for yourname"
dnsctl.py status
dnsctl.py review <PR#>
dnsctl.py merge <PR#>
```

Every step from Track A still happens underneath — branch, edit, preview,
commit, push, open a PR — `dnsctl.py` just names each one and does the
git/file work for you. Nothing about the underlying guarantee from Part 1
changes: the file is still what gets enforced, this is just a faster way
to edit it correctly.

---

<div class="flow">
<span><b>1</b><br>record add<br><small>edit + write</small></span>
<span>→</span>
<span><b>2</b><br>preview</span>
<span>→</span>
<span><b>3</b><br>submit<br><small>branch+commit+push+PR</small></span>
<span>→</span>
<span><b>4</b><br>status / review</span>
<span>→</span>
<span><b>5</b><br>merge</span>
</div>

Same shape as Track A's diagram, fewer boxes to type — `submit` alone
covers branch, commit, push, and opening the PR in one call.

---

## One CLI, two forges

`dnsctl.py` doesn't know or care whether this repo lives on GitHub or on
this lab's Forgejo — `submit`/`status`/`review`/`merge`/`validate` all
just call "whatever forge is hosting this repo," resolved automatically
from the `origin` remote's host:

- A GitHub remote → the real GitHub CLI (`gh`), completely unmodified
- Anything else (this lab's `git-server`) → a small, stdlib-only Forgejo
  API client that speaks Forgejo's REST API directly

Same commands, same script, either backend — the wrapper doesn't fork
itself per platform, it just dispatches under the hood.

<!--
This is the piece the real template's docs call out as GitHub-only (`gh
pr create/merge/review`) — this lab adds the Forgejo side rather than
skipping the wrapper entirely, so both tracks are teachable here.
-->

---

## What's still rough — and why that's left in

- The `record add`/`record edit` wizard still asks **"Proxy through
  Cloudflare (orange cloud)?"** for `A`/`CNAME` records — meaningless for
  PowerDNS. Answer `n`. This is the real script, unmodified on purpose:
  it's what a wrapper written against one specific provider looks like
  once you point it somewhere else.
- `merge`/`validate` check for a passing "DNS Preview"/"DNS Apply" CI
  status before they'll proceed — and now find a real one, same as
  against a GitHub repo with CI configured. `merge` checks once, not on a
  retry loop — if you merge before CI has posted a status yet, it refuses
  ("no check found"); re-run `status` after a few seconds and try again,
  or pass `--force` to skip the check entirely.

> A wrapper doesn't remove the underlying tool's assumptions — it just
> gives them a shorter name. Worth knowing which assumptions you inherited
> before you trust a green checkmark.

---

<!-- _class: section-title -->

# Part 6

## Hands-on practice

---

## What you'll do

**Lab 1 (required):** clone the `dns-as-code` repo, `dnscontrol preview` →
`push` the starting zone and `dig` it to see it's actually live, then
branch, add your own record by hand, `preview` it locally, open a PR,
watch CI comment the diff, merge, let CI apply it.

**Labs 2-5 (optional, any order after Lab 1):** editing/removing records
and catching mistakes before you commit, redoing the workflow with
`dnsctl.py` (the wrapper script — `record add` → `preview` → `submit` →
`status`/`review` → `merge` → `validate`), investigating and
rolling back merged history, and resolving a merge conflict safely.

**Full steps are in `~/lab/README.md`** inside your terminal — it's the
menu for all five labs plus a command cheat-sheet.

<!-- _footer: "[&larr; Hub](index.md)" -->

---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# Let's go

## Next: [labs.md](labs.md) for what each lab covers, then your terminal

Keep [cheat-sheet.md](cheat-sheet.md) open in another tab. Ask for help
any time — this is a lab, not a test.
