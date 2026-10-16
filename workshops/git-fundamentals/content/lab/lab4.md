# Lab 4 — Investigating History

"Who changed this? When? Why?" — these are the tools for answering that without asking around. They matter most once a repo has more than a handful of commits and more than one contributor, so this lab gives you a repo with a real past to investigate.

> **Starting here?** Run `dojo prep 4`. It builds the practice repo below, and it's safe to run even if you did the earlier labs.

## Set up your practice history

The shared sample repo has only a couple of commits, which isn't much to investigate. This command builds a practice repo in your terminal instead. It's yours alone and is never pushed:

```sh
lab-history
cd ~/lab/history-repo
```

It makes `~/lab/history-repo`: fifteen commits by two people (Alice and Bob) in a small `shop-config` project, with two feature branches that were merged, and a few things someone would want to explain. Run every command in this lab from that folder. If you break something, `lab-history --reset` rebuilds it from scratch.

---

## In this lab

| Command | What it does |
|---|---|
| `git log` | Browse history, one commit at a time, full detail |
| `git log --oneline` | One line per commit: short hash and message |
| `git log --oneline --graph --all` | The same, drawn as a graph of every branch |
| `git log --author=<name>` / `--since=<date>` | Only one person's commits, or only recent ones |
| `git show <commit>` | Show one commit's message and exactly what it changed |
| `git blame <file>` | Show which commit and author last changed each line |
| `git log -p <file>` | Show every change ever made to one file |
| `git log -S<text>` | Find the commits that added or removed some text |
| `gitleaks git` | Scan every commit for anything that looks like a credential |
| `git diff <a>..<b>` | Show everything that differs between two branches |

---

## The idea: history is a chain of snapshots

A commit is a snapshot of the whole project plus three pieces of metadata: an author, a message, and a pointer to its **parent** commit (a merge has two). Each commit is named by a hash, a long fingerprint of its contents, which `git log` shows shortened.

So history isn't a list of files that changed. It's a chain you walk backwards from your current commit, one parent at a time. Every command in this lab is a different way of walking that chain.

---

## 1. Browse the history

Three views of the same history, from most detail to most overview:

- `git log` gives full detail — author, date, full message — one commit per screen. Press `q` to exit the pager.
- `git log --oneline` gives one line per commit: short hash + message. This is the one you'll use most day to day.
- `git log --oneline --graph --all` is the same with a text graph of branches and merges. `--all` includes every branch, not just the one you're on.

```text
git log [--oneline] [--graph] [--all]
```

**Your turn:** run all three and predict how the output differs. Then answer from the graph: how many merge commits are there, which branch was merged first, and which of the two branches was started first?

```sh
git log
git log --oneline
git log --oneline --graph --all
```

<!-- dojo-reveal: Reading the graph -->

There are two merge commits (the ones where graph lines join), and the branches were merged in the opposite order from how they were started. Alice started `feature/logging` early, right after "Add database settings", and kept working on it. Bob started `feature/healthcheck` later, after "Remove client secret", but finished it sooner, so it was merged first. Both branch names are gone (they were deleted after merging), but their commits are still in the history, and the graph shows exactly where each one forked and rejoined.

<!-- /dojo-reveal -->

## 2. Filter down to what you need

On a real project `git log` is hundreds of commits. Filters let you read ten lines instead:

```text
git log --oneline --author=<name> --since=<date> --stat
```

`--stat` adds the list of files each commit touched.

**Your turn:** answer these from the history, using filters instead of scrolling. How many commits did Bob make? Which of them changed `config/app.yaml`? What happened on or after 7 August?

```sh
git log --oneline --author=Bob
git log --oneline --since=2026-08-07
git log --stat --oneline
```

## 3. See exactly what one commit changed

`git show <commit>` prints a commit's message and the diff it introduced — exactly what changed in that commit and no other.

```text
git show <commit>
```

**Your turn:** pick Bob's "Add database settings" commit from the log and note its short hash. Predict before you run `git show`: will it print the whole `config/app.yaml`, or only that commit's change?

```sh
git show <commit-hash>
```

<!-- dojo-reveal: Results of git show -->

Only that commit's change: the added lines marked with `+`, with a few unchanged lines around them for context. A commit stores a full snapshot, but `show` displays it as a diff against its parent, which is the part you care about.

<!-- /dojo-reveal -->

## 4. Find out who changed a line, and the story of a file

`git blame <file>` annotates every line with the commit, author, and date that last touched it. It's how you find out who to ask about a line — not to assign blame in the negative sense, despite the name.

```text
git blame <file>
```

**Your turn:** run it on the config. Predict: which lines will belong to Alice, which to Bob, and which commit owns the `timeout` line?

```sh
git blame config/app.yaml
```

<!-- dojo-reveal: Results of git blame -->

Each line is attributed to the commit that last changed it. The `timeout` line belongs to Alice's "Revert timeout to 30 seconds" commit, even though it reads exactly as it did originally: `blame` reports the last commit to *touch* a line, and the revert touched it.

