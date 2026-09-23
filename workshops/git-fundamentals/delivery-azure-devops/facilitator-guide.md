# Facilitator Guide — Session 1: Git Fundamentals

**Duration:** ~60 minutes (including setup/wrap-up buffer)
**Audience:** Engineering + IT Ops, mixed experience, no assumed git knowledge
**Format:** Part A tutorial/talk (~30 min), Part B hands-on lab (~30 min)

This guide complements [session-01-plan.md](session-01-plan.md) with detailed speaker notes, talking points, timing checkpoints, and troubleshooting tips.

---

## Pre-Session (15 min before start)

### Checklist

- [ ] **Tech setup:**
  - Test your internet connection and access to the sample repo in **Azure Repos** (Azure DevOps).
  - Have the sample repo cloned locally for live demo.
  - Test screen sharing and video conference — confirm everyone can see your screen.
  - Terminal font size: large enough for the back of the room to read (18pt+).
  - Demo editor (VS Code) open with the sample repo, ready to show diffs.
  - Have Azure DevOps portal open in a browser for live PR demo.

- [ ] **Materials ready:**
  - Printed or digital cheat sheet available to share (PDF or link in Azure DevOps wiki/pages).
  - Sample repo URL (Azure Repos) ready to share — format: `https://dev.azure.com/<org>/<project>/_git/<repo-name>`.
  - Backup: if a live demo fails, have screenshots/screencaps prepared.

- [ ] **Room/participants:**
  - Confirm attendees have **Azure DevOps/Microsoft Entra accounts** with access to your project.
  - Send pre-work checklist (see below) at least 24 hours before the session.
  - Explain the lab will happen after Part A — no need to rush.
  - Set expectations: "You'll try this hands-on; mistakes are learning opportunities. I'll walk the room to help."

---

## Part A — Tutorial (~30 minutes)

### Section 1: Why Version Control? (5 min)

**Goal:** Create urgency and relatability — show why git matters, not just for code but for any shared, changing files.

**Opening line:**
> "How many of you have ever worked on a document called something like `final.docx`, then `final_v2.docx`, then `final_REALLY_final.docx`? [pause for hands] Git solves that problem for everything we care about — code, configuration, scripts, even DNS zone files."

**Talking points:**

