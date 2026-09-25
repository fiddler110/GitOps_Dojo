# Lab 1 — Leak it

**Goal:** commit a secret, "delete" it, and watch git keep it anyway. Then scan for secrets and put a guard in front of the next commit.

Everything here stays in a repo on your own terminal; nothing is pushed. The tokens below are made up, but they look real, which is the point.

---

## 1. A small app with a secret in it

If git doesn't know who you are yet, tell it once:

```bash
git config --global user.name "$USER"
git config --global user.email "$USER@dojo.test"
```

Make a repo and an app that talks to an API with a token written right into the code:

```bash
mkdir -p ~/lab/leaky-app && cd ~/lab/leaky-app
git init -b main
cat > app.py <<'EOF'
API_URL = "https://api.example.test"
API_TOKEN = "ghp_R8vK2mQx7LpT4nWz9HcY1bFs6DjE3aGu5VtN"

print(f"calling {API_URL}")
EOF
git add app.py
git commit -m "Add the app"
```

## 2. "Delete" it

A reviewer spots the token. You fix it the obvious way: read it from the environment instead.

```bash
cat > app.py <<'EOF'
import os

API_URL = "https://api.example.test"
API_TOKEN = os.environ["API_TOKEN"]

print(f"calling {API_URL}")
EOF
git commit -am "Read the API token from the environment"
cat app.py
```

The file is clean now. Is the token gone?

```bash
git log -p
```

Scroll down: the old commit still has it, in full. Anyone who clones this repo gets every commit, so they get the token too. You can also search the whole history for a string:

```bash
git log -S "ghp_" --oneline
```

**Once a secret is pushed, treat it as leaked.** Rewriting history (`git filter-repo`, a force-push) doesn't reach clones, forks, CI caches or backups that already have it. The only fix is to **rotate**: revoke the token and issue a new one. Everything after this is about not getting here.

## 3. Scan for secrets

`gitleaks` knows what hundreds of kinds of secret look like. Scan every commit in the repo:

```bash
gitleaks git -v
```

It finds the token in the first commit, with the file, line and commit that added it. Run the same scan in CI on every push and on the whole history of an old repo when you inherit one.

## 4. Stop the next one before it's committed

A **pre-commit hook** is a script git runs before every commit; if it fails, there is no commit. Make one that asks gitleaks to check only what you are about to commit:

```bash
cat > .git/hooks/pre-commit <<'EOF'
#!/bin/sh
exec gitleaks git --pre-commit --staged --redact -v
EOF
chmod +x .git/hooks/pre-commit
```

Now make the same mistake again, with a new token:

```bash
echo 'BACKUP_TOKEN = "ghp_Z3xQ9wLk2VbN7cRt5YmH8sJd4FgP1aKe6UoW"' >> app.py
git commit -am "Add the backup token"
```

gitleaks prints a finding (with the value redacted) and **the commit doesn't happen**:

```bash
git log --oneline   # still two commits
```

Put it right. Undo the change and commit nothing:

```bash
git checkout app.py
```

One catch: `git commit --no-verify` skips hooks, and hooks live in `.git/`, which isn't shared when someone clones. A hook is a seatbelt for you, not a guarantee for the team. Teams add the same scan in CI and on the git server (push protection), and install hooks for everyone with a tool like `pre-commit`.

## Check yourself

1. You find a password in a commit from last year. You delete the line and push. Are you done? *(No. It's still in history and in every clone. Rotate it.)*
2. Why run gitleaks in CI as well as in a hook? *(Hooks are per clone and can be skipped. CI sees every push.)*

**Rules used:** 8 (never in git, including history), 7 (plan for leaks: rotation is the fix).

**Next:** [lab2.md](lab2.md)
