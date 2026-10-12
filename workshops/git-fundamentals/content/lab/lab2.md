# Lab 2 — Reviewing & Undoing Before You Commit

Not everything you type is meant to be kept. This lab is about catching mistakes before they become part of your history: discarding an edit, unstaging a file, and keeping local-only files out of git entirely. Along the way you'll see *why* each undo command works, which is what lets you pick the right one under pressure.

Do this from your `sample-training-repo` clone, on your `add-yourname` branch from Lab 1 (or any branch — nothing here needs to be pushed).

> **Starting here?** This lab needs the sample repo cloned. Run `lab-prep 2` to set that up; it's safe to run even if you did the earlier labs.

---

## In this lab

| Command | What it does |
|---|---|
| `git diff` | Show unstaged changes: working tree compared with the index |
| `git restore <file>` | Discard uncommitted edits: copy index to working tree |
| `git diff --staged` | Show staged changes: index compared with HEAD |
| `git restore --staged <file>` | Unstage a file but keep the edit: copy HEAD to index |
| `.gitignore` | A file of patterns that tells git to ignore untracked files |
| `git check-ignore -v <file>` | Show which rule is ignoring a file |

You'll meet each one when you need it, and the "Your turn" steps expect you to pick the right one from here.

---

## The idea: three places your work can live

Every "undo" in git is really "copy this file from one place to another", so first know the places:

```text
  working tree          index (staging area)         HEAD (last commit)
  the files you    -->  what the NEXT commit    -->  what the branch
  actually edit         will contain                 already contains
        git add               git commit
```

- The **working tree** is the files on disk, the ones your editor opens.
- The **index** (also called the staging area) is a draft of your next commit. `git add` copies a file from the working tree into it.
- **HEAD** is the commit you're sitting on. Commits are permanent and can't be changed by accident.

Keep that picture in mind. Each command below moves a file one step along the arrows, or back.

---

## 1. Make an edit you don't want

```sh
echo "- name: Test Entry" >> roster/team.yaml
git status
git diff
```

`git status` lists `roster/team.yaml` as modified, and `git diff` shows exactly what changed: the working tree compared with the index. Right now the index and HEAD are identical, so this edit exists in **one place only**: the working tree.

Suppose you decide this edit was a mistake and you want the file back exactly as it was.

Git's tool for this is **`git restore`**. It copies a file from one place into another, overwriting what was there. With no options it copies **from the index into the working tree**, which means "put this file back the way git has it".

```text
git restore <file>
```

**Your turn:** use `git restore` on `roster/team.yaml`, then run `git status` to confirm. Before you run it, predict: which of the three places gets overwritten, and what happens to your `Test Entry` line?

<!-- dojo-reveal: Show the command and why it works -->
```sh
git restore roster/team.yaml
git status
```

The working tree is the place that gets overwritten. Because nothing was staged, the index still held the committed version, so your file snaps back, the `Test Entry` line is gone, and `git status` is clean.

**This is destructive.** The discarded edit was only ever in the working tree, and git never saw it as a commit or a staged blob, so there is nothing to recover it from. Use it only when you're sure.
<!-- /dojo-reveal -->


---

## 2. Stage something, then change your mind

```sh
echo "- name: Another Test" >> roster/team.yaml
git add roster/team.yaml
git status
git diff
git diff --staged
```

`git status` now shows the file under "Changes to be committed". Notice the two diffs:

- `git diff` is **empty**: the working tree and the index match.
- `git diff --staged` shows the change: the index differs from HEAD.

So the edit now lives in two places (working tree and index). Staging and committing are two separate decisions, and you've made only the first.

Now you want the file **out of the next commit**, but you want to keep your edit on disk. `git restore` can do this too, with a flag that changes its destination:

```text
git restore --staged <file>
```

`--staged` makes it write into the **index** instead of the working tree, copying from **HEAD**. So it resets the draft of your next commit for that file and never touches the file on disk.

**Your turn:** unstage `roster/team.yaml`. Before you run it, predict what `git diff` and `git diff --staged` will show afterwards, and whether the `Another Test` line is still in the file.

<!-- dojo-reveal: Show the command and what you should see -->
```sh
git restore --staged roster/team.yaml
git status
git diff
git diff --staged
```

