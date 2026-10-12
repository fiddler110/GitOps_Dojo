# Lab 3 — Stashing

Scenario: you're halfway through an edit, and you suddenly need to switch branches — check something on `main`, or help debug another branch — but you're not ready to commit what you have. `git stash` is the "set this aside for a minute" escape hatch.

Do this from your `sample-training-repo` clone, on your `add-yourname` branch.

> **Starting here?** This lab needs the sample repo cloned and a branch of your own (Lab 1 step 2). Run `lab-prep 3` to set that up; it's safe to run even if you did the earlier labs.

---

## In this lab

| Command | What it does |
|---|---|
| `git stash` | Save your uncommitted changes on a stack and reset the working tree to HEAD |
| `git stash list` | Show everything on the stash stack |
| `git checkout <branch>` | Switch to an existing branch |
| `git stash pop` | Re-apply the newest stash and remove it from the stack |
| `git stash apply` | Re-apply the newest stash but keep it on the stack |
| `git restore <file>` | Discard uncommitted edits (Lab 2), used here for cleanup |

---

## The idea: why you can't just switch branches

Git won't let you switch branches if doing so would overwrite uncommitted work. You have two honest options: commit it (a half-finished commit nobody wants), or **stash** it.

A stash is a stack of saved snapshots, kept inside your repo but outside every branch. `git stash` takes your uncommitted changes to tracked files (staged and unstaged), saves them on top of the stack, and resets your working tree to match HEAD. Three things to remember:

- It is **local**: a stash is never pushed, and nobody else can see it.
- It belongs to the **repo, not to a branch**: you can create a stash on one branch and apply it on another.
- By default it saves **tracked files only**. A brand-new, untracked file stays in your working tree (`git stash -u` includes those).

---

## 1. Make an uncommitted edit

```sh
echo "- name: Work In Progress" >> roster/team.yaml
git status
```

`roster/team.yaml` shows as modified — this is deliberately unfinished work you're not ready to commit.

## 2. Stash it

The command that does this is plain `git stash`, and `git stash list` shows the stack.

**Your turn:** stash your edit. Before you run it, predict: what will `git status` say afterwards, and what will `git stash list` show?

<!-- dojo-reveal: Show the commands and what you should see -->
```sh
git stash
git status
git stash list
```

`git status` reports a clean tree, as if you'd never touched the file. The edit isn't lost: `git stash list` shows one entry, something like `stash@{0}: WIP on add-yourname: ...`. The `{0}` is its position on the stack; the newest is always `0`.
<!-- /dojo-reveal -->

## 3. Switch branches and come back

```sh
git checkout main
git status
git checkout add-yourname
```

With a clean tree you can move freely between branches. This is the whole point of stashing — no throwaway commit needed just to context-switch.

**Check yourself:** the stash belongs to the repo, not to a branch. If you ran `git stash pop` while you were on `main`, what would happen?

<!-- dojo-reveal: Show the answer -->
Git would apply your stashed edit to `main`'s working tree, as long as it doesn't conflict with what's there. It doesn't remember which branch it came from; the "WIP on add-yourname" label is only a note. That's handy when you realise you started work on the wrong branch, and a trap if you pop on the wrong one without looking at `git branch` first.
<!-- /dojo-reveal -->

## 4. Bring your edit back

There are two ways to re-apply a stash: **`git stash pop`** applies it and removes it from the stack, while **`git stash apply`** applies it and leaves it on the stack.

**Your turn:** you're back on `add-yourname`. Get your edit back, then decide which of the two to use if you wanted the same change on *two* branches.

<!-- dojo-reveal: Show the commands and the answer -->
```sh
git stash pop
git status
git diff
git stash list
```

Your edit is back exactly as you left it, and `git stash list` is now empty. To put the same change on two branches you'd use `git stash apply` on the first branch (the entry stays on the stack), switch, and then `pop` (or `apply` again) on the second.
<!-- /dojo-reveal -->

Clean up before moving on to the next lab:

```sh
git restore roster/team.yaml
```

---

## Recap

- `git stash` — set aside uncommitted changes to tracked files, restoring a clean working tree. It's local, and belongs to the repo rather than a branch.
- `git stash list` — see everything you've stashed.
- `git stash pop` — restore the most recent stash and remove it from the stack.
- `git stash apply` — restore the most recent stash but keep it on the stack too.
- Stashing is for short-term context switches, not long-term storage — if you're not coming back to it soon, commit it instead.

**Next:** [lab4.md](lab4.md) — investigating history with `log`, `blame`, and `show`.
