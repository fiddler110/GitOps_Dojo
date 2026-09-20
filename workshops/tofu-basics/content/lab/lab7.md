# Lab 7 — Drift: when reality changes behind your back

**Goal:** change your deployment by clicking in the portal, then see how OpenTofu notices (`plan`) and puts things right (`apply`).

```sh
cd ~/lab/tofu-basics
```

You need your Lab 5 deployment running (`terraform plan` says `No changes.`). Have the portal open in a browser tab.

**Drift** is when the real world no longer matches your code and your state: someone clicked in a console, a script ran, something crashed. It happens in every team that has both people and code. The question is whether you can *see* it.

---

## 1. A small drift: someone edits a tag

In the portal go to **Container instances**, click `ci-hello-dev`, and scroll to **Tags**. Click **Add tag**, use the key `edited_by` and the value `portal`, then **Save tags**.

(Saving replaces the whole tag set, so leave the existing `owner`, `env` and `managed_by` rows as they are.)

Now, in the terminal, **change nothing** and ask OpenTofu what it sees:

```sh
terraform plan
```

Expected:

```text
azurerm_resource_group.main: Refreshing state... [id=/subscriptions/260eb175-2be3-5b4e-a481-d14ff2e938cf/resourceGroups/rg-hello-dev-cac]
azurerm_container_group.hello: Refreshing state... [id=/subscriptions/260eb175-2be3-5b4e-a481-d14ff2e938cf/resourceGroups/rg-hello-dev-cac/providers/Microsoft.ContainerInstance/containerGroups/ci-hello-dev]

OpenTofu used the selected providers to generate the following execution
plan. Resource actions are indicated with the following symbols:
  ~ update in-place (current -> planned)

OpenTofu will perform the following actions:

  # azurerm_container_group.hello will be updated in-place
  ~ resource "azurerm_container_group" "hello" {
        id                          = "/subscriptions/260eb175-2be3-5b4e-a481-d14ff2e938cf/resourceGroups/rg-hello-dev-cac/providers/Microsoft.ContainerInstance/containerGroups/ci-hello-dev"
        name                        = "ci-hello-dev"
      ~ tags                        = {
          - "edited_by"  = "portal" -> null
            "env"        = "dev"
            "managed_by" = "opentofu"
            "owner"      = "student01"
        }
        # (13 unchanged attributes hidden)

        # (1 unchanged block hidden)
    }

Plan: 0 to add, 1 to change, 0 to destroy.
```

You changed no `.tf` file, yet there is a plan. That is the "Refreshing state" step from Lab 5 at work: OpenTofu re-read the real resource, found the extra tag, and computed what it would take to make reality match **your code** again: remove it (`- "edited_by" = "portal" -> null`).

```sh
terraform apply
```

Type `yes`. In-place edits are quick:

```text
azurerm_container_group.hello: Modifying... [id=/subscriptions/260eb175-...]
azurerm_container_group.hello: Modifications complete after 1s [id=/subscriptions/260eb175-...]

Apply complete! Resources: 0 added, 1 changed, 0 destroyed.
```

Reload the container's page in the portal: the `edited_by` tag is gone. **Your code won.**

## 2. A big drift: someone deletes the container

In the portal, open `ci-hello-dev` again and click **Delete**. A dialog warns you that this creates drift. Confirm with **Delete container instance**. You go back to the (now empty) list of container instances, and **Quota** drops to `0 / 2`. Your site is gone (reload it: 404).

Back in the terminal:

```sh
terraform plan
```

Expected (abridged):

