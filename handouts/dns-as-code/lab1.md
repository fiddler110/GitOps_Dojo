# Lab 1 — The Core Workflow

By the end of this lab you'll have previewed and applied the starting
zone, added your own DNS record on a branch, opened a pull request,
merged it, applied it, and confirmed the record is genuinely live — the
full loop you'll use for every change in this system. See the table in
[README.md](README.md) if you want the one-line summary first.

Do [00-github-setup.md](00-github-setup.md) and
[01-local-powerdns-stack.md](01-local-powerdns-stack.md) first if you
haven't — you need a GitHub repo with the starter `dnsconfig.js` pushed
to it, and a local PowerDNS container running, before this lab makes
sense.

---

## 1. Clone your practice repo

If you already have a local clone from setup, `cd` into it and skip to
step 2. Otherwise:

```sh
git clone https://github.com/<your-username>/dns-as-code-practice.git
cd dns-as-code-practice
```

---

## 2. Preview the current state

```sh
dnscontrol preview
```

If this is a fresh local PowerDNS container (no zones at all yet), this
first run shows *every* record in `dnsconfig.js` as a **CREATE** —
that's expected, not an error. This is the "diff before it happens"
dnscontrol gives you: nothing has touched PowerDNS yet, you're just
looking at what *would* happen.

---

## 3. Apply it

```sh
dnscontrol push
```

Then confirm the records are actually live — don't just trust the tool's
exit code:

```sh
dig @127.0.0.1 -p 5353 dojo.test A +short
dig @127.0.0.1 -p 5353 www.dojo.test A +short
dig @127.0.0.1 -p 5353 dojo.test MX +short
```

(Doing the real-domain path instead? Drop `@127.0.0.1 -p 5353` and query
your real domain directly — see
[02-cloudflare-domain-setup.md](02-cloudflare-domain-setup.md).)

Run `dnscontrol preview` again — it should now report **zero
corrections**. That's the loop you'll repeat for every future change:
edit → preview → (PR) → push → verify → preview again to confirm you're
clean.

---

## 4. Create a branch

Replace `yourname` with your name (keep it lowercase, no spaces — it's
about to become both a git branch and a DNS label):

```sh
git checkout -b add-yourname-record
```

Same reasoning as Git Fundamentals: work on a branch so nothing you do
here can affect anyone else's zone view until you're ready to share it —
useful habit even solo, since it's exactly how a real team would work.

---

## 5. Add your own record

Open `dnsconfig.js` and add a new `A` record for yourself inside the
`D("dojo.test", ...)` block, near the other `A` records:

```js
A("yourname", "203.0.113.30"),
```

`203.0.113.0/24` is IETF-reserved "documentation" address space (RFC
5737) — safe to use here since it can never be a real, routable address.
See `docs/record-types.md` in your repo for the full syntax reference
covering A/CNAME/MX/TXT — you'll use the others in Lab 2.

Pick whichever of these suits you. All three give the same result.

### Option 1: VS Code (recommended)

Open the repo folder in VS Code, open `dnsconfig.js`, add your record near
the other `A` records and save with `Ctrl+S` (`Cmd+S` on a Mac).

### Option 2: nano, in the terminal

```sh
nano dnsconfig.js
```

To save and exit: `Ctrl+O` (write out), `Enter` (keep the file name), `Ctrl+X` (exit).

### Option 3: a python3 one-liner

Replace `yourname` and the IP, then paste the whole command:

```sh
python3 -c '
p = "dnsconfig.js"
s = open(p).read()
s = s.replace("A(\"mail\"", "A(\"yourname\", \"203.0.113.30\"),\n\tA(\"mail\"", 1)
open(p, "w").write(s)
'
```

After editing, check the file:

```sh
cat dnsconfig.js
```

---

## 6. Preview your change locally

**Always do this before opening a PR** — it's the whole point of
DNS-as-Code: see the diff before it happens, not after.

```sh
dnscontrol preview
```

Confirm the diff shows only your one new record. If it shows anything
else, you edited the wrong place — fix it before continuing.

---

## 7. Review, commit, and push

```sh
git status
git diff
git add dnsconfig.js
git commit -m "Add A record for yourname"
git push -u origin add-yourname-record
```

Nothing you've done is visible to anyone else until this push — up to
that point, everything (branch, commits) existed only on your machine.

---

## 8. Open a pull request

Go to your repo on `github.com/<your-username>/dns-as-code-practice`.
GitHub usually shows a banner offering **Compare & pull request** for
the branch you just pushed — click it, and open the PR into `main`.
(`gh pr create` works too, if you've set up the GitHub CLI.)

**Write down your PR number** — Lab 4 uses it.

Unlike the workshop, no CI comment will appear automatically on this PR
(see [01-local-powerdns-stack.md](01-local-powerdns-stack.md) for why) —
your own `dnscontrol preview` output from step 6 *is* the review here.
Re-run it if it's been a while since you last checked.

---

## 9. Merge and apply it

Read your own diff on the PR's **Files changed** tab, then merge it:
click **Merge pull request** → **Confirm merge**.

Unlike the workshop, merging does **not** automatically apply the
change — pull `main` and run `dnscontrol push` yourself:

```sh
git checkout main
git pull
dnscontrol push
dig @127.0.0.1 -p 5353 yourname.dojo.test A +short
```

Then confirm you're clean:

```sh
dnscontrol preview   # should report 0 corrections
```

---

## Checkpoint

Before moving on, be ready to show or say:

- Your PR number and its diff.
- The `dig` output proving your record is genuinely live.
- In your own words: what's the difference between `dnscontrol preview`
  and `dnscontrol push`, and why do both exist?

**Next:** Labs 2-5 in [README.md](README.md) are optional deep dives —
pick whichever sounds most useful, or work through them in order. Lab 4
(rolling back history) uses the PR number from this lab, so keep it
handy.
