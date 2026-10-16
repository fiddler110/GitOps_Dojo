# Lab 9: Shift left with Rego, check the plan before the cloud does

**Time:** about 25 minutes. **Goal:** turn a policy into code that checks an OpenTofu *plan*, run it with `conftest`, and compare what it says with what the cloud says.

> **Starting here?** This lab needs your clone, the app applied, and the policy from Labs 3-8. Run `dojo prep 9` to set that up (the policy apply takes about 3.5 minutes). It is safe to run even if you did the earlier labs.

```sh
cd ~/lab/cloud-policy-as-code
```

---

## Why check before the cloud does

The cloud's policy is the last line of defence and the only one that cannot be bypassed. It is also **late**: you only meet it at `tofu apply`, usually in a pipeline, after a reviewer has already approved the change. The failure is a 403 in the middle of an apply, sometimes with half the resources already created.

`tofu plan` already knows everything the cloud will see: every resource and every value. If the same rule runs over the plan, the developer finds out in seconds, locally, or on the pull request, before anyone reviews or applies. That is **shifting left**. The cloud rule stays as the backstop; the plan check is the fast feedback.

The tool is **Open Policy Agent** (OPA), and its language is **Rego**. `conftest` is the small command that runs Rego against configuration files such as a plan.

## 1. Look at what a plan really contains

`tofu plan -out=plan.out` saves a plan to a file, and `tofu show -json` turns it into JSON that other tools can read. (`plan.out` and `plan.json` are in `.gitignore`: a plan can contain secrets, so never commit one.)

```text
tofu plan -out=<file>
tofu show -json <file> > <json file>
```

The plan is a JSON document. The part the policy cares about is `resource_changes`, a list with one entry per resource:

```text
{
    "format_version": "1.2",
    ...
    "resource_changes": [
        {
            "address": "azurerm_resource_group.app",
            "type": "azurerm_resource_group",
            "name": "app",
            "change": {
                "actions": ["no-op"],
                "before": { ... },
                "after": { "name": "rg-sam-app", "location": "canadacentral", "tags": { ... } }
            }
        }
    ]
}
```

Three things to remember: `address` names the resource, `change.actions` says what will happen (`create`, `update`, `delete`, `no-op`), and `change.after` is the resource *as it will be* once applied. Rego will walk this structure.

**Your turn:** predict: which `actions` will the app's existing resources show, since nothing has changed?

```sh
cd infra
tofu plan -out=plan.out
tofu show -json plan.out > plan.json
python3 -m json.tool plan.json | head -50
```

<!-- dojo-reveal: What the plan JSON shows -->

- `resource_changes` has an entry per resource, and unchanged ones show `"actions": ["no-op"]`.

<!-- /dojo-reveal -->

## 2. Read your first Rego rule

The rule lives in `policy/rego/costcenter.rego`. Open it in your editor, or print it, after reading it here:

```rego
package main

import rego.v1

# Lab 9: refuse any created or updated resource without a costCenter tag. Resources with no tags
# attribute at all (policy objects, for example) are not tagged things, so they are skipped.
deny contains msg if {
	some rc in input.resource_changes
	some action in rc.change.actions
	action in {"create", "update"}
	tags := rc.change.after.tags
	not tags.costCenter
	msg := sprintf("%s is missing the costCenter tag", [rc.address])
}
```

Rego is not like the languages you know. It is a **query language**: a rule is a list of conditions, and it holds when *every line is true for some choice of the variables*. Take it a line at a time:

| Line | Meaning |
|---|---|
| `package main` | The namespace. `conftest` looks in `main` by default, and the workflows pass `--namespace main` |
| `import rego.v1` | Opts in to the modern syntax (`if`, `contains`, `in`). It is already the default in OPA 1.x and harmless to keep, so you will see it in code written for older versions |
| `deny contains msg if { ... }` | A **set** called `deny`. For every way the body can be true, one `msg` is added to the set. `conftest` fails if `deny` is not empty |
| `input` | The document being checked: here, the plan JSON |
| `some rc in input.resource_changes` | Pick **each** resource change in turn. The rest of the body runs once per choice |
| `some action in rc.change.actions` / `action in {"create", "update"}` | Keep only changes that create or update. A delete or a no-op never fails the rule |
| `tags := rc.change.after.tags` | If the resource has no `tags` attribute, this line is undefined, the body stops, and nothing is denied. That is how policy objects, which have no tags, are skipped |
| `not tags.costCenter` | True when there is no `costCenter` key (or it is empty or `false`) |
| `msg := sprintf(...)` | Builds the text added to `deny` |

Two properties are worth saying out loud. A line that is **undefined** (a missing field) makes the whole body fail quietly rather than raise an error, which is why `not` is how you test for absence. And rules are **declarative**: you describe a violation, you do not write a loop. `some rc in ...` is the loop, and Rego runs the body for every one.

**Your turn:** print the file and match each line to the table.

```sh
cd ..
cat policy/rego/costcenter.rego
```

## 3. Give it something to refuse

`conftest test` runs the Rego rules against the plan JSON. The plan itself will succeed, because OpenTofu does not know your policy; `conftest` does.

```text
conftest test --policy <dir> --namespace main <plan.json>
```

Add a resource group with no `costCenter` tag. Open `infra/main.tf` in your editor and append:

