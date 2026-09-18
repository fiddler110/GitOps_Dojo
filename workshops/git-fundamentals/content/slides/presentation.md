---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
  @import url('assets/themes/presentation.css');
  .split { align-items: center; display: flex; gap: 48px; }
  .split > div { flex: 1; min-width: 0; }
  .split-30-70 > div:first-child { flex: 0 0 30%; }
  .split-30-70 > div:last-child { flex: 0 0 70%; }
  .mermaid .commit-label { font-size: 18px !important; }
footer: '[&larr; Hub](index.md) &nbsp;|&nbsp; Git Fundamentals | Engineering & IT Operations'
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# Git Fundamentals

## What, why, and how

Version control for Engineering & IT Operations

**30-minute talk + hands-on lab**

<!--
Welcome everyone. Cover session logistics. The lab runs entirely in the browser,
so attendees do not need Git or an editor installed locally.
-->

---

## Today

1. Why version control matters
2. What Git actually is
3. The vocabulary teams use
4. The everyday workflow
5. Branches, review, and collaboration
6. Hands-on practice

> The goal: understand what Git is doing, then do it yourself.

<!-- Ask for a quick show of hands: who has used Git before? -->

---

## Does this look familiar?

```text
dns-config.txt
dns-config-final.txt
dns-config-final-v2.txt
dns-config-REALLY-FINAL.txt
dns-config-REALLY-FINAL-fixed.txt
USE-THIS-ONE.txt
```

**Which is current? Who changed it? Why? Can we safely go back?**

<!-- Let the room react. This is the problem Git formalizes and solves. -->

---

## The operations reality

- Change tickets describe intent, but are not the changed files
- Shared drives allow accidental overwrites
- Backup dates are not a useful change history
- A bad configuration needs a fast, known rollback
- “Who changed this DNS record?” becomes incident detective work

> Scripts, runbooks, infrastructure, and DNS configuration all deserve history.

---

## What Git gives us

| Capability        | Practical result                          |
| ----------------- | ----------------------------------------- |
| **Full history**  | Who changed what, when, and why           |
| **Safe branches** | Experiment away from the stable version   |
| **Collaboration** | Combine work without overwriting it       |
| **Review**        | Discuss and approve a change before merge |
| **Rollback**      | Return to a known state when needed       |

---

<!-- _class: section-title -->

# What is Git, really?

The tool is not the hosting service.

---

## Git is not Forgejo or Azure DevOps

| Git                          | Forgejo / Azure Repos                          |
| ---------------------------- | ---------------------------------------------- |
| Runs where you work          | Runs as a shared service                       |
| Records local history        | Hosts the team's remote copy                   |
| Creates branches and commits | Adds pull requests, review, and access control |
| Works offline                | Connects collaborators                         |

**Today:** Forgejo keeps the lab contained. The same Git commands work with Azure Repos, GitHub, or GitLab.

---

## Local and remote

```text
┌─────────────────────────────┐       ┌────────────────────────┐
│ Your workspace              │       │ Shared Git service     │
│                             │ push  │                        │
│ Files + complete history    │ ────► │ Team's remote copy     │
│                             │ ◄──── │                        │
└─────────────────────────────┘ pull  └────────────────────────┘
```

- **Local:** full history, branches, and commits
- **Remote:** the shared collaboration point, usually named `origin`

---

## The mental model

<div class="flow">
	<span><strong>Working directory</strong><br><small>Your edits</small></span>
	<b>→</b>
	<span><strong>Staging area</strong><br><small>Selected changes</small></span>
	<b>→</b>
	<span><strong>Local repository</strong><br><small>Commits</small></span>
	<b>→</b>
	<span><strong>Remote repository</strong><br><small>Shared commits</small></span>
</div>

<!-- This is the anchor diagram. Refer back to these four zones. -->

---

## Repository and commit

### Repository
A project folder plus its complete history, stored by Git in `.git`.

### Commit
A named snapshot of selected changes, with author and time.

```text
7c13b8a  Add DNS record for api.example.com
```

