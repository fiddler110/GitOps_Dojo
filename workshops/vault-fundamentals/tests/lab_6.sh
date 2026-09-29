#!/bin/sh
# vault-fundamentals lab 6 (with the stack up): OpenBao Agent: an approle, a rendered secret file, rotation, 0600.
# Resets what it leaves behind first, so it can run again. Exits 1 on any failure.
#   sh workshops/vault-fundamentals/tests/lab_6.sh [student03]
. "$(dirname "$0")/lib.sh"

echo "== reset $s"
as 'pkill -u "$USER" -f "[b]ao agent"; rm -rf ~/lab/agent /dev/shm/$USER
    export BAO_NAMESPACE=students/$USER
    bao auth disable approle; bao secrets disable team; bao policy delete app-read' >/dev/null 2>&1

echo "== lab 6: OpenBao Agent"
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
finish "lab 6"
