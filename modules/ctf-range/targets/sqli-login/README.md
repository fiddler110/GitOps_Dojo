# Target 0 — `sqli-login`

CTF-1's warm-up (plan §7.3 row 0, kept from the original draft under a new
name). The first entry on the "Access and identity" ladder: a login form
whose query is built by plain string concatenation, so the classic
auth-bypass payload logs in as `admin` without the password. Single flag,
shown right on the welcome page — no second stage (the ladder row is explicit:
"none; single flag shown in the page").

This is an **attack-ladder target** (CTF-1 to CTF-4, decision CTF-D20), not a
CTF-5 defend target like `../customer-portal`: a student never patches it,
only attacks it, so there is no seed script, no volume, no pipeline, no SAST
stage — just the app, the image, and a solve script that proves it's solvable.

## The flaw

`/login` builds its `WHERE` clause with Python string concatenation:

```python
query = "SELECT username FROM users WHERE username = '" + username + "' AND password = '" + password + "'"
```

`username = admin' OR '1'='1' -- ` closes the string literal and makes the
clause always true, so the query returns the first row — `admin` — regardless
of the password field. The fix (not graded; this target has no gate) is the
one-line parameterized version, written as a comment in `app.py` right above
the vulnerable line.

## The second step: SSH (and the decoys)

Behind the login the portal links three log files (placement differs per box: one holds two credentials, one
holds one, one holds none) that leak three accounts. Only `svc-print`, with a random password, logs into the SSH service on container port 2222, which ctf-controller publishes as host port 22 on
the student's own box IP. It is a real SSH-2 server (`sshshell.py`, asyncssh) with an emulated shell: a few
built-in commands over a fake filesystem, no real shell. A real sshd can't run here (the container drops
every capability and runs non-root). `flag.txt` in the account's home directory holds the flag; the web page
no longer shows it. The host key is derived from the flag, so Reset doesn't trip a student's `known_hosts`.

It also binds an FTP decoy on 2121 (answers every login with 530) and an HTTP decoy on 8081 (answers 401 to
everything). In the lab, ctf-controller publishes the web, FTP and HTTP ports on host ports drawn per student
(`CTF_RANDOM_PORT_TARGETS`, `Config.random_ports`), so those numbers differ on every box; SSH stays on 22. The
standalone `docker run` below only publishes 5000; add `-p 2222:2222` (and so on) to see the others too.

## Data

In-process only (`sqlite3.connect(":memory:")`) — an `admin` row with a random
password that's never revealed, and one decoy row tied to `CTF_STUDENT`. No
volume, no file on disk: the container's root filesystem stays fully
read-only with nothing to mount.

## Environment

| Var | Meaning | Dev default |
|-----|---------|-------------|
| `CTF_STUDENT` | handle the decoy row is tied to (cosmetic only) | `student07` |
| `CTF_FLAG` | the slot's rendered flag value (plan §5) | `flag{sqli-login-dev…}` |
| `PORT` | listen port inside the container | `5000` |

## Build and run standalone

```sh
cd modules/ctf-range/targets/sqli-login
docker build -t ctf-sqli-login:dev .
docker run --rm -p 5000:5000 \
  -e CTF_STUDENT=student07 -e CTF_FLAG='flag{sqli-login-test}' \
  ctf-sqli-login:dev
```

## Verify the flaw

```sh
python3 exploit/solve.py --url http://127.0.0.1:5000
```

`exploit/solve.py` posts the bypass payload and checks for the admin welcome
page and the flag. Exit 0 = solved, exit 1 = the bypass didn't work (target
broken or genuinely patched — this target is never patched in a real run),
exit 2 = couldn't reach the target.

## Wiring into the attack ladder

Not wired into `CTF_ATTACK_TARGETS` yet — that's a `module.env`/workshop-pack
config change (`id=image:tag`), not a code change; see
`ctf-controller/controller.py`'s `parse_targets()`.

## Files

- `app.py` — the vulnerable Flask app.
- `exploit/solve.py` — reference auth-bypass solve / smoke check.
- `Dockerfile`, `requirements.txt` — the image.
