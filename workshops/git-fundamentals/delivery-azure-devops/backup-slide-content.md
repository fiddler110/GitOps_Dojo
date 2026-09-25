# Backup Slide Content — Git Fundamentals and Azure DevOps

This document contains optional, slide-ready content for questions, timing changes, or live-demo recovery. It is intentionally a content outline rather than a slide deck. Build only the slides that fit the audience and the session's remaining time.

## How to Use This Appendix

- Keep the core deck focused on the everyday workflow.
- Use a backup slide when a question is valuable to the whole room, not just one attendee.
- Prefer one concept or decision per slide.
- Keep command examples paired with a clear warning about whether they affect local or shared history.
- Use the Azure DevOps wording consistently: **Azure Repos** is the remote Git host; pull requests are created in the Azure DevOps portal.

## Backup Slide 1 — Git, Azure Repos, and Azure DevOps

**Purpose:** Answer the common “are Git and Azure DevOps the same thing?” question.

**On-slide content:**

| Git                                         | Azure Repos / Azure DevOps                                         |
| ------------------------------------------- | ------------------------------------------------------------------ |
| Version control tool on your machine        | Hosted Git repository and collaboration platform                   |
| Creates branches, commits, merges, and tags | Adds pull requests, permissions, policies, and project integration |
| Works locally, including offline            | Shared team copy accessed over the network                         |

**Speaker note:** Git is the engine; Azure Repos is where the team shares the repository and reviews changes.

## Backup Slide 2 — The Four Places Your Change Lives

**Purpose:** Unstick attendees who are confused about `add`, `commit`, and `push`.

**On-slide content:**

```text
Working directory  ->  Staging area  ->  Local repository  ->  Azure Repos
   edit files            git add             git commit              git push
```

**Speaker note:** `git status` tells you which zone contains the change. A commit is local until it is pushed.

## Backup Slide 3 — What to Do Before You Push

**Purpose:** Provide a quick pre-push checklist during the lab.

**On-slide content:**

```bash
git status
git diff
git diff --staged
git log --oneline -3
git pull --rebase
```

**Speaker note:** Explain each command briefly. The exact pull strategy should follow the team's repository guidance; do not introduce rebase as a universal rule without explaining the local convention.

## Backup Slide 4 — HTTPS or SSH for Azure Repos?

**Purpose:** Answer authentication questions without derailing the main lesson.

**On-slide content:**

- **HTTPS:** Often simplest to start; uses the organization's approved credential flow.
- **SSH:** Uses a local key pair registered with Azure DevOps; convenient after setup.
- Never put passwords or tokens directly in a clone URL.
- Use the authentication method approved by the organization.

**Speaker note:** Authentication failures are usually identity, permission, URL, or credential configuration issues. Capture the exact error without sharing secrets.

## Backup Slide 5 — Safe Undo Decision Tree

**Purpose:** Prevent destructive recovery commands from being used casually.

**On-slide content:**

```text
Do I want to remove an uncommitted edit?
  -> git restore <file>

Do I want to unstage an edit but keep it?
  -> git restore --staged <file>

Did I already push the commit to shared history?
  -> git revert <commit>

Am I rewriting only my own local, unshared work?
  -> Ask first, then consider reset/amend
```

**Speaker note:** The safest default after sharing is a new commit that reverses the old one. Pause before using reset or force-push.

## Backup Slide 6 — Pull Request Anatomy in Azure DevOps

**Purpose:** Make the lab's portal step concrete.

**On-slide content:**

1. Source branch: your feature branch
2. Target branch: usually `main`
3. Title and description: what changed and why
4. Reviewers: people who can evaluate the change
5. Files changed: the review surface
6. Policies and checks: conditions required before completion
7. Complete pull request: merge after approval and checks pass

**Speaker note:** A pull request is a conversation and a control point, not just a merge button.

## Backup Slide 7 — Merge Conflict Anatomy

**Purpose:** Reduce anxiety when the lab or demo produces a conflict.

