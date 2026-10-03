# Lab 8: Exemptions, a reviewed way to say "not yet"

**Time:** about 20 minutes. **Goal:** grant a time-limited exception to a rule, and make the exception go through the same review as any other change to policy: a pull request on your fork.

> **Starting here?** This lab needs your clone, the app and legacy resource group applied, and the policy from Labs 3-7. Run `lab-prep 8` to set that up (the policy apply takes about 3.5 minutes). It is safe to run even if you did the earlier labs.

```bash
cd ~/lab/cloud-policy-as-code
```

---

## The problem

In Lab 4 you created `rg-<you>-legacy`, a resource group from before the tagging rule, with no `costCenter` tag. Since Lab 6 the `team-baseline` set denies resources without one. The legacy group is the textbook awkward case:

- Fixing it needs a migration ticket and a finance conversation that is not happening this week.
- Weakening the rule for everyone, or switching the assignment to `audit`, punishes every other team for one stray group.
- Doing nothing leaves a red non-compliant row on the Policy blade forever, until people stop looking at the blade, which is worse than the original problem.

An **exemption** is the answer: *this one resource is excused from this one rule, for a stated reason, until a stated date.* Everything else stays enforced.

## 1. See the problem first

Open the portal's **Policy** blade and find the `team-baseline` assignment. Under **Non-compliant** the legacy resource group is listed with the reason: it has no `costCenter` tag. Write down the **Exempt** count for that row (0).

## 2. Read the exemption

In `policy/cloud/main.tf`, find the block headed `# Lab 8: exemptions`. Uncomment the data source and the exemption:

```hcl
data "azurerm_resource_group" "legacy" {
  name = "rg-${var.owner}-legacy"
}

resource "azurerm_resource_group_policy_exemption" "legacy_costcenter" {
  name                            = "legacy-costcenter"
  resource_group_id               = data.azurerm_resource_group.legacy.id
  policy_assignment_id            = azurerm_subscription_policy_assignment.team_baseline.id
  policy_definition_reference_ids = ["costcenter"]
  exemption_category              = "Waiver"
  display_name                    = "Legacy RG costCenter waiver"
  description                     = "Legacy resource group predates the tagging rule; migration ticket OPS-123."
  expires_on                      = "2026-10-09T00:00:00Z"
}
```

Every argument is a decision somebody should be able to question:

| Argument | What it says |
|---|---|
| `resource_group_id` | The **scope** of the waiver: this resource group and what is in it, nothing else |
| `policy_assignment_id` | Which assignment is being waived: the `team-baseline` set |
| `policy_definition_reference_ids` | Which member of the set: only `costcenter`. The location and image rules still apply to the legacy group. Without this line the waiver would cover the whole set |
| `exemption_category` | `Waiver` (we accept the risk) or `Mitigated` (the risk is handled some other way, say so in the description) |
| `description` | The reason, and where to find the ticket. A waiver with no reason cannot be reviewed |
| `expires_on` | When the waiver stops applying. Exceptions without a date become permanent |

## 3. Set the expiry a week from today

The date in the file is only an example. Ask the machine for one a week out:

```bash
date -u -d '+7 days' +%Y-%m-%dT00:00:00Z
```

```text
2026-10-09T00:00:00Z
```

Put the value you got on the `expires_on` line. A week is long enough to do the migration and short enough that someone has to come back and decide again. When a waiver reaches its date it simply **stops applying**: the resource goes back to non-compliant and the blade shows the exemption as expired. Nothing is deleted, so the history stays visible.

## 4. Check it, then send it for review

Waivers are the one place where policy gets *weaker*, so they are the changes most worth a second pair of eyes. Do not apply this from your terminal. Put it on a branch:

```bash
git checkout -b waive-legacy-costcenter
cd policy/cloud && tofu fmt && tofu validate && cd ../..
git add policy/cloud/main.tf
git commit -m "Waive costCenter on the legacy resource group until 2026-10-09 (OPS-123)"
git push -u origin waive-legacy-costcenter
```

```text
 * [new branch]      waive-legacy-costcenter -> waive-legacy-costcenter
```

Now open the pull request on **your fork**:

1. In Forgejo, open your fork (`<you>/cloud-policy-as-code`) and click **New pull request**.
2. Set **both** sides to your fork: base `main`, compare `waive-legacy-costcenter`. (Forgejo may default the base to the team repo; change it, because the team repo is not where your waiver belongs.)
3. Title: `Waive costCenter on the legacy RG until 2026-10-09`. In the description, give the reason, the ticket and the date. That text is the review record.
4. Create the pull request and open the **Files changed** tab.

Read the diff as a reviewer would, with these questions:

- Is the scope as small as it can be (one resource group, one rule)?
- Is there a reason and a ticket in `description`?
- Is the expiry date short, and in the future?
- Would the waiver still make sense to someone reading it in a year?

On a team, this is where a colleague would approve or push back. Here you are your own reviewer, which is a fine way to see what a reviewer sees.

## 5. Merge, and let the pipeline apply it

The pull request shows a **Policy check** run (the `pr.yml` workflow). You will take it apart in Lab 11; for now wait for it to go green. `main` is protected, so the **Merge** button stays disabled until that check passes. Then merge.

Merging pushes to `main`, which starts the **Apply** workflow (`main.yml`). Open **Actions** in your fork and watch it: it applies `policy/cloud`, then `infra`. The exemption is instant, since only definitions and assignments are slow.

## 6. Check the result

Back in the portal's **Policy** blade, press **Evaluate now**:

- The `team-baseline` row shows **Exempt: 1**, and the legacy resource group has moved out of the non-compliant list.
- The **Exemptions** card lists `legacy-costcenter` with its category, reason and expiry date.
- The waiver is narrow: it names only `costcenter`. If the legacy group were also in a wrong region, the `locations` member of the set would still flag it.

Pull the merged change into your clone so it matches the cloud:

```bash
git checkout main
git pull
```

## What just happened

- You excused one resource from one rule, with a reason and an expiry date, instead of weakening the rule for everyone.
- The exception is **code**: it is in git, reviewed in a pull request, and applied by the same pipeline as the rule it bends. Compare that with a waiver granted in a chat message, which nobody can find in six months.
- An exemption **expires by itself**. The default for exceptions is "gone soon", so a forgotten waiver is a non-compliant resource, which is visible, rather than a hole, which is not.

## Check yourself

1. Why name `policy_definition_reference_ids` instead of waiving the whole set? *(only the rule that cannot be met is waived; the rest of the set still protects the group)*
2. What happens on the `expires_on` date? *(the exemption stops applying and the resource shows as non-compliant again; the exemption record stays)*
3. Why raise the waiver as a pull request instead of applying it from the terminal? *(it makes the weakening of policy a reviewed, recorded decision)*

**Check box.** You are done when all of these hold:

- [ ] The pull request is merged into your fork's `main` and the **Apply** run is green.
- [ ] The Policy blade shows `legacy-costcenter` under **Exemptions**, expiring a week from today.
- [ ] `team-baseline` shows **Exempt: 1** and the legacy group is no longer listed as non-compliant.
- [ ] `git status` in your clone is clean on `main`.

## Recap

A rule that is right but cannot be met by one resource yet needs an exception, not a weaker rule. A good exception has a narrow scope, a reason, an owner and an end date, and it goes through review like any other change. **Next:** [lab9.md](lab9.md): catching violations earlier than the cloud does, before anything is applied.
