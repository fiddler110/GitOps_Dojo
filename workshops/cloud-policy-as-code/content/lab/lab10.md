# Lab 10: Testing policies, a rule you cannot test is a rule you cannot trust

**Time:** about 25 minutes. **Goal:** run the unit tests for your Rego, write a test that fails because it found a real bug, fix the bug, and see why policy deserves tests as much as application code.

> **Starting here?** This lab needs your clone and the policy from Labs 3-8 (Lab 9 left nothing behind). Run `dojo prep 10` to set that up (the policy apply takes about 3.5 minutes). It is safe to run even if you did the earlier labs.

```sh
cd ~/lab/cloud-policy-as-code
```

---

## Why policy needs tests

A policy has exactly two ways to be wrong, and both are silent:

- **Too loose:** it lets something through that it should have refused. Nobody notices until the bad resource is live.
- **Too strict:** it refuses things that are fine. People notice at once, then ask for an exemption or switch the rule off.

Neither shows up as an error. A rule that *runs* is not a rule that is *right*. The fix is the one you already apply to code: examples. For each rule, a handful of inputs with the answer you expect, run on every change. OPA has a test runner built in, so the tests are written in Rego too.

## 1. Run the tests that exist

`opa test` runs every rule whose name starts with `test_`. `-v` lists every test rather than just failures. `--ignore fixtures` matters: the `fixtures/` folder holds sample plans as JSON, and OPA tries to load every file as data, which clashes with the other documents, giving `merge error`. Try it without the flag if you are curious.

```text
opa test <dir> --ignore <pattern> -v
```

**Your turn:** predict how many tests pass.

```sh
opa test policy/rego --ignore fixtures -v
```

<!-- dojo-reveal: Results of opa test -->

```text
rego/costcenter_test.rego:9:
data.main.test_good_plan_passes: PASS (1.2ms)
...
data.main.test_canada_allowed: PASS (2.6ms)
data.main.test_other_region_denied: PASS (2.8ms)
--------------------------------------------------------------------------------
PASS: 8/8
```

(Your times and the order will differ.)

<!-- /dojo-reveal -->

## 2. Read a test

This is `policy/rego/regions_test.rego`:

```rego
package main

import rego.v1

rc(loc) := {"resource_changes": [{
	"address": "azurerm_resource_group.x",
	"change": {"actions": ["create"], "after": {"location": loc, "tags": {"costCenter": "1"}}},
}]}

test_canada_allowed if {
	count(deny) == 0 with input as rc("canadaeast")
}

test_other_region_denied if {
	count(deny) == 1 with input as rc("eastus")
}
```

- A rule whose name starts with **`test_`** is a test. It passes if its body is true.
- `rc(loc)` is a **helper function** that builds a minimal plan with one resource in the region you pass. A test needs only the fields the rule reads, not a real plan.
- **`with input as ...`** replaces `input` for this one expression: "evaluate `deny` as if the plan were this". It is how a test feeds an example to a rule.
- `count(deny) == 0` means "no violations"; `== 1` means "exactly one".

Good tests come in pairs: something that must pass and something that must fail. A suite with only passing examples proves nothing, because a rule that never denies anything passes it.

**Your turn:** open the test file in your editor, or print it.

```sh
cat policy/rego/regions_test.rego
```

## 3. Look at the rule under test

This is the rule, `policy/rego/regions.rego`:

```rego
package main

import rego.v1

allowed_regions := {"canadacentral", "canadaeast"}

deny contains msg if {
	some rc in input.resource_changes
	some action in rc.change.actions
	action in {"create", "update"}
	loc := rc.change.after.location
	loc != "" # only things that have a region: policy objects come through with ""
	not startswith(loc, "canada")
	msg := sprintf("%s uses region %s; allowed: %s", [rc.address, loc, concat(", ", sort(allowed_regions))])
}
```

The error message and the `allowed_regions` set both say two regions are allowed. Read the condition. It does not use the set. Someone took a shortcut: "all our regions start with `canada`". The two existing tests pass: `canadaeast` is allowed, `eastus` is refused.

**Check yourself:** Do you see a region that starts with `canada` and is not allowed?

<!-- dojo-reveal: Show the answer -->

`canadawest`: it starts with `canada`, so the rule never denies it, though it is not in the allowed set.

<!-- /dojo-reveal -->

**Your turn:** open the rule in your editor, or print it.

```sh
cat policy/rego/regions.rego
```

## 4. Write the test first

The platform's guardrail allows `canadacentral` and `canadaeast` only. A third Canadian region, `canadawest`, exists in the real world but is **not** allowed here. Writing the test before the fix means you *see it fail*, so you know the test can detect the bug (a test written after the fix might never have been capable of failing).

In your editor, append to `policy/rego/regions_test.rego`:

```rego
test_canadawest_denied if {
	count(deny) == 1 with input as rc("canadawest")
}
```

**Prefer the terminal?**

```sh
cat >> policy/rego/regions_test.rego <<'EOT'

test_canadawest_denied if {
	count(deny) == 1 with input as rc("canadawest")
}
EOT
```

**Your turn:** predict: will the new test pass or fail?

