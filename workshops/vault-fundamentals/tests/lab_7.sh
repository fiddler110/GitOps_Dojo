#!/bin/sh
# vault-fundamentals lab 7 (with the stack up): sops with OpenBao transit: encrypt, diff, rotate, close the old key.
# Resets what it leaves behind first, so it can run again. Exits 1 on any failure.
#   sh workshops/vault-fundamentals/tests/lab_7.sh [student03]
. "$(dirname "$0")/lib.sh"

echo "== reset $s"
as 'rm -rf ~/lab/config-repo; export BAO_NAMESPACE=students/$USER
    bao secrets disable transit; bao policy delete sops-encrypt' >/dev/null 2>&1
git_identity

echo "== lab 7: sops + transit"
ok   "transit and the sops key" 'export BAO_NAMESPACE=students/$USER; bao secrets enable transit && bao write -f transit/keys/sops'
ok   "encrypt with .sops.yaml" 'mkdir -p ~/lab/config-repo && cd ~/lab/config-repo && git init -q -b main &&
    printf "creation_rules:\n  - path_regex: \\\\.enc\\\\.yaml\$\n    hc_vault_transit_uri: $VAULT_ADDR/v1/students/$USER/transit/keys/sops\n" > .sops.yaml &&
    printf "database:\n  host: db.internal\n  password: s3cr3t-db-pass\napi:\n  url: https://api.example.test\n  key: s3cr3t-api-key\n" > app.enc.yaml &&
    sops encrypt -i app.enc.yaml'
lacks "no plaintext in the file" 'cat ~/lab/config-repo/app.enc.yaml' 's3cr3t-db-pass'
has  "decrypts one value" 'cd ~/lab/config-repo && sops decrypt --extract "[\"database\"][\"password\"]" app.enc.yaml' 's3cr3t-db-pass'
has  "textconv diff shows the change" 'cd ~/lab/config-repo && echo "*.enc.yaml diff=sopsdiffer" > .gitattributes &&
    git config diff.sopsdiffer.textconv "sops decrypt" && git add . && git commit -qm c1 &&
    sops set app.enc.yaml "[\"database\"][\"password\"]" "\"n3w-db-pass\"" && git diff' '+    password: n3w-db-pass'
ok   "commit" 'cd ~/lab/config-repo && git commit -qam c2'
has  "encrypt-only token can't decrypt" 'export BAO_NAMESPACE=students/$USER; cd ~/lab/config-repo &&
    printf "path \"transit/encrypt/sops\" {\n  capabilities = [\"update\"]\n}\n" | bao policy write sops-encrypt - >/dev/null &&
    T=$(bao token create -orphan -policy=sops-encrypt -ttl=15m -field=token) &&
    VAULT_TOKEN=$T sops decrypt app.enc.yaml' 'permission denied'
ok   "encrypt-only token can encrypt" 'export BAO_NAMESPACE=students/$USER; cd ~/lab/config-repo &&
    T=$(bao token create -orphan -policy=sops-encrypt -ttl=15m -field=token) &&
    printf "region: north\n" > ci.enc.yaml && VAULT_TOKEN=$T sops encrypt -i ci.enc.yaml && sops decrypt ci.enc.yaml'
has  "rotate the key, sops rotate -i gives vault:v2" 'export BAO_NAMESPACE=students/$USER; cd ~/lab/config-repo &&
    bao write -f transit/keys/sops/rotate >/dev/null && sops decrypt app.enc.yaml >/dev/null &&
    sops rotate -i app.enc.yaml && git commit -qam c3 && grep "enc: vault" app.enc.yaml' 'vault:v2'
has  "min_decryption_version=2 closes the old commit" 'export BAO_NAMESPACE=students/$USER; cd ~/lab/config-repo &&
    bao write transit/keys/sops/config min_decryption_version=2 >/dev/null &&
    git show HEAD~1:app.enc.yaml > old.enc.yaml; sops decrypt old.enc.yaml; rm -f old.enc.yaml' 'Error'
ok   "the current file still opens" 'cd ~/lab/config-repo && sops decrypt app.enc.yaml'
finish "lab 7"