<!-- /dojo-reveal -->

**Check yourself:** `blame` only tells you the *last* commit to touch a line. How would you see everything that has ever happened to the timeout, not just the latest change?

<!-- dojo-reveal: Show the answer -->

Run `git log -p config/app.yaml`. It lists only the commits that touched that file, newest first, with each commit's diff, so you can read the timeout going 30, then 5, then back to 30. The usual workflow is to run `blame` to find a suspicious line's commit, `git show` that hash to read the whole change and its message, and `git log -p` when you need the full story of the file.

<!-- /dojo-reveal -->

## 5. Hunt for a leaked secret

Somewhere in this history, someone committed an Azure client secret and a later commit took it out. The file looks clean now:

```sh
cat config/app.yaml
```

**Your turn:** Azure client secrets look like `abc8Q~...`, and this one started with `Dkx8Q~`. Find the commit that added it and the one that removed it. `-S` (the "pickaxe") lists commits where the number of occurrences of a string changed, which is exactly an add and a remove.

```text
git log -S<text> --oneline
```

```sh
git log -S"Dkx8Q~" --oneline
```

Then read the commit that added it, to see the secret itself:

```sh
git show <commit-that-added-it>
```

That worked because you already knew what to search for. Usually you don't. **A second option:** `gitleaks` knows what hundreds of kinds of credentials look like (Azure, AWS, GitHub tokens, private keys) and scans every commit for them, so you don't need to know the secret in advance.

```text
gitleaks git [path]
```

```sh
gitleaks git -v --no-banner .
```

Read the finding: the rule that matched, the file and line, and the commit and author. It points at the same commit the pickaxe did, without being told what to look for. Tools like this are what teams run in CI or a pre-commit hook to catch a secret before it is pushed.

<!-- dojo-reveal: What this tells you -->

The key is still there: in the "Add Azure client secret" commit's diff, and in every snapshot between that commit and the removal. Deleting a secret from the file only changes the latest snapshot; history keeps every earlier one, and anyone who clones the repo gets all of it.

So the fix for a leaked secret is never "commit a removal". **Revoke and replace the key first** (treat it as public), then, if you must, rewrite history with a tool like `git filter-repo` and force-push, which every collaborator then has to deal with. Better still, keep secrets out of the repo from the start: Bob's fix reads the key from an environment variable instead.

<!-- /dojo-reveal -->

## 6. Compare two branches

`git diff <branch>..<branch>` shows everything that differs between two branches — effectively the same diff a pull request would show a reviewer. To have something to compare, first make a branch with a change on it.

```text
git diff <from>..<to>
```

Create a throwaway branch from `main`:

```sh
git checkout -b lab4-explore
```

Open `config/app.yaml` in your editor, change `port: 8080` to `port: 9090`, and save.

**Prefer the terminal?**

```sh
sed -i 's/port: 8080/port: 9090/' config/app.yaml
```

Then commit it:

```sh
git add config/app.yaml
git commit -m "Lab 4: branch comparison example"
```

**Your turn:** compare `main` with `lab4-explore`. Predict: will your change show as added or deleted? Then think about direction: if you swapped the two names, what would change in the output?

```sh
git diff main..lab4-explore
```

<!-- dojo-reveal: Results of git diff main..lab4-explore -->

You see the old port line as a deletion (`-`) and the new one as an addition (`+`), because the diff reads as "what do I change in `main` to get `lab4-explore`". Swap them with `git diff lab4-explore..main` and the signs flip: the diff is now "how to get back to `main`". The first name is the "from", the second is the "to".

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
- `git log --author` / `--since` / `--stat` — filter history to the commits you care about.
- `git show <commit>` — see exactly what one commit changed.
- `git blame <file>` — see who last changed each line, and in which commit.
- `git log -p <file>` — see every change ever made to one file.
- `git log -S<text>` — find the commits that added or removed some text.
- `gitleaks git` — scan the whole history for secrets when you don't know what to search for.
- A secret removed in a later commit is still in history: revoke it, don't just delete it.
- `git diff <branch-1>..<branch-2>` — compare two branches directly.

**Next:** [lab5.md](lab5.md) — resolving a merge conflict and safely undoing a shared change.

---

## Challenge c2: The Detective (bonus)

Someone changed a line they shouldn't have. Find the commit, and say whose it was.

Only when your class has achievements on (you see a score on your landing page). Start it in the terminal:

```sh
dojo challenge start c2
cd ~/lab/challenge-repo
```

That makes your own repo `$USER/challenge-repo` and clones it to `~/lab/challenge-repo`, and prints the goal, with your own names in it. When you think it's done:

```sh
dojo check c2
```

A wrong answer costs nothing. `dojo check hint c2` gives a hint for part of the points, and
`dojo challenge reset c2` throws the repo away and starts you over from a fresh copy.

