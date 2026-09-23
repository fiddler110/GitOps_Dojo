# Lab 5 — Deploy hello

**Goal:** create a resource group and a running container with `apply`, open the site it serves, and watch it appear in the portal.

```sh
cd ~/lab/tofu-basics
```

Keep the portal open in another tab (Home or **Resource groups**). You'll watch it change.

---

## 1. Read what you're about to build

```sh
cat locals.tf
cat terraform.tfvars
```

`terraform.tfvars` holds the values (`location = "canadacentral"`, `environment = "dev"`, ...). `locals.tf` turns them into names and tags:

| Local | Value for you | Rule |
| ----- | ------------- | ---- |
| `rg_name` | `rg-hello-dev-cac` | resource groups must start with `rg-` |
| `ci_name` | `ci-hello-dev` | container groups must start with `ci-` |
| `dns_label` | `hello-dev-<your username>` | your site's name, unique across the class |
| `tags` | `owner`, `env`, `managed_by` | `owner` and `env` are **required** |

Now `main.tf`:

```sh
cat main.tf
```

Two resources. The important line is in the second one: `resource_group_name = azurerm_resource_group.main.name`. That reference tells OpenTofu the container group **depends on** the resource group, so the group is created first. The container itself runs the approved `dojo/hello:1.0` image and gets your message as the environment variable `MESSAGE`.

## 2. `plan`

```sh
terraform plan
```

Expected (abridged: the header text and a few lines are trimmed):

```terraform
  # azurerm_container_group.hello will be created
  + resource "azurerm_container_group" "hello" {
      + dns_name_label              = "hello-dev-student01"
      + dns_name_label_reuse_policy = "Unsecure"
      + exposed_port                = [
          + {
              + port     = 80
              + protocol = "TCP"
            },
        ]
      + fqdn                        = (known after apply)
      + id                          = (known after apply)
      + ip_address                  = (known after apply)
      + ip_address_type             = "Public"
      + location                    = "canadacentral"
      + name                        = "ci-hello-dev"
      + network_profile_id          = (known after apply)
      + os_type                     = "Linux"
      + resource_group_name         = "rg-hello-dev-cac"
      + restart_policy              = "Always"
      + sku                         = "Standard"
      + tags                        = {
          + "env"        = "dev"
          + "managed_by" = "opentofu"
          + "owner"      = "student01"
        }

      + container {
          + commands              = (known after apply)
          + cpu                   = 0.25
          + environment_variables = {
              + "MESSAGE" = "Hello from Dojo Cloud!"
              + "OWNER"   = "student01"
            }
          + image                 = "dojo/hello:1.0"
          + memory                = 0.125
          + name                  = "hello"

          + ports {
              + port     = 80
              + protocol = "TCP"
            }
        }
    }

  # azurerm_resource_group.main will be created
  + resource "azurerm_resource_group" "main" {
      + id       = (known after apply)
      + location = "canadacentral"
      + name     = "rg-hello-dev-cac"
      + tags     = {
          + "env"        = "dev"
          + "managed_by" = "opentofu"
          + "owner"      = "student01"
        }
    }

Plan: 2 to add, 0 to change, 0 to destroy.

Changes to Outputs:
  + fqdn        = (known after apply)
  + resource_id = (known after apply)
  + url         = "https://<class-address>/cloud/site/hello-dev-student01/"
```

Your `student01` will be your own username, and `<class-address>` is whatever address your facilitator's server has. Nothing has been sent to the cloud: `plan` is a rehearsal.

## 3. `apply`

```sh
terraform apply
```

Read the plan again, then type `yes`. **Now switch to the portal** and click **Refresh now** (or just wait: it refreshes by itself every ~3 seconds).

Expected, in the terminal:

```text
azurerm_resource_group.main: Creating...
azurerm_resource_group.main: Still creating... [10s elapsed]
azurerm_resource_group.main: Still creating... [20s elapsed]
azurerm_resource_group.main: Creation complete after 20s [id=/subscriptions/260eb175-2be3-5b4e-a481-d14ff2e938cf/resourceGroups/rg-hello-dev-cac]
azurerm_container_group.hello: Creating...
azurerm_container_group.hello: Still creating... [10s elapsed]
azurerm_container_group.hello: Creation complete after 13s [id=/subscriptions/260eb175-2be3-5b4e-a481-d14ff2e938cf/resourceGroups/rg-hello-dev-cac/providers/Microsoft.ContainerInstance/containerGroups/ci-hello-dev]

Apply complete! Resources: 2 added, 0 changed, 0 destroyed.

Outputs:

fqdn = "hello-dev-student01.canadacentral.dojo-cloud.test"
resource_id = "/subscriptions/260eb175-2be3-5b4e-a481-d14ff2e938cf/resourceGroups/rg-hello-dev-cac/providers/Microsoft.ContainerInstance/containerGroups/ci-hello-dev"
url = "https://<class-address>/cloud/site/hello-dev-student01/"
```

The whole apply takes about **35 seconds**: about 20 for the resource group and 13 for the container group. (Your subscription ID and username will differ.)

In the portal you should see the **resource group appear within a couple of seconds**, long before OpenTofu says "Creation complete": the cloud accepts the request quickly, then OpenTofu politely keeps checking until the resource reports it is ready. Then the container instance appears as **Running**, and **Quota** goes to `1 / 2`.

Order matters: the resource group was created **first**, then the container group. You never wrote that order down; OpenTofu worked it out from the reference in `main.tf`, the same **dependency graph** idea as `random_pet` and `local_file` in Lab 1.

