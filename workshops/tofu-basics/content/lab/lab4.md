# Lab 4 — Meet Dojo Cloud

**Goal:** open the cloud's web portal, see your (empty) subscription, find out how your terminal is connected to it, and run `init` for a real cloud provider. Nothing is created yet.

Track A ran entirely inside your terminal. Track B talks to **Dojo Cloud**, a practice cloud that works like Microsoft Azure: subscriptions, resource groups, container instances, tags, policy, quotas. It is an Azure-*inspired* training environment (not affiliated with Microsoft), but the provider you will use is the real `azurerm` provider and the HCL you write is genuine Azure HCL. Everything you learn transfers.

All commands run in the repo you cloned in Lab 0 (the top level of it, **not** `sandbox/`):

```sh
cd ~/lab/tofu-basics
```

---

## 1. Open the portal

Go back to the landing page and click the **Dojo Cloud** card. (Do not type a portal address by hand: use the card.) Keep the portal open in its own browser tab for the rest of the session.

On **Home** you should see:

- your **subscription**: named after your username, with a long **Subscription ID**
- **Quota: 0 / 2**, meaning 0 of the 2 container groups you are allowed
- **0 resource groups**, **0 container instances**, and the text "Nothing here yet"

Click through the left menu: **Resource groups**, **All resources**, **Container instances**, **Activity log**. All empty. **Class view** shows what everyone else has deployed (read-only).

The portal uses the same words as Azure:

| Word | What it is here |
| ---- | --------------- |
| **Subscription** | Your private slice of the cloud. Nobody else can touch yours. |
| **Resource group** | A folder that holds related resources. Every resource lives in one. |
| **Container instance** | A running container, like Azure Container Instances (its Azure name is *container group*, and OpenTofu calls it `azurerm_container_group`). |
| **Region / location** | Where it runs. Only `canadacentral` and `canadaeast` are allowed. |
| **Tags** | Labels (`owner`, `env`, ...) on resources. Two are **required**. |
| **Policy** | Rules the cloud enforces on every request (Lab 6). |
| **Quota** | A hard limit: 2 container groups per subscription (Lab 9). |
| **Activity log** | A record of every create/update/delete, and who did it. |

The portal refreshes itself about every 3 seconds, so leave it open and watch it while you work.

## 2. Look at the Track B files

```sh
ls -la
```

Expected (abridged; sizes and dates will differ):

```text
.gitignore
.terraform.lock.hcl
README.md
locals.tf
main.tf
outputs.tf
providers.tf
sandbox
terraform.tfvars
variables.tf
versions.tf
```

Same idea as `sandbox/`, but now split the way real repos are split:

| File | What it is |
| ---- | ---------- |
| `versions.tf` | Which OpenTofu and which provider (`hashicorp/azurerm`, `~> 5.6`) are required. |
| `providers.tf` | Provider settings. Note there are **no credentials** in it. |
| `variables.tf` | Inputs: region, workload name, environment, message, image version. Includes `validation` rules. |
| `locals.tf` | Names and tags computed once (Cloud Adoption Framework style: `rg-hello-dev-cac`). |
| `main.tf` | The resources: a resource group and a container group. |
| `outputs.tf` | What gets printed after `apply`. |
| `terraform.tfvars` | Your values for the variables. |
| `.terraform.lock.hcl` | The exact provider version and checksums. **Committed.** |

Read the two smallest ones:

```sh
cat versions.tf providers.tf
```

`providers.tf` is just `provider "azurerm" { features {} }`. There is no username, password or address. So how does OpenTofu know which cloud to talk to, and who you are?

## 3. Your credentials are in your environment

```sh
env | grep -E '^(ARM_|TF_VAR_)' | grep -v SECRET | sort
```

Expected (your IDs will differ):

```text
ARM_CLIENT_ID=76c35579-ab26-5f1c-92e1-596dcae444e8
ARM_METADATA_HOSTNAME=management.dojo.cloud
ARM_RESOURCE_PROVIDER_REGISTRATIONS=none
ARM_SUBSCRIPTION_ID=260eb175-2be3-5b4e-a481-d14ff2e938cf
ARM_TENANT_ID=5f2c1a40-7d3e-4b6a-9c11-3a7e2d9b8f10
ARM_USE_CLI=false
TF_VAR_owner=student01
TF_VAR_portal_base_url=http://localhost/cloud
```

