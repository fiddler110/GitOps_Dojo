# Lab 3 — The Change Process on a Shared Zone

**Part 2.** `dojo.test` is the whole class's zone, standing in for your company's production DNS. Here you can't just push. By the end of this lab you'll have taken one change through the full process: branch, pull request, CI preview, a review by someone else, merge, and CI applying it. On the way, you'll see the two gates that make that process the only way in.

| Rule | Enforced by |
| --- | --- |
| Only CI changes `dojo.test` | The lab's PowerDNS API changes `dojo.test` only for a job that proves, with a token Forgejo signed, that it runs for a push to `main` of this repo. |
| `main` only changes through a reviewed pull request | Branch protection on `main`: no direct pushes; the **DNS Preview** check must pass and one person other than the author must approve. |

---

## 1. Clone the shared repo

```sh
cd ~/lab
git clone http://git-server:3000/dns-team/dns-as-code.git
cd dns-as-code
batcat dnsconfig.js
```

Same layout as your own zone, but this `dnsconfig.js` declares `dojo.test` and lives on Forgejo, where the whole class works on it. The `.forgejo/workflows/` folder holds the two CI jobs: **DNS Preview** runs on every pull request, **DNS Apply** runs on every merge to `main`.

---

## 2. Preview

```sh
dnscontrol preview
```

**0 corrections.** Unlike your own zone in Lab 1, `dojo.test` is already live: the DNS Apply job applied `main` when the repo was created, and again after every merge since. Production is never empty.

---

## 3. Try to go around the process

Change the `mail` address in `dnsconfig.js` from `203.0.113.20` to `203.0.113.99`, then:

```sh
dnscontrol preview   # ± MODIFY mail.dojo.test, as you'd expect
dnscontrol push
```

The push fails with `403` and the message *dojo.test is the shared zone: only CI changes it*. Your terminal can read the shared zone but not change it, exactly like a company where only the pipeline holds the production credential.

Now try the other shortcut, committing straight to `main`:

```sh
git commit -am "Quick fix to mail"
git push
```

Git doesn't ask you to sign in: your terminal came with a Forgejo access token for your account, in `~/.git-credentials` (readable by you only), and git sends it on every push.

Forgejo rejects it: `main` is a protected branch. Put everything back the way it was:

```sh
git reset --hard origin/main
dnscontrol preview   # 0 corrections
```

---

## 4. Make a change the proper way

Create a branch:

```sh
git checkout -b add-$USER-app
```

Add a record for an app of yours. Use your username in the name, so it can't clash with anyone else's: add this line near the other `A` records, with your username (`studentXX`) in it:

```js
	A("studentXX-app", "203.0.113.30"),
```

Or let Python add it with your real username:

```sh
python3 -c '
import os
p = "dnsconfig.js"
s = open(p).read()
s = s.replace("\tA(\"mail\"", "\tA(\"%s-app\", \"203.0.113.30\"),\n\tA(\"mail\"" % os.environ["USER"], 1)
open(p, "w").write(s)
'
```

Preview it. The diff must show your one new record and nothing else:

```sh
dnscontrol preview
git diff
```

Commit and push the **branch**. Branches aren't protected, only `main`:

```sh
git add dnsconfig.js
git commit -m "Add $USER-app.dojo.test"
git push -u origin add-$USER-app
```

---

## 5. Open a pull request

On the workshop landing page, click **Open Forgejo** (it opens signed in as you). Forgejo offers to open a pull request for the branch you just pushed; open one into `main`. **Write down your PR number**; Lab 5 uses it.

Within a few seconds CI runs the **DNS Preview** job:

- It posts a comment with the `dnscontrol preview` output. CI previews your branch **merged into the current `main`**, so the comment shows exactly what merging would do, even if classmates merged after you branched.
- It sets the **DNS Preview** check on the PR. The merge button stays blocked until it passes.

---

## 6. Review someone else's change

The merge button is still blocked: `main` needs one approval, and you can't approve your own pull request. Pair up with a neighbour, or ask the facilitator, and review each other's:

1. In Forgejo, open their pull request from the repo's **Pull requests** tab.
2. Read **Files changed**: one new line, with their name on it?
3. Read the **DNS Preview** comment: exactly one `+ CREATE`, for their record? A preview showing a `DELETE` or `MODIFY` of someone else's record is a reason to ask questions, not to approve.
4. If it's right: **Review** (or **Finish review**) → **Approve**.

That's the real point of code review for DNS: a second person reads the diff *and* the preview before anything reaches production.

---

## 7. Merge, and let CI apply it

Once your PR has a green DNS Preview check and an approval, click **Merge** (Create merge commit).

The merge to `main` starts the **DNS Apply** job, the one thing allowed to change `dojo.test`. It holds no stored password: it asks Forgejo for a short-lived **ID token**, signed by Forgejo, that says *this job runs for a push to `main` of `dns-team/dns-as-code`*, and hands that to the PowerDNS API as its key. The API checks the signature and those three facts, so a job on another branch, a pull request or a fork gets `403`, even if it edits the workflow file. Watch it in the repo's **Actions** tab, then check:

```sh
dig @dns-server $USER-app.dojo.test A +short
```

The DNS Zones tab highlights your record in `dojo.test`. Bring your clone up to date and confirm there's nothing left to apply:

```sh
git checkout main
git pull
dnscontrol preview   # 0 corrections: CI already applied it
```

---

## If your pull request has conflicts

With the whole class adding lines next to `A("mail", ...)`, a classmate's merge may land on the same lines as yours. Forgejo then says the branch has conflicts, and the DNS Preview comment says there's nothing to preview yet. Bring `main` into your branch and fix it:

```sh
git checkout add-$USER-app
git pull origin main
```

Git stops with a conflict in `dnsconfig.js`. Open it, keep **both** records (theirs and yours), and delete the `<<<<<<<`, `=======` and `>>>>>>>` lines. Then:

```sh
dnscontrol preview   # must still show only your record as a CREATE
git add dnsconfig.js
git commit --no-edit
git push
```

CI previews the PR again. Lab 6 covers conflicts in more depth.

---

## Checkpoint

Before moving on, be ready to show or say:

- Your PR, its DNS Preview comment and its approval.
- The `dig` output proving your record is live in `dojo.test`.
- What stopped `dnscontrol push` and `git push` to `main` from your terminal, and why a company wants both gates.

**Next:** the rest of Part 2: [lab4.md](lab4.md) (`dnsctl.py`), [lab5.md](lab5.md) (history and rollback) and [lab6.md](lab6.md) (merge conflicts).
