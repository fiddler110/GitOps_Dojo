# Roadmap

Every piece of open work in one place. Each line is a summary; the linked plan holds the steps, decisions and
verify lines, and stays the source of truth for them. When a task is done, tick it in its plan (with the commit
SHA) and update or remove its line here.

Last updated: 2026-09-29 · Working branch: `feat/remediation` (from `main` after PR #3, 3a59106; the merged feature branches are deleted)

| Plan                                                                                                   | What it covers                                                     | Status                                                |
| ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ | ----------------------------------------------------- |
| [`threat-model-20260926-154208/REMEDIATION-PLAN.md`](threat-model-20260926-154208/REMEDIATION-PLAN.md) | Fixes for the 19 threat-model findings (report in the same folder) | P0-P6 done; P6 was a validation pass, outstanding items in plan §8   |
| [`workshops/vault-fundamentals/PLAN.md`](workshops/vault-fundamentals/PLAN.md)                         | The vault-fundamentals workshop                                    | P0-P5 done, merged (PR #3)                            |
| [`engine/student-reset.md`](engine/student-reset.md)                                                   | Facilitator reset of one student's whole environment               | R1.1 done (7172d9b); rest planned, decisions "proposed" |
| [`engine/MODULES-PLAN.md`](engine/MODULES-PLAN.md)                                                     | Workshop modules and extensions (merged, PR #2)                    | Only the user's browser pass open                     |
| [`workshops/tofu-basics/PLAN.md`](workshops/tofu-basics/PLAN.md)                                       | tofu-basics (merged, PR #1)                                        | Only manual checks open                               |

## Now

1. **Remediation P6 (T6.1) done 2026-09-29 as a validation pass (no new threat model, user decision):** 15 Fixed,
   2 Partial (FIND-11, FIND-17), 2 Accepted (FIND-15, FIND-19); nothing Tier 1 or Critical/Important open. Details
   and the outstanding list are in the plan §8. Next: merge `feat/remediation` (ask first). P0-P5 are built, live-tested
   locally and committed (last code: 8387736; also lab 10 diagram as Mermaid, 7c44a3b). The landing page shows the student's own
   Forgejo password again (efda7c4, user request; reverses the T2.1c line).
   **run.sh progress (2026-09-29, user request):** `run.sh` shows a live status table while the stack starts and `stop`
   shows one while it comes down (terminal only; compose output goes to a log; plain lines when piped or `NO_COLOR`).
   45c4365, 5988594, f7e6e0e, 7b844cd, 6722f53. Drawing tested against live containers only; the first real start/stop
   is the test (a flicker fix, 6722f53, is untested in a real terminal).
2. **Known gaps from P4/P5 testing** (details in the remediation plan §8):
   - **Closed 2026-09-29:** OpenBao SSO "auth token expired" (user's browser only; `sso_browser.py` passes headless,
     put down to a stale `localStorage` token, closed by the user). The runner controller left `Created` after
     `./run.sh vault-fundamentals`: `podman-compose` waited for the one-shot `runner-token-init` to be *running*,
     it had already exited, so `up` hung. Fixed by `service_completed_successfully` (8387736); the next fresh start
     came up 16 of 16 healthy, no `ADMIN_PASSWORD` in the controller.
   - Passed on the vault stack, CLI: unit, tenancy, cli_login, setup_tokens, pool, audit, labs 2/5/8/10.
   - Not exercised: 300 app-db connections, the app-host shim on 443, vault second start (no `stop`; hooks re-run), vault pool/audit/browser
     areas after the e2e split, and a real-browser "Release unused".
   - `lab_12` failed once ("revoked: the login is gone") and passed on retry, probably a revoke vs `DROP ROLE` race,
     unconfirmed.
   - PowerDNS keys are still derived from the shared token.
   - dns-as-code, dojo-introduction and git-fundamentals were not re-run after P4 (scope cut by the user).
3. **Home run:** `GATEWAY_TRUSTED_PROXIES=10.0.0.2/32` is set in `.env.home` (2026-09-29, git-ignored). Unverified: on the next `--env home` run, check the gateway log shows client IPs from the proxy's `X-Forwarded-For` (not `10.0.0.2` for everyone); if podman NATs the source, use the address the log shows.
4. **Small T5.6 follow-up:** the facilitator's VS Code tab needed a retry under load (a 404 and a VS Code
   "unknown error"). Not reproduced locally at 10 bots (2026-09-28). The 404 is code-server's optional `vsda` files,
   harmless. The "unknown error" is unexplained; recheck at the first 20+ student run, with the `/auth-check`
   logging from remediation T1.4. Sizing for 20-35 students is extrapolated from 10 bots.

## Later

- **Student reset** (R0-R4): R1.1 (`provision-account.sh`) is done. R1.2 onwards can start; R3.2 (OpenBao) needs the
  reset token from remediation T5.3, which stays in `openbao-setup` until then. R0 (live risk checks) is not done.
  Its §8 questions Q1 and Q3-Q7 are still open. Decisions: reset R9/R10, remediation D15/D16; D11 stays (no
  long-lived provisioner token, the unseal key never leaves `openbao-setup`).
- **vault-fundamentals follow-ups** (PLAN §13): policy as code (OpenTofu `vault` provider or `bao policy write` in
  CI), OpenBao PKI for `cert-autorenewal`, mirroring a pinned set of actions into Forgejo. Lab 11 doesn't yet show
  a restart logging in again (lab 10 ends on that promise).
- **tofu-basics follow-ups** (PLAN T10.x): `dojo` CLI, CI `plan` on pull requests, more resources, a remote state
  backend. Stretch labs 11-12 (T6.4) only if wanted.
- **Merge `feat/remediation` to `main`** after P6 (open a PR; not pushed yet, push only when asked).

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
