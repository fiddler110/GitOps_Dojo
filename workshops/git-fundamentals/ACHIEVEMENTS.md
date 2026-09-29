# git-fundamentals: achievements catalog (DRAFT for review)

Nothing here is built. This is the review copy of the catalog for this workshop; the runtime format comes later
(see `ROADMAP.md`, "Achievements"). Each workshop keeps its own catalog beside its `workshop.env`.

**How to read it.** Points are the defaults (milestone 10, funny 5, challenge 100, capstone 300, all settable in
`.env`). `core` means the milestone counts toward the certificate (80% of the `core` set). Triggers:

- `shell:` the student ran this command and it exited as stated (shell hook; the command and the branch are logged)
- `forgejo:` a Forgejo webhook event for that student
- `verify:` the achievements service checks the end state (verifiers, run by `dojo-check` or after an event)

`{user}` is the student's login (`student07`). Jokes are the toast text; edit freely.

## Completion

**Every lab is mandatory** (decided). `core` is every lab milestone, so the certificate and the "Workshop complete"
banner come at 80% of them, and the student's home page shows a running completion percentage. Challenges, the capstone
and the funny unlocks are optional bonuses and never count toward completion. `l1-merged` stays non-core: it depends on
someone merging the PR (see the auto-merge item in `ROADMAP.md`).

## Rules for challenges and capstones (apply to every workshop)

Students share one Forgejo, one DNS server, one CA, one cloud and one vault, so a challenge that changes shared state
breaks for the second person to try it. Every challenge and capstone must follow these:

1. **Write only to a space keyed on `{user}`:** their own repo, zone, namespace, slot or name prefix. Never `main` of a
   shared repo, a shared zone's apex, or an unprefixed name.
2. **Verify only that space.** Assertions read `{user}`-keyed state, never global state (a shared `main`, a whole zone,
   "the cloud is empty"), so another student's work can neither pass nor fail yours.
3. **No dependency on another student.** No peer approval, no "wait for a classmate". If a review or a merge is part of
   the goal, the seed provides the other party (a seeded PR from a bot account), or the facilitator, and only where
   truly required (the catalog says so).
4. **Change no shared config:** CA lifetimes, quotas, policies, branch protection and shared zones are read-only to a challenge.
5. **Seed per student.** The service creates one seed for each student (a repo, a branch set, a zone file) when the
   challenge is first opened. It is never one shared seed with a per-student label, because a fix to it lands for everyone.
6. **Independent of each other.** A challenge must still pass if another challenge was never attempted, or was undone
   (for example a capstone that destroys everything must not break an earlier challenge's check, which is verified when
   it runs, not re-checked later).

## Lab 1: the core workflow

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| l1-clone | Cloned Around | "You copied the whole repo. Bold. Legal. Fine." | 10 | yes | shell: `git clone` (exit 0) |
| l1-branch | Branching Out | "Now you have a place to make mistakes safely." | 10 | yes | shell: `git checkout -b` or `git switch -c` (exit 0) |
| l1-diff | Read Before You Commit | "Reviewing your own work. Unheard of." | 10 | yes | shell: `git diff` or `git status` after an edit |
| l1-commit | Commit to the Bit | "Your first commit. Local only; nobody has seen it yet." | 10 | yes | shell: `git commit` (exit 0) |
| l1-push | Pushed It Real Good | "It's on the server now. It's real." | 10 | yes | forgejo: push to a non-`main` branch |
| l1-pr | Pull Request Pending | "Now you wait, like everyone in software." | 10 | yes | forgejo: pull request opened |
| l1-prune | Tidy Desk | "Pruned the stale branches. Marie Kondo would nod." | 10 | yes | shell: `git fetch --prune` or `git fetch -p` |
| l1-cleanup | Deleted Without Regrets | "Safe delete, no drama." | 10 | yes | shell: `git branch -d` (exit 0) |
| l1-merged | Merged, Baby! | "Someone approved your work. Frame it." | 10 | no (needs the facilitator to merge) | forgejo: PR merged |

## Lab 2: reviewing and undoing before you commit

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| l2-restore | The Undo Button | "Ctrl+Z, but it's git." | 10 | yes | shell: `git restore <file>` (exit 0) |
| l2-unstage | Never Mind | "Staged it, regretted it, unstaged it. Growth." | 10 | yes | shell: `git restore --staged` or `git reset` (exit 0) |
| l2-ignore | Ignorance Is Bliss | "Some files are better left unseen." | 10 | yes | shell: a command that writes `.gitignore` |

## Lab 3: stashing

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| l3-stash | Hide the Evidence | "Sweeping uncommitted work under the rug." | 10 | yes | shell: `git stash` (exit 0) |
| l3-pop | Back From the Dead | "Your edit is back. Nobody noticed it was gone." | 10 | yes | shell: `git stash pop` or `git stash apply` (exit 0) |

## Lab 4: investigating history

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| l4-log | Historian | "Reading the group chat of the repo." | 10 | yes | shell: `git log` (exit 0) |
| l4-show | Crime Scene Investigator | "One commit, every detail." | 10 | yes | shell: `git show` (exit 0) |
| l4-blame | The Blame Game | "Someone wrote this line. Now you know who." | 10 | yes | shell: `git blame` (exit 0) |
| l4-compare | Spot the Difference | "Two branches walk into a diff." | 10 | yes | shell: `git diff <a>..<b>` or `git log <a>..<b>` |

## Lab 5: merge conflicts and undoing a change

