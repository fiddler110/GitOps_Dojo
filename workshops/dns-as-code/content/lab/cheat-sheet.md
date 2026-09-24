# DNS as Code Cheat Sheet

A quick reference for the commands used across [lab1.md](lab1.md)-[lab6.md](lab6.md). Print this, `glow` it, or keep it open in a split pane — you don't need to memorize any of it.

---

## Setup (already done for you here)

Preinstalled in this terminal: `dnscontrol`, `dig` (from `dnsutils`), `git`, `python3`. Verify:

```sh
dnscontrol version
dig -v
git --version
```

Two kinds of zone, both served by the `dns-server` container (PowerDNS):

| | Part 1: your zone | Part 2: the shared zone |
| --- | --- | --- |
| Zone | `<your-username>.dojo.test` | `dojo.test` |
| Config | `~/lab/my-zone/dnsconfig.js` (local git repo) | `dnsconfig.js` in `dns-team/dns-as-code`, cloned to `~/lab/dns-as-code` |
| Who runs `dnscontrol push` | You | Only CI, after a reviewed merge |

Either way, `dnsconfig.js` is the source of truth: you never edit records anywhere else.

---

## The Everyday Workflow

Your own zone (Part 1, [lab1.md](lab1.md)):

```text
edit dnsconfig.js → dnscontrol preview → dnscontrol push → dig → git commit
```

The shared zone (Part 2, [lab3.md](lab3.md)):

```text
edit dnsconfig.js → preview → branch/commit/push → PR → CI preview → someone approves → merge → CI applies → verify
```

| Step | Command | What it means |
| ---- | ------- | -------------- |
| Preview | `dnscontrol preview` | Dry-run diff against live PowerDNS. Changes nothing. Run this before *every* commit. |
| Branch | `git checkout -b <name>` | Work on your own line of change, same as any git repo. |
| Stage/commit/push | `git add`, `git commit`, `git push` | Same git mechanics as [Git Fundamentals](../../../git-fundamentals/) — nothing DNS-specific here. |
| Pull request | *(in Forgejo)* | `.forgejo/workflows/dns-preview.yml` runs `dnscontrol preview` on the PR and posts the diff as a comment — a "DNS Preview" status check. |
| Review | *(in Forgejo)* | Someone other than the author reads the diff and the DNS Preview comment and approves. `main` needs one approval. |
| Merge | *(in Forgejo)* | Allowed once DNS Preview passed and the PR is approved. `.forgejo/workflows/dns-apply.yml` then runs `dnscontrol push` for real and sets a "DNS Apply" status. |
| Verify | `dig @dns-server <name> <type> +short` | Confirm the live record matches what you expect. |
| Confirm clean | `dnscontrol preview` | Should report **zero corrections** once PowerDNS matches `dnsconfig.js` exactly. |

Full walkthroughs: [lab1.md](lab1.md) (your zone) and [lab3.md](lab3.md) (the shared zone).

**The gates on the shared zone.** `dnscontrol push` to `dojo.test` from your terminal fails with `403 ... only CI changes it`: the lab's PowerDNS API accepts changes to `dojo.test` only from the CI runner. `git push` to `main` fails too: `main` is protected, so changes arrive only as reviewed pull requests.

---

## Record Types

