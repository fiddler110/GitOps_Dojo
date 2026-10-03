---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
    @import url('assets/themes/presentation.css');
footer: "[&larr; Hub](index.md) &nbsp;|&nbsp; Cloud Policy as Code | Engineering & IT Operations"
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# Cloud Policy as Code

## Guardrails that live in git, not in a wiki

Builds on OpenTofu Basics: same plan, review, apply loop, now applied to the rules themselves

**Talk + hands-on lab**

<!--
TIMING (talk ~30 min, then labs 0-12 and the capstone):
  Slides 2-6 (problem, model, anatomy) .. ~10 min
  Slides 7-12 (audit, params, sets, modify, exemptions) .. ~10 min
  Slides 13-20 (Rego, tests, pipeline, drift, slow applies) .. ~10 min
  Slides 21-22 recap and lab map .. ~2 min
Say early: policy applies are SLOW (about 3.5 min). That is not a bug.
-->

---

## Today

1. Why guardrails, and why as code
2. The model: definition, assignment, scope, effect
3. Rolling out safely: audit, compliance, exemptions
4. Reuse: parameters, policy sets, modify and remediation
5. Shift left: the same rule in Rego, with tests
6. The pipeline, drift, and why applies are slow

> Everything you apply today is "Dojo Cloud Policy": the same model as the big clouds' policy services.

<!-- Set expectations. Labs follow the same order as this list. ~1 min. -->

---

## The guardrail problem

- Anyone with access can create anything: wrong region, no owner tag, a 64-core container
- Reviews catch some of it, after the fact
- A wiki page says "use Canadian regions". Nothing enforces it
- Fixing it later means finding every offender by hand
- Rules in people's heads drift as people change

> A guardrail is a rule the platform checks for you, on every request, whoever makes it.

<!-- ~2 min. Ask: "who has seen a resource with no owner tag?" -->

---

## The model in four words

| Word | What it is | Example |
| --- | --- | --- |
| **Definition** | The rule itself: a condition and an effect | "tag `costCenter` must exist" |
| **Assignment** | Switches a definition on at a scope | the rule, on the subscription |
| **Scope** | Where it applies: subscription, resource group | everything under the subscription |
| **Effect** | What happens on a match | `deny`, `audit`, `modify` |

A definition on its own does nothing. **Nothing is enforced until it is assigned.**

<!-- ~2 min. Stress the definition/assignment split: write once, assign many times. -->

---

## Scope and inheritance

```text
subscription        <- assignment here covers everything below
  └─ resource group <- or assign narrower, for stricter rules
       └─ container group, network, ...
```

- An assignment applies to its scope **and everything beneath it**
- Narrower assignments add rules; they never remove a parent's
- Platform guardrails sit at the top: you can read them, not change them
- Built-ins here: Canadian regions, tags `owner` and `env`, two images, cpu and memory caps, port 80, 10 env vars

<!-- ~2 min. Show the Policy blade in the portal and open one built-in. -->

---

## Anatomy of a rule

```json
{
  "mode": "Indexed",
  "policyRule": {
    "if":   { "field": "location",
              "notIn": ["canadacentral", "canadaeast"] },
    "then": { "effect": "deny" }
  }
}
```

- **if**: the condition. When it is true, the resource is a match
- **then**: what the engine does about the match
- **mode**: `Indexed` skips resource groups, `All` includes them

<!-- ~2 min. Read it aloud: "if the location is not in the list, deny". -->

---

## Fields, aliases, combinators

```json
{ "allOf": [
    { "field": "type", "equals": "Microsoft.ContainerInstance/containerGroups" },
    { "anyOf": [
        { "field": "tags['costCenter']", "exists": "false" },
        { "field": "tags['costCenter']", "isBlank": "true" } ] } ] }
```

- Fields: `type`, `name`, `location`, `tags['x']`, plus **aliases** for resource properties
- Combine with `allOf`, `anyOf`, `not`
- A `[*]` alias (a list) must hold for **every** element
- Operators are in the cheat sheet; `inExact` and `isBlank` are Dojo extras

