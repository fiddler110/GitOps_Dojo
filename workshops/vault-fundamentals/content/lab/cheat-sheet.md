# Vault Fundamentals — cheat sheet

`bao` is OpenBao's CLI; every command is the same as `vault`'s.

## Who am I?

```bash
bao status                    # is the vault up and unsealed?
bao token lookup              # your token: entity, policies, TTL
openbao-login                 # sign this shell in again (e.g. opened before the vault was ready)
```

## KV v2 secrets (labs 2-3)

```bash
bao kv put    secret/students/$USER/db user=app password=pw   # new version, replaces all keys
bao kv patch  secret/students/$USER/db password=pw2           # new version, changes only these keys
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

## Policies and tokens (lab 3)

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