Full reference: `docs/record-types.md` in the repo, or [dnscontrol.org](https://docs.dnscontrol.org/language-reference/domain-modifiers). All go inside a `D("...", ...)` block; names are relative to that zone, and `@` is the zone itself.

```js
A("name", "203.0.113.30"),                 // IPv4 address. "@" = bare apex domain.
CNAME("name", "dojo.test."),                // alias — target needs a TRAILING DOT
MX("@", 10, "mail.dojo.test."),             // mail routing — priority, then target (trailing dot)
TXT("name", "some text value"),             // arbitrary text — SPF/DKIM/DMARC/verification
```

- `203.0.113.0/24` is IETF-reserved "documentation" address space (RFC 5737) — safe to use throughout this lab, never a real routable address.
- **CNAME can't coexist with any other record on the same name** — DNS-wide rule, not specific to this project.
- Missing the trailing dot on a `CNAME`/`MX` target is the single most common mistake — see [lab1.md](lab1.md).

---

## Reading a `preview` Diff

`dnscontrol preview` reports one correction per record that differs from live state:

- **`+ CREATE`** — a record in `dnsconfig.js` that PowerDNS doesn't have yet.
- **`- DELETE`** — a record PowerDNS has that's no longer in `dnsconfig.js`, including one someone added outside the code (drift, [lab2.md](lab2.md)).
- **`± MODIFY`** — a record whose value changed, shown old → new.
- **A zone that doesn't exist yet** — preview only says it will be created; the records show up on the push itself ([lab1.md](lab1.md)).

Always read the whole diff before committing or merging. If it shows anything you didn't intend to change, stop and investigate before continuing.

---

## dig Quick Reference

```sh
dig @dns-server <name> A +short        # A record
dig @dns-server <name> CNAME +short    # CNAME record
dig @dns-server dojo.test MX +short    # MX records
dig @dns-server <name> TXT +short      # TXT record(s)
```

`@dns-server` points `dig` at this lab's PowerDNS container directly, instead of your normal resolver — necessary since `dojo.test` isn't a real, publicly resolvable domain.

---

## `dnsctl.py` — the CLI Wrapper

See [lab3.md](lab3.md) for a full walkthrough, and `docs/dnsctl-cli.md` in the repo for why some of its output still says "Cloudflare."

```sh
python3 scripts/dnsctl.py <command> [options]
```

### Local commands — no forge CLI needed

| Command | Does |
| --- | --- |
| `doctor` | Checks dnscontrol is on PATH, `.env`/`creds.json` are set up, git hooks enabled. Run this first. |
| `setup` | One-time: enables `.githooks`, creates `.env` from `.env.example`. |
| `preview` | `dnscontrol preview` — the dry-run diff. |
| `push` | `dnscontrol push` — applies the diff. Prompts for confirmation. Refused for `dojo.test` from your terminal (only CI may). |
| `record add <name>` | Interactive wizard to add a record. |
| `record edit <name>` | Change an existing record's value/priority/TTL in place. |
| `record remove <name>` | Remove a record. |
| `record list [name]` | List records currently in `dnsconfig.js`. |
| `record update-ip <old> <new>` | Bulk-replace an IP across every `A` record pointing at it. |
| `lint` | Fast offline sanity checks (duplicate lines, missing trailing dots, CNAME conflicts) — no network call. |
| `show` | Table/CSV/Markdown view of every managed record. |

### Commands that talk to Forgejo (PR lifecycle)

| Command | Does |
| --- | --- |
| `begin [description]` | Sync `main`, check for drift, create a branch. |
| `submit "<message>"` | Commit your change, push a branch, open a PR (creates the branch for you if you're still on `main`). |
| `status` | List your open PRs and their CI check status. |
| `review <PR#>` | Show a PR's diff and its "DNS Preview" comment. |
| `merge <PR#>` | Merge once checks pass (`--force` to skip waiting on the check). |
| `history` | List merges to `main` that touched `dnsconfig.js`, newest first. |
| `rollback <PR#\|commit>` | Revert a merged change via a *new* PR — never pushes to `main` directly. See [lab5.md](lab5.md). |
| `validate [target]` | Confirm a merge's "DNS Apply" run succeeded and live state matches `dnsconfig.js` (waits for the run by default). |

These pick `gh` or a Forgejo API client automatically based on your `origin` remote — against this lab's Forgejo, the first one that needs to talk to the API will prompt for your username/password (same as `git push`) and cache it for the rest of the session.

---

## Common Scenarios & Quick Fixes

**"CNAME target needs a name ending in a dot"** (or similar config error at `preview` time)

You forgot the trailing dot on a `CNAME`/`MX` target: `www.dojo.test` → `www.dojo.test.`. See [lab1.md](lab1.md).

**"preview shows a DELETE I didn't expect"**

Either the record was added outside the code (drift, [lab2.md](lab2.md)), or your branch is missing something. In the shared repo, `git pull origin main` first; CI's own preview already merges `main` in.

**"403 ... dojo.test is the shared zone: only CI changes it"**

Working as intended: open a pull request instead ([lab3.md](lab3.md)). For your own zone, check you're in `~/lab/my-zone`.

**"my PR's Merge button is greyed out"**

It needs a passing DNS Preview check **and** one approval from someone other than you. Ask a neighbour or the facilitator to review it.

**"push rejected — updates were rejected because the remote contains work..."**

Same as plain git: `git pull` to bring in what you're missing, resolve a conflict if one comes up (see [lab6.md](lab6.md)), then push again. A rejection mentioning a **protected branch** means you pushed to `main`: push a branch and open a PR.

**"a CI check isn't showing up on my PR yet"**

CI is a real background job, not instant — give it a few seconds and re-check (`dnsctl.py status`, or refresh the Forgejo PR page). `dnsctl.py merge` itself only refuses when a check exists and has *failed* (`--force` overrides that), but Forgejo still won't merge without a passing check and an approval.

**"I want to undo a change that's already merged to main"**

Don't hand-edit `dnsconfig.js` back — use `dnsctl.py rollback <PR#>` (or `git revert` for the equivalent raw-git move), which opens a new PR with the inverse diff instead of rewriting shared history. See [lab5.md](lab5.md).

---

## Merge Conflicts

Same mechanics as any git repo — see [lab6.md](lab6.md) for a hands-on walkthrough. Git marks the disputed section:

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

**DNS-specific rule: always re-run `dnscontrol preview` after resolving a conflict, before you push.** Git only checks that the file has no leftover conflict markers — it has no idea whether the JavaScript is still valid or whether you've accidentally duplicated a record. `preview` is what actually confirms the resolved file is sane.

To bail out entirely and start over:

```sh
git merge --abort
```

---

## Glossary

- **Zone:** the set of DNS records for one domain — here, your own `<username>.dojo.test` and the shared `dojo.test`.
- **Record:** one DNS entry (A, CNAME, MX, TXT, ...) — a name mapped to a value.
- **`dnsconfig.js`:** the source of truth; dnscontrol reads it and reconciles PowerDNS to match.
- **`dnscontrol preview`:** dry-run diff between `dnsconfig.js` and live state. Changes nothing.
- **`dnscontrol push`:** applies that diff for real.
- **Correction:** one line of a `preview`/`push` diff — a CREATE, MODIFY or DELETE.
- **Drift:** a difference between the live zone and `dnsconfig.js`, usually from a change made outside the code. The next push removes it.
- **TTL:** how long (in seconds) a resolver may cache a record before re-checking it.
- **PR (pull request):** a proposal to merge a branch, reviewed before it happens — same as Git Fundamentals.
- **DNS Preview / DNS Apply:** the two Forgejo Actions CI checks — preview comments the diff on every PR; apply runs `dnscontrol push` on merge to `main`.
- **`dnsctl.py`:** the CLI wrapper that automates this whole loop, one command per step.

---

## When to Ask for Help

- Before merging any PR whose diff you don't fully understand.
- During a merge conflict — they're normal, not a sign you did something wrong.
- If `dnscontrol preview` reports an error you don't recognize — read it carefully first, it's usually specific (e.g. a missing trailing dot), but ask if it's not obvious.
- If you think a merged change is wrong: don't hand-edit it back — ask about `dnsctl.py rollback` / `git revert` instead.

**More:** [README.md](README.md) for the lab menu, `docs/` in the sample repo for deeper reference, or <https://docs.dnscontrol.org/> for dnscontrol's own docs.
