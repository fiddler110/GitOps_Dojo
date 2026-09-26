# Lab 4 — You are the admin

**Goal:** run your own vault. In your own namespace you enable a secrets engine, write a least-privilege policy (in the UI, then as code), hand out a token with it, and prove what it can and can't do.

A **namespace** is a vault inside the vault: its own engines, policies, tokens and sign-in methods, invisible from the others. You are the admin of `students/<you>` and of nothing else. At work this is "the team's own vault"; on Azure it would be a Key Vault per team or per environment.

**In this lab you will:**

1. Switch your terminal to your own namespace.
2. Turn on a KV engine there and store two secrets: one for an app, one for admins only.
3. Write a policy that lets the app read its secret and nothing else, first in the UI, then as a file.
4. Make a token with only that policy, and prove what it can and can't do.
5. Revoke the token.

---

## 1. Step into your namespace

`export` sets a shell variable for this terminal and every command it runs. `bao` reads `BAO_NAMESPACE` and sends each request to that namespace, so from now on your commands go to `students/<you>`. `bao secrets list` shows the engines there:

```bash
export BAO_NAMESPACE=students/$USER
bao secrets list
```

Only the built-in engines: `secret/` from Lab 3 is in the root namespace, not in yours. `-namespace=` points one command somewhere else. Try your neighbour's:

```bash
bao secrets list -namespace=students/student02
```

`permission denied`. Admin of your own vault, nobody else's.

## 2. Enable an engine and store the team's secrets

A namespace starts empty. **Enable** a KV version 2 engine at the path `team/` (the same kind as `secret/`), put two secrets in it, and list them:

```bash
bao secrets enable -path=team kv-v2
bao kv put team/app db_password=app-db-pass api_key=app-api-key
bao kv put team/admin root_password=do-not-share
bao kv list team/
```

(If the first `put` says the mount is upgrading, wait two seconds and run it again.)

`team/app` is what an app needs; `team/admin` is something it must never see. The next step makes sure of that.

## 3. A least-privilege policy, in the UI

The app should read `team/app` and nothing else. Anything a policy doesn't allow is refused, so the policy needs one rule. In the Vault tab:

1. Switch to your namespace: click the **namespace picker** at the bottom of the side menu (it says `root`), open **students**, and choose your name. (Or add `?namespace=students/<you>` to the end of the address.) The picker now shows your name.
2. Open **Policies → ACL policies → Create ACL policy**.
3. Name it `app-read`, and give it this body:

   ```hcl
   path "team/data/app" {
     capabilities = ["read"]
   }
   ```

4. Click **Create policy**.

The rule reads: on the path `team/data/app` (KV v2 keeps values under `data/`, Lab 3), allow `read`, and nothing else. Check it arrived, from the terminal:

```bash
bao policy list
bao policy read app-read
```

## 4. The same policy, as code

Clicking is fine for trying things out, but a policy that decides who reads production secrets deserves review and history, like any other change. So keep it as a file: the file is what you'd commit and review.

Make a folder for it, and go there:

```bash
mkdir -p ~/lab/my-vault && cd ~/lab/my-vault
```

In VS Code, create **my-vault → `app-read.hcl`** with the same rule, and a comment that says why (`#` starts a comment in HCL, the language vault policies are written in):

```hcl
# The app reads its own secret, nothing else.
path "team/data/app" {
  capabilities = ["read"]
}
```

Save it, then upload it to the vault under the same name, `app-read`, and read it back:

```bash
bao policy write app-read app-read.hcl
bao policy read app-read
```

Same name, same rule, now with its comment: nothing the vault enforces changed, which is what you want when a file and the live system agree. From now on, a change to this policy is a change to the file: reviewed, then `bao policy write`.

## 5. A token for the app, and proof

A **token** is what a program shows the vault on every request. Make one that carries only `app-read` and lives 15 minutes. `$(...)` runs the command inside it and puts its output in `APP_TOKEN`; `-field=token` makes that output just the token. Then look the new token up:

```bash
APP_TOKEN=$(bao token create -orphan -policy=app-read -ttl=15m -field=token)
BAO_TOKEN=$APP_TOKEN bao token lookup
```

`policies` is `[app-read default]`, `ttl` about 15 minutes, and `entity_id` is empty: it's a token for a program, not a person.

Why `-orphan`? A token you make normally is your token's **child**, and it carries your identity along with it, which is the opposite of what an app should get. An orphan stands on its own: no parent, no identity, only the policy you gave it.

Now test it. `BAO_TOKEN=...` in front of a command uses that token for that one command:

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

Normal tokens form a tree: revoking a token revokes every child it made, which is how you cut off everything a leaked credential handed out, in one go. An orphan is outside that tree, so you revoke it by itself, as here.

Leave your namespace for the next labs:

```bash
unset BAO_NAMESPACE
```

## Check yourself

1. Why does the policy say `team/data/app` and not `team/app`? *(KV v2 keeps values under `data/`. Lab 3, step 4.)*
2. The app's token leaks. List two things that limit the damage. *(Least-privilege policy: one secret, read only. Short TTL, and it can be revoked at once.)*
3. Why keep policies in files? *(Review, history and rollback, like any code. The UI is for exploring.)*

**Rules used:** 1 (least privilege), 3 (short-lived and revocable), 7 (plan for leaks: revocation is routine).

**Next:** [lab5.md](lab5.md)
