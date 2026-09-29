# Remediation P4 scoping (read-only, 2026-09-29, branch feat/remediation)

Source: `threat-model-20260926-154208/REMEDIATION-PLAN.md` §5 P4 (lines 377-399), findings FIND-06/-12/-14 in
`3-findings.md` (196, 405, 476). Nothing in the repo was changed. 
Workshops that pick up each piece (from `workshop.env` MODULES + overlays):
- runner-pool: dns-as-code, dojo-introduction, vault-fundamentals
- app-host: vault-fundamentals, **dojo-introduction** (its overlay also defines app-host; the plan only names vault)
- dns-gate: dns-as-code, cert-autorenewal, dojo-introduction
- dojo-cloud (CloudAPI): tofu-basics, dojo-introduction
- openbao / app-db: vault-fundamentals, dojo-introduction (openbao)
- allocator, web-terminal: every workshop

---

## T4.1 (FIND-06, Moderate) [MODULE] + [WORKSHOP]: drop caps and no-new-privileges on runner-pool and app-host

### Files
- `modules/runner-pool/compose.yml:32-67` (service `runner-pool`; `user: "0:0"` at 42, comment at 40-41 "Rootless
  podman's default capabilities; no extra ones (T0.8)"). Optionally `runner-pool-shim` at 73-96 (root, binds 443).
- `workshops/vault-fundamentals/compose/docker-compose.override.yml:36-75` (service `app-host`, `user` at 44,
  `cap_add: [NET_ADMIN]` at 45-46, comment at 41-43 already says "dropping it after start-up is T4.1").
- `workshops/dojo-introduction/compose/docker-compose.override.yml`: its own app-host definition, same change.
- `workshops/vault-fundamentals/compose/app-host/apphost.py`: `isolate_slots()` at 314-340, called at 360 inside
  Platform set-up; `main()` at 702. `Dockerfile:30` ENTRYPOINT (`tini -- python3 -B -u apphost.py`).
- Docs: `modules/runner-pool/README.md`, vault-fundamentals README/PLAN notes on app-host.
- Working examples to copy: `modules/dns-gate/compose.yml:35-39`, `modules/dns-ui/compose.yml:38-42,71-76`,
  `modules/dojo-cloud/compose.yml:89-93`.

### What the processes actually do (to pick the add-back set)
- runner-pool (`modules/runner-pool/pool/supervise.py`, Alpine forgejo-runner image): `useradd -m` / `userdel -r`
  (99, 141), `os.chown`/`os.chmod` on the job home and TMPDIR (105-113, 283-287), `su <user> -c 'prlimit ...
  unshare -U --map-current-user -p -f --mount-proc forgejo-runner one-job'` (186-188), cleanup `su <user> -c
  'kill -9 -1'` (123, 209) and `rmtree` of the user's 0700 dirs as root (124-137). No listener.
- app-host (Debian bookworm-slim, util-linux `su` with PAM): `useradd -M` (365), chown/chmod (351-370, 392, 498),
  `su <slot> -c 'prlimit ... unshare -U ...'` (408-425, 506), `iptables` owner-match chain (314-340, NET_ADMIN),
  ThreadingHTTPServer on 8080.

### Approach
1. Both services: `security_opt: [no-new-privileges:true]`, `cap_drop: [ALL]`, `cap_add: [CHOWN, DAC_OVERRIDE,
   FOWNER, SETUID, SETGID, KILL]` (+ `FSETID` only if useradd's skel copy complains). This is a strict subset of
   podman 4+'s current default set (CHOWN, DAC_OVERRIDE, FOWNER, FSETID, KILL, NET_BIND_SERVICE, SETFCAP, SETGID,
   SETPCAP, SETUID, SYS_CHROOT), so the net removal is NET_BIND_SERVICE, SETFCAP, SETPCAP, SYS_CHROOT, FSETID.
   AUDIT_WRITE is already absent under podman 4+, so Debian PAM `su` already works without it.
2. `unshare -U`/`--mount-proc` run *after* `su` as an unprivileged uid; a new user namespace gets its own full cap
   set regardless of the parent's bounding set, and caps are lost at the `exec` anyway (map-current-user, not
   root). no-new-privileges only blocks gains through setuid bits/file caps on exec, and root→user via `su` is a
   drop. Expected to keep working, but it is the #1 thing the live test must prove.
