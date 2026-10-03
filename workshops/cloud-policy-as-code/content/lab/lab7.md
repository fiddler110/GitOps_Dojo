# Lab 7: Modify and remediation, policy that fixes things

**Time:** about 30 minutes (one slow apply of about 3.5 minutes). **Goal:** write a policy that does not refuse a resource but *changes* it, understand why that needs an identity, make OpenTofu coexist with it, and bring resources that already exist into line with remediation.

> **Starting here?** This lab needs your clone, the app applied, and the policy from Labs 3-6 (the `team-baseline` set assigned). Run `lab-prep 7` to set that up. It is safe to run even if you did the earlier labs, and the policy apply it performs takes about 3.5 minutes.

```bash
cd ~/lab/cloud-policy-as-code
```

---

## Why modify exists

So far every effect has said no: `deny` refuses, `audit` complains. Both push work back onto the person who wrote the resource. Some rules are not decisions, they are housekeeping: "every resource carries `managedBy = policy`", "every storage account has HTTPS only". Asking each developer to remember them is how the rules get forgotten.

The `modify` effect makes the cloud *write the field itself*. A resource arrives without the tag, the cloud adds it, and the developer never knew there was a rule. That is convenient, and it creates three things you must understand:

1. **It needs an identity.** A `deny` only reads the request. A `modify` has to *write* to a resource, sometimes long after the original request (see remediation below), and there is nobody signed in at that moment. So the assignment gets a **managed identity**, and the definition names the **role** that identity needs (`roleDefinitionIds`). In a real cloud you must grant that role; a policy that modifies things with no permission fails silently. Dojo Cloud asks for the same shape, but does not check the role GUID, so any valid one works. The identity also lives in a **location**, which is why the assignment below has a `location` argument that no other assignment needs.
2. **It does not touch existing resources.** Policy runs when a resource is written. A resource created last week was never written *by the policy*, so it stays as it is, and shows up as non-compliant until you **remediate** it.
3. **It fights OpenTofu.** OpenTofu thinks it owns every tag in your config. The cloud adds one that is not in your config. Next plan, OpenTofu wants to remove it, and the next write, the policy adds it again. You will watch this happen in step 4.

## 1. Read the rule

The rule is already in the repo:

```bash
cat policy/cloud/rules/add-managedby-tag.json
```

```json
{
  "if": {
    "field": "tags['managedBy']",
    "exists": false
  },
  "then": {
    "effect": "modify",
    "details": {
      "roleDefinitionIds": [
        "/providers/Microsoft.Authorization/roleDefinitions/b24988ac-6180-42a0-ab88-20f7382dd24c"
      ],
      "operations": [
        { "operation": "addOrReplace", "field": "tags['managedBy']", "value": "policy" }
      ]
    }
  }
}
```

Read it as a sentence: *if the resource has no `managedBy` tag, modify it: add or replace the `managedBy` tag with the value `policy`*. The `operations` list is the "then" part; `addOrReplace` also overwrites a wrong value, whereas `add` leaves an existing one alone.

The definition uses `mode = "Indexed"`. Indexed mode only looks at resources that have a location and tags and skips resource groups, which is what you want for a tag that belongs on workloads. So the resource group will not be tagged, but container groups will.

## 2. Enable the definition and the assignment

Open `policy/cloud/main.tf` and find the block headed `# Lab 7: modify and remediation`. Uncomment the **definition** and the **assignment**, but leave the `azurerm_resource_group_policy_remediation` block commented out for now. You will add it in step 6, because the order matters.

> Tip: in VS Code, select the lines and press `Ctrl+/` to toggle comments.

```bash
cd policy/cloud
tofu fmt
tofu validate
```

```text
Success! The configuration is valid.
```

Look at the assignment you just enabled:

```hcl
resource "azurerm_subscription_policy_assignment" "add_managedby_tag" {
  name                 = "add-managedby-tag"
  subscription_id      = data.azurerm_subscription.current.id
  policy_definition_id = azurerm_policy_definition.add_managedby_tag.id
  location             = "canadacentral"

  identity {
    type = "SystemAssigned"
  }
}
```

`identity { type = "SystemAssigned" }` is the managed identity: the cloud creates it and ties its lifetime to the assignment. Remove the `identity` block and try `tofu validate`; it still passes, because the provider cannot know the rule says `modify`. The cloud refuses at apply instead. (Put it back if you tried this.)

## 3. Apply, and read while it runs

```bash
tofu apply
```

Review the plan (2 to add: the definition and the assignment), type `yes`.

> **This apply is slow, about 100 seconds for the definition and the assignment, in parallel.** That is not Dojo Cloud being sluggish: the provider creates the object and then *waits until a read returns it*, because real clouds are eventually consistent and a policy that is not yet visible would make the next step fail randomly. Use the time: reread the paragraph "Why modify exists" above, then open the portal's **Policy** blade and look at the `team-baseline` row to see how the other assignments show up.

```text
azurerm_policy_definition.add_managedby_tag: Creation complete after 1m40s
azurerm_subscription_policy_assignment.add_managedby_tag: Creation complete after 1m41s
Apply complete! Resources: 2 added, 0 changed, 0 destroyed.
```

Open the portal's **Policy** blade. `add-managedby-tag` is listed with effect `modify`. Look at its **Non-compliant** column: your existing `ci-<you>-app` container group has no `managedBy` tag, so it is non-compliant. Nothing has changed it, because nothing wrote to it since the policy arrived. This is point 2 above, made visible.

## 4. A new resource is modified at once

You are allowed two container groups. Add a second one to `infra/main.tf`, below the first:

