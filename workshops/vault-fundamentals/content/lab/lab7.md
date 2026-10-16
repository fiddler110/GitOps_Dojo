# Lab 7 — Encrypted config in the repo

**Goal:** keep a config file with secrets in git, encrypted, with **sops**. The key that opens it never leaves the vault: OpenBao's **transit** engine does the encrypting and decrypting, and the vault decides who may. Then change who can read it, and rotate the key.

GitOps wants everything in git, and secrets are part of the config. Lab 1 showed why plaintext can't go there. Encrypted, it can.

**In this lab you will:**

1. Make an encryption key in your namespace that nobody can read out.
2. Tell sops to use it, with a small config file.
3. Write a config file with secrets in it, and encrypt it.
4. Commit it, and make `git diff` show real changes.
5. Make a token that may encrypt but not decrypt, as a CI job would have.
6. Rotate the key, then retire the old version.

---

## 1. A key in your vault

**Transit** is encryption as a service: you send it data, it sends back ciphertext (or the reverse), and the key itself can't be read out. You enable it in your namespace, make a key called `sops` (`-f` because the request has no data), and look at it.

```text
bao secrets enable transit
bao write -f transit/keys/<name>
```

**Your turn:** run these. Before the last line, predict: can you read the key material out?

```sh
export BAO_NAMESPACE=students/$USER
bao secrets enable transit
bao write -f transit/keys/sops
bao read transit/keys/sops       # latest_version 1, exportable false
```

<!-- dojo-reveal: Result of making the key -->

`latest_version` is 1 and `exportable` is false: there is no request that returns this key. Everything that uses it has to ask the vault.

<!-- /dojo-reveal -->


## 2. Tell sops which key to use

A `.sops.yaml` at the top of the repo tells sops which files to encrypt and with what. It has two parts:

- `path_regex`: this rule is for files whose names end in `.enc.yaml` (`\.` is a literal dot, `$` the end of the name).
- `hc_vault_transit_uri`: the key, as a URL: the vault's address, your namespace, then the key's path. So the file carries everything sops needs, and anyone who clones the repo uses the same key (if the vault lets them).

Make a repo for the config:

```sh
mkdir -p ~/lab/config-repo && cd ~/lab/config-repo
git init -b main
```

In VS Code, open or create **config-repo → `.sops.yaml`** and add this (the lab page fills in your user name; if you see student**XX**, replace it with yours):

```yaml
creation_rules:
  - path_regex: \.enc\.yaml$
    hc_vault_transit_uri: http://openbao:8200/v1/students/studentXX/transit/keys/sops
```

Save it. sops signs in with your token from `~/.vault-token`, like `hvac` in Lab 5.

## 3. Encrypt a config file

`sops encrypt -i <file>` encrypts a file in place (`-i` writes the result back into the same file). That's **envelope encryption**: sops makes a random **data key** for the file and encrypts the values with it, then asks transit to encrypt the data key (`vault:v1` is key version 1) and keeps only that encrypted copy. To read the file you need the data key, and only the vault can decrypt it, checking your policy every time. `sops decrypt` reads it back, whole or one value (`--extract` takes the path to the value, key by key).

```text
sops encrypt -i <file>
sops decrypt [--extract '["a"]["b"]'] <file>
```

In VS Code, create **config-repo → `app.enc.yaml`**, a normal config file with two secrets in it, and save it:

```yaml
database:
  host: db.internal
  password: s3cr3t-db-pass
api:
  url: https://api.example.test
  key: s3cr3t-api-key
```

**Your turn:** encrypt it, then look at it. Before you do, predict: will the key names still be readable? And the values?

```sh
sops encrypt -i app.enc.yaml
cat app.enc.yaml
```

<!-- dojo-reveal: Result of encrypting -->

VS Code shows the file change too. The **keys** are still readable (`database`, `password`, ...), so a reviewer can see what changed; the **values** are `ENC[AES256_GCM,...]`. At the bottom, under `sops:` → `hc_vault`, are the key's URL and `enc: vault:v1:...`.

<!-- /dojo-reveal -->

