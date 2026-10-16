# Lab 4 — You are the admin

**Goal:** run your own vault. In your own namespace you enable a secrets engine, write a least-privilege policy (in the UI, then as code), hand out a token with it, and prove what it can and can't do.

A **namespace** is a vault inside the vault: its own engines, policies, tokens and sign-in methods, invisible from the others. You are the admin of `students/<you>` and of nothing else. At work this is "the team's own vault"; on Azure it would be a Key Vault per team or per environment.

**In this lab you will:**

1. Switch your terminal to your own namespace.
2. Turn on a KV engine there and store two secrets: one for an app, one for admins only.
3. Write a policy that lets the app read its secret and nothing else, first in the UI, then as a file.
4. Make a token with only that policy, and prove what it can and can't do.
5. Revoke the token.

**Starting here?** Nothing from earlier labs is needed: this lab makes everything it uses. Your terminal is already signed in to the vault (Lab 0). For step 3, open the **Vault** card and sign in with **OIDC** first (Lab 0, step 2). Two words you'll meet: a **policy** is a list of paths, each with what may be done there (Lab 3, step 4); a **token** is what every request shows the vault to say who's asking (Lab 0, step 3).

---

## 1. Step into your namespace

`export` sets a shell variable for this terminal and every command it runs. `bao` reads `BAO_NAMESPACE` and sends each request to that namespace, so from now on your commands go to `students/<you>`. `bao secrets list` shows the engines there. `export` lasts only as long as this terminal: if you open a new one during the lab, run the `export` line again there, or `bao` talks to the root namespace and can't find `team/`. `-namespace=` points one command somewhere else.

```text
export BAO_NAMESPACE=students/<you>
bao secrets list [-namespace=<ns>]
```

**Your turn:** step in and list the engines, then try your neighbour's namespace. Before you run it, predict: will there be a `secret/` engine, and will the neighbour's list work?

```sh
export BAO_NAMESPACE=students/$USER
bao secrets list
bao secrets list -namespace=students/student02
```

<!-- dojo-reveal: Results of the namespace listings -->

You see the built-in engines, plus `database/`, which setup made for Lab 12. No `secret/`: the class's shared vault (Lab 3) is in the root namespace, not in yours. The neighbour's gives `permission denied`: admin of your own vault, nobody else's.

<!-- /dojo-reveal -->

## 2. Enable an engine and store the team's secrets

A namespace starts empty. **Enable** a KV version 2 engine at the path `team/` (the same kind as `secret/`), put two secrets in it, and list them. `team/app` is what an app needs; `team/admin` is something it must never see. The next step makes sure of that.

```text
bao secrets enable -path=<path> kv-v2
```

**Your turn:** run these. (If the first `put` says the mount is upgrading, wait two seconds and run it again.) Predict what `kv list` shows.

```sh
bao secrets enable -path=team kv-v2
echo '{"db_password": "app-db-pass", "api_key": "app-api-key"}' | bao kv put team/app -
printf '%s' 'do-not-share' | bao kv put team/admin root_password=-
bao kv list team/
```

<!-- dojo-reveal: Result of the listing -->

The list shows the two names, `admin` and `app`.

<!-- /dojo-reveal -->

## 3. A least-privilege policy, in the UI

The app should read `team/app` and nothing else. Anything a policy doesn't allow is refused, so the policy needs one rule. It reads: on the path `team/data/app` (KV v2 keeps values under `data/`, Lab 3), allow `read`, and nothing else.

```hcl
path "team/data/app" {
  capabilities = ["read"]
}
```

**Your turn:** in the Vault tab:

1. Switch to your namespace: click the **namespace picker** at the bottom of the side menu (it says `root`), open **students**, and choose your name. (Or add `?namespace=students/<you>` to the end of the address.) The picker now shows your name.
2. Open **Policies → ACL policies → Create ACL policy**.
3. Name it `app-read`, and give it the body above.
4. Click **Create policy**.

Check it arrived, from the terminal. Predict what you'll see:

```sh
bao policy list
bao policy read app-read
```

<!-- dojo-reveal: Results of checking the policy -->

`app-read` appears in the list (beside `default`), and `policy read` prints the rule you typed.

<!-- /dojo-reveal -->

## 4. The same policy, as code

Clicking is fine for trying things out, but a policy that decides who reads production secrets deserves review and history, like any other change. So keep it as a file: the file is what you'd commit and review. `bao policy write <name> <file>` uploads it. From now on, a change to this policy is a change to the file: reviewed, then `bao policy write`.

```text
bao policy write <name> <file>
```

Make a folder for it, and go there:

```sh
mkdir -p ~/lab/my-vault && cd ~/lab/my-vault
```

In VS Code, create **my-vault → `app-read.hcl`** with the same rule, and a comment that says why (`#` starts a comment in HCL, the language vault policies are written in):

```hcl
# The app reads its own secret, nothing else.
path "team/data/app" {
  capabilities = ["read"]
}
```

**Your turn:** save it, then upload it under the same name, `app-read`, and read it back. Predict: what changes in what the vault enforces?

