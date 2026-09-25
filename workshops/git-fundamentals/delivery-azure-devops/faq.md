# Git Fundamentals and Azure DevOps FAQ

Use this as an attendee follow-up reference and as a source for facilitator answers during Session 1.

## Git and Azure Repos

### What is the difference between Git and Azure DevOps?

Git is the version control tool installed on your computer. Azure DevOps is Microsoft's collaboration platform; Azure Repos hosts the shared Git repository and provides pull requests, permissions, policies, and related project features.

### Do I need to be online to use Git?

No. You can edit files, create branches, and commit locally while offline. You need network access to clone, pull from, or push to Azure Repos and to create or review a pull request.

### Why do I need both a local repository and Azure Repos?

The local repository gives you a complete working copy and history. Azure Repos provides the shared copy the team uses for collaboration, review, and backup.

### What does `origin` mean?

`origin` is the conventional name Git assigns to the remote repository when you clone it. It is just a short name; it does not describe a separate kind of repository.

### What is `.gitignore`?

`.gitignore` is a repository file containing patterns for files Git should leave untracked, such as editor settings, operating-system files, logs, build output, and local environment files. It helps prevent accidental commits and keeps `git status` focused on intentional work.

### Does `.gitignore` remove a file that was already committed?

No. Ignore rules apply to untracked files. A file that is already tracked remains tracked until it is removed from the index, and a secret that was committed should be treated as exposed and rotated rather than merely added to `.gitignore`.

## Everyday Commands

### Why should I run `git status` so often?

It shows your current branch, changed files, staged files, and whether your local branch is ahead of or behind the remote. It is the quickest way to understand what Git thinks is happening.

### What is the difference between `git add` and `git commit`?

`git add` selects changes for the next commit. `git commit` saves the selected changes as a snapshot in your local repository. Neither command sends anything to Azure Repos; use `git push` for that.

### Why do I need a branch?

A branch isolates your work from the shared `main` branch. It lets you make and review a change without exposing unfinished work as the team's source of truth.

### Why pull before starting work?

`git pull` brings down changes that teammates have already pushed. Starting from the current `main` branch reduces avoidable conflicts and makes your pull request easier to review.

### What is the difference between `git fetch` and `git pull`?

`git fetch` downloads remote updates without changing your current branch. `git pull` downloads updates and then integrates them into the current branch. Fetch is useful when you want to inspect changes before integrating them.

## Azure DevOps Pull Requests

### Is a pull request a Git command?

No. A pull request is an Azure DevOps workflow around Git branches. You push your branch with Git, then create and review the pull request in the Azure DevOps portal.

### Can I push directly to `main`?

The repository may technically allow it, but the team workflow should use a branch and pull request. Branch policies can require reviewers and checks before `main` changes.

### What if my pull request says I need approvals or checks?

That is usually a branch policy working as intended. Check the policy message, request the required reviewer, and fix any failed build or validation check. Ask the repository owner if the policy appears inconsistent with the lab instructions.

### Why can I push a branch but not create a pull request?

Pushing and creating a pull request use different Azure DevOps permissions. Confirm that you have project access, repository read/contribute access, and permission to create pull requests for that repository.

## Authentication and Recovery

### Should I use HTTPS or SSH?

Use the method supported by your organization. HTTPS is often the quickest first setup; it may require an approved credential flow or token. SSH uses a key pair configured with Azure DevOps and avoids repeated credential prompts after setup. Follow the repository's current authentication guidance rather than putting a password in a clone URL.

### What should I do if Git says “permission denied” or “repository not found”?

First confirm the repository URL, organization, project, and repository name. Then verify that you are signed in with the expected Microsoft Entra account and have been added to the Azure DevOps project. If HTTPS authentication fails, use the organization's approved credential method; if SSH fails, verify the key is uploaded and loaded locally.

### I made an edit but do not want it anymore. What should I do?

If it is not staged, `git restore <file>` discards the local edit. If it is staged, `git restore --staged <file>` removes it from the next commit without discarding the edit. Check `git status` first. Do not run a destructive command if you are unsure what it will remove.

### I already pushed a bad commit. Should I use `reset`?

Usually no on shared work. `git revert <commit>` creates a new commit that undoes the earlier one without rewriting shared history. Ask for help before using `reset` or force-pushing a branch that someone else may have pulled.

### What does a merge conflict mean?

Git found overlapping changes it could not safely combine automatically. Open the marked file, decide which content should remain, remove the conflict markers, then stage and commit the resolved file. A conflict is a request for a human decision, not evidence that the repository is broken.

### Where can I get help after the session?

Start with `git status`, the [cheat sheet](cheat-sheet.md), and this FAQ. For access, branch-policy, or authentication problems, contact the facilitator or repository owner with the exact command and error message, but do not include credentials or tokens.
