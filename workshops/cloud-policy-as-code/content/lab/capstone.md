# Capstone: a new rule, start to finish

**Time:** about 45 minutes (one slow apply of about 3.5 minutes). **Goal:** do everything from Labs 3-12 on a rule nobody has given you the steps for. This page is a brief, not a walkthrough.

> **Starting here?** Run `lab-prep 12` to bring your clone to the end of Lab 12. It is safe to run if you did the earlier labs, and takes about 3.5 minutes.

```bash
cd ~/lab/cloud-policy-as-code
git checkout main && git pull
```

---

## The brief

Your platform team has a new requirement from the release manager:

> **Container groups tagged `env=prod` must run `dojo/hello:2.0`.**
> Other environments may keep running `dojo/hello:1.0` or `dojo/hello:2.0`, as the platform's guardrails already allow.

The `1.0` image has a known fault and "prod" is where it must never appear. The rule has to hold three ways: **tested** in Rego, **checked** on every pull request, and **enforced** by the cloud. And it has to arrive the way every change arrives: through a reviewed pull request, merged and applied by the pipeline.

## What you must deliver

1. **Rego rule with tests.** A new rule in `policy/rego/` (a file of its own) that denies a planned container group tagged `env=prod` if any container uses an image other than `dojo/hello:2.0`. Tests cover at least: a prod group on 2.0 passes, a prod group on 1.0 is denied, a dev group on 1.0 passes, and a delete is ignored.
2. **Cloud definition and assignment.** A policy definition (rule JSON in `policy/cloud/rules/`) and an assignment at subscription scope in `policy/cloud/main.tf`, with a `nonComplianceMessage` that tells the developer what to do.
3. **A pull request** on your fork, with a description a reviewer could act on.
4. **Green CI, merged, and applied.** The **Policy check** is green, the pull request is merged and the **Apply** run on `main` is green.
5. **A refused resource.** Show, with real output, that a non-compliant resource is refused. That means a prod container group on `dojo/hello:1.0` is denied by the cloud, and you can name the assignment that denied it.

## Acceptance criteria

Tick every box before you call it done.

- [ ] `opa test policy/rego --ignore fixtures -v` passes, and your new file has at least four tests, at least one of which must fail if the rule were deleted.
- [ ] `conftest test --policy policy/rego --namespace main` on a plan with a prod group on 1.0 **fails** with a message naming the resource.
- [ ] The Policy blade lists your new assignment, with effect `deny`.
- [ ] A dev container group on 1.0 is **still allowed** (the rule is narrow), and a prod group on 2.0 is allowed.
- [ ] A prod group on `dojo/hello:1.0` is refused with `RequestDisallowedByPolicy` naming your assignment and showing your message.
- [ ] The **Drift** workflow is green after the merge.
- [ ] No test resource is left in the cloud, and `git status` is clean on `main`.

Remember the platform limits: at most 2 container groups per subscription (you already have 1), names must start `ci-`, and only `dojo/hello` images exist. Your test resources can live in your own scratch folder as in Lab 1, so they cannot touch the app.

## Hints

Try each step yourself for a few minutes before opening the next hint.

<details>
<summary>Hint 1: where to start</summary>

Follow the order of the labs: write the **Rego tests first** (Lab 10), then the rule (Lab 9). Build your test inputs with a helper like the `rc(loc)` one in `regions_test.rego`, but giving it a tag and a list of containers. In a plan, an `azurerm_container_group` has its containers in `change.after.container` (a list) and its tags in `change.after.tags`.

For the cloud side, copy the shape of `allowed-images.json` (Lab 5). You need to combine three conditions with `allOf`: the type, the `env` tag, and the image. The tag is the field `tags['env']`. Put the effect in as a parameter if you like, as in Lab 3, so you can try `audit` first.
</details>

<details>
<summary>Hint 2: the shape of the rule</summary>

The Rego rule has this skeleton (fill in the three blanks, then write a test for each branch):

```rego
deny contains msg if {
	some rc in input.resource_changes
	rc.type == "azurerm_container_group"
	some action in rc.change.actions
	action in {"create", "update"}
	rc.change.after.tags.env == ___
	some c in rc.change.after.container
	c.image != ___
	msg := sprintf("%s runs %s in prod; prod must run %s", [rc.address, c.image, ___])
}
```

The cloud rule's `if` has this skeleton. The alias is the same one the allowed-images rule uses, and a `[*]` alias is checked for every container:

```json
{
  "if": {
    "allOf": [
      { "field": "type", "equals": "Microsoft.ContainerInstance/containerGroups" },
      { "field": "tags['env']", "equals": "prod" },
      { "not": { "field": "Microsoft.ContainerInstance/containerGroups/containers[*].image", "equals": "dojo/hello:2.0" } }
    ]
  },
  "then": { "effect": "deny" }
}
```

Use `tofu fmt` and `opa fmt` before committing. The assignment's non-compliance message goes in the `non_compliance_message { content = "..." }` block of the `azurerm_subscription_policy_assignment`.
</details>

<details>
<summary>Hint 3: the traps</summary>

- **Slow apply.** Creating the definition and the assignment takes about 100 seconds, in parallel. Do not chain them with `depends_on`; let the pipeline do it while you write your pull request description. Applying from your terminal as well as merging will make the pipeline's apply a no-op, which is fine, but do not let both run at once.
- **Test with a scratch folder.** Copy `providers.tf`, `versions.tf` and `variables.tf` into `~/lab/scratch` as in Lab 1, add an `azurerm_resource_group` and a container group named `ci-${var.owner}-prod` with `tags = { owner = var.owner, env = "prod", costCenter = "cc-1001" }` and `image = "dojo/hello:1.0"`. All other guardrails (cpu, memory, port 80, owner and env tags, costCenter) must still be satisfied, or you will be refused for the wrong reason and prove nothing. Read the 403 and check it names *your* assignment.
- **Prove it is narrow.** Change `env` to `dev` and apply again: it must succeed. Then destroy.
- **A rule that looks right but is not.** Test the case `env = "production"` and `env = "Prod"`. Decide deliberately what the rule should do about them, write the decision down in a test, and mention it in your pull request.
- **Every `deny` rule in the package runs in your tests.** `count(deny)` counts violations from `costcenter.rego` and `regions.rego` too, so a test input with no `costCenter` tag fails for the wrong reason. Build your helper's input to satisfy the other rules, or test for your own message with `deny["..."]`.
- **Policy objects have no tags.** Your Rego rule is checked against the plans of `policy/cloud` too, where a policy object has no `container` list. A rule that raises an error on a missing field fails the whole check; one that simply does not match is fine.
</details>

## When you are done

Press **Run workflow** on the **Drift** workflow once more, and read the result. Then ask yourself the two questions a reviewer would: *Is this rule too narrow?* (what slips through?) and *Is it too strict?* (what would a developer be annoyed by?) Both answers go in the pull request description.

You have written a policy, tested it, shifted it left, gated it behind review, applied it by pipeline, proved it works, and checked it for drift. That is the whole practice.
