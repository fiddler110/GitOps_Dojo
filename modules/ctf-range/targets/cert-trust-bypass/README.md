# Target 3 — `cert-trust-bypass`

CTF-1 (plan §7.3 row 3, new, ties `cert-autorenewal`). An internal API meant
to require a trusted client certificate but that only parses the presented
PEM and reads its Subject CN — it never checks who signed it or whether it
has expired.

## The flaw

`POST /internal/ops` with a certificate PEM as the raw body. The handler
decodes it with Python's own X.509 parser and checks only the Subject CN
against `ops-internal`. **Any self-signed or expired certificate with that
CN is accepted** — there is no chain-of-trust check (no CA bundle is ever
consulted) and no expiry check. The fix (both steps, written as an inline
comment in `app.py`'s `internal_ops()`) is: verify the cert chains to a
trusted CA, and reject it if `notAfter` is in the past.

**Why plain HTTP, not real mTLS:** see `app.py`'s module docstring — the
bug is explicitly an application-layer check, and this attack-ladder
architecture gives one published port with no TLS trust store wired through
it. POSTing the PEM to an endpoint tests the identical mechanic (parse a
real X.509 cert, check its signer, check its expiry) without needing a full
mTLS handshake. A student generates the attacking cert with plain
`openssl req -x509 ...` — the exact tool `cert-autorenewal` already covers.

## Decoy port (nmap)

The attack ladder also publishes a decoy SSH listener on container port
2222 alongside the real app (plan §7.3's own nmap primer). It speaks just
enough of the SSH-2.0 banner to fingerprint under `nmap -sV`, then closes —
not a real sshd; see `app.py`'s decoy-listener comment. The standalone
`docker run` below only publishes 5000; add `-p 2222:2222` to see it too.

## Environment

| Var | Meaning | Dev default |
|-----|---------|-------------|
| `CTF_FLAG` | the slot's rendered flag value | `flag{cert-trust-bypass-dev…}` |
| `PORT` | listen port | `5000` |

## Build and run standalone

```sh
cd modules/ctf-range/targets/cert-trust-bypass
docker build -t ctf-cert-trust-bypass:dev .
docker run --rm -p 5000:5000 -e CTF_FLAG='flag{cert-trust-bypass-test}' ctf-cert-trust-bypass:dev
```

## Verify

```sh
python3 exploit/solve.py --url http://127.0.0.1:5000
```

Generates a throwaway self-signed cert with CN `ops-internal` via `openssl`
and POSTs it; checks for the flag.

## Files

- `app.py` — the vulnerable app.
- `exploit/solve.py` — reference solve (needs `openssl` on PATH).
- `Dockerfile`, `requirements.txt` — the image.
