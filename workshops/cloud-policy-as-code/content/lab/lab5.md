# Lab 5: Parameters and reuse

**Time:** about 15 minutes, of which about 5 are waiting (two policy applies). **Goal:** write **one** "allowed images" definition and assign it **twice** with different parameter values at different scopes; use `enforce = false` (DoNotEnforce) to see what a rule *would* block before it blocks anything; then enforce it.

> **Starting here?** This lab starts from the end of Lab 4 (costCenter rule on audit, the legacy group created). Run `dojo prep 5` to set that up; it applies the earlier labs' work and takes about 3.5 minutes.

## Read this first: two slow applies

This lab has two policy applies. The first creates a definition and two assignments: about **3.5 minutes**, because the definition takes about 100 seconds, then both assignments (created in parallel) take another 100 seconds. The wait is the provider confirming that the cloud's policy service has replicated each object (eventual consistency). The second apply only changes one assignment and takes about 2 minutes. Each has a "while it runs" section.

## The scenario

Platform rules already limit images to `dojo/hello:1.0` and `dojo/hello:2.0`. Your team wants to go further: the app group should run **only 2.0**, because 1.0 has a known bug. But the rest of the subscription may still use 1.0 while other teams migrate. That is one rule with two strictnesses.

## 1. Read the definition

The rule file `rules/allowed-images.json` looks like this:

```json
{
  "if": {
    "allOf": [
      { "field": "type", "equals": "Microsoft.ContainerInstance/containerGroups" },
      { "not": { "field": "Microsoft.ContainerInstance/containerGroups/containers[*].image", "in": "[parameters('allowedImages')]" } }
    ]
  },
  "then": {
    "effect": "[parameters('effect')]"
  }
}
```

Read it as: *if the resource is a container group, and it is not true that its images are in the allowed list, then apply the effect.* Three things to notice:

- `allOf` with a **type check** first. This rule is only about container groups. Without the `type` line it would try to read an image from every resource group.
- `containers[*].image` is a `[*]` field. The condition must hold for **every** container: one image outside the list makes the group non-compliant.
- `[parameters('allowedImages')]` is an **Array parameter** with no default. The rule itself contains no image names at all. Whoever assigns it must say which are allowed.

**Your turn:** open `rules/allowed-images.json` in your editor, or print it. Predict first: does the file contain any image names?

```sh
cd ~/lab/cloud-policy-as-code/policy/cloud
cat rules/allowed-images.json
```

<!-- dojo-reveal: What the file shows -->

- No image names at all: only the `[parameters('allowedImages')]` placeholder.

<!-- /dojo-reveal -->

## 2. Enable the Lab 5 block

The block you will enable in `policy/cloud/main.tf` has three resources. First the definition:

```hcl
resource "azurerm_policy_definition" "allowed_images" {
  name         = "allowed-images"
  policy_type  = "Custom"
  mode         = "Indexed"
  display_name = "Allowed container images"

  policy_rule = file("${path.module}/rules/allowed-images.json")

  parameters = jsonencode({
    allowedImages = {
      type = "Array"
    }
    effect = {
      type         = "String"
      defaultValue = "deny"
    }
  })
}
```

`mode = "Indexed"` this time: the rule is about a container group, never a resource group, so there is nothing for `All` to add. Two parameters: the Array with no default (required), and `effect` defaulting to `deny`.

Then the two assignments, **of the same definition**:

```hcl
resource "azurerm_subscription_policy_assignment" "images_subscription" {
  name                 = "images-subscription"
  subscription_id      = data.azurerm_subscription.current.id
  policy_definition_id = azurerm_policy_definition.allowed_images.id
  parameters = jsonencode({
    allowedImages = { value = ["dojo/hello:1.0", "dojo/hello:2.0"] }
  })
}

resource "azurerm_resource_group_policy_assignment" "images_strict" {
  name                 = "images-strict"
  resource_group_id    = data.azurerm_resource_group.infra.id
  policy_definition_id = azurerm_policy_definition.allowed_images.id
  parameters = jsonencode({
    allowedImages = { value = ["dojo/hello:2.0"] }
  })
  enforce = false
}
```