**A useful message says what changed and gives future-you context.**

---

## Branch and main

<div class="split">
<div>

- A **branch** is an independent line of work
- `main` is the stable, shared line
- One focused change per branch makes review and rollback easier

> Branch off. Make the change. Ask for review. Merge when ready.


</div>
<div>

<div class="mermaid">
gitGraph
	commit id: "Init"
	commit id: "Add homepage"
	branch add-api-record
	commit id: "Add endpoint"
	commit id: "Add tests"
	checkout main
	branch fix-typo
	commit id: "Fix typo"
	checkout main
	merge fix-typo id: "Merged fix" tag: "merge"
	checkout main
	merge add-api-record id: "Merged feature" tag: "merge"
</div>

<div class="small">

- **Step 1:** Branch `add-api-record` and `fix-typo` off `main`
- **Step 2:** Each branch commits its own work in isolation
- **Step 3:** Merge each branch back into `main` on its own
- **Step 4:** `main` never gets a direct commit

</div>

</div>
</div>

---

## Moving between local and remote

| Term       | Meaning                                               |
| ---------- | ----------------------------------------------------- |
| **Clone**  | Make the first full local copy                        |
| **Remote** | A named connection to a hosted repo, usually `origin` |
| **Pull**   | Bring remote commits into your current branch         |
| **Push**   | Send your local commits to the remote                 |

```bash
git clone http://git-server:3000/training/sample-training-repo.git
git pull
git push
```

---

## Pull Request & Merge

### Pull request
A conversation and review **before** one branch is merged into another.

```text
branch → push → pull request → review → merge → main
```

**\*\*A pull request is a Forgejo/Azure DevOps feature, not a Git command.**

### Merge
Combine the histories of two branches.

```text 
Like two rivers merging — separate currents become one flow, carrying both histories downstream
```


---

## Conflict: Git needs a decision

Two branches changed the same line. Git can't guess which one you want, so it pauses the merge and marks the file:

<div class="split split-30-70">
<div>


```text
<<<<<<< HEAD
ttl: 600
=======
ttl: 300
>>>>>>> feature-branch
```
</div>
<div>

1. Open the file and decide: keep `600`, keep `300`, pick a new value, or combine them
2. Delete the `<<<<<<<`, `=======`, and `>>>>>>>` marker lines
3. `git add dns-config.txt` — tell Git this file is resolved
4. `git commit` — completes the merge with your resolution

</div>
</div>

**Conflicts are normal. Git stops instead of guessing.**


---

<!-- _class: section-title -->

# The everyday Git workflow

Most of Git is one repeatable loop.

---

## 1. Clone once

```bash
git clone <repository-url>
cd sample-training-repo
```

You now have:

- The project files
- The complete Git history
- A remote named `origin`
- A checked-out default branch, usually `main`

---

## 2. Start from current `main`

```bash
git checkout main
git pull
git checkout -b add-yourname
```

- Move to the stable branch
- Get teammates' latest commits
- Create a branch for one focused change

> A current starting point means fewer surprises later.

**A note on `checkout` vs `switch`:** `checkout` is the classic, do-everything command — it switches branches, but it also checks out individual commits and restores files. Newer Git versions added `git switch` (and `git restore`) to split branch-switching into its own, more focused command: `git switch main` / `git switch -c add-yourname` do exactly the same thing as above. We teach `checkout` here because it's the one you'll see in most existing docs, tutorials, and scripts — but don't be surprised to see `switch` used instead.

---

## 3. Edit, inspect, select

```bash
# Edit roster/team.yaml

git status
git diff
git add roster/team.yaml
git status
```

- `status`: what state is my workspace in?
- `diff`: what did I actually change?
- `add`: which changes belong in the next commit?

**Use `git status` constantly.**

---

## 4. Commit a useful snapshot

```bash
git commit -m "Add Morgan to the team roster"
```

| Weak      | Useful                                  |
| --------- | --------------------------------------- |
| `updates` | `Add Morgan to the team roster`         |
| `fix`     | `Correct API record TTL to 300 seconds` |
| `stuff`   | `Document DNS rollback procedure`       |

