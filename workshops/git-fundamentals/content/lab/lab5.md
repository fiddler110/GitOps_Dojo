# Lab 5 — Merge Conflicts & Safely Undoing a Change

Two topics that go together: what happens when git *can't* merge automatically, and how to undo something once it's out there — safely.

Do this from your `sample-training-repo` clone. This lab creates its own throwaway branches, so it won't interfere with your Lab 1 branch.

> **Starting here?** This lab needs the sample repo cloned. Run `lab-prep 5` to set that up; it's safe to run even if you did the earlier labs.

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

```sh
git checkout main
git checkout -b conflict-a
```

Edit `roster/team.yaml` and change Alice's role — for example:

```yaml
- name: Alice Engineer
  role: Senior Engineer
```

```sh
git add roster/team.yaml
git commit -m "conflict-a: update Alice's role"
git checkout main
git checkout -b conflict-b
```

Now, on this second branch, edit **the same line** to something different:

```yaml
- name: Alice Engineer
  role: Principal Engineer
```

```sh
git add roster/team.yaml
git commit -m "conflict-b: update Alice's role"
```

Now try to bring both changes together. You're on `conflict-b`, so this merges `conflict-a` *into* it:

```sh
git merge conflict-a
```

Git stops and reports a conflict. Look at the file:

```sh
batcat roster/team.yaml
```

You'll see the two versions of the line, wrapped in markers:

```yaml
- name: Alice Engineer
<<<<<<< HEAD
  role: Principal Engineer
=======
  role: Senior Engineer
>>>>>>> conflict-a
```

**Your turn:** which role is yours (the branch you're on) and which is the incoming one? Work out which side of `=======` each is on.

<!-- dojo-reveal: Show the answer -->
- Everything between `<<<<<<< HEAD` and `=======` is your **current** branch's version (`conflict-b`: Principal Engineer). `HEAD` is the commit you're on.
- Everything between `=======` and `>>>>>>> conflict-a` is the **incoming** branch's version (Senior Engineer), labelled with the branch you asked to merge.

The markers are written into the file itself, which is why a conflicted file won't build or parse until you've cleaned them up.
<!-- /dojo-reveal -->

**Resolve it:** open the file, decide which version to keep (or combine them), and delete the `<<<<<<<`, `=======`, `>>>>>>>` markers yourself — git won't do this part for you. For example, keep just:

```yaml
- name: Alice Engineer
  role: Principal Engineer
```

Then finish the merge. Saving the file isn't enough: `git add` is how you tell git "this conflict is resolved", and the commit completes the merge.

```sh
git add roster/team.yaml
git commit
```

Git pre-fills a merge commit message — accepting the default is fine. This commit has **two parents**, one for each side, which is what makes it a merge. If you ever want to back out of a conflict entirely and start over:

```sh
git merge --abort
```

(No need to run that now — your merge is already resolved.)

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

Set up a commit to undo:

```sh
git checkout -b undo-demo
echo "- name: Oops Entry" >> roster/team.yaml
git add roster/team.yaml
git commit -m "Oops, wrong entry"
```

**Your turn:** undo that commit but keep the edit staged, ready to commit again with a better message. Predict what `git status` will show.

<!-- dojo-reveal: Show the command and what you should see -->
```sh
git reset --soft HEAD~1
git status
```

The commit is gone from the log, and `roster/team.yaml` is under "Changes to be committed": exactly as if you'd just run `git add`. Nothing was lost.
<!-- /dojo-reveal -->

**Your turn:** now throw it away completely — undo the commit *and* the edit. Commit it again first, since `--soft` left it staged:

```sh
git commit -m "Oops, wrong entry"
```

<!-- dojo-reveal: Show the command and what you should see -->
```sh
git reset --hard HEAD~1
git status
```

Clean tree, and the "Oops Entry" line is gone from the file. `--hard` also discards any *other* uncommitted edits in your working directory, and there's no confirmation, so only use it when you're sure you don't need the change.
<!-- /dojo-reveal -->

### Committed *and* pushed

**Do not use `git reset` here.** Rewriting history that someone else may have already pulled breaks their local repo: their copy still has the commit you erased, and git sees two histories that disagree.

**Check yourself:** so how do you undo a commit that other people already have, without erasing it?

<!-- dojo-reveal: Show the answer -->
You add a new commit that does the opposite. That's `git revert <commit>`: the original commit stays in history, a "Revert ..." commit goes on top, and anyone who pulls just receives one more normal commit. History only ever moves forward.
<!-- /dojo-reveal -->

This demo stays local — no need to actually push it — but the same command is what you'd run on a real shared branch. Make a commit to revert:

```sh
echo "- name: Reverted Later" >> roster/team.yaml
git add roster/team.yaml
git commit -m "Example commit to revert"
git log --oneline -1
```

**Your turn:** undo that commit the safe way, then look at the last two commits. Predict: will the original commit still be in the log?

<!-- dojo-reveal: Show the command and what you should see -->
```sh
git revert HEAD --no-edit
git log --oneline -2
```

Yes, both are there: the new "Revert ..." commit on top, and your original underneath it. The `-2` caps how many commits `git log` shows, and `--no-edit` accepts git's auto-generated message instead of opening an editor. The file's content is back to what it was, but the history records both the mistake and the fix, which is exactly what makes it safe once something is shared.
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

## Capstone: The Great Merge (bonus)

Two feature branches change the same spot, and one of them also broke something. Bring both into `main` through a
pull request, keep both changes, and undo the broken commit the safe way.

Only when your class has achievements on (you see a score on your landing page). Start it in the terminal:

```sh
dojo-challenge start capstone
cd ~/lab/challenge-repo
```

That makes your own repo `$USER/challenge-repo` and clones it to `~/lab/challenge-repo`, and prints the goal, with your own names in it. When you think it's done:

```sh
dojo-check capstone
```

A wrong answer costs nothing. `dojo-check hint capstone` gives a hint for part of the points, and
`dojo-challenge reset capstone` throws the repo away and starts you over from a fresh copy.

<!-- dojo-challenge: capstone -->