- **`images_subscription`:** the whole subscription, both images allowed.
- **`images_strict`:** only on `rg-<you>-app` (the `data` block looks it up by name), only 2.0 allowed. The resource type changed too: `..._resource_group_policy_assignment` takes `resource_group_id` where the subscription one takes `subscription_id`. Same definition, a different scope.
- **`enforce = false`:** the new idea. See below.

**Your turn:** in `policy/cloud/main.tf`, the section from `# Lab 5:` to `# Lab 6:` is commented out. Uncomment it in VS Code.

**Prefer the terminal?**

```sh
sed -i '/^# Lab 5:/,/^# Lab 6:/{/^# Lab [56]:/!s/^# \{0,1\}//}' main.tf
tofu fmt
```

## 3. Apply

`tofu plan` previews the changes and `tofu apply` creates them. Read the "while it runs" section below while the apply works.

**Your turn:** before you plan, predict how many resources will be added.

```sh
tofu plan
```

<!-- dojo-reveal: Results of tofu plan -->

```text
Plan: 3 to add, 0 to change, 0 to destroy.
```

One definition and two assignments.

<!-- /dojo-reveal -->

Apply it, type `yes`, and read while it runs.

```sh
tofu apply
```

## While it runs: reading

**What is `enforce = false`?** Every assignment has an **enforcement mode**. The default is `Default` (enforced). The other is **DoNotEnforce**, written `enforce = false` in HCL. In DoNotEnforce the cloud still **evaluates** the rule against every write and every existing resource, and records the result in compliance as NonCompliant, but it never refuses a write. It is a dry run that you can leave switched on.

How is that different from the `audit` you used in Lab 4?

| | `audit` (an effect) | DoNotEnforce (enforcement mode) |
| - | ------------------- | ------------------------------- |
| Set on | the definition's `then`, usually through the effect parameter | the assignment |
| Means | "this rule only ever observes" | "this rule denies, but is switched off for now" |
| Keeps the rule's real effect visible | no | yes. Compliance says what *deny* would do. |
| Switching on | change the effect | remove one line, no rule or parameter edited |

They overlap, and teams use either. Rule of thumb: use the effect parameter when a rule is *meant* to be advisory for good, and DoNotEnforce when a rule is meant to be enforced soon and you are only staging it.

**Why one definition and two assignments?** Compare the alternative: copy `allowed-images.json` and edit the list. Now there are two rules to keep in step, two to test, and they will drift. With one definition the logic lives once and the *policy values* live in the assignments, where they are small, obvious and per-scope. The same split as a function and its arguments.

**What do the scopes do?** A resource must satisfy every assignment that reaches it. A container group in `rg-<you>-app` is judged by **both** `images-subscription` (1.0 or 2.0) and `images-strict` (2.0 only), and must pass both, so 2.0 effectively. A container group anywhere else in the subscription is judged only by the first. Narrower scopes are stricter, never looser: you cannot use a closer assignment to *relax* a wider one. To relax, you need an exemption (Lab 8).

**Parameters have types.** `allowedImages` is an `Array`, and `jsonencode` turns an HCL list into the JSON the cloud expects. Hand it a string, and the cloud refuses the assignment.

**Open the portal.** After about 100 seconds the definition **Allowed container images** (Custom) shows under Definitions, and after another 100 seconds both assignments appear: one at your subscription scope, one at `rg-<you>-app`, the second marked **Do not enforce**.

## 4. The dry run

`enforce = false` means the new strict rule is evaluated but cannot refuse anything. Your app still runs `dojo/hello:1.0`.

**Your turn:** when the apply is done, open the **Compliance** view in the portal. Predict: is `ci-<you>-app` compliant with `images-subscription`? With `images-strict`?

