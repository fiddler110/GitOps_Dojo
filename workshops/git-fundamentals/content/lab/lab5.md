# Lab 5 — Merge Conflicts & Safely Undoing a Change

Two topics that go together: what happens when git *can't* merge automatically, and how to undo something once it's out there — safely.

Do this from your `sample-training-repo` clone, on `main`. This lab creates its own throwaway branches and deletes them again, and the commands start from `main` each time.

> **Starting here?** This lab needs the sample repo cloned. Run `dojo prep 5` to set that up; it's safe to run even if you did the earlier labs.

---

## In this lab

| Command | What it does |
|---|---|
| `git merge <branch>` | Combine another branch's commits into the current branch |
| `git merge --abort` | Back out of a conflicted merge and return to before it |
| `git add` + `git commit` | Mark a conflict resolved and finish the merge |
| `git reset --soft HEAD~1` | Undo the last commit, keeping its changes staged |
| `git reset --hard HEAD~1` | Undo the last commit and discard its changes |
| `git revert <commit>` | Undo a commit by adding a new commit that reverses it |
| `git log --oneline -n` | Show only the last `n` commits |

---

## Part A — Causing and resolving a conflict

### The idea

A merge combines two lines of history. Git compares both branches against the commit they came from (their common ancestor). If only one side changed a line, it takes that change. If **both sides changed the same line differently**, git has no way to know which you meant, so it stops and asks you. That is a conflict: a question git can't answer, not an error.

Normally the two sides are two different people. Here you'll play both parts yourself so you can see it end to end without needing a partner.

When git can't merge, it writes **conflict markers** into the file itself, wrapping the two versions of the disputed lines:

```yaml
- name: Alice Engineer
<<<<<<< HEAD
  role: Principal Engineer
=======
  role: Senior Engineer
>>>>>>> conflict-a
```

Everything between `<<<<<<< HEAD` and `=======` is your **current** branch's version, and everything between `=======` and `>>>>>>> <branch>` is the **incoming** branch's version. The markers are in the file, so a conflicted file won't build or parse until you've cleaned them up, and git won't do that part for you. Saving the file isn't enough to finish: `git add` tells git "this conflict is resolved", and the commit completes the merge. That commit has **two parents**, one for each side, which is what makes it a merge.

```text
git merge <branch>
git merge --abort
```

