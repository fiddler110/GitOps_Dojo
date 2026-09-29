# dns-gate module

`dns-api`, a gate in front of a workshop's PowerDNS API, and a key of its own for every account. Used by
`dns-as-code` and `cert-autorenewal` (remediation T3.1/T3.2, FIND-05 and FIND-11).

Add it with `MODULES="dns-gate"` in a `workshop.env`. The workshop runs PowerDNS as service `dns-server` (API on
`:8081`, its key in `POWERDNS_API_KEY`, derived in `workshop.env` and never given to students) and adds
`dns-api: depends_on: [dns-server]` in its overlay. Terminals and CI jobs talk to `http://dns-api:8081` only.

| Part | What it does |
|---|---|
| `gate/gate.py` | Stdlib Python. Checks `X-API-Key`, swaps in PowerDNS's key, forwards. One JSON audit line per zone change (allowed or refused) on stdout. |
| `gate/test_gate.py` | Unit tests, with real RS256 tokens made by the `openssl` CLI: `cd modules/dns-gate/gate && python3 -B -m unittest test_gate`. |
| `compose.yml` | The `dns-api` service (read-only, no capabilities, on `workshop_lab`); `web-terminal` waits for it. |
| `terminal/` | `start.d/50-dns-key.sh` writes each account's key to `~/.config/dojo/dns-api-key` (`0600`, its own; `/root` gets `FACILITATOR_USERNAME`'s), and every shell exports it as `DNS_API_KEY` (`/etc/zsh/zshenv`, `/etc/profile.d`). |

**Who may do what.** `X-API-Key` carries one of three things:

- **The read key** (`DNS_GATE_READ_KEY`, default `workshop-not-a-secret`, not a secret): reads only.
- **An account's own key**, `<user>.<mac>` with `mac = base32(HMAC-SHA256(STUDENT_PASSWORD_SEED, "dns:<user>"))[:32]`.
  It owns `<user>.<parent>` and every name under it, for each parent in `DNS_GATE_USER_PARENTS`: its own zone
  outright (`student07.dojo.test`), and in a zone the class shares (`DNS_GATE_SHARED_ZONES`) a `PATCH` whose rrsets
  are all its own names (`_acme-challenge.student07.certs.dojo.test`). The facilitator owns every name under each
  parent, but no parent, shared or CI zone itself.
- **A Forgejo Actions ID token** (the job sets `enable-openid-connect: true` and asks for audience `dns-api`): an
  RS256 JWT, checked against Forgejo's JWKS (fetched from `git-server`, again when a new `kid` shows up), with its
  `iss` (`PUBLIC_BASE_URL/git/api/actions`), `aud` and `exp`. It changes the CI-only zones
  (`DNS_GATE_CI_ZONES`) only when `repository` is `DNS_GATE_CI_REPO`, `ref` is `refs/heads/main` and `event_name` is
  `push`. Any other valid token reads. Source IPs mean nothing here: every terminal shares one network namespace.

Server config, TSIG keys and zones outside the lab are refused to everyone. Without `STUDENT_PASSWORD_SEED` no
account key works (reads and CI only), and the gate says so at start.

**Settings** (`module.env`; set them in `workshop.env`): `DNS_GATE_USER_PARENTS` (`dojo.test`),
`DNS_GATE_SHARED_ZONES`, `DNS_GATE_CI_ZONES`, `DNS_GATE_CI_REPO` (`org/repo`), `DNS_GATE_READ_KEY`.

A CI job fetches its token like this (the runner-pool shim fixes the token URL Forgejo builds under `/git/`):

```sh
DNS_API_KEY=$(curl -sSf -H "Authorization: Bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
  "$ACTIONS_ID_TOKEN_REQUEST_URL&audience=dns-api" | jq -r .value)
```

`creds.json` for dnscontrol names the variable, not the key: `"apiKey": "$DNS_API_KEY"`.

**Rate limit (tripwire, not a budget):** a token bucket per authenticated identity (never the source IP). Knobs in
module.env: `DNS_API_RATE_BURST` (default `200`) and `DNS_API_RATE_PER_SEC` (default `50`); `0` = off. CI and the
read key are shared by the class, so they get a x5 bucket. A refusal is a 429 with `Retry-After` and a
`"result":429,"why":"rate limit"` audit line naming the account.

**Not covered:** in `cert-autorenewal`, http-01. That challenge is answered from demo-app's shared webroot, where
each student owns only their own directory; this module doesn't change it. step-ca's name policy
(`*.certs.dojo.test` only) keeps every certificate inside the lab zone.
