# Slide Deck Outline — Part A: Git Fundamentals Tutorial (~30 min)

**Facilitator:** [YOUR NAME]  
**Date:** [INSERT DATE]  
**Format:** 30 minutes of presentation, encouraging audience interaction

This outline pairs with [facilitator-guide.md](facilitator-guide.md). Each section includes suggested slides, talking points, and interactive moments.

---

## Opening Slide (1 min)

**Title Slide:**
- **Main Title:** "Git Fundamentals: What, Why & How"
- **Subtitle:** "A lunch-and-learn on version control for Engineering & IT Ops"
- **Your name, date, time**
- **Agenda:** "30 min talk + 30 min hands-on lab"

**Speaker notes:** Welcome everyone. Quick logistics: bathrooms, chat/questions. After the talk, we're jumping into a real git lab on your machines — don't worry if you've never done this before.

---

## Section 1: Why Version Control? (5 min)

### Slide 1.1: The Problem — File Naming Hell
- **Visual:** Humorous image of file names like:
  - `final.docx`
  - `final_v2.docx`
  - `final_v3_REALLY_FINAL.docx`
  - `final_v3_REALLY_FINAL_v2.docx`
  - `THIS_ONE.docx`
- **Speaker talking point:** "Have you ever done this? It's chaos. Git solves this."

### Slide 1.2: The Ops Reality
- **Bullet points:**
  - Managing change tickets and backup dates (instead of version history)
  - Accidental overwrites on shared drives
  - "Who changed the DNS config? When? Why?"
  - No way to roll back a bad change quickly
- **Speaker point:** "This isn't just for code. Runbooks, scripts, configs, DNS files — everything benefits."

### Slide 1.3: What Git Does
- **4-box diagram:**
  1. ✅ **Full History** — Every change logged with who/when/why
  2. ✅ **Safe Branching** — Experiment without breaking production
  3. ✅ **Collaboration** — Multiple people, no collisions
  4. ✅ **Easy Rollback** — One command to undo a bad change
- **Speaker point:** "These aren't just nice-to-haves. They're game-changers for team reliability."

---

## Section 2: What Is Git, Really? (5 min)

### Slide 2.1: Git ≠ Azure DevOps
- **Two boxes side-by-side:**
  - **Left:** "Git" — laptop icon — "Local tool on your machine"
  - **Right:** "Azure Repos/DevOps" — cloud icon — "Hosting service (where you upload)"
- **Speaker point:** "These are different things. Git is what you run; Azure Repos is where the team shares."

### Slide 2.2: Local vs. Remote
- **Diagram (three-layer model):**
  ```text
  Your Machine (Full copy)  ←→  Azure Repos (Team's copy)
  ```
- **Bullet points:**
  - **Local:** You have the entire history. Can work offline.
  - **Remote:** Shared copy. "Source of truth."
  - **Connection:** `git push` and `git pull` keep them in sync.
- **Speaker point:** "You're not dependent on the server to use git. That's the power of distributed version control."

### Slide 2.3: Three-Part Mental Model
- **Diagram (key graphic — use this throughout the session):**
  ```text
  Working Dir  →  Staging Area  →  Local Repo  →  Azure Repos
  (your edits)    (stage changes)  (commits)    (shared copy)
  ```
- **Speaker point:** "This is the core model. Everything flows through these four zones. Keep this in mind."

---

## Section 3: Core Concepts & Vocabulary (8 min)

**Speaker intro:** "Here are the 10 key terms you'll hear over and over. I'm not asking you to memorize them — just get familiar."

### Slide 3.1: Repository & Commit
- **Repository (repo):**
  - 📁 Folder + hidden `.git` folder (the history storage).
  - Example: `https://dev.azure.com/myorg/myproject/_git/sample-training-repo`
- **Commit:**
  - 📸 A saved snapshot + message ("What changed and why?").
  - Example message: "Add DNS record for api.example.com"
- **Speaker point:** "A commit is like a checkpoint in a video game. You can jump back to any one."

