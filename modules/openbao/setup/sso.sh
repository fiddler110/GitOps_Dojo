# Single sign-on through Forgejo, sourced by setup.sh on every start with
# BAO_TOKEN set to the provisioner token (so log, retry and $state are here).
#
# Forgejo is the OIDC provider: an OAuth2 app owned by FORGEJO_ADMIN_USER,
# its client id and secret kept in $state/oidc-client. OpenBao's `oidc`
# method reaches Forgejo's public issuer through the SSO shim, trusting the
# shim's CA on an https:// name. Every account gets an identity entity named
# after its Forgejo login: students get the `student` policy (the workshop's
# hooks write it), the facilitator (entity `facilitator`, alias
# FORGEJO_ADMIN_USER) gets `facilitator`.
#
# The OpenBao image has busybox wget (GET and POST only) and no jq, so the
# Forgejo calls are plain wget and sed.

base="${PUBLIC_BASE_URL%/}"
callback="$base/ui/vault/auth/oidc/oidc/callback"
forgejo_api=http://git-server:3000/api/v1
forgejo_auth="Authorization: Basic $(printf '%s:%s' "$FORGEJO_ADMIN_USER" "$FORGEJO_ADMIN_PASSWORD" | base64 | tr -d '\n')"

# forgejo PATH [JSON]: GET PATH, or POST JSON to it; the response on stdout.
forgejo() {
  if [ $# -gt 1 ]; then
    wget -q -O - --header "$forgejo_auth" --header 'Content-Type: application/json' \
      --post-data "$2" "$forgejo_api$1"
  else
    wget -q -O - --header "$forgejo_auth" "$forgejo_api$1"
  fi
}

# json_field NAME: the string value of "NAME" in a one-object JSON response.
json_field() { sed -n "s/.*\"$1\":\"\([^\"]*\)\".*/\1/p"; }

log "sso: waiting for Forgejo's admin account"
retry 300 forgejo /user >/dev/null || { log "sso: Forgejo never accepted $FORGEJO_ADMIN_USER"; exit 1; }

# The OAuth2 app: reuse the one on $state while Forgejo still has it and the
# callback hasn't changed (another PUBLIC_BASE_URL), else make a new one.
# The secret is only shown when the app is created.
# Forgejo 16 has no way to skip its "Authorize Application" page for a
# trusted app, so each account approves once, on its first sign-in.
client="$state/oidc-client"
if [ ! -s "$client" ] || [ "$(sed -n 3p "$client")" != "$callback" ] \
  || ! forgejo /user/applications/oauth2 | grep -q "\"client_id\":\"$(sed -n 1p "$client")\""; then
  app="$(forgejo /user/applications/oauth2 \
    "{\"name\":\"OpenBao\",\"confidential_client\":true,\"redirect_uris\":[\"$callback\"]}")"
  cid="$(printf '%s' "$app" | json_field client_id)"
  csec="$(printf '%s' "$app" | json_field client_secret)"
  [ -n "$cid" ] && [ -n "$csec" ] || { log "sso: could not create Forgejo's OAuth2 app"; exit 1; }
  printf '%s\n%s\n%s\n' "$cid" "$csec" "$callback" > "$client"
  log "sso: Forgejo OAuth2 app $cid"
fi

ca_arg=
case "$base" in
  https://*)
    # The shim writes its CA when it first serves the name.
    ca=/shim/caddy/pki/authorities/local/root.crt
    retry 60 test -s "$ca" || { log "sso: no CA from the SSO shim"; exit 1; }
    ca_arg="oidc_discovery_ca_pem=@$ca" ;;
esac

bao read sys/auth/oidc >/dev/null 2>&1 || retry 30 bao auth enable oidc >/dev/null
# OpenBao fetches the issuer's discovery document here, through the shim.
retry 60 bao write auth/oidc/config oidc_discovery_url="$base/git" \
  oidc_client_id="$(sed -n 1p "$client")" oidc_client_secret="$(sed -n 2p "$client")" \
  default_role=forgejo $ca_arg >/dev/null
bao write auth/oidc/role/forgejo role_type=oidc user_claim=preferred_username \
  oidc_scopes=openid,profile allowed_redirect_uris="$callback" token_ttl=8h >/dev/null
accessor="$(bao read -field=accessor sys/auth/oidc)"

# entity NAME LOGIN POLICY: the entity and its alias for the Forgejo login,
# created or updated. Writing an alias that exists moves it to this entity,
# so a login from before this ran (which made its own entity) is fixed too.
entity() {
  bao write identity/entity/name/"$1" policies="$3" >/dev/null
  bao write identity/entity-alias name="$2" mount_accessor="$accessor" \
    canonical_id="$(bao read -field=id identity/entity/name/"$1")" >/dev/null
}
for s in $(class_users); do
  entity "$s" "$s" student
done
entity facilitator "$FORGEJO_ADMIN_USER" facilitator
log "sso: OIDC on $base/git, $STUDENT_COUNT students, ${BOT_COUNT:-0} bots and the facilitator"
