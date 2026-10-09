# Cloud-Policy-as-Code workshop: plan

Status: **P0 done; P1-P4 built offline, not yet live** (written 2026-10-02; updated the same day). Roadmap item RV35. Decisions are numbered PC-D*,
spikes PC-S*, phases PC-P*. Once the workshop ships, freeze this file in `docs/archive/` like the other plans.

## 1. The idea in one paragraph

Students learn the cloud guardrail model that Azure Policy uses: **definitions** (a rule written as data), **assignments**
(that rule applied at a scope, with parameters), **effects** (deny, audit, modify, append, disabled), **compliance**
(which existing resources break the rule) and **exemptions**. They write those policies as code, put them in git, and
have a pipeline apply them. They then add the **shift-left** half: the same rule written in Rego and checked by
Conftest against the `tofu plan` JSON in a pull request, so a bad change fails in review before it ever reaches the
cloud. The takeaway: *catch it in the PR, enforce it in the cloud, and keep both in git.*

**Is it like Azure Policy?** Yes, that is the main thread. Dojo Cloud already has hard-coded guardrails written
"Azure Policy" style (`modules/dojo-cloud/cloud-api/policy.py`: Canadian regions only, required tags, allowed images,
size caps), and it already returns ARM-shaped `PolicyViolation` errors. This workshop makes those rules **data
driven** and lets students write, assign and audit their own. Inside the product it is called **Dojo Cloud Policy**
(branding rule: Azure-inspired, no Microsoft names). The slides can say "the same model as the big clouds' policy
services".

## 2. Where it sits

- **Learning path:** after `tofu-basics` (students already know `plan`/`apply`, the `azurerm` provider and Dojo
  Cloud) and before or after `vault-fundamentals`. Proposed `WORKSHOP_ORDER=5`.
- **Pack:** `workshops/cloud-policy-as-code/`, `MODULES="dojo-cloud runner-pool sensei"`. Fork workflow
  (`FORGEJO_FORK_WORKFLOW=1`) like tofu-basics: each student forks `platform-team/cloud-policy-as-code`.
- **No new services.** All new runtime is inside `cloud-api` (module code, not engine) plus two static binaries in
  the terminal and runner images. Capacity should match tofu-basics + vault-fundamentals' runner pool; confirm with
  `./dojo capacity` in PC-P7.

## 3. Two enforcement points

| | Shift-left (PR) | Cloud-side (Dojo Cloud Policy) |
|---|---|---|
| Rule language | Rego (OPA), run by `conftest` | Policy definition JSON (the `if`/`then` grammar), written via `azurerm_policy_definition` |
| Runs on | `tofu show -json plan.out`, in the terminal and in a runner-pool job | every ARM write to `cloud-api`, plus a compliance scan of what already exists |
| Catches | a bad change before merge | anything that bypasses the pipeline (portal clicks, a local `apply`, old resources) |
| Effects | pass / warn / fail | deny, audit, modify, append, disabled |

## 4. Cloud-side design (changes to the `dojo-cloud` module)

1. **Policy engine** (`cloud-api/policy_engine.py`, pure functions, no I/O). Evaluates a subset of the Azure Policy
   rule grammar against an ARM resource body:
   - Conditions: `field`, `equals`, `notEquals`, `in`, `notIn`, `like`, `notLike`, `contains`, `exists`, `less`,
     `greater` (and `OrEquals`), combined with `allOf`, `anyOf`, `not`.
   - Fields: `type`, `name`, `location`, `tags`, `tags['x']`, and a small fixed alias table for container-group
     properties (image, cpu, memoryInGB, ports, env count). Unknown aliases are rejected when the definition is
     written, with a message that names them.
   - `parameters()` with typed parameters (`String`, `Array`, `Integer`) and `allowedValues`.
   - Effects: `deny` (403 `RequestDisallowedByPolicy`, today's error shape), `audit` (write succeeds, result
     recorded), `modify` (add or replace a tag) and `append`, `disabled`.
2. **Built-in definitions.** Today's hard-coded checks become built-in definitions assigned at a fixed
   **platform scope** students can read but not change (like a tenant-root management group). Format and size checks
   that are not really policy (name regexes, body shape, `MIN_CPU`) stay as plain validation. **Regression gate:**
   `test_policy_auth`, `test_fuzz` and `tofu-basics --test` must pass unchanged, so tofu-basics sees no difference.
