# cloud-policy-as-code: Cloud-Policy-as-Code

Write the rules that keep a cloud safe as code. Students use **Dojo Cloud Policy** (the same model as the big
clouds' policy services) through OpenTofu: definitions, assignments, parameters, sets, modify and remediation,
exemptions; then Rego and conftest to check a plan before it is applied, `opa test`, a CI pipeline and drift.
For anyone who has done [OpenTofu Basics](../tofu-basics/) and [Git Fundamentals](../git-fundamentals/).

```sh
cd engine && ./run.sh cloud-policy-as-code
```

**Running it as the facilitator? Read [`FACILITATOR.md`](FACILITATOR.md).** Depth over length: the session is
about 4 to 5 hours of content (about 4.8 with the capstone) (below). Split it over two sittings (labs 0-6, then 7-12) if you can.

## Running it

```sh
cd engine
./run.sh setup                       # first time only
./run.sh cloud-policy-as-code        # build (first time: several minutes) and start
./run.sh stop                        # stop and wipe everything
```

`.env` must set `PUBLIC_BASE_URL` and `GATEWAY_TOKEN`. Always start through `./run.sh`; run `./run.sh stop`
before restarting after an image change. Only amd64 has been built.

## Labs

| Lab | Topic | Minutes (estimate) |
| --- | ----- | ------------------ |
| 0 | Setup: fork, clone, `lab-prep 0` (CI secrets, branch protection), apply the app | 10 |
| 1 | Why guardrails: the 403 and the Policy blade | 8 |
| 2 | Anatomy of a definition; predict three cases | 12 |
| 3 | First policy as code: `require-costcenter-tag` (slow apply) | 15 |
| 4 | Audit and compliance; audit before deny | 12 |
| 5 | Parameters and reuse: one definition, two assignments, DoNotEnforce | 15 |
| 6 | Policy sets | 15 |
| 7 | Modify and remediation | 30 |
| 8 | Exemptions, reviewed as a PR | 20 |
| 9 | Shift left with Rego and conftest | 25 |
| 10 | Testing policies; fix a planted bug | 25 |
| 11 | Policy in the pipeline: PR checks, merge, apply | 30 |
| 12 | Drift | 25 |
| Capstone | A new rule end to end | 45 |

**Timings are estimates, not measurements.** Nothing here has been run with a class. The big honest number: creating
or destroying a policy definition or assignment takes about **100 seconds** each (the provider waits for the cloud's
eventual consistency), and the waits run in parallel, so one apply with several of them is about **3.5 minutes**.
Each lab is built around one policy apply and gives students something to read while it runs. Never chain
assignments with `depends_on`: that serialises the waits.

## What is in this folder

| Path | What it is |
| ---- | ---------- |
| `workshop.env` | Identity; `MODULES="dojo-cloud runner-pool sensei"`; points at the overlay |
| `check-pins-sync.sh` | Fails if a terminal file copied from `tofu-basics` has drifted (not `mirror.tf`: this pack mirrors its own providers) |
| `compose/docker-compose.override.yml` | CI jobs get tofu, opa, conftest, the offline provider mirror (`tofu_mirror` volume, filled by `tofu-mirror-init`), the Dojo Cloud CA, and runner_net aliases on `cloud-api` |
| `compose/terminal/` | Terminal image: OpenTofu, azurerm 5.6.0 offline mirror, opa 1.21.1, conftest 0.71.0, `lab-prep` |
| `content/slides/`, `content/lab/` | Deck, labs and cheat sheet |
| `content/sample-repo/` | Seed for `platform-team/cloud-policy-as-code`: `infra/`, `policy/cloud/`, `policy/rego/`, `.forgejo/workflows/` |
| `content/solutions/labN/` | The policy/cloud and infra files at the END of lab N; `lab-prep` stacks them |

## How CI works here

`lab-prep 0` saves the student's `ARM_*` login as Actions secrets on their fork and protects `main` (merging
needs the `Policy check / check (pull_request)` status). Jobs run in runner-pool (`runs-on: host`) with
`SSL_CERT_FILE=/run/cloud-pki/dojo-cloud-ca.pem`, `TF_CLI_CONFIG_FILE=/providers/tofurc`, `TF_VAR_owner` from the
fork's owner and `ARM_METADATA_HOSTNAME=management.dojo.cloud`.

Built-in guardrails (platform scope, readable, not changeable): Canadian regions, `owner` and `env` tags, images
`dojo/hello:1.0` and `2.0`, cpu and memory caps, port 80, at most 10 env vars. Names (`rg-*`, `ci-*`) and the
2-container-group quota are plain validation, not policy.

## Testing

Unit-level checks (no stack): `opa test` over `content/sample-repo/policy/rego/`, `conftest` against sample plans, and
`tofu validate` on the solutions.

Stack runs (use the fast bots; plain `--test` is for demos):

```sh
./run.sh cloud-policy-as-code --test 3 --fast                             # bots, one round, done markers
workshops/assets/smoke.sh cloud-policy-as-code --bots 1 --timeout 120      # full smoke
workshops/assets/retest.sh cloud-policy-as-code <lab> [--only]             # re-run from one lab (--only: just that lab)
```

A full smoke takes about an hour, because the azurerm provider waits about 100 seconds per policy create and delete.
The `sensei` module serves ready answers (`sensei/answers.json`) for the labs.

## Known limits

- Not yet run end to end with a class; timings are estimates.
- OpenTofu and the VS Code extension are pinned here and in `tofu-basics`/`dojo-introduction`;
  `engine/scripts/check-tool-pins.sh` (every `--dry-run`) fails if the copies disagree, so bump them together.
- arm64 checksums are pinned, but only amd64 has been built and tested. Student terminals have no internet: tools and the provider are baked in.
- The built-in guardrails are fixed; students cannot change platform-scope policy.
- Dojo Cloud is Azure-inspired practice software, not a real cloud.
