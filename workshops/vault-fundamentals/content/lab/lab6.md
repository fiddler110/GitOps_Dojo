# Lab 6 — Encrypted config in the repo

**Goal:** keep a config file with secrets in git, encrypted, with **sops**. The key that opens it never leaves the vault: OpenBao's **transit** engine does the encrypting and decrypting, and the vault decides who may. Then change who can read it, and rotate the key.

GitOps wants everything in git, and secrets are part of the config. Lab 1 showed why plaintext can't go there. Encrypted, it can.

---

## 1. A key in your vault

**Transit** is encryption as a service: you send it data, it sends back ciphertext (or the reverse), and the key itself can't be read out. Enable it in your namespace and make a key for sops:

```bash
export BAO_NAMESPACE=students/$USER
bao secrets enable transit
bao write -f transit/keys/sops
bao read transit/keys/sops       # latest_version 1, exportable false
```

## 2. Tell sops which key to use

A `.sops.yaml` at the top of the repo says which files to encrypt and with what. The key's URL has your namespace in its path, so the file carries everything sops needs:

```bash
mkdir -p ~/lab/config-repo && cd ~/lab/config-repo
git init -b main
cat > .sops.yaml <<EOF
creation_rules:
  - path_regex: \.enc\.yaml$
    hc_vault_transit_uri: $VAULT_ADDR/v1/students/$USER/transit/keys/sops
EOF
cat .sops.yaml
```

sops reads your token from `~/.vault-token`, like `hvac` in Lab 4.

## 3. Encrypt a config file

```bash
cat > app.enc.yaml <<'EOF'
database:
  host: db.internal
  password: s3cr3t-db-pass
api:
  url: https://api.example.test
  key: s3cr3t-api-key
EOF
sops encrypt -i app.enc.yaml
cat app.enc.yaml
```

The **keys** are still readable (`database`, `password`, ...), so a reviewer can see what changed; the **values** are `ENC[AES256_GCM,...]`. At the bottom, under `sops:` → `hc_vault`, is the key's URL and `enc: vault:v1:...`.

That's **envelope encryption**: sops made a random data key for this file and encrypted the values with it, then asked transit to encrypt the data key (`vault:v1` is key version 1). Only the vault can unwrap the data key, and it checks your policy every time.

(Here the plaintext sat in a file for a moment before `sops encrypt`. At work, `sops edit app.enc.yaml` opens an editor and writes it encrypted, so the plaintext never lands on disk.)

Read it back, whole or one value:

```bash
sops decrypt app.enc.yaml
sops decrypt --extract '["database"]["password"]' app.enc.yaml
```

## 4. Commit it, and make diffs readable

A diff of two encrypted files is noise. Git can decrypt both sides for you, only on your machine, only if you can decrypt:

```bash
echo '*.enc.yaml diff=sopsdiffer' > .gitattributes
git config diff.sopsdiffer.textconv "sops decrypt"
git add .
git commit -m "Add the app's encrypted config"
```

Change the password and look at the diff:

```bash
sops set app.enc.yaml '["database"]["password"]' '"n3w-db-pass"'
git diff                  # the real change: one line
git diff --no-textconv    # what anyone without the key sees
git commit -am "Rotate the database password"
```

## 5. Who can decrypt?

Your token can do both. A CI job that only *writes* config shouldn't be able to *read* it. Make a policy that can encrypt and nothing else, and a token with it:

```bash
cat > sops-encrypt.hcl <<'EOF'
# Encrypt with the sops key; decrypting is not allowed.
path "transit/encrypt/sops" {
  capabilities = ["update"]
}
EOF
bao policy write sops-encrypt sops-encrypt.hcl
ENC_TOKEN=$(bao token create -orphan -policy=sops-encrypt -ttl=15m -field=token)
```

sops takes a token from `VAULT_TOKEN` too:

```bash
VAULT_TOKEN=$ENC_TOKEN sops decrypt app.enc.yaml        # 403 permission denied
printf 'region: north\nlicense: abc-123\n' > ci.enc.yaml
VAULT_TOKEN=$ENC_TOKEN sops encrypt -i ci.enc.yaml      # works
sops decrypt ci.enc.yaml                                # you can read it
```

Who can read the config is now a vault policy, not "whoever has the repo". Take a person's access away in the vault and every copy of every file is closed to them at once, and every decrypt is in the audit log.

## 6. Rotate the key

Make a new version of the transit key:

```bash
bao write -f transit/keys/sops/rotate
sops decrypt app.enc.yaml > /dev/null && echo "still opens"
grep 'enc: vault' app.enc.yaml       # still vault:v1
```

Old versions still decrypt, so nothing breaks. Re-wrap the file with the newest version (sops also makes a new data key):

```bash
sops rotate -i app.enc.yaml
grep 'enc: vault' app.enc.yaml       # vault:v2
git commit -am "Re-key the app config"
```

## 7. Retire the old key version

The commit before this one still holds a copy wrapped with `vault:v1`, and so does every clone and backup. Tell transit to stop decrypting version 1:

```bash
bao write transit/keys/sops/config min_decryption_version=2
git show HEAD~1:app.enc.yaml > old.enc.yaml
sops decrypt old.enc.yaml            # fails: version 1 is retired
sops decrypt app.enc.yaml            # the current file still opens
rm old.enc.yaml
```

The readable `git diff` from step 4 can't open those old commits either now: `git log -p` stops at them with the same error. Retiring a key version closes every copy, yours included.

Compare that with Lab 1: a plaintext secret in history stays readable forever. An encrypted one stops opening when the vault says so. (You still rotate the secrets themselves if the file leaked: someone may have decrypted it before.)

```bash
unset BAO_NAMESPACE
```

## Check yourself

1. The repo is public by mistake. What leaked? *(Key names and ciphertext. Nobody can decrypt without access to the transit key in the vault.)*
2. What does transit encrypt: the file or something else? *(Only the file's data key, envelope encryption. The key never leaves the vault.)*
3. How do you stop someone reading the config, including old copies they cloned? *(Take away their decrypt policy; retire old key versions with `min_decryption_version`.)*

**Rules used:** 8 (never in git in plaintext), 1 (least privilege: encrypt-only), 6 (every decrypt is audited), 7 (key rotation is routine).