3. **ARM endpoints** that the pinned `azurerm` provider calls (exact list from PC-S1):
   - `Microsoft.Authorization/policyDefinitions` at subscription scope (built-ins listed read-only).
   - `policyAssignments` at subscription and resource-group scope, with parameters, `enforcementMode`
     (`Default`/`DoNotEnforce`) and `notScopes`.
   - `policyExemptions` (a waiver or mitigation with an expiry).
   - `policySetDefinitions` (initiatives): a set of definitions, with set-level parameters passed down to each
     member, assigned as one; compliance is shown per set and per member.
4. **Isolation (A20).** A student's definitions, assignments and exemptions live in their own subscription and apply
   only to it. No student can reach another's scope or the platform scope. Names are per subscription, so they never
   clash.
5. **Compliance.** After every write and on request (`POST .../policyStates/latest/triggerEvaluation`, or a portal
   button), each assignment is evaluated against the student's existing resources. The portal gains a **Policy**
   blade: assignments, compliant and non-compliant resources with the reason, exemptions. The facilitator's `/admin`
   tab shows every student's blade (the access rule). Strings rendered with `textContent` only.
6. **Remediation** for `modify`: a "Remediate" button (and the matching ARM call, if the provider exposes it) applies
   the tag change to existing resources.
7. **State.** Policy objects go in the existing `cloud-api` state, which already lives in a named volume, so
   `./dojo stop` wipes them with everything else.

## 5. Shift-left design

- Terminal and runner images get **`opa`** and **`conftest`**: static builds, version-pinned and sha256-verified per
  architecture, added in the workshop's `compose/terminal/Dockerfile`. They reach jobs through runner-pool's
  `JOB_TOOLS="opa conftest tofu"`.
- The seed repo holds `infra/` (a small Dojo Cloud deployment), `policy/rego/` (Rego plus `*_test.rego`),
  `policy/cloud/` (the HCL that writes definitions and assignments) and `.forgejo/workflows/`:
  - **pr.yml:** `tofu plan` → `tofu show -json` → `conftest test`, then `opa test policy/rego`. A failing policy
    blocks the merge (branch protection on the fork).
  - **main.yml:** on merge, `tofu apply` in `policy/cloud/`, then `infra/`.
  - **drift.yml** (manual dispatch, or each push): `tofu plan -detailed-exitcode` on `policy/cloud/` shows when
    someone changed or disabled an assignment in the portal.
- Plans run with the student's own Dojo Cloud credentials, which the runner gets as Actions secrets on the fork (the
  same pattern as vault-fundamentals' CI login; to be decided in PC-S4).

## 6. Labs (draft, 12 plus a capstone)

| Lab | Topic | Student does |
|---|---|---|
| 0 | Setup | Fork, clone, `lab-prep 0`, look at the repo layout |
| 1 | Why guardrails | `apply` a resource in a disallowed region; read the `PolicyViolation` error; find the built-in definition in the portal |
| 2 | Anatomy of a definition | Read a built-in's JSON: `if`/`then`, fields, effect, parameters; definition vs assignment |
| 3 | First policy as code | `azurerm_policy_definition` requiring a `costCenter` tag; assign it to your resource group; watch the next `apply` get denied; fix the HCL |
| 4 | Audit and compliance | Switch to `audit`; old resources show as non-compliant in the Policy blade; why teams audit before they deny |
| 5 | Parameters and reuse | One "allowed images" definition, two assignments with different parameters; `enforcementMode = DoNotEnforce` as a dry run |
| 6 | Policy sets (initiatives) | Group the tag, location and image rules into a "team baseline" set with `azurerm_policy_set_definition`; pass set parameters down to members; assign the set once; read compliance per set and per member; add a rule to the set and watch it apply without a new assignment |
| 7 | Modify and remediation | Auto-add `env = lab` to resources that lack it; run a remediation on existing ones |
| 8 | Exemptions | A time-limited exemption for one resource, with a reason, reviewed in a PR |
| 9 | Shift left with Rego | The same `costCenter` rule in Rego; `conftest test` on the plan JSON in the terminal |
| 10 | Testing policies | `opa test` with passing and failing fixtures; why a policy without tests is a liability |
| 11 | Policy in the pipeline | Open a PR that breaks a rule: CI fails it; fix it, merge, and `main.yml` applies the policies |
| 12 | Drift | Disable an assignment in the portal; the drift job flags it; git wins |
| Capstone | | A new rule end to end (Rego + cloud definition + tests + PR), verified by Sensei / achievements |