**On-slide content:**

```text
<<<<<<< HEAD
content from the current branch
=======
content from the branch being merged
>>>>>>> other-branch
```

**Resolution steps:**

1. Read both versions and decide what the file should contain.
2. Remove the conflict markers.
3. Save and inspect the result.
4. Run the relevant validation.
5. `git add <file>` and commit the resolution.
6. Push the branch and update the Azure DevOps pull request.

**Speaker note:** Never leave conflict markers in a file. The correct resolution is a content decision, not automatically “ours” or “theirs.”

## Backup Slide 8 — `revert` Versus `reset`

**Purpose:** Answer a deeper recovery question without teaching unsafe habits by accident.

**On-slide content:**

| Command              | Best fit                                          | Shared history?               |
| -------------------- | ------------------------------------------------- | ----------------------------- |
| `git revert`         | Create a new commit that undoes an earlier commit | Safe default after sharing    |
| `git reset`          | Move a local branch pointer                       | Use cautiously before sharing |
| `git commit --amend` | Fix the most recent local commit                  | Use before sharing            |

**Speaker note:** If teammates may have pulled the commit, do not rewrite the branch without agreement from the repository owner.

## Backup Slide 9 — When `git pull` Is Not Enough

**Purpose:** Help attendees understand why the working branch may be behind or diverged.

**On-slide content:**

- `git fetch`: download remote information only.
- `git log --oneline --graph --all`: inspect the commit shape.
- `git diff main...your-branch`: review branch changes.
- Ask the team which merge or rebase convention the repository uses.

**Speaker note:** This is a preview of the branching and recovery sessions. Keep the live demonstration small unless the audience is ready for it.

## Backup Slide 10 — `.gitignore`: Keep Local Files Out

**Purpose:** Answer questions about untracked files and prevent accidental commits of local or sensitive content.

**On-slide content:**

```gitignore
.DS_Store
.env
*.log
dist/
```

- `.gitignore` lists patterns Git should leave untracked.
- It is useful for editor files, OS metadata, logs, build output, and local configuration.
- It does not untrack a file that was already committed.
- It does not erase a secret from history; rotate a committed secret immediately.

**Speaker note:** A quick demo can create a temporary `.log` file, show it with `git status`, add `*.log` to `.gitignore`, and show that it no longer appears as an untracked file.

## Backup Slide 11 — DNS-as-Code Connection

**Purpose:** Connect Session 1 to the later training roadmap.

**On-slide content:**

```text
Edit zone/config file
    -> validate locally
    -> commit with intent
    -> push branch
    -> review in Azure DevOps
    -> run checks
    -> merge and deploy
```

**Speaker note:** The Git workflow stays recognizable even when the file is a DNS zone, infrastructure definition, runbook, or application configuration. Later sessions add domain-specific validation and automation.

## Backup Slide 12 — If the Live Demo Fails

**Purpose:** Keep the session moving during a network, permission, or screen-sharing problem.

**On-slide content:**

- Show the prepared screenshot or terminal transcript.
- Explain which step was supposed to happen.
- Have attendees continue with the local portion of the lab.
- Pair anyone blocked by Azure DevOps access with a working attendee.
- Record the exact failure for follow-up; do not troubleshoot credentials publicly.

**Speaker note:** The learning objective is the workflow, not whether one laptop behaves perfectly. Resume the live demo only after the room is moving again.

## Selection Guide

| Situation                                     | Use these slides |
| --------------------------------------------- | ---------------- |
| Git versus Azure DevOps confusion             | 1, 2             |
| Attendees are unsure what to run next         | 3                |
| Authentication questions dominate             | 4                |
| Someone asks how to undo work                 | 5, 8             |
| Pull request review needs explanation         | 6                |
| A conflict appears                            | 7                |
| The audience asks what comes next             | 9, 11            |
| The audience asks about local or secret files | 10               |
| Live tooling is unavailable                   | 12               |
