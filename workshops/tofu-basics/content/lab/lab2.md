# Lab 2 — Change a value and read the plan

**Goal:** edit an input, predict what OpenTofu will do, then confirm with `plan`. Also: outputs, state, and idempotency.

> **Starting here?** This lab needs your clone, with the sandbox applied (Lab 1). Run `dojo prep 2` to set that up; it's safe to run even if you did the earlier labs.

```sh
cd ~/lab/tofu-basics/sandbox
```

---

## 1. Idempotency — apply twice, change once

**Idempotency** means running the same config repeatedly is safe: if the desired state already matches reality, OpenTofu has nothing to do.

**Your turn:** you applied the sandbox last lab and changed nothing since. Before you run it, predict what `plan` will say.

```sh
terraform plan
```

<!-- dojo-reveal: Results of plan -->

Expected:

```text
No changes. Your infrastructure matches the configuration.
```

The desired state matches reality, so there is nothing to do.

<!-- /dojo-reveal -->

## 2. Change an input

Inputs live in `terraform.tfvars`: the values you set for the variables declared in `variables.tf`. Changing one is the everyday way to change infrastructure, and the next step is to read what that change would do before you do it.

Open `terraform.tfvars` in your editor and change `learner` to your own first name (lowercase), so the file reads:

```terraform
learner  = "ada"
greeting = "Hello from OpenTofu!"
```

**Prefer the terminal?**

```sh
nano terraform.tfvars
```

Save with `Ctrl+O`, `Enter`, `Ctrl+X`.

**Your turn:** before you run anything, predict which resources use `var.learner`. Look in `main.tf`.

<!-- dojo-reveal: Answer -->

- Two of them.

<!-- /dojo-reveal -->

## 3. Plan it

Whether a change is applied in place (`~`) or by destroying and recreating (`-/+`) is decided by the **provider**, per attribute. This is why you always read the plan: a "small" edit can mean destroying something.

```text
terraform plan
```

**Your turn:** before you run it, predict: will both resources change the same way? Then run it.

```sh
terraform plan
```

<!-- dojo-reveal: Results of plan with the new name -->

Expected (abridged):

```terraform
  ~ update in-place (current -> planned)
-/+ destroy and then create replacement

  # local_file.greeting must be replaced
-/+ resource "local_file" "greeting" {
      ~ content = <<-EOT # forces replacement
            Hello from OpenTofu!
          - From: student (deep-wildcat)
          + From: ada (deep-wildcat)
        EOT
      ...
    }

  # terraform_data.note will be updated in-place
  ~ resource "terraform_data" "note" {
      ~ input  = "Deployed by student" -> "Deployed by ada"
      ...
    }

Plan: 1 to add, 1 to change, 1 to destroy.
```

**One edit, two different outcomes:**

- `terraform_data.note` can be **updated in place** (`~`) — the provider can change `input` without recreating anything.
- `local_file.greeting` says **`# forces replacement`** — the provider can't edit a file's content in place, so it deletes and recreates it (`-/+`).
- Note that `random_pet.nickname` isn't in the plan. Its name (`deep-wildcat`) is remembered in state and stays stable.

<!-- /dojo-reveal -->

## 4. Apply, then look around

After an apply, a handful of read-only commands let you look around. `terraform output` prints the values from `outputs.tf`. `terraform state list` prints one line per tracked resource, `resource_type.name`; that is the address you use with `-replace` and other targeted commands. `terraform show` prints the full detail held in state.

```text
terraform output [name]
terraform state list
terraform show
```

**Your turn:** apply, type `yes`, then look around. Predict what `cat out/hello.txt` will say now.

```sh
terraform apply
```

```sh
cat out/hello.txt        # the new text
terraform output         # values from outputs.tf
terraform output nickname
terraform state list     # everything OpenTofu is tracking
terraform show           # full detail of what's in state
```

<!-- dojo-reveal: Results of looking around -->

- `hello.txt` shows `From: ada (...)`, your new name.
- `state list` shows the three resources by address.

<!-- /dojo-reveal -->

## 5. Force a replacement

Sometimes a resource must be rebuilt even though its config didn't change. `-replace=<address>` tells OpenTofu to plan a rebuild of that one resource, using the address from `state list`.

```text
terraform plan -replace=<address>
```

**Your turn:** before you run it, predict: if the pet is replaced, what else must be?

```sh
terraform plan -replace=random_pet.nickname
```

<!-- dojo-reveal: Results of plan -replace -->

- The pet is replaced, so its `id` changes, and because the file *uses* the pet's id, the file is replaced too. That chain is the dependency graph at work.
- You don't have to apply this one.

<!-- /dojo-reveal -->

## 6. Break a rule on purpose

A variable can carry a `validation` block, a rule that rejects bad input before it reaches anything real. `-var name=value` sets a variable for one run without editing any file.

```text
terraform plan -var <name>=<value>
```

**Your turn:** `variables.tf` has a `validation` block on `pet_words`. Before you run this, predict what OpenTofu will do with `9`.

```sh
terraform plan -var pet_words=9
```

<!-- dojo-reveal: Results of the validation failure -->

Expected:

```text
Error: Invalid value for variable
  var.pet_words is 9
pet_words must be between 2 and 4.
```

<!-- /dojo-reveal -->

You'll see the same idea used for cloud policies later.

## Check yourself

1. What is the difference between `~` and `-/+`?
2. Why wasn't `random_pet.nickname` recreated when you changed `learner`?
3. Where does OpenTofu remember what it created?

<!-- dojo-reveal: Show the answer -->

1. `~` is an in-place edit; `-/+` is destroy-and-recreate.
2. Nothing it depends on changed, and its value is stored in state.
3. In state, `terraform.tfstate`.

<!-- /dojo-reveal -->

**Next:** [lab3.md](lab3.md)