Slides: about 20 (the guardrail problem, definitions/assignments/effects, scopes and inheritance, audit before deny,
shift-left vs enforcement, policy testing, exemptions as a process, drift). Cheat sheet: definition JSON fields,
effects, Rego basics, `conftest`/`opa` commands. Add a highlight.js grammar for Rego (`engine/presentation/engine.js`,
an engine file, so ask first) and a Prism one for the lab reader.

## 7. Phases

| Phase | Work | Done when |
|---|---|---|
| PC-P0 | Spikes PC-S1..S5 | Each has a written answer here |
| PC-P1 | Policy engine + built-ins in `cloud-api` | Unit tests for the grammar and effects; the existing dojo-cloud suites and `tofu-basics --test 3` unchanged |
| PC-P2 | ARM endpoints, compliance, exemptions, Policy blade, `/admin` view | A real `tofu apply` of each `azurerm_*policy*` resource works locally; portal checked with Playwright |
| PC-P3 | Pack scaffold: `workshop.env`, terminal Dockerfile (opa, conftest), seed repo, workflows | `./dojo cloud-policy-as-code --dry-run` clean; the stack starts; a PR pipeline runs on runner-pool |
| PC-P4 | Labs 0-12, slides, cheat sheet, `lab-prep N` | Every lab walked by hand locally; slides checked for overflow by screenshot |
| PC-P5 | Bots (`--test`), Sensei checks, achievements catalog | `--test 3` runs every lab green |
| PC-P6 | Capstone + achievements isolation (A20) | Catalog validator passes |
| PC-P7 | Live checks: capacity, class-sized `--test`, `--env home` | Results in RELEASES |

## 8. Spikes

- **PC-S1, provider wire calls.** Point the pinned `azurerm` at a request-logging stub and `apply`/`destroy` each
  policy resource: `azurerm_policy_definition`, `azurerm_policy_set_definition`,
  `azurerm_subscription_policy_assignment`, `azurerm_resource_group_policy_assignment`,
  `azurerm_resource_group_policy_exemption`.
  Record every method, path, `api-version` and the fields it reads back (it fails on missing ones). Also check
  what a `modify` assignment's `identity` block makes the provider call.
- **PC-S2, grammar subset.** Confirm the condition list in §4 covers labs 1-8, and nothing more is needed.
- **PC-S3, binaries.** `opa` (static) and `conftest` release pins and sha256 for amd64 and arm64; both run in the
  Alpine runner image.