3. app-host NET_ADMIN only at start (T4.1b). Recommended: split start-up in two execs.
   - `apphost.py --isolate-only`: compute the slot uid range from STUDENT_COUNT/BOT_COUNT (same code as line 360),
     run `isolate_slots()`, exit.
   - then `exec setpriv --bounding-set -net_admin,-setpcap -- python3 -B -u apphost.py` (normal mode, skips
     isolation or makes it a no-op check). For uid 0, execve sets permitted = bounding set, so NET_ADMIN is gone
     from the long-running process and every child. Needs `SETPCAP` in `cap_add` (PR_CAPBSET_DROP requires it) and
     drops it in the same call. `setpriv` is in util-linux (Essential on bookworm).
   - Wire it via the Dockerfile ENTRYPOINT (`tini -- sh -c '... && exec setpriv ...'`) or a tiny `start.sh`. Keep
     `restart: unless-stopped` semantics: a container restart gets NET_ADMIN again and re-runs the idempotent
     isolation. Alternative (no restructure): ctypes `prctl(PR_CAPBSET_DROP)` + `capset` in Python after
     isolation; more code and harder to read, not recommended.
4. Seccomp (T4.1c): omitting `seccomp=` already means podman's default profile. Stating a host path
   (`/usr/share/containers/seccomp.json`) is not portable across hosts. Suggest a comment only, plus the
   `podman inspect` check that `SeccompProfilePath` isn't `unconfined`. (Open question 1.)
5. Optional: harden `runner-pool-shim` too (`cap_drop: [ALL]`, `cap_add: [NET_BIND_SERVICE]`, maybe CHOWN for
   its `/data` CA write, no-new-privileges). It is the same pattern as dojo-cloud's front at 88-93.

### What could break
- `su` needs SETUID+SETGID; Debian PAM `su` may log a pam_loginuid/audit warning: check the log but not fatal today.
- `userdel -r` / `rmtree` of users' 0700 homes needs DAC_OVERRIDE (root traversing others' dirs).
- Stopping a runner/app: if supervise.py/apphost.py signals the `su` child directly (Popen.kill/terminate on a
  process now owned by the job uid), KILL is needed. Kept in the set for that reason.
- `--mount-proc` inside the new pidns: depends on the kernel/seccomp allowing unprivileged userns, not on the
  container's caps. It works today with no SYS_ADMIN, so dropping more should not matter; verify anyway.
- app-host: if any code path re-runs `isolate_slots()` after start (e.g. on reset), it will fail without NET_ADMIN.
  grep for callers of `isolate_slots` (only line 360 today). Slot apps must not bind <1024 (NET_BIND_SERVICE gone).
- Job tools that rely on setuid binaries (sudo, ping) fail under no-new-privileges. No `sudo` found in workshop
  workflows (quick grep); the dns-as-code dnscontrol and vault bao/sops jobs don't need it.
- podman-compose: `cap_drop`/`security_opt` are already in use in 4 modules, so it supports them.

### Verify
- `podman inspect workshop_runner_pool workshop_app_host --format '{{.HostConfig.CapDrop}} {{.HostConfig.CapAdd}}
  {{.HostConfig.SecurityOpt}}'`; inside app-host: `grep Cap /proc/1/status` and the Python pid's `CapEff`/`CapBnd`
  (decode with `capsh --decode`) show no NET_ADMIN; `iptables -S` still shows DOJO_SLOT_EGRESS; a slot app still
  can't reach `git-server:3000` and can reach openbao/app-db.
