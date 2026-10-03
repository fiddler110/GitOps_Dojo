# Lab 3: Your first policy as code

**Time:** about 15 minutes, of which about 3.5 are waiting. **Goal:** write a real rule, "every resource must carry a `costCenter` tag", as a definition and an assignment in OpenTofu, watch it refuse a write, then fix the application so it passes.

> **Starting here?** This lab needs your clone with the app applied (Lab 0). Run `lab-prep 3` to set that up; it is safe to run even if you did the earlier labs.

## Read this first: policy applies are slow

Creating a policy definition takes about **100 seconds**, and creating an assignment takes about another **100 seconds**. The assignment cannot start until its definition exists, so applying a first policy takes about **3.5 minutes** in total. Nothing is wrong when `tofu apply` seems to hang.

The reason is **eventual consistency**. A cloud's policy service is spread over many servers, and a new definition or assignment takes a while to reach all of them. The provider does not return until it has seen the object everywhere, because otherwise the next step (assigning a definition that "does not exist yet") would fail at random. The wait is the provider being careful, not your laptop being slow. Sets, exemptions and remediations, which you meet later, do not have this wait.

Every lab that applies policy tells you this up front, and has a reading section for the wait. Start the apply, then read on.

## The scenario

Finance needs every resource to carry a `costCenter` tag so that the bill can be split by team. At the moment your application has no such tag. You will write the rule first, see it refuse a write, and *then* fix the app. That order matters in real life: the policy tells you what is wrong.

## 1. Read the rule

```bash
cd ~/lab/cloud-policy-as-code/policy/cloud
cat rules/require-costcenter-tag.json
```

```json
{
  "if": {
    "field": "tags['costCenter']",
    "exists": false
  },
  "then": {
    "effect": "[parameters('effect')]"
  }
}
```

If the tag `costCenter` does not exist, then apply whatever effect the assignment asked for. Two choices worth noticing:

- The rule describes the **bad case** (tag missing), as you learned in Lab 2.
- The effect is a **parameter**, not the word `deny`. The rule is written once and the assignment chooses how strict to be. You will use that in Lab 4.

The rule is a separate JSON file, not an inline string, so that an editor, a script or a test can read it as plain JSON.

## 2. Uncomment the definition and the assignment

Open `policy/cloud/main.tf` in VS Code. Lines 5 to 27 are commented out: a definition and an assignment. Uncomment them (select the lines and press `Ctrl+/`), or do it from the terminal:

```bash
sed -i '5,27s/^# \{0,1\}//' main.tf
tofu fmt
sed -n 1,30p main.tf
```

Now read what you enabled:

```hcl
resource "azurerm_policy_definition" "require_costcenter" {
  name         = "require-costcenter-tag"
  policy_type  = "Custom"
  mode         = "All"
  display_name = "Require a costCenter tag"

  policy_rule = file("${path.module}/rules/require-costcenter-tag.json")

  parameters = jsonencode({
    effect = {
      type          = "String"
      allowedValues = ["audit", "deny", "disabled"]
      defaultValue  = "deny"
    }
  })
}

resource "azurerm_subscription_policy_assignment" "require_costcenter" {
  name                 = "require-costcenter"
  subscription_id      = data.azurerm_subscription.current.id
  policy_definition_id = azurerm_policy_definition.require_costcenter.id
}
```

The **definition**:

- `policy_type = "Custom"`: yours, as opposed to the platform's `BuiltIn`.
- `mode = "All"`: evaluate every resource, resource groups too. The tag has to be on groups as well as containers, so `Indexed` would be wrong here.
- `policy_rule = file(...)`: the JSON from step 1.
- `parameters`: declares one parameter, `effect`, which may only be `audit`, `deny` or `disabled`, and defaults to `deny`.

The **assignment**:

- It names the definition by reference (`azurerm_policy_definition.require_costcenter.id`), so OpenTofu knows to create the definition first. That implicit dependency is also why you never need `depends_on` here.
- `subscription_id` is the **scope**: your whole subscription. This folder deliberately assigns at subscription scope, not on the resource group, so you can apply policy without needing `infra/` first.
- It supplies no `parameters`, so `effect` takes its default: `deny`.

## 3. Plan and apply

```bash
tofu init
tofu plan
```

```text
Plan: 2 to add, 0 to change, 0 to destroy.
```

```bash
tofu apply
```

Type `yes`. Now **leave it running** and read the next section. About 3.5 minutes later:

```text
azurerm_policy_definition.require_costcenter: Creating...
azurerm_policy_definition.require_costcenter: Still creating... [10s elapsed]
...
azurerm_policy_definition.require_costcenter: Creation complete after 1m40s
azurerm_subscription_policy_assignment.require_costcenter: Creating...
...
azurerm_subscription_policy_assignment.require_costcenter: Creation complete after 1m40s

Apply complete! Resources: 2 added, 0 changed, 0 destroyed.
```

(Exact times vary by a few seconds.)

## While it runs: reading

**Why a parameter for the effect?** Imagine the rule said `"effect": "deny"`. Switching to `audit` would mean editing the definition. A definition is shared: other assignments, and later a policy set, may use it. Changing it changes everyone's behaviour at once. A parameter moves the decision into the assignment, which is the place that knows the scope and the audience. This is the single most useful habit in policy design: *the definition says what is wrong; the assignment says how seriously.*