**Optional: see the graph.** `terraform graph` prints the graph as text in DOT, the language of the Graphviz drawing tool. Save it to a file:

```sh
terraform graph > graph.dot
```

Open `graph.dot` in the VS Code editor (Explorer, left), press **Ctrl+A** then **Ctrl+C**, and paste it into <https://www.devtoolsdaily.com/graphviz/> in your own browser to draw it.

How to read the picture:

- **An arrow means "waits for".** `azurerm_container_group.hello → azurerm_resource_group.main`: the container group can't start until the resource group exists.
- **Work starts at the bottom and moves up.** The things nothing depends on sit at the top. The bottom holds what's needed first: your **variables** (folded-page shapes) and the **provider** (diamond). The two **resources** (boxes) sit in between, with `local.*` and `output.*` (ovals) around them.
- **Ignore the plumbing.** `(expand)` is where OpenTofu works out how many copies of a resource there are (`count`, `for_each`). `provider[...] (close)` shuts the provider down once its last resource is done. `[root] root` is the finish line at the top.
- **Find `output.url`.** Its arrows go only to `local.dns_label` and `var.portal_base_url`, never to a resource. That's why the plan above already showed the full `url`, while `fqdn` and `resource_id` said `(known after apply)`: those two wait for the container group, and a value that comes from a resource can't be known until the resource exists.
- **It's not a numbered list.** Anything whose arrows all point at finished work starts straight away, in parallel with anything else that's ready. `destroy` follows the arrows in reverse. You'll see both in Lab 10.

Then delete the file, so it doesn't show up in `git status` later in this lab:

```sh
rm graph.dot
```

## 4. Open your site

```sh
terraform output url
```

Two ways to open it:

- Open the link the `url` output shows, **or**
- in the portal, go to **Container instances**, find `ci-hello-dev` and click **Browse**.

You should see a dark blue page saying **Hello from Dojo Cloud!**, with pills `owner: student01` and `image: dojo/hello:1.0`. That is a real container, started by your `apply`.

If the link from the terminal doesn't open on your setup, use **Browse** in the portal: it always points at the right place.

The `fqdn` output (`hello-dev-student01.canadacentral.dojo-cloud.test`) is the address a real cloud would give the container. It isn't a real internet name in this lab, so you can't type it in a browser; the portal's **Browse** is the clickable route.

## 5. Explore in the portal

Click `ci-hello-dev` in **Container instances**:

- **Overview** shows resource group, location, FQDN, IP, size (0.25 vCPU / 0.125 GB), image, DNS label and the full **Resource ID**. It's the same ID printed in your terminal.
- **Tags** shows `owner`, `env` and `managed_by` from `locals.tf`.
- **JSON view** is the raw API representation, the thing the provider actually receives.
- **Logs** shows what the container printed: `dojo/hello:1.0 starting for owner 'student01' - listening on :80`.

Then open **Activity log**. Two rows, both by you:

```text
Create/Update resource group        Succeeded   rg-hello-dev-cac
Create/Update container group       Succeeded   rg-hello-dev-cac / ci-hello-dev
```

Every change to your subscription lands here, whether OpenTofu or a person made it. Remember that for Lab 7.

## 6. Outputs, state, and "nothing to do"

```sh
terraform output
terraform state list
terraform plan
```

`terraform output` prints the same three outputs as at the end of `apply`, so you never need to scroll back for them. `terraform state list` prints:

```text
azurerm_container_group.hello
azurerm_resource_group.main
```

and the plan:

```text
azurerm_resource_group.main: Refreshing state... [id=/subscriptions/260eb175-...]
azurerm_container_group.hello: Refreshing state... [id=/subscriptions/260eb175-...]

No changes. Your infrastructure matches the configuration.
```

Now that state exists, `plan` **does** ask the cloud ("refreshing"): it compares your config, your state, and what is really there. All three agree.

```sh
git status --short
```

This prints nothing: `terraform.tfstate` and `.terraform/` are in `.gitignore`, and you haven't edited any tracked file.

**Leave everything running.** Labs 6 to 9 build on it.

## What just happened

`apply` sent two requests to the cloud API (one per resource), the cloud checked them against its **policy** (they passed), started a container, and returned the IDs. OpenTofu saved everything it learned in `terraform.tfstate`. The portal, the site and the state file are three views of the same thing.

## Check yourself

1. Why was the resource group created before the container group? *(the container group refers to the resource group's name, so it depends on it)*
2. Why does the second `plan` say "Refreshing state" but the first one didn't? *(there was no state to refresh the first time)*
3. Where would you look to see who created a resource and when? *(the portal's Activity log)*

## Troubleshooting

| You see | Cause / fix |
| ------- | ----------- |
| `apply` seems stuck on "Still creating..." | Normal: the resource group takes ~20 s and the container group ~13 s. Give it a full minute. |
| The portal doesn't show the new resource yet | It refreshes every ~3 seconds. Click **Refresh now**. |
| `Error: ... DnsNameLabelInUse` | Someone else already uses that site name. Sites are named `<workload>-<env>-<owner>`; check `TF_VAR_owner` is your own username (`echo $TF_VAR_owner`). |
| The `url` link doesn't load | Use **Browse** in the portal. From the terminal you can also check the site directly: `curl -s http://cloud-api:8080/cloud/site/hello-dev-$TF_VAR_owner/ \| grep '<h1>'` prints `<h1>Hello from Dojo Cloud!</h1>`. |
| You typed `terraform apply` and pressed Enter but nothing happens | It's waiting for your answer. Type `yes`. |

**Next:** [lab6.md](lab6.md)