| ID | Title | Joke | Pts | Core | Trigger |
|---|---|---|---|---|---|
| l5-conflict | Conflict Zone | "Two edits, one line, zero chill." | 10 | yes | shell: `git merge` exits non-zero and leaves a conflict |
| l5-resolved | The Peacemaker | "You picked a side. Or both. Diplomat." | 10 | yes | shell: `git commit` completes a merge (conflict resolved) |
| l5-revert | Time Traveller | "Undid a commit the polite way." | 10 | yes | shell: `git revert` (exit 0) |
| l5-reset | Nuclear Option | "Used reset. Hopefully on purpose." | 10 | yes | shell: `git reset --hard` (exit 0) |

## Funny unlocks (5 points, any time)

| ID | Title | Joke | Pts | Trigger |
|---|---|---|---|---|
| f-wrongdir | Lost in Translation | "fatal: not a git repository. Check your `pwd`." | 5 | shell: any `git` command exits 128 with "not a git repository" |
| f-nothing | Empty Handed | "Nothing to commit. Existential." | 5 | shell: `git commit` exits 1 with nothing staged |
| f-main | Living Dangerously | "You committed straight to `main`. The facilitator saw that." | 5 | shell: `git commit` (exit 0) while on `main` |
| f-detached | Off With Your Head | "Detached HEAD. You're fine. Probably." | 5 | shell: `git checkout <hash>` or `--detach` |
| f-amend | Amend and Pretend | "Rewrote your last commit like it never happened." | 5 | shell: `git commit --amend` (exit 0) |
| f-force | With Great Power | "You tried `--force`. Growth opportunity." | 5 | shell: `git push --force` (or `-f`), any exit |
| f-rejected | Rejected! | "The server said no. It's not personal." | 5 | shell: `git push` exits non-zero, "rejected" |

(The cheating and the "bumped into your neighbour" unlocks are shared across every workshop, so they live with the
module, not here.)

## Challenges (100 points, optional, no steps given)

Each has two hints (25% each) and an answer that scores zero. The check is by outcome, so any way of doing it counts.

**Where they run.** The lab repo `training/sample-training-repo` is shared by the class, so a challenge never merges
into its `main`. When a student opens a challenge, the service creates their own copy, `{user}/challenge-repo` (a
seeded fork owned by that student, with the challenge's planted branches and commits). Pull requests, merges and
`main` below all mean that repo. Merging there is safe: nobody else can see it change.

### C1: The Hotfix (after Lab 1 or 2)

- **Goal shown to the student:** "Production has a typo in `roster/team.yaml`. Ship a fix without touching `main`
  directly. Prove it with a pull request."
- **Constraints:** in `{user}/challenge-repo`; branch named `hotfix-{user}`; the PR changes only `roster/team.yaml`;
  PR title starts with `hotfix:`; the change sets Alice's role to `{role_for_user}` (a per-student value from a fixed
  silly list, e.g. "Chief Snack Officer") so an answer can't be copied.
- **Verify:** forgejo `branch_exists`, `pr_open` or `pr_merged`, `pr_files == [roster/team.yaml]`, `file_contains` on
  the branch. No direct push to `main` (checked from the repo's own history).
- **Hint 1:** "Everything you need is in Lab 1. What do you do before you edit anything?"
- **Hint 2:** "Branch, edit the one line, commit, push, open the PR from Forgejo."
- **Answer:** the command list.
- **Collision check:** own repo, own branch, no merge into a shared `main`. Nothing needs a facilitator.

### C2: The Detective (after Lab 3 or 4)

- **Goal:** "Someone changed a line they shouldn't have. Find the commit that introduced `{target_line}` and tell us its
  short hash and its author. Put both in `answer.txt` on a branch called `case-{user}` and push it."
- **Seed:** planted commits in `{user}/challenge-repo`; `{target_line}` is picked per student from a list, and the
  verifier computes the true answer for that repo with `git log -S` / `git blame`. Each student's history has its
  own hashes, so an answer can't be shared.
- **Verify:** forgejo `file_contains` on `case-{user}` in the student's repo for the right hash and author.
- **Hint 1:** "Which command answers 'who changed this line?'"
- **Hint 2:** "`git blame` on the file, or `git log -S '<text>'` to search history for when a string appeared."
- **Answer:** the two commands and the expected output shape.
- **Collision check:** read-only investigation of a private repo, one new branch.

## Capstone (300 points, optional): The Great Merge

- **Goal:** "Two feature branches, `feature-a` and `feature-b`, both edit the same lines. A third commit on one of them
  broke something. Bring both changes into `main` through a pull request with **both** edits kept, no conflict markers
  left behind, and the broken commit undone the safe way."
- **Seed:** the two conflicting branches and the bad commit are created in the student's own `{user}/challenge-repo`
  (Forgejo user repos, so no branch names need a `{user}` suffix).
- **Verify:** forgejo `pr_merged` into that repo's `main`; `file_contains` both edits and no `<<<<<<<`; history
  contains a revert commit for the bad one.
- **Hints:** (1) "Merge one, then the other; expect a conflict." (2) "`git revert` undoes a commit without rewriting
  history."
- **Collision check:** the merge lands in a private repo, so it can't conflict with anyone. Fully solo; no facilitator.
- **Badge tier:** capstone (stars).

## Rough totals (for scale)

Core milestones ~190 · funny up to ~35 · challenges 200 · capstone 300 · plus first blood and
class-clear bonuses. A student who does everything lands near 750.
