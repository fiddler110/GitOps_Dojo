# Lab 3 — Stashing

Scenario: you're halfway through an edit, and you suddenly need to switch branches — check something on `main`, or help debug another branch — but you're not ready to commit what you have. `git stash` is the "set this aside for a minute" escape hatch.

Do this from your `sample-training-repo` clone. Lab 1 deleted your old branch, so you'll make a fresh one for this lab in step 1 and delete it again at the end.

> **Starting here?** This lab needs the sample repo cloned. Run `dojo prep 3` to set that up; it's safe to run even if you did the earlier labs.

---

## In this lab

| Command | What it does |
|---|---|
| `git stash` | Save your uncommitted changes on a stack and reset the working tree to HEAD |
| `git stash list` | Show everything on the stash stack |
| `git checkout <branch>` | Switch to an existing branch |
| `git stash pop` | Re-apply the newest stash and remove it from the stack |
| `git stash apply` | Re-apply the newest stash but keep it on the stack |
| `git stash drop` | Remove a stash entry without applying it |
| `git restore <file>` | Discard uncommitted edits (Lab 2), used here for cleanup |

---

## The idea: why you can't just switch branches

Git won't let you switch branches if doing so would overwrite uncommitted work. You have two honest options: commit it (a half-finished commit nobody wants), or **stash** it.

A stash is a stack of saved snapshots, kept inside your repo but outside every branch. `git stash` takes your uncommitted changes to tracked files (staged and unstaged), saves them on top of the stack, and resets your working tree to match HEAD. Three things to remember:

- It is **local**: a stash is never pushed, and nobody else can see it.
- It belongs to the **repo, not to a branch**: you can create a stash on one branch and apply it on another.
- By default it saves **tracked files only**. A brand-new, untracked file stays in your working tree (`git stash -u` includes those).

---

## 1. Start on your own branch

The scenario needs two branches that differ. Lab 1 cleaned up its branch, so make a fresh one from an up-to-date `main` and give it a change of its own.

`git branch --show-current` prints the branch you are on.

**Your turn:** go to `main`, create a branch called `stash-demo`, and check you are on it. Predict what the last command prints.

```sh
git checkout main
git checkout -b stash-demo
git branch --show-current
```

Now give the branch a change of its own. Open `roster/team.yaml` in your editor, add your own entry at the bottom (for example `- name: Your Name`), and save. If you did Lab 1 you already have one; add another.

**Prefer the terminal?**

```sh
echo "- name: Your Name" >> roster/team.yaml
```

Commit it, so your branch now differs from `main`:

```sh
git add roster/team.yaml
git commit -m "Add my entry"
```

## 2. Make an uncommitted edit

`roster/team.yaml` is a tracked file, so any edit to it is exactly what a stash would save. Open it in your editor again, add a line such as `- name: Work In Progress` at the bottom, and save. Don't stage or commit it: this is deliberately unfinished work.

**Prefer the terminal?**

```sh
echo "- name: Work In Progress" >> roster/team.yaml
```

**Your turn:** before you run it, predict what `git status` will say about the file.

```sh
git status
```

- `roster/team.yaml` shows as modified.

## 3. Try to switch with unfinished work

Now the interruption: you need to look at something on `main`.

**Your turn:** try to switch to `main`. Predict: will git let you?

```sh
git checkout main
git branch --show-current
```

- Git refuses with `Your local changes to the following files would be overwritten by checkout: roster/team.yaml`, and you are still on your own branch.
- It refuses because `main` and your branch have different versions of `team.yaml`, and switching would overwrite your unsaved edit. That is the problem stash solves.

## 4. Stash it

The command that does this is plain `git stash`, and `git stash list` shows the stack.

```text
git stash
git stash list
```

**Your turn:** stash your edit. Before you run it, predict: what will `git status` say afterwards, and what will `git stash list` show?

```sh
git stash
git status
git stash list
```

- `git status` reports a clean tree, as if you'd never touched the file. Your committed entry is still there; only the unfinished edit was set aside.
- The edit isn't lost: `git stash list` shows one entry, something like `stash@{0}: WIP on stash-demo: ...`. The `{0}` is its position on the stack; the newest is always `0`.

## 5. Switch branches and come back

With a clean tree you can move freely between branches. This is the whole point of stashing — no throwaway commit needed just to context-switch.

**Your turn:** try the switch again, look around, and come back. Predict: will git let you switch this time, and will your commit from step 1 be visible on `main`?

```sh
git checkout main
git status
git log --oneline -3
git checkout stash-demo
```

