# Target 12 — `api-mass-assignment`

CTF-2 "Server-side trust and APIs" (plan §7.3 row 12). API-only — OWASP API
Security Top 10 API3:2023 Broken Object Property Level Authorization. No
HTML anywhere; drive it with `curl`/`httpie`/`jq`.

## The flaw

`PATCH /users/me` does `_USERS[username].update(body)` — every key in the
client's JSON body lands on the user record, `role` included, even though
only `bio` was ever meant to be client-settable. The fix (written as a
comment in `app.py` right above the vulnerable line) is an explicit
allow-list of bindable fields.

## Flow

1. `POST /login` with `{"username": "student07", "password": "changeme123"}` → a bearer token, role `student`.
2. `PATCH /users/me` with `{"role": "admin"}` → the record now has `role: admin`.
3. `GET /admin/report` with that same token → now passes the role check and returns the flag.

## Environment

| Var | Meaning | Dev default |
|-----|---------|-------------|
| `CTF_STUDENT` | the one seeded account's handle | `student07` |
| `CTF_FLAG` | the slot's rendered flag value | `flag{api-mass-assignment-dev…}` |
| `PORT` | listen port | `5000` |

## Build and run standalone

```sh
cd modules/ctf-range/targets/api-mass-assignment
docker build -t ctf-api-mass-assignment:dev .
docker run --rm -p 5000:5000 \
  -e CTF_STUDENT=student07 -e CTF_FLAG='flag{api-mass-assignment-test}' \
  ctf-api-mass-assignment:dev
```

## Verify

```sh
python3 exploit/solve.py --url http://127.0.0.1:5000
```

## Files

- `app.py` — the vulnerable JSON API.
- `exploit/solve.py` — reference solve.
- `Dockerfile`, `requirements.txt` — the image.
