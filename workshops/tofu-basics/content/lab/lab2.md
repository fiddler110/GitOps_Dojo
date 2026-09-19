# Lab 2 — Change a value and read the plan

**Goal:** edit an input, predict what OpenTofu will do, then confirm with `plan`. Also: outputs, state, and idempotency.

```sh
cd ~/lab/tofu-basics/sandbox
```

---

## 1. Idempotency — apply twice, change once

```sh
terraform plan
```

Expected:

```text
No changes. Your infrastructure matches the configuration.
```

The desired state matches reality, so there is nothing to do. This is **idempotency**: running the same config repeatedly is safe.

## 2. Change an input

Open `terraform.tfvars` and change `learner` to your own first name (lowercase):

```sh
nano terraform.tfvars
```

```hcl
learner  = "ada"
greeting = "Hello from OpenTofu!"
```

Save with `Ctrl+O`, `Enter`, `Ctrl+X`. **Before** you run anything: which resources use `var.learner`? *(Look in `main.tf` — two of them.)*

## 3. Plan it

```sh
terraform plan
```

Expected (abridged):

```text
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

Whether a change is `~` or `-/+` is decided by the **provider**, per attribute. This is why you always read the plan — a "small" edit can mean destroying something.

Note that `random_pet.nickname` isn't in the plan. Its name (`deep-wildcat`) is remembered in state and stays stable.

## 4. Apply, then look around

```sh
terraform apply
```

Type `yes`. Then:

```sh
cat out/hello.txt        # the new text
terraform output         # values from outputs.tf
terraform output nickname
terraform state list     # everything OpenTofu is tracking
terraform show           # full detail of what's in state
```

`terraform state list` prints one line per resource: `resource_type.name`. That is the address you use with `-replace` and other targeted commands.

## 5. Force a replacement

Sometimes a resource must be rebuilt even though its config didn't change:

```sh
terraform plan -replace=random_pet.nickname
```

The pet is replaced, so its `id` changes, and because the file *uses* the pet's id, the file is replaced too. That chain is the dependency graph at work. You don't have to apply this one.

## 6. Break a rule on purpose

`variables.tf` has a `validation` block on `pet_words`. Try to violate it without editing any file:

```sh
terraform plan -var pet_words=9
```

Expected:

```text
Error: Invalid value for variable
  var.pet_words is 9
pet_words must be between 2 and 4.
```

Validation rules stop bad input before it reaches anything real. You'll see the same idea used for cloud policies later.

## Check yourself

1. What is the difference between `~` and `-/+`? *(in-place edit vs. destroy-and-recreate)*
2. Why wasn't `random_pet.nickname` recreated when you changed `learner`? *(nothing it depends on changed, and its value is stored in state)*
3. Where does OpenTofu remember what it created? *(state — `terraform.tfstate`)*

**Next:** [lab3.md](lab3.md)