```text
azurerm_resource_group.main: Refreshing state... [id=...]
azurerm_container_group.hello: Refreshing state... [id=...]

Note: Objects have changed outside of OpenTofu

OpenTofu detected the following changes made outside of OpenTofu since the
last "tofu apply" which may have affected this plan:

  # azurerm_container_group.hello has been deleted
  - resource "azurerm_container_group" "hello" {
      - fqdn                        = "hello-dev-student01.canadacentral.dojo-cloud.test" -> null
      - id                          = "/subscriptions/260eb175-.../containerGroups/ci-hello-dev" -> null
        name                        = "ci-hello-dev"
        tags                        = {
            "env"        = "dev"
            "managed_by" = "opentofu"
            "owner"      = "student01"
        }
        # (12 unchanged attributes hidden)

        # (1 unchanged block hidden)
    }

Unless you have made equivalent changes to your configuration, or ignored the
relevant attributes using ignore_changes, the following plan may include
actions to undo or respond to these changes.

─────────────────────────────────────────────────────────────────────────────

OpenTofu used the selected providers to generate the following execution
plan. Resource actions are indicated with the following symbols:
  + create

OpenTofu will perform the following actions:

  # azurerm_container_group.hello will be created
  + resource "azurerm_container_group" "hello" {
      + dns_name_label              = "hello-dev-student01"
      ...
    }

Plan: 1 to add, 0 to change, 0 to destroy.

Changes to Outputs:
  ~ fqdn        = "hello-dev-student01.canadacentral.dojo-cloud.test" -> (known after apply)
  ~ resource_id = "/subscriptions/260eb175-.../containerGroups/ci-hello-dev" -> (known after apply)
```

Read it in two halves. The first says **"Objects have changed outside of OpenTofu"**: the container group `has been deleted`. That is the drift report. The second is the plan to fix it: `+ create` (1 to add), because your code still says the container should exist.

```sh
terraform apply
```

Type `yes`:

```text
azurerm_container_group.hello: Creating...
azurerm_container_group.hello: Still creating... [10s elapsed]
azurerm_container_group.hello: Creation complete after 12s [id=...]

Apply complete! Resources: 1 added, 0 changed, 0 destroyed.
```

About 12-15 seconds later the container is back in the portal, **Running**, and your site is up again. Check:

```sh
terraform plan
```

`No changes. Your infrastructure matches the configuration.` (You'll see the usual two "Refreshing state" lines above it.)

## 3. Read the story in the Activity log

Open the portal's **Activity log**. Your recent rows (newest first) tell exactly what happened, and **who did it**:

```text
Create/Update container group           Succeeded     <- your apply, bringing the container back
Delete container group (portal)         Succeeded     <- you, deleting it in the portal
Update container group tags             Succeeded     <- your first apply, putting the tags back
Update container group tags (portal)    Succeeded     <- you, adding edited_by
...                                                   <- older rows follow (Lab 5, and Lab 6's failed attempts)
```

Changes made by OpenTofu have plain names; changes made by hand in this portal are labelled **(portal)**. In a real cloud the activity log is how you find out who touched what, and it is why "clicking in the console" is discouraged for anything that IaC owns.

## What just happened

`plan` compares three things: your **code** (what you want), your **state** (what OpenTofu remembers), and the **real world** (what the cloud says now). In Lab 1 all three matched. Here the real world moved, and OpenTofu noticed because it **refreshes** before planning.

| | Click in a console | Change the code |
| - | ------------------ | ---------------- |
| Reviewable in git? | no | yes |
| Repeatable? | no | yes |
| Noticed by the next `plan`? | yes, as drift | (it is the plan) |
| Who did it? | the activity log | the git history |

Neither `apply` above was a surprise: `plan` told you first. Drift you can *see* is drift you can fix. When drift is intentional (say the portal change was right), the fix is to update the **code** to match, not to fight it.

## Check yourself

1. What did `terraform plan` compare to notice the missing container? *(the real cloud, via a refresh, against state and config)*
2. Why did the deleted container come back with `+ create` rather than an error? *(your code still describes it; `apply` makes reality match the code)*
3. If the portal change had been correct, what should you have done instead of `apply`? *(edit the `.tf` files to include it, then plan until "No changes")*

## Troubleshooting

| You see | Cause / fix |
| ------- | ----------- |
| The portal has no **Delete** button, or an error when deleting or saving tags | The facilitator can switch portal write actions off. Ask them to turn them on for this lab. |
| The portal still shows the old state | It refreshes every ~3 s. Click **Refresh now**. |
| `plan` says `No changes` after you deleted the container | Make sure you deleted `ci-hello-dev` (not just opened it), and that you are running `plan` in `~/lab/tofu-basics`. |
| `Error: a resource with the ID ... already exists` | Your `terraform.tfstate` was deleted or you are in a different folder, so OpenTofu forgot what it created. Ask the facilitator to **Purge** your subscription, then `apply` again. |

**Next:** [lab8.md](lab8.md)