<!-- dojo-reveal: Results of the apply and Compliance -->

```text
azurerm_policy_definition.allowed_images: Creation complete after 1m40s
azurerm_resource_group_policy_assignment.images_strict: Creation complete after 1m41s
azurerm_subscription_policy_assignment.images_subscription: Creation complete after 1m41s

Apply complete! Resources: 3 added, 0 changed, 0 destroyed.
```

Your app was running `dojo/hello:1.0` the whole time, and it is untouched: nothing was refused, and no write was attempted. In the **Compliance** view:

- `ci-<you>-app` is **Compliant** with `images-subscription` (1.0 is on that list).
- `ci-<you>-app` is **NonCompliant** with `images-strict`. The reason lists the conditions that matched, ending (abridged) in `containers[*].image is 'dojo/hello:1.0', which is not in [dojo/hello:2.0]`.

That second line is the whole value of DoNotEnforce: before blocking anyone, you can see exactly which of your existing resources the stricter rule would catch. Here it catches one, and it is yours.

<!-- /dojo-reveal -->

## 5. Move the app to 2.0

Fix it before enforcing. The image of a container cannot be changed in place, so OpenTofu replaces the container group; expect a few seconds of downtime.

Open `infra/main.tf` in your editor and change the image:

```hcl
    image  = "dojo/hello:2.0"
```

**Your turn:** predict: will the plan show a change in place, or a replacement?

```sh
cd ~/lab/cloud-policy-as-code/infra
tofu plan
tofu apply -auto-approve
```

<!-- dojo-reveal: Results of plan and apply -->

```text
Plan: 1 to add, 0 to change, 1 to destroy.
```

```text
azurerm_container_group.app: Destruction complete after 5s
azurerm_container_group.app: Creation complete after 20s

Apply complete! Resources: 1 added, 0 changed, 1 destroyed.
```

In **Compliance**, `ci-<you>-app` is now Compliant with `images-strict` as well.

<!-- /dojo-reveal -->

## 6. Enforce

Removing `enforce = false` turns the dry run into a real rule, with no rule or parameter edited. It changes only the assignment and takes about 2 minutes.

Open `policy/cloud/main.tf` in your editor and remove the `enforce = false` line from `images_strict`.

**Your turn:** predict what the plan will show, then apply.

```sh
cd ~/lab/cloud-policy-as-code/policy/cloud
tofu fmt
tofu plan
tofu apply -auto-approve
```

<!-- dojo-reveal: Results of plan and apply -->

```text
  ~ resource "azurerm_resource_group_policy_assignment" "images_strict" {
      ~ enforce = false -> true
    }

Plan: 0 to add, 1 to change, 0 to destroy.
```

Going from "report only" to "enforced" cost you *no* rule edits and nothing broke, because you checked the report first. That is the point of DoNotEnforce.

```text
Apply complete! Resources: 0 added, 1 changed, 0 destroyed.
```

<!-- /dojo-reveal -->

## 7. Same image, two scopes, two verdicts

Prove the scope works: the same image should be refused in one group and allowed in another. In the scratch folder, you will try to start a container group running 1.0 **inside the strict resource group**. (A subscription may hold at most two container groups and the app uses one, so run the second attempt only after the first was refused.)

Set up the scratch folder:

```sh
mkdir -p ~/lab/scratch && cd ~/lab/scratch
cp ~/lab/cloud-policy-as-code/infra/{providers,versions,variables}.tf .
sed -i 's#tfstate/infra#tfstate/scratch#' versions.tf
tofu init
```

Create `main.tf` there in your editor:

