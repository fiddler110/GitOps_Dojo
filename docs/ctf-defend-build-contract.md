# ctf-defend three-target build contract

Shared interface for the five parallel build pieces (A targets, B checker + terminal, C controller + builder,
D bot + SIEM, E pack content). Decisions are in `docs/CTF-WORKSHOP-PLAN.md` ("Defend lab redesign"). Fold this
into the plan after the live run, then delete it. Nothing here touches `engine/`.

## Names and numbers

| target | index | severity | weight | signal kind |
|---|---|---|---|---|
| `customer-portal` | 0 | high | 3 | request log (SQL injection) |
| `policy-bypass` | 1 | medium | 2 | audit log (policy write allowed for the wrong caller) |
| `leaky-config` | 2 | low | 1 | file-access + auth log (unauthenticated log read, then reuse of a logged credential) |

- Env (all pack-level, set in `workshops/ctf-defend/workshop.env` or its compose override):
  `CTF_DEFEND_TARGETS="customer-portal policy-bypass leaky-config"` (index = position), `CTF_PORT_STRIDE=100`,
  `CTF_TARGET_STAGGER=0.5`, `CTF_SCHEDULE_SEED` (optional; default chosen once at controller start).
- Slot (container) name: `ctf-<target>-<user>`. Published host port: `CTF_HOST_PORT_BASE + target_index *
  CTF_PORT_STRIDE + user_index`. The slot's service port inside is always 5000.
- Per-slot flag: derived per `(user, target)` by `ctf-controller/flags.py` (`render(user, seed, challenge=target)`);
  `CTF_FLAG` env on the slot.
- Student repos: one per target under the student's own owner, named exactly the target (`customer-portal`,
  `policy-bypass`, `leaky-config`), each with the target's `app.py`, `Dockerfile`, a `README.md` that tells the
  student what the app is and what the platform provides, and `.forgejo/workflows/defend-pr.yml` + `defend-main.yml`.
  The repos do NOT contain any exploit script.

## Verdicts and check scripts

- Verdict strings, everywhere: `exploitable`, `contained`, `broke-normal-use`, `unreachable`.
- Each target has `modules/ctf-range/targets/<t>/exploit/check.py`:
  `python3 check.py --url URL [--expect-flag F] [--legit-key K]` prints one JSON line
  `{"verdict": "...", "note": "..."}` and exits 0 exploitable, 1 contained, 3 broke-normal-use, 2 unreachable.
  "contained" requires the exploit to be blocked AND one legitimate request to still succeed. `note` is one short
  sentence about what was seen, never a payload and never a row count.
- `customer-portal/exploit/dump.py` stays (the bot imports it).

## policy-bypass identity (option B)

The image has `proxy.py` (NOT in the student repo) listening on 5000 and forwarding to the student's `app.py` on
127.0.0.1:5001. It sets `X-Caller-Role` (`security-team` when the request carries `Authorization: Bearer
$CTF_SECTEAM_KEY`, otherwise `developer`) and `X-Gateway-Token: $CTF_PROXY_TOKEN`, replacing client-supplied
values. The student's `app.py` must only trust the role when the token header matches. The seeded README states
this contract in plain words (discoverability rule). The flaw stays: the policy trusts the request's own
`tags['provisioned-by']`. Fix: use `X-Caller-Role`. `check.py` takes `--legit-key` to send the security-team
request.

## Services and endpoints

- **ctf-checker** (new, `modules/ctf-range/ctf-checker/`, port 9200, networks `workshop_lab` + `ctf_net` +
  `runner_net`): holds the check scripts (not student-readable) and a copy of each target's seed app for gating.
  - `POST /check` body `{"user": "student01"}` (identity as `dojo-flag`: `$USER`) -> `{"results": [{"target",
    "verdict", "note", "at"}]}` for all three live slots in schedule order. Light rate limit (one run per user per
    3 s).
  - `POST /gate` (`Authorization: Bearer $CTF_BUILD_TOKEN`) body `{"user","target","ref"}`: clones the student's repo
    at `ref` from the git server itself (as `ctf-builder` does), runs the candidate app locally with its seed,
    runs `check.py`, returns `{"verdict","note","pass": verdict == "contained"}`. The PR workflow calls this
    instead of running a script from the repo.
