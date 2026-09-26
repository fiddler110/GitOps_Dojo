# STRIDE + Abuse Cases — Threat Analysis

> This analysis uses the standard **STRIDE** methodology (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege) extended with **Abuse Cases** (business logic abuse, workflow manipulation, feature misuse). The "A" column in tables below represents Abuse — a supplementary category covering threats where legitimate features are misused for unintended purposes. This is distinct from Elevation of Privilege (E), which covers authorization bypass.

## Exploitability Tiers

Threats are classified into three exploitability tiers based on the prerequisites an attacker needs:

| Tier | Label | Prerequisites | Assignment Rule |
|------|-------|---------------|----------------|
| **Tier 1** | Direct Exposure | `None` | Exploitable by unauthenticated external attacker with NO prior access. The prerequisite field MUST say `None`. |
| **Tier 2** | Conditional Risk | Single prerequisite: `Authenticated User`, `Privileged User`, `Internal Network`, or single `{Boundary} Access` | Requires exactly ONE form of access. The prerequisite field has ONE item. |
| **Tier 3** | Defense-in-Depth | `Host/OS Access`, `Admin Credentials`, `{Component} Compromise`, `Physical Access`, or MULTIPLE prerequisites joined with `+` | Requires significant prior breach, infrastructure access, or multiple combined prerequisites. |

> In this lab every student shell shares the `workshop_lab` network, so "Authenticated User" (holding the shared class credential and a slot) is the floor for all internal services. See the Component Exposure Table in [0.1-architecture.md](0.1-architecture.md).

## Summary

