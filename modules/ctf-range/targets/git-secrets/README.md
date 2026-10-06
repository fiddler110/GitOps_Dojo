# Target 8 — `git-secrets`

CTF-3 (plan §7.3 row 8, ties `git-fundamentals`). Unlike every other
attack-ladder target, **there is no bug in this app at all**. The whole
foothold lives outside `ctf_net`, in a Forgejo repo's git history.

## The flaw

A per-student repo (`<student>/internal-tools`, seeded by
`modules/ctf-range/terminal/start.d/55-git-secrets.sh`) has:

1. A commit that adds `deploy.sh` containing `DEPLOY_TOKEN=<token>`.
2. A later commit that "cleans up" `deploy.sh` to read the token from an
   environment variable instead — the token no longer appears anywhere on
   `main`'s current tree.

Deleting a file, or editing it in a later commit, does not revoke what an
earlier commit held: `git log -p` (or Forgejo's own commit/diff view) still
shows the token in the first commit's diff. That's the whole lesson — same
one `git-fundamentals` teaches, now with something to actually recover.

## Escalation

The recovered token is a deploy trigger credential, not the flag itself.
`POST /deploy/trigger` with that token (form field `token`, or header
`X-Deploy-Token`) returns the flag. The check in `app.py` is correct — this
target has nothing to exploit directly; it only accepts a credential that
was never supposed to leave the repo.

## Decoy port (nmap)

Also publishes a decoy SSH listener on container port 2222 (plan §7.3's
nmap primer) — not a real sshd, see `app.py`'s decoy-listener comment.

## Environment

| Var | Meaning | Dev default |
|-----|---------|-------------|
| `CTF_FLAG` | the slot's rendered flag value | `flag{git-secrets-dev…}` |
| `CTF_TARGET_TOKEN` | the exact value planted in this student's git history | `flag{git-secrets-token-dev…}` |
| `PORT` | listen port | `5000` |

Both are rendered generically by `ctf-controller`'s `AttackManager._env_for`
(the same `flags.render` derivation as every other target's `CTF_FLAG`, just
with its own `<target>-token` challenge tag so the two values can never
collide) — no per-target code in the controller.

## Build and run standalone

```sh
cd modules/ctf-range/targets/git-secrets
docker build -t ctf-git-secrets:dev .
docker run --rm -p 5000:5000 \
  -e CTF_FLAG='flag{git-secrets-test}' \
  -e CTF_TARGET_TOKEN='flag{git-secrets-token-test}' \
  ctf-git-secrets:dev
```

## Verify

```sh
# Standalone, skipping the Forgejo step:
python3 exploit/solve.py --url http://127.0.0.1:5000 --token 'flag{git-secrets-token-test}'

# The real path, against a seeded repo:
python3 exploit/solve.py --url http://127.0.0.1:5000 \
  --forgejo-url http://127.0.0.1:3000 --repo student01/internal-tools
```

## Files

- `app.py` — the (deliberately bug-free) token-gated app.
- `exploit/solve.py` — reference solve: recover the token from Forgejo
  history, then trigger the deploy.
- `Dockerfile`, `requirements.txt` — the image.
- The actual vulnerable artifact is the seed repo, built by
  `modules/ctf-range/terminal/start.d/55-git-secrets.sh`, not anything here.