`git status` lists the file as "not staged for commit" again. `git diff` shows the `Another Test` line (the edit is still in your working tree), and `git diff --staged` is now empty (the index matches HEAD again).

Compare the two forms, because they are easy to mix up:

| Command | Copies from | Copies to | Your edit |
|---|---|---|---|
| `git restore <file>` | index | working tree | **lost** |
| `git restore --staged <file>` | HEAD | index | kept |
<!-- /dojo-reveal -->

Clean up before moving on:

```sh
git restore roster/team.yaml
```

**Check yourself:** if you stage an edit with `git add`, then edit the same file again, which of the three places hold which version? What would `git restore <file>` throw away now?

<!-- dojo-reveal: Show the answer -->
All three differ: HEAD has the committed version, the index has the first edit, and the working tree has the first edit plus the second. `git restore <file>` copies from the index, so it discards only the **second** edit and leaves the staged first one in place. `git status` will list the file twice, once staged and once not staged, which is how you can tell.
<!-- /dojo-reveal -->

---

## 3. Keep local-only files out of git

Not every file that shows up in `git status` should be committed: build output, editor settings, local secrets. `.gitignore` is how you tell git to leave them alone.

A `.gitignore` is a plain text file, usually at the top of the repo, with one pattern per line. Git treats any untracked file that matches a pattern as if it didn't exist:

```text
# a comment goes on its own line
*.log
build/
.env
!keep.log
```

`*.log` matches any file ending in `.log`, `build/` matches a whole directory, `.env` matches one specific file, and a leading `!` makes an exception to an earlier rule.

A few things worth knowing:

- Patterns are matched relative to the folder holding the `.gitignore`, and one in a subfolder applies to that folder and below.
- The `.gitignore` file is committed like any other, so the whole team shares the same rules. For personal rules that shouldn't be shared (your editor's temp files, say), use `.git/info/exclude`, which works the same way but is never committed.
- Ignored files stay on disk. Git just stops listing them and stops `git add .` from sweeping them in by accident, which is the most common way secrets and junk end up in a repo.

Create a file that shouldn't be committed:

```sh
touch scratch.log
git status
```

`scratch.log` shows up as untracked.

**Your turn:** make git ignore every `.log` file, then confirm with `git status` that `scratch.log` has gone. What do you expect `git status` to list instead?

<!-- dojo-reveal: Show the command and what you should see -->
```sh
echo "*.log" >> .gitignore
git status
```

`scratch.log` disappears, but `.gitignore` itself appears as a new untracked file. That's correct: the rule is a file in the repo, and you'd commit it so that everyone who clones gets the same rule. To see *why* a file is ignored, ask git: `git check-ignore -v scratch.log` prints the file and line of the matching rule.
<!-- /dojo-reveal -->

Clean up (this is a throwaway exercise, not something to commit):

```sh
rm scratch.log .gitignore
git status
```

**Check yourself:** a teammate committed `config.env` last week, then added `config.env` to `.gitignore`. It's still showing as modified when they edit it. Why, and does the `.gitignore` entry protect the secret inside?

<!-- dojo-reveal: Show the answer -->
`.gitignore` only affects **untracked** files. Once a file has been committed, git tracks it and keeps reporting changes regardless of the ignore rule. To stop tracking it you'd run `git rm --cached config.env` and commit that, and the file stays on disk.

That still doesn't protect the secret: it remains in every earlier commit, which anyone who cloned the repo already has. If a secret was ever committed, treat it as exposed and rotate it. Adding it to `.gitignore` afterwards is not a fix.
<!-- /dojo-reveal -->

---

## Recap

- Files live in three places: the **working tree**, the **index**, and **HEAD**. `git add` moves a change from the first to the second, and `git commit` from the second to the third.
- `git diff` compares working tree to index; `git diff --staged` compares index to HEAD.
- `git restore <file>` — copies index to working tree: discards uncommitted edits.
- `git restore --staged <file>` — copies HEAD to index: unstages, keeping your edit.
- `.gitignore` — keeps new, untracked files out of `git status` and `git add .`; it does nothing for files already committed.

**Next:** [lab3.md](lab3.md) — stashing, for when you need to switch branches mid-edit.
