# Lab 9 — Scale it: `for_each` and quotas

**Goal:** create several similar resources from one block with `for_each`, then run into a **quota**, and learn why the plan couldn't warn you.

> **Starting here?** This lab needs hello deployed to Dojo Cloud (Lab 5). Run `lab-prep 9` to set that up; it's safe to run even if you did the earlier labs.

```sh
cd ~/lab/tofu-basics
```

Your Lab 5 `hello` container is still running, and the portal's Home page says **Quota: 1 / 2**. Remember that number.

---

## 1. Why `for_each`?

You could copy-paste the `azurerm_container_group` block for every extra site. Copy-paste means every future change (a new tag, a new image) has to be made N times. `for_each` says: *make one copy of this block per item in a set.* OpenTofu also has `count`, which numbers copies (`[0]`, `[1]`); `for_each` names them by key (`["blue"]`), which is safer: remove `"blue"` from the middle of a list and only `blue` disappears.

## 2. Add two more sites

Append a second container group resource to `main.tf`. It's identical to `hello` except for its name, its site name (the DNS label), and the message, which all include the key:

```sh
cat >> main.tf <<'HCL'

# Lab 9: more sites, built from ONE block. for_each makes one copy per name.
resource "azurerm_container_group" "extra" {
  for_each = toset(["blue", "green"])

  name                = "${local.ci_name}-${each.key}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  os_type             = "Linux"
  ip_address_type     = "Public"
  dns_name_label      = "${local.dns_label}-${each.key}"

  exposed_port {
    port     = 80
    protocol = "TCP"
  }

  container {
    name   = "hello"
    image  = "dojo/hello:${var.image_tag}"
    cpu    = 0.25
    memory = 0.125

    ports {
      port     = 80
      protocol = "TCP"
    }

    environment_variables = {
      MESSAGE = "${var.message} (${each.key})"
      OWNER   = var.owner
    }
  }

  tags = local.tags
}
HCL
```

Check it and preview:

```sh
terraform fmt -check && echo fmt-ok
terraform validate
terraform plan -no-color | grep -E '^  # |^Plan:'
```

(`-no-color` matters here: without it OpenTofu wraps the lines in colour codes and `grep` finds nothing.) Expected:

```text
fmt-ok
Success! The configuration is valid.
  # azurerm_container_group.extra["blue"] will be created
  # azurerm_container_group.extra["green"] will be created
Plan: 2 to add, 0 to change, 0 to destroy.
```

Two new resources, addressed `extra["blue"]` and `extra["green"]`. Your existing `hello` is untouched. The plan is happy.

Before you apply, do the sums. Your quota is **2 container groups**. You have 1. This plan adds 2.

## 3. Apply and hit the limit

```sh
terraform apply
```

Type `yes`:

```text
azurerm_container_group.extra["green"]: Creating...
azurerm_container_group.extra["blue"]: Creating...
azurerm_container_group.extra["blue"]: Still creating... [10s elapsed]
azurerm_container_group.extra["blue"]: Creation complete after 13s [id=/subscriptions/260eb175-2be3-5b4e-a481-d14ff2e938cf/resourceGroups/rg-hello-dev-cac/providers/Microsoft.ContainerInstance/containerGroups/ci-hello-dev-blue]

Error: creating Container Group (Subscription: "260eb175-2be3-5b4e-a481-d14ff2e938cf"
Resource Group Name: "rg-hello-dev-cac"
Container Group Name: "ci-hello-dev-green"): performing ContainerGroupsCreateOrUpdate: unexpected status 409 (409 Conflict) with error: QuotaExceeded: Subscription quota reached: at most 2 container groups are allowed. Destroy one before creating another.

  with azurerm_container_group.extra["green"],
  on main.tf line 47, in resource "azurerm_container_group" "extra":
  47: resource "azurerm_container_group" "extra" {
```

`QuotaExceeded`, status `409`. Both were requested at the same moment; **whichever request reaches the cloud first wins.** In this run `blue` won and `green` was refused; on your screen it may be the other way round (then the error names `ci-hello-dev-blue`). It took about 15 seconds.

**A quota is a hard cap on how much you may have, and no plan can predict it.** `plan` computes what to *ask for*; whether the cloud will say yes depends on what else exists in the subscription, including things outside your code. Real clouds have quotas everywhere (vCPUs per region, public IPs, storage accounts), and the way you meet them is exactly this error, at `apply`.

## 4. See where you stand

The apply half-succeeded. OpenTofu recorded what did get created:

```sh
terraform state list
```

```text
azurerm_container_group.extra["blue"]
azurerm_container_group.hello
azurerm_resource_group.main
```

(Yours might list `["green"]` instead of `["blue"]`.) In the portal, **Container instances** shows two (your `hello` and one extra), Home shows **Quota: 2 / 2**, and you can **Browse** both sites. Look at the extra one: its message ends with `(blue)`.

## 5. Fix the code to match reality

You can't have three, so make the code say what you can have. Edit the `for_each` line in `main.tf` so it lists **only the site that exists** (the one in your `state list`). If yours is `blue`:

```sh
sed -i 's/for_each = toset(\["blue", "green"\])/for_each = toset(["blue"])/' main.tf
grep -n 'for_each =' main.tf
terraform plan
```

(If yours is `green`, use `"green"` instead.) Expected:

```text
48:  for_each = toset(["blue"])
...
No changes. Your infrastructure matches the configuration.
```

Code, state and cloud agree again, and the quota is fully used. If you wanted a third site you'd have to give one back first: destroy something, or ask for more quota.

## What just happened

- `for_each` turned one block into several **instances**, each with a key you can see in the address, `extra["blue"]`.
- The cloud enforced a limit that OpenTofu couldn't know about in advance.
- A failed `apply` is **not** a rollback: what succeeded stays created (and in state). That's why you *read the state* afterwards and made the code match.

## Check yourself

1. Why did `terraform plan` say `2 to add` when you could only afford one more? *(plan doesn't know the cloud's quotas; they are enforced when the request is sent)*
2. If you delete `"green"` from the set, what happens to `extra["blue"]`? *(nothing: instances are tracked by key, so only the removed key is destroyed)*
3. After the failed apply, which command tells you what was actually created? *(`terraform state list`, plus the portal)*

## Troubleshooting

| You see | Cause / fix |
| ------- | ----------- |
| `QuotaExceeded` | You already have the maximum of 2 container groups. This is the lesson. Destroy one, or reduce your `for_each`, as in section 5. |
| `DnsNameLabelInUse` | Another site already uses that name. Site names are `<workload>-<env>-<owner>-<key>`; make sure `TF_VAR_owner` is your own username. |
| `Invalid for_each argument` or a syntax error | A typo in the pasted block. `terraform validate` names the line. If it's a mess, `git checkout main.tf` and paste again. |
| Portal shows fewer or more than you expect | It refreshes every ~3 s; click **Refresh now**. `terraform state list` is the OpenTofu view of the truth. |
| `terraform plan` wants to destroy `extra["blue"]` | Your state has `blue` but your `for_each` no longer does. That's expected; apply removes it (which frees up quota). |

**Next:** [lab10.md](lab10.md)
