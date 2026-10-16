# Lab 1: Why guardrails? Meet your first refusal

**Time:** about 8 minutes. **Goal:** break the platform's built-in rules on purpose, read what the cloud says, and find those same rules in the portal. By the end you should be able to answer: *who said no, which rule, and where is that rule written down?*

> **Starting here?** This lab needs your clone with the app applied (Lab 0). Run `dojo prep 1` to set that up; it is safe to run even if you did Lab 0.

## Why guardrails exist

Access control (who may do something) is not enough. A developer who is *allowed* to create container groups can still create one in a country your data may not leave, running an unreviewed image, with eight times the CPU the team budgeted. Roles answer "may this person create resources?". **Policy** answers "what may those resources look like?".

Two properties make policy different from a code review or a checklist:

1. It is enforced **by the cloud, at write time**, for every tool: the portal, the CLI, OpenTofu, a pipeline. There is no path around it that does not involve changing the policy itself.
2. It is **data**. The rule is a document the cloud evaluates, which means you can store it, review it and test it.

The platform team has already assigned a set of guardrails to everyone. You can read them but not change them.

## 1. A scratch folder

You are going to try things that fail. Do it in a throwaway folder with its own state, so your real app is never at risk. The folder reuses the same provider setup and login as the app. The `sed` points the copied backend at a state named `scratch`: left on `infra`, the scratch folder would share your app's state, and its first apply would destroy the app. `TF_VAR_owner` is already set, so the scratch resources are named `rg-<you>-scratch`.

**Your turn:** run these. Before you do, predict: which line protects your real app from the scratch experiments?

```sh
mkdir -p ~/lab/scratch && cd ~/lab/scratch
cp ~/lab/cloud-policy-as-code/infra/{providers,versions,variables}.tf .
sed -i 's#tfstate/infra#tfstate/scratch#' versions.tf
tofu init
```

- The `sed` line: it points the backend at the `scratch` state.

## 2. A resource group in the wrong country

`tofu plan` only checks that your configuration is valid. The refusal comes when the write reaches the cloud, so you will see it at `apply`, not before. Every refusal you will meet in this workshop has the same shape: a status code, `RequestDisallowedByPolicy`, the resource, the policy name and a reason.

```text
tofu apply -auto-approve
```

Create `main.tf` in the scratch folder in your editor with a resource group in `eastus`:

```hcl
resource "azurerm_resource_group" "scratch" {
  name     = "rg-${var.owner}-scratch"
  location = "eastus"
  tags = {
    owner = var.owner
    env   = "dev"
  }
}
```

**Prefer the terminal?**

```sh
cat > main.tf <<'EOT'
resource "azurerm_resource_group" "scratch" {
  name     = "rg-${var.owner}-scratch"
  location = "eastus"
  tags = {
    owner = var.owner
    env   = "dev"
  }
}
EOT
```

**Your turn:** before you run it, predict: will it fail, and if so, who will say no and what will the message name?

```sh
tofu apply -auto-approve
```

<!-- dojo-reveal: Results of the eastus apply -->

- It fails at apply, not at plan. Expected (abridged):

```text
Error: creating "Resource Group (Subscription: \"<your subscription id>\"\nResource Group Name: \"rg-student01-scratch\")": unexpected status 403 (403 Forbidden) with error:
RequestDisallowedByPolicy: Resource 'rg-student01-scratch' was disallowed by policy.
Policy: 'Allowed locations'. Location 'eastus' is not allowed; use one of: canadacentral, canadaeast.
```

Read it slowly:

- **403** and `RequestDisallowedByPolicy`: the request was fine, the caller was allowed, but *a policy said no*. A missing permission would be a different error.
- **`Resource 'rg-student01-scratch'`**: what was refused.
- **`Policy: 'Allowed locations'`**: which rule refused it. This is a name you can look up.
- The last sentence: why, and how to fix it.

Nothing was created. A denied write has no side effects.

<!-- /dojo-reveal -->

## 3. A resource group with no tags

Two of the built-in rules are about tags: `owner` and `env` must be present. In `main.tf`, change `eastus` to `canadacentral` and delete the `env` line.

**Prefer the terminal?**

```sh
cat > main.tf <<'EOT'
resource "azurerm_resource_group" "scratch" {
  name     = "rg-${var.owner}-scratch"
  location = "canadacentral"
  tags = {
    owner = var.owner
  }
}
EOT
```

**Your turn:** the region is now fine. Predict which policy refuses it this time, then restore the `env` tag and apply again.

```sh
tofu apply -auto-approve
sed -i 's/owner = var.owner/owner = var.owner\n    env   = "dev"/' main.tf
tofu apply -auto-approve
```

<!-- dojo-reveal: Results of the two applies -->

The first apply is refused:

```text
Error: creating "Resource Group (Subscription: \"<your subscription id>\"\nResource Group Name: \"rg-student01-scratch\")": unexpected status 403 (403 Forbidden) with error:
RequestDisallowedByPolicy: Resource 'rg-student01-scratch' was disallowed by policy.
Policy: 'Require tag 'env''. The resource is missing the required tag 'env'.
```

