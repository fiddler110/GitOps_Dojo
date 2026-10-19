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

Git signs every commit with a name and an email, so it needs to know yours once (`--global` means "for every repo of mine"). `git init` turns a folder into a repo (`-b main` names the first branch `main`), and `git add` then `git commit` pick a file and record it for good:

```text
git config --global user.name "<name>"
git init -b main
git add <file>
git commit -m "<message>"
```

Start by creating the app. Make the folder first:

```sh
git config --global user.name "$USER"
git config --global user.email "$USER@dojo.test"
mkdir -p ~/lab/leaky-app
cd ~/lab/leaky-app
git init -b main
```

`leaky-app` now shows in the VS Code Explorer (click the refresh arrow if it doesn't). Right-click **leaky-app** → **New File...**, name it `app.py`, and paste this in:

```python
API_URL = "https://api.example.test"
API_TOKEN = "ghp_EXAMPLEfakeNotRealDoNotUse0000000001"

print(f"calling {API_URL}")
```

Save it (**Ctrl+S**). This is the mistake: `API_TOKEN` is a credential, written straight into the code. It's how a secret usually gets into git: someone tests with a real token and forgets it's there.

**Your turn:** commit it. Before you run it, predict: will git stop you, or warn you about the token?

```sh
git add app.py
git commit -m "Add the app"
```

<!-- dojo-reveal: Result of the first commit -->

Git accepts it without a word: git has no idea what a secret looks like. One commit now holds the token.

<!-- /dojo-reveal -->

## 2. "Delete" it

A reviewer spots the token. The obvious fix is to make the code read the token from an **environment variable** (a value the program is given when it starts), so the file no longer holds it. The history commands you need:

- `git commit -am` includes every file git already tracks, so you don't need `git add` again.
- `git log -p` shows every commit, newest first, with the lines each one changed (`-` removed, `+` added). Press **Space** to page down and **q** to quit.
- `git log -S "text"` lists the commits that added or removed a string.

```text
git log -p
git log -S "<string>" --oneline
```

In VS Code, replace the whole of `app.py` with this (**Ctrl+A**, then paste) and save:

```python
import os

API_URL = "https://api.example.test"
API_TOKEN = os.environ["API_TOKEN"]

print(f"calling {API_URL}")
```

**Your turn:** commit the fix and look at the file. Then, before you run the log commands, predict: is the token gone from the repo? (`ghp_` is how GitHub tokens start, which is why scanners look for it.)

```sh
git commit -am "Read the API token from the environment"
cat app.py
git log -p
git log -S "ghp_" --oneline
```

<!-- dojo-reveal: Results of the fix and the history -->

The file is clean, but the second commit shows the token on a `-` line and the first shows it being added: it's still there, in full. Anyone who clones this repo gets every commit, so they get the token too. `git log -S` lists both commits.

<!-- /dojo-reveal -->

## 3. Once it's pushed, it's leaked

If you had pushed that first commit, you could rewrite history (`git filter-repo`, then a force-push), but that doesn't reach the clones, forks, CI caches and backups that already have it. **Once a secret is pushed, treat it as leaked.** The only fix is to **rotate** it: revoke the token where it was issued, and use a new one. Everything after this lab is about not getting here.

## 4. Scan for secrets

`gitleaks` knows what hundreds of kinds of secret look like. `gitleaks git` scans every commit in the repo, and `-v` (verbose) shows each finding. At work you'd run the same scan in CI on every push, and over the whole history of an old repo when you take it over.

```text
gitleaks git -v
```

**Your turn:** before you run it, predict: will it flag the current `app.py`, the history, or both?

```sh
gitleaks git -v
```

<!-- dojo-reveal: Result of the scan -->

It finds the token in the first commit, with the file, line, commit and author that added it, and ends with `leaks found: 1`. The current file is clean; the history is not.

<!-- /dojo-reveal -->

## 5. Stop the next one before it's committed

Finding a leak after it's committed is too late. A **pre-commit hook** is a script git runs just before every commit: if the script fails, there is no commit. Git looks for hooks in the repo's `.git/hooks/` folder, and skips one it can't run, so the file must be executable.

A hook has limits. `git commit --no-verify` skips it. And nothing in `.git/` is ever committed, so your hook stays on your machine: everyone who clones the repo has to install it for themselves. A hook is a seatbelt for you, not a guarantee for the team. Teams add the same scan in CI and on the git server (push protection), and install hooks for everyone with a tool like `pre-commit`.

Open **leaky-app → `.git` → `hooks`** in VS Code: git put some `*.sample` scripts there when you ran `git init`. Create a new file in that folder named `pre-commit` (no extension), with this in it:

```sh
#!/bin/sh
# Before each commit: scan only what is about to be committed (--staged),
# and hide any secret it finds in the output (--redact).
exec gitleaks git --pre-commit --staged --redact -v
```

Save it, then make it executable:

```sh
chmod +x .git/hooks/pre-commit
```

Now make the same mistake again. Add this line to the end of `app.py` in VS Code, and save:

```python
BACKUP_TOKEN = "ghp_EXAMPLEfakeNotRealDoNotUse0000000002"
```

**Your turn:** try to commit it. Before you run it, predict: will the commit happen? What will the log show? `git checkout app.py` then throws away your change to the file and brings back the committed version.

```sh
git commit -am "Add the backup token"
git log --oneline   # still two commits
git checkout app.py
```

<!-- dojo-reveal: Results of the blocked commit -->

gitleaks prints a finding (the value shows as `REDACTED`) and **the commit doesn't happen**: the log still shows two commits. After the checkout, VS Code shows the line disappear.

<!-- /dojo-reveal -->

## Check yourself

1. You find a password in a commit from last year. You delete the line and push. Are you done?

<!-- dojo-reveal: Show the answer -->

No. It's still in history and in every clone. Rotate it.

<!-- /dojo-reveal -->

2. Why run gitleaks in CI as well as in a hook?

<!-- dojo-reveal: Show the answer -->

A hook works only in clones that switched it on, and can be skipped. CI sees every push.

<!-- /dojo-reveal -->

**Rules used:** 8 (never in git, including history), 7 (plan for leaks: rotation is the fix).

**Next:** [lab2.md](lab2.md)
