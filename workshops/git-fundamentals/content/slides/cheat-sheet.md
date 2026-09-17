---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/cheat-sheet.css');
footer: '[&larr; Hub](index.md) &nbsp;|&nbsp; Git Fundamentals | Cheat Sheet'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# Cheat Sheet

## Every command from Labs 1-5, in one place

Keep this open in a split pane or another tab while you work — you don't
need to memorize any of it.

<p class="nav">Full detail: <code>~/lab/cheat-sheet.md</code> in your terminal.</p>

---

## Get the repo

```sh
git clone <repository-url>   # full copy, once per repo
cd <repo-name>
git pull                     # get the latest from the remote
```

`clone` downloads every commit and branch, not just the current snapshot.
`pull` fetches and merges new commits — run it whenever you start work.

---

## Branch, review, commit, push

```sh
git checkout -b <branch-name>   # create + switch, one step

git status                      # what changed?
git diff                        # exact line-by-line changes, unstaged

git add <filename>              # stage one file
git add .                       # stage everything changed
git commit -m "message"         # save a snapshot of what's staged

git push -u origin <branch-name>   # first push from this branch
git push                           # every push after that
```

Then open a pull request in Forgejo into `main`.

---

## Branching & navigation

```sh
git branch                        # list local branches
git branch -a                     # list remote branches too
git checkout <branch-name>        # switch to an existing branch
git branch -d <branch-name>       # delete a merged branch
git branch -D <branch-name>       # delete a branch, even unmerged
git log --oneline                 # history, one line per commit
git log --oneline --graph --all   # same, with a branch/merge graph
```

---

## Reviewing & undoing before you commit

```sh
git restore <filename>            # discard uncommitted changes to a file
git restore .                     # discard ALL uncommitted changes
git restore --staged <filename>   # unstage a file, keep the edit
```

`restore` only touches uncommitted work, and it's destructive with no
confirmation prompt — double-check with `status`/`diff` first.

---

## Stashing

```sh
git stash          # set aside uncommitted changes
git stash list      # see everything you've stashed
git stash pop       # restore the most recent stash, remove from stack
git stash apply     # restore the most recent stash, keep on stack
```

> A short-term clipboard, not storage — commit the work if you're not
> coming back to it soon.

---

## Undoing committed changes

**Not pushed yet — safe to rewrite history**

```sh
git reset --soft HEAD~1               # undo last commit, keep staged
git reset --hard HEAD~1               # undo last commit, discard it
git commit --amend -m "New message"   # fix the last commit's message
```

**Already pushed — never rewrite history**

```sh
git revert <commit-hash>
```

`revert` creates a *new* commit undoing an earlier one — safe on shared branches.

---

## Merge conflicts

```text
<<<<<<< HEAD
your current branch's version
=======
the incoming branch's version
>>>>>>> other-branch
```

Resolve by hand, delete the markers, then:

```sh
git add <filename>
git commit
```

To bail out entirely: `git merge --abort`

---

## Investigating history

<div class="two-column small">

```sh
git log
git log --oneline
git show <commit-hash>
git blame <filename>
git log -p <filename>
git diff <branch-1>..<branch-2>
```

- `log` — full detail: author, date, message
- `show` — exactly what one commit changed
- `blame` — who last touched each line
- `diff a..b` — everything that differs

</div>

---

## Common scenarios

**"I forgot to add a file to my last commit"**
```sh
git add <filename>
git commit --amend --no-edit
```

**"push rejected... remote contains work"**
`git pull` (resolve a conflict if one comes up), then push again.

**"detached HEAD state"**
`git checkout main` (or any branch name) gets you back onto a branch.

---

## Glossary

<div class="two-column small">

- **Repo:** files + full history (the hidden `.git` folder).
- **Commit:** a saved snapshot, with a message.
- **Branch:** an independent line of work.
- **Remote:** the shared Forgejo copy — usually `origin`.
- **Stage:** what goes into the next commit.
- **Merge:** combine one branch's changes into another.
- **PR:** a proposal to merge, reviewed first.
- **Conflict:** git can't auto-merge; needs a human decision.
- **Revert:** a new commit undoing an earlier one — safe.
- **Reset:** moves your branch pointer back — only safe pre-push.
- **HEAD:** the commit you're currently on.

</div>

---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# When to ask for help

- Before force-pushing, or anything that says "cannot be undone."
- During a conflict — normal, not a sign you did something wrong.
- Unsure what a command does: `git <command> --help`, or just ask.
- Think you lost committed work? It's almost never gone — the reflog
  keeps it. Ask for help recovering it rather than guessing.

<p class="nav"><a href="index.md">&larr; Back to hub</a> &middot; <a href="labs.md">&larr; Lab overview</a> &middot; <a href="presentation.md">&larr; Deck</a></p>