- Tests: `modules/runner-pool/tests/pool.sh`, `workshops/vault-fundamentals/tests/labs_8_9.sh`, `lab_10.sh`,
  `labs_11_13.sh` (the plan names these; they exist), plus `tests/p4_browser.py` for the Apps panel. dns-as-code:
  a PR preview job + a merge-to-main DNS Apply (runner-pool, JOB_TOOLS dnscontrol). dojo-introduction: starts
  healthy, one runner job, one app deploy.
- Unit: `python3 -B -m pytest workshops/vault-fundamentals/compose/app-host/tests/test_apphost.py` if the
  `--isolate-only` split touches testable code.

### Scope / overlap / model
- Scope: [MODULE] runner-pool + [WORKSHOP] vault-fundamentals and dojo-introduction. No engine files.
- Overlaps P3 live tests: #2 dns-as-code (runner-pool), #3 dojo-introduction (runner-pool, app-host), #5 vault
  `checks.sh`/`p2_browser.py`. Code can be written now; rebuild/live-test only after P3 tests 2, 3 and 5 are done
  (one stack builder at a time; the runner-pool image tag is shared).
- Model: **sonnet** for the compose edits; the app-host setpriv split is small but the cap reasoning is subtle:
  sonnet with this doc as the brief is enough, opus only if the first live run fails in a confusing way.

---

## T4.2 (FIND-14, Low) [ENGINE, ask]: allocator pages to static scripts, textContent, CSP

Needs the user's engine go (D1 lists T4.2 as "not yet approved, ask first").

