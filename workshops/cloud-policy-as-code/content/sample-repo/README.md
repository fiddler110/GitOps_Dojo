# cloud-policy-as-code

Policy as code for Dojo Cloud: the rules live in git, are reviewed in pull requests, and are applied by CI.

- `infra/`: a small deployment (one resource group, one container group) that the policies govern.
- `policy/cloud/`: OpenTofu that writes Dojo Cloud Policy objects (definitions, assignments, exemptions).
- `policy/cloud/rules/`: the policy rules as plain JSON, loaded with `file()`.
- `policy/rego/`: Rego rules and tests that check a plan before anything is applied.
- `policy/rego/fixtures/`: cut-down `tofu show -json` plans used by the Rego tests.
- `.forgejo/workflows/`: `pr.yml` (plan and check), `main.yml` (apply), `drift.yml` (detect out-of-band changes).

Your username reaches OpenTofu as `TF_VAR_owner` (the terminal and CI set it), so there is nothing to edit before you start. Parts of `policy/cloud/main.tf` are commented out with the lab that enables them.
