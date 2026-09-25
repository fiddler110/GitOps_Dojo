# Lab 5 — Merge Conflicts & Safely Undoing a Change

**Optional.** Two topics that go together: what happens when git *can't*
merge automatically, and how to undo something once it's out there —
safely.

Do this from your `git-fundamentals-practice` clone. This lab creates its
own throwaway branches, so it won't interfere with your Lab 1 branch.

---

## Part A — Causing and resolving a conflict

A conflict happens when two branches change the *same line* in different
ways. Normally that's two different people; here, you'll play both parts
yourself so you can see it end to end without needing a partner.

```sh
git checkout main
git checkout -b conflict-a
```

Edit `roster/team.yaml` and change Alice's role — for example:

```yaml
- name: Alice Engineer
  role: Senior Engineer
```

```sh
git add roster/team.yaml
git commit -m "conflict-a: update Alice's role"
git checkout main
git checkout -b conflict-b
```

Now, on this second branch, edit **the same line** to something
different:

```yaml
- name: Alice Engineer
  role: Principal Engineer
```

```sh
git add roster/team.yaml
git commit -m "conflict-b: update Alice's role"
```

Now try to bring both changes together:

```sh
git merge conflict-a
```

Git stops and reports a conflict. Look at the file:

```sh
cat roster/team.yaml
```

You'll see something like:

```yaml
- name: Alice Engineer
<<<<<<< HEAD
  role: Principal Engineer
=======
  role: Senior Engineer
>>>>>>> conflict-a
```

- Everything between `<<<<<<< HEAD` and `=======` is your current
  branch's version.
- Everything between `=======` and `>>>>>>> conflict-a` is the incoming
  branch's version.

**Resolve it:** open the file, decide which version to keep (or combine
them), and delete the `<<<<<<<`, `=======`, `>>>>>>>` markers yourself —
git won't do this part for you. For example, keep just:

```yaml
- name: Alice Engineer
  role: Principal Engineer
```

Then finish the merge:

```sh
git add roster/team.yaml
git commit
```

Git pre-fills a merge commit message — accepting the default is fine. If
you ever want to back out of a conflict entirely and start over:

```sh
git merge --abort
```

(No need to run that now — your merge is already resolved.)

Clean up:

```sh
git checkout main
git branch -D conflict-a conflict-b
```

---

## Part B — Undoing a change safely

The right way to undo something depends on whether anyone else could
already have it.

**Not committed yet:** see [lab2.md](lab2.md) — `git restore`.

**Committed, but not pushed (nobody else has it):** you can rewrite
history freely.

```sh
git checkout -b undo-demo
echo "- name: Oops Entry" >> roster/team.yaml
git add roster/team.yaml
git commit -m "Oops, wrong entry"

# undo the commit, keep the edit staged again:
git reset --soft HEAD~1
git status

# or undo the commit AND throw away the edit entirely:
git reset --hard HEAD~1
git status
```

**Committed *and* pushed (shared with others):** do **not** use
`git reset` here. Rewriting history that someone else may have already
pulled breaks their local repo — on GitHub specifically, it can also
silently drop commits off an open pull request. Use `git revert` instead —
it adds a *new* commit that undoes an earlier one, so history only ever
moves forward. (This demo stays local — no need to actually push it — but
the same command is what you'd run on a real shared branch.)

```sh
echo "- name: Reverted Later" >> roster/team.yaml
git add roster/team.yaml
git commit -m "Example commit to revert"
git log --oneline -1
git revert HEAD --no-edit
git log --oneline -2
```

Notice `git revert` added a new commit on top, rather than erasing the
one before it — that's what makes it safe once something is shared.

Clean up:

```sh
git checkout main
git branch -D undo-demo
```

---

## Recap

- **Conflict:** git marks `<<<<<<<` / `=======` / `>>>>>>>` around the
  disputed lines; you resolve by hand, then `git add` + `git commit`.
  `git merge --abort` bails out entirely if needed.
- **Not committed:** `git restore` (Lab 2).
- **Committed, not shared:** `git reset` is safe — it rewrites your own
  local history.
- **Committed and shared:** `git revert` is safe — it adds a new commit
  instead of rewriting history.

You've now covered the full loop (Lab 1) plus the most common "something
went sideways" tools. That's the everyday git toolkit — see
[README.md](README.md) for the quick reference, and
[cheat-sheet.md](cheat-sheet.md) for the full command list.