### Files
- `engine/allocator/server.py` (1738 lines):
  - `page()` 557-581: inline `<style>` (name form, full, busy pages).
  - `render_name_form()` 704-712: **inline `onsubmit=` handler at 708** (double-submit guard). Blocked by any CSP
    without `'unsafe-hashes'`.
  - `render_confirmation()` 727-845: inline `<style>` at ~793; no script.
  - `render_facilitator_workspace()` 846-1290: inline `<style>` at ~1206 and the whole roster script 916-1188.
    `escapeHtml` at 986; `innerHTML` at 1070-1077 (tile header with studentId, **name**, ip) and 1111
    (`statusHtml`); `statusHtml` at 992-993 uses inline `style="color:..."` attributes.
    Other handlers (`onclick` at 928, 1035, 1082-1088) are JS property assignments: fine under CSP once the script
    is external. `el.style.x = ...` (962-979, 1126) is CSSOM and is **not** blocked by `style-src`.
  - Extension tabs/panels built with `html.escape` at 1192-1201 (server side, not student strings): fine.
  - `send_html()` 605-613: the one place to add the CSP header (and `send_json` doesn't need it).
  - `do_GET()` 1297+: add a route for the static script(s).
- `engine/allocator/Dockerfile`: COPY the new static file(s) (e.g. `engine/allocator/static/admin.js`,
  `landing.js`).
- `engine/allocator/render_extensions.py:41` `ENGINE_PREFIXES`: add the new prefix only if a non-`/admin` static
  path is introduced (see below), so a manifest route can't shadow it.
- Docs: `engine/README.md` (rendering/security section). Note the user currently has uncommitted edits there.
- Caddy (`engine/gateway/Caddyfile`): **no change needed**. `/admin*` (113-146) and the catch-all `handle`
  (243-256) both proxy to `allocator:8080`.

### Approach
1. Move the `/admin` script (916-1188) verbatim to `static/admin.js`, served at `/admin/admin.js` (under the
   facilitator gate, no collision possible). Page gets `<script src="/admin/admin.js" defer>`. Anything the script
   needs from the server (FACILITATOR_USERNAME etc.) goes in `data-*` attributes, not an inline block.
2. Rebuild the tile header with `createElement` + `textContent` for studentId, name, ip; `statusHtml` becomes a
   span with a class (`.st-on` / `.st-off`) and `textContent`. Delete `escapeHtml`. No `innerHTML` left
   (`grep -c innerHTML` = 0 is a test).
3. Styles: two options. (a) Move each `<style>` block to a static CSS file. (b) Keep the inline blocks and allow
   them by hash: compute `sha256` of each style block once at import time and send
   `style-src 'self' 'sha256-...'`. (b) is fewer moving parts but couples the header to the exact text; (a) is
   cleaner. Recommend (a) for `/admin` (`/admin/admin.css`) and the same for the student pages.
4. Student pages need a static path students can reach (not `/admin`). Options: a new engine prefix such as
   `/_dojo/` served by the allocator (add to `ENGINE_PREFIXES`), or drop the `onsubmit` guard and use style
   hashes so the student pages need no external file at all. (Open question 3.) The guard is cosmetic: `/assign`
   is idempotent per cookie and rate-limited since T3.4.
5. Header on every `send_html` response: `Content-Security-Policy: default-src 'self'; script-src 'self';
   style-src 'self'; img-src 'self'; frame-src 'self'; frame-ancestors 'self'; object-src 'none';
   base-uri 'none'; form-action 'self'`. (`default-src` doesn't cover `form-action`/`frame-ancestors`, so list
   them.) Inline SVG icons in the DOM are fine under this policy. The static files are served with
   `Cache-Control: no-store` or a short max-age, and `X-Content-Type-Options: nosniff`.
6. Keep the allocator single-threaded rules: static files read once at start into memory (no disk I/O per
   request), no Docker call involved. The portal is polled, so serving from memory matters.

### What could break
- `/admin` iframes: `frame-src 'self'` allows `/ide/`, `/term/`, `/forgejo-login`, `/slides/`, `/admin/watch/..`
  and module tabs (their `src` is checked same-origin by the renderer). The iframes' own content is governed by
  its own headers, not this CSP. If a module tab ever points at another origin, it would break: none do.
- `frame-ancestors 'self'`: `/admin` is the top-level page, nothing frames it; the student landing page is not
  framed either. Check the home deployment behind the user's home-lab Caddy (`--env home`) isn't framing it.
- Any forgotten inline handler or `style=` attribute silently stops working: Playwright must collect
  `console` CSP violations on `/`, `/admin`, name form, busy and full pages.
- The Release unused / Release / password buttons (T3.4, not yet browser-tested) move with the script.
- Allocator image rebuild affects every workshop; can't build while the P3 stack runs (shared image tags).

### Verify
- `curl -si` (with class/facilitator basic auth through the gateway) shows the header on `/` and `/admin`.
- Playwright (`mcr.microsoft.com/playwright/python:v1.55.0-noble`, `--network host`, `http_credentials`): zero
  `securitypolicyviolation`/console CSP errors on `/`, the name form submit, `/admin`; every `/admin` tab frames
  (IDE, Terminal, Forgejo, Slides, plus a module tab, e.g. vault's Runners/Audit/Apps); roster tile appears
  within one refresh after a student joins; a display name of `<img src=x onerror=alert(1)>` renders as text;
  Release, Release unused and password reveal still work.
- `python3 -B -m pytest engine/allocator/tests` (render_extensions tests if `ENGINE_PREFIXES` changes).

### Scope / overlap / model
- Scope: **[ENGINE, ask]**. Workshop-agnostic by nature.
- Overlaps P3 live test #5 (T3.4: Release unused in a real browser, `/auth-check` latency, vault gateway
  regression) directly: same file and same buttons. Must wait until test #5 has passed, otherwise a failure can't
  be attributed. Building needs the machine free (every workshop uses the allocator image).
- Model: **sonnet** (mechanical refactor with a clear spec); give it the line refs above.

---

## T4.3 (FIND-12, Low) [MODULE] + [WORKSHOP] + [ENGINE, ask]: rate limits and shared pools

Four independent pieces; they can be split into T4.3a-d and committed separately.

### T4.3a OpenBao rate-limit quota per student namespace [WORKSHOP] (+ [MODULE] policy)
- Files: `workshops/vault-fundamentals/compose/openbao-setup.d/10-tenancy.sh:28-31` (the per-student namespace
  loop): add `bao write sys/quotas/rate-limit/student-$s path="students/$s/" rate=<N> interval=1s` (idempotent:
  a write replaces). `modules/openbao/setup/policies/provisioner.hcl`: add
  `path "sys/quotas/rate-limit/*" { capabilities = ["create","read","update","delete","list"] }` (setup runs as
  the provisioner after root is revoked). dojo-introduction uses openbao too: check whether it has its own tenancy
  hook and whether it needs the same.
- Could break: rate too low trips the labs' own loops and `--test` bots (all bot traffic is also per namespace, so
  one student can't starve another, which is the point). Shared paths in the root namespace (`secret/`, auth
  login) are not per student; a root-level quota would throttle the whole class, so don't add one.
  Confirm OpenBao 2.7.0 supports rate-limit quotas on namespace paths (it inherited Vault OSS quotas; verify with
  `bao read sys/quotas/config` and a 1000-request loop).
