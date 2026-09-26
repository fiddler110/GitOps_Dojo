# Security Assessment

---

## Report Files

| File | Description |
|------|-------------|
| [0-assessment.md](0-assessment.md) | This document — executive summary, risk rating, action plan, metadata |
| [0.1-architecture.md](0.1-architecture.md) | Architecture overview, components, scenarios, tech stack |
| [1-threatmodel.md](1-threatmodel.md) | Threat model DFD diagram with element, flow, and boundary tables |
| [1.1-threatmodel.mmd](1.1-threatmodel.mmd) | Pure Mermaid DFD source file |
| [2-stride-analysis.md](2-stride-analysis.md) | Full STRIDE-A analysis for all components |
| [3-findings.md](3-findings.md) | Prioritized security findings with remediation |
| [1.2-threatmodel-summary.mmd](1.2-threatmodel-summary.mmd) | Summary DFD for large systems |

---

## Executive Summary

GitOps Dojo is a lunch-and-learn training platform: one Caddy gateway publishes a browser-only lab (per-student VS Code and terminal, a Forgejo git server, slides) and, depending on the workshop, module services such as Dojo Cloud, OpenBao, autoscaled Forgejo runners, an app host, PowerDNS and a private ACME CA. Everything runs as containers on one host started by `./run.sh`. Students are separated from the internet and from each other by the gateway's identity headers, per-account processes in one shared terminal container, and per-student credentials issued by root brokers, OpenBao namespaces and per-tenant namespaces in the runners and app host.

The per-service controls are generally well built: identity headers are overwritten by Caddy and backed by a constant-time gateway token check, brokers bind credentials to the kernel-reported uid, the Dojo Cloud executor uses a fixed template and image allowlist, module panels use a strict CSP with `textContent`, and OpenBao has per-student namespaces, a templated policy and an audit device. The main weakness is that the *identity underneath* those controls is weak. Every student shares one Linux and Forgejo password, and it is displayed to all of them (FIND-03). On top of that, the per-student IDE and terminal listeners are unauthenticated and reachable from student-controlled app code (FIND-04), and dns-as-code runs pull-request CI on a shared host runner that dns-api trusts by source IP (FIND-05). At the edge, `--default` setup publishes known passwords behind a Basic Auth gate with no brute-force limit (FIND-01).

The analysis covers 28 system elements across 6 trust boundaries.

### Risk Rating: Elevated

For its intended use (a short-lived, facilitator-run class on a trusted LAN or the home-lab host), the most likely attackers are curious students, and they can already cross into each other's accounts, secrets and deployments (one Critical and two Important Tier 2 findings). Tier 1 exposure is limited to the gateway credentials and public slides, and it is serious only when the stack is started with `--default` passwords on a reachable host. Fixing per-student passwords, restricting inbound terminal ports and removing IP trust for CI would bring the rating to Moderate.

> **Note on threat counts:** This analysis identified 101 threats across 26 components. This count reflects comprehensive STRIDE-A coverage, not systemic insecurity. Of these, **5 are directly exploitable** without prerequisites (Tier 1). The remaining 96 represent conditional risks and defense-in-depth considerations.

---

## Action Summary