| Component | Link | S | T | R | I | D | E | A | Total | T1 | T2 | T3 | Risk |
|-----------|------|---|---|---|---|---|---|---|-------|----|----|----|------|
| Gateway | [Link](#gateway) | 2 | 1 | 1 | 1 | 1 | 0 | 1 | 7 | 3 | 4 | 0 | High |
| Allocator | [Link](#allocator) | 2 | 1 | 1 | 1 | 2 | 1 | 1 | 9 | 0 | 9 | 0 | Critical |
| WorkspaceControl | [Link](#workspacecontrol) | 1 | 1 | 1 | 0 | 0 | 1 | 0 | 4 | 0 | 3 | 1 | Medium |
| WebTerminal | [Link](#webterminal) | 2 | 1 | 1 | 1 | 1 | 0 | 1 | 7 | 0 | 7 | 0 | Critical |
| Forgejo | [Link](#forgejo) | 1 | 1 | 0 | 0 | 1 | 1 | 1 | 5 | 0 | 5 | 0 | Critical |
| Presentation | [Link](#presentation) | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 2 | 2 | 0 | 0 | High |
| RunScript | [Link](#runscript) | 0 | 1 | 0 | 1 | 0 | 1 | 0 | 3 | 0 | 0 | 3 | High |
| CloudAPI | [Link](#cloudapi) | 1 | 1 | 1 | 0 | 1 | 1 | 1 | 6 | 0 | 4 | 2 | High |
| CloudHost | [Link](#cloudhost) | 0 | 1 | 0 | 1 | 1 | 1 | 0 | 4 | 0 | 0 | 4 | High |
| DojoBroker | [Link](#dojobroker) | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 2 | 0 | 2 | 0 | Critical |
| OpenBaoBroker | [Link](#openbaobroker) | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 2 | 0 | 2 | 0 | Critical |
| OpenBao | [Link](#openbao) | 1 | 0 | 1 | 2 | 1 | 1 | 0 | 6 | 0 | 4 | 2 | Critical |
| OpenBaoSetup | [Link](#openbaosetup) | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 2 | 0 | 0 | 2 | Medium |
| RunnerPool | [Link](#runnerpool) | 0 | 1 | 0 | 1 | 1 | 1 | 1 | 5 | 0 | 5 | 0 | Medium |
| RunnerController | [Link](#runnercontroller) | 1 | 0 | 0 | 1 | 1 | 0 | 0 | 3 | 0 | 2 | 1 | Medium |
| AppHost | [Link](#apphost) | 1 | 1 | 0 | 1 | 1 | 1 | 1 | 6 | 0 | 6 | 0 | High |
| ForgejoRunner | [Link](#forgejorunner) | 0 | 1 | 0 | 1 | 1 | 1 | 0 | 4 | 0 | 4 | 0 | High |
| DNSAPI | [Link](#dnsapi) | 1 | 1 | 1 | 0 | 1 | 1 | 1 | 6 | 0 | 6 | 0 | High |
| PowerDNS | [Link](#powerdns) | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 3 | 0 | 2 | 1 | Low |
| PowerDNSAdmin | [Link](#powerdnsadmin) | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | Low |
| StepCA | [Link](#stepca) | 1 | 1 | 0 | 1 | 1 | 0 | 0 | 4 | 0 | 3 | 1 | Medium |
| EnvFile | [Link](#envfile) | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 2 | 0 | 0 | 2 | Medium |
| TerminalHome | [Link](#terminalhome) | 0 | 1 | 0 | 1 | 1 | 0 | 0 | 3 | 0 | 3 | 0 | Critical |
| ForgejoData | [Link](#forgejodata) | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | Medium |
| OpenBaoSetupVolume | [Link](#openbaosetupvolume) | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | Medium |
| PostgreSQL | [Link](#postgresql) | 1 | 0 | 0 | 1 | 1 | 0 | 0 | 3 | 0 | 1 | 2 | Low |
| **Totals** | | **19** | **16** | **7** | **21** | **18** | **12** | **8** | **101** | **5** | **73** | **23** | |

---

## Gateway

**Trust Boundary:** PublicEdge
**Role:** Caddy reverse proxy; the only published service; Basic Auth, TLS, identity header injection, route gates
**Data Flows:** DF01, DF02, DF03, DF04, DF05, DF06, DF18, DF19, DF20, DF21, DF22, DF40
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T01.S1 | Spoofing | Guessing or brute-forcing the shared class or facilitator Basic Auth credential; `env-setup.sh --default` sets `admin`/`admin`, `student`, `student123`, and Caddy has no attempt limit | None | DF01, DF02 | Interactive setup with random passwords; add rate limiting / fail2ban; refuse to start with default passwords when PUBLIC_BASE_URL is not localhost | Open |
| T01.S2 | Spoofing | Client-supplied `X-Auth-User` / `X-Gateway-Token` headers forging an identity to upstreams | None | DF03, DF18 | `header_up` replaces client values on every proxied block (Caddyfile) | Mitigated |
| T01.D | Denial of Service | Unauthenticated request floods and 401 floods against the single public listener, with no rate or connection limits | None | DF01 | Caddy rate-limit module or upstream proxy limits; host firewall | Open |

#### Tier 2 — Conditional Risk

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T01.T | Tampering | Man-in-the-middle modifies pages or injects script when the gateway serves plain HTTP (`PUBLIC_BASE_URL=http://...`) on a LAN | Internal Network | DF01, DF02 | Serve HTTPS (real hostname or internal CA); add HSTS | Open |
| T01.R | Repudiation | Every student authenticates with the same Basic Auth user and Caddy has no access log configured, so requests cannot be attributed | Authenticated User | DF01 | Enable Caddy access logs with the slot identity; log allocator decisions | Open |
| T01.I | Information Disclosure | Basic Auth credentials (base64) and the session cookie sent in cleartext in HTTP delivery mode; `Secure` cookie flag is off | Internal Network | DF01, DF02 | HTTPS everywhere; `Secure` cookies | Open |
| T01.A | Abuse | The single shared class credential is forwarded to non-attendees, who can claim slots and get a shell on the lab network | Authenticated User | DF01 | Per-session join codes, slot cap, facilitator approval | Open |

#### Tier 3 — Defense-in-Depth

*No Tier 3 threats identified.*

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Elevation of Privilege | Authorization decisions are delegated to the Allocator and rendered route gates; the Caddyfile's `/admin` block requires the facilitator credential exclusively. |

---

## Allocator

**Trust Boundary:** WorkshopLab
**Role:** Slot assignment, session cookies, `/auth-check` forward-auth, Forgejo SSO and `/admin` roster (single-threaded Python)
**Data Flows:** DF03, DF07, DF08
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

*No Tier 1 threats identified.*

#### Tier 2 — Conditional Risk

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T02.S1 | Spoofing | Another container on `workshop_lab` sends forged `X-Auth-User: <facilitator>` directly to `allocator:8080` | Authenticated User | DF03 | `gateway_authorized()` requires `X-Gateway-Token` via `hmac.compare_digest` before any routing | Mitigated |
| T02.S2 | Spoofing | Session cookie captured on the wire in HTTP mode and replayed to take over a student's slot | Internal Network | DF03 | `Secure` flag when HTTPS; serve HTTPS | Open |
| T02.T | Tampering | Cross-site request forgery against `/assign` or `/admin/release/<sid>` | Authenticated User | DF03 | `SameSite=Lax` cookie; release requires `X-Requested-With: dojo-admin` | Mitigated |
| T02.R | Repudiation | `log_message` is a no-op; slot claims, releases, SSO logins and watch sessions leave no record | Authenticated User | DF03 | Structured audit log of identity decisions | Open |
| T02.I | Information Disclosure | The landing page shows every student the same `STUDENT_PASSWORD`, which is also every other student's Linux and Forgejo password | Authenticated User | DF03 | Per-student random passwords | Open |
| T02.D1 | Denial of Service | One client repeatedly POSTs `/assign` without a cookie and claims every free slot, locking the class out | Authenticated User | DF03 | Limit slots per client, facilitator approval or join codes | Open |
| T02.D2 | Denial of Service | Single-threaded `HTTPServer` with a 10 s socket timeout: slow or stalled requests block `/auth-check` for everyone | Authenticated User | DF03 | ThreadingHTTPServer with a lock, or lower timeouts and gateway limits | Open |
| T02.E | Elevation of Privilege | Open redirect through `/forgejo-login?next=` used to phish after SSO | Authenticated User | DF03, DF08 | `local_path()` accepts only single-slash printable site paths | Mitigated |
| T02.A | Abuse | Student-chosen display names (up to 60 characters) shown on the facilitator roster used for impersonation or markup injection | Authenticated User | DF03 | `escapeHtml()` on roster fields; add a CSP header as defence in depth | Open |

#### Tier 3 — Defense-in-Depth

*No Tier 3 threats identified.*

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| None | All seven STRIDE-A categories have at least one threat for this component. |

---

## WorkspaceControl

**Trust Boundary:** WebTerminalContainer
**Role:** Root control API (port 7682) that spawns per-account code-server/ttyd with `su -`
**Data Flows:** DF07, DF09
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

*No Tier 1 threats identified.*

#### Tier 2 — Conditional Risk

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T03.S | Spoofing | A container on `workshop_lab` calls `/start` or `/stop` to spawn or kill another account's workspace | Authenticated User | DF07 | `X-Control-Token` compared with `hmac.compare_digest` | Mitigated |
| T03.T | Tampering | Username injected into the `su - <user> -c` command line | Authenticated User | DF09 | `valid_username()` allowlist of provisioned accounts before any spawn | Mitigated |
| T03.R | Repudiation | Start/stop/watch calls are not logged (`log_message` suppressed) | Authenticated User | DF07 | Log control-plane calls with caller and target | Open |

#### Tier 3 — Defense-in-Depth

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T03.E | Elevation of Privilege | Anyone holding `CONTROL_TOKEN` can run a code-server as any account, including the facilitator | Allocator Compromise | DF07, DF09 | Keep the token only in allocator/web-terminal; rotate per run | Open |

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Information Disclosure | Status responses require the control token and contain only process state. |
| Denial of Service | Only the token-holding Allocator can call it; spawning is idempotent per account. |
| Abuse | No user-facing features; it only executes Allocator decisions. |

---

## WebTerminal

**Trust Boundary:** WebTerminalContainer
**Role:** Shared container: per-student code-server (`--auth none`) and ttyd, student shells, iptables loopback isolation
**Data Flows:** DF04, DF09, DF10, DF11, DF12, DF13, DF14, DF15, DF16, DF17
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

*No Tier 1 threats identified.*

#### Tier 2 — Conditional Risk

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T04.S1 | Spoofing | A student runs `su - studentNN` with the shared `STUDENT_PASSWORD` shown on their own landing page and becomes any other student | Authenticated User | DF09, DF10 | Per-student random passwords or locked passwords (`passwd -l`) for student accounts | Open |
| T04.S2 | Spoofing | code-server/ttyd listen on `0.0.0.0:9000-9899` with no auth; the DOJO_ISOLATION chain filters only OUTPUT inside this container, so code on another `workshop_lab` container (a student's app on AppHost) opens any student's IDE or shell | Authenticated User | DF04 | INPUT rule allowing 9000-9899 only from the gateway, or per-user Unix sockets / code-server password injected by the gateway | Open |
| T04.T | Tampering | After `su`, a student edits or deletes another student's lab work, git config, or tokens | Authenticated User | DF10 | Per-student credentials; restrictive home permissions | Open |
| T04.R | Repudiation | All students share one network namespace and source IP, so actions on lab services cannot be tied to a student | Authenticated User | DF11, DF14, DF15, DF16 | Per-student identity in every service log (tokens already carry it); keep terminal session logs | Open |
| T04.I | Information Disclosure | `/proc` is not mounted with `hidepid`, so `ps aux` shows other students' command lines, including secrets passed as arguments in the labs (`bao kv put ... db_password=...`) | Authenticated User | DF09 | podman `--security-opt proc-opts=hidepid=2` or per-user PID namespaces; teach stdin/`@file` input | Open |
| T04.D | Denial of Service | One student exhausts the container-wide `mem_limit` (4g) or `pids_limit` shared by 30 students | Authenticated User | DF04 | Per-account ulimits and code-server heap caps exist; add cgroup per user or per-student containers | Open |
| T04.A | Abuse | The terminal is a pivot onto `workshop_lab`: students scan and attack every internal service directly | Authenticated User | DF14, DF15, DF16, DF17 | Network policy per service; authenticate every service (as most modules do) | Open |

#### Tier 3 — Defense-in-Depth

*No Tier 3 threats identified.*

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Elevation of Privilege | Students have no sudo; `NET_ADMIN` and brokers are root-only; escaping to root needs a kernel bug. |

---

## Forgejo

**Trust Boundary:** WorkshopLab
**Role:** Git server, Actions, OIDC issuer; accounts seeded by bootstrap.sh
**Data Flows:** DF05, DF08, DF11, DF26, DF28, DF29, DF34, DF38
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

*No Tier 1 threats identified.*

#### Tier 2 — Conditional Risk

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T05.S | Spoofing | Logging in to Forgejo as another student with the shared `STUDENT_PASSWORD` | Authenticated User | DF05, DF11 | Per-student passwords | Open |
| T05.T | Tampering | Students push branches to the shared org repo and change `.forgejo/workflows/*` so their code runs in CI with CI privileges | Authenticated User | DF11, DF34 | Forks-only workflow, protected workflow files, approval before running PR workflows | Open |
| T05.D | Denial of Service | Large pushes or repeated clones exhaust Forgejo (2g `mem_limit`) for the class | Authenticated User | DF11 | Repository size limits, request limits | Open |
| T05.E | Elevation of Privilege | Forgejo admin password is `admin` in `--default` mode and the admin login form is reachable from every student | Authenticated User | DF05 | Random admin password; interactive setup | Open |
| T05.A | Abuse | Forgejo identity is the root of trust for OpenBao OIDC, Actions ID tokens and AppHost deploys, so a hijacked student account yields that student's secrets and deploy slot | Authenticated User | DF26, DF31 | Per-student passwords; short token TTLs (present) | Open |

#### Tier 3 — Defense-in-Depth

*No Tier 3 threats identified.*

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Repudiation | Forgejo records pushes, PRs and reviews per account (attribution weakened only by the shared password, covered under Spoofing). |
| Information Disclosure | Repositories are intentionally visible to the class; no secrets are seeded into them. |

---

## Presentation

**Trust Boundary:** PublicEdge
**Role:** Marp slide server behind unauthenticated `/slides`
**Data Flows:** DF06
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T06.I | Information Disclosure | Slides, cheat sheets and lab copies (`content/slides/lab/*.md.txt`) are readable by anyone who can reach the gateway, before the Basic Auth gate | None | DF06 | Move `/slides` behind the shared gate or serve only public decks | Open |
| T06.D | Denial of Service | Unauthenticated floods on `/slides` consume gateway and presentation capacity | None | DF06 | Gateway rate limiting | Open |

#### Tier 2 — Conditional Risk

*No Tier 2 threats identified.*

#### Tier 3 — Defense-in-Depth

*No Tier 3 threats identified.*

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Spoofing | No identity is used by this read-only service. |
| Tampering | Content is mounted read-only (`:ro`) from the repo. |
| Repudiation | Read-only public content; no actions to attribute. |
| Elevation of Privilege | No privileged operations are exposed. |
| Abuse | Only static slide rendering is exposed. |

---

## RunScript

**Trust Boundary:** LabHost
**Role:** `engine/run.sh`, `env-setup.sh` and `render_extensions.py`: loads secrets, renders manifests, builds images, starts the stack
**Data Flows:** DF39, DF40, DF42
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

*No Tier 1 threats identified.*

#### Tier 2 — Conditional Risk

*No Tier 2 threats identified.*

#### Tier 3 — Defense-in-Depth

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T07.T | Tampering | A malicious or broken `extensions.json` injects raw Caddy config or routes to arbitrary upstreams | Host/OS Access | DF40 | Fixed gate templates; renderer rejects engine-path collisions and unknown upstreams; bad manifests stop the start | Mitigated |
| T07.I | Information Disclosure | `env-setup.sh --default` writes fixed, published passwords for every human account | Host/OS Access | DF39 | Warn or refuse `--default` when PUBLIC_BASE_URL is not localhost | Open |
| T07.E | Elevation of Privilege | Builds pull mutable tags (`caddy:2-alpine`, `python:3.12-alpine`, `docker:dind`, `step-ca:latest`, `pdns-auth-49:latest`) so a compromised upstream image runs with the stack's privileges | RunScript Compromise | DF40 | Pin images by digest, as `dns-admin` already does | Open |

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Spoofing | Runs only as the operator's own shell; no remote callers. |
| Repudiation | Operator-only tool on the host. |
| Denial of Service | No listener. |
| Abuse | Only the operator can run it. |

---

## CloudAPI

**Trust Boundary:** WorkshopLab
**Role:** Dojo Cloud ARM-like API (:443) and portal (:8080) with OAuth client-credentials, HMAC JWTs and a fixed Docker executor
**Data Flows:** DF14, DF18, DF23
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

*No Tier 1 threats identified.*

#### Tier 2 — Conditional Risk

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T08.T | Tampering | Modifying another student's resource groups | Authenticated User | DF14 | Subscription ownership check on every path; only reachable by impersonating the owner (FIND-03) | Mitigated |
| T08.R | Repudiation | Activity log keeps only a recent window in JSON state; operational logs go to stdout only | Authenticated User | DF14 | Persist an append-only activity log | Open |
| T08.D | Denial of Service | No request rate limiting; students can flood deployment and polling APIs | Authenticated User | DF14, DF18 | Quotas exist (2 groups, CPU/memory caps); add per-client rate limits | Open |
| T08.A | Abuse | Students run container groups for non-lab purposes within quota | Authenticated User | DF14 | Image allowlist limits workloads to `dojo/hello` | Mitigated |

#### Tier 3 — Defense-in-Depth

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T08.S | Spoofing | Portal trusts `X-Auth-User` when `X-Gateway-Token` matches; the same token is shared by every module service, so any one compromised service can impersonate any user here | AppHost Compromise | DF18 | Per-service gateway secrets or signed identity assertions | Open |
| T08.E | Elevation of Privilege | CloudAPI holds the Docker socket of a privileged nested daemon; a bug in the executor becomes root on CloudHost | CloudAPI Compromise | DF23 | Fixed create template, image allowlist, `CapDrop: ALL`; run DinD rootless | Open |

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Information Disclosure | Responses are scoped to the caller's subscription; secrets are HMAC-derived and compared in constant time. |

---

## CloudHost

**Trust Boundary:** CloudNet
**Role:** Privileged Docker-in-Docker daemon running student container groups
**Data Flows:** DF23
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

*No Tier 1 threats identified.*

#### Tier 2 — Conditional Risk

*No Tier 2 threats identified.*

#### Tier 3 — Defense-in-Depth

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T09.T | Tampering | A student container escapes the nested runtime into the privileged outer container and the host kernel | CloudAPI Compromise | DF23 | Rootless DinD or sysbox; no `privileged: true` | Open |
| T09.I | Information Disclosure | Student containers reach each other or the outside | CloudAPI Compromise | DF23 | `--icc=false` and a `DOCKER-USER` drop rule | Mitigated |
| T09.D | Denial of Service | Nested containers exhaust the 3 GiB / 4096 PID budget | CloudAPI Compromise | DF23 | Per-container limits (PIDs 64, CPU, memory) | Mitigated |
| T09.E | Elevation of Privilege | Docker socket created mode 0666 on a shared volume and daemon runs `privileged: true`: any process that can reach the socket controls a root-equivalent daemon | CloudAPI Compromise | DF23 | Socket mode 0660 with a dedicated group; rootless daemon | Open |

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Spoofing | Only CloudAPI mounts the socket volume. |
| Repudiation | Actions are recorded by CloudAPI's activity log. |
| Abuse | Workloads are constrained by CloudAPI's image allowlist. |

---

## DojoBroker

**Trust Boundary:** WebTerminalContainer
**Role:** Root Unix-socket broker issuing Dojo Cloud credentials to the caller's uid
**Data Flows:** DF12
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

*No Tier 1 threats identified.*

#### Tier 2 — Conditional Risk

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T10.S | Spoofing | After `su - studentNN` (shared password), the broker issues studentNN's Dojo Cloud credentials to the attacker | Authenticated User | DF12 | SO_PEERCRED binding is correct; fix the shared password | Open |
| T10.I | Information Disclosure | Students read the signing key used to derive every student's client secret | Authenticated User | DF12 | Key file mode 0400 root on a read-only volume | Mitigated |

#### Tier 3 — Defense-in-Depth

*No Tier 3 threats identified.*

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Tampering | Requests carry no caller-controlled identity; the uid comes from the kernel. |
| Repudiation | Issued credentials are logged by CloudAPI on use. |
| Denial of Service | Local socket; a caller can only slow its own login. |
| Elevation of Privilege | Identity is derived only from SO_PEERCRED. |
| Abuse | Only issues the caller's own credentials. |

---

## OpenBaoBroker

**Trust Boundary:** WebTerminalContainer
**Role:** Root Unix-socket broker signing two-minute JWTs for OpenBao login
**Data Flows:** DF13
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

*No Tier 1 threats identified.*

#### Tier 2 — Conditional Risk

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T11.S | Spoofing | After `su - studentNN`, the broker signs a JWT for studentNN and the attacker gets that student's vault token | Authenticated User | DF13 | SO_PEERCRED binding is correct; fix the shared password | Open |
| T11.I | Information Disclosure | Students read the JWT signing key | Authenticated User | DF13 | Private key readable by root only; public key mounted into OpenBaoSetup | Mitigated |

#### Tier 3 — Defense-in-Depth

*No Tier 3 threats identified.*

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Tampering | Identity comes from the kernel, not the request. |
| Repudiation | OpenBao's audit device records each login by entity. |
| Denial of Service | Local socket; impact limited to the caller's own login. |
| Elevation of Privilege | JWTs are bound to the caller's own role and namespace. |
| Abuse | Only mints short-lived tokens for the caller. |

---

## OpenBao

**Trust Boundary:** WorkshopLab
**Role:** OpenBao 2.7.0 vault with per-student namespaces, templated policy and file audit
**Data Flows:** DF15, DF19, DF24, DF26, DF27, DF30, DF32
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

*No Tier 1 threats identified.*

#### Tier 2 — Conditional Risk

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T12.S | Spoofing | Logging in as another student through the broker or Forgejo OIDC after impersonating them | Authenticated User | DF15, DF26 | Per-student passwords | Open |
| T12.R | Repudiation | Vault actions not attributable | Authenticated User | DF15 | File audit device enabled and surfaced in the audit panel | Mitigated |
| T12.D | Denial of Service | Students flood login or KV endpoints; no rate-limit quota configured | Authenticated User | DF15 | OpenBao rate-limit quotas per namespace | Open |
| T12.E | Elevation of Privilege | Policy or namespace mistake lets a student read another student's namespace or `team/*` data | Authenticated User | DF15 | Per-student namespaces, templated policy, tenancy tests (`tests/tenancy.sh`) | Mitigated |

#### Tier 3 — Defense-in-Depth

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T12.I1 | Information Disclosure | Listener has `tls_disable = true`; tokens and secrets cross `workshop_lab` and `runner_net` in plaintext | WebTerminal Compromise | DF15, DF30, DF32 | TLS listener with the internal CA | Open |
| T12.I2 | Information Disclosure | Audit device sets `hmac_accessor = false`, so token accessors are stored in clear in the audit log | OpenBaoSetup Compromise | DF24 | Keep accessors HMAC'd unless the panel needs them | Open |

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Tampering | Writes are governed by the same policies analysed under Elevation of Privilege. |
| Abuse | Lab-intended shared paths (`team/*`) are policy-controlled. |

---

## OpenBaoSetup

**Trust Boundary:** WorkshopLab
**Role:** Root setup container: init, unseal loop, provisioner token, workshop tenancy scripts
**Data Flows:** DF24, DF25
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

*No Tier 1 threats identified.*

#### Tier 2 — Conditional Risk

*No Tier 2 threats identified.*

#### Tier 3 — Defense-in-Depth

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T13.I | Information Disclosure | Unseal key (single share) and long-lived provisioner token persisted on the setup volume | Host/OS Access | DF25 | Revoke root token (done); short-TTL provisioner; transit/KMS auto-unseal | Open |
| T13.E | Elevation of Privilege | Provisioner policy can manage policies, auth methods and namespaces, so it is root-equivalent | Host/OS Access | DF24 | Scope the provisioner policy; revoke after setup | Open |

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Spoofing | No listener; only talks outbound to OpenBao. |
| Tampering | Setup scripts are mounted from the repo read-only. |
| Repudiation | OpenBao audit records provisioner actions. |
| Denial of Service | One-shot setup plus unseal loop; no inbound traffic. |
| Abuse | No user-facing features. |

---

## RunnerPool

**Trust Boundary:** RunnerNet
**Role:** Single-use Forgejo runners executing student CI as fresh Unix users in user+PID namespaces
**Data Flows:** DF28, DF30, DF31
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

*No Tier 1 threats identified.*

#### Tier 2 — Conditional Risk

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T14.T | Tampering | A job leaves files or processes that tamper with the next job | Authenticated User | DF28 | Per-job user, private HOME/TMPDIR, cleanup, single-use registration | Mitigated |
| T14.I | Information Disclosure | A job reads other jobs' secrets or tokens | Authenticated User | DF28 | Per-job user and PID namespace; cleanup after each job | Mitigated |
| T14.D | Denial of Service | Jobs exhaust the pool's 2 GiB memory or PID budget | Authenticated User | DF28 | `prlimit` per job, `mem_limit`, `pids_limit` | Open |
| T14.E | Elevation of Privilege | Container runs as root (`user: 0:0`) with default capabilities; isolation rests only on unprivileged user namespaces, so a userns/kernel escape gives root over every job and the runner secrets | Authenticated User | DF28 | `cap_drop: ALL` except what `unshare` needs, `no-new-privileges`, non-root supervisor | Open |
| T14.A | Abuse | Students run arbitrary workloads (scanning, mining) in CI | Authenticated User | DF28 | Internal network only, resource limits | Open |

#### Tier 3 — Defense-in-Depth

*No Tier 3 threats identified.*

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Spoofing | Runner registrations are ephemeral and created by the controller. |
| Repudiation | Forgejo keeps job logs per run and account. |

---

## RunnerController

**Trust Boundary:** WorkshopLab
**Role:** Runner autoscaler with Forgejo admin access and the `/admin` Runners panel
**Data Flows:** DF20, DF29
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

*No Tier 1 threats identified.*

#### Tier 2 — Conditional Risk

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T15.S | Spoofing | A student calls the panel API directly | Authenticated User | DF20 | Gateway token plus exact facilitator identity; POSTs need `X-Requested-With` | Mitigated |
| T15.D | Denial of Service | Students queue many jobs to starve the pool | Authenticated User | DF29 | Runner cap and failure back-off | Open |

#### Tier 3 — Defense-in-Depth

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T15.I | Information Disclosure | Holds `FORGEJO_ADMIN_PASSWORD` and `GATEWAY_TOKEN` in its environment; compromise yields Forgejo admin and facilitator impersonation | RunnerController Compromise | DF29 | Scoped Forgejo token instead of admin password; per-service secrets | Open |

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Tampering | Panel writes require facilitator identity. |
| Repudiation | Facilitator-only actions; Forgejo logs runner changes. |
| Elevation of Privilege | Facilitator gate enforced server-side. |
| Abuse | Only facilitator can act. |

---

## AppHost

**Trust Boundary:** WorkshopLab
**Role:** Deploy target that runs student app bundles per slot; on `workshop_lab` and `runner_net`
**Data Flows:** DF21, DF31, DF32, DF33
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

*No Tier 1 threats identified.*

#### Tier 2 — Conditional Risk

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T16.S | Spoofing | Deploying into another student's slot | Authenticated User | DF31 | Actions ID token audience check; slot = repo owner of `<owner>/<repo>` on main (impersonation covered by FIND-03) | Mitigated |
| T16.T | Tampering | Bundle path traversal during extraction | Authenticated User | DF31 | Extraction as the slot user in its own home with `--no-same-owner --no-same-permissions` | Mitigated |
| T16.I | Information Disclosure | Slot apps read other slots' platform tokens or the signing key | Authenticated User | DF32 | Token files 0400 per slot user; key 0600 root | Mitigated |
| T16.D | Denial of Service | A slot app exhausts the 1 GiB / 1024 PID container budget | Authenticated User | DF21 | prlimit per slot, restart throttling | Open |
| T16.E | Elevation of Privilege | Student app code has unrestricted network access on `workshop_lab`, including other students' unauthenticated code-server/ttyd ports | Authenticated User | DF21 | Per-slot network namespace or egress allowlist (OpenBao, app-db only) | Open |
| T16.A | Abuse | Apps serve arbitrary content to the class under the lab origin | Authenticated User | DF21 | `sandbox; default-src 'none'` CSP on app pages; request cookies/headers dropped | Mitigated |

#### Tier 3 — Defense-in-Depth

*No Tier 3 threats identified.*

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Repudiation | Deploys are tied to Forgejo Actions runs and the slot owner. |

---

## ForgejoRunner

**Trust Boundary:** RunnerNet
**Role:** Shared Forgejo Actions runner using the `host` executor (dns-as-code)
**Data Flows:** DF34, DF35
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

*No Tier 1 threats identified.*

#### Tier 2 — Conditional Risk

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T17.T | Tampering | Jobs share one filesystem; a job can plant files or binaries that alter later students' jobs | Authenticated User | DF34 | Ephemeral per-job runners (as runner-pool does) | Open |
| T17.I | Information Disclosure | Jobs can read the runner registration secret in `runner_config` | Authenticated User | DF34 | Separate job user from runner daemon; ephemeral registrations | Open |
| T17.D | Denial of Service | A job hogs the single runner and blocks everyone's required `DNS Preview` check | Authenticated User | DF34 | Job timeouts; more runners | Open |
| T17.E | Elevation of Privilege | A PR that edits `dns-preview.yml` runs arbitrary commands with CI identity and pushes to protected `dojo.test` without review | Authenticated User | DF35 | Run PR workflows from the base branch; require approval to run; per-job credentials instead of source-IP trust | Open |

#### Tier 3 — Defense-in-Depth

*No Tier 3 threats identified.*

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Spoofing | Registration is created by `register.sh` with a random secret. |
| Repudiation | Forgejo keeps per-run logs tied to the triggering account. |
| Abuse | Covered by the Elevation of Privilege threat (workflow edits). |

---

## DNSAPI

**Trust Boundary:** WorkshopLab
**Role:** PowerDNS API gate swapping the public key for the real key and enforcing zone rules
**Data Flows:** DF16, DF35, DF36
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

*No Tier 1 threats identified.*

#### Tier 2 — Conditional Risk

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T18.S | Spoofing | CI is recognised only by source IP of `forgejo-runner`; any code running there is treated as the pipeline | Authenticated User | DF35 | Per-run signed tokens (Actions ID token) instead of IP trust | Open |
| T18.T | Tampering | One student edits or deletes another student's `<name>.dojo.test` zone with the shared public key | Authenticated User | DF16 | Per-student keys issued by a broker, zone ownership check | Open |
| T18.R | Repudiation | Gate suppresses request logs; zone changes cannot be attributed | Authenticated User | DF16 | Log method, zone and caller | Open |
| T18.D | Denial of Service | No rate limit on writes | Authenticated User | DF16 | Per-client limits | Open |
| T18.E | Elevation of Privilege | Writes outside zone endpoints (server config, TSIG keys) | Authenticated User | DF36 | Gate refuses every non-zone write, CI included | Mitigated |
| T18.A | Abuse | Zone squatting: a student creates `otherstudent.dojo.test` first | Authenticated User | DF16 | Pre-create zones per student; ownership check | Open |

#### Tier 3 — Defense-in-Depth

*No Tier 3 threats identified.*

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Information Disclosure | Reads are intentionally open to the class; the real key is never returned. |

---

## PowerDNS

**Trust Boundary:** WorkshopLab
**Role:** Authoritative DNS with HTTP API (`pdns-auth-49:latest`)
**Data Flows:** DF36, DF37, DF41
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

*No Tier 1 threats identified.*

#### Tier 2 — Conditional Risk

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T19.S | Spoofing | Students call the PowerDNS API directly, bypassing the gate | Authenticated User | DF36 | Real API key derived from `GATEWAY_TOKEN`, never given to students | Mitigated |
| T19.D | Denial of Service | DNS query floods from student terminals | Authenticated User | DF41 | Container limits | Open |

#### Tier 3 — Defense-in-Depth

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T19.T | Tampering | Mutable `latest` image tag pulls unreviewed upstream changes | RunScript Compromise | DF36 | Pin by digest | Open |

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Repudiation | Changes arrive through DNSAPI/PowerDNSAdmin (analysed there). |
| Information Disclosure | Zone data is intentionally public to the class. |
| Elevation of Privilege | Only `NET_BIND_SERVICE` added; no privileged mode. |
| Abuse | Authoritative-only server; recursion not offered. |

---

## PowerDNSAdmin

**Trust Boundary:** WorkshopLab
**Role:** PowerDNS-Admin UI on `dns_admin_net`, trusting gateway remote-user
**Data Flows:** DF22, DF37
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

*No Tier 1 threats identified.*

#### Tier 2 — Conditional Risk

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T20.S | Spoofing | Forged remote-user header from a student container | Privileged User | DF22 | Only gateway and dns-server share `dns_admin_net`; gateway token required | Mitigated |

#### Tier 3 — Defense-in-Depth

*No Tier 3 threats identified.*

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Tampering | Facilitator-only UI. |
| Repudiation | Facilitator-only; PowerDNS-Admin keeps its own history. |
| Information Disclosure | Random Flask `SECRET_KEY` per start; discarded local password. |
| Denial of Service | Not reachable by students. |
| Elevation of Privilege | Capabilities dropped except `NET_BIND_SERVICE`; read-only root. |
| Abuse | Facilitator-only. |

---

## StepCA

**Trust Boundary:** WorkshopLab
**Role:** Smallstep CA with an ACME provisioner for cert-autorenewal
**Data Flows:** DF17, DF41
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

*No Tier 1 threats identified.*

#### Tier 2 — Conditional Risk

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T21.S | Spoofing | Any student obtains certificates for any name they can validate, including other students' hostnames via cross-writable zones | Authenticated User | DF17 | Per-student provisioners or name constraints | Open |
| T21.I | Information Disclosure | CA key password defaults to the published `workshop-not-a-secret` | Authenticated User | DF17 | Random password from env-setup | Open |
| T21.D | Denial of Service | ACME order floods | Authenticated User | DF17 | Rate limits | Open |

#### Tier 3 — Defense-in-Depth

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T21.T | Tampering | Mutable `step-ca:latest` base image | RunScript Compromise | DF17 | Pin by digest | Open |

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Repudiation | step-ca logs issuance. |
| Elevation of Privilege | Runs as unprivileged `step` user after setup. |
| Abuse | Covered by Spoofing (issuance for others' names). |

---

## EnvFile

**Trust Boundary:** LabHost
**Role:** `engine/.env`: every password and machine token in plaintext
**Data Flows:** DF39
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

*No Tier 1 threats identified.*

#### Tier 2 — Conditional Risk

*No Tier 2 threats identified.*

#### Tier 3 — Defense-in-Depth

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T22.I | Information Disclosure | Plaintext secrets on disk, then copied into container environments visible via `inspect` | Host/OS Access | DF39 | File mode 0600; secrets files instead of env; git-ignored (present) | Open |
| T22.T | Tampering | Editing `.env` changes every credential and token | Host/OS Access | DF39 | Host access control | Open |

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Spoofing | Not an actor. |
| Repudiation | Host-level file. |
| Denial of Service | Host-level file. |
| Elevation of Privilege | Covered by Tampering. |
| Abuse | Not user-facing. |

---

## TerminalHome

**Trust Boundary:** WebTerminalContainer
**Role:** `terminal_home` volume with every student's home, tokens and git credentials
**Data Flows:** DF10
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

*No Tier 1 threats identified.*

#### Tier 2 — Conditional Risk

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T23.I | Information Disclosure | Another student reads `~/.vault-token`, cached git credentials or lab secrets after `su` | Authenticated User | DF10 | Per-student passwords; `chmod 700` homes | Open |
| T23.T | Tampering | Another student modifies files after `su` | Authenticated User | DF10 | Per-student passwords | Open |
| T23.D | Denial of Service | One student fills the shared volume | Authenticated User | DF10 | `fsize` ulimit; add quotas | Open |

#### Tier 3 — Defense-in-Depth

*No Tier 3 threats identified.*

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Spoofing | Not an actor. |
| Repudiation | Covered by WebTerminal. |
| Elevation of Privilege | Covered by WebTerminal. |
| Abuse | Not user-facing. |

---

## ForgejoData

**Trust Boundary:** WorkshopLab
**Role:** Forgejo SQLite DB, repositories and runner registrations
**Data Flows:** DF38
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

*No Tier 1 threats identified.*

#### Tier 2 — Conditional Risk

*No Tier 2 threats identified.*

#### Tier 3 — Defense-in-Depth

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T24.I | Information Disclosure | Password hashes, runner secrets and tokens unencrypted in the volume | Host/OS Access | DF38 | Host access control; ephemeral volumes wiped by `stop` | Open |

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Spoofing | Not an actor. |
| Tampering | Only Forgejo mounts it. |
| Repudiation | Not applicable to a volume. |
| Denial of Service | Covered by Forgejo limits. |
| Elevation of Privilege | Not applicable to a volume. |
| Abuse | Not user-facing. |

---

## OpenBaoSetupVolume

**Trust Boundary:** WorkshopLab
**Role:** Setup volume holding the unseal key and provisioner token
**Data Flows:** DF25
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

*No Tier 1 threats identified.*

#### Tier 2 — Conditional Risk

*No Tier 2 threats identified.*

#### Tier 3 — Defense-in-Depth

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T25.I | Information Disclosure | Anyone with host or volume access can unseal the vault and act as provisioner | Host/OS Access | DF25 | Auto-unseal via KMS/transit; revoke provisioner after setup | Open |

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Spoofing | Not an actor. |
| Tampering | Mounted only by OpenBaoSetup. |
| Repudiation | Not applicable to a volume. |
| Denial of Service | Loss only blocks re-unseal after restart. |
| Elevation of Privilege | Covered by Information Disclosure. |
| Abuse | Not user-facing. |

---

## PostgreSQL

**Trust Boundary:** WorkshopLab
**Role:** `app-db` for lab 12: per-student databases and roles
**Data Flows:** DF27, DF33
**Pod Co-location:** N/A

### STRIDE-A Analysis

#### Tier 1 — Direct Exposure (No Prerequisites)

*No Tier 1 threats identified.*

#### Tier 2 — Conditional Risk

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T26.D | Denial of Service | Students exhaust connections | Authenticated User | DF33 | Per-role connection limits | Open |

#### Tier 3 — Defense-in-Depth

| ID | Category | Threat | Prerequisites | Affected Flow | Mitigation | Status |
|----|----------|--------|---------------|---------------|------------|--------|
| T26.S | Spoofing | Initial per-student passwords left in `app_db_bootstrap` | Host/OS Access | DF27 | OpenBao `rotate-root` right after setup; superuser password random and discarded | Mitigated |
| T26.I | Information Disclosure | Connections from OpenBao and apps are not TLS-protected | WebTerminal Compromise | DF27, DF33 | Enable TLS on app-db | Open |

#### Categories Not Applicable

| Category | Justification |
|----------|---------------|
| Tampering | Per-student roles limit writes to own database. |
| Repudiation | Dynamic logins carry per-lease names. |
| Elevation of Privilege | Superuser password discarded; roles scoped. |
| Abuse | Lab-only data. |