```hcl
resource "azurerm_container_group" "second" {
  name                = "ci-${var.owner}-second"
  location            = azurerm_resource_group.app.location
  resource_group_name = azurerm_resource_group.app.name
  os_type             = "Linux"
  ip_address_type     = "Public"
  dns_name_label      = "${var.owner}-second"

  exposed_port {
    port     = 80
    protocol = "TCP"
  }

  container {
    name   = "hello"
    image  = "dojo/hello:2.0"
    cpu    = 0.25
    memory = 0.125

    ports {
      port     = 80
      protocol = "TCP"
    }
  }

  tags = local.tags
}
```

Notice that `tags = local.tags` contains no `managedBy`. Apply it:

```bash
cd ~/lab/cloud-policy-as-code/infra
tofu apply
```

```text
azurerm_container_group.second: Creation complete after 20s
Apply complete! Resources: 1 added, 0 changed, 0 destroyed.
```

No refusal, no warning: the request was accepted and the cloud quietly changed it on the way in. Now ask OpenTofu what it thinks:

```bash
tofu plan
```

```text
  # azurerm_container_group.second will be updated in-place
  ~ resource "azurerm_container_group" "second" {
      ~ tags = {
          - "managedBy" = "policy" -> null
            # (3 unchanged elements hidden)
        }
    }

Plan: 0 to add, 1 to change, 0 to destroy.
```

**This is the fight.** The code says "these three tags", reality has four. OpenTofu plans to remove `managedBy`. If you applied, the cloud would run the policy again on that write and put it back, and the next plan would show the same diff, forever. A pipeline that applies on every merge would also "change" the resource on every run, hiding real changes in noise.

## 5. Tell OpenTofu the tag is not its business

The tag is owned by policy, so tell OpenTofu to ignore it. Add a `lifecycle` block to **both** container groups (the `second` one now, and `app`, which will be remediated in the next step):

```hcl
  tags = local.tags

  # The modify policy adds managedBy outside this config; do not fight it.
  lifecycle {
    ignore_changes = [tags["managedBy"]]
  }
```

```bash
tofu fmt
tofu plan
```

```text
No changes. Your infrastructure matches the configuration.
```

`ignore_changes = [tags["managedBy"]]` is narrow on purpose. It ignores one tag key, not all of `tags`, so if someone removes `costCenter` from the config, OpenTofu still notices. Ignoring a whole attribute because one key in it is noisy is how real drift gets hidden. Rule of thumb: **whichever system owns a field, the other one must be told to leave it alone.**

## 6. Remediate what already exists

`ci-<you>-app` still has no `managedBy` tag. A **remediation** is a one-off task that runs a `modify` policy over resources that already exist. Back in `policy/cloud/main.tf`, uncomment the last block of Lab 7:

```hcl
resource "azurerm_resource_group_policy_remediation" "managedby" {
  name                 = "managedby"
  resource_group_id    = data.azurerm_resource_group.infra.id
  policy_assignment_id = azurerm_subscription_policy_assignment.add_managedby_tag.id
}
```

It names a scope (your app resource group) and an assignment, and says "apply this assignment's modify to everything in that scope". It uses the assignment's identity, which is why that identity exists.

```bash
cd ~/lab/cloud-policy-as-code/policy/cloud
tofu apply
```

```text
azurerm_resource_group_policy_remediation.managedby: Creation complete after 1s
Apply complete! Resources: 1 added, 0 changed, 0 destroyed.
```

Remediations are instant. Go to the portal's **Policy** blade and press **Evaluate now** on the assignment row: **Non-compliant** for `add-managedby-tag` drops to 0. Open `ci-<you>-app` in the portal's resource view and check its tags: `managedBy = policy` is there now. Then, in `infra/`, run `tofu plan` once more; thanks to step 5 it still says no changes.

## 7. Tidy up the experiment

You only needed the second group to see the policy act on a new resource. Delete the whole `azurerm_container_group.second` block from `infra/main.tf` (keep the `lifecycle` on `app`), and:

```bash
cd ~/lab/cloud-policy-as-code/infra
tofu apply
```

```text
Apply complete! Resources: 0 added, 0 changed, 1 destroyed.
```

## What just happened

- You wrote a **modify** policy: the cloud completes a resource instead of refusing it.
- Modify needs a **managed identity** and a role (`roleDefinitionIds`) because it writes to resources, possibly later and with nobody signed in. Dojo Cloud asks for the same shape as the real thing but does not verify the role.
- A new resource is modified when it is written. An existing one is not. **Remediation** brings the existing ones into line.
- Two systems that both write the same field fight. `ignore_changes` on exactly the tag the policy owns ends it.

## Check yourself

1. Why does a modify assignment need an identity, when deny does not? *(it writes to resources, possibly later by remediation, so it needs permission of its own; deny only reads the request)*
2. After you assigned the policy, was `ci-<you>-app` tagged? *(no: policy acts on writes; it needed a remediation)*
3. Why `ignore_changes = [tags["managedBy"]]` and not `ignore_changes = [tags]`? *(ignoring one key keeps OpenTofu watching every other tag)*

**Check box.** You are done when all of these hold:

- [ ] `tofu plan` in `infra/` and in `policy/cloud/` both say no changes.
- [ ] The Policy blade shows `add-managedby-tag` with effect `modify` and 0 non-compliant.
- [ ] `ci-<you>-app` has the tag `managedBy = policy`.
- [ ] Only one container group (`ci-<you>-app`) is left, with `ignore_changes` on `managedBy`.

## Recap

Policy can do more than refuse: `modify` fixes resources as they are written, using an identity of its own. It never touches what was already there until you remediate. And because it writes outside your code, tell OpenTofu which field belongs to whom. **Next:** [lab8.md](lab8.md): what to do when a rule is right but one resource genuinely cannot meet it yet.