<!-- ~2 min. Walk the nesting from the outside in. -->

---

## Parameters: one rule, many uses

```json
"parameters": {
  "allowedImages": { "type": "Array" },
  "effect": { "type": "String", "defaultValue": "deny",
              "allowedValues": ["deny", "audit", "disabled"] }
},
"policyRule": {
  "if": { "field": "image", "notIn": "[parameters('allowedImages')]" },
  "then": { "effect": "[parameters('effect')]" }
}
```

- The **assignment** supplies the values
- Same definition: subscription allows `1.0` + `2.0`, one resource group allows only `2.0`

<!-- ~2 min. Parameters are why you write the rule once. -->

---

## Audit before deny

| Step | Effect | What happens to a bad resource |
| --- | --- | --- |
| 1 | `audit` | Created, but marked non-compliant |
| 2 | read compliance | You see exactly who would break |
| 3 | fix or exempt the offenders | The list shrinks to zero |
| 4 | `deny` | New bad requests are refused |

- Turning on `deny` blind breaks pipelines and people on day one
- With `effect` as a parameter, step 4 is a **one-line change**
- Assignment `enforce = false` (DoNotEnforce) is the dry run: evaluates, never blocks

<!-- ~2 min. This is the habit to take home. -->

---

## Compliance: reading the verdict

- Evaluated on every write, and on demand
- States: **Compliant**, **NonCompliant**, **Exempt**, **NotStarted**
- The Policy blade lists assignments, resources and the reason for each verdict
- `deny` refuses with `403 RequestDisallowedByPolicy`, naming the assignment, definition and message

```text
RequestDisallowedByPolicy: resource 'ci-sam-app' was disallowed by policy.
  assignment: require-costcenter   message: Add a costCenter tag.
```

> Write a clear `nonComplianceMessage`. It is the only help the engineer gets.

<!-- ~2 min. -->

---

## Policy sets: bundle the baseline

```hcl
resource "azurerm_policy_set_definition" "baseline" {
  name = "team-baseline"
  policy_definition_reference {
    policy_definition_id = azurerm_policy_definition.costcenter.id
    reference_id         = "costcenter"
  }
  # ... images, locations
}
```

- One **assignment** of the set covers every member; compliance is shown per member
- Add a member rule and it applies **without a new assignment**
- A definition still used by an assignment or set cannot be deleted (`PolicyDefinitionInUse`)

<!-- ~2 min. -->

---

## Modify: fix it instead of refusing it

```json
"then": {
  "effect": "modify",
  "details": {
    "roleDefinitionIds": ["00000000-0000-0000-0000-000000000000"],
    "operations": [{ "operation": "addOrReplace",
                     "field": "tags['managedBy']", "value": "policy" }]
  }
}
```

- Runs on **new** writes, adding or removing tags for you
- Needs an assignment **identity** (`identity { type = "SystemAssigned" }`) and a `location`
- The role GUID is required but not checked in Dojo Cloud

<!-- ~2 min. -->

---

## Remediation and the tofu fight

- `modify` does **not** touch resources that already exist
- A **remediation task** applies it to them: `azurerm_resource_group_policy_remediation`
- Policy changes a tag, then OpenTofu sees drift from your code and changes it back
- Fix: tell tofu to ignore what policy owns

```hcl
lifecycle {
  ignore_changes = [tags["managedBy"]]
}
```

<!-- ~2 min. Real-world gotcha: two controllers fighting over one field. -->

---

## Exemptions are a process, not a hole

- Sometimes a rule must not apply: a legacy resource group, a migration
- An **exemption** is a scoped, named exception to one assignment
- Categories: **Waiver** (accepted risk) and **Mitigated** (handled elsewhere)
- Always set `expires_on` and a `description` with the reason
- Raise it as a **pull request**, so the waiver is reviewed and visible in git
- Expired exemptions stop applying: the resource is checked again

<!-- ~2 min. An exemption in git has an owner and an end date. -->

---

## Shift left: catch it before the cloud does

