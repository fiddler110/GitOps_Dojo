# policy-bypass

CloudGuard is a small policy service in Flask. It guards two resource groups, `rg-sandbox` (open to everyone)
and `rg-vault-gateway`, where only the security team may provision resources.

- `GET /api/policy` shows the active policy; `GET /api/resources` lists what was provisioned;
  `GET /spec` is the API reference.
- `POST /api/provision` takes `name`, `resourceGroup`, and optional `tags` and `properties`. The request
  is evaluated against the policy in `app.py` by `policy_engine.py`.

What the platform provides:

- A gateway proxy sits in front of the app. The app listens on `127.0.0.1:5001`; the proxy takes the traffic
  on port 5000.
- The proxy sets two headers on every request, replacing whatever the client sent: `X-Caller-Role`, which is
  `security-team` when the request carries the security team's API key and `developer` otherwise, and
  `X-Gateway-Token`, a secret shared with the app in the `CTF_PROXY_TOKEN` environment variable.
  A role header is only genuine when `X-Gateway-Token` equals `CTF_PROXY_TOKEN`.
- `app.py` already has a helper, `_caller_role()`, which returns the proxy's role or `unknown`.
- Your pull request is built and tested before it can be merged; merging to `main` redeploys your slot.
- `dojo-check policy-bypass` in your terminal reports whether the live app is still exploitable.
- Audit lines for each provision request appear in the security dashboard.