- **terminal**: `/usr/local/bin/dojo` is NOT used; install `dojo-check` (the plan calls it `dojo check`; the
  `dojo-check` binary is what is installed, and a `dojo-flag`-style `check` alias is fine). `dojo-check` prints one
  line per target: `customer-portal  HIGH    still exploitable`, `...contained`, etc., and exits 0.
  `dojo-check <target>` checks one. Address env `CTF_CHECKER_ADDR` (default `http://ctf-checker:9200`).
- **ctf-controller** additions (Bearer `CTF_CONTROL_TOKEN`):
  - `GET /schedule` -> `{"seed", "t0": null|epoch, "dwell_s", "stagger", "users": {"student01": [{"target",
    "index", "severity", "weight", "start_offset_s"}, ...]}}`; `GET /schedule?user=student01` -> that row.
  - Order: the six permutations of the three targets, shuffled once by the seed, dealt to students round-robin by
    roster index (so 20 students get 3-4 of each). `start_offset_s = position * stagger * dwell_s` (position 0, 1, 2);
    `dwell_s` comes from the bot's existing dwell constant (480 s at scale 1; the bot applies `CTF_TIME_SCALE`).
  - `POST /redeploy` body `{"user","target","image"}` (target required once the three-target mode is on).
  - `GET /slots` rows gain `target`.
- **ctf-builder**: `POST /build` body gains `target`; image tag per `(user, target)`.

## SIEM / bot

- Bot per student: fetch own row from `GET /schedule?user=` after the facilitator Start, then run the three
  attacks as independent timers: at `t0 + start_offset_s` begin recon -> probe -> exploit against that target's
  URL, using its dwell/ramp. Benign noise throughout (about 15% of traffic).
- Event docs gain `target` (same value as `challenge`) and the signal fields below. `dump_success` stays the
  breach event, one per `(user, target)`. `_breached` and the visibility tiers (base/paths/full) become per
  `(user, target)`; the wall banner is red if any target is breached; the panel groups by target and shows severity.
- Signal fields (extra row fields; every one must be specific, countable and separable from benign noise):
  - customer-portal: `method, path, query, status, bytes, rows_returned, ua, klass`. Strong indicator: `GET
    /search` with SQL metacharacters in `q` and `rows_returned` far above the benign 0-3 (`klass=sqli`).
  - policy-bypass: `method, path, caller, resource_group, outcome (allowed|denied), asserted_tag, klass`. Strong
    indicator: `outcome=allowed`, `resource_group=rg-vault-gateway`, `caller=developer`,
    `asserted_tag=security-team`, usually preceded by one or more `outcome=denied` rows. Benign: allowed writes to
    `rg-sandbox`, and allowed protected writes by `caller=security-team`.
  - leaky-config: `method, path, auth (none|basic-fail|basic-ok), account, ua, status, klass`. Strong indicator:
    `GET /admin/logs/...` `auth=none` `status=200`, then `auth=basic-ok` with `account=ops-admin` from a `ua` that
    never appears in the benign traffic (the ops dashboard's own UA). Benign: `/status` and `/healthz` polls.
- Scoring stays per target: green 10 / yellow 5 / red 0 x weight, time to contain and MTTP display only.

## File ownership (no two pieces edit the same file)

- A: `modules/ctf-range/targets/{customer-portal,policy-bypass,leaky-config}/**` only.
- B: `modules/ctf-range/ctf-checker/**`, `modules/ctf-range/terminal/**`, `modules/ctf-range/compose.yml`,
  `modules/ctf-range/module.env`.
- C: `modules/ctf-range/ctf-controller/**`, `modules/ctf-range/ctf-builder/**`.
- D: `modules/ctf-range/attacker-bot/**`, `modules/achievements/**`.
- E: `workshops/ctf-defend/**`, `modules/ctf-range/lab-info/**`, `modules/ctf-range/README.md`.
- Anything another piece needs from a file you do not own goes in your final report as an exact request.
