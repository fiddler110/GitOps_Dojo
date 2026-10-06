#!/bin/sh
# Target 11 `tfstate-treasure` (plan row 11, CTF-3, ties `tofu-basics` +
# `vault-fundamentals`): give each student their OWN `infra-state` Forgejo
# repo holding a committed terraform.tfstate -- state files are secrets too.
# The "resource" in it is an OpenBao AppRole login (role_id/secret_id)
# standing in for the cloud credential a real tfstate commonly leaks; it
# opens exactly one Vault path (secret/data/tfstate-treasure/<user>) holding
# this challenge's flag, a path the student's own OpenBao login has no
# policy for at all (modules/openbao's SSO/CLI login grants nothing in this
# pack -- see docker-compose.override.yml) -- the credential in the state
# file is the *only* way in.
#
# The matching Vault-side half (the policy, the AppRole role, the flag
# itself) is compose/openbao-setup.d/60-tfstate-treasure.sh, run in the
# openbao-setup container with the provisioner token. Both hooks derive the
# role_id/secret_id independently from STUDENT_PASSWORD_SEED, same HMAC-
# SHA256 formula as every flag/token in this range (flags.py's render()) --
# two copies, not shared code, same idiom as 55-git-secrets.sh's
# deploy_token_for; this container has python3 to do it directly, unlike
# openbao-setup's Alpine image (see that hook's comment).
#
# This pack only (workshop-level hook, 90+ prefix): reuses the same
# curl+netrc idiom as 90-ctf-defend-test.sh / 55-git-secrets.sh. Runs as
# root, after student accounts exist. Never fails the container: every wait
# is bounded, a timeout just skips that student with a warning.
set -u

admin_user="${FORGEJO_ADMIN_USER:-}"
admin_password="${FORGEJO_ADMIN_PASSWORD:-}"
if [ -z "$admin_user" ] || [ -z "$admin_password" ]; then
  echo "[tfstate-treasure] FORGEJO_ADMIN_USER/PASSWORD not set, skipping provisioning" >&2
  exit 0
fi

base_url="http://git-server:3000"
api="$base_url/api/v1"
repo_name="infra-state"
student_count="${STUDENT_COUNT:-0}"
student_prefix="${STUDENT_PREFIX:-student}"

netrc="$(mktemp)"
trap 'rm -f "$netrc"' EXIT
chmod 600 "$netrc"
printf 'machine git-server\n\tlogin %s\n\tpassword %s\n' "$admin_user" "$admin_password" > "$netrc"

api_curl() { curl --netrc-file "$netrc" "$@"; }
http_status() { api_curl -s -o /dev/null -w '%{http_code}' "$@"; }

log() { printf '[tfstate-treasure] %s\n' "$1"; }

# --- role_id/secret_id, same derivation as 60-tfstate-treasure.sh's --------
# derive(): flags.py's render() formula, minus the "flag{...}" wrapper.
derive() {
  python3 -c '
import hashlib, hmac, os, sys
challenge, user = sys.argv[1], sys.argv[2]
seed = os.environ.get("STUDENT_PASSWORD_SEED", "")
if not seed:
    print(f"dev-{challenge}-{user}")
else:
    print(hmac.new(seed.encode(), f"ctf:{challenge}:{user}".encode(), hashlib.sha256).hexdigest()[:16])
' "$1" "$2"
}
role_id_for()   { derive tfstate-treasure-role "$1"; }
secret_id_for() { derive tfstate-treasure-secret "$1"; }

# --- wait for the admin API (bounded: ~5 minutes) --------------------------
i=0
until [ "$(http_status "$api/user")" = "200" ]; do
  i=$((i + 1))
  if [ "$i" -ge 60 ]; then
    log "Forgejo admin API never became ready; skipping provisioning"
    exit 0
  fi
  sleep 5
done

counter=1
while [ "$counter" -le "$student_count" ]; do
  username="$(printf '%s%02d' "$student_prefix" "$counter")"
  counter=$((counter + 1))

  j=0
  while [ "$(http_status "$api/users/$username")" != "200" ]; do
    j=$((j + 1))
    if [ "$j" -ge 30 ]; then
      log "no Forgejo account for $username yet; skipping this student"
      continue 2
    fi
    sleep 2
  done

  if [ "$(http_status "$api/repos/$username/$repo_name")" = "200" ]; then
    log "repo '$username/$repo_name' already exists"
  else
    log "creating repo '$username/$repo_name'"
    api_curl -sf -X POST "$api/user/repos?sudo=$username" \
      -H 'Content-Type: application/json' \
      -d "{\"name\":\"$repo_name\",\"private\":false,\"auto_init\":false}" \
      >/dev/null || log "warning: could not create '$username/$repo_name'"
  fi

  repo_empty="$(api_curl -sf "$api/repos/$username/$repo_name" 2>/dev/null | grep -o '"empty":[a-z]*' | cut -d: -f2)"
  if [ "$repo_empty" != "true" ]; then
    log "'$username/$repo_name' already has history, leaving it alone"
    continue
  fi

  role_id="$(role_id_for "$username")"
  secret_id="$(secret_id_for "$username")"
  work="$(mktemp -d)"
  git -C "$work" init -q -b main
  git -C "$work" config user.name "$admin_user"
  git -C "$work" config user.email "ctf-range@example.com"

  cat > "$work/main.tf" <<'TF'
# Deploys the internal-tools backend. State is remote in theory; in practice
# someone ran `terraform apply` from their laptop once and never set that up.
terraform {
  required_providers {
    vault = { source = "hashicorp/vault" }
  }
}

provider "vault" {
  address = "http://openbao:8200"
}

resource "vault_approle_auth_backend_login" "deploy" {
  backend   = "approle"
  role_id   = var.deploy_role_id
  secret_id = var.deploy_secret_id
}
TF

  # terraform.tfstate: committed by hand (TODO still open), full of exactly
  # what a real tfstate file holds in plaintext -- the provider login this
  # run used.
  cat > "$work/terraform.tfstate" <<JSON
{
  "version": 4,
  "terraform_version": "1.9.0",
  "serial": 3,
  "lineage": "$(cat /proc/sys/kernel/random/uuid)",
  "outputs": {},
  "resources": [
    {
      "mode": "managed",
      "type": "vault_approle_auth_backend_login",
      "name": "deploy",
      "provider": "provider[\"registry.terraform.io/hashicorp/vault\"]",
      "instances": [
        {
          "schema_version": 0,
          "attributes": {
            "backend": "approle",
            "role_id": "$role_id",
            "secret_id": "$secret_id",
            "lease_duration": 900
          },
          "sensitive_attributes": []
        }
      ]
    }
  ]
}
JSON
  cat > "$work/README.md" <<'MD'
# infra-state

Deploy state for the internal-tools backend. `terraform.tfstate` is checked
in -- remote state is on the backlog (INFRA-241).
MD

  git -C "$work" add main.tf terraform.tfstate README.md
  git -C "$work" commit -q -m "Initial deploy"
  git -C "$work" push -q "http://$admin_user:$admin_password@git-server:3000/$username/$repo_name.git" main \
    || log "warning: could not push history to '$username/$repo_name'"
  rm -rf "$work"
  log "provisioned '$username/$repo_name'"
done

log "done"
exit 0
