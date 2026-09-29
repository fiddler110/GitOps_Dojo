# openbao module

One OpenBao server for the class, its web UI on the landing page and in `/admin`, and the `bao` CLI in every terminal.

Add it with `MODULES="openbao"` in a `workshop.env`. Built for `vault-fundamentals`; its plan
(`workshops/vault-fundamentals/PLAN.md`) has the design.

| Part | What it does |
|---|---|
| `compose.yml` | `openbao` (pinned by digest, raft storage, plain HTTP on `workshop_lab` only), `openbao-setup`, `openbao-sso-shim` and `openbao-audit`. Every volume is named, so `./run.sh stop` removes the vault with the rest. |
| `config.hcl` | The server config: UI on, raft storage, and the file audit device (OpenBao 2.6 and later refuse to enable audit devices through the API, so it is declared here). `openbao-audit` reads the file as OpenBao's uid, and accessors are written in the clear (`hmac_accessor = false`) so a leaked token can be traced by its accessor; tokens and values stay HMACed. |
| `sso-shim/Caddyfile` | Caddy in OpenBao's network namespace. It answers for `PUBLIC_BASE_URL` there and forwards `/git/*` to `git-server`, so OpenBao reaches Forgejo's OIDC issuer by its public URL. `module.env` points that host name at `127.0.0.1` inside OpenBao. On an `https://` name the shim serves with its own CA, which OpenBao must trust (`oidc_discovery_ca_pem`). |
| `setup/` | `openbao-setup` (`setup.sh`, on the OpenBao image). First start: init with one key share (a lab shortcut; production uses auto-unseal) and unseal. Every start: a temporary root token from the unseal key, a short-lived provisioner token (and the reset token, below), root revoked; then, as the provisioner, the UI framing header, the `facilitator` policy, SSO (`sso.sh`, below), CLI login (`cli.sh`, below), then each `/etc/openbao-setup.d/*.sh` hook a workshop mounts (sourced with `BAO_TOKEN` and a `retry` helper; each must be safe to re-run); then the provisioner is revoked. It stays up, unsealing whenever `openbao` restarts sealed (within about 10 s). See **Tokens** below. |
| `audit/audit.py` | `openbao-audit` (stdlib Python on the allocator image, `workshop_lab`, as OpenBao's uid so the shared logs volume stays OpenBao's): follows the audit file (`openbao_logs`, read-only) and answers `GET /entries?ns=<namespace>` to a caller who sends their own vault token as `X-Vault-Token`. OpenBao says what the token may do (`sys/capabilities-self`): the admin of a namespace (`update` on its `sys/policies/acl/*`) reads that namespace's entries, a token with `sudo` on `sys/audit` (the facilitator) every one (`ns=*`). Filters: `accessor` (also matches the entry that made the token), `path`, `limit`. It also serves the facilitator's **Audit** tab in `/admin` (`audit/panel.*`, route `/vault-audit`, `facilitator` gate): every namespace, newest first, filtered by student (their namespace, plus their requests on the shared `secret/`), operation, path, accessor (click one to follow a token) and errors; it checks `X-Gateway-Token` and `X-Auth-User`, as the Runners panel does. |
| `tests/setup_tokens.sh` | The token check (`sh modules/openbao/tests/setup_tokens.sh`, stack up): `/setup` holds no live token, and the reset token reaches the student namespaces but is refused on the root namespace's `sys/`, identities and the shared `secret/`. `--recreate student01` also deletes and re-creates that namespace (destructive). |
| `tests/cli_login.sh` | The CLI login check (`sh modules/openbao/tests/cli_login.sh`, stack up): a new shell for two students and the facilitator is signed in to its own entity, and one account can't get another's JWT, token or the broker key. |
| `tests/test_audit.py` | Unit tests for `openbao-audit` and the Audit tab, no stack needed (`python3 -B -m unittest discover -s modules/openbao/tests -p 'test_*.py'`); a temporary file stands in for OpenBao's audit log. |
| `tests/sso_browser.py` | The SSO check in a real browser (Playwright's image; the command is in its header): a student through the card, the facilitator through the `/admin` tab, each landing in their own entity and policy. |
| `extensions.json` | Landing card and `/admin` tab **Vault**, both through `/forgejo-login?next=/ui/vault/auth?with=oidc`, so the browser is signed in to Forgejo before the UI's "sign in with OIDC" page; the `/ui` and `/v1` routes on the `shared` gate (which strips the gate's `Authorization` header, which OpenBao would read as a token); the status-strip check on `sys/health`, which is 200 only when the vault is unsealed. |
| `terminal/Dockerfile` | `bao-audit` (your namespace's audit trail from `openbao-audit`, as a table or `--json`), and `bao`, pinned and sha256-verified per architecture, and `BAO_ADDR` / `VAULT_ADDR` (`http://openbao:8200`) for every shell. Tools built on the Vault client, such as sops and `hvac`, read the `VAULT_*` names. Also the identity broker and `openbao-login` (CLI login, below) and `start.d/50-openbao.sh`, which makes the broker's key and starts it. VS Code gets HCL highlighting for `.hcl` files (policies, server config) from HashiCorp's `hashicorp.hcl` extension (Open VSX, pinned and sha256-verified), with its telemetry code removed so it is grammar-only and starts no process. |

**OpenBao's UI refuses to be framed by default** (`frame-ancestors 'none'`). For the `/admin` tab, `openbao-setup`
sets `sys/config/ui/headers/Content-Security-Policy` to the same policy with `frame-ancestors 'self'`.

**Settings** (set in `engine/.env` or `workshop.env`): `OPENBAO_MEM_LIMIT` (512m).

**Single sign-on** (`setup/sso.sh`, every start): Forgejo is the OIDC provider. `openbao-setup` creates a confidential
OAuth2 app owned by `FORGEJO_ADMIN_USER` (its id and secret kept on `openbao_setup`, reused while Forgejo still has
it), the `oidc` auth method on `${PUBLIC_BASE_URL}/git` (trusting the shim's CA on `https://`) and its role `forgejo`,
and one identity entity per account, aliased to the Forgejo login: `studentNN` (and each demo bot `testuserN` with
`./run.sh --test`) with the policy `student`, which the workshop's hooks write, and `facilitator` with `facilitator`.
Hooks loop over the same accounts with `for s in $(class_users)`. Forgejo 16 can't skip its "Authorize Application" page
for a trusted app, so each account approves once, on its first sign-in.

**CLI login** (`terminal/`, `setup/cli.sh`): the browser can't reach a terminal's `localhost`, so `bao login
-method=oidc` can't work there. Instead a root-owned broker in the terminal signs a two-minute RS256 JWT (`iss`
`dojo-terminal`, `aud` `openbao`, `sub` the login name) for whichever account asks on its unix socket (`SO_PEERCRED`
says who; only students and the facilitator get one). Its key is on `openbao_broker_key` (terminal only); the public
half goes on `openbao_broker_pub`, where `openbao-setup` reads it for the `jwt` auth method and its role `terminal`.
Each login name is aliased to the same entity as the account's SSO login. Every shell start runs `openbao-login
--quiet` from `/etc/zsh/zshenv`: it trades a JWT for a token in `~/.vault-token` (read by `bao`, sops and `hvac`)
when there is none or the one it wrote has under an hour left, and leaves alone a token the user got with `bao
login`. A shell opened before OpenBao was ready has no token: run `openbao-login`.

## Rate limit (tripwire)

A workshop whose tenancy hook makes per-student namespaces (vault-fundamentals) also puts a `sys/quotas/rate-limit`
quota in each one. It is a tripwire against a runaway loop, not a budget: `OPENBAO_NAMESPACE_RATE` (module.env) is
requests per second per namespace, default `200`, `0` = no quota. One student's loop gets 429s; the rest of the class
is untouched. The workshop's `provisioner.hcl` grants `sys/quotas/rate-limit/students-*` (from the root namespace, each quota scoped to a student namespace with `path`) for this.

## Tokens

Nothing keeps a root or provisioner token (remediation T5.3, D11). On every start `openbao-setup`:

1. makes a **temporary root** from the unseal key (`bao operator generate-root`; on the very first start, the init
   root token);
2. with it, revokes what an earlier start left (a start that dies half-way leaves the accessors of its tokens in
   `/setup/pending-accessors`), writes the policies and mints a **provisioner** token (`-ttl=2h`, not renewed) and,
   if the workshop has a `reset.hcl`, the **reset** token; then revokes the root;
3. runs the set-up and the hooks as the provisioner, then revokes it.

**Policies.** `setup/policies/provisioner.hcl` grants the exact paths `setup.sh`, `sso.sh` and `cli.sh` write. A
workshop whose hooks write more mounts `/etc/openbao-setup.d/provisioner.hcl`, appended to it: its hooks' exact
paths, nothing wider (vault-fundamentals: `compose/openbao-setup.d/provisioner.hcl`). A hook that writes a new path
adds it there, or the start stops with "permission denied".

**Reset token** (the student-reset plan's R9, remediation D15). Minted only when the workshop mounts
`/etc/openbao-setup.d/reset.hcl`; its policy is `setup/policies/reset.hcl` (renew and look up itself) plus that file,
which grants the per-student paths only (vault-fundamentals: delete and re-create `students/<name>` and what its
hooks put there; not the namespace `students`, policies, auth methods, identities or the shared `secret/` data). It is
periodic (24h), kept in memory only at `/run/openbao-setup/reset-token` (the container's tmpfs) and renewed hourly by
`openbao-setup`; its accessor is on `/setup/reset-accessor`, so the next start revokes it before minting a new one.
Handing it to a resident `openbao-reset` service is the reset plan's R3.2.

`/setup` keeps the unseal key, the accessors above and SSO's OAuth2 app, and no live token:
`sh modules/openbao/tests/setup_tokens.sh` checks it.

## Accepted risks

Decided with the threat-model remediation (`threat-model-20260926-154208/REMEDIATION-PLAN.md`, D9), and told to the
class in vault-fundamentals (slide "What today's vault cuts short"):

- **One unseal key share, on `openbao_setup`** (FIND-17). The vault unseals itself after a restart. Whoever can read
  that volume (host access) can unseal it and make a root token as step 1 does; revoking the tokens protects against a
  token read from the volume or a leaked environment, not against that. Production: auto-unseal (KMS or HSM), or key
  shares held by several people.
- **Plain HTTP** to OpenBao on `workshop_lab` (and `runner_net` where a workshop adds it) (FIND-19). Only the
  stack's own containers are on those networks; browsers reach OpenBao only through the gateway.
- **`hmac_accessor = false`** in `config.hcl`'s audit device: `openbao-audit`, `bao-audit` and the Audit tab match
  requests to students by token accessor. An accessor can't be used to authenticate, and tokens and secret values
  stay HMAC-hashed in the log.
