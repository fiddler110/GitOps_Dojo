# Remediation verification (T6.1), 2026-09-29

Baseline: `3-findings.md` (2026-09-26, rating Elevated). Method: commit per finding, an `rg` check of the fix in the
tree, and the local live passes recorded in `docs/archive/REMEDIATION-PLAN.md` (T3.6, T4.5, T5.x). Not a new threat model, and no
new live run.

| Finding | Sev | Verdict | Evidence |
|---|---|---|---|
| FIND-01 default creds, no brute-force limit | Important | Fixed | bf3b98c, d934055; `rate_limit` in gateway Caddyfile, default passwords refused |
| FIND-02 unauthenticated slides | Low | Fixed | cad3132 |
| FIND-03 shared student password | Critical | Fixed | 17fcb1a; per-student passwords, locked Linux accounts |
| FIND-04 open IDE/terminal ports | Important | Fixed | 47e477e |
| FIND-05 PR code on shared runner | Important | Fixed | de09a30; tests passed 2026-09-29 |
| FIND-06 runner/app-host root + caps | Moderate | Fixed | eb6b700; `cap_drop`, `no-new-privileges` |
| FIND-07 allocator slot exhaustion | Moderate | Fixed | 3056674, f20e260; threaded server |
| FIND-08 cleartext over HTTP | Moderate | Fixed | 94ca136; warning + HSTS |
| FIND-09 shared ACME CA | Moderate | Fixed | de09a30 |
| FIND-10 /proc visibility | Moderate | Fixed | 9074e7f, 1caf9d3; PID namespace per student |
| FIND-11 shared DNS key | Moderate | **Partial** | de09a30; PowerDNS keys still derive from the shared token |
| FIND-12 no rate/resource limits | Low | Fixed | a2d7363, eb6b700, 54c8924 |
| FIND-13 no identity logging | Low | Fixed | 244ff59 |
| FIND-14 allocator CSP | Low | Fixed | a2d7363 |
| FIND-15 privileged DinD | Important (T3) | **Accepted** | effe96b socket 0660; DinD stays (D9) |
| FIND-16 shared master secrets | Moderate | Fixed | 008441e, b560cfe, 72c82de; `engine/.env` mode 600 |
| FIND-17 unseal share / root-equivalent token | Moderate | **Partial** | 16b1f80; token revoked each start, single unseal share stays (D9) |
| FIND-18 mutable image tags | Low | Fixed | 6b047ca; only local `:local` builds unpinned |
| FIND-19 plaintext internal transport | Low | **Accepted** | documented (D9) |

**Totals:** 15 Fixed, 2 Partial, 2 Accepted. No Tier 1 finding and no Critical/Important Tier 2 finding open.
Overall rating Elevated -> Moderate by this validation, not a re-scored model.

## Outstanding (none Critical/Important)

- Vault second start (hooks re-run) untested.
- Not exercised: 300 app-db connections, app-host shim on 443, real-browser "Release unused".
- `lab_12` flaked once (revoke vs `DROP ROLE` race, unconfirmed).
- `GATEWAY_TRUSTED_PROXIES` unchecked on a home run.
- Facilitator VS Code "unknown error" under load, unexplained.
- dns-as-code, dojo-introduction, git-fundamentals not re-run after P4.
- PowerDNS keys derived from the shared token (FIND-11 remainder).
