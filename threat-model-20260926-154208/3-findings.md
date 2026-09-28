# Security Findings

---

## Tier 1 — Direct Exposure (No Prerequisites)

### FIND-01: Default credentials and no brute-force limit on the public Basic Auth gate

| Attribute | Value |
|-----------|-------|
| SDL Bugbar Severity | Important |
| CVSS 4.0 | 9.5 (CVSS:4.0/AV:N/AC:L/AT:P/PR:N/UI:N/VC:H/VI:H/VA:L/SC:H/SI:H/SA:L) |
| CWE | [CWE-1392](https://cwe.mitre.org/data/definitions/1392.html): Use of Default Credentials |
| OWASP | A07:2025 – Authentication Failures |
| Exploitation Prerequisites | None |
| Exploitability Tier | Tier 1 — Direct Exposure |
| Remediation Effort | Low |
| Mitigation Type | Standard Mitigation |
| Component | Gateway |
| Related Threats | [T01.S1](2-stride-analysis.md#gateway), [T01.S2](2-stride-analysis.md#gateway), [T01.D](2-stride-analysis.md#gateway), [T05.E](2-stride-analysis.md#forgejo), [T06.D](2-stride-analysis.md#presentation), [T07.I](2-stride-analysis.md#runscript) |

#### Description

The gateway is the only published listener and protects every lab service with HTTP Basic Auth using two shared credentials (class and facilitator). `./run.sh setup --default` writes fixed, published values for every human credential: `admin`/`admin` for the facilitator, `student` for ttyd, `student123` for all students and `admin` for the Forgejo administrator. Caddy has no attempt limit, lockout or rate limiting, so an unauthenticated attacker who can reach the port (LAN or the home-lab `dojo.macleodtech.ca` deployment) can guess or brute-force the class credential and, with the default, the facilitator credential, which opens `/admin` and every student's workspace.

#### Evidence

**Prerequisite basis:** The gateway publishes `GATEWAY_LISTEN` (`engine/docker-compose.yml` gateway service) and `/slides` is the only unauthenticated route (`engine/gateway/Caddyfile`); the Component Exposure Table lists Gateway with prerequisite `None`.

- `engine/scripts/env-setup.sh:155-178`: `--default` sets `TTYD_PASSWORD=student`, `STUDENT_PASSWORD=student123`, `FACILITATOR_USERNAME=admin`, `FACILITATOR_PASSWORD=admin`, `FORGEJO_ADMIN_PASSWORD=admin`.
- `engine/gateway/Caddyfile`: `basic_auth` blocks with no `rate_limit` or equivalent directive.
- `engine/allocator/server.py:517`: allocator request logging is a no-op, so failed guesses leave no trail beyond Caddy's default logs.

#### Remediation

1. Make interactive setup (random passwords) the only path when `PUBLIC_BASE_URL` is not `localhost`, or have `run.sh` refuse to start with the known defaults outside localhost.
2. Add request/attempt rate limiting in front of Basic Auth (Caddy `rate_limit` plugin, or the home-lab reverse proxy / fail2ban on 401s).
3. Rotate the class credential per session.

#### Verification

Run `./run.sh setup --default` then `./run.sh <workshop> --env home` and confirm the start is refused; send 50 bad Basic Auth attempts and confirm HTTP 429 or a ban.

### FIND-02: Slides and lab copies served without authentication

| Attribute | Value |
|-----------|-------|
| SDL Bugbar Severity | Low |
| CVSS 4.0 | 6.9 (CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:L/VI:N/VA:N/SC:N/SI:N/SA:N) |
| CWE | [CWE-200](https://cwe.mitre.org/data/definitions/200.html): Exposure of Sensitive Information to an Unauthorized Actor |
| OWASP | A01:2025 – Broken Access Control |
| Exploitation Prerequisites | None |
| Exploitability Tier | Tier 1 — Direct Exposure |
| Remediation Effort | Low |
| Mitigation Type | Standard Mitigation |
| Component | Presentation |
| Related Threats | [T06.I](2-stride-analysis.md#presentation) |

#### Description

The Caddyfile's `@slides` matcher proxies `/slides/*` to the presentation service before the Basic Auth gate. Besides decks, the presentation root includes the git-ignored `content/slides/lab/*.md.txt` copies of every lab, which reveal internal hostnames, ports, lab flows and default values such as `workshop-not-a-secret`. Anyone reaching the gateway can read them and plan attacks before class.

#### Evidence

**Prerequisite basis:** `engine/gateway/Caddyfile` `@slides` route has no `basic_auth`; Presentation is `None` in the Component Exposure Table.

- `engine/gateway/Caddyfile`: `handle @slides { reverse_proxy presentation:... }` placed outside the authenticated block.
- `engine/run.sh`: copies `content/lab/*.md` to `content/slides/lab/*.md.txt` at start for the lab reader.

#### Remediation

Place `/slides` behind the shared class gate (keeping a public-deck allowlist if needed), or serve the lab copies only through an authenticated path.

#### Verification

`curl -i http://<host>/slides/lab/lab-01.md.txt` without credentials returns 401.

---

## Tier 2 — Conditional Risk (Authenticated / Single Prerequisite)

### FIND-03: One shared password for every student's Linux and Forgejo account enables cross-student impersonation

| Attribute | Value |
|-----------|-------|
| SDL Bugbar Severity | Critical |
| CVSS 4.0 | 9.3 (CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:H/VI:H/VA:L/SC:H/SI:H/SA:N) |
| CWE | [CWE-287](https://cwe.mitre.org/data/definitions/287.html): Improper Authentication |
| OWASP | A07:2025 – Authentication Failures |
| Exploitation Prerequisites | Authenticated User |
| Exploitability Tier | Tier 2 — Conditional Risk |
| Remediation Effort | Medium |
| Mitigation Type | Custom Mitigation |
| Component | WebTerminal |
| Related Threats | [T02.I](2-stride-analysis.md#allocator), [T04.S1](2-stride-analysis.md#webterminal), [T04.T](2-stride-analysis.md#webterminal), [T05.S](2-stride-analysis.md#forgejo), [T05.A](2-stride-analysis.md#forgejo), [T08.T](2-stride-analysis.md#cloudapi), [T10.S](2-stride-analysis.md#dojobroker), [T10.I](2-stride-analysis.md#dojobroker), [T11.S](2-stride-analysis.md#openbaobroker), [T11.I](2-stride-analysis.md#openbaobroker), [T12.S](2-stride-analysis.md#openbao), [T16.S](2-stride-analysis.md#apphost), [T23.I](2-stride-analysis.md#terminalhome), [T23.T](2-stride-analysis.md#terminalhome) |

#### Description

`entrypoint.sh` sets every `studentNN` Linux password to the same `STUDENT_PASSWORD`, and Forgejo bootstrap gives every student account the same password. The allocator displays that password on every student's landing page. Any student can therefore run `su - student07` in their terminal or sign in to Forgejo as student07. Every per-student control downstream trusts those identities: the Dojo Cloud and OpenBao brokers bind credentials to the caller's uid via `SO_PEERCRED`, OpenBao OIDC and AppHost deploys trust the Forgejo identity, and home directories hold `~/.vault-token` and git credentials. One student can read and modify another's secrets, cloud resources, repositories and deployed apps. The broker, OpenBao namespace and AppHost ownership controls are well built; the shared password bypasses all of them.

#### Evidence

**Prerequisite basis:** Requires only the shared class credential and a claimed slot (Authenticated User); `su` is available in the Debian bookworm terminal image.

- `engine/web-terminal/entrypoint.sh:206`: `echo "$username:$student_password" | chpasswd` for every student.
- `engine/allocator/server.py:694`: landing page renders `STUDENT_PASSWORD` to each student.
- `modules/dojo-cloud/terminal/dojo-broker.py` and `modules/openbao/terminal/openbao-broker.py`: identity from `SO_PEERCRED` uid.
- Existing controls (mitigated threats referencing this finding): CloudAPI subscription ownership checks and AppHost repo-owner slot binding are correct once identity is sound.

#### Remediation

1. Generate a random password per student at slot assignment, show it only to that student, and set it for both Linux and Forgejo.
2. Alternatively lock student Linux passwords (`passwd -l`) since code-server/ttyd already run as the user, removing `su` as a path.
3. Set student home directories to `0700`.

#### Verification

From student01's terminal, `su - student02` with the displayed password fails; Forgejo login as student02 with student01's password fails.

### FIND-04: Unauthenticated code-server and ttyd reachable from other containers on the lab network

| Attribute | Value |
|-----------|-------|
| SDL Bugbar Severity | Important |
| CVSS 4.0 | 8.8 (CVSS:4.0/AV:N/AC:L/AT:P/PR:L/UI:N/VC:H/VI:H/VA:L/SC:H/SI:H/SA:N) |
| CWE | [CWE-306](https://cwe.mitre.org/data/definitions/306.html): Missing Authentication for Critical Function |
| OWASP | A01:2025 – Broken Access Control |
| Exploitation Prerequisites | Authenticated User |
| Exploitability Tier | Tier 2 — Conditional Risk |
| Remediation Effort | Medium |
| Mitigation Type | Standard Mitigation |
| Component | WebTerminal |
| Related Threats | [T03.T](2-stride-analysis.md#workspacecontrol), [T04.S2](2-stride-analysis.md#webterminal), [T04.A](2-stride-analysis.md#webterminal), [T16.E](2-stride-analysis.md#apphost) |

#### Description

Per-student code-server instances run with `--bind-addr 0.0.0.0:{port} --auth none`, and ttyd has no authentication; the design relies on the gateway being the only client. The `DOJO_ISOLATION` iptables chain is attached only to `OUTPUT` inside the terminal container, so it stops students from reaching each other over loopback but does nothing for inbound connections from other containers. In vault-fundamentals, AppHost runs student `start.sh` code on `workshop_lab` with only user and PID namespaces (no network namespace), so a student's deployed app can connect to `web-terminal:9000-9899` and get another student's IDE and shell. The same applies to any student-controlled code on other `workshop_lab` services (runner jobs reaching OpenBao/app-host via runner_net are not on workshop_lab, but app-host is on both).

#### Evidence

**Prerequisite basis:** AppHost is on `workshop_lab` and `runner_net` (`workshops/vault-fundamentals/compose/docker-compose.override.yml:36-75`) and executes student code; any enrolled student can deploy (Authenticated User).

- `engine/web-terminal/workspace-control.py:227`: `--bind-addr 0.0.0.0:{port} --auth none`.
- `engine/web-terminal/entrypoint.sh:162-183`: `iptables -A OUTPUT -j DOJO_ISOLATION` with per-uid `--uid-owner` rules; no INPUT filtering.
- `workshops/vault-fundamentals/compose/app-host/apphost.py:388`: `unshare -U --map-current-user -p -f --mount-proc` (no `-n`).
- Existing control: `valid_username()` allowlist in workspace-control prevents command injection into `su`.

#### Remediation

1. Add an INPUT rule in the terminal container accepting 9000-9899 only from the gateway's address (resolved at start) and dropping the rest.
2. Give AppHost slots a network namespace with an egress allowlist (OpenBao, app-db).
3. Longer term, have the gateway inject a per-slot code-server password or use Unix sockets.

#### Verification

From an AppHost slot, `curl http://web-terminal:9001/` times out; the student's own IDE through the gateway still works.

### FIND-05: Pull-request workflows run student-modified code on a shared host runner trusted by dns-api

| Attribute | Value |
|-----------|-------|
| SDL Bugbar Severity | Important |
| CVSS 4.0 | 8.4 (CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:L/VI:H/VA:L/SC:N/SI:H/SA:N) |
| CWE | [CWE-284](https://cwe.mitre.org/data/definitions/284.html): Improper Access Control |
| OWASP | A01:2025 – Broken Access Control |
| Exploitation Prerequisites | Authenticated User |
| Exploitability Tier | Tier 2 — Conditional Risk |
| Remediation Effort | Medium |
| Mitigation Type | Redesign |
| Component | ForgejoRunner |
| Related Threats | [T05.T](2-stride-analysis.md#forgejo), [T17.T](2-stride-analysis.md#forgejorunner), [T17.I](2-stride-analysis.md#forgejorunner), [T17.E](2-stride-analysis.md#forgejorunner), [T18.S](2-stride-analysis.md#dnsapi) |

#### Description

In dns-as-code, `dns-preview.yml` runs on `pull_request` with `runs-on: host`, i.e. directly in the shared `forgejo-runner` container with the host executor. Students push branches to the shared organisation repository, so a pull request can change the workflow file and run arbitrary commands. dns-api treats any request whose source IP resolves to `forgejo-runner` as the CI pipeline and allows writes to the protected `dojo.test` zone, so a PR job can bypass review and change production-like DNS. Jobs also share one filesystem with the runner daemon and can read its registration file and tamper with later jobs.

#### Evidence

**Prerequisite basis:** Students have push rights to the shared repo in the Forgejo org (Authenticated User); dns-api identifies CI by `self.client_address[0] in CI.get()` (`gate.py:151`).

- `workshops/dns-as-code/content/sample-repo/.forgejo/workflows/dns-preview.yml:14-20`: `on: pull_request`, `runs-on: host`.
- `modules/forgejo-runner/runner/register.sh:68-79`: `host:host` label, `docker_host: "-"`.
- `workshops/dns-as-code/compose/dns-api/gate.py:40,72-95,151`: CI recognised by resolved IP of `CI_HOSTS`.
- Existing control: gate refuses all non-zone writes even from CI (`gate.py:98`).

#### Remediation

1. Require approval before running workflows from PRs, or have PR workflows execute from the base branch definition.
2. Replace IP trust with a per-run credential (Actions OIDC token verified by dns-api) and only for `push` to `main`.
3. Use ephemeral per-job runners (as runner-pool does).

#### Verification

Open a PR that edits `dns-preview.yml` to PATCH `dojo.test`; confirm the job does not run without approval and dns-api rejects the write.

### FIND-06: Runner pool and app-host run as root with default capabilities

| Attribute | Value |
|-----------|-------|
| SDL Bugbar Severity | Moderate |
| CVSS 4.0 | 7.3 (CVSS:4.0/AV:L/AC:H/AT:P/PR:L/UI:N/VC:H/VI:H/VA:L/SC:N/SI:N/SA:N) |
| CWE | [CWE-250](https://cwe.mitre.org/data/definitions/250.html): Execution with Unnecessary Privileges |
| OWASP | A02:2025 – Security Misconfiguration |
| Exploitation Prerequisites | Authenticated User |
| Exploitability Tier | Tier 2 — Conditional Risk |
| Remediation Effort | Medium |
| Mitigation Type | Standard Mitigation |
| Component | RunnerPool |
| Related Threats | [T14.T](2-stride-analysis.md#runnerpool), [T14.I](2-stride-analysis.md#runnerpool), [T14.E](2-stride-analysis.md#runnerpool), [T16.T](2-stride-analysis.md#apphost), [T16.I](2-stride-analysis.md#apphost) |

#### Description

The runner-pool supervisor and app-host containers run as `user: "0:0"` with default capabilities and no `no-new-privileges`. Student CI jobs and apps are isolated only by fresh Unix users inside unprivileged user and PID namespaces plus `prlimit`. A user-namespace or kernel escape (historically common) gives root over every job, other slots' tokens, the runner registration secrets and the app-host signing key. Existing controls (per-job user, private HOME/TMPDIR, cleanup, single-use registrations, token files `0400`) are sound at the Unix-permission layer.

#### Evidence

**Prerequisite basis:** Any student can trigger CI jobs and deploys (Authenticated User); exploitation needs a namespace escape (AC:H).

- `modules/runner-pool/compose.yml:42,80`: `user: "0:0"`.
- `workshops/vault-fundamentals/compose/docker-compose.override.yml:44`: app-host `user: "0:0"`.
- `workshops/vault-fundamentals/compose/app-host/apphost.py:388`: `prlimit ... unshare -U --map-current-user -p -f --mount-proc`.

#### Remediation

Add `cap_drop: [ALL]` with only the capabilities `unshare`/`setpriv` need, `security_opt: [no-new-privileges:true]`, a seccomp profile, and consider a per-job container (runner `docker`/`podman` backend) for stronger isolation.

#### Verification

`podman inspect` of runner-pool and app-host shows dropped capabilities and `no-new-privileges`; labs 7-11 tests still pass.

### FIND-07: Slot exhaustion and head-of-line blocking in the single-threaded allocator

| Attribute | Value |
|-----------|-------|
| SDL Bugbar Severity | Moderate |
| CVSS 4.0 | 7.1 (CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:N) |
| CWE | [CWE-770](https://cwe.mitre.org/data/definitions/770.html): Allocation of Resources Without Limits or Throttling |
| OWASP | A06:2025 – Insecure Design |
| Exploitation Prerequisites | Authenticated User |
| Exploitability Tier | Tier 2 — Conditional Risk |
| Remediation Effort | Medium |
| Mitigation Type | Custom Mitigation |
| Component | Allocator |
| Related Threats | [T01.A](2-stride-analysis.md#gateway), [T02.D1](2-stride-analysis.md#allocator), [T02.D2](2-stride-analysis.md#allocator) |

#### Description

Any holder of the shared class credential can POST `/assign` without a cookie as often as they like; each request claims a new free slot, so a script can take every slot and lock the class out. The allocator is intentionally a single-threaded `HTTPServer` with a 10-second socket timeout, and it serves `/auth-check` for every proxied request; a few clients holding connections open stall authentication for the whole class. Leaked class credentials (shared by email or slides) make this reachable by non-attendees.

#### Evidence

**Prerequisite basis:** `/assign` requires only gateway Basic Auth (`engine/allocator/server.py:1402-1471`); Allocator is `Authenticated User` in the exposure table.

- `engine/allocator/server.py:1410-1471`: `/assign` mints a new slot and cookie per request with no per-client cap.
- `engine/allocator/server.py:4,515`: single-threaded `HTTPServer`, `timeout = 10`.

#### Remediation

1. Cap assignments per Basic-Auth session or require a facilitator-issued join code.
2. Add `/admin` bulk release and a slot-reservation limit.
3. Put gateway-side connection/request limits in front of the allocator and lower its socket timeout.

#### Verification

Script 40 cookie-less `/assign` POSTs and confirm only the cap is granted; hold 5 idle connections and confirm `/auth-check` latency stays under a second.

### FIND-08: Credentials and session cookies in cleartext when served over HTTP

| Attribute | Value |
|-----------|-------|
| SDL Bugbar Severity | Moderate |
| CVSS 4.0 | 6.0 (CVSS:4.0/AV:A/AC:L/AT:P/PR:N/UI:N/VC:H/VI:L/VA:N/SC:N/SI:N/SA:N) |
| CWE | [CWE-319](https://cwe.mitre.org/data/definitions/319.html): Cleartext Transmission of Sensitive Information |
| OWASP | A04:2025 – Cryptographic Failures |
| Exploitation Prerequisites | Internal Network |
| Exploitability Tier | Tier 2 — Conditional Risk |
| Remediation Effort | Low |
| Mitigation Type | Standard Mitigation |
| Component | Gateway |
| Related Threats | [T01.T](2-stride-analysis.md#gateway), [T01.I](2-stride-analysis.md#gateway), [T02.S2](2-stride-analysis.md#allocator) |

#### Description

When `PUBLIC_BASE_URL` is `http://` (the default `localhost:8080`, and LAN classroom use), Basic Auth credentials, the allocator session cookie and all lab traffic cross the network unencrypted. The cookie gets `Secure` only when the public URL is HTTPS. An attacker on the same Wi-Fi or LAN can capture the class or facilitator credential and hijack sessions.

#### Evidence

**Prerequisite basis:** Requires a position on the network path between students and the gateway (Internal Network).

- `engine/allocator/server.py:40,1469-1471`: `Secure` added only for HTTPS public URLs.
- `engine/.env` `PUBLIC_BASE_URL` / `GATEWAY_LISTEN` defaults to plain HTTP on :8080.

#### Remediation

Serve HTTPS for any non-localhost class (Caddy automatic TLS or the internal CA), add HSTS, and have `run.sh` warn when a non-localhost URL uses `http://`.

#### Verification

Browse the class URL and confirm HTTPS with HSTS; the `Set-Cookie` header includes `Secure`.

### FIND-09: Shared ACME CA with a published default password issues certificates for other students' names

| Attribute | Value |
|-----------|-------|
| SDL Bugbar Severity | Moderate |
| CVSS 4.0 | 6.0 (CVSS:4.0/AV:N/AC:L/AT:P/PR:L/UI:N/VC:L/VI:H/VA:N/SC:L/SI:L/SA:N) |
| CWE | [CWE-1392](https://cwe.mitre.org/data/definitions/1392.html): Use of Default Credentials |
| OWASP | A07:2025 – Authentication Failures |
| Exploitation Prerequisites | Authenticated User |
| Exploitability Tier | Tier 2 — Conditional Risk |
| Remediation Effort | Medium |
| Mitigation Type | Standard Mitigation |
| Component | StepCA |
| Related Threats | [T21.S](2-stride-analysis.md#stepca), [T21.I](2-stride-analysis.md#stepca) |

#### Description

The cert-autorenewal step-ca uses `STEP_CA_PASSWORD` defaulting to the published `workshop-not-a-secret` for both the CA key and the `admin` JWK provisioner, and runs an open ACME provisioner. Combined with the shared PowerDNS key (FIND-11), any student can pass dns-01 or http-01 for another student's hostname and obtain a valid certificate, or use the admin provisioner password to sign arbitrary certificates within the lab trust store.

#### Evidence

**Prerequisite basis:** step-ca listens on `workshop_lab`, reachable from every student terminal (Authenticated User).

- `workshops/cert-autorenewal/compose/docker-compose.override.yml:100`: `STEP_CA_PASSWORD=${STEP_CA_PASSWORD:-workshop-not-a-secret}`.
- `workshops/cert-autorenewal/compose/step-ca/entrypoint.sh:16,45-49`: same password file for CA and `admin` provisioner, `--acme`.

#### Remediation

Generate `STEP_CA_PASSWORD` in `env-setup.sh` and never give it to students; add per-student name constraints or ACME EAB per student.

#### Verification

`grep STEP_CA_PASSWORD engine/.env` shows a random value; a student cannot obtain a certificate for another student's hostname.

### FIND-10: Other students' command lines, including lab secrets, visible through /proc

| Attribute | Value |
|-----------|-------|
| SDL Bugbar Severity | Moderate |
| CVSS 4.0 | 5.7 (CVSS:4.0/AV:L/AC:L/AT:P/PR:L/UI:N/VC:H/VI:N/VA:N/SC:N/SI:N/SA:N) |
| CWE | [CWE-214](https://cwe.mitre.org/data/definitions/214.html): Invocation of Process Using Visible Sensitive Information |
| OWASP | A02:2025 – Security Misconfiguration |
| Exploitation Prerequisites | Authenticated User |
| Exploitability Tier | Tier 2 — Conditional Risk |
| Remediation Effort | Medium |
| Mitigation Type | Standard Mitigation |
| Component | WebTerminal |
| Related Threats | [T04.I](2-stride-analysis.md#webterminal) |

#### Description

All students share one container and PID namespace, and `/proc` is not mounted with `hidepid`, so `ps aux` or `/proc/<pid>/cmdline` shows every process's arguments. Several labs pass secrets as arguments (for example `bao kv put ... db_password=...`, `curl -H 'X-Vault-Token: ...'`), which other students can harvest while they run.

#### Evidence

**Prerequisite basis:** Any student shell in the shared web-terminal container (Authenticated User).

- `engine/web-terminal/entrypoint.sh`: no `hidepid` remount; the vault-fundamentals `PLAN.md` notes that rootless podman cannot remount `/proc` with `hidepid`.
- `workshops/vault-fundamentals/content/lab/*.md`: `bao kv put` with inline secret values.

#### Remediation

Teach and use stdin/`@file` input for secrets in labs (`bao kv put path value=-`); run each student shell in its own PID namespace (as runner-pool and AppHost already do) or use `--security-opt proc-opts=hidepid=2` where supported.

#### Verification

While student01 runs a long `bao` command, `ps aux` in student02's terminal does not show its arguments.

### FIND-11: Shared DNS API key lets any student change or squat another student's zone

| Attribute | Value |
|-----------|-------|
| SDL Bugbar Severity | Moderate |
| CVSS 4.0 | 5.3 (CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:N/VI:L/VA:L/SC:N/SI:N/SA:N) |
| CWE | [CWE-639](https://cwe.mitre.org/data/definitions/639.html): Authorization Bypass Through User-Controlled Key |
| OWASP | A01:2025 – Broken Access Control |
| Exploitation Prerequisites | Authenticated User |
| Exploitability Tier | Tier 2 — Conditional Risk |
| Remediation Effort | Medium |
| Mitigation Type | Custom Mitigation |
| Component | DNSAPI |
| Related Threats | [T18.T](2-stride-analysis.md#dnsapi), [T18.E](2-stride-analysis.md#dnsapi), [T18.A](2-stride-analysis.md#dnsapi) |

#### Description

In dns-as-code every terminal uses the same public key `workshop-not-a-secret`; dns-api swaps it for the real key and blocks only the protected zone. It cannot tell students apart, so any student can create, edit or delete `<other>.dojo.test`, or create it first. In cert-autorenewal students receive the real PowerDNS key directly (default `workshop-not-a-secret`) and there is no gate at all.

#### Evidence

**Prerequisite basis:** dns-api is on `workshop_lab` (Authenticated User).

- `workshops/dns-as-code/compose/dns-api/gate.py:38,67`: single `PUBLIC_KEY`, `zone_allowed_for_students()` checks only the protected zone.
- `workshops/dns-as-code/compose/terminal/start.d/90-my-zone.sh:53`: same key for every student.
- `workshops/cert-autorenewal/compose/docker-compose.override.yml:60,85`: `PDNS_AUTH_API_KEY=${POWERDNS_API_KEY:-workshop-not-a-secret}`.
- Existing control: non-zone writes refused (`gate.py:98`).

#### Remediation

Issue per-student keys (a broker like Dojo Cloud's, or keys derived with HMAC from the username) and check zone ownership in the gate; pre-create each student's zone; put a gate in front of cert-autorenewal's PowerDNS too.

#### Verification

With student01's key, a PATCH to `student02.dojo.test` returns 403.

### FIND-12: No request rate limiting and shared resource pools on internal lab services

| Attribute | Value |
|-----------|-------|
| SDL Bugbar Severity | Low |
| CVSS 4.0 | 5.3 (CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:N/VI:N/VA:L/SC:N/SI:N/SA:L) |
| CWE | [CWE-770](https://cwe.mitre.org/data/definitions/770.html): Allocation of Resources Without Limits or Throttling |
| OWASP | A06:2025 – Insecure Design |
| Exploitation Prerequisites | Authenticated User |
| Exploitability Tier | Tier 2 — Conditional Risk |
| Remediation Effort | Medium |
| Mitigation Type | Standard Mitigation |
| Component | CloudAPI |
| Related Threats | [T04.D](2-stride-analysis.md#webterminal), [T05.D](2-stride-analysis.md#forgejo), [T08.D](2-stride-analysis.md#cloudapi), [T08.A](2-stride-analysis.md#cloudapi), [T09.D](2-stride-analysis.md#cloudhost), [T12.D](2-stride-analysis.md#openbao), [T14.D](2-stride-analysis.md#runnerpool), [T14.A](2-stride-analysis.md#runnerpool), [T15.D](2-stride-analysis.md#runnercontroller), [T16.D](2-stride-analysis.md#apphost), [T17.D](2-stride-analysis.md#forgejorunner), [T18.D](2-stride-analysis.md#dnsapi), [T19.D](2-stride-analysis.md#powerdns), [T21.D](2-stride-analysis.md#stepca), [T23.D](2-stride-analysis.md#terminalhome), [T26.D](2-stride-analysis.md#postgresql) |

#### Description

Internal services (CloudAPI, dns-api, PowerDNS, step-ca, OpenBao, app-db, Forgejo, runners) have no per-client request limits, and resources are pooled per container: the web terminal's 4 GiB and PID limit is shared by the whole class. One student can degrade the lab for everyone. Existing quotas (Dojo Cloud 2 groups and CPU/memory caps, per-job and per-slot `prlimit`, per-container PIDs in CloudHost) mitigate part of this.

#### Evidence

**Prerequisite basis:** All listed services are on `workshop_lab` or `runner_net` (Authenticated User).

- `engine/docker-compose.yml` web-terminal `mem_limit`/`pids_limit`.
- `modules/dojo-cloud/cloud-api/`: quotas but no rate limiting.
- `modules/openbao/config.hcl`: no rate-limit quota.
- Existing controls: `prlimit` in `modules/runner-pool` and `apphost.py:388`; CloudHost per-container PID/CPU/memory caps.

#### Remediation

Add OpenBao rate-limit quotas per namespace, per-client limits in CloudAPI/dns-api, Postgres per-role `CONNECTION LIMIT`, and per-user cgroup or ulimit caps in the terminal.

#### Verification

A loop of 1000 requests from one student is throttled (429) while other students' requests succeed.

### FIND-13: Identity and control-plane actions are not logged

| Attribute | Value |
|-----------|-------|
| SDL Bugbar Severity | Low |
| CVSS 4.0 | 5.3 (CVSS:4.0/AV:N/AC:L/AT:N/PR:L/UI:N/VC:N/VI:L/VA:N/SC:N/SI:N/SA:N) |
| CWE | [CWE-778](https://cwe.mitre.org/data/definitions/778.html): Insufficient Logging |
| OWASP | A09:2025 – Security Logging and Alerting Failures |
| Exploitation Prerequisites | Authenticated User |
| Exploitability Tier | Tier 2 — Conditional Risk |
| Remediation Effort | Low |
| Mitigation Type | Standard Mitigation |
| Component | Allocator |
| Related Threats | [T01.R](2-stride-analysis.md#gateway), [T02.R](2-stride-analysis.md#allocator), [T03.R](2-stride-analysis.md#workspacecontrol), [T04.R](2-stride-analysis.md#webterminal), [T08.R](2-stride-analysis.md#cloudapi), [T12.R](2-stride-analysis.md#openbao), [T18.R](2-stride-analysis.md#dnsapi) |

#### Description

The allocator, workspace-control and dns-api override `log_message` to discard request logs, and Caddy has no access log configured. Slot claims, releases, Forgejo SSO, watch sessions and zone changes leave no record, and all students share one source IP, so misuse cannot be attributed after the fact. OpenBao's file audit device (with the audit panel) is a good existing control for vault actions.

#### Evidence

**Prerequisite basis:** Actions are taken by enrolled students (Authenticated User).

- `engine/allocator/server.py:517`, `engine/web-terminal/workspace-control.py`, `workshops/dns-as-code/compose/dns-api/gate.py:124`: `def log_message(...): pass`.
- `engine/gateway/Caddyfile`: no `log` directive.
- Existing control: `modules/openbao/config.hcl:24-30` file audit device.

#### Remediation

Log a structured line per identity decision (slot id, account, action, target) in allocator, workspace-control and dns-api; enable Caddy access logs with the resolved `X-Auth-User`.

#### Verification

`podman logs allocator` shows an entry for each `/assign`, release and SSO login.

### FIND-14: Allocator pages lack CSP and frame-ancestors and use inline script

| Attribute | Value |
|-----------|-------|
| SDL Bugbar Severity | Low |
| CVSS 4.0 | 2.0 (CVSS:4.0/AV:N/AC:H/AT:P/PR:L/UI:A/VC:L/VI:L/VA:N/SC:N/SI:N/SA:N) |
| CWE | [CWE-1021](https://cwe.mitre.org/data/definitions/1021.html): Improper Restriction of Rendered UI Layers or Frames |
| OWASP | A02:2025 – Security Misconfiguration |
| Exploitation Prerequisites | Authenticated User |
| Exploitability Tier | Tier 2 — Conditional Risk |
| Remediation Effort | Medium |
| Mitigation Type | Standard Mitigation |
| Component | Allocator |
| Related Threats | [T02.T](2-stride-analysis.md#allocator), [T02.E](2-stride-analysis.md#allocator), [T02.A](2-stride-analysis.md#allocator), [T16.A](2-stride-analysis.md#apphost) |

#### Description

The landing and `/admin` pages are built with inline `<script>` and `innerHTML` and are served without `Content-Security-Policy` or `frame-ancestors`. Student-controlled display names are escaped with `escapeHtml()`, so no injection was found, but a future escaping mistake would run script in the facilitator's `/admin` context, and the pages can be framed. Module panels (Runners, audit, AppHost) already use a strict CSP with `textContent`. Existing controls also cover CSRF (`SameSite=Lax`, `X-Requested-With` on release) and open redirects (`local_path()`).

#### Evidence

**Prerequisite basis:** Display names are set by enrolled students (Authenticated User) and viewed by the facilitator.

- `engine/allocator/server.py:940-990`: inline script building roster rows with `innerHTML` and `escapeHtml()`.
- `engine/allocator/server.py:1469`: cookie `HttpOnly; SameSite=Lax`.

#### Remediation

Move allocator script to a static file, render roster fields with `textContent`, and send `Content-Security-Policy: default-src 'self'; frame-ancestors 'self'`.

#### Verification

Response headers on `/` and `/admin` include the CSP; browser console shows no CSP violations.

---

## Tier 3 — Defense-in-Depth (Prior Compromise / Host Access)

### FIND-15: Privileged Docker-in-Docker with a world-writable socket behind Dojo Cloud

| Attribute | Value |
|-----------|-------|
| SDL Bugbar Severity | Important |
| CVSS 4.0 | 8.7 (CVSS:4.0/AV:L/AC:L/AT:P/PR:H/UI:N/VC:H/VI:H/VA:H/SC:H/SI:H/SA:H) |
| CWE | [CWE-250](https://cwe.mitre.org/data/definitions/250.html): Execution with Unnecessary Privileges |
| OWASP | A02:2025 – Security Misconfiguration |
| Exploitation Prerequisites | CloudAPI Compromise |
| Exploitability Tier | Tier 3 — Defense-in-Depth |
| Remediation Effort | High |
| Mitigation Type | Redesign |
| Component | CloudHost |
| Related Threats | [T08.E](2-stride-analysis.md#cloudapi), [T09.T](2-stride-analysis.md#cloudhost), [T09.I](2-stride-analysis.md#cloudhost), [T09.E](2-stride-analysis.md#cloudhost) |

#### Description

CloudHost runs `docker:dind` with `privileged: true` and exposes its socket at mode `0666` on a volume shared with CloudAPI. Anyone who compromises CloudAPI (or any other container that mounts the volume) controls a root-equivalent daemon on the lab host and can escape to the host kernel. The compose file acknowledges the risk; the fixed create template, image allowlist, `CapDrop: ALL`, `--icc=false` and per-container limits are good existing controls for what students can request.

#### Evidence

**Prerequisite basis:** Requires code execution in CloudAPI first (`modules/dojo-cloud/compose.yml:13-64`; students reach only the HTTP API).

- `modules/dojo-cloud/compose.yml:13,33`: `privileged: true`.
- `modules/dojo-cloud/cloud-host/entrypoint.sh:45`: `chmod 0666 /run/cloud/docker.sock`.
- `modules/dojo-cloud/cloud-host/Dockerfile:16`: `FROM docker.io/library/docker:dind` (unpinned).

#### Remediation

Use rootless DinD (`docker:dind-rootless`) or sysbox; set the socket to `0660` with a group only CloudAPI has; pin the image by digest.

#### Verification

`podman inspect cloud-host` shows `Privileged=false`; socket permissions are `srw-rw----`.

### FIND-16: Master secrets shared across many containers as plaintext environment variables

| Attribute | Value |
|-----------|-------|
| SDL Bugbar Severity | Moderate |
| CVSS 4.0 | 8.5 (CVSS:4.0/AV:L/AC:L/AT:P/PR:H/UI:N/VC:H/VI:H/VA:N/SC:H/SI:H/SA:N) |
| CWE | [CWE-522](https://cwe.mitre.org/data/definitions/522.html): Insufficiently Protected Credentials |
| OWASP | A04:2025 – Cryptographic Failures |
| Exploitation Prerequisites | AppHost Compromise |
| Exploitability Tier | Tier 3 — Defense-in-Depth |
| Remediation Effort | High |
| Mitigation Type | Redesign |
| Component | EnvFile |
| Related Threats | [T02.S1](2-stride-analysis.md#allocator), [T03.S](2-stride-analysis.md#workspacecontrol), [T03.E](2-stride-analysis.md#workspacecontrol), [T08.S](2-stride-analysis.md#cloudapi), [T15.S](2-stride-analysis.md#runnercontroller), [T15.I](2-stride-analysis.md#runnercontroller), [T19.S](2-stride-analysis.md#powerdns), [T20.S](2-stride-analysis.md#powerdnsadmin), [T22.I](2-stride-analysis.md#envfile), [T22.T](2-stride-analysis.md#envfile), [T24.I](2-stride-analysis.md#forgejodata), [T26.S](2-stride-analysis.md#postgresql) |

#### Description

Every credential lives in plaintext in `engine/.env` and is passed into containers as environment variables. `GATEWAY_TOKEN` is shared by the gateway, allocator, CloudAPI, the runner controller, app-host and the dns-admin panel, and the PowerDNS API key is derived from it; `CONTROL_TOKEN` gives full control of workspaces; `FORGEJO_ADMIN_PASSWORD` is given to the allocator and the runner controller. Compromising any single one of these services yields the facilitator trust anchor (forged `X-Auth-User` for every service) and Forgejo admin. Existing controls: the gateway token and control token are compared in constant time, PowerDNS-Admin is isolated on `dns_admin_net`, app-db's superuser password is discarded after rotation.

#### Evidence

**Prerequisite basis:** Requires compromise of one module container or host access to `engine/.env` (Tier 3).

- `engine/docker-compose.yml`: `GATEWAY_TOKEN`, `CONTROL_TOKEN`, `FORGEJO_ADMIN_PASSWORD` in multiple `environment:` blocks.
- `modules/runner-pool/compose.yml`, `workshops/vault-fundamentals/compose/docker-compose.override.yml`, `modules/dojo-cloud/compose.yml`: same `GATEWAY_TOKEN`.
- `workshops/dns-as-code/workshop.env`: PowerDNS key derived from `GATEWAY_TOKEN`.

#### Remediation

Give each service its own gateway secret (Caddy can set a per-upstream `X-Gateway-Token`), replace the Forgejo admin password with scoped tokens, use compose `secrets:` files with `0400`, and `chmod 600 engine/.env`.

#### Verification

`podman inspect app-host` shows no `GATEWAY_TOKEN` usable at CloudAPI; each service rejects another service's token.

### FIND-17: Single unseal share and long-lived root-equivalent provisioner token on the setup volume

| Attribute | Value |
|-----------|-------|
| SDL Bugbar Severity | Moderate |
| CVSS 4.0 | 8.4 (CVSS:4.0/AV:L/AC:L/AT:N/PR:H/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N) |
| CWE | [CWE-522](https://cwe.mitre.org/data/definitions/522.html): Insufficiently Protected Credentials |
| OWASP | A04:2025 – Cryptographic Failures |
| Exploitation Prerequisites | Host/OS Access |
| Exploitability Tier | Tier 3 — Defense-in-Depth |
| Remediation Effort | Medium |
| Mitigation Type | Standard Mitigation |
| Component | OpenBaoSetup |
| Related Threats | [T12.E](2-stride-analysis.md#openbao), [T13.I](2-stride-analysis.md#openbaosetup), [T13.E](2-stride-analysis.md#openbaosetup), [T25.I](2-stride-analysis.md#openbaosetupvolume) |

#### Description

`setup.sh` initialises OpenBao with one key share, stores the unseal key and a renewable provisioner token on the `openbao_setup` volume and auto-unseals forever. The provisioner policy manages namespaces, auth methods and policies, which is root-equivalent. Anyone with host or volume access can unseal and fully control the vault. The root token revocation and the per-student namespace plus templated policy design are good existing controls; the lab comment already names auto-unseal as the production pattern.

#### Evidence

**Prerequisite basis:** The setup volume is mounted only by `openbao-setup`; reaching it requires host or container-runtime access (Host/OS Access).

- `modules/openbao/setup/setup.sh:3-18`: one key share, unseal loop, provisioner token renewal.
- `modules/openbao/setup/policies/provisioner.hcl`: broad `sys/*` capabilities.

#### Remediation

Use transit or KMS auto-unseal (or Shamir with several shares for demonstrations), scope the provisioner policy to what the workshop scripts need, and revoke the provisioner token when setup finishes.

#### Verification

`bao token lookup` with the stored provisioner token fails after setup; the setup volume holds no unseal key.

### FIND-18: Base images pulled by mutable tags

| Attribute | Value |
|-----------|-------|
| SDL Bugbar Severity | Low |
| CVSS 4.0 | 7.5 (CVSS:4.0/AV:N/AC:H/AT:P/PR:H/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N) |
| CWE | [CWE-829](https://cwe.mitre.org/data/definitions/829.html): Inclusion of Functionality from Untrusted Control Sphere |
| OWASP | A03:2025 – Software Supply Chain Failures |
| Exploitation Prerequisites | RunScript Compromise |
| Exploitability Tier | Tier 3 — Defense-in-Depth |
| Remediation Effort | Low |
| Mitigation Type | Standard Mitigation |
| Component | RunScript |
| Related Threats | [T07.T](2-stride-analysis.md#runscript), [T07.E](2-stride-analysis.md#runscript), [T19.T](2-stride-analysis.md#powerdns), [T21.T](2-stride-analysis.md#stepca) |

#### Description

Several images are built from or run with mutable tags (`step-ca:latest`, `pdns-auth-49:latest`, `docker:dind`, `caddy:2-alpine`, `python:3.12-alpine`, `forgejo/runner:13`). A compromised or broken upstream push would be pulled at the next build and run inside the lab, several with root or `privileged`. OpenBao, Postgres and PowerDNS-Admin are already pinned by digest, and terminal tools are version-pinned and sha256-verified. `render_extensions.py`'s fixed gate templates are an existing control against manifest injection.

#### Evidence

**Prerequisite basis:** Requires an upstream registry or maintainer compromise affecting what `run.sh` builds (RunScript Compromise).

- `workshops/cert-autorenewal/compose/step-ca/Dockerfile:15`, `workshops/dns-as-code/compose/docker-compose.override.yml:39`, `modules/dojo-cloud/cloud-host/Dockerfile:16`, `engine/gateway/Dockerfile:1`, `engine/allocator/Dockerfile:1`.
- Pinned examples: `modules/openbao/compose.yml:12`, `modules/dns-ui/dns-admin/Dockerfile:11`.

#### Remediation

Pin every base and service image by digest and refresh them deliberately (Renovate or a script).

#### Verification

`grep -rn 'FROM\|image:' engine modules workshops` shows `@sha256:` on every external image.

### FIND-19: Plaintext internal transport to OpenBao and PostgreSQL

| Attribute | Value |
|-----------|-------|
| SDL Bugbar Severity | Low |
| CVSS 4.0 | 2.0 (CVSS:4.0/AV:A/AC:H/AT:P/PR:H/UI:N/VC:L/VI:L/VA:N/SC:N/SI:N/SA:N) |
| CWE | [CWE-319](https://cwe.mitre.org/data/definitions/319.html): Cleartext Transmission of Sensitive Information |
| OWASP | A04:2025 – Cryptographic Failures |
| Exploitation Prerequisites | WebTerminal Compromise |
| Exploitability Tier | Tier 3 — Defense-in-Depth |
| Remediation Effort | Medium |
| Mitigation Type | Standard Mitigation |
| Component | OpenBao |
| Related Threats | [T12.I1](2-stride-analysis.md#openbao), [T12.I2](2-stride-analysis.md#openbao), [T26.I](2-stride-analysis.md#postgresql) |

#### Description

OpenBao listens with `tls_disable = true`, and app-db accepts plaintext connections, so tokens, secrets and database credentials cross `workshop_lab` and `runner_net` unencrypted. Sniffing a bridge network requires root in a container on it, so this is defence in depth. The audit device writes token accessors in clear (`hmac_accessor = false`) by design so the audit panel can trace leaks; tokens and values stay HMAC'd.

#### Evidence

**Prerequisite basis:** Capturing bridge traffic requires root/`NET_RAW` in a lab container (WebTerminal Compromise).

- `modules/openbao/config.hcl:14`: `tls_disable = true`.
- `modules/openbao/config.hcl:24-30`: `hmac_accessor = "false"`.
- `workshops/vault-fundamentals/compose/docker-compose.override.yml:82`: postgres without TLS settings.

#### Remediation

Issue internal certificates at start (the stack already builds CAs for Dojo Cloud) and enable TLS on OpenBao and app-db; keep `hmac_accessor = false` only if the panel needs it.

#### Verification

`bao status` over `https://openbao:8200` succeeds with the lab CA; `psql "sslmode=require"` connects.

---

## Threat Coverage Verification

| Threat ID | Finding ID | Status |
|-----------|------------|--------|
| T01.S1 | FIND-01 | ✅ Covered (FIND-01) |
| T01.S2 | FIND-01 | ✅ Mitigated (FIND-01) |
| T01.T | FIND-08 | ✅ Covered (FIND-08) |
| T01.R | FIND-13 | ✅ Covered (FIND-13) |
| T01.I | FIND-08 | ✅ Covered (FIND-08) |
| T01.D | FIND-01 | ✅ Covered (FIND-01) |
| T01.A | FIND-07 | ✅ Covered (FIND-07) |
| T02.S1 | FIND-16 | ✅ Mitigated (FIND-16) |
| T02.S2 | FIND-08 | ✅ Covered (FIND-08) |
| T02.T | FIND-14 | ✅ Mitigated (FIND-14) |
| T02.R | FIND-13 | ✅ Covered (FIND-13) |
| T02.I | FIND-03 | ✅ Covered (FIND-03) |
| T02.D1 | FIND-07 | ✅ Covered (FIND-07) |
| T02.D2 | FIND-07 | ✅ Covered (FIND-07) |
| T02.E | FIND-14 | ✅ Mitigated (FIND-14) |
| T02.A | FIND-14 | ✅ Covered (FIND-14) |
| T03.S | FIND-16 | ✅ Mitigated (FIND-16) |
| T03.T | FIND-04 | ✅ Mitigated (FIND-04) |
| T03.R | FIND-13 | ✅ Covered (FIND-13) |
| T03.E | FIND-16 | ✅ Covered (FIND-16) |
| T04.S1 | FIND-03 | ✅ Covered (FIND-03) |
| T04.S2 | FIND-04 | ✅ Covered (FIND-04) |
| T04.T | FIND-03 | ✅ Covered (FIND-03) |
| T04.R | FIND-13 | ✅ Covered (FIND-13) |
| T04.I | FIND-10 | ✅ Covered (FIND-10) |
| T04.D | FIND-12 | ✅ Covered (FIND-12) |
| T04.A | FIND-04 | ✅ Covered (FIND-04) |
| T05.S | FIND-03 | ✅ Covered (FIND-03) |
| T05.T | FIND-05 | ✅ Covered (FIND-05) |
| T05.D | FIND-12 | ✅ Covered (FIND-12) |
| T05.E | FIND-01 | ✅ Covered (FIND-01) |
| T05.A | FIND-03 | ✅ Covered (FIND-03) |
| T06.I | FIND-02 | ✅ Covered (FIND-02) |
| T06.D | FIND-01 | ✅ Covered (FIND-01) |
| T07.T | FIND-18 | ✅ Mitigated (FIND-18) |
| T07.I | FIND-01 | ✅ Covered (FIND-01) |
| T07.E | FIND-18 | ✅ Covered (FIND-18) |
| T08.S | FIND-16 | ✅ Covered (FIND-16) |
| T08.T | FIND-03 | ✅ Mitigated (FIND-03) |
| T08.R | FIND-13 | ✅ Covered (FIND-13) |
| T08.D | FIND-12 | ✅ Covered (FIND-12) |
| T08.E | FIND-15 | ✅ Covered (FIND-15) |
| T08.A | FIND-12 | ✅ Mitigated (FIND-12) |
| T09.T | FIND-15 | ✅ Covered (FIND-15) |
| T09.I | FIND-15 | ✅ Mitigated (FIND-15) |
| T09.D | FIND-12 | ✅ Mitigated (FIND-12) |
| T09.E | FIND-15 | ✅ Covered (FIND-15) |
| T10.S | FIND-03 | ✅ Covered (FIND-03) |
| T10.I | FIND-03 | ✅ Mitigated (FIND-03) |
| T11.S | FIND-03 | ✅ Covered (FIND-03) |
| T11.I | FIND-03 | ✅ Mitigated (FIND-03) |
| T12.S | FIND-03 | ✅ Covered (FIND-03) |
| T12.R | FIND-13 | ✅ Mitigated (FIND-13) |
| T12.I1 | FIND-19 | ✅ Covered (FIND-19) |
| T12.I2 | FIND-19 | ✅ Covered (FIND-19) |
| T12.D | FIND-12 | ✅ Covered (FIND-12) |
| T12.E | FIND-17 | ✅ Mitigated (FIND-17) |
| T13.I | FIND-17 | ✅ Covered (FIND-17) |
| T13.E | FIND-17 | ✅ Covered (FIND-17) |
| T14.T | FIND-06 | ✅ Mitigated (FIND-06) |
| T14.I | FIND-06 | ✅ Mitigated (FIND-06) |
| T14.D | FIND-12 | ✅ Covered (FIND-12) |
| T14.E | FIND-06 | ✅ Covered (FIND-06) |
| T14.A | FIND-12 | ✅ Covered (FIND-12) |
| T15.S | FIND-16 | ✅ Mitigated (FIND-16) |
| T15.I | FIND-16 | ✅ Covered (FIND-16) |
| T15.D | FIND-12 | ✅ Covered (FIND-12) |
| T16.S | FIND-03 | ✅ Mitigated (FIND-03) |
| T16.T | FIND-06 | ✅ Mitigated (FIND-06) |
| T16.I | FIND-06 | ✅ Mitigated (FIND-06) |
| T16.D | FIND-12 | ✅ Covered (FIND-12) |
| T16.E | FIND-04 | ✅ Covered (FIND-04) |
| T16.A | FIND-14 | ✅ Mitigated (FIND-14) |
| T17.T | FIND-05 | ✅ Covered (FIND-05) |
| T17.I | FIND-05 | ✅ Covered (FIND-05) |
| T17.D | FIND-12 | ✅ Covered (FIND-12) |
| T17.E | FIND-05 | ✅ Covered (FIND-05) |
| T18.S | FIND-05 | ✅ Covered (FIND-05) |
| T18.T | FIND-11 | ✅ Covered (FIND-11) |
| T18.R | FIND-13 | ✅ Covered (FIND-13) |
| T18.D | FIND-12 | ✅ Covered (FIND-12) |
| T18.E | FIND-11 | ✅ Mitigated (FIND-11) |
| T18.A | FIND-11 | ✅ Covered (FIND-11) |
| T19.S | FIND-16 | ✅ Mitigated (FIND-16) |
| T19.T | FIND-18 | ✅ Covered (FIND-18) |
| T19.D | FIND-12 | ✅ Covered (FIND-12) |
| T20.S | FIND-16 | ✅ Mitigated (FIND-16) |
| T21.S | FIND-09 | ✅ Covered (FIND-09) |
| T21.I | FIND-09 | ✅ Covered (FIND-09) |
| T21.T | FIND-18 | ✅ Covered (FIND-18) |
| T21.D | FIND-12 | ✅ Covered (FIND-12) |
| T22.I | FIND-16 | ✅ Covered (FIND-16) |
| T22.T | FIND-16 | ✅ Covered (FIND-16) |
| T23.I | FIND-03 | ✅ Covered (FIND-03) |
| T23.T | FIND-03 | ✅ Covered (FIND-03) |
| T23.D | FIND-12 | ✅ Covered (FIND-12) |
| T24.I | FIND-16 | ✅ Covered (FIND-16) |
| T25.I | FIND-17 | ✅ Covered (FIND-17) |
| T26.S | FIND-16 | ✅ Mitigated (FIND-16) |
| T26.I | FIND-19 | ✅ Covered (FIND-19) |
| T26.D | FIND-12 | ✅ Covered (FIND-12) |
