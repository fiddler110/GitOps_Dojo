# Lab 4 — Investigating History

"Who changed this? When? Why?" — these are the tools for answering that without asking around. Especially useful once a repo has more than a handful of commits and more than one contributor.

Do this from your `sample-training-repo` clone (Lab 1, step 1, if you haven't cloned it yet). If you haven't made a commit of your own yet either, do Lab 1 steps 3-5 first so you have something in your own history to look at.

> **Starting here?** This lab needs the sample repo cloned. Run `lab-prep 4` to set that up; it's safe to run even if you did the earlier labs.

---

## 1. Browse recent commits

```sh
git log
```

Full detail — author, date, full message — one commit per screen. Press `q` to exit the pager.

```sh
git log --oneline
```

One line per commit: short hash + message. This is the one you'll use most day to day.

```sh
git log --oneline --graph --all
```

Same thing, but with a text graph of branches and merges — useful once there's more than one branch in play.

## 2. See exactly what one commit changed

Copy a commit hash from `git log --oneline` (your own most recent commit works well), then:

```sh
git show <commit-hash>
```

This prints the full diff introduced by that single commit — exactly what changed, in that commit and no other.

## 3. Find out who changed a specific line

```sh
git blame roster/team.yaml
```

Every line is annotated with the commit, author, and date that last touched it. This is how you find out who to ask about a specific line — not to assign blame in the negative sense, despite the name.

## 4. Compare two branches

```sh
git checkout -b lab4-explore
echo "- name: Branch Explorer" >> roster/team.yaml
git add roster/team.yaml
git commit -m "Lab 4: branch comparison example"
git diff main..lab4-explore
```

`git diff <branch>..<branch>` shows everything that differs between two branches — this is effectively the same diff a pull request would show a reviewer.

Clean up:

```sh
git checkout main
git branch -D lab4-explore
```

`lab4-explore` was never merged into `main`, so the safe `-d` delete would refuse it — capital `-D` forces the delete anyway. That's fine here because it's a disposable practice branch; on real work, a refusal from `-d` is usually git telling you something isn't merged yet, worth a second look before you force it.

---

## Recap

- `git log` / `git log --oneline` — browse history.
- `git log --oneline --graph --all` — visualize branches and merges.
- `git show <commit>` — see exactly what one commit changed.
- `git blame <file>` — see who last changed each line, and in which commit.
- `git diff <branch-1>..<branch-2>` — compare two branches directly.

**Next:** [lab5.md](lab5.md) — resolving a merge conflict and safely undoing a shared change.