(The last line starts with your class's address, so it will look different on the real server.)

These are the standard names the `azurerm` provider reads: a tenant, a subscription, and a **service principal** (`ARM_CLIENT_ID` plus a secret that the `grep -v SECRET` hid; it is set too, and it is yours alone, so never paste it anywhere). This is exactly how a CI pipeline logs in to real Azure. Keeping credentials in the environment instead of in `.tf` files is what keeps them out of git.

Compare `ARM_SUBSCRIPTION_ID` with the Subscription ID on the portal Home page. Same value.

`TF_VAR_owner` shows another rule: OpenTofu turns any environment variable named `TF_VAR_<name>` into the input variable `var.<name>`. `variables.tf` declares `owner` with **no default**, because your terminal supplies it.

## 4. The cloud is just an API

`ARM_METADATA_HOSTNAME` is the address of Dojo Cloud's front door. Ask it who it is:

```sh
curl -s "https://management.dojo.cloud/metadata/endpoints?api-version=2022-09-01" | python3 -m json.tool | head -4
```

Expected:

```text
{
    "name": "dojocloud",
    "resourceManager": "https://management.dojo.cloud/",
    "microsoftGraphResourceId": "https://graph.dojo.cloud/",
```

The provider fetches this document first, then asks `login.dojo.cloud` for a token, then sends plain HTTPS requests ("create this resource group", "create this container group") to `management.dojo.cloud`. In real Azure the same calls go to `management.azure.com`. **A provider is a translator from HCL to a cloud's API. That is all.**

## 5. `init`: install the provider

```sh
terraform init
```

Expected:

```text
Initializing the backend...

Initializing provider plugins...
- Reusing previous version of hashicorp/azurerm from the dependency lock file
- Installing hashicorp/azurerm v5.6.0...
- Installed hashicorp/azurerm v5.6.0 (unauthenticated)

OpenTofu has been successfully initialized!
```

(Followed by the usual "You may now begin working with OpenTofu" advice, trimmed here.) It takes about 2 seconds.

**What just happened:** `init` read `versions.tf` (`~> 5.6` means "5.6 or any newer 5.x") and `.terraform.lock.hcl` (which pins **exactly** `5.6.0`), and installed that version into `.terraform/`. The lab network has no internet, so it came from a local copy, the same trick as in Track A. "Unauthenticated" only means OpenTofu could not check the publisher's signature for a local copy; it still verifies the files against the checksums in the lock file.

Look at the lock file and at what `init` created:

```sh
head -8 .terraform.lock.hcl
ls -la .terraform/providers/registry.opentofu.org/hashicorp/azurerm/5.6.0/
```

```text
# This file is maintained automatically by "tofu init".
# Manual edits may be lost in future updates.

provider "registry.opentofu.org/hashicorp/azurerm" {
  version     = "5.6.0"
  constraints = "~> 5.6"
  hashes = [
    "h1:+9/JWbUEP2uDjLA4wEGTOcC/WdK8Tv4cOk+YqLu4y6M=",
```

The `.terraform/providers/...` folder holds only a link to the shared copy (`linux_amd64 -> /opt/tofu-providers/...`), which is why your `.terraform` is tiny even though the provider itself is over 200 MB.

Finally:

```sh
terraform validate
```

Expected: `Success! The configuration is valid.`

You are connected, and nothing exists yet. Next you will create something.

## Check yourself

1. Where do your cloud credentials come from, and why aren't they in `providers.tf`? *(environment variables, `ARM_*`; secrets never go in files that are committed to git)*
2. What does `~> 5.6` in `versions.tf` allow, and what does `.terraform.lock.hcl` then pin? *(any 5.x from 5.6 up; the lock pins one exact version and its checksums so everyone gets identical code)*
3. What is a provider, in one sentence? *(a plugin that translates your HCL into API calls for one platform)*

## Troubleshooting

| You see | Cause / fix |
| ------- | ----------- |
| `Error: Required plugins are not installed ... run: tofu init` | You skipped `init`, or you are in the wrong folder. `cd ~/lab/tofu-basics` and run `terraform init`. (The message says `tofu` because `terraform` **is** OpenTofu.) |
| `env` shows no `ARM_` lines | Credentials are attached when a shell starts. Open a new terminal tab and try again. Still nothing? Tell the facilitator. |
| `curl: (60) SSL certificate problem` | Your shell doesn't have the cloud's certificate. Open a new terminal tab (same fix as above). |
| The portal card or page does not open | Go back to the landing page and click the **Dojo Cloud** card again. Don't type addresses by hand. |

**Next:** [lab5.md](lab5.md)
