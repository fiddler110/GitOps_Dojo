# Lab 4 — Investigating History

"Who changed this? When? Why?" — these are the tools for answering that without asking around. Especially useful once a repo has more than a handful of commits and more than one contributor.

Do this from your `sample-training-repo` clone (Lab 1, step 1, if you haven't cloned it yet). If you haven't made a commit of your own yet either, do Lab 1 steps 3-5 first so you have something in your own history to look at.

> **Starting here?** This lab needs the sample repo cloned. Run `lab-prep 4` to set that up; it's safe to run even if you did the earlier labs.

---

## In this lab

| Command | What it does | Section |
|---|---|---|
| `git log` | Browse history, one commit at a time, full detail | 1 |
| `git log --oneline` | One line per commit: short hash and message | 1 |
| `git log --oneline --graph --all` | The same, drawn as a graph of every branch | 1 |
| `git show <commit>` | Show one commit's message and exactly what it changed | 2 |
| `git blame <file>` | Show which commit and author last changed each line | 3 |
| `git log -p <file>` | Show every change ever made to one file | 3 |
| `git diff <a>..<b>` | Show everything that differs between two branches | 4 |

---

## The idea: history is a chain of snapshots

A commit is a snapshot of the whole project plus three pieces of metadata: an author, a message, and a pointer to its **parent** commit (a merge has two). Each commit is named by a hash, a long fingerprint of its contents, which `git log` shows shortened.

So history isn't a list of files that changed. It's a chain you walk backwards from your current commit, one parent at a time. Every command in this lab is a different way of walking that chain.

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

Same thing, but with a text graph of branches and merges — useful once there's more than one branch in play. `--all` includes every branch, not just the one you're on.

**Your turn:** find your own Lab 1 commit in the list and note its short hash. You'll use it next.

## 2. See exactly what one commit changed

`git show <commit>` prints a commit's message and the diff it introduced — exactly what changed in that commit and no other.

**Your turn:** use it on your own commit, and predict before you run it: will it show your whole `team.yaml` file, or only your change?

<!-- dojo-reveal: Show the command and what you should see -->
```sh
git show <commit-hash>
```

Only your change: the added lines marked with `+`, with a few unchanged lines around them for context. A commit stores a full snapshot, but `show` displays it as a diff against its parent, which is the part you care about.
<!-- /dojo-reveal -->

## 3. Find out who changed a specific line

```sh
git blame roster/team.yaml
```

Every line is annotated with the commit, author, and date that last touched it. This is how you find out who to ask about a specific line — not to assign blame in the negative sense, despite the name.

**Check yourself:** `blame` only tells you the *last* commit to touch a line. How would you see everything that has ever happened to this file, not just the latest change?

<!-- dojo-reveal: Show the answer -->
```sh
git log -p roster/team.yaml
```

`git log -p <file>` lists only the commits that touched that file, newest first, with each commit's diff. The usual workflow is to run `blame` to find a suspicious line's commit, `git show` that hash to read the whole change and its message, and `git log -p` when you need the full story of the file.
<!-- /dojo-reveal -->

## 4. Compare two branches

```sh
git checkout -b lab4-explore
echo "- name: Branch Explorer" >> roster/team.yaml
git add roster/team.yaml
git commit -m "Lab 4: branch comparison example"
```

`git diff <branch>..<branch>` shows everything that differs between two branches — this is effectively the same diff a pull request would show a reviewer.

**Your turn:** compare `main` with `lab4-explore`. Then think about direction: if you swapped the two names, what would change in the output?

<!-- dojo-reveal: Show the command and the answer -->
```sh
git diff main..lab4-explore
```

You see your new line as an addition (`+`), because the diff reads as "what do I change in `main` to get `lab4-explore`". Swap them with `git diff lab4-explore..main` and the same line shows as a deletion (`-`): the diff is now "how to get back to `main`". The first name is the "from", the second is the "to".
<!-- /dojo-reveal -->

Clean up:

```sh
git checkout main
git branch -D lab4-explore
```

`lab4-explore` was never merged into `main`, so the safe `-d` delete would refuse it — capital `-D` forces the delete anyway. That's fine here because it's a disposable practice branch; on real work, a refusal from `-d` is usually git telling you something isn't merged yet, worth a second look before you force it.

---

## Recap

- A commit is a snapshot, an author, a message and a pointer to its parent; history is the chain of parents.
- `git log` / `git log --oneline` — browse history.
- `git log --oneline --graph --all` — visualize branches and merges.
- `git show <commit>` — see exactly what one commit changed.
- `git blame <file>` — see who last changed each line, and in which commit.
- `git log -p <file>` — see every change ever made to one file.
- `git diff <branch-1>..<branch-2>` — compare two branches directly.

**Next:** [lab5.md](lab5.md) — resolving a merge conflict and safely undoing a shared change.

---

## Challenge c2: The Detective (bonus)

Someone changed a line they shouldn't have. Find the commit, and say whose it was.

Only when your class has achievements on (you see a score on your landing page). Start it in the terminal:

```sh
dojo-challenge start c2
cd ~/lab/challenge-repo
```

That makes your own repo `$USER/challenge-repo` and clones it to `~/lab/challenge-repo`, and prints the goal, with your own names in it. When you think it's done:

```sh
dojo-check c2
```

A wrong answer costs nothing. `dojo-check hint c2` gives a hint for part of the points, and
`dojo-challenge reset c2` throws the repo away and starts you over from a fresh copy.

<!-- dojo-challenge: c2 -->
