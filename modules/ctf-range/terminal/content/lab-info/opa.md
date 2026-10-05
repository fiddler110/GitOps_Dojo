# opa (Open Policy Agent)

Evaluates policy written in **Rego** against a piece of input data and
answers a question like "is this request allowed?" — the same engine
`cloud-policy-as-code` uses for real. Here it lets you run a policy
yourself and see exactly why it allowed or denied something, instead of
only observing a service's allow/deny decision from the outside.

## A minimal policy and input, evaluated locally

```text
cat > policy.rego <<'EOF'
package example

default allow = false

allow {
    input.role == "admin"
}
EOF

echo '{"role": "user"}' > input.json
opa eval -d policy.rego -i input.json "data.example.allow"
```
```text
{
  "result": [
    {
      "expressions": [
        {
          "value": false,
          "text": "data.example.allow",
          ...
        }
      ]
    }
  ]
}
```
`-d` loads the policy (a directory or file), `-i` loads the input, and the
last argument is the Rego expression to evaluate — here, "what does
`allow` come out to." Change `input.json`'s role to `"admin"` and re-run
to see `value` flip to `true`.

## Reading a policy itself

```text
package example       # namespace for this policy's rules

default allow = false  # the fallback if nothing below matches - start
                        # from deny, then carve out exceptions, not the
                        # other way around

allow {
    input.role == "admin"   # one way to become true; multiple `allow { }`
}                            # blocks are OR'd together
```
A rule block is a set of conditions **AND**ed together; multiple blocks
with the same name are **OR**ed. Reading a policy is mostly reading which
of these shapes you're looking at.

## Testing a policy against known cases

```text
cat > policy_test.rego <<'EOF'
package example

test_admin_allowed {
    allow with input as {"role": "admin"}
}

test_user_denied {
    not allow with input as {"role": "user"}
}
EOF

opa test .
```
```text
PASS: 2/2
```
`opa test` runs every rule named `test_*` and reports pass/fail per case —
the same tool and the same idea as any other unit test suite, just over
policy instead of application code. A policy that passes every test you
wrote still only proves what you thought to test; it says nothing about a
case nobody wrote a test for.

## Where this connects

If a target's briefing mentions a policy or a `deny`/`allow` rule, `opa
eval`/`opa test` let you load the actual policy file (if it's reachable)
and experiment with inputs locally, the same way a developer would before
ever deploying a change to it.
