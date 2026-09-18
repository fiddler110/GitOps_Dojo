# Lab 1 — The Core Workflow

**Required.** By the end of this lab you'll have previewed and applied the starting zone, added your own DNS record on a branch, opened a pull request, watched CI comment on it, merged it, and confirmed the record is genuinely live — the full loop you'll use for every change in this system. See the table in [README.md](README.md) if you want the one-line summary first.

---

## 1. Clone the sample repo

```sh
git clone http://git-server:3000/dns-team/dns-as-code.git
cd dns-as-code
```

Same as any git repo — `clone` downloads the whole thing, history included.

---

## 2. Preview the current state

```sh
dnscontrol preview
```

The `dns-server` container (PowerDNS) starts with no zones at all, so this first run shows *every* record in `dnsconfig.js` as a **CREATE** — that's expected, not an error. This is the "diff before it happens" dnscontrol gives you: nothing has touched PowerDNS yet, you're just looking at what *would* happen.

---

## 3. Apply it

```sh
dnscontrol push
```

Then confirm the records are actually live — don't just trust the tool's exit code:

```sh
dig @dns-server dojo.test A +short
dig @dns-server www.dojo.test A +short
dig @dns-server dojo.test MX +short
```

Run `dnscontrol preview` again — it should now report **zero corrections**. That's the loop you'll repeat for every future change: edit → preview → (PR) → push → verify → preview again to confirm you're clean.

---

## 4. Create a branch

Replace `yourname` with your name (keep it lowercase, no spaces — it's about to become both a git branch and a DNS label):

```sh
git checkout -b add-yourname-record
```

Same reasoning as Git Fundamentals: work on a branch so nothing you do here can affect anyone else's zone view until you're ready to share it.

---

## 5. Add your own record

Open `dnsconfig.js` and add a new `A` record for yourself inside the `D("dojo.test", ...)` block, near the other `A` records:

```js
A("yourname", "203.0.113.30"),
```

`203.0.113.0/24` is IETF-reserved "documentation" address space (RFC 5737) — safe to use here since it can never be a real, routable address. See `docs/record-types.md` in the repo (`cat docs/record-types.md` or `glow docs/record-types.md`) for the full syntax reference covering A/CNAME/MX/TXT — you'll use the others in Lab 2.

### Recommended: Nano

```sh
nano dnsconfig.js
```

To save and exit: `Ctrl+O`, `Enter`, `Ctrl+X`.

### Fallback: python3 one-liner

Replace `yourname` and the IP, then paste the whole command:

```sh
python3 -c '
p = "dnsconfig.js"
s = open(p).read()
s = s.replace("A(\"mail\"", "A(\"yourname\", \"203.0.113.30\"),\n\tA(\"mail\"", 1)
open(p, "w").write(s)
'
```

### Optional: Vim

```sh
vim dnsconfig.js
```

Jump to the right spot, `o` to open a new line, type your record, `Esc`, `:wq`, `Enter`.

After editing, check the file:

```sh
batcat dnsconfig.js
```

---

## 6. Preview your change locally

**Always do this before opening a PR** — it's the whole point of DNS-as-Code: see the diff before it happens, not after.

```sh
dnscontrol preview
```

Confirm the diff shows only your one new record. If it shows anything else, you edited the wrong place — fix it before continuing.

---

## 7. Review, commit, and push

```sh
git status
git diff
```

`git status` shows *which* files changed — right now that should be just `dnsconfig.js`, nothing else. `git diff` shows *exactly what* changed, line by line, before you commit it — a second look at the same thing `dnscontrol preview` just showed you from the DNS side, this time from git's side. Get in the habit of reading both before every commit.

```sh
git add dnsconfig.js
git commit -m "Add A record for yourname"
```

`git add` moves your change into the **staging area** — a holding pen for exactly what you want in the next commit. `git commit` then saves a permanent snapshot of everything staged, along with a message describing *what* changed and *why*.

```sh
git push -u origin add-yourname-record
```

`push` uploads your branch and its commit to the shared Forgejo server — `-u origin add-yourname-record` also remembers this branch's remote, so future pushes from it just need `git push`. Nothing you've done is visible to anyone else until this push — up to that point, everything (branch, commits) existed only on your machine.

---

## 8. Open a pull request

Go back to the workshop landing page (the tab or window where you clicked **Open VS Code** or **Open Terminal**) and click **Open Forgejo** — it opens a new tab, already signed in as you.

Find your `add-yourname-record` branch (Forgejo usually prompts you with a banner offering to open a pull request for a recently-pushed branch) and open a pull request into `main`.

Within a few seconds, a **"DNS Preview"** comment appears on the PR with the exact `dnscontrol preview` diff — CI running the same command you already ran locally, so you (and the facilitator) can compare without re-running it by hand. **Write down your PR number** — Lab 4 uses it.

---

## 9. Merge and confirm it went live

The facilitator will review and merge it (or, if you're facilitating yourself, merge it once the "DNS Preview" check is green).

Merging triggers CI to run `dnscontrol push` automatically — you don't run it yourself this time. Give it a few seconds, then confirm:

```sh
dig @dns-server yourname.dojo.test A +short
```

If you want to see the mechanics directly instead of taking CI's word for it:

```sh
git checkout main
git pull
dnscontrol preview   # should report 0 corrections — CI already applied it
```

---

## Checkpoint

Before moving on, be ready to show or say:

- Your PR number and its "DNS Preview" comment.
- The `dig` output proving your record is genuinely live.
- In your own words: what's the difference between `dnscontrol preview` and `dnscontrol push`, and why do both exist?

**Next:** Labs 2-5 in [README.md](README.md) are optional deep dives — pick whichever sounds most useful, or work through them in order. Lab 4 (rolling back history) uses the PR number from this lab, so keep it handy.