- Cloud policy answers at **apply** time: late, slow, after the PR merged
- Rego checks the **plan JSON** in the pull request, in seconds
- The same rule, in two places: Rego for fast feedback, cloud policy as the backstop

```bash
tofu plan -out=plan.out
tofu show -json plan.out > plan.json
conftest test --policy policy/rego plan.json
```

<!-- ~2 min. Shift left = earlier in the pipeline. -->

---

## The same rule in Rego

```rego
package main

deny contains msg if {
  some rc in input.resource_changes
  rc.type == "azurerm_container_group"
  not rc.change.after.tags.costCenter
  msg := sprintf("%s: missing costCenter tag", [rc.address])
}
```

- `deny contains msg if` builds a set of messages; empty set = pass
- Every line in the body must be true for the rule to fire
- `conftest` fails the build when `deny` is not empty

<!-- ~2 min. Compare line by line with the JSON rule. -->

---

## Testing policies

```rego
package main

test_missing_tag_denied if {
  count(deny) == 1 with input as {"resource_changes": [{
    "address": "x", "type": "azurerm_container_group",
    "change": {"after": {"tags": {}}}}]}
}
```

```bash
opa test policy/rego --ignore fixtures -v
```

- Cover the pass **and** the fail case. A rule with no tests is a guess
- Write the test first: it fails, then you fix the rule

<!-- ~2 min. Tests catch the planted bug in lab 10. -->

---

## The pipeline

| Event | Workflow | Does |
| --- | --- | --- |
| Pull request | `pr.yml` | plan, `conftest`, `opa test`: must be green to merge |
| Merge to `main` | `main.yml` | apply `policy/cloud`, then `infra` |
| Schedule or manual | `drift.yml` | compare reality with git, fail on **DRIFT** |

- Nobody applies policy from a laptop: **git is the change record**
- A broken rule fails on the PR, long before it reaches the cloud

<!-- ~2 min. Policy applies first so new guardrails are in place before infra. -->

---

## Drift: when the cloud stops matching git

- Someone sets an assignment to DoNotEnforce in the portal "just for a minute"
- Or deletes it. The guardrail is gone, and nothing in git says so
- `drift.yml` plans against reality and fails loudly when they differ
- The fix is the pipeline: re-run `main.yml`, **git wins**

> Policy that can be changed by hand is a suggestion. Detect drift and put it back.

<!-- ~2 min. Lab 12 does exactly this. -->

---

## Why policy applies are slow

- Creating a definition or assignment takes **about 100 s**; destroying an assignment too
- The provider waits for the cloud's **eventual consistency**: the control plane has accepted the rule, but every region's evaluator has not yet caught up
- The waits run in parallel: one apply with several policies is about **3.5 min**
- Sets, exemptions and remediations are instant
- Never chain assignments with `depends_on`: it turns parallel waits into serial ones

> Plan the apply, start it, and read the next section while you wait.

<!-- ~2 min. Tell them up front so nobody cancels a "stuck" apply. -->

---

## Recap

- A **definition** is a rule; an **assignment** at a **scope** turns it on
- Roll out with **audit**, read **compliance**, then **deny**
- **Parameters** and **sets** make rules reusable; **modify** plus **remediation** fixes instead of refusing
- **Exemptions** are reviewed, expiring exceptions
- Rego on the plan JSON shifts the check **left**, and `opa test` keeps it honest
- The pipeline applies policy; **drift** detection keeps git in charge

<!-- ~1 min. -->

---

## The lab map

| Labs | You will |
| --- | --- |
| 0-2 | Set up, meet a denial, read a rule |
| 3-4 | First policy as code, audit and compliance |
| 5-6 | Parameters, DoNotEnforce, policy sets |
| 7-8 | Modify, remediation, exemptions |
| 9-10 | Rego on the plan, testing policies |
| 11-12 | The PR pipeline, drift |
| Capstone | One new rule end to end |

Applies take ~3.5 min. Start them, then read on.

<!-- ~1 min. Send them to ~/lab/README.md. -->