| Tier | Description | Threats | Findings | Priority |
|------|-------------|---------|----------|----------|
| [Tier 1](3-findings.md#tier-1--direct-exposure-no-prerequisites) | Directly exploitable | 5 | 2 | 🔴 Critical Risk |
| [Tier 2](3-findings.md#tier-2--conditional-risk-authenticated--single-prerequisite) | Requires authenticated access | 73 | 12 | 🟠 Elevated Risk |
| [Tier 3](3-findings.md#tier-3--defense-in-depth-prior-compromise--host-access) | Requires prior compromise | 23 | 5 | 🟡 Moderate Risk |
| **Total** | | **101** | **19** | |

### Priority by Tier and CVSS Score (Top 10)

| Finding | Tier | CVSS Score | SDL Severity | Title |
|---------|------|------------|-------------|-------|
| [FIND-01](3-findings.md#find-01-default-credentials-and-no-brute-force-limit-on-the-public-basic-auth-gate) | T1 | 9.5 | Important | Default credentials and no brute-force limit on the public Basic Auth gate |
| [FIND-02](3-findings.md#find-02-slides-and-lab-copies-served-without-authentication) | T1 | 6.9 | Low | Slides and lab copies served without authentication |
| [FIND-03](3-findings.md#find-03-one-shared-password-for-every-students-linux-and-forgejo-account-enables-cross-student-impersonation) | T2 | 9.3 | Critical | One shared password for every student's Linux and Forgejo account enables cross-student impersonation |
| [FIND-04](3-findings.md#find-04-unauthenticated-code-server-and-ttyd-reachable-from-other-containers-on-the-lab-network) | T2 | 8.8 | Important | Unauthenticated code-server and ttyd reachable from other containers on the lab network |
| [FIND-05](3-findings.md#find-05-pull-request-workflows-run-student-modified-code-on-a-shared-host-runner-trusted-by-dns-api) | T2 | 8.4 | Important | Pull-request workflows run student-modified code on a shared host runner trusted by dns-api |
| [FIND-06](3-findings.md#find-06-runner-pool-and-app-host-run-as-root-with-default-capabilities) | T2 | 7.3 | Moderate | Runner pool and app-host run as root with default capabilities |
| [FIND-07](3-findings.md#find-07-slot-exhaustion-and-head-of-line-blocking-in-the-single-threaded-allocator) | T2 | 7.1 | Moderate | Slot exhaustion and head-of-line blocking in the single-threaded allocator |
| [FIND-08](3-findings.md#find-08-credentials-and-session-cookies-in-cleartext-when-served-over-http) | T2 | 6.0 | Moderate | Credentials and session cookies in cleartext when served over HTTP |
| [FIND-09](3-findings.md#find-09-shared-acme-ca-with-a-published-default-password-issues-certificates-for-other-students-names) | T2 | 6.0 | Moderate | Shared ACME CA with a published default password issues certificates for other students' names |
| [FIND-10](3-findings.md#find-10-other-students-command-lines-including-lab-secrets-visible-through-proc) | T2 | 5.7 | Moderate | Other students' command lines, including lab secrets, visible through /proc |

### Quick Wins

| Finding | Title | Why Quick |
|---------|-------|-----------|
| [FIND-01](3-findings.md#find-01-default-credentials-and-no-brute-force-limit-on-the-public-basic-auth-gate) | Default credentials and no brute-force limit on the public Basic Auth gate | Setting random passwords is one `env-setup.sh` path plus a start-up guard; rate limiting is a proxy setting |
| [FIND-02](3-findings.md#find-02-slides-and-lab-copies-served-without-authentication) | Slides and lab copies served without authentication | Moving one Caddy route behind the existing gate |
| [FIND-08](3-findings.md#find-08-credentials-and-session-cookies-in-cleartext-when-served-over-http) | Credentials and session cookies in cleartext when served over HTTP | Serve HTTPS; the `Secure` flag already follows the URL scheme |
| [FIND-13](3-findings.md#find-13-identity-and-control-plane-actions-are-not-logged) | Identity and control-plane actions are not logged | Replace no-op `log_message` overrides and add a Caddy `log` directive |
| [FIND-18](3-findings.md#find-18-base-images-pulled-by-mutable-tags) | Base images pulled by mutable tags | Add `@sha256:` digests to a handful of `FROM`/`image:` lines |

---

## Analysis Context & Assumptions

### Analysis Scope
| Constraint | Description |
|------------|-------------|
| Scope | `engine/`, all `modules/`, and all workshop packs on branch `feat/vault-fundamentals` at `6ca99bd` (git-fundamentals, dns-as-code, cert-autorenewal, tofu-basics, vault-fundamentals) |
| Excluded | Slide and lab prose (except where labs show secrets on command lines), demo bots, tests, the user's home-lab reverse proxy, host OS and podman configuration |
| Focus Areas | Student-to-student isolation, gateway authentication and identity propagation, CI/CD trust, secret handling, container privileges |

### Infrastructure Context
| Category | Discovered from Codebase | Findings Affected |
|----------|--------------------------|-------------------|
| Deployment | Single-host podman/compose stack; only the gateway is published ([engine/docker-compose.yml](../engine/docker-compose.yml)); classification `NETWORK_SERVICE` | All |
| Edge authentication | Caddy Basic Auth with shared class and facilitator credentials, forward-auth to the allocator ([engine/gateway/Caddyfile](../engine/gateway/Caddyfile)) | FIND-01, FIND-02, FIND-08 |
| Secrets | Plaintext `engine/.env` written by [engine/scripts/env-setup.sh](../engine/scripts/env-setup.sh), passed as environment variables | FIND-01, FIND-16 |
| Secrets management | OpenBao 2.7.0 with namespaces, templated policy, file audit ([modules/openbao/config.hcl](../modules/openbao/config.hcl)) | FIND-17, FIND-19 |
| Student isolation | Shared terminal container, per-uid loopback iptables chain ([engine/web-terminal/entrypoint.sh](../engine/web-terminal/entrypoint.sh)) | FIND-03, FIND-04, FIND-10 |
| CI/CD | Shared host runner ([modules/forgejo-runner/runner/register.sh](../modules/forgejo-runner/runner/register.sh)); single-use runner pool ([modules/runner-pool/compose.yml](../modules/runner-pool/compose.yml)) | FIND-05, FIND-06 |
| Container runtime | Privileged Docker-in-Docker for Dojo Cloud ([modules/dojo-cloud/compose.yml](../modules/dojo-cloud/compose.yml)) | FIND-15 |

### Needs Verification
| Item | Question | What to Check | Why Uncertain |
|------|----------|---------------|---------------|
| FIND-05 PR workflow source | Does Forgejo run the PR head's version of `dns-preview.yml` for same-repo branches without approval? | Push a branch that edits the workflow and open a PR on a running dns-as-code stack | Forgejo Actions semantics were not tested live |
| FIND-03 home permissions | Are `/home/studentNN` directories `0700` or world-readable? | `ls -ld /home/student*` in the terminal | Depends on Debian `useradd` `HOME_MODE` defaults; not observed live |
| FIND-03 `su` availability | Does `su` work for students in the terminal image (PAM config)? | `su - student02` from student01 | Assumed from Debian util-linux defaults |
| app-db cross-database access | Can a student role `CONNECT` to another student's database? | `\c student02` as student01's dynamic role | `PUBLIC` CONNECT privilege revocation not confirmed |
| FIND-04 reachability | Can an AppHost slot open TCP to `web-terminal:9000-9899`? | `curl` from a deployed app on a vault-fundamentals stack | Inferred from compose networks and iptables rules |

### Finding Overrides
| Finding ID | Original Severity | Override | Justification | New Status |
|------------|-------------------|----------|---------------|------------|
| — | — | — | No overrides applied. Update this section after review. | — |

### Additional Notes

This was a static analysis of source and configuration only. The container runtime was not accessible from the analysis session (podman permission denied), so no finding was reproduced on a running stack or in a browser; the Needs Verification table lists the checks that matter most. The platform is intentionally a short-lived training lab, and several design comments (for example in `modules/dojo-cloud/compose.yml` and `modules/openbao/setup/setup.sh`) already acknowledge lab shortcuts; the findings still record them because the stack can be served on a real host (`--env home`).

---

## References Consulted

### Security Standards
| Standard | URL | How Used |
|----------|-----|----------|
| Microsoft SDL Bug Bar | https://www.microsoft.com/en-us/msrc/sdlbugbar | Severity classification |
| OWASP Top 10:2025 | https://owasp.org/Top10/2025/ | Threat categorization |
| CVSS 4.0 | https://www.first.org/cvss/v4.0/specification-document | Risk scoring |
| CWE | https://cwe.mitre.org/ | Weakness classification |
| STRIDE | https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats | Threat enumeration |

### Component Documentation
| Component | Documentation URL | Relevant Section |
|-----------|------------------|------------------|
| Caddy | https://caddyserver.com/docs/caddyfile/directives/reverse_proxy | `header_up`, `forward_auth` |
| code-server | https://coder.com/docs/code-server/FAQ | `--auth` options |
| Forgejo Actions | https://forgejo.org/docs/latest/user/actions/ | Pull request events, runner labels |
| OpenBao | https://openbao.org/docs/configuration/listener/tcp/ | `tls_disable`, audit `hmac_accessor` |
| step-ca | https://smallstep.com/docs/step-ca/provisioners/ | ACME and JWK provisioners |
| Docker-in-Docker | https://hub.docker.com/_/docker | Rootless variant |

---

## Report Metadata

| Field | Value |
|-------|-------|
| Source Location | `/home/scott/Development/GitOps_Dojo` |
| Git Repository | `https://github.com/fiddler110/GitOps_Dojo.git` |
| Git Branch | `feat/vault-fundamentals` |
| Git Commit | `6ca99bd` (`2026-09-25 21:19:58 -0400`) |
| Model | `Claude Opus 5.5 (claude-opus-5.5)` |
| Machine Name | `Scott-Desktop` |
| Analysis Started | `2026-09-26 15:42:08 UTC` |
| Analysis Completed | `2026-09-26 16:23:32 UTC` |
| Duration | `0h 41m 24s` |
| Output Folder | `threat-model-20260926-154208` |
| Prompt | `/threat-model-analyst` |

---

## Classification Reference

| Classification | Values |
|---------------|--------|
| **Exploitability Tiers** | **T1** Direct Exposure (no prerequisites) · **T2** Conditional Risk (single prerequisite) · **T3** Defense-in-Depth (multiple prerequisites or infrastructure access) |
| **STRIDE + Abuse** | **S** Spoofing · **T** Tampering · **R** Repudiation · **I** Information Disclosure · **D** Denial of Service · **E** Elevation of Privilege · **A** Abuse (feature misuse) |
| **SDL Severity** | `Critical` · `Important` · `Moderate` · `Low` |
| **Remediation Effort** | `Low` · `Medium` · `High` |
| **Mitigation Type** | `Redesign` · `Standard Mitigation` · `Custom Mitigation` · `Existing Control` · `Accept Risk` · `Transfer Risk` |
| **Threat Status** | `Open` · `Mitigated` · `Platform` |
| **Incremental Tags** | `[Existing]` · `[Fixed]` · `[Partial]` · `[New]` · `[Removed]` (incremental reports only) |
| **CVSS** | CVSS 4.0 vector with `CVSS:4.0/` prefix |
| **CWE** | Hyperlinked CWE ID (e.g., [CWE-306](https://cwe.mitre.org/data/definitions/306.html)) |
| **OWASP** | OWASP Top 10:2025 mapping (e.g., A01:2025 – Broken Access Control) |