- Verify: loop 1000 `bao kv get` in student01's namespace → 429s; student02 at the same time → 200.
  `tests/tenancy.sh`, `labs_5_7.sh`, `e2e.sh`.

### T4.3b app-db connection limits [WORKSHOP]
- File: `workshops/vault-fundamentals/compose/app-db/init.sh:23-30`.
- Plan says `CONNECTION LIMIT 5` per student role, but the apps log in as **short-lived dynamic roles** the vault
  creates (creation statements are written by students in lab 12), so a per-role limit on `vault_<s>` doesn't
  bound the app's logins. Better: `ALTER DATABASE app_${s} CONNECTION LIMIT <N>` (bounds every login to that
  student's DB) plus `ALTER ROLE vault_${s} CONNECTION LIMIT 3`.
- Shared pool maths: Postgres default `max_connections` = 100 (no override found in the overlay). 30 students + bots
  × N must stay under ~97. N=3 fits 30 students; with `--test 20` (50 accounts) it doesn't. Either raise
  `max_connections` (`command: postgres -c max_connections=...` in the overlay, plus `mem_limit` check) or keep N
  small. (Open question 5.)
- Verify: 10 parallel `psql` as one student's app role → the 4th+ fails with "too many connections for database";
  another student's still connect. `tests/labs_11_13.sh`.

