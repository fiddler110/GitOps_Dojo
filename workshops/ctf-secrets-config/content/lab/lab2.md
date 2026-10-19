# Lab 2: Deploy trigger (`git-secrets`)

By the end of this lab you'll have recovered a secret from a git repository that, right now, doesn't
contain it at all -- and used it to trigger a deploy you were never handed credentials for.

---

## The briefing

There's no target to scan for this one. Instead, you already have your own `internal-tools` repository in
Forgejo -- the same one your team actually uses. Somewhere in it is the credential a deploy service
expects, even though nobody would hand it to you on request. There's also a deploy-trigger service running
on the Attack Range, under the id `git-secrets`, in case you want to check your work against the real
thing once you have something to try.

## 1. Look at the repo as it is today

Open your `internal-tools` repo in Forgejo (or `git clone`/`git pull` it in your terminal) and look at
`deploy.sh`. Read it carefully: does it contain a secret right now, or does it read one from somewhere
else (an environment variable)?

If the file itself holds nothing today, that doesn't mean nothing was ever there.

## 2. Look at the repo as it used to be

A file's current contents are only the most recent chapter. Git keeps every chapter, and `git log` can show
you a commit's full diff, not just its message -- the `-p` ("patch") flag:

```sh
git log -p -- deploy.sh
```

You should see more than one commit touching this file. One of them added something as a plain `+` line in
its diff; a later one took it back out (or swapped it for an environment-variable read). Deleting a file in
a later commit, or editing it to no longer contain the secret, does not remove that earlier diff from
history. (Forgejo's own web UI shows the same thing: open the repo, click **Commits**, and open the diff for
the commit that first added the file.)

> **Hint.** Skimmed past it? `git log --oneline -- deploy.sh` first, to see how many commits touched the
> file at all, then come back to `-p` on the one that looks like it added something.

## 3. Use it

Start the `git-secrets` target from the **Attack Range** card and note your slot's IP. The token you found
is a deploy credential, not the flag itself -- it's accepted by one endpoint, as either a form field or a
header:

```sh
curl -s -X POST http://<your-slot-ip>:5000/deploy/trigger -d "token=<recovered-token>"
# or:
curl -s -X POST http://<your-slot-ip>:5000/deploy/trigger -H "X-Deploy-Token: <recovered-token>"
```

The check on that endpoint is correct -- there's no bug to find there. The only way in is already having
read the token out of history.

## 4. Submit

```sh
dojo flag '<flag>'
```

## Debrief

The secret was never in the current file, yet it was recoverable, because git is an append-only record:
removing a line in a later commit adds a new commit and leaves the old diff untouched, in every clone
and fork. The real-world fix is to treat the secret as burned the moment it was committed: revoke and
rotate it first, then (optionally) rewrite history, and keep secrets out of repositories with
environment injection, a vault, and a pre-commit or CI secret scanner. It has no clean home in the OWASP Top 10, but
hardcoded and leaked credentials (CWE-798) are one of the most common routes to a real compromise. The
`git-fundamentals` workshop teaches the history model that makes this possible.

Reflect: if a teammate pushed a token yesterday and deleted it today, what is the first thing you
would do, and in what order?

## Still stuck?

Read [exploit-guide/git-secrets.md](exploit-guide/git-secrets.md) for the full walkthrough -- try the
hints above for real first.
