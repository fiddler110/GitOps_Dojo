# Git Cheat Sheet

A quick reference for the commands used across [lab1.md](lab1.md)-
[lab5.md](lab5.md). Print this, keep it open in a split pane, or paste it
into your notes — you don't need to memorize any of it.

---

## Setup (once per machine)

See [00-github-setup.md](00-github-setup.md) for the full walkthrough.

```sh
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

Verify it:

```sh
git config --global user.name
git config --global user.email
```

---

## The Everyday Workflow

### Get the repo

```sh
git clone <repository-url>   # full copy, once per repo
cd <repo-name>
git pull                     # get the latest from the remote
```

`clone` downloads every commit and branch, not just the current
snapshot — after cloning, you have the whole project's history on your
machine. `pull` fetches new commits from the remote and merges them into
your current branch; run it whenever you start work, so you're not
building on stale history.

### Create a branch for your work

```sh
git checkout -b <branch-name>
```

Creates a new branch pointing at your current commit and switches you
onto it. Work on a branch, not directly on `main`, so your in-progress
changes can't affect anyone else until you're ready to share them.

### See what changed

```sh
git status              # which files changed, and how (modified/staged/untracked)
git diff                # the exact line-by-line changes, unstaged
git diff <filename>      # the same, for one file
```

`git status` is the command you'll run more than any other — it always
tells you exactly where you stand. `git diff` shows you the content of
the change, not just which files it touched; read it before every
commit.

### Stage and commit

```sh
git add <filename>          # stage one file
git add .                   # stage everything changed
git commit -m "message"     # save a snapshot of what's staged
```

Staging is a deliberate middle step: it lets you build a commit out of
exactly the changes you want, even if your working directory has other,
unrelated edits sitting around. The commit message should say what
changed and, if it isn't obvious, why — `"fix bug"` tells a reviewer
nothing; `"fix off-by-one error in roster loop"` does.

### Push and share

```sh
git push -u origin <branch-name>   # first push from this branch
git push                           # every push after that
```

Nothing you've done is visible to anyone else until you push — up to
that point, everything (branch, commits) exists only on your machine.
`-u` remembers the branch's remote so later pushes don't need the full
form.

Then open a pull request on GitHub — either click the **Compare & pull
request** banner GitHub shows after a push, or run `gh pr create` if
you've set up the GitHub CLI.

### Clean up after it's merged

```sh
git checkout main
git pull
git fetch --prune                  # or: git fetch -p
git branch -d <branch-name>
```

Once a PR merges, GitHub can delete the branch on the server (there's a
**Delete branch** button right on the merged PR), but your local clone
doesn't find out on its own. `git fetch --prune` removes local
*remote-tracking* branches (`origin/<branch-name>`) whose remote no
longer exists; `git branch -d` then removes your own local branch (it
refuses if the branch isn't fully merged, so it's safe to run without
checking first).

---

## Branching & Navigation

```sh
git branch                        # list local branches (* marks the current one)
git branch -a                     # list remote branches too
git checkout <branch-name>        # switch to an existing branch
git checkout -b <branch-name>     # create and switch, in one step
git branch -d <branch-name>       # delete a branch (only if it's merged)
git branch -D <branch-name>       # delete a branch, even if it isn't merged
git fetch --prune                 # remove remote-tracking branches deleted on the server
git log --oneline                 # history, one line per commit
git log --oneline --graph --all   # the same, with a branch/merge graph
```

---

## Reviewing & Undoing Before You Commit

See [lab2.md](lab2.md) for a hands-on walkthrough of all of this.

```sh
git restore <filename>            # discard uncommitted changes to a file
git restore .                     # discard ALL uncommitted changes (careful!)
git restore --staged <filename>   # unstage a file, keeping the edit
```

`git restore` only ever touches uncommitted work — once something is
committed, restoring won't undo it (see "Undoing Committed Changes"
below instead). It's destructive for what it does touch: there's no
confirmation prompt, so double-check with `git status`/`git diff` first
if you're not certain.

---

## Stashing

See [lab3.md](lab3.md) for a full walkthrough. Use this when you need to
switch branches but aren't ready to commit yet.

```sh
git stash          # set aside uncommitted changes; working tree goes clean
git stash list      # see everything you've stashed
git stash pop       # restore the most recent stash and remove it from the stack
git stash apply     # restore the most recent stash but keep it on the stack
```

Stashing is a short-term clipboard, not storage — if you're not coming
back to it soon, commit the work instead (even to a throwaway branch).

---

## Undoing Committed Changes

See [lab5.md](lab5.md) for the full walkthrough, including why this
distinction matters.

### Not pushed yet (local only) — safe to rewrite history

```sh
git reset --soft HEAD~1     # undo the last commit, keep the changes staged
git reset --hard HEAD~1     # undo the last commit, discard the changes entirely
git commit --amend -m "New message"   # fix the last commit's message
git commit --amend --no-edit          # add staged changes to the last commit, message unchanged
```

### Already pushed (shared with others) — never rewrite history

```sh
git revert <commit-hash>
```

`revert` creates a *new* commit that undoes an earlier one, instead of
erasing anything — so anyone who already pulled the original commit
isn't left with a broken local history. On GitHub, rewriting history on
a branch backing an open pull request can also silently drop commits
from the PR's diff. Find the hash to revert with `git log --oneline`.
**Never use `git reset` on a branch someone else might already have
pulled from** — that's the line that matters, not whether you
personally think it's safe.

---

## Merge Conflicts

A conflict happens when two branches change the same line differently
and git can't pick a winner automatically. See [lab5.md](lab5.md) to
cause and resolve one yourself. Git marks the disputed section like
this:

```text
<<<<<<< HEAD
your current branch's version
=======
the incoming branch's version
>>>>>>> other-branch
```

To resolve: open the file, decide what the final content should be,
delete the `<<<<<<<`/`=======`/`>>>>>>>` markers yourself, then:

```sh
git add <filename>
git commit
```

To bail out entirely and start over:

```sh
git merge --abort
```

---

## Ignoring Local-Only Files

Add patterns to a `.gitignore` file at the repo root for files that
should never be tracked — build output, editor settings, local secrets:

```gitignore
.DS_Store
.env
*.log
dist/
```

`.gitignore` only affects files git doesn't already know about. It does
not untrack a file that was already committed, and it does nothing to
remove a secret from history — if a secret was ever committed, treat it
as exposed and rotate it. See [lab2.md](lab2.md).

---

## Investigating History

See [lab4.md](lab4.md) for a full walkthrough.

```sh
git log                           # full detail: author, date, message
git log --oneline                 # one line per commit
git show <commit-hash>            # exactly what one commit changed
git blame <filename>              # who last touched each line, and in which commit
git log -p <filename>             # full history of changes to one file
git diff <branch-1>..<branch-2>    # everything that differs between two branches
```

---

## Common Scenarios & Quick Fixes

**"I forgot to add a file to my last commit"**

```sh
git add <filename>
git commit --amend --no-edit
```

**"I want to see what's on `main` before pulling"**

```sh
git fetch                  # download updates, don't merge them yet
git diff main origin/main  # compare your main to the remote's main
git pull                   # now actually merge it in
```

**"Which branches have already been merged?"**

```sh
git branch --merged
```

**"`git branch -a` still shows branches that were already merged and deleted on GitHub"**

```sh
git fetch --prune
```

Deleting a branch on GitHub doesn't touch your local remote-tracking
branches — `git fetch --prune` syncs them by removing any whose remote
counterpart is gone.

**"push rejected — updates were rejected because the remote contains work..."**

The remote has commits you don't have locally yet. Run `git pull` to
bring them in (resolve a conflict if one comes up), then push again.

**"detached HEAD state"**

You've checked out a specific commit instead of a branch.
`git checkout main` (or any branch name) gets you back onto a branch.

**"GitHub keeps asking for a username/password on push"**

HTTPS pushes need a [personal access token](https://github.com/settings/tokens)
instead of your account password, or use the GitHub CLI
(`gh auth login`) to set up credentials for you once. SSH keys are the
other common fix — see <https://docs.github.com/en/authentication>.

---

## Glossary

- **Repository (repo):** a folder containing your files plus the full
  git history (the hidden `.git` folder).
- **Commit:** a saved snapshot of staged changes, with a message.
- **Branch:** an independent line of work; defaults to `main`.
- **Remote:** the shared copy on GitHub — usually called `origin`.
- **Remote-tracking branch:** your local record of where a remote's
  branch was as of your last fetch (e.g. `origin/main`) — not a branch
  you work on directly, and `git fetch --prune` cleans it up once the
  real branch is deleted.
- **Clone:** download a repo and its full history to your machine.
- **Pull / push:** sync commits down from / up to the remote.
- **Staging area:** where you mark exactly what goes into the next
  commit.
- **Merge:** combine one branch's changes into another.
- **Pull request (PR):** a proposal to merge a branch, with room for
  review and discussion before it happens.
- **Conflict:** what happens when git can't auto-merge and needs a human
  decision.
- **Stash:** a temporary, short-term holding spot for uncommitted
  changes.
- **Revert:** a new commit that undoes an earlier one — safe on shared
  branches.
- **Reset:** moves your branch pointer backward, rewriting local
  history — only safe before pushing.
- **HEAD:** shorthand for "the commit you're currently on."

---

## When to Ask for Help

- Before force-pushing, or anything that says "cannot be undone."
- During a conflict — they're normal, not a sign you did something
  wrong.
- If you're unsure what a command does: `git <command> --help`.
- If you think you've lost committed work, it's almost never actually
  gone — git keeps old commits around (the reflog) even after a branch
  is deleted or reset. `git reflog` is the first place to look for a
  "lost" commit.

**More:** [README.md](README.md) for the lab menu, the official docs at
<https://git-scm.com/doc>, or GitHub's own guides at
<https://docs.github.com/>.
