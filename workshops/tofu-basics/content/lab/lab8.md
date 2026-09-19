# Lab 8 — Change types: in-place vs replace

**Goal:** make three small edits and predict, before you run `plan`, whether each one is a quiet update (`~`) or a rebuild (`-/+`). Then try forcing a rebuild and meet `create_before_destroy`.

```sh
cd ~/lab/tofu-basics
```

You need your deployment running and `terraform plan` clean (`No changes.`).

In Lab 2 you saw one edit produce both a `~` and a `-/+`. **The provider decides, attribute by attribute,** which changes the cloud can do to a running thing and which need a new one. The only way to know is to read the plan. Here is how the `azurerm_container_group` behaves:

| Edit | Result |
| ---- | ------ |
| a tag | `~` update in place |
| an environment variable (your message) | `-/+` replace |
| the image | `-/+` replace |
| the size (Lab 6), the DNS name label | `-/+` replace |

Make your prediction for each edit below, then check.

---

## 1. A tag: in place

Add a tag in `locals.tf`. Put a new line under `managed_by` in the `tags` block:

```sh
sed -i '/managed_by = "opentofu"/a\    cost_center = "training"' locals.tf
terraform fmt
git diff
```

`terraform fmt` tidies formatting and prints the names of files it changed (`locals.tf`). It re-aligns the `=` signs. The diff (header trimmed):

```text
   tags = {
-    owner      = var.owner
-    env        = var.environment
-    managed_by = "opentofu"
+    owner       = var.owner
+    env         = var.environment
+    managed_by  = "opentofu"
+    cost_center = "training"
   }
```

```sh
terraform plan
```

Expected (abridged):

```text
  # azurerm_container_group.hello will be updated in-place
  ~ resource "azurerm_container_group" "hello" {
      ~ tags                        = {
          + "cost_center" = "training"
            "env"         = "dev"
            "managed_by"  = "opentofu"
            "owner"       = "student01"
        }
        ...
    }

  # azurerm_resource_group.main will be updated in-place
  ~ resource "azurerm_resource_group" "main" {
      ~ tags     = {
          + "cost_center" = "training"
            ...
        }
    }

Plan: 0 to add, 2 to change, 0 to destroy.
```

`~` twice: the tags are on both resources, and both can change in place.

```sh
terraform apply
```

Type `yes`:

```text
azurerm_resource_group.main: Modifying... [id=/subscriptions/260eb175-...]
azurerm_resource_group.main: Modifications complete after 0s [id=/subscriptions/260eb175-...]
azurerm_container_group.hello: Modifying... [id=/subscriptions/260eb175-...]
azurerm_container_group.hello: Modifications complete after 0s [id=/subscriptions/260eb175-...]

Apply complete! Resources: 0 added, 2 changed, 0 destroyed.
```

A second or two, and **no downtime**: your site kept running. Check the tag in the portal.

## 2. The message: replace

The site's text is passed to the container as an **environment variable** (`MESSAGE`). Change it in `terraform.tfvars`:

```sh
sed -i 's/^message .*/message     = "Hello, Canada!"/' terraform.tfvars
git diff terraform.tfvars
terraform plan
```

Expected (abridged):

```text
  # azurerm_container_group.hello must be replaced
-/+ resource "azurerm_container_group" "hello" {
      ~ fqdn                        = "hello-dev-student01.canadacentral.dojo-cloud.test" -> (known after apply)
      ~ id                          = "/subscriptions/260eb175-.../containerGroups/ci-hello-dev" -> (known after apply)
      ~ ip_address                  = "10.20.78.32" -> (known after apply)
        name                        = "ci-hello-dev"
        ...
      ~ container {
          ~ commands                     = [] -> (known after apply)
          ~ environment_variables        = { # forces replacement
              ~ "MESSAGE" = "Hello from Dojo Cloud!" -> "Hello, Canada!"
                # (1 unchanged element hidden)
            }
            name                         = "hello"
            ...
        }
    }

Plan: 1 to add, 0 to change, 1 to destroy.
```

`# forces replacement` is printed right next to the attribute responsible. Only the container group is replaced; the resource group (which never changed) is left alone. (Your IP will differ.)

```sh
terraform apply
```

Type `yes`:

```text
azurerm_container_group.hello: Destroying... [id=/subscriptions/260eb175-...]
azurerm_container_group.hello: Still destroying... [id=/subscriptions/260eb175-...rInstance/containerGroups/ci-hello-dev, 10s elapsed]
azurerm_container_group.hello: Destruction complete after 13s
azurerm_container_group.hello: Creating...
azurerm_container_group.hello: Still creating... [10s elapsed]
azurerm_container_group.hello: Creation complete after 13s [id=/subscriptions/260eb175-...]

Apply complete! Resources: 1 added, 0 changed, 1 destroyed.
```

About 27 seconds: 13 to destroy, then 13 to create. The site was **down the whole time**. Reload it (portal **Browse**): **Hello, Canada!** Compare with step 1: a tag edit was a second, a message edit was half a minute of downtime.

## 3. The image: replace

Now switch to the newer image. The starter's `validation` only allows `1.0` and `2.0`, the two versions policy approves.

```sh
sed -i 's/^image_tag .*/image_tag   = "2.0"/' terraform.tfvars
terraform plan
```

