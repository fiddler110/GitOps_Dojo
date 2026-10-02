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

> **`main` keeps moving.** The live zone is whatever `main` said at the last merge, and the whole class merges into it. `dnscontrol preview` compares *your files* with the *live zone*, so if your clone is behind `main`, a classmate's newer record looks like something you want to **delete**. Whenever a preview shows a `- DELETE` you didn't write, don't push: bring your clone up to date (`git pull`) and preview again.

---

## 3. Try to go around the process

Add a record for yourself straight into `dnsconfig.js`, named after your username so nobody else's record is touched:

```sh
sed -i "s/^\tA(\"mail\"/\tA(\"studentXX-quick\", \"203.0.113.99\"),\n&/" dnsconfig.js
git diff   # one new A record, nothing else
```

Then try to push it to the live zone:

```sh
dnscontrol preview   # + CREATE studentXX-quick.dojo.test, as you'd expect
dnscontrol push
```

The push fails with `403` and the message *dojo.test is the shared zone: only CI changes it*. Your terminal can read the shared zone but not change it, exactly like a company where only the pipeline holds the production credential.

Now try the other shortcut, committing straight to `main`:

```sh
git commit -am "Quick add of studentXX-quick"
git push
```

Git doesn't ask you to sign in: your terminal came with a Forgejo access token for your account, in `~/.git-credentials` (readable by you only), and git sends it on every push.

Forgejo rejects it: `main` is a protected branch. Put everything back the way it was, on the latest `main`:

```sh
git fetch
git reset --hard origin/main
dnscontrol preview   # 0 corrections
```

---

## 4. Make a change the proper way

Start from the latest `main`, then create your branch. `main` is the shared source of truth and changes while you work, so always branch from a fresh copy:

```sh
git checkout main
git pull
git checkout -b add-studentXX-app
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
line = "\tA(\"%s-app\", \"203.0.113.30\"),\n" % os.environ["USER"]
if line not in s:   # safe to run twice
    s = s.replace("\tA(\"mail\"", line + "\tA(\"mail\"", 1)
open(p, "w").write(s)
'
```

Preview it. The diff must show your one new record and nothing else:

```sh
dnscontrol preview
git diff
```

**Saw a `- DELETE` (or a `± MODIFY`) of a record you didn't touch?** A classmate merged after you branched, and your branch doesn't have their record yet, so the preview wants to remove it from the live zone. Nothing is wrong with your change; your branch is just behind `main`. Bring `main` in, then preview again:

```sh
git stash                 # only if you haven't committed yet
git pull origin main      # (git merge origin/main) brings in their record
git stash pop
dnscontrol preview        # your one + CREATE, and nothing else
```

If you've already committed, skip the stash lines. Do this right before you push, too: the preview you read must be your change *on top of the latest `main`*, which is exactly what CI's DNS Preview comment shows in the next step.

Commit and push the **branch**. Branches aren't protected, only `main`:

```sh
git add dnsconfig.js
git commit -m "Add studentXX-app.dojo.test"
git push -u origin add-studentXX-app
```

---

## 5. Open a pull request

On the workshop landing page, click **Open Forgejo** (it opens signed in as you). Forgejo offers to open a pull request for the branch you just pushed; open one into `main`. **Write down your PR number**; Lab 5 uses it.

Within a few seconds CI runs the **DNS Preview** job:

- It posts a comment with the `dnscontrol preview` output. CI previews your branch **merged into the current `main`**, so the comment shows exactly what merging would do, even if classmates merged after you branched.
- It sets the **DNS Preview** check on the PR. The merge button stays blocked until it passes.

---

## 6. Review someone else's change

The merge button is still blocked: `main` needs one approval, and you can't approve your own pull request. Pair up with a neighbour and review each other's, or run `sensei review` and let Sensei approve yours. No neighbour free? Sensei, the class review bot, has opened a practice pull request ("Add status.dojo.test") that anyone can review. It only opens it: the facilitator decides whether it merges. Run `sensei review` in your terminal and it picks a pull request for you to review (someone's waiting longest, or the practice one). Once you have reviewed any pull request that isn't yours, Sensei approves yours too within a few seconds. `sensei status` shows where yours stands, and `sensei help` lists the rest: `sensei approve` asks for it now, and `sensei approve --force` approves right away as long as your change is just your own record. So you are never stuck waiting for a neighbour.

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
dig @dns-server studentXX-app.dojo.test A +short
```

The DNS Zones tab highlights your record in `dojo.test`. Bring your clone up to date and confirm there's nothing left to apply:

```sh
git checkout main
git pull
dnscontrol preview   # 0 corrections: CI already applied it
```

---

## If your branch is behind `main`, or your pull request has conflicts

Most of the time `git pull origin main` on your branch just works (it brings in the other merges), and Forgejo's **Update branch** button does the same. Sometimes it can't: with the whole class adding lines next to `A("mail", ...)`, a classmate's merge may land on the same lines as yours. Forgejo then says the branch has conflicts, and the DNS Preview comment says there's nothing to preview yet. Bring `main` into your branch and fix it:

```sh
git checkout add-studentXX-app
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
