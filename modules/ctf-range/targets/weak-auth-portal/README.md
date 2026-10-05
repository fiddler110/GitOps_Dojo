# Target 2 — `weak-auth-portal`

CTF-1 (plan §7.3 row 2, new). A login portal whose password-reset token is
derived purely from public information — no server secret is mixed in at
all — so it's computable by anyone who guesses the scheme, without the
token ever being sent to them.

## The flaw

`POST /reset` accepts `username`, `token`, `new_password`. The token it
checks against is `sha256(f"reset:{user}:{bucket}")[:6]`, where `bucket` is
the current 60-second time window — both inputs public. The fix (one line,
inline comment in `app.py`) mixes in a server-side secret the attacker can
never know, turning it into a real HMAC. The flavor-only "no login rate
limit" half of the row's foothold text is also true here (`/login` has no
attempt limiting) but isn't the gating path — the password space is too
large for a live solve script to brute force, and the reset-token bug alone
is enough to take over `ops-admin`, whose real password is random and never
revealed.

## Decoy port (nmap)

The attack ladder also publishes a decoy SSH listener on container port
2222 alongside the real app (plan §7.3's own nmap primer). It speaks just
enough of the SSH-2.0 banner to fingerprint under `nmap -sV`, then closes —
not a real sshd; see `app.py`'s decoy-listener comment. The standalone
`docker run` below only publishes 5000; add `-p 2222:2222` to see it too.

## Environment

| Var | Meaning | Dev default |
|-----|---------|-------------|
| `CTF_FLAG` | the slot's rendered flag value | `flag{weak-auth-portal-dev…}` |
| `PORT` | listen port | `5000` |

## Build and run standalone

```sh
cd modules/ctf-range/targets/weak-auth-portal
docker build -t ctf-weak-auth-portal:dev .
docker run --rm -p 5000:5000 -e CTF_FLAG='flag{weak-auth-portal-test}' ctf-weak-auth-portal:dev
```

## Verify

```sh
python3 exploit/solve.py --url http://127.0.0.1:5000
```

Computes the current-bucket token for `ops-admin` independently (no
requests to learn it) and resets the password with it; checks for the flag.

## Files

- `app.py` — the vulnerable app.
- `exploit/solve.py` — reference token-guessability solve.
- `Dockerfile`, `requirements.txt` — the image.