A different rule, the same shape. With the `env` tag back, the second apply creates the group:

```text
azurerm_resource_group.scratch: Creation complete after 2s
Apply complete! Resources: 1 added, 0 changed, 0 destroyed.
```

<!-- /dojo-reveal -->

## 4. A container that is too big

The platform's CPU, memory, image, port and environment-variable limits are enforced by the same policy engine, but they are reported with the cloud's older, plainer error codes, so the shape of the error differs from the location and tag rules. The custom policies you write from Lab 3 onward always report as the 403 form, with the assignment and definition named.

In your editor, append a container group to `main.tf`, asking for twice the allowed CPU (`0.5`):

```hcl
resource "azurerm_container_group" "scratch" {
  name                = "ci-${var.owner}-scratch"
  location            = azurerm_resource_group.scratch.location
  resource_group_name = azurerm_resource_group.scratch.name
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
    cpu    = 0.5
    memory = 0.125

    ports {
      port     = 80
      protocol = "TCP"
    }
  }

  tags = {
    owner = var.owner
    env   = "dev"
  }
}
```

**Prefer the terminal?** Append the same block with a heredoc:

```sh
cat >> main.tf <<'EOT'

resource "azurerm_container_group" "scratch" {
  name                = "ci-${var.owner}-scratch"
  location            = azurerm_resource_group.scratch.location
  resource_group_name = azurerm_resource_group.scratch.name
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
    cpu    = 0.5
    memory = 0.125

    ports {
      port     = 80
      protocol = "TCP"
    }
  }

  tags = {
    owner = var.owner
    env   = "dev"
  }
}
EOT
```

**Your turn:** before you run it, predict: will the status code be 403 again? Will the message name a policy?

```sh
tofu apply -auto-approve
```

<!-- dojo-reveal: Results of the oversize container apply -->

```text
Error: creating Container Group (Subscription: "<your subscription id>"
Resource Group Name: "rg-student01-scratch"
Container Group Name: "ci-student01-scratch"): performing ContainerGroupsCreateOrUpdate: unexpected status 400 (400 Bad Request) with error:
InvalidResourceRequest: Requested 0.5 vCPU / 0.125 GB exceeds the per-container limit of 0.25 vCPU / 0.125 GB.
```

Notice this one is a **400**, not a 403, and has no policy name. That is deliberate: the location and tag rules report as `RequestDisallowedByPolicy`, the resource limits in the older plainer form.

<!-- /dojo-reveal -->

Change `cpu = 0.5` back to `cpu = 0.25` if you like and apply again to watch it succeed; either way you finish with step 6.

## 5. Find the rules in the portal

Open the **Dojo Cloud** portal and go to the **Policy** blade (a blade is one page of the portal; this one is for policy). You will see:

- **Assignments:** the platform's guardrails, each named `platform-...`, with scope `/` (the whole platform) and an enforcement mode of **Enforced**. Find "Allowed locations" and "Require tag 'env'": they are the exact names in the errors above.
- **Definitions:** the built-in definitions behind them (marked BuiltIn): Allowed locations, Require tag 'owner', Require tag 'env', Allowed container images, Maximum container CPU, Maximum container memory, Allowed container ports, Maximum environment variables.
- **Compliance:** for each resource, whether it passes each assignment. Your `ci-<you>-app` should be fully compliant.

Click "Allowed locations" and read its definition. You can read it, but there is no edit button for a built-in. That separation is the point: *the people who write the rules are not the people who deploy under them*.

> **Two kinds of "no".** Dojo Cloud also refuses some things that are not policy at all: resource names must start with `rg-` and `ci-`, and a subscription may hold at most two container groups. Those are plain validation in the API. You cannot see them in the Policy blade, and you cannot change them with policy.

## 6. Clean up the scratch folder

```bash
tofu destroy -auto-approve
```

Destroys are not evaluated by policy, so they are instant. Before you run it, predict how many resources it will destroy.

<!-- dojo-reveal: Results of tofu destroy -->

```text
Destroy complete! Resources: 2 destroyed.
```

(If you stopped before the container group was created, it says 1 destroyed.)

<!-- /dojo-reveal -->

Your real app in `~/lab/cloud-policy-as-code/infra` was never touched.

## Check

- [ ] You saw a `RequestDisallowedByPolicy` 403 and can say which policy refused you and why.
- [ ] You found "Allowed locations" under the portal's Policy blade and saw it is a built-in with scope `/`.
- [ ] You can explain why the CPU error is a 400 and the location error a 403 (see step 4).

## Recap

- Policy limits what resources may *look like*; roles limit who may create them.
- It is enforced by the cloud at write time, so a bad `apply` fails at the end, not at `plan`.
- A refusal names the resource, the policy and the reason, and a denied write creates nothing.
- The platform's guardrails live in the Policy blade, read-only to you.

**Next:** [Lab 2](lab2.md) opens up a definition and shows how a rule, an assignment and a scope fit together.
