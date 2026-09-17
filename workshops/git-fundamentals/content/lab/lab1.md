# Lab 1 — The Core Workflow

**Required.** By the end of this lab you'll have personally cloned a repo, created a branch, made and committed a change, pushed it, and opened a pull request. This is the loop you'll use for most of your day-to-day git work — see the table in [README.md](README.md) if you want the one-line summary of each step first.

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

Use the editor method unless the facilitator tells you otherwise. The copy-paste method is available if editing in the terminal is getting in the way of learning the Git workflow. If you're in VS Code, you can also just click `roster/team.yaml` in the file explorer and edit it normally — the Nano/Vim instructions below are for the plain-terminal path.

### Recommended: Nano

```sh
nano roster/team.yaml
```

This opens the roster file in Nano, a beginner-friendly terminal text editor. Use the arrow keys to move to the bottom of the file, then add your entry.

To save and exit:

```text
Ctrl+O
Enter
Ctrl+X
```

- `Ctrl+O` means "write out". It saves the file.
- `Enter` accepts the current file name, `roster/team.yaml`.
- `Ctrl+X` exits Nano and returns you to the shell.

### Fallback: Copy-paste append

Replace the name and role, then paste the whole command:

```sh
cat >> roster/team.yaml <<'EOF'
- name: Your Name
  role: Your Role
EOF
```

- `cat` reads the lines you paste.
- `>> roster/team.yaml` appends those lines to the end of the roster file.
- `<<'EOF'` starts a pasted block of text.
- The final `EOF` ends the pasted block.

### Optional: Vim

Use this if you already know Vim or want to try it:

```sh
vim roster/team.yaml
```

This opens the roster file in Vim, a powerful terminal editor with different modes.

Press these keys:

```text
G
o
Esc
:wq
Enter
```

- `G` jumps to the bottom of the file.
- `o` opens a new line below the current line and switches into insert mode so you can type.
- `Esc` leaves insert mode and returns to command mode.
- `:wq` means "write and quit". It saves the file and exits Vim.
- `Enter` runs the `:wq` command.

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

You will need to authenticate your git session to the git-server here and will see a popup at the top of your screen in VS Code for your `username `and then `password`, or a `username for 'http://git-server:3000':` prompt in the ttyd.

Use your student account with password `student123`.

```sh
# Ex. If you look at your terminal, your username is your student user id or use whoami
student01@952724d621d6 ~/lab/sample-training-repo/roster
$ git push

# Or

student01@952724d621d6 ~/lab/sample-training-repo/roster
$ whoami
student01
```

Your local branch doesn't exist on the remote repository, so you need to push the current branch and set the remote as *upstream* for it to be added to the repo.

```sh
git push -u origin add-yourname

# or the more verbose 
git push --set-upstream origin <branch>
```

This uploads your branch and its commit to the shared Forgejo server. Until this point, everything you did was entirely local — nobody else could see it. `-u origin add-yourname` also remembers this branch's remote, so future pushes from this branch just need `git push`.

---

## 7. Open a pull request

Go back to the workshop landing page (the tab or window where you clicked **Open VS Code** or **Open Terminal**) and click **Open Forgejo**. It opens a new tab, already signed in as you — no separate login.

Find your `add-yourname` branch (Forgejo usually prompts you with a banner offering to open a pull request for a recently-pushed branch) and open a pull request into `main`. The facilitator will review and merge it.

---

## 8. Clean up after your branch is merged

Once the facilitator merges your pull request, `add-yourname` has done its job — the change lives on `main` now. Your local copy doesn't know that yet, though. Switch back to `main` and bring it up to date:

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

**Next:** Labs 2-5 in [README.md](README.md) are optional deep dives — pick whichever sounds most useful, or work through them in order.
