# Lab 1 — The Core Workflow

By the end of this lab you'll have personally cloned a repo, created a branch, made and committed a change, pushed it, and opened a pull request. This is the loop you'll use for most of your day-to-day git work — see the table in [README.md](README.md) if you want the one-line summary of each step first.

---

## In this lab

| Command | What it does |
|---|---|
| `git clone <url>` | Copy a remote repo, with its whole history, to your machine |
| `git checkout -b <name>` | Create a branch and switch to it |
| `git status` | Show which files are modified, staged or untracked |
| `git diff` | Show the exact lines you changed |
| `git add <file>` | Stage a change for the next commit |
| `git commit -m "msg"` | Save the staged changes as a commit |
| `git log -1` | Show your latest commit |
| `git push -u origin <branch>` | Upload the branch and remember its remote |
| `git pull` | Bring the remote's new commits into your branch |
| `git fetch --prune` | Forget remote-tracking branches deleted on the server |
| `git branch -d <name>` | Delete a merged local branch |

Later labs say "your turn" and leave the command to you. The [cheat sheet](cheat-sheet.md) has a map of every command in the course, with the lab that teaches it.

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

**Check yourself:** `git add` and `git commit` are two separate steps. Run `git status` after `git add` but before `git commit` the next time you do this: what would it show you, and what's different about it afterwards?

<!-- dojo-reveal: Show the answer -->
Between the two, `git status` lists the file under **"Changes to be committed"**: it's staged, in the draft of your next commit, but not yet part of history. After `git commit` the tree is clean ("nothing to commit"), and the change is a commit you can see in `git log`. Staging is the step where you choose *what* goes into a commit; committing is the step that records it.
<!-- /dojo-reveal -->

---

## 6. Push

Everything so far has been local: nobody else can see your branch or your commit. `git push` is the command that sends them to the shared server.

**Your turn:** run a plain `git push` and read what git tells you. It will refuse. Work out why from the message, and from what you know about where this branch exists.

<!-- dojo-reveal: Show why it fails and the fix -->
Your branch exists only on your machine, so git has no remote branch to send it to and doesn't know what to call it there. The error even prints the fix:

```sh
git push -u origin add-yourname

# or the more verbose
git push --set-upstream origin add-yourname
```

This uploads your branch and its commit to the shared Forgejo server. `origin` is the name git gave the remote you cloned from, and `-u` records "this local branch tracks that remote branch", so from now on a plain `git push` from this branch just works.
<!-- /dojo-reveal -->

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

## Checkpoint

Before moving on, be ready to show or say:

- Your current branch (`git status`).
- Your latest commit (`git log -1`).
- The URL of your pull request.
- In your own words: what changed locally at `git commit`, and what changed remotely at `git push`?
- What `git fetch --prune` cleaned up, and why `git branch -d` refuses to delete an unmerged branch.

<!-- dojo-reveal: Check your answers -->
- **At `git commit`:** a new commit was added to your local `add-yourname` branch. Only your machine changed.
- **At `git push`:** the Forgejo server received the branch and the commit, so now others can see them (and open a pull request).
- **`git fetch --prune`:** removed your local record of `origin/add-yourname` once the server's copy was deleted.
- **`git branch -d` refuses unmerged branches** so you can't throw away commits that exist nowhere else by accident; `-D` overrides it when you mean it.
<!-- /dojo-reveal -->

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