The plaintext sat in a file for a moment before `sops encrypt`, and your editor may keep its own copy (VS Code's local history keeps earlier saves of a file). At work, `sops edit app.enc.yaml` opens the decrypted file in a temporary editor and writes it back encrypted, so the plaintext never lands in the repo folder.

**Your turn:** read it back, whole or one value:

```sh
sops decrypt app.enc.yaml
sops decrypt --extract '["database"]["password"]' app.enc.yaml
```

<!-- dojo-reveal: Result of decrypting -->

The first prints the original plaintext file; the second prints just `s3cr3t-db-pass`.

<!-- /dojo-reveal -->

## 4. Commit it, and make diffs readable

A diff of two encrypted files is noise. Git can decrypt both sides for you, only on your machine, only if you can decrypt. Two pieces do it: `.gitattributes` tells git which files get a special diff, and `git config` says what that diff runs (`sops decrypt`, to turn each side into text first).

In VS Code, create **config-repo → `.gitattributes`** with one line, and save. `sops set` (used below) changes one value in place, encrypting as it goes (the new value is JSON, hence the quotes inside quotes).

```text
*.enc.yaml diff=sopsdiffer
```

**Your turn:** set up the diff, commit everything, then change the password. Before the two diffs, predict which one shows the real change and which is noise.

```sh
git config diff.sopsdiffer.textconv "sops decrypt"
git add .
git commit -m "Add the app's encrypted config"
sops set app.enc.yaml '["database"]["password"]' '"n3w-db-pass"'
git diff                  # the real change: one line
git diff --no-textconv    # what anyone without the key sees
git commit -am "Rotate the database password"
```

<!-- dojo-reveal: Results of the two diffs -->

`git diff` shows the real change: one line, old password to new. `git diff --no-textconv` shows only changed ciphertext, which is all anyone without the key sees.

<!-- /dojo-reveal -->


## 5. Who can decrypt?

Your token can do both. A CI job that only *writes* config shouldn't be able to *read* it, so you make a policy that can encrypt and nothing else. Transit's encrypt is a write (`update`) to `transit/encrypt/<key>`; decrypt would be `transit/decrypt/<key>`, and the policy doesn't mention it, so it's refused. sops takes a token from `VAULT_TOKEN` too, and putting it in front of a command uses it for that one command.

In VS Code, create **config-repo → `sops-encrypt.hcl`**:

```hcl
# Encrypt with the sops key; decrypting is not allowed.
path "transit/encrypt/sops" {
  capabilities = ["update"]
}
```

Save it.

**Your turn:** upload it and make a 15-minute token with only this policy (as in Lab 4), then try to decrypt with it. Predict the result.

```sh
bao policy write sops-encrypt sops-encrypt.hcl
ENC_TOKEN=$(bao token create -orphan -policy=sops-encrypt -ttl=15m -field=token)
VAULT_TOKEN=$ENC_TOKEN sops decrypt app.enc.yaml        # 403 permission denied
```

<!-- dojo-reveal: Result of the decrypt attempt -->

Refused with a 403: that token can't decrypt.

<!-- /dojo-reveal -->

Now the job it's for. In VS Code, create **config-repo → `ci.enc.yaml`**, and save:

```yaml
region: north
license: abc-123
```

**Your turn:** encrypt it with the encrypt-only token, then read it with yours. Predict which step works.

```sh
VAULT_TOKEN=$ENC_TOKEN sops encrypt -i ci.enc.yaml      # works
sops decrypt ci.enc.yaml                                # you can read it
```

<!-- dojo-reveal: Result of the encrypt-only job -->

Both work: the encrypt-only token encrypts, and your own token decrypts.

<!-- /dojo-reveal -->

Who can read the config is now a vault policy, not "whoever has the repo". Take a person's access away in the vault and every copy of every file is closed to them at once, and every decrypt is in the audit log.

## 6. Rotate the key

Rotating the transit key makes a new key version. Old versions still decrypt, so nothing breaks. Then `sops rotate` makes a new data key, re-encrypts the values with it, and has transit encrypt the new data key with the newest key version.

**Your turn:** make a new version of the transit key. Predict: does the file still open, and which version does it name?

```sh
bao write -f transit/keys/sops/rotate
sops decrypt app.enc.yaml > /dev/null && echo "still opens"
grep 'enc: vault' app.enc.yaml       # still vault:v1
```

<!-- dojo-reveal: Result of rotating the key -->

It prints `still opens`, and the file still names `vault:v1`.

<!-- /dojo-reveal -->

**Your turn:** re-encrypt the file with the newest version. Predict what the `grep` shows now.

```sh
sops rotate -i app.enc.yaml
grep 'enc: vault' app.enc.yaml       # vault:v2
git commit -am "Re-key the app config"
```

<!-- dojo-reveal: Result of sops rotate -->

`vault:v2`.

<!-- /dojo-reveal -->


## 7. Retire the old key version

The commit before this one still holds a copy encrypted with `vault:v1`, and so does every clone and backup. `min_decryption_version` tells transit to stop decrypting older versions. `git show HEAD~1:<file>` prints a file as it was one commit back.

```text
bao write transit/keys/<name>/config min_decryption_version=<n>
```

**Your turn:** retire version 1, pull the old file out of git history into `old.enc.yaml`, and try both. Predict which one opens.

```sh
bao write transit/keys/sops/config min_decryption_version=2
git show HEAD~1:app.enc.yaml > old.enc.yaml
sops decrypt old.enc.yaml            # fails: version 1 is retired
sops decrypt app.enc.yaml            # the current file still opens
rm old.enc.yaml
```

<!-- dojo-reveal: Result of retiring version 1 -->

The old file fails: version 1 is retired. The current file still opens.

<!-- /dojo-reveal -->

The readable `git diff` from step 4 can't open those old commits either now: `git log -p` stops at them with the same error. Retiring a key version closes every copy, yours included. `ci.enc.yaml` from step 5 was encrypted with version 1 too, so it's closed as well (try `sops decrypt ci.enc.yaml`): before you retire a version, `sops rotate` every file you still need.

Compare that with Lab 1: a plaintext secret in history stays readable forever. An encrypted one stops opening when the vault says so. (You still rotate the secrets themselves if the file leaked: someone may have decrypted it before.)

Clean up:

```sh
unset BAO_NAMESPACE
```

## Check yourself

1. The repo is public by mistake. What leaked?

<!-- dojo-reveal: Show the answer -->

Key names and ciphertext. Nobody can decrypt without access to the transit key in the vault.

<!-- /dojo-reveal -->

2. What does transit encrypt: the file or something else?

<!-- dojo-reveal: Show the answer -->

Only the file's data key, envelope encryption. The key never leaves the vault.

<!-- /dojo-reveal -->

3. How do you stop someone reading the config, including old copies they cloned?

<!-- dojo-reveal: Show the answer -->

Take away their decrypt policy; retire old key versions with `min_decryption_version`.

<!-- /dojo-reveal -->


**Rules used:** 8 (never in git in plaintext), 1 (least privilege: encrypt-only), 6 (every decrypt is audited), 7 (key rotation is routine).

**Next:** [lab8.md](lab8.md)
