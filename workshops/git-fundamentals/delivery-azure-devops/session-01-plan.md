# Session 1 Content Plan — Git Fundamentals

**Duration:** ~60 minutes (lunch-and-learn)
**Audience:** Engineering + IT Ops, mixed experience, assume zero git knowledge
**Format:** Part A tutorial/talk (~30 min), Part B hands-on lab (~30 min)

Goal for attendees to be able to say after this session: *"I understand what
git is doing and why, and I can clone, branch, commit, push, and open a pull
request on my own."*

---

## Part A — Tutorial (~30 minutes)

### 1. Why Version Control? (5 min)
- The problem it solves: `final.docx`, `final_v2.docx`, `final_v2_REALLY.docx`
  — but for code/config/scripts.
- What operations folks already do informally (shared drives, backups,
  change tickets) and how git formalizes/improves it.
- Key benefits to land:
  - Full history of *who changed what, when, and why*.
  - Safe experimentation (branches) without breaking what works.
  - Collaboration without overwriting each other's work.
  - Ability to review changes before they go live (pull requests).
  - Easy rollback when something breaks.
- Brief framing: this isn't just for developers — infra-as-code, scripts,
  runbooks, and configuration (including DNS zone files, later session) all
  benefit the same way.

### 2. What Is Git, Really? (5 min)
- Git vs. Azure DevOps/Azure Repos — git is the tool, while Azure Repos is the
  hosting service. Keep this distinction simple and concrete.
- Local vs. remote repository — your machine has the full history too, not
  just the server.
- High-level mental model (diagram): working directory → staging area →
  local repo (commits) → remote repo.
- Avoid deep internals (blobs/trees/objects) — keep it conceptual for a
  lunch session; mention it exists for the curious.

### 3. Core Concepts / Vocabulary (8 min)
Introduce each with a one-line plain-English definition and a small diagram
where useful:
- **Repository (repo)** — a project's folder + its full history.
- **Commit** — a saved snapshot with a message describing the change.
- **Branch** — an independent line of work off the main history.
- **Main/trunk branch** — the "source of truth" branch (e.g. `main`).
- **Remote** — the hosted Azure Repos copy of the repository, usually called
  `origin`.
- **Clone** — get a full local copy of a remote repo.
- **Pull / Push** — sync commits down from / up to a remote.
- **Merge** — combine changes from one branch into another.
- **Pull Request (PR) / Merge Request (MR)** — a request to review and merge
  a branch, with a place for comments/approval.
- **Conflict** — when git can't automatically reconcile two changes to the
  same lines and needs a human decision.

### 4. Core Git Workflows — The Everyday Loop (8 min)
Walk through the "day in the life" loop, tied to the diagram from #2:

```
git clone   → (once) get the repo
git pull    → get latest changes before starting work
<edit files>
git status  → see what changed
git add     → stage the changes you want to commit
git commit  → save a snapshot with a message
git push    → send commits to the remote
```

- Emphasize: `status` is your best friend — use it constantly.
- Emphasize: commit messages are for future-you and your teammates — a
  quick convention (e.g. "what changed + why") goes a long way.
- Briefly show what a good vs. vague commit message looks like.

### 5. Core Git Workflows — Branching & Working With Others (4 min)
- Why branch per change/feature instead of editing `main` directly.
- Simple feature-branch flow diagram: branch off `main` → commit → push →
  open PR → review → merge → delete branch.
- One sentence on why this matters more once >1 person touches the same
  repo (ops runbooks, DNS zone files, etc.) — sets up Session 2/3.

### 6. Optional Extension Topics — "When Something Happens"

These topics remain documented for the shared deck and cheat sheet, but are
not part of the focused 30-minute presentation. Use them as appendix slides,
short facilitator demonstrations, or the optional second lab activity. The
everyday loop and the branch/PR flow are the required presentation content.

**a. Stashing — "I need to switch gears without committing"**
- Scenario: mid-edit, asked to urgently check something else on `main` or
  another branch.
- `git stash` → set aside uncommitted changes, working tree goes clean.
- `git stash list` → see what's stashed.
- `git stash pop` → bring the changes back when ready.
- One-liner: think of it as a clipboard for your uncommitted work.

**b. Undoing / Rolling Back — "I need this change gone"**
Distinguish clearly (a common point of confusion) between three levels:
- **Not staged yet:** `git restore <file>` (or `git checkout -- <file>`)
  discards uncommitted edits to a file.
