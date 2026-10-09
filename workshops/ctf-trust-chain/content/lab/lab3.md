# Lab 3: CI pipeline (`runner-escape`)

By the end of this lab you'll understand why a CI secret that "nothing reads" still isn't safe, and you'll
see a real runner boundary hold.

---

## The briefing

There's no target to scan. You already have your own `ci-pipeline` repository in Forgejo: a normal workflow
that lints the code on every push to `main`, plus one Actions secret, `CTF_FLAG`, that workflow never
touches. Jobs run on a shared `runner-pool` runner -- the same machines run every student's pipeline.

The question this lab asks: if a workflow file itself is something you can change, is a secret sitting next
to it in the same repo actually out of your reach?

## 1. Read before you touch anything

Open `.forgejo/workflows/ci.yml` and the repo's README. Which events trigger a run? What does Forgejo run
when a pull request is the trigger -- the workflow file as it exists on the branch being merged *into*, or
the one on the branch the PR comes *from*? That's the question this whole lab turns on.

> **Hint 1.** A `pull_request` trigger on most CI systems, Forgejo included, runs the workflow file from the
> *source* branch of the PR, not the target. If you can edit that file on a branch, you decide what the job
> does, before anyone reviews it.

> **Hint 2.** Once your own branch's job runs, it's an ordinary shell step with the repo's secrets available
> to it. You don't need write access anywhere else -- only a way to get a value back out of the job and into
> something you can read. Forgejo's own API is reachable from inside the job with the token every run is
> handed; check what that token is allowed to post, and remember secrets get masked in raw log output, so a
> value you want to actually read needs to leave in a form the masking won't catch (not plaintext in a log
> line).

## 2. Try the escalation too, and expect it to fail

The same PR's workflow can also try to look around the runner for anything another job left behind: its own
user, its home directory, running processes. Add a step that checks. It's meant to come back empty, and
that's the finding, not a bug -- read `modules/runner-pool/README.md` for why.

## 3. Submit

Once you have the flag out of the job and somewhere you can read it:

```sh
dojo-flag submit runner-escape '<flag>'
```

## 4. Debrief

What made this possible wasn't a weak check anywhere -- the lint step, the token, the runner itself all
behaved exactly as designed. It's that *the workflow file is also attacker-reachable input* the moment a PR
can carry it. What would have stopped this? (Requiring review before a modified workflow can run; the
narrowest possible token scope for a job; never storing a secret a workflow doesn't need in the same repo.)

## Still stuck?

Read [exploit-guide/runner-escape.md](exploit-guide/runner-escape.md) for the full walkthrough -- try the
hints above for real first.
