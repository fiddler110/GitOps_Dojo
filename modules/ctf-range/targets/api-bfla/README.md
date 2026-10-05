# Target 13 — `api-bfla`

CTF-2 "Server-side trust and APIs" (plan §7.3 row 13). API-only — OWASP API
Security Top 10 API5:2023 Broken Function Level Authorization. No HTML
anywhere; drive it with `curl`/`httpie`/`jq`.

## The flaw

`POST /admin/reset-all` checks only that the bearer token is *valid* — it
never checks the token's role is `facilitator` (a role nothing here ever
issues; every login gets `student`). The fix (written as a comment in
`app.py` right above the vulnerable line) is one extra check:
`role == "facilitator"`.

## Non-destructive by default

The ladder row itself notes the solve script should prove this "without
actually running it against the live range." Here, calling the route
without `X-Confirm-Reset: yes` returns the flag and an honest `"reset":
false` — the bug (any valid token reaches an admin-only function) is fully
proven without mutating anything. Only `--confirm` on the reference solve
(sending that header) also resets the in-memory roster; never do that
against a shared/live deployment.

## Flow

1. `POST /login` with `{"username": "student07", "password": "changeme123"}` → a bearer token, role `student`.
2. `POST /admin/reset-all` with that token, no extra header → `{"reset": false, "flag": "..."}`.

## Environment

| Var | Meaning | Dev default |
|-----|---------|-------------|
| `CTF_STUDENT` | the one seeded account's handle | `student07` |
| `CTF_FLAG` | the slot's rendered flag value | `flag{api-bfla-dev…}` |
| `PORT` | listen port | `5000` |

## Build and run standalone

```sh
cd modules/ctf-range/targets/api-bfla
docker build -t ctf-api-bfla:dev .
docker run --rm -p 5000:5000 \
  -e CTF_STUDENT=student07 -e CTF_FLAG='flag{api-bfla-test}' \
  ctf-api-bfla:dev
```

## Verify

```sh
python3 exploit/solve.py --url http://127.0.0.1:5000
```

## Files

- `app.py` — the vulnerable JSON API.
- `exploit/solve.py` — reference solve (non-destructive by default).
- `Dockerfile`, `requirements.txt` — the image.