**What is the cloud doing for the 100 seconds?** It stores your JSON, validates it (unknown fields or operators are rejected when you create the definition), and replicates it. Try to picture the alternative: a deny rule that is active on one server and not on another for a minute. The wait buys consistency.

**What will it do to my existing app?** Nothing yet. Policy evaluates **writes**. A resource that already exists is never deleted or blocked by a new rule; it is just reported as non-compliant. You will see exactly that in step 5.

**Open the portal.** Keep the Policy blade open and refresh now and then. About 100 seconds in, **Require a costCenter tag** appears under Definitions with policy type Custom. About 100 seconds later, the **Assignments** list shows `require-costcenter`, scope your subscription.

**Think ahead.** The rule's first line is `"field": "tags['costCenter']"`. What would the rule do to a resource with the tag present but empty? (Answer: nothing. `exists` only asks whether the key is there. The built-in `env` rule used `isBlank` as well, because it cared. This rule does not.)

## 4. See it refuse a write

Your app was created before the rule existed, so the rule has not touched it. Make something new without the tag, in the scratch folder:

```bash
mkdir -p ~/lab/scratch && cd ~/lab/scratch
cp ~/lab/cloud-policy-as-code/infra/{providers,versions,variables}.tf .
sed -i 's#tfstate/infra#tfstate/scratch#' versions.tf
tofu init
cat > main.tf <<'EOT'
resource "azurerm_resource_group" "scratch" {
  name     = "rg-${var.owner}-scratch"
  location = "canadacentral"
  tags = {
    owner = var.owner
    env   = "dev"
  }
}
EOT
tofu apply -auto-approve
```

The group has `owner` and `env`, so it satisfies every built-in. Expected (abridged):

```text
Error: creating "Resource Group (Subscription: \"<your subscription id>\"\nResource Group Name: \"rg-student01-scratch\")": unexpected status 403 (403 Forbidden) with error:
RequestDisallowedByPolicy: Resource 'rg-student01-scratch' was disallowed by policy.
Policy: 'Require a costCenter tag'. Assignment 'require-costcenter', definition 'Require a costCenter tag':
tag 'costCenter' does not exist.
```

This is the form from Lab 1 with the extra detail that custom policies give: **which assignment** and **which definition** refused you, and the reason from your own rule. Everything is traceable back to the two resources in your `main.tf`.

Now add the tag and apply the scratch again; it is allowed:

```bash
sed -i 's/env   = "dev"/env   = "dev"\n    costCenter = "cc-1001"/' main.tf
tofu apply -auto-approve
```

```text
Apply complete! Resources: 1 added, 0 changed, 0 destroyed.
```

Remove it again (`tofu destroy -auto-approve`) before moving on.

## 5. What the policy thinks of your app

In the portal's **Policy** blade, open **Compliance**. Your `rg-<you>-app` and `ci-<you>-app` are listed as **NonCompliant** against `require-costcenter`, with the reason `tag 'costCenter' does not exist`. They are running, untouched, and flagged. This is the difference between *enforcement* (blocks new writes) and *compliance* (reports what exists).

Compliance is recomputed on every write and on demand, so it goes green as soon as you fix the resource.

## 6. Fix the application

The app's tags live in one place, `locals` in `infra/main.tf`. Edit it so that it reads:

```hcl
locals {
  # owner and env are required by the built-in guardrails; Lab 3 adds costCenter.
  tags = {
    owner      = var.owner
    env        = "dev"
    costCenter = "cc-1001"
  }
}
```

(You can change the comment to anything. Only the `costCenter` line matters.) Check it and apply:

```bash
cd ~/lab/cloud-policy-as-code/infra
tofu fmt
tofu plan
```

```text
Plan: 0 to add, 2 to change, 0 to destroy.
```

Two in-place changes: a tag added to the resource group and to the container group. Nothing is replaced, so the app keeps running.

```bash
tofu apply -auto-approve
```

```text
Apply complete! Resources: 0 added, 2 changed, 0 destroyed.
```

The policy checked these two writes and allowed them, because the tag is now present. Back in the portal, **Compliance** now shows both resources as **Compliant**.

## 7. Commit it

```bash
cd ~/lab/cloud-policy-as-code
git status --short
git add infra policy
git commit -m "Require a costCenter tag, and tag the app"
```

Commit but do **not** push yet. Pushing to `main` starts the Apply pipeline, which is Lab 11's subject.

## Check

- [ ] The Policy blade lists the definition `Require a costCenter tag` and the assignment `require-costcenter`.
- [ ] A resource group without `costCenter` was refused with a 403 naming the assignment and the definition.
- [ ] `ci-<you>-app` and `rg-<you>-app` show Compliant after you added the tag.

```bash
cd ~/lab/cloud-policy-as-code/policy/cloud && tofu state list
```

```text
data.azurerm_subscription.current
azurerm_policy_definition.require_costcenter
azurerm_subscription_policy_assignment.require_costcenter
```

## Recap

- A definition plus an assignment is a working policy. The assignment's **scope** decides who is covered.
- Applying either takes about 100 seconds because the cloud makes sure the policy is everywhere before it says "done".
- A new rule blocks new writes; existing resources are flagged, not removed.
- The refusal names the assignment and the definition, so you can always trace it back to code.
- Make the effect a parameter so the assignment, not the rule, decides how strict to be.

**Next:** [Lab 4](lab4.md): what if you cannot just deny? Audit mode and compliance.