If you ever want to back out of a conflict entirely and start over, `git merge --abort` returns you to before the merge. (You won't need it today if you resolve cleanly.)

### Side one

Create the first branch from `main`:

```sh
git checkout main
git checkout -b conflict-a
```

Open `roster/team.yaml` in your editor and change Alice's role — for example:

```yaml
- name: Alice Engineer
  role: Senior Engineer
```

Save, then commit:

```sh
git add roster/team.yaml
git commit -m "conflict-a: update Alice's role"
git checkout main
git checkout -b conflict-b
```

### Side two

Now, on this second branch, open the file again and edit **the same line** to something different:

```yaml
- name: Alice Engineer
  role: Principal Engineer
```

Save, then commit:

```sh
git add roster/team.yaml
git commit -m "conflict-b: update Alice's role"
```

### Merge them

**Your turn:** you're on `conflict-b`, so this merges `conflict-a` *into* it. Predict: will git finish on its own? Then, once you open the file, work out which role is yours and which is incoming.

```sh
git merge conflict-a
batcat roster/team.yaml
```

<!-- dojo-reveal: Results of git merge conflict-a -->

- Git stops and reports a conflict in `roster/team.yaml`.
- The file shows the markers shown above. Between `<<<<<<< HEAD` and `=======` is your current branch (`conflict-b`: Principal Engineer); between `=======` and `>>>>>>> conflict-a` is the incoming one (Senior Engineer).

<!-- /dojo-reveal -->

**Resolve it:** open the file in your editor, decide which version to keep (or combine them), and delete the `<<<<<<<`, `=======`, `>>>>>>>` markers yourself. For example, keep just:

```yaml
- name: Alice Engineer
  role: Principal Engineer
```

Then finish the merge. Git pre-fills a merge commit message — accepting the default is fine.

```sh
git add roster/team.yaml
git commit
git log --oneline --graph -4
```

<!-- dojo-reveal: Results of finishing the merge -->

- The merge commit appears on top, with the graph showing both branches joining.

<!-- /dojo-reveal -->

Clean up:

```sh
git checkout main
git branch -D conflict-a conflict-b
```

---

## Part B — Undoing a change safely

### The idea

The right way to undo something depends on whether anyone else could already have it.

| Where is the change? | Safe tool | Why |
|---|---|---|
| Edited, not committed | `git restore` (see [lab2.md](lab2.md)) | Only your working tree is affected |
| Committed, **not pushed** | `git reset` | You're rewriting history nobody else has |
| Committed **and pushed** | `git revert` | It adds a new commit, so history only moves forward |

### Committed, but not pushed

Nobody else has it, so you can rewrite history freely. You already did this once: [lab1.md](lab1.md) step 9 used `git reset --hard` to move `main` back after committing on it by mistake. Here it's the same command for its own sake, on a throwaway branch.

`git reset` moves your branch pointer (and `HEAD`) back to an earlier commit. `HEAD~1` means "one commit before `HEAD`": `HEAD` is your current commit, so `HEAD~1` is its parent. The flag decides what happens to the changes in the commit you stepped back over:

| Flag | The commit | Staging area | Working tree |
|---|---|---|---|
| `--soft` | undone | changes **kept staged** | untouched |
| `--hard` | undone | cleared | **reset to match: edits lost** |

```text
git reset --soft HEAD~1
git reset --hard HEAD~1
```

Set up a commit to undo. Start on a new branch off `main`:

```sh
git checkout main
git checkout -b undo-demo
```

Open `roster/team.yaml` in your editor, add a line `- name: Oops Entry`, and save.

**Prefer the terminal?**

```sh
echo "- name: Oops Entry" >> roster/team.yaml
```

Then commit it:

```sh
git add roster/team.yaml
git commit -m "Oops, wrong entry"
```

**Your turn:** undo that commit but keep the edit staged, ready to commit again with a better message. Predict what `git status` will show.

```sh
git reset --soft HEAD~1
git status
```

<!-- dojo-reveal: Results of git reset --soft -->

The commit is gone from the log, and `roster/team.yaml` is under "Changes to be committed": exactly as if you'd just run `git add`. Nothing was lost.

<!-- /dojo-reveal -->

**Your turn:** now throw it away completely — undo the commit *and* the edit. Commit it again first, since `--soft` left it staged. Predict: will the "Oops Entry" line survive?

```sh
git commit -m "Oops, wrong entry"
git reset --hard HEAD~1
git status
```

<!-- dojo-reveal: Results of git reset --hard -->

Clean tree, and the "Oops Entry" line is gone from the file. `--hard` also discards any *other* uncommitted edits in your working directory, and there's no confirmation, so only use it when you're sure you don't need the change.

<!-- /dojo-reveal -->

### Committed *and* pushed

**Do not use `git reset` here.** Rewriting history that someone else may have already pulled breaks their local repo: their copy still has the commit you erased, and git sees two histories that disagree.

**Check yourself:** so how do you undo a commit that other people already have, without erasing it?

<!-- dojo-reveal: Show the answer -->
You add a new commit that does the opposite. That's `git revert <commit>`: the original commit stays in history, a "Revert ..." commit goes on top, and anyone who pulls just receives one more normal commit. History only ever moves forward.

<!-- /dojo-reveal -->

```text
git revert <commit> [--no-edit]
```

This demo stays local — no need to actually push it — but the same command is what you'd run on a real shared branch. Make a commit to revert: open `roster/team.yaml` in your editor, add `- name: Reverted Later`, and save.

**Prefer the terminal?**

```sh
echo "- name: Reverted Later" >> roster/team.yaml
```

Then commit it:

```sh
git add roster/team.yaml
git commit -m "Example commit to revert"
git log --oneline -1
```

**Your turn:** undo that commit the safe way, then look at the last two commits. Predict: will the original commit still be in the log? (`-2` caps how many commits `git log` shows, and `--no-edit` accepts git's auto-generated message instead of opening an editor.)

```sh
git revert HEAD --no-edit
git log --oneline -2
```

<!-- dojo-reveal: Results of git revert -->

Yes, both are there: the new "Revert ..." commit on top, and your original underneath it. The file's content is back to what it was, but the history records both the mistake and the fix, which is exactly what makes it safe once something is shared.

<!-- /dojo-reveal -->

Clean up:

```sh
git checkout main
git branch -D undo-demo
```

---

## Recap

- **Conflict:** both branches changed the same line, so git can't choose. It marks `<<<<<<<` / `=======` / `>>>>>>>` around the disputed lines; you resolve by hand, then `git add` + `git commit`. `git merge --abort` bails out entirely if needed.
- **Not committed:** `git restore` (Lab 2).
- **Committed, not shared:** `git reset` is safe — it rewrites your own local history. `--soft` keeps the changes staged, `--hard` discards them.
- **Committed and shared:** `git revert` is safe — it adds a new commit instead of rewriting history.

You've now covered the full loop (Lab 1) plus the most common "something went sideways" tools. That's the everyday git toolkit — see [README.md](README.md) for the quick reference, and don't hesitate to ask the facilitator about anything that came up.

---

## Capstone (bonus)

Only when your class has achievements on (you see a score on your landing page). A capstone is a goal with no steps, in
a repo of your own, for extra points. Start it in the terminal:

```sh
dojo challenge start capstone
cd ~/lab/challenge-repo
```

That makes your own repo `$USER/challenge-repo`, clones it to `~/lab/challenge-repo` and shows your brief. The brief is
saved as `~/capstone.md` with your own names filled in; read it again any time with `glow ~/capstone.md`. When you think
it's done:

```sh
dojo check capstone
```

A wrong answer costs nothing. `dojo check hint capstone` gives a hint for part of the points (hints already used stay used).

**Start over.** `dojo challenge reset capstone` deletes `~/lab/challenge-repo` (including any uncommitted work),
builds a fresh copy and clones it, as often as you like. Use it if the repo is in a mess, or if you fixed it a way the
check can't recognise.

## The Great Merge

It's release day. Alice's `feature-a` and Bob's `feature-b` are both finished and have to ship together on `main`, but
the release has three problems hiding in it:

1. Both features added their line to the end of `CHANGELOG.md`, so git can't combine them on its own.
2. A commit on `feature-b`, "Make deploys faster", set `timeout_seconds` to 0 and breaks every deploy.
3. Alice committed her `debug.log` test output on `feature-a`, and nothing stops it happening again.

Get a clean release onto `main`. How you do it is up to you, as long as the end result below is true. Everything you
need is in the labs: Lab 2 (`.gitignore`, untracking a file), Lab 4 (reading history) and Lab 5 (conflicts and `git revert`).

**About the branches.** Both feature branches are already in your clone, but only as remote-tracking branches, so
`git branch` shows just `main`. See them with `git branch -a` (`origin/feature-a`, `origin/feature-b`). You can merge
`origin/feature-a` straight in, or make a local copy to look around first:

```sh
git switch feature-a        # creates a local feature-a that tracks origin/feature-a
git log --oneline main..feature-a
git switch main
```

If they ever seem missing, `git fetch origin` brings them down.

**End result (what the check looks for)**

- Work in your own repo `<you>/challenge-repo`.
- `main` changes only through a **merged pull request** (from any branch, built any way you like). Pushing straight to `main` fails the check.
- `CHANGELOG.md` on `main` has **both** feature lines and none of the `<<<<<<<`, `=======`, `>>>>>>>` marker lines.
- `config/settings.yaml` on `main` has `timeout_seconds: 30`. Revert the commit, fix the value forward, or leave that commit out of your merge: all count.
- `debug.log` is **not** on `main`, and `.gitignore` on `main` ignores it (a rule like `*.log`).
- The **history is intact**: every commit `main` started with is still there. A force-push, or rebasing or squashing `main`, fails the check. Never rewrite shared history.