- **Staged but not committed:** `git restore --staged <file>` un-stages
  without losing the edit.
- **Already committed, not pushed:** `git commit --amend` (fix the last
  commit) or `git reset` (move the branch pointer back) — mention briefly,
  flag as "ask before doing this if you're not sure."
- **Already pushed / need to undo safely on a shared branch:** `git revert
  <commit>` — creates a *new* commit that undoes an old one, safe for
  shared history because it doesn't rewrite anything.
- Key message for this audience: **`revert` is the safe default once
  something is pushed/shared; `reset`/rewriting history is for your own
  local, not-yet-shared work.**

**c. Investigating — "What happened, and where did it break?"**
This is the "detective work" toolkit — high value for ops folks tracing an
incident back to a change:
- `git log` / `git log --oneline --graph` — the timeline of commits; what
  changed and when.
- `git log -p <file>` or `git log --follow <file>` — history of one specific
  file (e.g. a zone file or config).
- `git show <commit>` — see exactly what a specific commit changed.
- `git blame <file>` — see who last changed each line, and in which commit
  (great starting point for "who do I ask about this line?").
- `git diff <branch1>..<branch2>` — compare two branches/points in time.
- `git bisect` — binary-search through commit history to find the exact
  commit that introduced a bug/break; mention conceptually with an example
  ("broke sometime in the last 40 commits, `bisect` finds it in ~6 tries
  instead of checking all 40") rather than a full live demo, time-permitting.

**d. Other Flows Worth Knowing (quick mentions, pointer to cheat sheet)**
- `.gitignore` — telling git what *not* to track (secrets, local-only
  files, build output).
- Tags (`git tag`) — marking a specific commit as a release point, useful
  once we're tracking DNS/config changes tied to deployments.
- `git fetch` vs `git pull` — `pull` is really `fetch` + merge; worth
  knowing when you want to look before you merge.

### 7. Q&A / Bridge to Lab (≤2 min)
- Quick pause for questions before switching to hands-on mode.
- Set expectations: "you will make a mistake in the lab, that's fine — it's
  the safest place to make one, and now you've also seen how to undo it."

**Slide count estimate:** ~16-20 core slides, plus appendix slides for these
optional topics. The core presentation should be dry-run at 25-30 minutes so
the first lab activity has protected time.

---

## Part C — Appendix / Preview: Automation Around Git

**Not part of the 60-minute core session** — this content is heavier and
assumes the audience already has the Part A mental model down. Keep it as
either (a) a short "here's what's coming" teaser at the very end of Session 1
(5 min max, conceptual only, no live demo), or (b) the seed content for a
dedicated Session 2/3 slot ("Automating Checks with Git: Hooks & Pipelines").
Decide placement once Part A timing is dialed in.

### 8. Pre-commit Hooks & Local Automation

**What they are:** scripts that git runs automatically at specific points in
the workflow (`pre-commit`, `commit-msg`, `pre-push`, `post-merge`, etc.).
They let you catch problems *before* a commit/push ever happens, instead of
after a reviewer or a pipeline flags it.

**How they work:**
- Git looks in `.git/hooks/` for an executable script matching the hook
  name (e.g. `.git/hooks/pre-commit`) and runs it at that point in the
  workflow. If the script exits non-zero, git stops the operation (e.g. the
  commit is blocked) until it's fixed.
- `.git/hooks/` is **not** version-controlled by default (it lives inside
  the local `.git` folder), so a hook you write only affects your machine
  unless you deliberately share/install it for the team.

**Setting up a hook for yourself (local only):**
- Add an executable script at `.git/hooks/pre-commit` (any language —
  shell, Python, etc.) that runs checks and exits non-zero to block the
  commit.
- Good starter use cases: block commits with `TODO`/`FIXME` left in, block
  commits over a certain file size, run a quick formatter.

**Setting up hooks as part of a repository (shared with the team):**
Since `.git/hooks/` isn't committed, teams use a framework to manage and
distribute hook scripts through the actual repo:
- **[pre-commit](https://pre-commit.com/)** (language-agnostic, Python-based)
  — define hooks in a versioned `.pre-commit-config.yaml`, teammates run
  `pre-commit install` once after cloning to wire it into their local
  `.git/hooks/`.
- **Husky** (common in JS/Node projects) — similar idea, installed via
  `npm install` + a `prepare` script so it's automatic after `npm install`.
- Both approaches mean the *hook definitions* live in the repo (reviewed
  like any other code), but each person still has to "install" them locally
  once — git itself has no built-in way to force-run a hook from a fresh
  clone without this kind of setup step.

**What they're good for (concrete examples relevant to this audience):**
- Linting/formatting code or config before it's committed.
- Validating file syntax — e.g. a DNS zone file or YAML config parses
  correctly before it's even pushed (great callback to Session 3).
- Secret scanning — block a commit that accidentally includes an API key
  or password.
- Enforcing commit message conventions (`commit-msg` hook).
- Running a fast subset of tests before allowing a push (`pre-push`).

**Key message:** hooks are a *local, fast, first line of defense* — they
don't replace the pipeline checks in Part 9 below (which run for everyone,
regardless of whether they installed hooks), but they give faster feedback
and reduce noisy failed pipeline runs.

### 9. CI/CD Pipeline Primer — Azure DevOps Pipelines

**What a pipeline is:** an automated set of steps that runs in response to a
git event (push, opening/updating a PR, a tag, a schedule) — typically to
build, test, lint, scan, and/or deploy. Think of it as "hooks, but running
on a server for everyone, not just on your machine."

**Why it matters for this team:**
- Turns "please remember to test this" into "it's checked automatically,
  every time."
- Can be required as a **status check** — a PR literally cannot be merged
  until the pipeline passes (pairs directly with the PR flow from Part A).
- For DNS-as-code specifically (preview for Session 3): a pipeline can
  validate zone file syntax and even do a dry-run/plan before anything is
  applied to a real DNS provider.

**Azure DevOps Pipelines:**
- Defined as YAML in `azure-pipelines.yml` (or classic UI-based pipelines,
  less common now).
- Triggers similarly on push/PR; structured as **stages → jobs → steps**,
  running on an **agent** (Microsoft-hosted pool or self-hosted).
- PR builds can be wired to **branch policies** as a required check before
  merge.

**Setting up credentials securely:**
- **Never** put secrets/credentials directly in the pipeline YAML or in
  repo files — that's the #1 mistake to call out explicitly.
- **Azure DevOps:** store secrets in a **variable group** (optionally
  backed by Azure Key Vault) or directly as a secret **pipeline variable**;
  connections to external systems (e.g. Azure subscription) go through a
  **service connection**, which centralizes and can restrict/authorize
  credential use per pipeline.
- **Best practice:** prefer short-lived, federated credentials over
  long-lived static secrets where possible, such as Azure DevOps workload
  identity federation service connections.
- Add branch protection / environment approval rules so deploy-capable
  pipelines can't be triggered from just any branch or without a sign-off.

**Key message:** hooks catch things fast and locally; pipelines catch things
reliably and consistently for everyone, and are the gate that keeps `main`
deployable. Together they're the "why version control matters" story from
Part A, made concrete.

---

## Part B — Hands-on Lab (~30 minutes)

See detailed exercise plan: [workshop-01-lab-plan.md](workshop-01-lab-plan.md)

High-level flow only (full steps in the lab plan doc):
1. Confirm git is installed + configured (name/email) — should be done in
   pre-work, brief live check only.
2. Clone the shared sample training repo.
3. Create a personal branch, make a change, commit, push.
4. Open a pull request against `main`.
5. (Optional Lab 2) Practice stash, investigation, revert, or conflict
  resolution from a disposable branch or clone.
6. Wrap-up: recap vocabulary used during the lab, point to cheat sheet.

---

## Materials Needed

- [ ] Shared sample repo (see workshop plan) hosted in Azure Repos.
- [ ] Facilitator machine with a projector-friendly terminal font/theme.
- [ ] Cheat sheet handout/link (see resources plan).
- [ ] Pre-work email: install git, configure name/email, and confirm access to
      the Azure Repos sample repository.

## Decisions Before Building Slides

- Use Azure Repos and the Azure DevOps portal for the normal delivery path.
- Keep the core deck command-line focused; mention GUI clients only if the
  audience needs an accessibility or onboarding alternative.
- Decide whether the hooks and Azure DevOps Pipelines appendix is shown as a
  short teaser or held for Session 5 after the core deck is timed.
