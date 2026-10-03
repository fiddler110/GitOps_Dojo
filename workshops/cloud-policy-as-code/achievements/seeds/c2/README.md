# Challenge c2: Waiver With a Deadline

A new rule says every resource group needs a `reviewedBy` tag. The group `rg-{user}-c2` predates the
rule, and its owner has two weeks to sort it out. Give them a reviewed, dated waiver, as code.

0. Apply the starter once before you add anything (`tofu init && tofu apply`): the group must exist
   before the rule does, because a deny refuses a *new* group without the tag.
1. `main.tf` already has the resource group and a `deny` definition (`rules/require-reviewedby.json`).
   Assign the definition **at the scope of `rg-{user}-c2` only**. After the apply the Policy blade lists
   `rg-{user}-c2` as non-compliant (an existing resource is not removed by a deny, only reported).
2. Add an `azurerm_resource_group_policy_exemption` for that assignment on `rg-{user}-c2`: category
   `Waiver`, a description a reviewer could act on, and an `expires_on` **at most 14 days** from today.
3. `tofu apply`, then check the blade: the assignment shows **Exempt: 1** and no non-compliant resource.
4. Commit and push `main.tf` (`git push origin main`), then run `dojo-check c2`.
5. When it passes, `tofu destroy` and run `dojo-check c2` again: nothing of the challenge may be left
   assigned at `rg-{user}-c2`.
