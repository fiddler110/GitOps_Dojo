# Target 5 — `leaky-config`

CTF-3 (plan §7.3 row 5). An ops dashboard's debug-log and config-backup
directory is reachable with no auth at all — a control that lived in
infrastructure (a reverse proxy) which never got ported into the app.

## The flaw

`GET /admin/logs` and `GET /admin/logs/<name>` serve two files with no
auth check: `app.log` and `ops-dashboard.conf.bak`. The fix (one line,
inline comment in `app.py`) is to require the same Basic Auth check
`/internal/metrics` already has before serving anything under `/admin/logs`.

Two files, two different lessons:

- `ops-dashboard.conf.bak` is **noise** — it looks like a leaked secret
  (a DB connection string) but unlocks nothing on this target. Chasing it
  is a believable dead end.
- `app.log` has the real leak: one `WARN` line where a failed-auth handler
  logged the attempted credentials in plaintext instead of redacting them.
  Those credentials are the real password for the `metrics-agent` account.

**Escalation** is pure credential reuse, not a second bug: the leaked
`metrics-agent` password is valid against `/internal/metrics` (Basic
Auth, correctly checked — the bug is never in the check itself), which
returns the flag.

## Decoy port (nmap)

Also publishes a decoy SSH listener on container port 2222 (plan §7.3's
nmap primer) — not a real sshd, see `app.py`'s decoy-listener comment.
The standalone `docker run` below only publishes 5000; add `-p 2222:2222`
to see it too.

## Environment

| Var | Meaning | Dev default |
|-----|---------|-------------|
| `CTF_FLAG` | the slot's rendered flag value | `flag{leaky-config-dev…}` |
| `PORT` | listen port | `5000` |

## Build and run standalone

```sh
cd modules/ctf-range/targets/leaky-config
docker build -t ctf-leaky-config:dev .
docker run --rm -p 5000:5000 -e CTF_FLAG='flag{leaky-config-test}' ctf-leaky-config:dev
```

## Verify

```sh
python3 exploit/solve.py --url http://127.0.0.1:5000
```

Reads `/admin/logs/app.log`, extracts the leaked `user=`/`pass=` pair, and
reuses it against `/internal/metrics`; checks for the flag.

## Files

- `app.py` — the vulnerable app.
- `exploit/solve.py` — reference leak-and-reuse solve.
- `Dockerfile`, `requirements.txt` — the image.
