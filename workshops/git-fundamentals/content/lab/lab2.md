# Lab 2 — Reviewing & Undoing Before You Commit

**Optional.** Not everything you type is meant to be kept. This lab practices catching mistakes before they become part of your history — discarding an edit, unstaging a file, and keeping local-only files out of git entirely.

Do this from your `sample-training-repo` clone, on your `add-yourname` branch from Lab 1 (or any branch — nothing here needs to be pushed).

> **Starting here?** This lab needs the sample repo cloned. Run `lab-prep 2` to set that up; it's safe to run even if you did the earlier labs.

---

## 1. Make an edit you don't want

```sh
echo "- name: Test Entry" >> roster/team.yaml
git status
```

`git status` shows `roster/team.yaml` as modified. Suppose you decide this edit was a mistake and you want the file back exactly as it was.

## 2. Discard it

```sh
git restore roster/team.yaml
git status
```

The file is back to its last-committed state, and `git status` shows a clean working tree. `git restore` only works on changes you haven't committed — that's the point of it. **This is destructive and unrecoverable for uncommitted work**, so only use it when you're sure.

---

## 3. Stage something, then change your mind

```sh
echo "- name: Another Test" >> roster/team.yaml
git add roster/team.yaml
git status
```

Notice `git status` now shows the file staged ("Changes to be committed"), not just modified.

```sh
git restore --staged roster/team.yaml
git status
```

This unstages the file — the edit is still there in your working directory, it's just no longer marked to go into the next commit. Staging and committing are two separate decisions; this is how you back out of the first one without losing your work.

Clean up before moving on:

```sh
git restore roster/team.yaml
```

---

## 4. Keep local-only files out of git

Not every file that shows up in `git status` should be committed — build output, editor settings, local secrets. That's what `.gitignore` is for.

```sh
touch scratch.log
git status
```

`scratch.log` shows up as untracked. Now tell git to ignore it:

```sh
echo "*.log" >> .gitignore
git status
```

`scratch.log` no longer appears. `git status` only shows `.gitignore` itself as a new, untracked file — which, unlike `scratch.log`, you'd actually want to commit so the rule applies for everyone who clones the repo.

Clean up (this is a throwaway exercise, not something to commit):

```sh
rm scratch.log .gitignore
git status
```

**Important:** `.gitignore` only affects *untracked* files. It does not stop tracking a file git already committed, and it does not remove a secret from history — if a secret was ever committed, treat it as exposed and rotate it, don't just add it to `.gitignore` afterward.

---

## Recap

- `git restore <file>` — discard uncommitted changes to a file.
- `git restore --staged <file>` — unstage a file without losing the edit.
- `.gitignore` — stop new, untracked files from showing up in `git status` at all.

**Next:** [lab3.md](lab3.md) — stashing, for when you need to switch branches mid-edit.