- **PC-S4, CI credentials.** How a runner job gets the student's Dojo Cloud login without the student pasting a
  secret into the repo (fork Actions secrets set at setup, or a broker endpoint like the terminal's).
- **PC-S5, compliance cost.** A class of 30 with about 10 resources and 5 assignments each: evaluation must stay
  well under the portal's poll interval; evaluate on writes and on demand, never on every poll.

## 8a. Spike answers (2026-10-02)

- **PC-S1, provider wire calls** (azurerm 5.6.0, tofu 1.12.6, against a logging stub; detail in the spike notes):
  - Definitions `policyDefinitions` [2021-06-01] and sets `policySetDefinitions` [2025-01-01] at
    `{sub}/providers/Microsoft.Authorization/...`. The provider first GETs the built-in path
    `/providers/Microsoft.Authorization/policyDefinitions/{n}` (no subscription), then the subscription path.
  - Assignments `policyAssignments` [2022-06-01] at subscription and RG scope. **PUT must return 201 on create**
    (a 200 fails). `identity { type = "SystemAssigned" }` sends top-level `identity`; answer with `principalId`
    and `tenantId`.
  - Exemptions `policyExemptions` [2020-07-01-preview] (Waiver or Mitigated, `expiresOn`).
  - Remediation exists: `azurerm_resource_group_policy_remediation` →
    `{sub}/resourceGroups/{rg}/providers/Microsoft.PolicyInsights/remediations/{n}` [2021-10-01].
  - The data source by `display_name` lists `{sub}/providers/Microsoft.Authorization/policyDefinitions`; the list
    must include built-ins.
  - Responses need id, name and type plus the echoed properties.
  - Plan-time checks: `policy_rule` must be a JSON string; mode must be All or Indexed; assignment names are 1-64
    characters. The assignment's definition id isn't checked, so our API must reject a missing definition.
  - **Speed:** each definition and assignment took about 1m41 to create (provider-side consistency polling). See
    PC-S1b.
- **PC-S2, grammar:** the §4 condition list covers labs 1-8 (location `in`, tag `exists`, image `in` on
  `containers[*]`, modify on `tags['x']`). Two Dojo extensions: `inExact` and the alias
  `containers[*].environmentVariableCount` (we have no `count`).
- **PC-S3, binaries:** opa v1.21.1 (static), conftest v0.71.0, sha256 pinned for amd64 and arm64; both run on Alpine
  and in the terminal image. They are installed in the workshop terminal Dockerfile and reach jobs through
  runner-pool `JOB_TOOLS: "opa conftest tofu"` in the workshop overlay.
- **PC-S4, CI credentials:** `lab-prep 0` (run as the student) asks the dojo-broker for the student's ARM_* values
  and PUTs them as Actions secrets on their fork through the Forgejo API (the vault labs already PUT secrets this
  way). cloud-api auth needs no change. **Needed:** the workshop overlay puts cloud-api on `runner_net`, with the
  `*.dojo.cloud` aliases, and gives jobs the Dojo Cloud CA (`SSL_CERT_FILE`). Verify live.
- **PC-S5, compliance cost:** evaluate on writes and on demand (trigger, or a portal button), never on a poll.
  30 students × 10 resources × 5 assignments is ~1,500 pure-Python evaluations: milliseconds.
- **PC-S1b, speed:** a fixed consistency wait inside azurerm 5.6.0; no API response shortens it. A definition
  create polls 10 × 10 s (~100 s); an assignment create or delete polls 20 × 5 s (~100 s). Sets, exemptions and
  remediations take 0 s. The waits run in parallel for independent resources, so one apply that creates
  definitions and then assignments costs ~200 s however many there are. **Open question for the user:** accept
  ~3.5 min policy applies (labs are written so each lab has one apply, and students read while it runs), or
  switch policy objects to `azapi_resource` (untested; adds a provider to the mirror and teaches a less common
  provider).

**Decisions added 2026-10-02 (build):**
- **PC-D8:** we accept azurerm's fixed consistency wait (PC-S1b); labs are written around one policy apply each.
- **PC-D9:** the terminal and CI share OpenTofu state through a Dojo Cloud `http` backend
  (`/_dojo/tfstate/<name>`, Basic auth with the student's ARM client id and secret, LOCK/UNLOCK, purged by
  `stop` and student reset). It's dojo-cloud module code, not engine.
- **PC-D10:** built-in guardrails for location and tags answer 403 RequestDisallowedByPolicy; image, cpu,
  memory, ports and env-var limits keep their 400 errors so tofu-basics is byte-identical.

## 9. Decisions so far

- **PC-D1:** Main thread is the Azure Policy model (cloud-side, data-driven), with Rego/Conftest as the shift-left
  half. Not Rego-only, because the cloud enforcement model is what the user asked for.
- **PC-D2:** Built on `dojo-cloud` and `runner-pool`; no new services, no engine changes except the Rego highlight
  grammar.
- **PC-D3:** Today's hard-coded guardrails become built-in definitions at a platform scope; tofu-basics behaviour
  must not change.
- **PC-D4:** Policy state lives in the existing `cloud-api` named volume, wiped by `./dojo stop`.
- **PC-D5 (user, 2026-10-02):** Full length. The goal is understanding the concept, not fitting a lunch hour:
  bigger within reason is better. No lunch-sized cut.
- **PC-D6 (user, 2026-10-02):** Policy sets (initiatives) get their own lab (lab 6), so `policySetDefinitions` is
  in scope for PC-P2.
- **PC-D7 (user, 2026-10-02):** Name `Cloud-Policy-as-Code` (`WORKSHOP_NAME="Cloud-Policy-as-Code"`, folder
  `workshops/cloud-policy-as-code/`).

## 10. Open questions for the user

None yet. New ones go here as the spikes turn them up.
