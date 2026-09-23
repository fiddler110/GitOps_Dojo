# Git Fundamentals Cheat Sheet

A quick reference for the commands covered in **Session 1: Git Fundamentals**.
Print this or save it — you won't need to memorize anything.

---

## Setup (One Time)

Configure git so it knows who you are:

```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@company.com"
```

Verify it worked:
```bash
git config --global user.name
git config --global user.email
```

---

## The Everyday Workflow

### Start Your Day
```bash
# Get a full copy of the remote repo (first time only)
git clone <repository-url>

# Navigate into the repo
cd <repo-name>

# Get the latest changes from the remote
git pull
```

### Create a Branch for Your Work
```bash
# Create and switch to a new branch
git checkout -b <branch-name>

# Example:
git checkout -b add-newfeature
```

### Make Your Changes
```bash
# See what changed (untracked, modified, staged)
git status

# See the exact line-by-line changes in a file
git diff <filename>

# See all changes
git diff
```

### Stage & Commit
```bash
# Add specific file(s) to the staging area
git add <filename>

# Add all changed files to staging
git add .

# Save a snapshot with a message
git commit -m "Brief description of what changed and why"

# Good commit message examples:
# "Add new DNS record for api.example.com"
# "Fix typo in load balancer config"
# "Remove unused backup script"
```

### Push & Share
```bash
# Send your commits to the remote
git push -u origin <branch-name>

# Example:
git push -u origin add-newfeature
```

Then **open a pull request** in the Azure DevOps portal to ask for review.

---

## Branching & Navigation

```bash
# List all local branches (current branch marked with *)
git branch

# List remote branches too
git branch -a

# Switch to an existing branch
git checkout <branch-name>

# Create and switch to a new branch (shorthand)
git checkout -b <branch-name>

# Delete a branch (after it's merged)
git branch -d <branch-name>

# See commit history (brief, one line per commit)
git log --oneline

# See commit history with a graph visualization
git log --oneline --graph --all
```

---

## Handling Changes Before You Commit

### Discard Uncommitted Changes
```bash
# Discard changes to one file (not staged)
git restore <filename>

# OR (older syntax, still works)
git checkout -- <filename>

# Discard ALL uncommitted changes (BE CAREFUL!)
git restore .
```

### Undo Staging (Staged but Not Committed)
```bash
# Remove a file from staging (but keep the edits)
git restore --staged <filename>

# OR (older syntax)
git reset <filename>
```

### Stash (Set Aside Work Temporarily)
Use stash when you need to switch branches but aren't ready to commit yet:

```bash
# Save uncommitted changes to a "clipboard"
git stash

# See what's stashed
git stash list

# Get your changes back
git stash pop

# Get a specific stash (if you have multiple)
git stash pop stash@{0}
```

---

## Undoing Committed Changes

### If You Haven't Pushed Yet (Local Only)

```bash
# Undo the last commit, but keep the changes in your working directory
git reset --soft HEAD~1

# Undo the last commit AND discard the changes
git reset --hard HEAD~1

# Fix a typo in the last commit message
git commit --amend -m "New message"
```

### If You've Already Pushed (Safe Method)

**Never use `git reset` on shared branches.** Instead, use `git revert`:

```bash
# Create a NEW commit that undoes a previous commit
git revert <commit-hash>

# Example:
git revert abc123def456
```

Find the commit hash with `git log --oneline`.

---

## Merge Conflicts

Conflicts happen when two branches change the same line. Git will mark them:

```text
<<<<<<< HEAD
version: 1.2.0
=======
version: 1.3.0
>>>>>>> feature-branch
```

### To Resolve

1. Open the conflicted file in your editor.
2. Choose which version you want (or combine them manually).
3. Delete the conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`).
4. Stage and commit:

```bash
git add <filename>
git commit -m "Resolve merge conflict in <filename>"
```

### To Abort (Start Over)

```bash
git merge --abort
```

## Ignoring Local-Only Files

Create or update a `.gitignore` file at the repository root when files should
not be tracked:

```gitignore
# macOS and local environment files
.DS_Store
.env

# Logs and generated output
*.log
dist/
```

Then check the result:

```bash
git status
```

Important: `.gitignore` affects untracked files. It does not stop tracking a
file that was already committed, and it does not remove a secret from history.
If a secret was committed, ask for help immediately and rotate it.

---

## Investigating & Understanding History

```bash
# See what changed in a specific commit
git show <commit-hash>

# See the change history of one file (line by line, who changed it)
git blame <filename>

# See commit history for one file
git log -p <filename>

# Compare two branches
git diff <branch-1>..<branch-2>

# Find the commit that introduced a bug (advanced)
git bisect start
```

---

## Common Scenarios & Quick Fixes

### "I pushed to the wrong branch — help!"
- **Stop.** Don't force-push. Open a pull request anyway, and ask the team/facilitator to help merge to the right place.

### "I forgot to add a file to my last commit"
```bash
git add <filename>
git commit --amend --no-edit
```

### "I want to see what's on main before pulling"
```bash
git fetch                  # Download updates from remote (doesn't change your files)
git diff main origin/main  # Compare your main to remote main
git pull                   # Now actually merge it in
```

### "Which branches have been merged already?"
```bash
git branch --merged
```

### "I want to delete all my local branches except main"
```bash
git branch --list | grep -v 'main' | xargs git branch -d
```

---

## Glossary

- **Repository (repo):** A folder containing your files + full git history.
- **Commit:** A saved snapshot of your changes with a message.
- **Branch:** An independent line of work (defaults to `main`).
- **Remote:** The hosted Azure Repos copy — usually called `origin`.
- **Clone:** Download a repo and its full history to your machine.
- **Pull / Push:** Sync commits down from / up to the remote.
- **Merge:** Combine one branch's changes into another.
- **Pull Request (PR) / Merge Request (MR):** A proposal to merge a branch, with space for review/discussion.
- **Conflict:** When git can't auto-merge and needs human judgment.
- **Stash:** Temporarily save uncommitted changes.
- **Revert:** Create a new commit that undoes a previous commit (safe for shared branches).
- **Reset:** Move the branch pointer back (only safe locally, before pushing).
- **HEAD:** Shorthand for "the current commit you're on."

---

## When to Ask for Help

- **Before force-pushing:** Ask first, especially if others are using the branch.
- **During a conflict:** It's OK to ask — conflicts are normal, not a sign you did something wrong.
- **If you're unsure what a command will do:** `git --help <command>` or ask the team.
- **If you've lost commits:** They're not really gone (git keeps them for 30 days in the reflog) — ask for help recovering.

---

## Resources

- **Session 1 slides:** Distributed during the session.
- **Lab exercises:** See `CONTRIBUTING.md` in the sample repo.
- **Next session:** Branching Workflows & Pull Requests in Practice (Session 2).
- **Official git docs:** https://git-scm.com/doc (when you're ready for deeper dives).

---

**Good luck! Version control is a skill, not a gift — everyone feels lost at first.**
