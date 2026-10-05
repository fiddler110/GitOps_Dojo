# Target 1 — `idor-pcap`

CTF-1 (plan §7.3 row 1, the old draft's `pcap-dashboard` kept under its new
name). A "support ticket archive" that serves numbered packet captures with
no ownership check at all.

## The flaw

`GET /data/<n>` returns ticket `n`'s capture to anyone, for any `n` — the
IDOR. Enumerating `0..9` (no hint which one matters) finds ticket 7: a real,
parseable pcap with a cleartext FTP login (`USER svc-backup` / `PASS
Backup!2024`) readable with `strings`, `tcpdump -r`, or `tshark -r` /
Wireshark's "Follow TCP Stream". Those same credentials gate `/admin`
(HTTP Basic Auth) — credential reuse, the deeper lesson of row 5
(`leaky-config`).

**Documented simplification:** the ladder's escalation step is "a Python
binary with `cap_setuid`" — real Linux-capability privesc, which needs a
local shell. This target's architecture (one published port, no shell -
see `app.py`'s module docstring) has no channel for that, so `/admin`
stands in for it: same leaked identity unlocks it, and its response
explains the capability-abuse step and carries the flag. The Lab Info
library covers `getcap`/`cap_setuid` on its own.

## Decoy ports (nmap)

The attack ladder also publishes decoy SSH (2222) and FTP (2121) listeners
alongside the real app (plan §7.3's own nmap primer — a student scans their
box and finds more than the port they'll actually use, same as a HackTheBox
box). Neither is a real service — each just speaks enough of the opening
handshake to fingerprint under `nmap -sV`, then fails the next step; see
`app.py`'s decoy-listener comment. The FTP decoy even accepts `svc-backup`'s
leaked creds for `USER`/`PASS` and still answers "Login incorrect" — the
real foothold here is the IDOR, not a live FTP login, and that dead end is
the point. The standalone `docker run` below only publishes 5000; add
`-p 2222:2222 -p 2121:2121` to see the decoys too.

## Environment

| Var | Meaning | Dev default |
|-----|---------|-------------|
| `CTF_FLAG` | the slot's rendered flag value | `flag{idor-pcap-dev…}` |
| `PORT` | listen port | `5000` |

## Build and run standalone

```sh
cd modules/ctf-range/targets/idor-pcap
docker build -t ctf-idor-pcap:dev .
docker run --rm -p 5000:5000 -e CTF_FLAG='flag{idor-pcap-test}' ctf-idor-pcap:dev
```

## Verify

```sh
python3 exploit/solve.py --url http://127.0.0.1:5000
```

Enumerates `/data/0..9`, extracts the leaked FTP creds from whichever ticket
has them, replays them against `/admin`, checks for the flag.

## Files

- `app.py` — the vulnerable app (serves and crafts the pcaps in-process).
- `exploit/solve.py` — reference IDOR + credential-reuse solve.
- `Dockerfile`, `requirements.txt` — the image.