**Describe the outcome, not the act of editing.**

---

## 5. Push and request review

```bash
git push -u origin add-yourname
```

Then in the Git service:

1. Open a pull request into `main`
2. Explain the change
3. Review and discuss
4. Approve and merge
5. Delete the completed branch

`-u` connects the local branch to its remote counterpart.

---

## The whole loop

<div class="mermaid">
flowchart LR
	clone["clone once"] --> pull["pull"]
	pull --> branch["branch"]
	branch --> edit["edit"]
	edit --> status["status/diff"]
	status --> add["add"]
	add --> commit["commit"]
	commit --> push["push"]
	push --> merge["PR + merge"]
	merge -- "next focused change" --> pull
</div>

```bash
git status   # Where am I and what changed?
git log -1   # What did I most recently commit?
```

---

## Ready to practice?

In the browser you will:
<div class="small">

1. Open your terminal
2. Clone the shared repository
3. Create a personal branch
4. Add yourself to `roster/team.yaml`
5. Inspect, stage, commit, and push
6. Open a pull request in Forgejo

</div>

Next: [labs.md](labs.md) for what each lab covers. 
Help: [cheat-sheet.md](cheat-sheet.md) is available here as well as within the lab environment.

> Questions before we put hands on keyboards?

---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# Appendix

## When something happens

Optional demonstrations and reference slides

---

## Pause unfinished work: stash

```bash
git stash          # Set uncommitted work aside
git checkout main  # Handle the interruption
git checkout -     # Return to the previous branch
git stash pop      # Restore the work
```

Useful when you need to switch context but are not ready to commit.

```bash
git stash list     # See saved stashes
```

**A stash is temporary local storage, not a backup or shared commit.**

---

## Undo at the right level

| Situation                     | Command                       |
| ----------------------------- | ----------------------------- |
| Uncommitted edit              | `git restore <file>`          |
| Staged, not committed         | `git restore --staged <file>` |
| Fix your latest local commit  | `git commit --amend`          |
| Undo an already shared commit | `git revert <commit>`         |

> Once history is pushed and shared, prefer `revert`: it records the undo without rewriting history.

---

## Investigate history

```bash
git log --oneline --graph   # Timeline
git show <commit>           # One commit's changes
git blame roster/team.yaml  # Last commit for each line
git log -p -- <file>        # History of one file
```

Use history to answer:

- What changed?
- When and why did it change?
- Who has useful context?

---

## Keep local files local

`.gitignore` contains patterns Git should not track:

```gitignore
.DS_Store
.env
*.log
dist/
```

- Keeps `git status` focused on intentional work
- Does not stop tracking a file already committed
- <u>*Does not remove a secret from history*</u>

**If a secret is committed, rotate it immediately.**

---

## Quick reference

```bash
git status                    # Inspect current state
git checkout -b <branch>       # Create and enter a branch
git diff                      # Review unstaged changes
git add <file>                # Stage selected changes
git commit -m "<message>"     # Save a snapshot
git push -u origin <branch>   # Publish the branch
git log --oneline --graph     # Inspect history
git restore <file>            # Discard an uncommitted edit
git revert <commit>           # Safely undo shared history
```

---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# Clone. Branch. Change. Review.

The commands are small. The reliable workflow is the real skill.

<script type="module">
	import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs"
	mermaid.initialize({
		startOnLoad: true,
		theme: "dark",
		themeVariables: {
			background: "#18242e",
			primaryColor: "#21313c",
			primaryTextColor: "#e8f0f2",
			primaryBorderColor: "#3dd6c3",
			lineColor: "#a9bac2",
			git0: "#69aee8",
			git1: "#3dd6c3",
			gitBranchLabel0: "#111820",
			gitBranchLabel1: "#111820",
			commitLabelColor: "#e8f0f2",
			commitLabelBackground: "#111820",
			tagLabelColor: "#111820",
			tagLabelBackground: "#f0b95b",
		},
	})
</script>
