# Target 7 — `ssrf-fetcher`

CTF-2 "Server-side trust and APIs" (plan §7.3 row 7). A "preview this URL"
feature that fetches server-side with no allow-list, reaching an
internal-only admin endpoint it was never meant to.

## The flaw

`/preview` calls `urllib.request.urlopen(url)` on whatever URL the client
sends, with no check on scheme or destination. The fix (written as a
comment in `app.py` right above the vulnerable line) is to resolve the host
first and reject anything that isn't a known-public address before ever
calling `urlopen`.

## Why one image runs two servers

The ladder row wants "an internal-only admin endpoint on another service in
the same target." This architecture gives one published port per slot
(`docker_api.py`'s `build_create_request()`), so the "other service" is a
second Flask app in the same process, bound to `127.0.0.1` only, in a
background thread. It's never published and isn't on a routable address —
nothing outside the container can reach it — but `/preview`'s own fetch runs
*inside* the container, so it can reach loopback fine. See `app.py`'s module
docstring.

## Environment

| Var | Meaning | Dev default |
|-----|---------|-------------|
| `CTF_FLAG` | the slot's rendered flag value | `flag{ssrf-fetcher-dev…}` |
| `PORT` | public listen port | `5000` |
| `INTERNAL_PORT` | internal-only (loopback) listen port | `5001` |

## Build and run standalone

```sh
cd modules/ctf-range/targets/ssrf-fetcher
docker build -t ctf-ssrf-fetcher:dev .
docker run --rm -p 5000:5000 -e CTF_FLAG='flag{ssrf-fetcher-test}' ctf-ssrf-fetcher:dev
```

## Verify

```sh
python3 exploit/solve.py --url http://127.0.0.1:5000
```

Posts `url=http://127.0.0.1:5001/internal/admin/flag` to `/preview` and
checks the response for the flag.

## Files

- `app.py` — the vulnerable public app plus the internal-only admin app it
  runs alongside.
- `exploit/solve.py` — reference solve.
- `Dockerfile`, `requirements.txt` — the image.