```hcl
resource "azurerm_resource_group" "scratch" {
  name     = "rg-${var.owner}-scratch"
  location = var.location
  tags = {
    owner = var.owner
    env   = "dev"
  }
}
```

**Prefer the terminal?**

```sh
cat >> infra/main.tf <<'EOT'

resource "azurerm_resource_group" "scratch" {
  name     = "rg-${var.owner}-scratch"
  location = var.location
  tags = {
    owner = var.owner
    env   = "dev"
  }
}
EOT
```

**Your turn:** plan it, turn it into JSON, and check it. Before you run it, predict: how many tests will fail, and which resource will be named? Will `azurerm_resource_group.app` appear?

```sh
cd infra
tofu plan -out=plan.out
tofu show -json plan.out > plan.json
cd ..
conftest test --policy policy/rego --namespace main infra/plan.json
```

<!-- dojo-reveal: Results of conftest -->

```text
FAIL - infra/plan.json - main - azurerm_resource_group.scratch is missing the costCenter tag

2 tests, 1 passed, 0 warnings, 1 failure
```

The plan itself succeeded: OpenTofu does not know your policy. `conftest` did, and its message names the **resource address** so you know where to look. The "2 tests" are the two `deny` rules in the folder (`costcenter.rego` and `regions.rego`); one passed (the region is fine) and one failed.

Note what did not fail: `azurerm_resource_group.app` is `no-op`, so the `create`/`update` filter skipped it. The check looks at **what is about to change**, not at everything.

<!-- /dojo-reveal -->

## 4. Now ask the cloud

The cloud rule is the backstop. Apply the same plan and see what the platform says. (Answer `yes` when asked; it fails.)

**Your turn:** predict: will the cloud agree with `conftest`? What will its message name?

```sh
cd infra
tofu apply
```

<!-- dojo-reveal: Results of tofu apply -->

```text
Error: creating "Resource Group (Subscription: \"<your subscription id>\"\nResource Group Name: \"rg-sam-scratch\")": unexpected status 403 (403 Forbidden) with error:
RequestDisallowedByPolicy: Resource 'rg-sam-scratch' was disallowed by policy.
Policy: 'Require a costCenter tag'. Assignment 'team-baseline', definition 'Require a costCenter tag':
tag 'costCenter' does not exist.
```

Compare the two refusals:

| | `conftest` on the plan | the cloud |
|---|---|---|
| When | seconds after `tofu plan`, no credentials needed for the check | in the middle of `tofu apply` |
| Where | your terminal or the pull request | the apply log |
| What it names | the resource address in your code | the assignment and definition on the platform side |
| Can it be skipped? | yes, if someone does not run it | no |

They are two copies of **the same rule**, written in two languages, which is the cost of shifting left: you now have two things to keep in step. Lab 10 is about how to be sure they stay right.

<!-- /dojo-reveal -->

## 5. Fix it and clean up

In your editor, add the missing tag to the scratch group in `infra/main.tf`:

```hcl
  tags = {
    owner      = var.owner
    env        = "dev"
    costCenter = "cc-1001"
  }
```

**Your turn:** run the check again. Predict the summary line.

```sh
cd infra
tofu plan -out=plan.out
tofu show -json plan.out > plan.json
cd ..
conftest test --policy policy/rego --namespace main infra/plan.json
```

<!-- dojo-reveal: Results of conftest -->

```text
2 tests, 2 passed, 0 warnings, 0 failures
```

<!-- /dojo-reveal -->

You do not need the scratch group. Delete the whole `azurerm_resource_group.scratch` block from `infra/main.tf`, then check `git status`: only the files you meant to change should show (and none should be `plan.out` or `plan.json`), and the plan should be clean.

```sh
git status --short
cd infra
tofu plan
```

<!-- dojo-reveal: Results of tofu plan -->

```text
No changes. Your infrastructure matches the configuration.
```

<!-- /dojo-reveal -->

## What just happened

- A plan is data. `tofu show -json` turns it into a JSON document with a `resource_changes` list.
- A Rego rule describes a **violation** as a set of conditions over that data. `deny contains msg if { ... }` adds a message each time the body is true; `conftest` fails when the set is not empty.
- The same rule now runs in two places: over the plan (fast, skippable) and in the cloud (late, unavoidable). Neither replaces the other.

## Check yourself

1. Why does a missing field not crash a Rego rule?
2. Why did `azurerm_resource_group.app` not appear in the failure, even though the rule covers resource groups?
3. What is the advantage of `conftest` over waiting for the cloud's 403?

<!-- dojo-reveal: Show the answers -->

1. An undefined expression makes the body fail quietly; so `not` is the way to test absence.
2. Its action was `no-op`; the rule only looks at create and update.
3. Earlier feedback, no apply needed, and it can run on every pull request.

<!-- /dojo-reveal -->

**Check box.** You are done when all of these hold:

- [ ] You saw `conftest` fail on the scratch group with the costCenter message, and pass once the tag was added.
- [ ] You saw the cloud's 403 for the same resource.
- [ ] The scratch group is gone from `infra/main.tf` and `tofu plan` reports no changes.

## Recap

Rego lets the same rule run on the plan, before anything is applied. A rule is a list of conditions; `deny contains msg if` collects violations; `conftest` runs it. **Next:** [lab10.md](lab10.md): a rule you cannot test is a rule you cannot trust, so you will test one, and find a bug.
