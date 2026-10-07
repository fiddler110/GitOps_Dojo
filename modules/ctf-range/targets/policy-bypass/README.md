# Target 9 — `policy-bypass`

CTF-4 (plan §7.3 row 9, new, ties `cloud-policy-as-code`). A04:2021
"Insecure Design" — there is no bug to find in how the policy is evaluated;
the rule itself is wrong, and it still passes every shape/syntax check a
real `opa test` analogue would run.

## The flaw

`policy_engine.py` is vendored **verbatim** from
`modules/dojo-cloud/cloud-api/policy_engine.py` — the real Azure-Policy-style
rule evaluator the `cloud-policy-as-code` workshop teaches against, not a
toy stand-in. It runs the rule exactly as written. The rule, defined in
`app.py`, is what's wrong: it denies a write to the protected resource
group `rg-vault-gateway` **unless the request's own `tags['provisioned-by']`
already reads `security-team`** — i.e. it treats a label the requester
attaches to their own request as proof of who the requester is. Nothing
server-side verifies it. `GET /api/policy` shows the whole rule, in the
open — the same "the policy compiles and passes its tests, the rule is
still wrong" lesson as the plan's A04 row names, so the fix isn't hidden,
just wrong. The inline comment in `app.py` names the actual fix: check a
caller-identity field the gateway itself attaches server-side, never
anything inside the request body a requester shapes.

## Escalation

None needed — self-reporting the one tag the (broken) rule checks is the
whole exploit. `POST /api/provision` into `rg-vault-gateway` with
`tags: {"provisioned-by": "security-team"}` returns the flag directly, the
same "single flag, shown on success" shape as target 0 `sqli-login`.

## Decoy port (nmap)

A decoy SSH listener on container port 2222 alongside the real app (plan
§7.3's nmap primer), identical to every other target in this ladder — see
`app.py`'s decoy-listener comment; not a real sshd.

## Environment

| Var | Meaning | Dev default |
|-----|---------|-------------|
| `CTF_FLAG` | the slot's rendered flag value | `flag{policy-bypass-dev…}` |
| `PORT` | listen port | `5000` |

## Build and run standalone

```sh
cd modules/ctf-range/targets/policy-bypass
docker build -t ctf-policy-bypass:dev .
docker run --rm -p 5000:5000 -e CTF_FLAG='flag{policy-bypass-test}' ctf-policy-bypass:dev
```

## Verify

```sh
python3 exploit/solve.py --url http://127.0.0.1:5000
```

Reads `/api/policy`, extracts the tag name and value the rule treats as
proof (never hardcodes it), self-reports it on a provision request, and
checks for the flag in the response.

## Files

- `app.py` — the vulnerable policy assignment/definition (as data) and the
  small API around it.
- `policy_engine.py` — vendored, unmodified, real rule evaluator (see its
  own header comment).
- `exploit/solve.py` — reference solve.
- `Dockerfile`, `requirements.txt` — the image.
