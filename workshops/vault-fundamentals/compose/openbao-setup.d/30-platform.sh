# vault-fundamentals setup hook: labs 11-12 start half-configured (PLAN.md S19,
# P4). Sourced by the openbao module's setup.sh on every start with the
# provisioner token; safe to re-run. In each student's namespace:
#   - auth/jwt-platform trusts app-host's platform identity: its public keys
#     (JWKS) and its issuer. The student writes the role (which slot may log
#     in) and the policy it gets (Lab 11).
#   - database/ holds the connection to the student's own Postgres database
#     as vault_<s>, whose first password (from app-db's first start) the vault
#     rotates at once, so no person knows it. The student writes the role that
#     says what a login made for an app may do (Lab 12).

platform=http://app-host:8080

for s in $(class_users); do
  export BAO_NAMESPACE="students/$s"

  bao auth list -format=json 2>/dev/null | grep -q '"jwt-platform/"' \
    || retry 10 bao auth enable -path=jwt-platform -description="app-host platform identity (lab 11)" jwt >/dev/null
  # OpenBao fetches the keys when this is written: wait for app-host.
  retry 120 bao write auth/jwt-platform/config jwks_url="$platform/.well-known/jwks.json" \
    bound_issuer="$platform" >/dev/null 2>&1 \
    || { log "platform: app-host's keys never answered for $s"; exit 1; }

  bao secrets list -format=json 2>/dev/null | grep -q '"database/"' \
    || retry 10 bao secrets enable -path=database -description="app-db logins made on demand (lab 12)" database >/dev/null
  if ! bao read database/config/app-db >/dev/null 2>&1; then
    retry 120 test -s "/app-db/$s" || { log "platform: no first password from app-db for $s"; exit 1; }
    # OpenBao logs in to check the connection when this is written: wait for
    # app-db (its first start sets up every database before it listens).
    retry 120 bao write database/config/app-db plugin_name=postgresql-database-plugin \
      connection_url="postgresql://{{username}}:{{password}}@app-db:5432/app_$s?sslmode=disable" \
      username="vault_$s" password=@"/app-db/$s" password_authentication=scram-sha-256 \
      allowed_roles="*" >/dev/null 2>&1 \
      || { log "platform: could not connect the vault to app_$s"; exit 1; }
    retry 10 bao write -f database/rotate-root/app-db >/dev/null
  fi
  unset BAO_NAMESPACE
done
log "platform: auth/jwt-platform and database/ in $(class_users | wc -l) namespaces"
