# Challenge c1: Allowed Environments

Your platform team wants to know, without blocking anyone yet, which resources carry an `env` tag that
is not on an approved list. Different teams approve different lists, so the list is a **parameter**.

1. Finish `rules/allowed-envs.json`: a rule that flags a resource whose `env` tag is not in the
   array parameter `allowedEnvs`. Use the literal effect `audit` (it reports, it never refuses).
2. In `main.tf`, add a policy definition that uses the rule and declares `allowedEnvs` (type `Array`),
   and assign it **at the scope of the resource group `rg-{user}-c1` only** (an
   `azurerm_resource_group_policy_assignment`), with `allowedEnvs = ["dev", "test"]`.
3. `tofu init && tofu apply`. The resource group is tagged `env = "sandbox"`, so after the apply the
   Policy blade should list `rg-{user}-c1` as **non-compliant** for your assignment (press
   **Evaluate now** if you are impatient).
4. Commit and push `main.tf` and the rule to this repo (`git push origin main`), then run `dojo-check c1`.

Everything here lives in `rg-{user}-c1` and its own state, so your lab policy is untouched. Clean up
afterwards with `tofu destroy`.
