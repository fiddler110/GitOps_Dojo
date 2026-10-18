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

## What a job can reach

Two facts about CI that the rest of this lab leans on:

- **A job is handed a token.** Every job gets an automatic `secrets.GITHUB_TOKEN`, scoped to its own
  repository. What it may do depends on the workflow's `permissions:` block, and it cannot push to a branch
  on this server. Forgejo's API is at `http://git-server:3000/api/v1`, and `GITHUB_REPOSITORY` and
  `GITHUB_EVENT_PATH` in the job's environment tell a step which repo and which pull request it belongs
  to. Posting a comment on a pull request is an API call like any other.
- **Logs are masked.** The job log replaces any secret's exact value with `***`. That is a string match on
  the value, so output that no longer contains that exact string is not masked.

A step that wants to get a value out of a job has those two channels: the log, and a call back to the API.

> **Hint 1.** A `pull_request` trigger on most CI systems, Forgejo included, runs the workflow file from the
> *source* branch of the PR, not the target. If you can edit that file on a branch, you decide what the job
> does, before anyone reviews it.

> **Hint 2.** Once your own branch's job runs, it's an ordinary shell step with the repo's secrets
> available to it. You don't need write access anywhere else, only a way to get a value back out of the
> job and into something you can read. Which of the two channels above can you read from your terminal?

## 2. Try the escalation too, and expect it to fail

The same PR's workflow can also try to look around the runner for anything another job left behind: its own
user, its home directory, running processes. Add a step that checks. It's meant to come back empty, and
that's the finding, not a bug -- read `modules/runner-pool/README.md` for why.

## 3. Submit

Once you have the flag out of the job and somewhere you can read it:

```sh
dojo flag '<flag>'
```

## 4. Debrief

What made this possible wasn't a weak check anywhere -- the lint step, the token, the runner itself all
behaved exactly as designed. It's that *the workflow file is also attacker-reachable input* the moment a PR
can carry it. What would have stopped this? (Requiring review before a modified workflow can run; the
narrowest possible token scope for a job; never storing a secret a workflow doesn't need in the same repo.)

## Still stuck?

Read [exploit-guide/runner-escape.md](exploit-guide/runner-escape.md) for the full walkthrough -- try the
hints above for real first.
