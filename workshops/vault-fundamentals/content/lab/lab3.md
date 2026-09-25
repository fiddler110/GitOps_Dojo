# Lab 3 — You are the admin

**Goal:** run your own vault. In your own namespace you enable a secrets engine, write a least-privilege policy (in the UI, then as code), hand out a token with it, and prove what it can and can't do.

A **namespace** is a vault inside the vault: its own engines, policies, tokens and sign-in methods, invisible from the others. You are the admin of `students/<you>` and of nothing else. At work this is "the team's own vault"; on Azure it would be a Key Vault per team or per environment.

---

## 1. Step into your namespace

Every `bao` command in this shell now goes to your namespace:

```bash
export BAO_NAMESPACE=students/$USER
bao secrets list
```

Only the built-in engines: `secret/` from Lab 2 is in the root namespace, not in yours. Try your neighbour's:

```bash
bao secrets list -namespace=students/student02
```

`permission denied`. Admin of your own vault, nobody else's.

## 2. Enable an engine and store the team's secrets

```bash
bao secrets enable -path=team kv-v2
bao kv put team/app db_password=app-db-pass api_key=app-api-key
bao kv put team/admin root_password=do-not-share
bao kv list team/
```

(If the first `put` says the mount is upgrading, wait two seconds and run it again.)

## 3. A least-privilege policy, in the UI

The app should read `team/app` and nothing else. In the Vault tab:

1. Switch to your namespace: use the **namespace picker** in the side menu and choose `students/<you>` (or add `?namespace=students/<you>` to the end of the address).
2. Open **Policies → ACL policies → Create ACL policy**.
3. Name it `app-read`, and give it this body:

   ```hcl
   path "team/data/app" {
     capabilities = ["read"]
   }
   ```

4. Click **Create policy**.

Check it arrived, from the terminal:

```bash
bao policy list
bao policy read app-read
```

## 4. The same policy, as code

Clicking is fine for trying things out, but a policy that decides who reads production secrets deserves review and history, like any other change. Write it as a file (the file is what you'd commit and review) and apply it:

```bash
mkdir -p ~/lab/my-vault && cd ~/lab/my-vault
cat > app-read.hcl <<'EOF'
# The app reads its own secret, nothing else.
path "team/data/app" {
  capabilities = ["read"]
}
EOF
bao policy write app-read app-read.hcl
```

Same name, same rules: the write changed nothing, which is what you want when a file and the live system agree.

## 5. A token for the app, and proof

Make a short-lived token that carries only `app-read`:

```bash
APP_TOKEN=$(bao token create -policy=app-read -ttl=15m -field=token)
BAO_TOKEN=$APP_TOKEN bao token lookup
```

`policies` is `[app-read default]`, `ttl` about 15 minutes, and there is no `entity_id`: it's a token for a program, not a person. Now test it. `BAO_TOKEN=...` in front of a command uses that token for that one command:

```bash
BAO_TOKEN=$APP_TOKEN bao kv get team/app                 # works
BAO_TOKEN=$APP_TOKEN bao kv get team/admin               # permission denied
BAO_TOKEN=$APP_TOKEN bao kv put team/app api_key=stolen  # permission denied
BAO_TOKEN=$APP_TOKEN bao secrets list                    # permission denied
```

It does exactly one thing. If it leaks, the damage is one secret, for 15 minutes at most.

## 6. Revoke it

You don't have to wait 15 minutes:

```bash
bao token revoke "$APP_TOKEN"
BAO_TOKEN=$APP_TOKEN bao kv get team/app     # permission denied: the token is gone
```

Tokens form a tree: this one is a child of yours, so revoking yours would have revoked it too. That's how you cut off everything a leaked credential handed out, in one go.

Leave your namespace for the next labs:

```bash
unset BAO_NAMESPACE
```

## Check yourself

1. Why does the policy say `team/data/app` and not `team/app`? *(KV v2 keeps values under `data/`. Lab 2, step 4.)*
2. The app's token leaks. List two things that limit the damage. *(Least-privilege policy: one secret, read only. Short TTL, and it can be revoked at once.)*
3. Why keep policies in files? *(Review, history and rollback, like any code. The UI is for exploring.)*

**Rules used:** 1 (least privilege), 3 (short-lived and revocable), 7 (plan for leaks: revocation is routine).
