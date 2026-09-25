# openbao module

One OpenBao server for the class, its web UI on the landing page and in `/admin`, and the `bao` CLI in every terminal.

Add it with `MODULES="openbao"` in a `workshop.env`. Built for `vault-fundamentals`; its plan
(`workshops/vault-fundamentals/PLAN.md`) has the design.

| Part | What it does |
|---|---|
| `compose.yml` | `openbao` (pinned by digest, raft storage, plain HTTP on `workshop_lab` only), `openbao-setup` and `openbao-sso-shim`. Every volume is named, so `./run.sh stop` removes the vault with the rest. |
| `config.hcl` | The server config: UI on, raft storage, and the file audit device (OpenBao 2.6 and later refuse to enable audit devices through the API, so it is declared here). |
| `sso-shim/Caddyfile` | Caddy in OpenBao's network namespace. It answers for `PUBLIC_BASE_URL` there and forwards `/git/*` to `git-server`, so OpenBao reaches Forgejo's OIDC issuer by its public URL. `module.env` points that host name at `127.0.0.1` inside OpenBao. On an `https://` name the shim serves with its own CA, which OpenBao must trust (`oidc_discovery_ca_pem`). |
| `setup/` | `openbao-setup` (`setup.sh`, on the OpenBao image). First start: init with one key share (a lab shortcut; production uses auto-unseal), unseal, the provisioner policy and a periodic provisioner token, then revoke root. Every start: the UI framing header, the `facilitator` policy, then each `/etc/openbao-setup.d/*.sh` hook a workshop mounts (sourced with `BAO_TOKEN` and a `retry` helper; each must be safe to re-run). Then it stays up, unsealing whenever `openbao` restarts sealed (within about 10 s). The key and token live on `openbao_setup`, which nothing else mounts: `podman exec workshop_openbao_setup cat /setup/provisioner-token`. |
| `extensions.json` | Landing card and `/admin` tab **Vault**, both opening the UI's "sign in with OIDC" page; the `/ui` and `/v1` routes on the `shared` gate (which strips the gate's `Authorization` header, which OpenBao would read as a token); the status-strip check on `sys/health`, which is 200 only when the vault is unsealed. |
| `terminal/Dockerfile` | `bao`, pinned and sha256-verified per architecture, and `BAO_ADDR` / `VAULT_ADDR` (`http://openbao:8200`) for every shell. Tools built on the Vault client, such as sops and `hvac`, read the `VAULT_*` names. |

**OpenBao's UI refuses to be framed by default** (`frame-ancestors 'none'`). For the `/admin` tab, `openbao-setup`
sets `sys/config/ui/headers/Content-Security-Policy` to the same policy with `frame-ancestors 'self'`.

**Settings** (set in `engine/.env` or `workshop.env`): `OPENBAO_MEM_LIMIT` (512m).

**Not built yet** (vault-fundamentals P1): SSO setup (T1.3) and CLI login (T1.4). Until then the workshop's
`spike/t05-sso.sh` sets up SSO by hand, with the provisioner token.
