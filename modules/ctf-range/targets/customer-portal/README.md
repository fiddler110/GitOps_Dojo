# Target 14 — `customer-portal`

CTF-5's dedicated **app-code defend target** (decision CTF-D25, plan §7.3 row
14, §8.12). A small Flask portal over a **plaintext SQLite** database of
synthetic customer records that reference the student. It is the full GitOps
payoff of the series: the student fixes application *source*, opens a PR, the
pipeline scans and re-runs the exploit as the gate (CTF-D19), and merging to
main rebuilds the image and redeploys it in place.

> **Built here:** the vulnerable app, its seed data, the container image, the
> reference exploit/gate, the **informational SAST stage** (`sast/scan.py`,
> CWE-89, CTF-S17/D23/D24), and the **defend pipeline** definition
> (`.forgejo/workflows/`, the S6 scan + exploit-gate on PR and the
> rebuild→redeploy on merge). **Not here yet, and why:** the pipeline's build →
> push → *live* redeploy-in-place tail needs range infra that the scaffold
> stubs — the boxed `ctf-host` build (CTF-D21), the in-lab registry, and
> `ctf-controller` (S14); and the **wall of shame** (§8.12) needs the SOC/CTF
> event contract (spike CTF-S11), the attacker bots, and the presentation
> widget route, none of which exist yet. `defend-main.yml` carries those two
> steps as the documented S6 contract, marked, not faked.

## The flaw (graded)

SQL injection. `/search` builds its `WHERE` clause by string-concatenating the
`q` parameter, so `%' OR '1'='1' -- ` returns every row — including the
`portal-service` account whose `password` column holds the **flag**. `/login`
shares the same root cause (a bypassable `email`/`password` check).

The query also selects the whole row, so the dump exposes every customer's
cleartext password — the breach is legible, which is what the wall of shame
renders.

## The fix (what the student does in CTF-5)

Edit `app.py`: replace the string-built SQL with a **parameterized query** (the
`?` placeholder and a params tuple). The SAFE version is written inline as a
comment directly beneath each vulnerable query. Then PR → merge → redeploy.

- **Graded, gated:** the SQL injection. Once parameterized, the dump returns no
  flag and the target goes green (CTF-D19).
- **Bonus (CTF-D17), not gated:** the cleartext passwords. Hash/encrypt at
  rest. Surfaced by bots and the SAST stage, but never moves the status light
  on its own.

## Data

`seed.py` builds a `customers` table from `CTF_STUDENT`: five synthetic
public-figure rows with emails/account-ids tied to the handle, plus one
`portal-service` row whose password is `CTF_FLAG`. All fake, all lab-local — no
real PII. Seeding is idempotent (no-op if the DB is already populated), so a
restart keeps the student's data.

## Environment

| Var | Meaning | Dev default |
|-----|---------|-------------|
| `CTF_STUDENT` | handle the data references | `student07` |
| `CTF_FLAG` | the slot's rendered flag value (§5); the seed never sees the password seed | `flag{customer-portal-dev…}` |
| `CTF_DB_PATH` | SQLite file path | `/data/portal.db` |
| `PORT` | listen port inside the container | `5000` |

## Build and run standalone

```sh
cd modules/ctf-range/targets/customer-portal
docker build -t ctf-customer-portal:dev .
docker run --rm -p 5000:5000 \
  -e CTF_STUDENT=student07 -e CTF_FLAG='flag{customer-portal-test}' \
  ctf-customer-portal:dev
```

Or through the module's dev compose instance:
`./dojo <pack-using-ctf-range>` (none wired yet — build the image directly
for now).

## Verify the flaw and the fix

```sh
# VULNERABLE: dumps rows and finds the flag → exit 0
python3 exploit/dump.py --url http://127.0.0.1:5000

# After parameterizing both queries in app.py and rebuilding:
# PATCHED: injection returns nothing → exit 1  (this is the CTF-D19 gate pass)
python3 exploit/dump.py --url http://127.0.0.1:5000
```

`exploit/dump.py` is the same check the defend pipeline runs as the gate: exit 0
= still vulnerable (red), exit 1 = patched (green), exit 2 = couldn't reach the
target.

```sh
# SAST (informational, CTF-D23): points at the flaw, never gates. Finds the two
# string-built queries on the vulnerable source; silent once parameterized.
python3 sast/scan.py app.py            # exit 0 even with findings
python3 sast/scan.py --strict app.py   # exit 1 if any finding (human spot-check)
```

The defend pipeline (`.forgejo/workflows/`) chains these: `defend-pr.yml` runs
the SAST (informational) then the exploit re-run as the CTF-D19 gate — a PR
passes only when the dump returns nothing; `defend-main.yml` rebuilds and asks
`ctf-controller` to redeploy the slot in place on merge to main.

## Files

- `app.py` — the vulnerable Flask app (the source students edit).
- `seed.py` — builds the synthetic SQLite DB from the handle.
- `entrypoint.sh` — seed (idempotent) then run.
- `exploit/dump.py` — reference SQLi dump + CTF-D19 gate check.
- `sast/scan.py` — pinned, no-network CWE-89 SAST (informational, CTF-D23/D24).
- `.forgejo/workflows/defend-pr.yml` — PR gate: SAST + exploit re-run (CTF-D19).
- `.forgejo/workflows/defend-main.yml` — merge: rebuild + redeploy (S6 contract).
- `Dockerfile`, `requirements.txt` — the image.