1. **The problem without version control:**
   - Shared drive chaos: who changed what? When? Why?
   - Backups don't tell you the story of *how we got here*.
   - Accidents (accidentally delete a file, overwrite someone's change) are hard to recover from.
   - No clear "source of truth" — which version is live?

2. **What operations teams already do informally:**
   - Keeping change tickets (who, when, what).
   - Nightly backups or snapshots.
   - "Ask before you touch this file" norms.
   - Announce in Slack/email when making big changes.

3. **How git formalizes and improves this:**
   - **Full history:** Every change is logged with *who, when, what, and why* (commit message).
   - **Safe experimentation:** Branch off without touching production/main. Fail safely.
   - **Collaboration without collisions:** Multiple people can work on the same repo; git merges carefully.
   - **Review before go-live:** Pull requests let you say "I want to merge this; please review." No accidents, no surprises.
   - **Easy rollback:** One line undoes a change if something breaks.

4. **Why this matters beyond code:**
   - Infrastructure as code (Terraform, Ansible).
   - Runbooks, scripts, playbooks.
   - Configuration (DNS zone files, app configs).
   - Documentation.

**Checkpoint:** Ask the room: "Can anyone think of a file or process in your team that would be safer with this kind of tracking?" (Wait for a few answers — reinforces relevance.)

**Timing:** If running long, tighten the "why" (you know your audience — emphasize what matters to *them*). If short, ask follow-ups.

---

### Section 2: What Is Git, Really? (5 min)

**Goal:** Demystify git. Clarify git ≠ Azure DevOps. Show the local/remote distinction.

**Opening line:**
> "Git is a *tool*. Azure DevOps (specifically Azure Repos) is a *hosting service*. Git runs on your machine; Azure Repos is where you upload it so the team can see it."

**Key distinctions:**

1. **Git vs. Azure DevOps (Azure Repos):**
   - **Git:** Free, open-source version control software. Runs locally on your machine.
   - **Azure DevOps (Azure Repos):** Microsoft's hosting service that stores your repo and adds extra features (Pull Requests, Build Pipelines, Teams).
   - **Analogy:** Git is the engine; Azure Repos is the platform. Like Gmail (email engine) vs. Google Drive (storage platform).

2. **Local vs. Remote repo:**
   - **Local repo (on your machine):** Full history, all branches, all commits. You have *everything*.
   - **Remote repo (on Azure Repos):** A copy that the team shares. It's the "source of truth" for the team.
   - **Key insight:** You can work offline and commit locally. Sync when you're ready to share.

3. **Three-part mental model (diagram this on screen or a slide):**

   ```text
   Working Directory  →  Staging Area  →  Local Repo  →  Remote Repo
   (files on disk)       (stage before)   (commits)       (shared copy)
   ```

   - **Working directory:** Where you edit files.
   - **Staging area:** "I've decided what to commit" — a temporary holding area. Lets you commit some changes and not others.
   - **Local repo:** Permanent history on your machine (hidden `.git` folder).
   - **Remote repo:** Copy on Azure Repos that everyone accesses.

4. **Why mention internals?** (Optional, skip if time is tight)
   - Git stores commits as immutable snapshots (not diffs like some older systems).
   - Every commit has a unique hash (looks like `abc123def456...`).
   - Branches are just pointers to commits.
   - This is why git can do powerful things like bisect and revert safely.
   - **For now:** Don't memorize this. Just know it's deterministic and reliable.

**Live demo (if time allows):**
- Show `git status` in a real repo to illustrate the three parts.
- Show `.git` folder (it's just files — nothing magical).

**Checkpoint:** "Any questions on local vs. remote? That's the main 'aha' moment I always see."

**Timing:** Keep this snappy. The goal is clarity, not depth. Save the internals for a later session.

---

### Section 3: Core Concepts & Vocabulary (8 min)

**Goal:** Introduce terms with plain-English definitions so attendees can follow the lab and future sessions.

**Setup:** "Here are 10 key terms. I'll define each one in one sentence. You'll see these words over and over, so they'll stick."

**Terms (with talking points):**

1. **Repository (repo)**
   - **Definition:** A folder containing your project files + a hidden `.git` folder that stores the full history.
   - **Talking point:** It's the whole package — files *and* history.

2. **Commit**
   - **Definition:** A saved snapshot of your changes, plus a message describing what changed and why.
   - **Talking point:** Like a checkpoint in a video game. You can jump back to any commit.
   - **Emphasis:** Good commit messages are crucial. "Fix bug" is vague; "Fix off-by-one error in DNS query loop" is clear.

3. **Branch**
   - **Definition:** An independent line of work — you can edit code on a branch without affecting main.
   - **Analogy:** Like a practice copy. Main is the "live" version; branches are safe sandboxes.

4. **Main / Master / Trunk**
   - **Definition:** The "source of truth" branch — the version that's (usually) running in production or considered stable.
   - **Note:** Many repositories now use `main` as the default branch name. The exact default is a repository convention, not a Git requirement.

5. **Remote**
   - **Definition:** A hosted copy of your repo (on Azure Repos) that the team shares.
   - **Convention:** Usually called `origin` (the default remote added when you clone).

6. **Clone**
   - **Definition:** Download a full copy of a remote repo to your machine for the first time.
   - **Talking point:** You get *everything* — all branches, all history. No need for a server after cloning.

7. **Pull / Push**
   - **Definition:** **Pull** = download new commits from remote. **Push** = upload your commits to remote.
   - **Memory aid:** Pull = get (down), Push = send (up).
   - **Emphasis:** Pull before you push to avoid conflicts.

8. **Merge**
   - **Definition:** Combine changes from one branch into another (usually a feature branch into main).
   - **Talking point:** Git tries to do this automatically; if it can't, it asks for help (conflict).

9. **Pull Request (PR)**
   - **Definition:** A proposal to merge a branch, with space for comments, approval, and discussion.
   - **Talking point:** This is where code review happens. "Please review my work before I merge it."
   - **Azure DevOps note:** PRs are created in the Azure DevOps portal (not a git command). You'll open it after pushing your branch.

10. **Conflict**
    - **Definition:** When git can't auto-merge (two branches edited the same line differently), it needs a human to decide.
    - **Talking point:** Conflicts are *normal* and not scary. Git tells you exactly where to look. You'll see this in the lab.

**Live example (if slides have examples):**
- Show a commit message and point out what makes it good.
- Show conflict markers so they recognize them in the lab.

**Checkpoint:** "Any of these confusing? Ask now before we move to the workflow."

**Timing:** Definitions should be snappy. This is a reference section — they'll internalize it through repetition in the lab.

---

### Section 4: Core Workflows — The Everyday Loop (8 min)

**Goal:** Walk through the day-to-day flow step-by-step, tying it to the three-part model from Section 2.

**Intro:** "This is what you'll do 90% of the time. Memorize this loop, and you can handle most situations."

**The loop (narrate + show commands on screen):**

```text
1. git clone <url>           # (once) get the repo
2. git pull                  # get latest from remote
3. <edit files>              # do your work
4. git status                # see what changed
5. git add <files>           # stage what you want to commit
6. git commit -m "message"   # save a snapshot
7. git push                  # send to remote
```

**Detailed talking points:**

**Step 1: Clone (once)**
```bash
git clone https://dev.azure.com/<org>/<project>/_git/<repo-name>
cd <repo-name>
```
- "First time only. You now have the full repo history on your machine."

**Step 2: Pull (every time you start work)**
```bash
git pull
```
- "Get any new changes your teammates pushed since yesterday."
- "This step prevents 'surprise' merge conflicts later."
- **Common question:** "Can't I just clone again?" — No, cloning is slow and wasteful; `pull` is fast.

**Step 3-4: Edit & Check**
```bash
# Make edits in your editor
git status      # "What's changed?"
git diff        # "Show me exactly what changed"
```
- "Your best friend is `git status`. Use it constantly. It tells you where you are."
- "Before committing, use `git diff` to review your changes. Catch mistakes early."

**Step 5-6: Stage & Commit**
```bash
git add roster/team.yaml           # stage this file
git commit -m "Add Alice to roster" # commit with a message
```
- "Staging is optional but powerful — you can commit some changes and not others, even from the same file."
- "The message is for future-you and your teammates. Be specific."
- **Example of good vs. bad:**
  - Bad: `git commit -m "update"`
  - Good: `git commit -m "Update DNS config to add backup nameserver"`

**Step 7: Push**
```bash
git push
```
- "Send your commits to the shared Azure Repos remote."
- "Your teammates can now see your work."

**Common mistakes to flag:**
- "If you get an error like 'rejected', it usually means the remote has changes you don't have. Run `git pull` and try again."
- "If you get asked for a password, make sure your SSH key is set up or use HTTPS (ask the team which one)."

**Live demo (highly recommended):**
- Clone the sample Azure Repos repo: `git clone https://dev.azure.com/<org>/<project>/_git/<repo-name>`
- Show `git status` after clone (clean working tree on `main`).
- Make a small edit to a file.
- Show `git status`, `git diff`, `git add`, `git commit`, `git push`.
- Then show the change appear in Azure Repos portal.

**Visual walkthrough:** Show the working dir → staging area → local repo → remote repo progression as you narrate each step.

**Checkpoint:** "Does that flow make sense? It's the same every day."

**Timing:** This is the heart of the session. Spend time here. Live demo is crucial to make it concrete.

---

### Section 5: Branching & Working With Others (4 min)

**Goal:** Introduce why branches matter (setting up Session 2/3) and the basic feature-branch workflow.

**Why branches?**
- "On your own, you could edit `main` directly and it would work. But on a team, if everyone edits `main`, you'll step on each other."
- "Branches let everyone work independently, then merge carefully when ready."

**Feature-branch workflow (diagram on screen):**

```text
main (v1.0)
    ↓
git checkout -b add-newfeature  # branch off
    ↓
(edit, commit, push)
    ↓
Open pull request
    ↓
(review, approve)
    ↓
Merge PR
    ↓
main (v1.1) — includes your feature
```

**Simple branching rules:**
1. **One branch per change/feature** — `add-load-balancer`, `fix-typo-docs`, etc.
2. **Branch off `main`** — don't branch off a branch (unless you have a reason).
3. **Descriptive name** — `fix-dns-query-timeout` is better than `fix-bug` or `work-stuff`.
4. **Delete after merge** — keeps the branch list clean.

**Pull request workflow (Azure DevOps):**
- You push your branch to Azure Repos: `git push -u origin <branch-name>`.
- You open a PR in the Azure DevOps portal (a UI button, not a git command).
- Your teammates review in the portal: "Do you like this change? Any problems?"
- Once approved (and builds pass, if any), merge the branch into `main`.
- Delete the branch (often done automatically after merge).

**Emphasis:** "This process is what prevents accidents and makes team work safe. Next session (Session 2) dives deep into this workflow."

**Checkpoint:** "More details in the lab. For now: one branch per feature, push, open a PR, merge when ready."

**Timing:** Keep this high-level. Session 2 is the deep dive.

---

### Appendix: "When Something Happens" — Optional Scenarios

**Goal:** Keep advanced recovery topics available for appendix slides, Lab 2,
or a short facilitator demonstration. These are not part of the timed core
presentation.

**Framing:** "This is the other 10% of the time — when things don't go smoothly. The good news: git has tools for all of this, and nothing is actually permanent."

**Note:** Keep these as **facilitator demos**, not attendee exercises (to protect timing). Attendees will try a subset in the lab.

---

#### 6a. Stashing — "I need to switch gears"

**Scenario:** You're halfway through editing `config.yaml` on branch A. A high-priority bug appears on `main`. You need to switch branches but aren't ready to commit yet.

**Solution:** `git stash`

**Live demo:**

```bash
# You have uncommitted changes
git status
# Output: modified: config.yaml

# Stash (set aside) the changes
git stash

# Working directory is now clean
git status
# Output: nothing to commit, working tree clean

# Switch to main and fix the bug
git checkout main
# ... fix the bug, commit, push ...

# When ready, switch back to your branch
git checkout branch-a

# Restore your stashed changes
git stash pop

# Your edits are back!
git status
# Output: modified: config.yaml
```

**Key talking points:**
- "Stash is like a clipboard for your uncommitted work. It's temporary."
- "You can stash multiple times. `git stash list` shows all stashes."
- "`git stash pop` restores the most recent. There's also `git stash apply` (doesn't delete the stash)."

**When to use:** Switching contexts without committing. Not a long-term storage tool.

---

#### 6b. Undoing / Rolling Back

**Scenario 1: "I made changes but haven't committed yet."**

```bash
# See what changed
git status
git diff

# Discard the changes (CAREFUL — can't undo this!)
git restore <filename>
# Or: git checkout -- <filename>

# Discard ALL uncommitted changes
git restore .
```

**Scenario 2: "I committed, but haven't pushed yet."**

```bash
# Undo the last commit; keep the edits
git reset --soft HEAD~1

# Undo the last commit; discard the edits
git reset --hard HEAD~1

# Fix a typo in the last commit message
git commit --amend -m "New message"
```

**Scenario 3: "I committed AND pushed (shared with the team)."**

**STOP. Do NOT use `git reset` on shared branches.**

Instead, use `git revert` (creates a new commit that undoes the old one):

```bash
# Find the commit you want to undo
git log --oneline

# Create a new commit that undoes it
git revert abc123def456
```

**Key talking points:**
- **Local (not pushed):** You can use `reset` or `amend` — rewrites history.
- **Shared (already pushed):** Use `revert` — adds a new commit, doesn't rewrite history.
- **Why?** If teammates pulled your commit, rewriting history breaks their local repo. Reverting is safe and clear.
- **Memory aid:** Before it's shared, you can rewrite. After it's shared, you add a new commit.

**Checkpoint:** "Does the distinction make sense? Most accidents happen on local branches, so `reset` usually applies. But know `revert` for when things are shared."

---

#### 6c. Merge Conflicts

**Scenario:** Two branches edited the same line. Git can't auto-merge.

**Live demo (show conflict markers):**

```bash
# Try to merge branch-b into your branch
git merge branch-b

# Output: CONFLICT (content merge) in roster/team.yaml
# Automatic merge failed; fix conflicts and then commit the result.
```

**The conflict file looks like:**

```yaml
- name: Alice
<<<<<<< HEAD
  role: Senior Engineer
=======
  role: Principal Engineer
>>>>>>> branch-b
```

**Resolution:**

```bash
# Open the file in your editor and choose which version you want
# (or manually combine them)

# Let's say you keep "Principal Engineer"
- name: Alice
  role: Principal Engineer
```

**Then:**

```bash
# Stage the resolved file
git add roster/team.yaml

# Commit (git prompts you; you can accept the default message)
git commit

# Merge is complete!
```

**Key talking points:**
- "Conflicts are normal. They happen when two branches change the same line."
- "Git marks the conflict clearly with `<<<<<<<`, `=======`, `>>>>>>>`."
- "You just open the file, pick a version (or combine them), and commit."
- "You can always `git merge --abort` to start over if you panic."

**Checkpoint:** "Conflicts look scary, but they're just git saying 'I need a human to decide.' You've got this."

---

#### 6d. Investigating History (Optional, if time allows)

**Scenario:** "Who changed this line? When? Why?"

```bash
# See the change history of a file (one commit per line)
git blame <filename>

# See detailed changes to a file
git log -p <filename>

# See what changed in a specific commit
git show abc123def456

# Compare two branches
git diff main..branch-a
```

**Emphasis:** "These tools are your friends for debugging. Especially in ops, knowing *why* a change was made is gold."

#### 6e. `.gitignore` — "What should Git leave alone?"

**Scenario:** A local-only file, generated output, or credentials file appears as untracked, but should not be committed.

**Key talking points:**
- `.gitignore` lists patterns for files Git should leave untracked.
- Common entries include editor settings, operating-system files, logs, build output, and local secrets.
- It keeps `git status` useful and helps prevent accidental commits of machine-specific content.
- It does not remove a file that Git is already tracking. A secret that was committed should be treated as exposed and rotated.

**Small example:**

```gitignore
.DS_Store
.env
*.log
dist/
```

**Demo:** Create a temporary `.log` file, run `git status`, add `*.log` to `.gitignore`, and run `git status` again. Emphasize that ignore rules do not erase history.

**Timing:** Keep this to 1-2 minutes or point attendees to the cheat sheet. Do not add real credentials to demonstrate the concept.

---

**End of Part A**

**Transition to Part B:**

> "That's the theory. Now let's get your hands on the keyboard. Part B is where you'll try all this on your own, with help from me and the team nearby."

**Timing checkpoint:** You should be at approximately 25-30 minutes before
starting Lab 1. Protect the full Lab 1 workflow before offering Lab 2.

---

## Part B — Hands-on Lab (~30 minutes)

See [workshop-01-lab-plan.md](workshop-01-lab-plan.md) for the two lab activities and checkpoints.

### Facilitation Tips

- **Walk the room:** Circulate. Don't stay at your own computer.
- **Help bottlenecks:** If multiple people are stuck on the same step, pause the group and solve it together.
- **Celebrate progress:** "Alice just pushed her branch! Everyone else, you're close."
- **Merge live (optional):** If the group is keeping pace, open the Azure DevOps portal, show a PR, demonstrate a code review, and merge one live so attendees see the full flow. Otherwise, merge them after the session.
- **Handle Lab 2:** Lab 1 is the required instructor-led flow. Offer Lab 2 as an optional self-directed workshop after the core checkpoint; do not start Lab 2 until attendees have completed their PR workflow.

### Troubleshooting Common Lab Issues

| Issue                                   | Cause                                         | Solution                                                                                               |
| --------------------------------------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| "Permission denied" or "Repo not found" | SSH key not set up or no access to repo       | Use the approved HTTPS clone URL, or ask the Azure DevOps project admin to verify access and SSH setup |
| `git status` shows untracked files      | Files created in the repo but not added       | `git add` them if they're intentional; `.gitignore` to exclude them if not                             |
| "Merge conflict" during push            | Remote main changed since you pulled          | `git pull` first, resolve conflict, then push                                                          |
| "Detached HEAD" state                   | Checked out a commit hash instead of a branch | `git checkout main` to get back on a branch                                                            |
| Can't open a PR                         | Branch not pushed to remote                   | Run `git push -u origin <branch-name>`                                                                 |
| Accidental push to main                 | Pushed directly instead of opening a PR       | It's OK! Use `git revert` to undo, or ask team for help                                                |
| "SSL: CERTIFICATE_VERIFY_FAILED"        | Corporate firewall/cert issues                | Use HTTPS instead of SSH, or check with IT on cert setup                                               |

### When Someone Gets Lost

**Reassure them:** "Everyone gets lost. It's normal. Let's trace back."

**Quick diagnostic:**

```bash
# Where are we?
git status

# What branch?
git branch

# What's the history?
git log --oneline -5
```

**Most common fixes:**
- `git pull` to sync if they're behind.
- `git checkout <branch-name>` if they're on the wrong branch.
- `git restore .` to discard uncommitted changes they didn't mean to make.
- Start over on a fresh branch if things are too tangled (it's OK!).

### End-of-Lab Proficiency Check

Before closing, ask each attendee to show or report:

- Their current personal branch from `git status`.
- Their latest commit from `git log -1`.
- Their pull request URL.
- In their own words, the difference between `git commit` and `git push`.

This is a lightweight completion check for the core objective. It is more
useful than relying on confidence feedback alone and does not require the
facilitator to grade the optional recovery workshop.

---

## Wrap-Up & Next Steps (~5 min)

**What attendees should take away:**

1. They've cloned, branched, committed, pushed, and opened a PR.
2. They can now confidently use git for their day-to-day work.
3. They know where to find the cheat sheet when they forget a command.

**Announce next session:**

> "Session 2 is [date/time]: **Branching Workflows & Pull Requests in Practice**. We'll go deeper into pull requests, code review in Azure DevOps, and how to avoid common mistakes when working on a team. See you there!"

**Distribute materials:**

- Cheat sheet (PDF or Slack/wiki link).
- Sample repo URL (for practicing after the session).
- Feedback form (optional, but valuable for improving future sessions).

**Recording & resources:**

- Recording link (if recorded).
- Link to this repo (in Azure DevOps wiki or project documentation).
- Cheat sheet link.
- Office hours: "If you get stuck after the session, DM me on Teams or email. I'm happy to help over lunch or coffee."

---

## Appendix: Answers to Common Questions

### "Why not use a GUI?"
- It's great once you're comfortable! But we're learning the fundamentals. CLI is the same everywhere; GUIs vary by platform.

### "Why is it called 'Git'?"
- Linus Torvalds (Linux creator) named it. He said: "I'm an egotistical bastard, and I name all my projects after myself. First 'Linux', now 'git'." It's also slang for a foolish person — he was joking.

### "Can I use git without Azure DevOps?"
- Yes! Git is local. You can use it alone without ever pushing to a remote. But for team collaboration, you need a hosting service like Azure Repos (part of Azure DevOps).

### "What's the difference between `git pull` and `git fetch`?"
- `fetch` downloads remote changes but doesn't merge them into your branch.
- `pull` does `fetch` + `merge` in one command.
- Most of the time, `pull` is what you want.

### "How do I undo a push?"
- If you pushed to a shared branch: Use `git revert` (safe).
- If you pushed to your own branch and haven't merged to main: Use `git push --force` (risky; ask the team/admin first). Note: Azure DevOps administrators can restrict force-push by policy.
- **Best answer:** Try not to. That's why Pull Requests exist — review before you merge into main.

### "Will I accidentally delete important files?"
- Not unless you run `git reset --hard` and explicitly tell it to. Git is very conservative about data loss.
- Worst case: reflog stores deleted commits for ~30 days.

### "Is there a way to see a visual history?"
- `git log --oneline --graph --all` is text-based (works on any machine).
- **Azure DevOps portal** has a visual "Branches" view showing branch graph, merge paths, and PR history — this is very helpful for team collaboration.
- Tools like `gitk` or `tig` are GUIs for history (optional, local machine only).

---

**Last reminder:** You've got this. Teaching git is scary because attendees have varying experience levels, but the fundamentals are simple. Keep it calm, answer questions patiently, and celebrate small wins. Your enthusiasm is contagious.

Good luck! 🚀
