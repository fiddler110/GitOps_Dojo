# Lab 8 — CI logs in to OpenBao

**Goal:** let a pipeline read a secret from the vault. First the common way, **AppRole** with its login secret stored in the CI system, which works but leaves a long-lived secret behind. Then with the **job's own identity**: an OIDC token Forgejo issues for this one run, which the vault checks is from *your repo* on *`main`*. Nothing is stored at all.

---

## 1. The secret the pipeline needs

This lab works in your namespace and your fork from Labs 3 and 7. If you skipped them, this block catches you up (it's safe to run anyway):

```bash
export BAO_NAMESPACE=students/$USER
bao secrets list | grep -q '^team/' || bao secrets enable -path=team kv-v2
bao auth list | grep -q '^approle/' || bao auth enable approle
[ -d ~/lab/vault-fundamentals ] || {
  curl -u "$USER" -H "Content-Type: application/json" -d '{}' \
    http://git-server:3000/api/v1/repos/platform-team/vault-fundamentals/forks
  git clone http://git-server:3000/$USER/vault-fundamentals.git ~/lab/vault-fundamentals
}
cd ~/lab/vault-fundamentals
git config credential.helper 'cache --timeout=3600'
```

A deploy token for the pipeline, and a policy that reads it and nothing else:

```bash
# a new KV mount refuses writes for a moment while it upgrades: retry
until bao kv put team/ci deploy_token="deploy-$USER-$RANDOM$RANDOM"; do sleep 2; done
printf 'path "team/data/ci" {\n  capabilities = ["read"]\n}\n' | bao policy write ci-read -
```

The job will print a **fingerprint** of what it read, never the value. Here is the one to expect:

```bash
printf %s "$(bao kv get -field=deploy_token team/ci)" | sha256sum | cut -c1-12
```

## 2. The usual way: AppRole, login secret in Forgejo

An AppRole for CI (as in Lab 5), whose secret ID lives a day:

```bash
bao write auth/approle/role/ci token_policies=ci-read token_ttl=5m secret_id_ttl=24h
```

Now store its two IDs as **repository secrets** in your fork. The API call below reads them from a file, so they never appear on a command line, where other users on this machine could see them:

```bash
put_secret() {  # put_secret NAME VALUE: a repository secret in your fork
  (umask 077; printf '{"data":"%s"}' "$2" > ~/.secret-body.json)
  curl -s -o /dev/null -w "$1: HTTP %{http_code}\n" -u "$USER" -X PUT \
    -H "Content-Type: application/json" -d @$HOME/.secret-body.json \
    http://git-server:3000/api/v1/repos/$USER/vault-fundamentals/actions/secrets/$1
  rm -f ~/.secret-body.json
}
put_secret BAO_ROLE_ID "$(bao read -field=role_id auth/approle/role/ci/role-id)"
put_secret BAO_SECRET_ID "$(bao write -f -field=secret_id auth/approle/role/ci/secret-id)"
```

`HTTP 201` (or `204`) for each means stored. Check Forgejo → your fork → **Settings** → **Actions** → **Secrets**: both names are there.

The workflow logs in with them and reads the deploy token:

```bash
mkdir -p .forgejo/workflows
cat > .forgejo/workflows/vault-approle.yml <<'EOF'
name: vault-approle
on: push
jobs:
  read:
    runs-on: host
    env:
      BAO_ADDR: http://openbao:8200
      BAO_NAMESPACE: students/${{ github.repository_owner }}
    steps:
      - name: Log in with AppRole and read the deploy token
        env:
          ROLE_ID: ${{ secrets.BAO_ROLE_ID }}
          SECRET_ID: ${{ secrets.BAO_SECRET_ID }}
        run: |
          export BAO_TOKEN="$(bao write -field=token auth/approle/login role_id="$ROLE_ID" secret_id="$SECRET_ID")"
          token="$(bao kv get -field=deploy_token team/ci)"
          echo "deploy token fingerprint: $(printf %s "$token" | sha256sum | cut -c1-12)"
EOF
git add .forgejo/workflows/vault-approle.yml
git commit -m "CI reads the deploy token with AppRole"
git push
```

In Forgejo → **Actions**, the run's log shows the same fingerprint as your terminal. It works. But look at what it took:

- A **secret ID valid for a day** now sits in Forgejo. From Lab 7: anyone who can push a workflow to this repo can print it, and use it from anywhere until it expires.
- Something had to put it there, and rotate it. That's **secret zero** again: the pipeline's first credential came from a person, and it's long-lived.

## 3. The job's own identity

Forgejo can give each job a signed **OIDC token** that says which repo, branch, workflow and person started it. It's valid for minutes, made for this one run, and never stored anywhere.

Your namespace already trusts Forgejo's signing keys (your facilitator set that up):

```bash
bao read auth/jwt-ci/config
```

`bound_issuer` is Forgejo's Actions issuer, and `jwks_url` is where the vault fetches the public keys to check signatures. What's missing is the **role**: who may log in, and what they get. Only jobs from **your fork**, on **`main`**, with the audience `openbao`:

```bash
bao write auth/jwt-ci/role/ci-main - <<EOF
{
  "role_type": "jwt",
  "user_claim": "sub",
  "bound_audiences": ["openbao"],
  "bound_claims": {
    "repository": "$USER/vault-fundamentals",
    "ref": "refs/heads/main"
  },
  "token_policies": ["ci-read"],
  "token_ttl": "5m"
}
EOF
```

The workflow asks Forgejo for its token (`enable-openid-connect: true` makes Forgejo offer one), shows the claims (never the token itself: it's a credential for as long as it's valid), and logs in with it:

```bash
cat > .forgejo/workflows/vault-oidc.yml <<'EOF'
name: vault-oidc
on: push
jobs:
  read:
    runs-on: host
    enable-openid-connect: true
    env:
      BAO_ADDR: http://openbao:8200
      BAO_NAMESPACE: students/${{ github.repository_owner }}
    steps:
      - name: Log in with this job's identity and read the deploy token
        run: |
          id_token="$(mktemp)"
          curl -sSf -H "Authorization: Bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
            "$ACTIONS_ID_TOKEN_REQUEST_URL&audience=openbao" | jq -j .value > "$id_token"
          echo "What this job's token says about it:"
          jq -R 'split(".")[1] | gsub("-";"+") | gsub("_";"/") | @base64d | fromjson
                 | {iss, aud, repository, ref, workflow, actor, exp}' "$id_token"
          export BAO_TOKEN="$(bao write -field=token auth/jwt-ci/login role=ci-main jwt=@"$id_token")"
          rm -f "$id_token"
          echo "The vault token it got:"
          bao token lookup -format=json | jq '.data | {display_name, policies, ttl}'
          token="$(bao kv get -field=deploy_token team/ci)"
          echo "deploy token fingerprint: $(printf %s "$token" | sha256sum | cut -c1-12)"
EOF
git add .forgejo/workflows/vault-oidc.yml
git commit -m "CI reads the deploy token with its own identity"
git push
```

Open the **vault-oidc** run. The claims show your repo, `refs/heads/main` and your name as `actor`; the vault token has `ci-read` and a TTL of about 5 minutes; the fingerprint matches. **No secret was stored in Forgejo for this.**

## 4. Another branch is refused

The role trusts `main` only. Push the same code from a branch:

```bash
git switch -c try-a-branch
git commit --allow-empty -m "Try the vault login from a branch"
git push -u origin try-a-branch
```

In **Actions**, the two new runs differ:

- **vault-oidc fails**: `error validating claims: claim "ref" does not match any associated bound claim values`. A branch, which anyone with write access can push without review, can't read what `main` reads.
- **vault-approle succeeds**: the AppRole login can't tell a branch from `main`. Whoever holds the secret ID gets in.

```bash
git switch main
git push origin --delete try-a-branch
```

## 5. Retire the stored secret

The OIDC login does the job, so the AppRole path goes: in the vault, then in Forgejo, then in the repo.

```bash
bao delete auth/approle/role/ci
for s in BAO_ROLE_ID BAO_SECRET_ID; do
  curl -s -o /dev/null -w "$s: HTTP %{http_code}\n" -u "$USER" -X DELETE \
    http://git-server:3000/api/v1/repos/$USER/vault-fundamentals/actions/secrets/$s
done
git rm .forgejo/workflows/vault-approle.yml
git commit -m "Drop the AppRole login: CI uses its own identity"
git push
```

Deleting the role first matters: it makes every secret ID issued for it useless at once, including any copy someone printed.

```bash
unset BAO_NAMESPACE
```

## At work

The same pattern, with ready-made steps instead of `curl` and `bao`:

- **GitHub Actions**: `permissions: id-token: write`, then `hashicorp/vault-action` with `method: jwt` (it works against OpenBao too), or `azure/login` with **workload identity federation** for Azure.
- **Azure DevOps**: a service connection with workload identity federation.
- **GitLab**: `id_tokens:` in the job, and the JWT auth method in the vault.

In each, the vault (or the cloud) trusts the CI system's issuer, and a role binds **which repo, which branch or environment** may log in.

## Check yourself

1. What does the vault check before it accepts the job's token? *(The signature against Forgejo's keys, the issuer, the audience `openbao`, expiry, and the bound claims: this repo, on `main`.)*
2. Why is a pushed branch refused but `main` allowed? *(Changes reach `main` through review; a branch can be pushed by anyone with write access. Binding `ref` keeps unreviewed code away from the secret.)*
3. What can someone do with a job's log from the OIDC run? *(Nothing: it holds claims and a fingerprint, no credential. The ID token was never printed and expires in minutes.)*

**Rules used:** 2 (identity over secrets), 4 (no secret zero left in the pipeline), 3 (a 5-minute token), 1 (one repo, one branch, one path), 7 (retiring the old credential).
