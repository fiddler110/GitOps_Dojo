# Target 10 — `runner-escape`

CTF-4 (plan §7.3 row 10, GitOps, needs `runner-pool`). **No image** — same
shape as `tfstate-treasure` (11): the foothold is a Forgejo repo and a CI
job, not a container in `ctf-host`. This directory is docs + a reference
exploit; provisioning lives in
`workshops/ctf-defend-test/compose/terminal/start.d/96-runner-escape.sh`
(web-terminal, this pack only — new/unproven outside this harness, same
scoping reasoning as `tfstate-treasure` needing `openbao`).

## The flaw

Every student gets their own `<student>/ci-pipeline` Forgejo repo with a
normal CI workflow on `main` (`.forgejo/workflows/ci.yml`: checkout + lint,
touches no secret) and one Actions secret, `CTF_FLAG`, that workflow never
reads.

Forgejo's `pull_request` trigger runs the **PR branch's** version of the
workflow file, not `main`'s — proven live in this codebase already
(`defend-pr.yml`, target 14, runs on `pull_request` with
`secrets.CTF_FLAG` injected, part of the CTF-5 defend loop and
live-verified end to end). So a student who opens a PR against their *own*
repo with an edited `ci.yml` gets arbitrary shell code executed on a shared
`runner-pool` runner — "a workflow in a fork runs attacker-controlled
code on a shared runner" (plan row 10's foothold), the same mechanism as a
real contributor's fork PR, just without a separate fork in this
single-tenant layout. That code can read `secrets.CTF_FLAG` (same
`pull_request`-with-secrets path `defend-pr.yml` already relies on) and the
implicit `secrets.GITHUB_TOKEN` (confirmed present on every job, 40 chars,
`docs/archive/REMEDIATION-PLAN.md` T0.3).

**Exfil channel — a PR comment, not a file write.** On this pinned Forgejo
the auto-issued `GITHUB_TOKEN` is blocked by the branch pre-receive hook
from pushing to *any* branch (`User 'forgejo-actions' is not allowed to
push`), so the obvious "write the flag to a file on the branch" route is a
dead end. The token *can* post a PR comment, though, so the injected step
base64-encodes the flag and posts it as a comment on its own PR (prefixed
with a marker); the solve reads it back with an ordinary comments-API call.
No job-log API needed. The edited workflow grants itself
`permissions: write-all` so the token can comment — one more thing the PR
branch's workflow controls.

This target deliberately never uses `pull_request_target` — T0.3 left its
reliability on this pinned Forgejo version inconclusive and it was never
resettled; `pull_request` alone is sufficient for this foothold and is
already proven (both here and by `defend-pr.yml`), so `runner-escape`
doesn't carry that open risk (`docs/CTF-SPIKES.md`).

## Escalation (expected to fail — that's the lesson)

Plan row 10: "read another job's leftover state; expected to fail, which is
the point." `runner-pool` gives every job its own Linux user and PID
namespace and deletes everything the job left behind the moment it exits
(`modules/runner-pool/README.md`) — so a second step in the same malicious
PR that records `id`, `ls -la /home`, `ls -la /tmp` and `ps aux` and posts
them as another PR comment comes back showing only *this* job's own user
(e.g. `uid=20005`), another runner's home present but `drwx------` and
unreadable, and `ps aux` holding only this job's own process tree — nothing
from any other student's or any earlier job's run. There is no second flag:
the dead end is the debrief ("why runners are single-use"). Live-verified
exactly this way on 2026-10-06.

## Verify

Run from inside the student's own terminal account — `git-server` is
reachable directly there, the same way every other no-image target in this
range reaches Forgejo.

```sh
python3 exploit/solve.py --repo student01/ci-pipeline --user student01
```

Reads the current `ci.yml`, opens a branch + PR with an added step that
posts `secrets.CTF_FLAG` (base64, marker-prefixed) as a PR comment using
`secrets.GITHUB_TOKEN`, and a second step that posts an `id`+`/home`+`/tmp`
+`ps aux` probe as another comment; polls the PR's comments, decodes the
flag comment and prints the probe comment (expected to show nothing but this
job's own, freshly-created user).

## Files

- `exploit/solve.py` — reference open-a-PR-and-read-the-leak solve.