### T4.3c token bucket per identity in CloudAPI and dns-api [MODULE]
- Files: `modules/dojo-cloud/cloud-api/server.py` (Handler at 319, ThreadingHTTPServer at 839; identity via
  `auth.py` `Auth`), `modules/dns-gate/gate/gate.py` (`identify()` 192 returns the Caller; Handler 292;
  ThreadingHTTPServer 369). Reuse the allocator's `AssignLimit` shape (`engine/allocator/server.py:199-214`) as a
  small per-key dict of buckets under a `threading.Lock` held only for the arithmetic (no I/O under it, same rule
  as cloud-api's `Readiness._lock` at 247). Reply 429 with `Retry-After`. Key = the authenticated identity
  (student name, `ci:<repo>` for ID tokens, `read` for the read key), never the source IP (shared netns).
  Env knobs in each `module.env` (e.g. `DNS_API_RATE`, `CLOUD_API_RATE`), no `${VAR:?}`.
- Could break: dnscontrol `push` and `terraform/tofu apply` burst many calls; bots at `--test 20`; DNS Apply CI
  (one `ci:` identity for the whole class repo) must not be throttled by students. Set a generous burst.
- Verify: unit tests next to each (`test_gate.py`, a new cloud-api test); live: a 1000-request loop from student01
  gets 429s while student02's `dnscontrol push` / `tofu apply` succeed.

### T4.3d terminal per-user nproc/as [ENGINE, ask]
- File: `engine/web-terminal/workspace-control.py`: the `su` launches at 280-281 (namespace holder), 328 (IDE),
  346 and 422 (ttyd), 365 (tmux list). Wrap the user side with `prlimit --nproc=<N> --as=<bytes> --` (the runner
  and app-host pattern), or write `/etc/security/limits.d/dojo.conf` and enable `pam_limits` for `su` in the
  terminal image (engine Dockerfile). prlimit is explicit and doesn't depend on PAM config; recommended.
- Limits: RLIMIT_NPROC counts per uid (each student has its own uid, and T2.3b already gives each a PID
  namespace), so a fork bomb stops at N for that student. RLIMIT_AS is per process, not per user: the container's
  shared `mem_limit` stays a shared pool. A real per-user memory cap needs per-user cgroups (cgroup delegation in
  rootless podman): out of scope, record as residual.
- Could break: code-server + extensions + language servers spawn many threads (threads count against NPROC) and
  reserve large virtual address space (node/V8 reserves GBs of AS: an `--as` limit easily kills code-server).
  Suggest nproc only (e.g. 512) and no `as`, or `as` only on the ttyd/tmux shell, not the IDE.
- Verify: `:(){ :|:& };:` as student01 in a terminal; student02's terminal and IDE stay responsive; facilitator
  watch tiles still update; `--test 3` bots finish.

### Scope / overlap / model
- Scope: a, b [WORKSHOP] (+ provisioner.hcl [MODULE]); c [MODULE]; d **[ENGINE, ask]**.
- Overlaps P3 live tests: c (dns-gate) with #1 cert-autorenewal, #2 dns-as-code, #3 dojo-introduction: wait for all
  three. c (cloud-api) with #3. a/b with #5 (vault checks). d (terminal image) with every test: wait for all.
- Model: **sonnet** for a, b, c (small, pattern-following). **opus** for d only if the user wants the cgroup route;
  sonnet for plain prlimit.

---

## Open questions for the user
1. Seccomp (T4.1c): a comment + inspect check (podman default is already applied), or pin an explicit profile path?
2. Harden `runner-pool-shim` in T4.1 too (not in the plan, same file, cheap)?
3. T4.2 engine go. And for the student pages: new engine static prefix (e.g. `/_dojo/`, added to
   `ENGINE_PREFIXES`) or style hashes + drop the cosmetic `onsubmit` guard (no new route)?
4. T4.3d engine go; nproc only, or also an address-space cap (risky for code-server)? Per-user cgroups out of scope?
5. app-db: per-database limit instead of per-role (the plan's wording), and raise `max_connections` for `--test 20`?
6. Rate numbers: OpenBao per-namespace rps, dns-api and CloudAPI burst/rate. Proposal: OpenBao 50 rps; dns-api burst
   60, 10/s; CloudAPI burst 60, 5/s; tune in the live pass.
7. dojo-introduction also runs app-host and openbao: include it in T4.1 and T4.3a (the plan names only vault)?

## Recommended order (after the P3 live tests and T3.6 docs, and the user's go for P4)
1. **T4.1** (module/workshop, Moderate, the biggest rating win): code while P3 tests run, build after tests 2/3/5.
   ~60-90k tokens (sonnet: edits ~15k; live pass with pool.sh + vault labs 8-13 + dns-as-code job ~50-70k).
2. **T4.3a + T4.3b + T4.3c** together (no engine; one combined live pass per "batch fixes, then test"):
   ~80-110k tokens (edits + unit tests ~30k; live loops in vault, dns-as-code, tofu-basics ~60-80k).
3. **T4.2** (engine, ask): ~60-80k tokens (refactor ~25k; Playwright CSP/iframe/roster pass ~35-50k).
4. **T4.3d** (engine, ask): ~30-50k tokens (edit ~8k; fork-bomb + IDE check on one stack ~25-40k). Could ride along
   in T4.2's live pass since both need an engine rebuild.
5. **T4.4** docs + §8 entry: ~15k tokens.
Total ~250-350k tokens across P4.
