# Lab 1 — The Core Workflow

By the end of this lab you'll have personally cloned a repo, created a branch, made and committed a change, pushed it, and opened a pull request. This is the loop you'll use for most of your day-to-day git work — see the table in [README.md](README.md) if you want the one-line summary of each step first.

---

## 1. Clone the sample repo

Use the internal Forgejo URL from inside this terminal:

```sh
git clone http://git-server:3000/training/sample-training-repo.git
cd sample-training-repo
```

`clone` downloads the whole repository — every commit, every branch — to your machine. You now have a full local copy; you don't need the network to look at history or make commits, only to share them.

---

## 2. Create a branch

Replace `yourname` with your name:

```sh
git checkout -b add-yourname
```

This creates a new branch pointing at the same commit as `main`, and switches you onto it. Anything you commit now happens on `add-yourname`, not `main` — so there's no way to break anything anyone else is working on. Naming the branch after what it's for (or who it's for) helps everyone else understand it at a glance.

---

## 3. Edit the roster

Open `roster/team.yaml` and add yourself to the team list:

```yaml
- name: Your Name
  role: Your Role
```

Pick whichever of these suits you. All three give the same result.

### Option 1: your editor (recommended)

Open `sample-training-repo/roster/team.yaml` in your editor, add your entry at the bottom, and save with `Ctrl+S`
(`Cmd+S` on a Mac in VS Code). Keep the same indentation as the entries above yours.

- **Terminal workspace** (a file list on the left of your terminal): run `e roster/team.yaml`. It opens a simple
  editor in a floating pane: paste or type, `Ctrl+S` saves, `Ctrl+Q` quits.
- **VS Code:** open the file from the explorer on the left.

### Option 2: nano, in the terminal

```sh
nano roster/team.yaml
```

This opens the roster file in nano, a beginner-friendly terminal text editor. Use the arrow keys to move to the
bottom of the file, then add your entry. To save and exit, press `Ctrl+O` (write out), `Enter` (keep the file
name), then `Ctrl+X` (exit).

### Option 3: append with `cat`

Replace the name and role, then paste the whole command:

```sh
cat >> roster/team.yaml <<'EOF'
- name: Your Name
  role: Your Role
EOF
```

- `>> roster/team.yaml` appends the lines to the end of the file (a single `>` would overwrite it).
- `<<'EOF'` starts the pasted block of text, and the final `EOF` ends it.

After editing, read the file to make sure your entry is there:

```sh
batcat roster/team.yaml
```

`batcat` prints the file with line numbers and syntax highlighting, which makes it easier to confirm your YAML still looks right.

---

## 4. Review your change

```sh
git status
git diff
```

- `git status` shows *which* files changed — right now, `roster/team.yaml` should be listed as modified, and nothing else.
- `git diff` shows *exactly what* changed, line by line, before you commit it. Get in the habit of reading this before every commit — it catches typos and accidental edits early.

---

## 5. Stage and commit

```sh
git add roster/team.yaml
git commit -m "Add Your Name to team roster"
```

- `git add` moves your change into the **staging area** — a holding pen for exactly what you want in the next commit. If you had touched other files you didn't mean to change, you could leave them unstaged.
- `git commit` saves a permanent snapshot of everything staged, along with a message. A good commit message says *what* changed and, if it's not obvious, *why* — future-you (and your reviewer) will thank you.

Check it landed:

```sh
git log -1
```

---

## 6. Push

Try just a simple `git push` now and see what git tells you. 

Your local branch doesn't exist on the remote repository, so you need to push the current branch and set the remote as *upstream* for it to be added to the repo.

```sh
git push -u origin add-yourname

# or the more verbose 
git push --set-upstream origin <branch>
```

This uploads your branch and its commit to the shared Forgejo server. Until this point, everything you did was entirely local — nobody else could see it. `-u origin add-yourname` also remembers this branch's remote, so future pushes from this branch just need `git push`.

Git didn't ask for a password. Your terminal came with a Forgejo **access token** for your account, saved in `~/.git-credentials`; git's `store` helper (set in your `~/.gitconfig`) sends it with every push. Look at the file:

```sh
ls -l ~/.git-credentials
```

```text
-rw------- 1 studentXX studentXX 74 ... /home/studentXX/.git-credentials
```

`-rw-------` (mode `0600`) means only you can read it. Anyone who has the token can push as you, so it must not be readable by the other accounts on this machine. It is also narrow: it works on repositories and pull requests, but it can't change your account settings or sign in to the Forgejo web page.

---

## 7. Open a pull request

Go back to the workshop landing page (the tab or window where you opened your terminal) and click **Open Forgejo**. It opens a new tab, already signed in as you — no separate login.

Find your `add-yourname` branch (Forgejo usually prompts you with a banner offering to open a pull request for a recently-pushed branch) and open a pull request into `main`. Sensei, the class review bot, looks at it within a few seconds and, if your roster entry follows the format, rubber-stamps it and merges it for you. If something is off, Sensei leaves a comment saying what and flags your facilitator, who will take a look.

---

## 8. Clean up after your branch is merged

Once Sensei (or, if it flagged your PR, the facilitator) merges your pull request, `add-yourname` has done its job — the change lives on `main` now. Your local copy doesn't know that yet, though. Switch back to `main` and bring it up to date:

```sh
git checkout main
git pull
```

Now tell git to notice that the branch is gone from the server:

```sh
git fetch --prune
```

Forgejo deletes the remote branch as soon as a PR merges (this repo is configured that way), but your local clone still remembers a *remote-tracking* branch called `origin/add-yourname` pointing at it — `git fetch --prune` (or the shorthand `git fetch -p`) removes remote-tracking branches whose remote counterpart no longer exists. Without it, `git branch -a` would keep showing `origin/add-yourname` indefinitely, long after it's actually gone.

`--prune` only cleans up *remote-tracking* branches. Your own local `add-yourname` branch is still sitting there, so delete it too:

```sh
git branch -d add-yourname
```

`-d` is the safe delete: git checks that the branch is fully merged into your current branch first and refuses if it isn't (use `-D` to force it — but only once you're sure you don't need those commits). Confirm it's gone:

```sh
git branch
```

Make `git fetch --prune` a habit at the start of every work session — it keeps your local branch list matching what's actually on the server, so you're never guessing whether a branch you see locally still means anything.

---

## 9. When you commit on the wrong branch

Step 2 was "create a branch" — and sooner or later everyone forgets it, edits away, commits, and only then notices
the prompt still says `main`. Nothing is broken and nothing is lost: the fix is three short steps, and it's worth doing
once now, deliberately, so you recognise it later.

You're on `main` and up to date from step 8, which is exactly where the mistake starts. Make it on purpose:

```sh
git status                      # confirms: On branch main
echo "# Notes from the workshop" > notes.md
git add notes.md
git commit -m "Add workshop notes"
git log --oneline -2
```

That commit is sitting on your local `main`, where it doesn't belong. (If your class has achievements on, this is the
one and only time the lab tells you to earn **Living Dangerously** — and there's a second one waiting for you once
you've put `main` back.)

### Why nothing is lost

A branch in git is just a **label pointing at a commit** — it is not a container holding your work. Your commit
exists on its own; `main` merely happens to point at it. So you don't need to move the commit anywhere. You add a
second label, then move `main` off it.

### Step 1: label the commits before you touch anything

```sh
git branch notes-yourname
git log --oneline --graph --decorate -2
```

```text
* 4f1c2ab (HEAD -> main, notes-yourname) Add workshop notes
* 9cc890c (origin/main) Add Your Name to team roster
```

`git branch <name>` (no `-b`, no `checkout`) creates the label at your current commit **without switching you onto
it** — that's what `HEAD ->` points at. `--decorate` is what prints the names in brackets, and they are the whole
point here: one commit with two labels on it, and `origin/main` still back where the server is. Your commit is now
safe whatever happens to `main` next.

Do this first, always. The label is the safety net, so it goes in *before* the destructive command, not after.

### Step 2: move `main` back to where the server has it

```sh
git fetch
git reset --hard origin/main
git log --oneline --graph --decorate -2
git status
```

`origin/main` is your local record of what the server's `main` looked like at your last `fetch` — so `git fetch`
first, to make sure that record is current. `git reset --hard origin/main` then moves your `main` to exactly that
commit and makes your working directory match it. Your accidental commit is no longer on `main`; `notes.md` is gone
from the working directory, and `git status` is clean.

You'll often see this written as `git reset --hard HEAD~1` instead ("one commit before where I am"), and that works
too — but it makes you count. Two accidental commits need `HEAD~2`, three need `HEAD~3`, and `--hard` with the wrong
number silently throws away work you meant to keep. Resetting to `origin/main` says "match the server" and needs no
arithmetic, so prefer it whenever the branch tracks a remote.

`--hard` also discards *uncommitted* edits in your working directory, with no confirmation and no undo. If you have
any, commit or stash them ([lab3.md](lab3.md)) before you reset.

### Step 3: switch to your branch and carry on

```sh
git checkout notes-yourname
git log --oneline -2
batcat notes.md
```

There's your commit, and there's `notes.md` back in your working directory — on a branch this time. From here it's
the normal loop again: push with `-u`, open a pull request.

### Already pushed to the wrong branch?

Then stop and don't use `git reset`. Rewriting a branch other people have pulled breaks their clone — and in most
real repositories `main` is protected, so the force-push it would need is refused anyway. Use `git revert` on the
shared branch instead: [lab5.md](lab5.md) covers it. The question is never "is it committed", it's **"has anyone
else already got it"**.

Clean up this exercise before moving on:

```sh
git checkout main
git branch -d notes-yourname
```

`-d` refuses, exactly as described in step 8 — your commit was never merged into `main`, which is the whole point of
this exercise. You're sure you don't need it, so force it:

```sh
git branch -D notes-yourname
git branch
```

> **If you ever lose track of a commit**, it is almost certainly still there. `git reflog` lists every commit `HEAD`
> has pointed at recently, including ones no branch points to any more, and `git checkout -b rescue <hash>` brings
> one back. Ask your facilitator rather than trying more commands blind.

---

## Checkpoint

Before moving on, be ready to show or say:

- Your current branch (`git status`).
- Your latest commit (`git log -1`).
- The URL of your pull request.
- In your own words: what changed locally at `git commit`, and what changed remotely at `git push`?
- What `git fetch --prune` cleaned up, and why `git branch -d` refuses to delete an unmerged branch.
- Why a commit made on the wrong branch is never lost, and which of the three rescue commands is the
  destructive one.

**Next:** [lab2.md](lab2.md) — reviewing and undoing changes before you commit.

---

## Challenge c1: The Hotfix (bonus)

Production has a typo: your own role in `roster/team.yaml` is misspelled. Ship the fix without touching `main`
directly.

Only when your class has achievements on (you see a score on your landing page). Start it in the terminal:

```sh
dojo-challenge start c1
cd ~/lab/challenge-repo
```

That makes your own repo `$USER/challenge-repo` and clones it to `~/lab/challenge-repo`, and prints the goal, with your own names in it. When you think it's done:

```sh
dojo-check c1
```

A wrong answer costs nothing. `dojo-check hint c1` gives a hint for part of the points, and
`dojo-challenge reset c1` throws the repo away and starts you over from a fresh copy.

<!-- dojo-challenge: c1 -->
