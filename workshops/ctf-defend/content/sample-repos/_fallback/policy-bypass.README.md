# policy-bypass

A small cloud-provisioning API: `POST /api/provision` creates a resource in a resource group, and a policy
decides whether the write is allowed. `GET /api/policy` shows the policy. Some groups are protected and only the
security team may write to them.

## What the platform provides

A gateway in front of this app (not in this repo) decides who the caller is and tells the app in a header:
`X-Caller-Role` is `security-team` or `developer`, and `X-Gateway-Token` proves the header came from the
gateway. Anything the caller puts in the request body, tags included, is the caller's own claim.

## Running it yourself

```sh
python3 app.py      # listens on :5000 (PORT to change it)
```

## What the platform does

- The **PR gate** starts your branch, tries a protected write as an ordinary developer, and sends one legitimate
  security-team request. Pass means the first is refused and the second still works (advisory: it never blocks the merge).
- Merging to `main` rebuilds and redeploys your slot. `dojo check policy-bypass` checks your live slot.
