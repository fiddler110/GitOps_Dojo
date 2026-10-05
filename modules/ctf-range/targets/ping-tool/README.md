# Target 4 — `ping-tool`

CTF-2 "Server-side trust and APIs" (plan §7.3 row 4). A "network
diagnostics" page that shells out with the submitted host pasted straight
into the command line — classic OS command injection.

## The flaw

`/diagnostics` builds `f"host {host}"` and runs it with `subprocess.run(...,
shell=True)`. `host=127.0.0.1; cat /tmp/sudo-note.txt` runs a second command
after the lookup. The fix (written as a comment in `app.py` right above the
vulnerable line) is `subprocess.run(["host", host], shell=False)` — no shell,
no metacharacters.

## Two documented simplifications

See `app.py`'s module docstring for both, in full:

1. **`host` instead of real `ping`.** Every slot container drops all
   capabilities (`docker_api.py`'s `build_create_request()`), so a real
   `ping` can't open a raw ICMP socket here regardless of this bug — it
   would fail before an attacker got the chance to inject anything. A DNS
   lookup (`host`) needs no special capability and teaches the identical
   "never paste user input into a shell command" lesson.
2. **`/escalate` stands in for `sudo -l` + GTFOBins.** The same global
   `CapDrop`/`no-new-privileges` hardening removes `CAP_SETUID` from every
   container, so there is no real root/non-root boundary inside a slot to
   escalate across — real `sudo` would simply fail to elevate, in any
   target, not just this one. The command-injection RCE instead reads a
   note (written at startup to `/tmp`, the one writable path) describing
   the rule a real `sudo -l` would show; redeeming its token via
   `/escalate` is the "used the GTFOBins binary" step and reveals the flag.

## Environment

| Var | Meaning | Dev default |
|-----|---------|-------------|
| `CTF_FLAG` | the slot's rendered flag value | `flag{ping-tool-dev…}` |
| `PORT` | listen port | `5000` |

## Build and run standalone

```sh
cd modules/ctf-range/targets/ping-tool
docker build -t ctf-ping-tool:dev .
docker run --rm -p 5000:5000 -e CTF_FLAG='flag{ping-tool-test}' ctf-ping-tool:dev
```

## Verify

```sh
python3 exploit/solve.py --url http://127.0.0.1:5000
```

Injects a second command into `/diagnostics` to read the escalation note,
then redeems its token against `/escalate`; checks for the flag.

## Files

- `app.py` — the vulnerable app.
- `exploit/solve.py` — reference solve.
- `Dockerfile`, `requirements.txt` — the image.
