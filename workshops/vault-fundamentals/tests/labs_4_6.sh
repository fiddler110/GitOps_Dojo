#!/bin/sh
# vault-fundamentals labs 4-6 (T2.6), with the stack up: runs the labs' steps
# as one student signed in by the terminal's CLI login, and checks what each
# lab promises. It first removes what an earlier run left (the lab folders,
# approle and transit in the student's namespace, the app secret), so it can
# run again. Exits 1 on any failure.
#   sh workshops/vault-fundamentals/tests/labs_4_6.sh [student03]
s="${1:-student03}"; other=student01
failed=0
as() { podman exec -i workshop_terminal su - "$s" -c "$1"; }
ok()   { if out="$(as "$2" 2>&1)"; then echo "  ok:   $1"; else echo "  FAIL: $1: $(echo "$out" | tail -3)"; failed=1; fi; }
has()  { out="$(as "$2" 2>&1)"; case "$out" in *"$3"*) echo "  ok:   $1" ;; *) echo "  FAIL: $1: $(echo "$out" | tail -3)"; failed=1 ;; esac; }
lacks() { out="$(as "$2" 2>&1)"; case "$out" in *"$3"*) echo "  FAIL: $1: $(echo "$out" | tail -3)"; failed=1 ;; *) echo "  ok:   $1" ;; esac; }

echo "== reset $s"
as 'pkill -u "$USER" -f "[b]ao agent"; rm -rf ~/lab/app ~/lab/agent ~/lab/config-repo /dev/shm/$USER
    export BAO_NAMESPACE=students/$USER
    bao auth disable approle; bao secrets disable transit; bao secrets disable team
    unset BAO_NAMESPACE; bao kv metadata delete secret/students/$USER/app' >/dev/null 2>&1

echo "== lab 4: the app reads a secret"
as 'git config --global user.name "$USER"; git config --global user.email "$USER@dojo.test"' >/dev/null
lacks "a .env file stays out of git" 'mkdir -p ~/lab/app && cd ~/lab/app && git init -q -b main &&
    printf "DB_PASSWORD=dev-db-pass-123\nAPI_KEY=dev-api-key-456\n" > .env && echo .env > .gitignore &&
    printf "import os\nprint(len(os.environ[\"DB_PASSWORD\"]))\n" > app_env.py &&
    set -a && . ./.env && set +a && python3 app_env.py && git add . && git status --short' ' .env'
ok   "hvac is signed in with ~/.vault-token" 'python3 -c "import hvac, sys; sys.exit(not hvac.Client().is_authenticated())"'
ok   "puts the app secret" 'bao kv put secret/students/$USER/app db_password=vault-db-pass-789 api_key=vault-api-key-012'
as 'cat > ~/lab/app/app_vault.py' <<'EOF'
import logging
import os

import hvac

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(levelname)s %(message)s")
log = logging.getLogger("app")
client = hvac.Client()
resp = client.secrets.kv.v2.read_secret_version(
    mount_point="secret",
    path=f"students/{os.environ['USER']}/app",
    raise_on_deleted_version=True,
)
secret = resp["data"]["data"]
log.debug("loaded config: %s", secret)
log.info("read version %s of the app's secret", resp["data"]["metadata"]["version"])
log.info("connecting to the database with a %d-character password", len(secret["db_password"]))
EOF
has  "the app reads version 1" 'cd ~/lab/app && python3 app_vault.py' 'read version 1'
has  "after a patch it reads version 2" 'bao kv patch secret/students/$USER/app db_password=rotated-db-pass-000 >/dev/null && cd ~/lab/app && python3 app_vault.py' 'read version 2'
has  "DEBUG logs the secret" 'cd ~/lab/app && LOG_LEVEL=DEBUG python3 app_vault.py' 'rotated-db-pass-000'
lacks "the fixed line doesn't" 'cd ~/lab/app && sed -i "s/log.debug(\"loaded config: %s\", secret)/log.debug(\"loaded config keys: %s\", sorted(secret))/" app_vault.py && LOG_LEVEL=DEBUG python3 app_vault.py' 'rotated-db-pass-000'
ok   "renew_self" 'python3 -c "import hvac; c = hvac.Client(); c.auth.token.renew_self(); print(c.auth.token.lookup_self()[\"data\"][\"ttl\"])"'

echo "== lab 5: OpenBao Agent"
ok   "catch-up block (team/app, app-read)" 'export BAO_NAMESPACE=students/$USER
    bao secrets list | grep -q "^team/" || bao secrets enable -path=team kv-v2
    for i in 1 2 3 4 5; do bao kv put team/app db_password=app-db-pass api_key=app-api-key && break; sleep 2; done
    printf "path \"team/data/app\" {\n  capabilities = [\"read\"]\n}\n" | bao policy write app-read -'
ok   "approle role and the two IDs" 'export BAO_NAMESPACE=students/$USER
    bao auth enable approle && bao write auth/approle/role/app token_policies=app-read token_ttl=2m token_max_ttl=10m secret_id_ttl=1h &&
    mkdir -p ~/lab/agent && cd ~/lab/agent &&
    bao read -field=role_id auth/approle/role/app/role-id > role-id &&
    bao write -f -field=secret_id auth/approle/role/app/secret-id > secret-id && chmod 600 role-id secret-id'
as 'install -d -m 700 /dev/shm/$USER; cd ~/lab/agent; cat > agent.hcl <<EOF
vault {
  address = "$VAULT_ADDR"
}
auto_auth {
  method "approle" {
    namespace = "students/$USER"
    config = {
      role_id_file_path                   = "role-id"
      secret_id_file_path                 = "secret-id"
      remove_secret_id_file_after_reading = true
    }
  }
}
template_config {
  static_secret_render_interval = "5s"
}
template {
  destination = "/dev/shm/$USER/app.env"
  perms       = "0600"
  contents    = <<-EOT
  {{ with secret "team/data/app" }}DB_PASSWORD={{ .Data.data.db_password }}
  API_KEY={{ .Data.data.api_key }}{{ end }}
  EOT
}
EOF'
as 'cd ~/lab/agent && (nohup bao agent -config=agent.hcl > agent.log 2>&1 &) ; sleep 4' >/dev/null 2>&1
has  "the agent rendered the secret" 'cat /dev/shm/$USER/app.env' 'DB_PASSWORD=app-db-pass'
has  "the file is 0600" 'stat -c %a /dev/shm/$USER/app.env' '600'
lacks "the secret-id file is gone" 'ls ~/lab/agent' 'secret-id'
ok   "rotate in the vault" 'BAO_NAMESPACE=students/$USER bao kv patch team/app db_password=rotated-lab5'
as 'sleep 8' >/dev/null
has  "the agent re-rendered it" 'cat /dev/shm/$USER/app.env' 'DB_PASSWORD=rotated-lab5'
o="$(podman exec workshop_terminal su - "$other" -c "cat /dev/shm/$s/app.env" 2>&1)"
case "$o" in *rotated-lab5*) echo "  FAIL: $other can read it"; failed=1 ;; *) echo "  ok:   $other can't read it" ;; esac
as 'pkill -u "$USER" -f "[b]ao agent"; rm -rf /dev/shm/$USER' >/dev/null 2>&1

echo "== lab 6: sops + transit"
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

[ "$failed" = 0 ] && echo PASS || { echo FAILED; exit 1; }