```sh
bao policy write app-read app-read.hcl
bao policy read app-read
```

<!-- dojo-reveal: Result of the upload -->

Same name, same rule, now with its comment: nothing the vault enforces changed, which is what you want when a file and the live system agree.

<!-- /dojo-reveal -->

## 5. A token for the app, and proof

There's no app to build here: you play the app. Its whole job is to read `team/app`, so you make the token an app would be given, then use that token yourself and see what it's allowed. (Lab 5 writes an app, and Lab 6 gives it this same `app-read` policy through an identity of its own.)

A **token** is what a program shows the vault on every request. You'll make one that carries only `app-read` and lives 15 minutes. `$(...)` runs the command inside it and puts its output in `APP_TOKEN`; `-field=token` makes that output just the token.

Why `-orphan`? A token you make normally is your token's **child**, and it carries your identity along with it (your entity, and with it your `student` policy), which is the opposite of what an app should get. An orphan stands on its own: no parent, no identity, only the policy you gave it.

```text
bao token create -orphan -policy=<name> -ttl=<time> -field=token
```

**Your turn:** make the token and look it up. Before you run it, predict what `policies`, `ttl` and `entity_id` will say.

```sh
APP_TOKEN=$(bao token create -orphan -policy=app-read -ttl=15m -field=token)
BAO_TOKEN=$APP_TOKEN bao token lookup
```

<!-- dojo-reveal: Result of the token lookup -->

`policies` is `[app-read default]`, `ttl` about 15 minutes, and `entity_id` is `n/a`: it's a token for a program, not a person.

<!-- /dojo-reveal -->

Now test it. `BAO_TOKEN=...` in front of a command uses that token for that one command. Predict which of the four work:

```sh
BAO_TOKEN=$APP_TOKEN bao kv get team/app                 # works
BAO_TOKEN=$APP_TOKEN bao kv get team/admin               # permission denied
BAO_TOKEN=$APP_TOKEN bao kv put team/app api_key=stolen  # permission denied
BAO_TOKEN=$APP_TOKEN bao secrets list                    # permission denied
```

<!-- dojo-reveal: Results of the four tests -->

Only the first works. The token does exactly one thing. If it leaks, the damage is one secret, for 15 minutes at most.

<!-- /dojo-reveal -->

## 6. Revoke it

You don't have to wait 15 minutes. Normal tokens form a tree: revoking a token revokes every child it made, which is how you cut off everything a leaked credential handed out, in one go. An orphan is outside that tree, so you revoke it by itself, as here.

**Your turn:** revoke the token, then try it again. Predict the result.

```sh
bao token revoke "$APP_TOKEN"
BAO_TOKEN=$APP_TOKEN bao kv get team/app
```

<!-- dojo-reveal: Result after revoking -->

`permission denied`: the token is gone.

<!-- /dojo-reveal -->

Clean up: leave your namespace for the next labs.

```sh
unset BAO_NAMESPACE
```

## Check yourself

1. Why does the policy say `team/data/app` and not `team/app`?

<!-- dojo-reveal: Show the answer -->

KV v2 keeps values under `data/`. Lab 3, step 4.

<!-- /dojo-reveal -->

2. The app's token leaks. List two things that limit the damage.

<!-- dojo-reveal: Show the answer -->

Least-privilege policy: one secret, read only. Short TTL, and it can be revoked at once.

<!-- /dojo-reveal -->

3. Why keep policies in files?

<!-- dojo-reveal: Show the answer -->

Review, history and rollback, like any code. The UI is for exploring.

<!-- /dojo-reveal -->

**Rules used:** 1 (least privilege), 3 (short-lived and revocable), 7 (plan for leaks: revocation is routine).

**Next:** [lab5.md](lab5.md)

---

## Challenge c1 (bonus)

Only when your class has achievements on (you see a score on your landing page). A challenge is a goal with no steps, in a repo of your own, for extra points. Start it in the terminal:

```sh
dojo challenge start c1
cd ~/lab/challenge-secret
```

That makes your own repo `$USER/challenge-secret`, clones it to `~/lab/challenge-secret` and shows your brief. The brief is saved as `~/challenge-c1.md` with your own names filled in; read it again any time with `glow ~/challenge-c1.md`. When you think it's done:

```sh
dojo check c1
```

A wrong answer costs nothing. `dojo check hint c1` gives a hint for part of the points (hints already used stay used).

**Start over.** `dojo challenge reset c1` deletes `~/lab/challenge-secret` (including any uncommitted work), builds a fresh copy and clones it, as often as you like.

## The Shared Secret

A teammate's app needs to read one of your secrets, and only that one. The repo's `seed.sh`, run with your own token, makes two secrets in your namespace and an AppRole for the teammate's app with no policy yet. Give the app read access to one secret and to nothing else in your namespace.

**End result (what the check looks for)**

- In your namespace `students/$USER`, the app's AppRole (`buddy-$USER`) has a policy other than `default`.
- Together its policies allow reading `challenge/one`.
- They do not allow reading `challenge/two`.