### Slide 3.2: Branch & Main
- **Branch:**
  - 🌳 An independent line of work (safe sandbox).
  - Example: `add-newfeature`, `fix-dns-bug`, `update-docs`
- **Main (or Master):**
  - 🏆 The "official" branch (usually running in production).
  - "Where the stable version lives."
- **Speaker point:** "One branch per feature. Don't edit `main` directly."

### Slide 3.3: Remote, Clone, Push, Pull
- **Remote:**
  - 🌐 Hosted copy on Azure Repos.
  - Usually called `origin`.
- **Clone:**
  - 📥 Download the full repo to your machine (first time only).
- **Push / Pull:**
  - ⬆️ **Push:** Send your commits to Azure Repos.
  - ⬇️ **Pull:** Get new commits from Azure Repos.
- **Speaker point:** "Pull before you push. It prevents 'surprise' conflicts."

### Slide 3.4: Merge & Pull Request
- **Merge:**
  - 🔀 Combine two branches.
  - Usually done after review.
- **Pull Request (PR):**
  - 📝 "Please review my work before merging."
  - Created in Azure DevOps portal (not a git command).
- **Speaker point:** "PRs are where code review happens. This is what makes team work safe."

### Slide 3.5: Conflict
- **Conflict:**
  - ⚠️ When two branches edit the same line, git asks for help.
  - Not scary — just need a human decision.
  - Git tells you exactly where to look.
- **Speaker point:** "You'll see one in the lab. It looks scary, but it's manageable."

---

## Section 4: Core Workflows — The Everyday Loop (8 min)

**Speaker intro:** "This is what you'll do 90% of the time. One simple loop."

### Slide 4.1: The Loop (Title Slide)
- **Large text:** "The Everyday Git Workflow"
- **Subtext:** "Repeat this every day"

### Slide 4.2: Clone (Once)
```bash
git clone <repo-url>
cd <repo-name>
```
- **Talking point:** "First time only. You now own a full copy of the repo."

### Slide 4.3: Pull (Every Day)
```bash
git pull
```
- **Talking point:** "Get the latest changes from your teammates before you start."

### Slide 4.4: Edit, Check, Commit
```bash
<edit files in your editor>
git status      # "What changed?"
git diff        # "Show me exactly what"
git add <file>  # "I want to commit this"
git commit -m "Clear message about what changed"
```
- **Talking point:** "`git status` is your best friend. Use it constantly. And good commit messages are crucial."

### Slide 4.5: Push
```bash
git push
```
- **Talking point:** "Send your work to Azure Repos. Your teammates can now see it."

### Slide 4.6: Branch-Per-Feature (Optional Bonus Slide)
- **Diagram:**
  ```text
  main
    ↓ git checkout -b add-newfeature
  add-newfeature (your branch)
    ↓ (edit, commit, push)
  Open PR → Review → Merge
    ↓
  main (updated)
  ```
- **Talking point:** "This is the safe way to collaborate. Branch off, experiment, open a PR for review."

---

## Appendix Slides: "When Something Happens" — Optional Topics

Keep these slides after the core deck so the shared presentation retains the
advanced concepts without making them part of the timed talk. Use them during
Lab 2 or as facilitator-led demonstrations only if time and audience interest
allow.

### Slide 5.1: Stashing (Demo Slide)
- **Scenario:** Mid-edit, need to switch branches. Don't want to commit yet.
- **Solution:**
  ```bash
  git stash          # Set aside your work
  git checkout main  # Switch branches
  git stash pop      # Bring your work back
  ```
- **Visual:** Show stashed changes being set aside, then restored.
- **Speaker point:** "Stash is your clipboard. Use it when you need to switch gears."

### Slide 5.2: Undoing (Demo Slide)
- **Three scenarios:**
  1. **Not committed yet:** `git restore <file>` (discard edits)
  2. **Committed, not pushed:** `git reset --soft HEAD~1` (undo, keep edits)
  3. **Already pushed (shared):** `git revert <commit>` (add a new commit that undoes it)
- **Speaker point:** "Local? You can rewrite history. Shared? Use revert (it's safer)."

