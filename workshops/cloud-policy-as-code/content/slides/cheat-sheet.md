---
marp: true
theme: default
paginate: true
size: 16:9
html: true
style: |
    @import url('assets/themes/cheat-sheet.css');
footer: "[&larr; Hub](index.md) &nbsp;|&nbsp; Cloud Policy as Code | Cheat Sheet"
---

<!-- _class: lead -->
<!-- _paginate: false -->
<!-- _footer: "[&larr; Hub](index.md)" -->

# Cheat Sheet

## Cloud Policy as Code: everything from Labs 0-12

Keep this open in a split pane while you work. You don't need to memorize any of it.

---

## The definition JSON

```json
{ "mode": "Indexed",
  "parameters": { "effect": { "type": "String", "defaultValue": "deny" } },
  "policyRule": {
    "if":   { "field": "location", "notIn": ["canadacentral", "canadaeast"] },
    "then": { "effect": "[parameters('effect')]" } } }
```

| Field | Meaning |
| --- | --- |
| `mode` | `Indexed` skips resource groups; `All` includes them |
| `parameters` | Values the assignment fills in; `type`, `defaultValue`, `allowedValues` |
| `policyRule.if` | The condition (`field` + operator, or `allOf`/`anyOf`/`not`) |
| `policyRule.then` | `effect`, plus `details` for modify |

---

## Operators

| Operator | True when |
| --- | --- |
| `equals` / `notEquals` | Exact match (case-insensitive) |
| `in` / `notIn` | Value is in / not in a list |
| `inExact` | Like `in`, but case-sensitive (Dojo extra) |
| `like` / `notLike` | Wildcard `*` match |
| `contains` / `notContains` | Substring match |
| `exists` | Field present (`"true"`) or absent (`"false"`) |
| `isBlank` | Field missing or empty (Dojo extra) |
| `less` `lessOrEquals` `greater` `greaterOrEquals` | Number comparison |
| `[*]` alias | Condition must hold for every list element |

Fields: `type`, `name`, `location`, `tags`, `tags['x']`, aliases. Dojo alias extra: `environmentVariableCount`.
Parameters: `"[parameters('x')]"`.

---

## Effects

| Effect | What it does |
| --- | --- |
| `deny` | Refuses the write with `403 RequestDisallowedByPolicy` |
| `audit` | Allows it, marks it NonCompliant |
| `modify` | Adds, replaces or removes tags (`addOrReplace`, `add`, `remove`); needs identity and `details.roleDefinitionIds` |
| `append` | Adds fields to the request |
| `disabled` | Rule stays defined but does nothing |

Assignment `enforce = false` (DoNotEnforce): evaluate and report, never block.

Compliance states: **Compliant**, **NonCompliant**, **Exempt**, **NotStarted**.

---

## The azurerm resources

| Resource | Use |
| --- | --- |
| `azurerm_policy_definition` | The rule (JSON from `file()`) |
| `azurerm_policy_set_definition` | A bundle of definitions with set parameters |
| `azurerm_subscription_policy_assignment` | Turn a definition or set on at subscription scope |
| `azurerm_resource_group_policy_assignment` | The same, narrower |
| `azurerm_resource_group_policy_exemption` | A reviewed, expiring exception |
| `azurerm_resource_group_policy_remediation` | Apply modify to existing resources |
| `data "azurerm_subscription" "current"` | The subscription scope id |

Assignment with modify: add `identity { type = "SystemAssigned" }` and `location`.

---

## Rego basics

```rego
package main

deny contains msg if {
  some rc in input.resource_changes
  rc.type == "azurerm_container_group"
  not rc.change.after.tags.costCenter
  msg := sprintf("%s: missing costCenter", [rc.address])
}
```

| Idea | Note |
| --- | --- |
| Body | Every line must be true (AND); a new rule of the same name is OR |
| `not x` | True when `x` is undefined or false |
| `some x in list` | Iterate |
| `:=` / `==` | Assign / compare |
| `deny contains msg` | A set of failure messages; empty = pass |

---

## conftest and opa

```bash
tofu plan -out=plan.out
tofu show -json plan.out > plan.json
conftest test --policy policy/rego plan.json
opa test policy/rego --ignore fixtures -v
opa eval -d policy/rego -i plan.json 'data.main.deny'
opa fmt -w policy/rego
```

- Always pass `--ignore fixtures`: a plain `opa test policy/rego` hits a merge error
- Test names start with `test_`; use `with input as {...}`
- `conftest` exit code is non-zero when `deny` is not empty

---

## Common errors and fixes

| Error | Cause | Fix |
| --- | --- | --- |
| `RequestDisallowedByPolicy` (403) | A `deny` rule matched | Read the assignment and message; fix the resource, or raise an exemption PR |
| `PolicyDefinitionInUse` (400) | An assignment or set still uses the definition | Delete the assignment (or remove it from the set) first |
| Apply "stuck" for ~100 s | Eventual consistency in the provider | Wait: about 3.5 min total; don't cancel |
| Tofu keeps changing a tag back | `modify` and your code both own it | `lifecycle { ignore_changes = [tags["x"]] }` |
| `opa test` merge error | Fixtures loaded as policy | `opa test policy/rego --ignore fixtures -v` |
| `drift.yml` fails "DRIFT" | Cloud differs from git | Re-run `main.yml`; git wins |