The interesting part of the plan:

```text
      ~ container {
          ~ commands                     = [] -> (known after apply)
          ~ image                        = "dojo/hello:1.0" -> "dojo/hello:2.0" # forces replacement
            name                         = "hello"
            ...
        }
    }

Plan: 1 to add, 0 to change, 1 to destroy.
```

```sh
terraform apply
```

Type `yes` (about 27 seconds again; the end of the output is `Apply complete! Resources: 1 added, 0 changed, 1 destroyed.`). Browse to the site: the page is now **green** and the pills say `image: dojo/hello:2.0`. Same message, new image. **Pinning image versions in code** is what makes an upgrade a reviewable one-line change, and rolling back the same.

## 4. Force a replacement: `-replace`

Sometimes a resource must be rebuilt even though nothing in the config changed (it is stuck, or you want a fresh start). Don't edit anything, just ask:

```sh
terraform plan -replace=azurerm_container_group.hello
```

Expected (abridged):

```text
  # azurerm_container_group.hello will be replaced, as requested
-/+ resource "azurerm_container_group" "hello" {
      ~ fqdn                        = "hello-dev-student01.canadacentral.dojo-cloud.test" -> (known after apply)
      ...
    }

Plan: 1 to add, 0 to change, 1 to destroy.
```

`will be replaced, as requested`. `azurerm_container_group.hello` is the address you see in `terraform state list`. You don't have to apply it.

## 5. Optional: `create_before_destroy`

Replacement means **destroy, then create**, hence the downtime. OpenTofu can reverse the order for a resource with a `lifecycle` block, so the new one exists before the old one is removed. Try it. Add this at the end of the `azurerm_container_group` "hello" resource in `main.tf` (just above its closing `}`):

```hcl
  lifecycle {
    create_before_destroy = true
  }
```

(Or from the terminal, which inserts it before the last line of the file:)

```sh
sed -i '$i\\n  lifecycle {\n    create_before_destroy = true\n  }' main.tf
```

Now force a replacement:

```sh
terraform plan -replace=azurerm_container_group.hello | grep -E 'Plan:|replace'
```

```text
+/- create replacement and then destroy
  # azurerm_container_group.hello will be replaced, as requested
Plan: 1 to add, 0 to change, 1 to destroy.
```

The symbol flips to `+/-`: *create* first, *then* destroy. Apply it:

```sh
terraform apply -replace=azurerm_container_group.hello
```

Type `yes`:

```text
azurerm_container_group.hello: Creating...

Error: a resource with the ID "/subscriptions/260eb175-2be3-5b4e-a481-d14ff2e938cf/resourceGroups/rg-hello-dev-cac/providers/Microsoft.ContainerInstance/containerGroups/ci-hello-dev" already exists - to be managed via Terraform this resource needs to be imported into the State. Please see the resource documentation for "azurerm_container_group" for more information

  with azurerm_container_group.hello,
  on main.tf line 13, in resource "azurerm_container_group" "hello":
  13: resource "azurerm_container_group" "hello" {
```

It **fails, harmlessly** (the old container is still running; check `terraform state list` and the portal). The replacement has exactly the same name and Resource ID as the original, and two things can't have the same ID at the same time. `create_before_destroy` only works when old and new can **coexist**, meaning their names, DNS labels and so on differ (for example a random suffix in the name). It is a tool for zero-downtime upgrades of things behind a load balancer, not a switch to flip on everything.

Remove the block again:

```sh
git checkout main.tf
```

## What just happened

| Edit | Plan symbol | Cost |
| ---- | ----------- | ---- |
| tag | `~` | ~1 s, no downtime |
| message (environment variable) | `-/+` | ~27 s, site down |
| image | `-/+` | ~27 s, site down |
| `-replace=...` | `-/+` | same as any replace |
| `create_before_destroy` | `+/-` | needs the new one to be able to coexist with the old |

You can't memorise which attributes are which for every resource in every provider, and you don't need to: **read the plan, look for `# forces replacement`, and decide whether you can afford it.**

Leave things as they are: image `2.0`, message "Hello, Canada!", the `cost_center` tag. The next lab builds on them.

## Check yourself

1. You change one tag and one environment variable in a single edit. What does `plan` say for the container group? *(replace, `-/+`; the whole resource is replaced if any one attribute forces it)*
2. What does `# forces replacement` mean? *(this attribute can't be edited in place, so the resource is destroyed and recreated)*
3. Why did `create_before_destroy` fail here? *(the new container has the same name/ID as the old one, so they can't exist together)*

## Troubleshooting

| You see | Cause / fix |
| ------- | ----------- |
| `Invalid value for variable ... image_tag must be 1.0 or 2.0` | Only those two images are approved, and your `validation` block says so. Use `1.0` or `2.0`. |
| `terraform fmt` printed nothing | The file was already formatted. Nothing to do. |
| `plan` shows `-/+` when you expected `~` | Read which attribute says `# forces replacement`. Some attributes just can't change in place. |
| Site shows the old message/image | The replacement takes ~27 s. Wait for `Apply complete!` and reload. |
| The site is down after a failed `apply` | See Lab 6, section 3: fix the cause, `apply` again. |

**Next:** [lab9.md](lab9.md)
