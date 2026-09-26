# Lab 1 — Leak it

**Goal:** commit a secret, "delete" it, and watch git keep it anyway. Then scan for secrets, and put a guard in front of the next commit.

Everything here stays in a folder on your own terminal; nothing is pushed. The tokens below are made up, but they look real, which is the point: the scanner in step 4 recognises their shape.

**In this lab you will:**

1. Make a tiny app with a token written into its code, and commit it.
2. "Fix" it the way most people do, and see that git still has the token.
3. Learn why the only real fix is to rotate the token.
4. Scan the repo's history with `gitleaks`.
5. Add a pre-commit hook that stops the next leak before it's committed.

---

## 1. A small app with a secret in it

Git signs every commit with a name and an email. If it doesn't know yours yet, tell it once (`--global` means "for every repo of mine"):

```bash
git config --global user.name "$USER"
git config --global user.email "$USER@dojo.test"
```

Make a folder for the app, go into it, and turn it into a git repo (`-b main` names the first branch `main`):

```bash
mkdir -p ~/lab/leaky-app
cd ~/lab/leaky-app
git init -b main
```

`leaky-app` now shows in the VS Code Explorer (click the refresh arrow if it doesn't). Create the app: right-click **leaky-app** → **New File...**, name it `app.py`, and paste this in:

```python
API_URL = "https://api.example.test"
API_TOKEN = "ghp_R8vK2mQx7LpT4nWz9HcY1bFs6DjE3aGu5VtN"

print(f"calling {API_URL}")
```

Save it (**Ctrl+S**). This is the mistake: `API_TOKEN` is a credential, written straight into the code. It's how a secret usually gets into git: someone tests with a real token and forgets it's there.

Back in the terminal, commit it. `git add` picks the file for the next commit, and `git commit` records it for good:

```bash
git add app.py
git commit -m "Add the app"
```

## 2. "Delete" it

A reviewer spots the token. You fix it the obvious way: the code reads the token from an **environment variable** (a value the program is given when it starts), so the file no longer holds it.

In VS Code, replace the whole of `app.py` with this (**Ctrl+A**, then paste) and save:

```python
import os

API_URL = "https://api.example.test"
API_TOKEN = os.environ["API_TOKEN"]

print(f"calling {API_URL}")
```

Commit the fix (`-a` includes every file git already tracks, so you don't need `git add` again):

```bash
git commit -am "Read the API token from the environment"
cat app.py
```

The file is clean now. Is the token gone? `git log -p` shows every commit, newest first, with the lines each one changed (`-` removed, `+` added):

```bash
git log -p
```

Press **Space** to page down and **q** to quit. The second commit shows the token on a `-` line, and the first shows it being added: it's still there, in full. Anyone who clones this repo gets every commit, so they get the token too. You can also ask git which commits added or removed a string:

```bash
git log -S "ghp_" --oneline
```

(`ghp_` is how GitHub tokens start, which is why scanners look for it.)

## 3. Once it's pushed, it's leaked

If you had pushed that first commit, you could rewrite history (`git filter-repo`, then a force-push), but that doesn't reach the clones, forks, CI caches and backups that already have it. **Once a secret is pushed, treat it as leaked.** The only fix is to **rotate** it: revoke the token where it was issued, and use a new one. Everything after this lab is about not getting here.

## 4. Scan for secrets

`gitleaks` knows what hundreds of kinds of secret look like. `gitleaks git` scans every commit in the repo, and `-v` (verbose) shows each finding:

```bash
gitleaks git -v
```

It finds the token in the first commit, with the file, line, commit and author that added it, and ends with `leaks found: 1`. At work you'd run the same scan in CI on every push, and over the whole history of an old repo when you take it over.

## 5. Stop the next one before it's committed

Finding a leak after it's committed is too late. A **pre-commit hook** is a script git runs just before every commit: if the script fails, there is no commit.

Git looks for hooks in the repo's `.git/hooks/` folder. Open **leaky-app → `.git` → `hooks`** in VS Code: git put some `*.sample` scripts there when you ran `git init`. Create a new file in that folder named `pre-commit` (no extension), with this in it:

```sh
#!/bin/sh
# Before each commit: scan only what is about to be committed (--staged),
# and hide any secret it finds in the output (--redact).
exec gitleaks git --pre-commit --staged --redact -v
```

Save it. Then make it executable (git skips a hook it can't run):

```bash
chmod +x .git/hooks/pre-commit
```

Now make the same mistake again. Add this line to the end of `app.py` in VS Code, and save:

```python
BACKUP_TOKEN = "ghp_Z3xQ9wLk2VbN7cRt5YmH8sJd4FgP1aKe6UoW"
```

Try to commit it:

```bash
git commit -am "Add the backup token"
```

gitleaks prints a finding (the value shows as `REDACTED`) and **the commit doesn't happen**. Check:

```bash
git log --oneline   # still two commits
```

Put it right. `git checkout app.py` throws away your change to the file and brings back the committed version; VS Code shows the line disappear:

```bash
git checkout app.py
```

A hook has limits. `git commit --no-verify` skips it. And nothing in `.git/` is ever committed, so your hook stays on your machine: everyone who clones the repo has to install it for themselves. A hook is a seatbelt for you, not a guarantee for the team. Teams add the same scan in CI and on the git server (push protection), and install hooks for everyone with a tool like `pre-commit`.

## Check yourself

1. You find a password in a commit from last year. You delete the line and push. Are you done? *(No. It's still in history and in every clone. Rotate it.)*
2. Why run gitleaks in CI as well as in a hook? *(A hook works only in clones that switched it on, and can be skipped. CI sees every push.)*

**Rules used:** 8 (never in git, including history), 7 (plan for leaks: rotation is the fix).

**Next:** [lab2.md](lab2.md)
