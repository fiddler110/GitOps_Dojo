# Roadmap

Every piece of open work in one place. Each line is a summary; the linked plan holds the steps, decisions and
verify lines, and stays the source of truth for them. When a task is done, tick it in its plan (with the commit
SHA) and update or remove its line here.

Last updated: 2026-09-28 · Working branch: `feat/vault-fundamentals` (`main` is behind it with nothing of its own)

| Plan | What it covers | Status |
|------|----------------|--------|
| [`threat-model-20260926-154208/REMEDIATION-PLAN.md`](threat-model-20260926-154208/REMEDIATION-PLAN.md) | Fixes for the 19 threat-model findings (report in the same folder) | Agreed (D1-D14), nothing built |
| [`workshops/vault-fundamentals/PLAN.md`](workshops/vault-fundamentals/PLAN.md) | The vault-fundamentals workshop | P0-P4 done, P5 content built, T5.6 open |
| [`engine/student-reset.md`](engine/student-reset.md) | Facilitator reset of one student's whole environment | Planned, decisions "proposed" |
| [`engine/MODULES-PLAN.md`](engine/MODULES-PLAN.md) | Workshop modules and extensions (merged, PR #2) | Only the user's browser pass open |
| [`workshops/tofu-basics/PLAN.md`](workshops/tofu-basics/PLAN.md) | tofu-basics (merged, PR #1) | Only manual checks open |

## Now

1. **vault-fundamentals T5.6: the long live pass.** `./run.sh vault-fundamentals --test 20`, then
   `bash workshops/vault-fundamentals/tests/e2e.sh --load 30`, the Audit tab in a browser, the facilitator's view
   of bots, `./run.sh stop` leaves nothing; fill in README "Sizing". It covers the weekend's lab and slide changes
   (labs 0-13, the new bot step `step_vf_lab10`), which so far have had no run on a stack.
2. **Remediation P0: live verification** (T0.1-T0.5). Four static findings to confirm or downgrade on a real stack
   before changing code: `su` between students (FIND-03), app/runner → `web-terminal:9001` (FIND-04), same-repo PR
   runs a modified workflow (FIND-05), cross-student `\c` on app-db. Can share the T5.6 stack for the vault checks.
3. **Commit the weekend's uncommitted work** (yours): the `/admin` sidebar layout (`engine/allocator/server.py`),
   Mermaid in the lab reader (+ Prism `python`), zsh aliases, vault labs 3-6 and slide edits, threat-model table
   formatting.

## Next: security remediation (P1-P3)

Goal: overall rating **Elevated → Moderate**, no Tier 1 and no Critical/Important Tier 2 finding left open.

| Task | Finding | What | Scope |
|------|---------|------|-------|
| T1.1 | FIND-01 Important | Refuse default passwords off localhost; generated secrets; gateway rate limit (`caddy-ratelimit`) | engine, approved |
| T1.2 | FIND-02 Low | All of `/slides` behind the class gate (Playwright checks then need credentials) | engine, approved |
| T1.3 | FIND-08 Moderate | Warn on plain HTTP off localhost, HSTS, LAN-over-HTTPS recipe | engine, approved |
| T1.4 | FIND-13 Low | One structured log line per identity / control-plane decision | engine, approved |
| T1.5 | FIND-18 Low | Pin every image by digest, `check-pins.sh` in `--dry-run` | all, approved |
| T2.1 | FIND-03 **Critical** | Lock student Linux passwords, per-student Forgejo password (HMAC seed) and token, homes `0700`, rewrite labs that mention the password | engine, approved |
| T2.2 | FIND-04 Important | `terminal_ingress` network + `INPUT` rules for IDE ports; app-host egress allowlist | engine, approved + workshop |
| T2.3 | FIND-10 Moderate | Secrets off the command line in labs; PID-namespace spike | workshop; engine part ask |
| T3.1 | FIND-05 Important | dns-api trusts Actions OIDC tokens, not IP; PR model (Q-A); dns-as-code on `runner-pool` | workshop + module |
| T3.2 | FIND-11 Moderate | Per-student DNS API keys | workshop |
| T3.3 | FIND-09 Moderate | step-ca secrets and a name policy | workshop |
| T3.4 | FIND-07 Moderate | `/assign` rate limit, allocator timeouts | engine, **ask** |
| T3.5 | app-db | `REVOKE CONNECT ... FROM PUBLIC` (only if P0 shows the leak) | workshop |

## Later

- **Remediation P4-P6:** drop caps / `no-new-privileges` for runner-pool and app-host (T4.1), allocator pages to
  static scripts + CSP + `textContent` (T4.2, engine ask), rate limits and shared pools (T4.3), Tier 3 defence in
  depth (T5.1-T5.4: DinD socket, `.env` `0600` and per-upstream gateway tokens, OpenBao provisioner token revoked
  after setup, accepted plaintext to OpenBao/Postgres), then an incremental `/threat-model-analyst` run (T6.1).
- **Student reset** (R0-R4): check the risks on a live stack (R0), then the account hooks, `/admin` Reset, service
  resets per module. Its §8 questions (Q1-Q7) need answers first. **Clashes with remediation to settle before
  building:**
  - Q2 wants a resident service holding the OpenBao provisioner token; remediation D11/T5.3 revokes that token after
    every start. Pick one: a reset endpoint that re-derives a short-lived token from the unseal key the way T5.3
    does, or narrow D11.
  - T2.1 (per-student password seed, `~/.git-credentials` token, homes `0700`) changes account provisioning, which
    R1.1 extracts from `entrypoint.sh`. Do T2.1 first, or build R1.1 with the D13 seed in mind; a reset must
    re-issue the student's Forgejo token.
- **Merge `feat/vault-fundamentals` → `main`** after T5.6 (brings a24d0e7, the `run.sh --env` fix for workshops with
  modules, and ca89792 `/forgejo-login?next=`). Cherry-pick a24d0e7 to `main` sooner if `--env home` is needed there.
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
- `AGENTS.md` is a committed copy of the git-ignored `CLAUDE.md` and will drift from it. Pick one: keep only
  `AGENTS.md`, or make one a symlink to the other.
- `workshops/vault-fundamentals/PLAN.md`: the header's status and "Last updated" still say P3/P4; T5.7-T5.11 say
  "(uncommitted)" but are in 95c9c71 and c15d66e.
