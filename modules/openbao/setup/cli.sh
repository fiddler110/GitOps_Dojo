# CLI login from the terminal, sourced by setup.sh after sso.sh (which made
# the entities and set $STUDENT_COUNT, $STUDENT_PREFIX, class_users).
#
# The terminal's identity broker signs a short-lived RS256 JWT for the Linux
# account that asks (iss dojo-terminal, aud openbao, sub the login name); its
# public key is on openbao_broker_pub. The `jwt` auth method in the root
# namespace trusts that key, and each login name is aliased to the same
# entity as the account's Forgejo SSO login, so both get the same policies.

pub=/broker/pub.pem
log "cli: waiting for the terminal's broker key"
retry 300 test -s "$pub" || { log "cli: no broker key from the terminal"; exit 1; }

bao read sys/auth/jwt >/dev/null 2>&1 || retry 30 bao auth enable jwt >/dev/null
# Re-read every start: a new terminal volume means a new key.
bao write auth/jwt/config jwt_validation_pubkeys=@"$pub" bound_issuer=dojo-terminal \
  default_role=terminal >/dev/null
bao write auth/jwt/role/terminal role_type=jwt user_claim=sub bound_audiences=openbao \
  token_ttl=8h token_max_ttl=24h >/dev/null
jwt_accessor="$(bao read -field=accessor sys/auth/jwt)"

# cli_alias ENTITY LOGIN: LOGIN on the jwt method signs in as ENTITY.
cli_alias() {
  bao write identity/entity-alias name="$2" mount_accessor="$jwt_accessor" \
    canonical_id="$(bao read -field=id identity/entity/name/"$1")" >/dev/null
}
cli_alias_same() { cli_alias "$1" "$1"; }
par_each cli_alias_same || { log "cli: could not make every student's jwt alias"; exit 1; }
cli_alias facilitator "$FACILITATOR_USERNAME"
log "cli: jwt login for $STUDENT_COUNT students, ${BOT_COUNT:-0} bots and the facilitator ($FACILITATOR_USERNAME)"