```hcl
data "azurerm_resource_group" "rg" {
  name = "rg-${var.owner}-app"
}

resource "azurerm_container_group" "scratch" {
  name                = "ci-${var.owner}-scratch"
  location            = data.azurerm_resource_group.rg.location
  resource_group_name = data.azurerm_resource_group.rg.name
  os_type             = "Linux"
  ip_address_type     = "Public"
  dns_name_label      = "${var.owner}-scratch"

  exposed_port {
    port     = 80
    protocol = "TCP"
  }

  container {
    name   = "hello"
    image  = "dojo/hello:1.0"
    cpu    = 0.25
    memory = 0.125

    ports {
      port     = 80
      protocol = "TCP"
    }
  }

  tags = {
    owner      = var.owner
    env        = "dev"
    costCenter = "cc-1001"
  }
}
```

**Prefer the terminal?** Write the same file with a heredoc: `cat > main.tf <<'EOT'`, paste the block above, and end with `EOT`.

**Your turn:** predict: refused or allowed, and which assignment will be named?

```sh
tofu apply -auto-approve
```

<!-- dojo-reveal: Results of the strict-group apply -->

```text
Error: creating Container Group (Subscription: "<your subscription id>"
Resource Group Name: "rg-student01-app"
Container Group Name: "ci-student01-scratch"): performing ContainerGroupsCreateOrUpdate: unexpected status 403 (403 Forbidden) with error:
RequestDisallowedByPolicy: Resource 'ci-student01-scratch' was disallowed by policy.
Policy: 'Allowed container images'. Assignment 'images-strict', definition 'Allowed container images': ...
```

(abridged.) It names `images-strict`, not `images-subscription`.

<!-- /dojo-reveal -->

Now point the same container at the **legacy** group, which only the subscription-wide assignment covers. In `main.tf`, change `rg-${var.owner}-app` in the data source to `rg-${var.owner}-legacy`.

**Prefer the terminal?**

```sh
sed -i 's/-app"/-legacy"/' main.tf
```

**Your turn:** predict the outcome, then apply.

```sh
tofu apply -auto-approve
```

<!-- dojo-reveal: Results of the legacy-group apply -->

```text
Apply complete! Resources: 1 added, 0 changed, 0 destroyed.
```

The same image, 1.0, allowed in one group and refused in another: that is scope.

<!-- /dojo-reveal -->

Clean up:

```sh
tofu destroy -auto-approve
```

## 8. Commit it

```sh
cd ~/lab/cloud-policy-as-code
git add infra policy
git commit -m "Allowed images: one definition, two assignments; app on 2.0"
```

## Check

- [ ] The portal shows one **Allowed container images** definition and two assignments of it, at two scopes.
- [ ] You saw `ci-<you>-app` NonCompliant with `images-strict` while it was set to not enforce, and Compliant after moving to 2.0.
- [ ] A 1.0 container group was refused in `rg-<you>-app` but created in `rg-<you>-legacy`.

## Recap

- Put the logic in the definition and the values in the assignment: one definition, many assignments.
- A resource must satisfy every assignment that reaches it. A narrower scope can only be stricter.
- `enforce = false` (DoNotEnforce) keeps evaluating and reporting but never blocks, a safe way to stage a deny rule. `audit` is the rule's own effect; DoNotEnforce is a switch on the assignment.
- Look at the compliance report before you enforce.

**Next:** [Lab 6](lab6.md): you now have several assignments to manage. Bundle them into a **policy set**.

---

## Challenge c1: Allowed Environments (bonus)

Write your own parameterised `audit` rule: flag any resource whose `env` tag is not in a list you pass in, and see it
report a seeded resource group as non-compliant. It works on one resource group of your own, so the lab's assignments
stay as they are.

Only when your class has achievements on (you see a score on your landing page). Start it in the terminal:

```sh
dojo challenge start c1
cd ~/lab/challenge-c1
```

That makes your own repo `$USER/challenge-c1` and clones it to `~/lab/challenge-c1`, and prints the goal, with your own names in it. Push `main` when you think it's done, then:

```sh
dojo check c1
```

A wrong answer costs nothing. `dojo check hint c1` gives a hint for part of the points, and
`dojo challenge reset c1` throws the repo away and starts you over from a fresh copy.