- The switch succeeds with no complaint, and `git status` on `main` is clean.
- `main`'s log does not include your "Add my entry" commit; it lives only on your branch.

**Check yourself:** the stash belongs to the repo, not to a branch. If you ran `git stash pop` while you were on `main`, what would happen?

<!-- dojo-reveal: Show the answer -->

Git would apply your stashed edit to `main`'s working tree, as long as it doesn't conflict with what's there. It doesn't remember which branch it came from; the "WIP on stash-demo" label is only a note. That's handy when you realise you started work on the wrong branch, and a trap if you pop on the wrong one without looking at `git branch` first.

<!-- /dojo-reveal -->

## 6. Bring your edit back

A stash has two jobs when you bring it back: **re-apply** the saved changes to your working tree, and then either **keep** or **remove** the entry on the stack. The two commands differ only in that second part:

| Command | Re-applies the changes | The stash entry | Use it when |
|---|---|---|---|
| `git stash pop` | yes | **removed** from the stack | you're done with the stash: the normal "back to work" |
| `git stash apply` | yes | **kept** on the stack | you might need the same changes again |
| `git stash drop` | no | removed | you applied it earlier and the entry is just clutter now |

```text
git stash pop
git stash apply
git stash drop
```

**`pop` is the everyday one.** You stashed to deal with an interruption, the interruption is over, and you want your work back with nothing left behind. This is what you'll use nine times out of ten.

**`apply` is for when one copy isn't enough.** Some real examples:

- **The same change on two branches.** You made a fix on `main` by mistake, or a config tweak that two branches both need. `git stash` it, `git checkout` the first branch and `git stash apply`, then check out the second branch and `git stash pop`. With `pop` on the first branch the stash would already be gone.
- **A safety net.** You're about to try something risky with the changes (a big refactor, a messy merge). `apply` puts them back but keeps the stash, so if it goes wrong you can `git restore .` and apply the entry again.
- **A stash that might not fit.** If the branch you're on has changed the same lines, the changes can conflict. Either command stops and marks the conflict, and git then **keeps the entry** even for `pop`, so a conflicted `pop` can never lose your work. Resolve the conflict, then `git stash drop` to clear the entry yourself.

When there is more than one entry, `git stash list` numbers them, newest first. Name one to target it, such as `git stash pop stash@{1}`, and `git stash show -p stash@{1}` previews what is in it first.

**Your turn:** you're back on `stash-demo`. First use the **keeping** form. Predict: will your edit come back, and will `git stash list` still show the entry?

```sh
git stash apply
git status
git stash list
```

- Your edit is back in `roster/team.yaml`, exactly as you left it.
- `git stash list` still shows `stash@{0}`: `apply` doesn't remove the entry.

**Your turn:** now compare with the removing form. Throw the edit away again, then bring it back with `pop`. Predict: what will `git stash list` show this time?

```sh
git restore roster/team.yaml
git stash pop
git diff
git stash list
```

- The edit is back again, the same as before.
- `git stash list` is now empty: `pop` re-applied the changes **and** removed the entry.

**Check yourself:** you run `git stash pop` on a branch where the same line of `team.yaml` has been changed, and git reports a conflict. Is your stash still on the stack? What do you do next?

<!-- dojo-reveal: Show the answer -->

Yes, it's still there. When `pop` hits a conflict, git applies what it can, marks the conflict in the file, and **leaves the entry on the stack** so nothing is lost. Resolve the markers in the file (the same way as a merge conflict, which Lab 5 covers), then run `git stash drop` to remove the entry by hand once you're happy.

<!-- /dojo-reveal -->

Clean up before moving on to the next lab. Discard the edit, go back to `main` and delete the practice branch (`-D`, because its commit was never merged):

```sh
git restore roster/team.yaml
git checkout main
git branch -D stash-demo
```

---

## Recap

- `git stash` — set aside uncommitted changes to tracked files, restoring a clean working tree. It's local, and belongs to the repo rather than a branch.
- `git stash list` — see everything you've stashed.
- `git stash pop` — restore the most recent stash and remove it from the stack.
- `git stash apply` — restore the most recent stash but keep it on the stack too: for the same change on two branches, or as a safety net.
- `git stash drop` — remove an entry by hand. A conflicted `pop` keeps its entry, so you drop it yourself once resolved.
- Stashing is for short-term context switches, not long-term storage — if you're not coming back to it soon, commit it instead.

**Next:** [lab4.md](lab4.md) — investigating history with `log`, `blame`, and `show`.
