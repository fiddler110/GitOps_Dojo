# Vault Fundamentals — cheat sheet

`bao` is OpenBao's CLI; every command is the same as `vault`'s.

## Who am I?

```bash
bao status                    # is the vault up and unsealed?
bao token lookup              # your token: entity, policies, TTL
openbao-login                 # sign this shell in again (e.g. opened before the vault was ready)
```

## `pass`: secrets on your own machine (lab 2)

```bash
gpg --quick-gen-key "$USER <$USER@dojo.test>" default default 1y   # a key pair; asks for a passphrase
pass init "$USER@dojo.test"            # a store in ~/.password-store, encrypted for that key
pass git init                          # keep its history in git
pass insert -m dojo/db                 # type lines, then Ctrl+D; stays out of shell history
pass generate dojo/api-token 32        # a random one
pass show dojo/db                      # decrypt and print (| head -1 for just the password)
EDITOR=nano pass edit dojo/db          # change it (a commit)
pass init -p dojo you@x them@x         # re-encrypt one folder for several people
```

On your own machine at work: Linux `apt install pass`; macOS `brew install pass gnupg`; **Windows**
[gopass](https://www.gopass.pw/), which reads and writes the same store: `winget install gopass.gopass` and
`winget install GnuPG.Gpg4win`, then `gopass setup` (commands: `gopass insert`, `gopass show`, `gopass generate`).

## KV v2 secrets (labs 3-4)

```bash
printf '%s' 'pw' | bao kv put secret/students/$USER/db user=app password=-   # new version, replaces all keys
printf '%s' 'pw2' | bao kv patch secret/students/$USER/db password=-         # new version, changes only these keys
echo '{"a": "1", "b": "2"}' | bao kv put secret/students/$USER/x -          # several keys, as JSON
# key=- reads the value from stdin: a command line is visible to everyone in `ps`
bao kv get    secret/students/$USER/db                        # newest version
bao kv get    -field=password secret/students/$USER/db        # one value, for scripts
bao kv get    -version=1 secret/students/$USER/db             # an old version
bao kv list   secret/students/$USER/
bao kv metadata get secret/students/$USER/db                  # every version, when, deleted or not
bao kv rollback -version=2 secret/students/$USER/db           # old data as a new version
bao kv delete   secret/students/$USER/db                      # hide newest (soft delete)
bao kv undelete -versions=3 secret/students/$USER/db          # bring it back
bao kv destroy  -versions=1 secret/students/$USER/db          # wipe a version for good
bao kv metadata delete secret/students/$USER/db               # wipe the secret and its history
```

## Policies and tokens (lab 4)

```bash
export BAO_NAMESPACE=students/$USER     # work in your own namespace; `unset` to leave
bao secrets enable -path=team kv-v2
bao policy list
bao policy read  app-read
bao policy write app-read app-read.hcl
bao token create -orphan -policy=app-read -ttl=15m -field=token  # no parent, no identity
BAO_TOKEN=<token> bao kv get team/app  # run one command as another token
bao token revoke <token>
```

A policy is paths and capabilities; anything not allowed is denied:

```hcl
path "team/data/app" {
  capabilities = ["read"]   # create, read, update, patch, delete, list, sudo, deny
}
```

KV v2 paths inside a policy: `<mount>/data/...` (values), `<mount>/metadata/...` (list, history), `<mount>/delete/`,
`undelete/`, `destroy/...`.

## Apps and the Agent (labs 5-6)

```python
import hvac
client = hvac.Client()   # VAULT_ADDR, and VAULT_TOKEN or ~/.vault-token
resp = client.secrets.kv.v2.read_secret_version(mount_point="secret", path="students/<you>/app",
                                                raise_on_deleted_version=True)
resp["data"]["data"]     # the values; resp["data"]["metadata"]["version"]
client.auth.token.renew_self()
```

```bash
bao auth enable approle
bao write auth/approle/role/app token_policies=app-read token_ttl=2m token_max_ttl=10m
bao read -field=role_id auth/approle/role/app/role-id       # like a user name
bao write -f -field=secret_id auth/approle/role/app/secret-id  # like a password: secret zero
bao agent -config=agent.hcl > agent.log 2>&1 &              # log in, renew, render templates
```

Log that you loaded a secret, never its value.

## sops and transit (lab 7)

```bash
bao secrets enable transit
bao write -f transit/keys/sops                     # a key that never leaves the vault
sops encrypt -i app.enc.yaml                       # uses .sops.yaml's hc_vault_transit_uri
sops decrypt app.enc.yaml
sops decrypt --extract '["database"]["password"]' app.enc.yaml
sops set app.enc.yaml '["database"]["password"]' '"new"'
sops edit app.enc.yaml                             # plaintext only in the editor
git config diff.sopsdiffer.textconv "sops decrypt"  # with '*.enc.yaml diff=sopsdiffer' in .gitattributes
bao write -f transit/keys/sops/rotate              # new key version; old ones still decrypt
sops rotate -i app.enc.yaml                        # new data key, wrapped with the newest version
bao write transit/keys/sops/config min_decryption_version=2  # retire old versions
```

`.sops.yaml` (the key URL carries your namespace):

```yaml
creation_rules:
  - path_regex: \.enc\.yaml$
    hc_vault_transit_uri: http://openbao:8200/v1/students/<you>/transit/keys/sops
```

## CI and the vault (labs 8-9)

```yaml
# .forgejo/workflows/ci.yml: a job that logs in with its own identity
on: push
jobs:
  read:
    runs-on: host
    enable-openid-connect: true                  # Forgejo offers the job an ID token
    env:
      BAO_ADDR: http://openbao:8200
      BAO_NAMESPACE: students/${{ github.repository_owner }}
    steps:
      - run: |
          curl -sSf -H "Authorization: Bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
            "$ACTIONS_ID_TOKEN_REQUEST_URL&audience=openbao" | jq -j .value > "$HOME/id"
          export BAO_TOKEN="$(bao write -field=token auth/jwt-ci/login role=ci-main jwt=@$HOME/id)"
          bao kv get -field=deploy_token team/ci | sha256sum   # a fingerprint, never the value
```

```bash
bao read auth/jwt-ci/config                        # whose keys and issuer the vault trusts
bao write auth/jwt-ci/role/ci-main - <<EOF         # who may log in: this repo, on main
{"role_type":"jwt","user_claim":"sub","bound_audiences":["openbao"],
 "bound_claims":{"repository":"$USER/vault-fundamentals","ref":"refs/heads/main"},
 "token_policies":["ci-read"],"token_ttl":"5m"}
EOF
```

`${{ secrets.NAME }}` is masked as `***` in logs, but anyone who can push a workflow can print it (`| base64`).

## Deployments (labs 10-13)

```bash
# Lab 10: the pipeline delivers the app's secret ID, wrapped, once per deploy
bao write auth/approle/role/app token_policies=app-read token_period=10m \
  secret_id_num_uses=1 secret_id_ttl=5m                  # single-use, 5 minutes; a renewable token
bao write -f -wrap-ttl=60s -field=wrapping_token auth/approle/role/app/secret-id   # the wrapper
printf '%s' "$WRAPPED" | bao write sys/wrapping/lookup token=-   # where it was made, how long it lives
BAO_TOKEN="$WRAPPED" bao unwrap -field=secret_id                  # once; again: "not valid or does not exist"
```

```hcl
# policies/app-deliver.hcl: mint secret IDs for the app, wrapped only
path "auth/approle/role/app/secret-id" {
  capabilities     = ["update"]
  min_wrapping_ttl = "10s"
  max_wrapping_ttl = "120s"
}
# app/agent.hcl, in the approle config: open only a wrapper made at that path
#   secret_id_response_wrapping_path = "auth/approle/role/app/secret-id"
```

Lab 11 onwards: the platform's identity instead, so nothing is delivered.

```bash
curl -s http://app-host:8080/.well-known/jwks.json      # the platform's public keys
bao write auth/jwt-platform/role/app role_type=jwt user_claim=sub bound_audiences=openbao \
  bound_subject="slot:$USER" token_policies=app-read token_ttl=15m
curl -s http://app-host:8080/$USER/                      # your app (also the My App card)
```

```hcl
# app/agent.hcl: log in with the slot's platform identity
auto_auth {
  method "jwt" {
    namespace  = "students/<you>"
    mount_path = "auth/jwt-platform"
    config = { path = "/run/platform/<you>/token", role = "app", remove_jwt_after_reading = false }
  }
}
```

```bash
# Deploy step: the job's ID token for app-host, and the app folder
id_token="$(curl -sSf -H "Authorization: Bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
  "$ACTIONS_ID_TOKEN_REQUEST_URL&audience=app-host" | jq -j .value)"
tar -czf app.tgz -C src/app . && curl -sS --fail-with-body -H "Authorization: Bearer $id_token" \
  --data-binary @app.tgz http://app-host:8080/deploy
```

```bash
bao read database/creds/app                   # a Postgres login made now (lab 12)
bao lease lookup|renew|revoke <lease_id>
bao token lookup -format=json <token> | jq -r .data.accessor
bao-audit --accessor <accessor>               # what that token did (lab 13)
bao token revoke -accessor <accessor>         # it, and every token it made
```

## Secrets in git (lab 1)

```bash
git log -p                     # every change, including removed lines
git log -S "text" --oneline    # commits that added or removed "text"
gitleaks git -v                # scan the whole history
gitleaks git --pre-commit --staged --redact -v   # scan what you're about to commit (hook)
```

A secret that reached a remote is leaked: **rotate it**. Deleting it from the file, or from history, isn't enough.

## The rules

1. Least privilege · 2. Identity over secrets · 3. Short-lived and revocable · 4. Know your secret zero ·
5. Separation of duties · 6. Audit everything · 7. Plan for leaks · 8. Never in git, logs or images