### Slide 5.3: Merge Conflicts (Demo Slide)
- **Show conflict markers:**
  ```text
  <<<<<<< HEAD
  version: 1.2.0
  =======
  version: 1.3.0
  >>>>>>> feature-branch
  ```
- **Resolution:**
  1. Open file, pick a version (or combine).
  2. Delete conflict markers.
  3. `git add` + `git commit`.
- **Speaker point:** "Conflicts look scary, but git shows you exactly where. Just pick a version."

### Slide 5.4: Investigating History (Demo Slide, Optional)
- **Commands to mention:**
  ```bash
  git log --oneline           # See recent commits
  git blame <file>            # Who changed each line?
  git show <commit-hash>      # What changed in this commit?
  ```
- **Speaker point:** "These are your friends for debugging. 'Who changed this? When? Why?'"

### Slide 5.5: `.gitignore` — Keep Local Files Out of the Repo (Optional)
- **Purpose:** Show how to keep generated, machine-specific, temporary, or sensitive files from appearing as untracked changes.
- **Example:**
  ```gitignore
  .DS_Store
  .env
  *.log
  dist/
  ```
- **Key points:**
  - `.gitignore` contains patterns for files Git should not track.
  - It keeps `git status` focused on intentional work.
  - It does not stop tracking a file that was already committed.
  - It does not erase a secret from history; rotate a committed secret immediately.
- **Speaker point:** "Ignore rules prevent accidental future adds; they do not erase anything from Git history."
- **Demo option:** Create a temporary `.log` file, show it with `git status`, add `*.log` to `.gitignore`, and show that it no longer appears as an untracked file.

---

## Closing Slide (1 min)

**Title:** "Ready to Practice?"

**Bullet points:**
- You've got the concepts.
- Now let's get your hands on the keyboard.
- Part B: Real hands-on lab (30 min).
- I'll walk the room; you're not alone.

**Speaker point:** "Questions before we jump into the lab? Ask now — no dumb questions."

---

## Presentation Tips

### Pacing
- Use timing notes in [facilitator-guide.md](facilitator-guide.md).
- Spend the most time on Section 4 (everyday workflow) — that's the core.
- Sections 5 are demos — you drive; attendees watch (to save time).

### Engagement
- Start with the "final.docx" question (get hands up).
- Use the three-part model diagram throughout — keep reinforcing it.
- Ask "Any questions?" at checkpoints (don't rush).
- Live demo a clone + push if you have time (makes it real).

### Visuals
- Keep slides simple (text + one diagram per slide, mostly).
- Use the three-part mental model diagram in Section 2.3 repeatedly — it's your anchor.
- Show actual terminal output when demoing (screenshots are fine if you're remote).

### Contingency
- If you fall behind: Skip Section 5 (stash/undo). Do a live demo instead in the lab.
- If you're ahead: Use "Investigating History" slide or ask more questions of the room.

---

## Materials to Have Ready

- **Printed cheat sheet** (one per attendee, or link in chat).
- **Sample repo URL** (paste in chat or write on whiteboard).
- **Backup slides** (screencaps of git commands if your live demo fails).
- **Timer** (to keep pace).

---

## Suggested Slide Tools

- **Recommended:** Google Slides, PowerPoint, or Keynote (all are fine).
- **Design:** Keep it simple. Dark background, large font, minimal text.
- **Export:** PDF for distribution after the session.

---

## Notes for Building Your Slides

1. **Use this outline as a skeleton** — expand each section with your own stories/examples.
2. **Add your org's branding** (logo, colors) to title slide.
3. **Customize examples** — if your team uses specific Azure DevOps projects or repos, reference them.
4. **Test the demos** — make sure you can clone, edit, and push live without fumbling.
5. **Practice timing** — do a full run-through before the session.

---

## After You Build Slides

- [ ] Export to PDF for distribution.
- [ ] Link from the main README or Azure DevOps wiki.
- [ ] Send to attendees the day before (optional, but helps).
- [ ] Print slides (optional, but useful for note-taking).

