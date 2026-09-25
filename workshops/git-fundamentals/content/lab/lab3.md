# Lab 3 — Stashing

**Optional.** Scenario: you're halfway through an edit, and you suddenly need to switch branches — check something on `main`, or help debug another branch — but you're not ready to commit what you have. `git stash` is the "set this aside for a minute" escape hatch.

Do this from your `sample-training-repo` clone, on your `add-yourname` branch.

---

## 1. Make an uncommitted edit

```sh
echo "- name: Work In Progress" >> roster/team.yaml
git status
```

`roster/team.yaml` shows as modified — this is deliberately unfinished work you're not ready to commit.

## 2. Stash it

```sh
git stash
git status
```

Your edit is gone from the working directory, and `git status` reports a clean tree — as if you'd never touched the file. It isn't lost, though; it's saved on a stack.

```sh
git stash list
```

## 3. Switch branches and come back

```sh
git checkout main
git status
git checkout add-yourname
```

You can move freely between branches with a clean tree. This is the whole point of stashing — no throwaway commit needed just to context-switch.

## 4. Bring your edit back

```sh
git stash pop
git status
git diff
```

Your edit is back, exactly as you left it, and it's off the stash stack (`git stash list` would now be empty). If you wanted to keep it on the stack instead of removing it, `git stash apply` does that — useful if you want to apply the same stashed change to more than one branch.

Clean up before moving on to the next lab:

```sh
git restore roster/team.yaml
```

---

## Recap

- `git stash` — set aside uncommitted changes, restoring a clean working tree.
- `git stash list` — see everything you've stashed.
- `git stash pop` — restore the most recent stash and remove it from the stack.
- `git stash apply` — restore the most recent stash but keep it on the stack too.
- Stashing is for short-term context switches, not long-term storage — if you're not coming back to it soon, commit it instead.

**Next:** [lab4.md](lab4.md) — investigating history with `log`, `blame`, and `show`.