```sh
opa test policy/rego --ignore fixtures
```

<!-- dojo-reveal: Results of opa test -->

```text
rego/regions_test.rego:18:
data.main.test_canadawest_denied: FAIL (1.1ms)
--------------------------------------------------------------------------------
PASS: 8/9
FAIL: 1/9
```

**This failure is the point.** You have a test that describes the behaviour you want, and it proves the rule does not have it: `startswith("canadawest", "canada")` is true, so the rule never denies it. When it turns green after the fix, you know it was the fix.

<!-- /dojo-reveal -->

## 5. Fix the rule

The message and the `allowed_regions` set already name the right regions; only the check disagrees. In your editor, in `policy/rego/regions.rego`, replace the `startswith` line so the rule uses the set that is already there:

```rego
	not loc in allowed_regions
```

`loc in allowed_regions` is true if `loc` is a member of the set; `not` turns that around. The message and the check now come from the same list, so they cannot disagree. `opa fmt --diff` prints nothing when the files are already formatted (`opa fmt -w policy/rego` rewrites them in place).

**Your turn:** run the tests again. Predict the count.

```sh
opa fmt --diff policy/rego
opa test policy/rego --ignore fixtures -v
```

<!-- dojo-reveal: Results of opa test -->

```text
data.main.test_canadawest_denied: PASS (1.5ms)
--------------------------------------------------------------------------------
PASS: 9/9
```

<!-- /dojo-reveal -->

## 6. Test the edges

A bug like this hides at the boundary between "obviously fine" and "obviously wrong". `--coverage` reports which lines of the policy the tests ran; 100 means every line of every rule was exercised at least once. Coverage cannot tell you the tests are *good* (the old suite also covered `regions.rego` fully, and still missed the bug), but low coverage tells you for certain that something is untested.

In your editor, add one more test to `policy/rego/regions_test.rego` that throws a list of awkward values at the rule, using `every`:

```rego
test_near_misses_denied if {
	every loc in ["eastus", "westeurope", "canada", "canadacentral2"] {
		count(deny) == 1 with input as rc(loc)
	}
}
```

**Prefer the terminal?**

```sh
cat >> policy/rego/regions_test.rego <<'EOT'

test_near_misses_denied if {
	every loc in ["eastus", "westeurope", "canada", "canadacentral2"] {
		count(deny) == 1 with input as rc(loc)
	}
}
EOT
```

**Your turn:** predict the coverage number. Then confirm the same rule still works on a real plan from the fixtures (the files the pull request pipeline will check): one should pass and one should fail.

```sh
opa test policy/rego --ignore fixtures --coverage | python3 -c "import sys,json; print(json.load(sys.stdin)['coverage'])"
conftest test --policy policy/rego --namespace main policy/rego/fixtures/plan-good.json
conftest test --policy policy/rego --namespace main policy/rego/fixtures/plan-bad.json
```

<!-- dojo-reveal: Results of the coverage and fixture checks -->

```text
100
```

```text
2 tests, 2 passed, 0 warnings, 0 failures
FAIL - policy/rego/fixtures/plan-bad.json - main - azurerm_resource_group.app is missing the costCenter tag

2 tests, 1 passed, 0 warnings, 1 failure
```

`plan-bad.json` is a cut-down real plan, kept in the repo so the rules are exercised against the real structure of a plan and not only against hand-built examples.

<!-- /dojo-reveal -->

Commit your work. You are on `main` of your fork; the next lab uses a branch and a pull request, and `dojo prep 11` assumes these changes are made.

```sh
git add policy/rego
git commit -m "regions.rego: check the allowed set, not a prefix; test canadawest"
git push origin main
```

## What just happened

- Policy is code, and wrong code is silent. A test suite with a pass **and** a fail case for each rule is how you notice.
- `opa test` runs every `test_` rule; `with input as` feeds each one an example.
- You wrote the failing test first, watched it fail for the right reason, and only then fixed the rule. That order is what makes the test trustworthy.
- The bug was a duplicated truth: the list of regions in a set, and the same list implied by a prefix. Policies are full of these. One source, used everywhere.

## Check yourself

1. Why must a suite include a case that is supposed to be refused?
2. What does `with input as rc("canadawest")` do?
3. Why `--ignore fixtures`?

<!-- dojo-reveal: Show the answers -->

1. A rule that denies nothing passes any suite of "good" examples.
2. It runs the rule as if that were the plan, for that one expression.
3. OPA loads every file in the folder as data; the fixture plans clash with each other.

<!-- /dojo-reveal -->

**Check box.** You are done when all of these hold:

- [ ] `opa test policy/rego --ignore fixtures -v` shows every test passing, including `test_canadawest_denied`.
- [ ] You saw `test_canadawest_denied` fail before you edited `regions.rego`.
- [ ] `regions.rego` uses `allowed_regions`, not `startswith`.
- [ ] The change is committed and pushed to your fork's `main`.

## Recap

Rules need examples. Write the test that exposes the bug, watch it fail, fix the rule, watch it pass, and keep the test forever so the bug cannot return. **Next:** [lab11.md](lab11.md): run the same checks automatically on every pull request.
