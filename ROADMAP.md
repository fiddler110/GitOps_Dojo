# Roadmap

Every piece of open work in one place. Each line is a summary; the linked plan holds the steps, decisions and
verify lines, and stays the source of truth for them. When a task is done, tick it in its plan (with the commit
SHA) and update or remove its line here.

Last updated: 2026-09-29 · Working branch: `feat/remediation` (from `main` after PR #3, 3a59106; the merged feature branches are deleted)

| Plan                                                                                                   | What it covers                                                     | Status                                  |
| ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ | --------------------------------------- |
| [`threat-model-20260926-154208/REMEDIATION-PLAN.md`](threat-model-20260926-154208/REMEDIATION-PLAN.md) | Fixes for the 19 threat-model findings (report in the same folder) | P0-P2 done; P3 built; P4 scoped        |
| [`workshops/vault-fundamentals/PLAN.md`](workshops/vault-fundamentals/PLAN.md)                         | The vault-fundamentals workshop                                    | P0-P5 done, merged (PR #3)              |
| [`engine/student-reset.md`](engine/student-reset.md)                                                   | Facilitator reset of one student's whole environment               | Planned, decisions "proposed"           |
| [`engine/MODULES-PLAN.md`](engine/MODULES-PLAN.md)                                                     | Workshop modules and extensions (merged, PR #2)                    | Only the user's browser pass open       |
| [`workshops/tofu-basics/PLAN.md`](workshops/tofu-basics/PLAN.md)                                       | tofu-basics (merged, PR #1)                                        | Only manual checks open                 |

## Now

1. **Remediation P3 built, P4 scoped** (2026-09-29). Order set by the user: **do the work first, test everything at
   the end** in one combined pass (T4.5 in the remediation plan).
   1. **Docs and content, done and uncommitted:** `engine/README.md` and `modules/forgejo-runner/README.md` (T3.6),
      the cert-autorenewal lab-5 cron fix (`bots/steps.sh`, `lab/lab5.md`). Review, then commit.
   2. **P4 work, built 2026-09-29 (uncommitted, untested live):** ([`P4-SCOPING.md`](threat-model-20260926-154208/P4-SCOPING.md); design rule D17: every limit is a
      tripwire with an env knob, nothing reduces what students can do): T4.1 caps on runner-pool, its shim and
      app-host (incl. dojo-introduction) → T4.3a-c OpenBao quota, app-db per-database limit, per-identity buckets
      → T4.2 allocator CSP (engine, ask) → T4.3d terminal `nproc` (engine, ask) → T4.4 docs. D18 confirmed; engine edits done.
   3. **Then T4.5, the one combined live pass** (locally, one stack at a time, `podman ps` first): cert-autorenewal
      `--test 2` (cron fix + off-zone refusal), dns-as-code `--test 3` (merge still applies `dojo.test`),
      dojo-introduction, git-fundamentals `--test 3`, T3.4 rest (`/auth-check` under 1 s with 5 idle sockets, Release
      unused in a browser, vault `checks.sh` + `p2_browser.py`) and the P4 checks. Passed already on 2026-09-29 (before
      P4 changes): dns-as-code incl. a facilitator merge writing `dojo.test`, dojo-introduction, git-fundamentals.
      Then tick T3.6 and P4, and ask before P5.
   Q-A confirmed: (A). Set `GATEWAY_TRUSTED_PROXIES` in `.env.home` on the next home run.
2. **Small T5.6 follow-up:** the facilitator's VS Code tab needed a retry under load (a 404 and a VS Code
   "unknown error"). Not reproduced locally at 10 bots (2026-09-28: 12 loads, 6 of them concurrent cold starts, all
   fine). The 404 is code-server's optional `vsda` files, on every load and harmless. The "unknown error" is
   unexplained; recheck at the first 20+ student run, with the `/auth-check` logging added in remediation T1.4.
   Sizing for 20-35 students is extrapolated from 10 bots.

## Order agreed with the student-reset plan (2026-09-28)

1. Remediation P0 (+ reset R0 on the same stack) → 2. remediation P1 → 3. **reset R1.1**: `provision-account.sh`
   extracted from `entrypoint.sh`, no behaviour change (engine, ask) → 4. **remediation T2.1** built inside that
   script → 5. the rest of the remediation, where **T5.3** also mints a narrow **reset token** for a resident
   `openbao-reset` service → 6. reset R1.2 onwards.

Decisions: remediation D15/D16, reset R9/R10. D11 stays: no long-lived provisioner token, and the unseal key never
leaves `openbao-setup`.

## Next: security remediation (P1-P3)

Goal: overall rating **Elevated → Moderate**, no Tier 1 and no Critical/Important Tier 2 finding left open.

| Task | Finding              | What                                                                                                                                   | Scope                       |
| ---- | -------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | --------------------------- |
| R1.1 | (reset plan)         | Move per-account setup to `provision-account.sh`, no behaviour change; before T2.1                                                     | engine, **ask**             |
| T2.1 | FIND-03 **Critical** | Lock student Linux passwords, per-student Forgejo password (HMAC seed) and token, homes `0700`, rewrite labs that mention the password | engine, approved            |
| T2.2 | FIND-04 Important    | `terminal_ingress` network + `INPUT` rules for IDE ports; app-host egress allowlist                                                    | engine, approved + workshop |
| T2.3 | FIND-10 Moderate     | Secrets off the command line in labs; PID-namespace spike                                                                              | workshop; engine part ask   |
| T3.1 | FIND-05 Important    | dns-api trusts Actions OIDC tokens, not IP; PR model (Q-A); dns-as-code on `runner-pool`                                               | workshop + module           |
| T3.2 | FIND-11 Moderate     | Per-student DNS API keys                                                                                                               | workshop                    |
| T3.3 | FIND-09 Moderate     | step-ca secrets and a name policy                                                                                                      | workshop                    |
| T3.4 | FIND-07 Moderate     | `/assign` rate limit, allocator timeouts                                                                                               | engine, **ask**             |
| T3.5 | app-db               | `REVOKE CONNECT ... FROM PUBLIC` (only if P0 shows the leak)                                                                           | workshop                    |

## Later

- **Remediation P4-P6:** drop caps / `no-new-privileges` for runner-pool and app-host (T4.1), allocator pages to
  static scripts + CSP + `textContent` (T4.2, engine ask), rate limits and shared pools (T4.3), Tier 3 defence in
  depth (T5.1-T5.4: DinD socket, `.env` `0600` and per-upstream gateway tokens, OpenBao provisioner token revoked
  after setup, accepted plaintext to OpenBao/Postgres), then an incremental `/threat-model-analyst` run (T6.1).
- **Student reset** (R0-R4): R0 (live risk checks) can run on the P0 stack. R1.1 comes before remediation T2.1
  (below); R1.2 onwards after it; R3.2 (OpenBao) after remediation T5.3. Its §8 questions Q1 and Q3-Q7 are still
  open.
- **vault-fundamentals follow-ups** (PLAN §13): policy as code (OpenTofu `vault` provider or `bao policy write` in
  CI), OpenBao PKI for `cert-autorenewal`, mirroring a pinned set of actions into Forgejo. Lab 11 doesn't yet show
  a restart logging in again (lab 10 ends on that promise).
- **tofu-basics follow-ups** (PLAN T10.x): `dojo` CLI, CI `plan` on pull requests, more resources, a remote state
  backend. Stretch labs 11-12 (T6.4) only if wanted.

## Manual checks (the user, in a browser)

- **vault-fundamentals:** the P4 browser pass (My App card, `/admin` Apps tab, labs 9-13 in the reader, Part 6
  slides) and a person walking labs 7-9 in the UI.
- **Modules (MODULES-PLAN T3.4):** the per-workshop browser checklist in its §7.
- **tofu-basics T9.4** (human dry-run with 3-5 people) and **T9.9** (browser pass over labs 4-10 and the portal).
  Steps: [`workshops/tofu-basics/TEST-PLAN.md`](workshops/tofu-basics/TEST-PLAN.md).
- **This weekend's UI changes:** the `/admin` sidebar at desktop width and under 700 px, and Mermaid diagrams in
  the lab reader, light and dark.

## Housekeeping

- `handouts/*.pptx` are committed binaries of 30-36 MB, and every deck change adds a full copy to git history.
  Consider Git LFS or publishing them as release assets instead.
- `handouts/build-presentations.sh` hashes all of `workshops/assets/` as a deck input, so a lab-reader-only change
  re-exports every deck (new ~15-36 MB blobs with identical slides). Narrow `shared=` to what Marp reads (the
  themes, not `lab-reader.*` or `vendor/`).
