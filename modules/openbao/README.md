# openbao module

One OpenBao server for the class, its web UI on the landing page and in `/admin`, and the `bao` CLI in every terminal.

Add it with `MODULES="openbao"` in a `workshop.env`. Built for `vault-fundamentals`; its plan
(`workshops/vault-fundamentals/PLAN.md`) has the design.

| Part | What it does |
|---|---|
| `compose.yml` | `openbao` (pinned by digest, raft storage, plain HTTP on `workshop_lab` only), `openbao-setup`, `openbao-sso-shim` and `openbao-audit`. Every volume is named, so `./run.sh stop` removes the vault with the rest. |
| `config.hcl` | The server config: UI on, raft storage, and the file audit device (OpenBao 2.6 and later refuse to enable audit devices through the API, so it is declared here). `openbao-audit` reads the file as OpenBao's uid, and accessors are written in the clear (`hmac_accessor = false`) so a leaked token can be traced by its accessor; tokens and values stay HMACed. |
| `sso-shim/Caddyfile` | Caddy in OpenBao's network namespace. It answers for `PUBLIC_BASE_URL` there and forwards `/git/*` to `git-server`, so OpenBao reaches Forgejo's OIDC issuer by its public URL. `module.env` points that host name at `127.0.0.1` inside OpenBao. On an `https://` name the shim serves with its own CA, which OpenBao must trust (`oidc_discovery_ca_pem`). |
| `setup/` | `openbao-setup` (`setup.sh`, on the OpenBao image). First start: init with one key share (a lab shortcut; production uses auto-unseal), unseal, the provisioner policy and a periodic provisioner token, then revoke root. Every start: the UI framing header, the `facilitator` policy, SSO (`sso.sh`, below), CLI login (`cli.sh`, below), then each `/etc/openbao-setup.d/*.sh` hook a workshop mounts (sourced with `BAO_TOKEN` and a `retry` helper; each must be safe to re-run). Then it stays up, unsealing whenever `openbao` restarts sealed (within about 10 s). The key and token live on `openbao_setup`, which nothing else mounts: `podman exec workshop_openbao_setup cat /setup/provisioner-token`. |
| `audit/audit.py` | `openbao-audit` (stdlib Python on the allocator image, `workshop_lab`, as OpenBao's uid so the shared logs volume stays OpenBao's): follows the audit file (`openbao_logs`, read-only) and answers `GET /entries?ns=<namespace>` to a caller who sends their own vault token as `X-Vault-Token`. OpenBao says what the token may do (`sys/capabilities-self`): the admin of a namespace (`update` on its `sys/policies/acl/*`) reads that namespace's entries, a token with `sudo` on `sys/audit` (the facilitator) every one (`ns=*`). Filters: `accessor` (also matches the entry that made the token), `path`, `limit`. It also serves the facilitator's **Audit** tab in `/admin` (`audit/panel.*`, route `/vault-audit`, `facilitator` gate): every namespace, newest first, filtered by student (their namespace, plus their requests on the shared `secret/`), operation, path, accessor (click one to follow a token) and errors; it checks `X-Gateway-Token` and `X-Auth-User`, as the Runners panel does. |
| `tests/cli_login.sh` | The CLI login check (`sh modules/openbao/tests/cli_login.sh`, stack up): a new shell for two students and the facilitator is signed in to its own entity, and one account can't get another's JWT, token or the broker key. |
| `tests/sso_browser.py` | The SSO check in a real browser (Playwright's image; the command is in its header): a student through the card, the facilitator through the `/admin` tab, each landing in their own entity and policy. |
| `extensions.json` | Landing card and `/admin` tab **Vault**, both through `/forgejo-login?next=/ui/vault/auth?with=oidc`, so the browser is signed in to Forgejo before the UI's "sign in with OIDC" page; the `/ui` and `/v1` routes on the `shared` gate (which strips the gate's `Authorization` header, which OpenBao would read as a token); the status-strip check on `sys/health`, which is 200 only when the vault is unsealed. |
| `terminal/Dockerfile` | `bao-audit` (your namespace's audit trail from `openbao-audit`, as a table or `--json`), and `bao`, pinned and sha256-verified per architecture, and `BAO_ADDR` / `VAULT_ADDR` (`http://openbao:8200`) for every shell. Tools built on the Vault client, such as sops and `hvac`, read the `VAULT_*` names. Also the identity broker and `openbao-login` (CLI login, below) and `start.d/50-openbao.sh`, which makes the broker's key and starts it. |

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
