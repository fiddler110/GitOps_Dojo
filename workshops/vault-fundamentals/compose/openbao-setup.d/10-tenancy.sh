# vault-fundamentals setup hook, sourced by the openbao module's setup.sh on
# every start with the provisioner token (BAO_TOKEN, `log`, `retry`,
# STUDENT_COUNT, STUDENT_PREFIX, `class_users` (students, then demo bots), `par_each` and `enable_once` are set). Safe to re-run. It makes:
#   - the shared KV v2 mount `secret/` (lab 3) and a welcome secret in each
#     student's folder, written once (a re-run doesn't add versions);
#   - the `student` policy (student.hcl), which the module attaches to every
#     student's entity: their own folder in `secret/`, admin in their own
#     namespace;
#   - the namespace students/<name> for each student (lab 4 onwards).
#
# One-user mode (a facilitator's student reset; setup.sh reset_one, with the
# reset token and DOJO_ONE_USER set): only that student's part. Teardown
# deletes their namespace (which revokes every token and lease made in it)
# and their folder in secret/; provision makes both again as above.

here=/etc/openbao-setup.d

if [ -z "${DOJO_ONE_USER:-}" ]; then
  bao secrets list -format=json 2>/dev/null | grep -q '"secret/"' \
    || retry 30 bao secrets enable -path=secret -version=2 kv >/dev/null
  retry 30 bao policy write student "$here/student.hcl" >/dev/null

  bao namespace lookup students >/dev/null 2>&1 || retry 30 bao namespace create students >/dev/null
fi

# seed NAME: the welcome secret, only if the student has none yet (cas=0).
# The first write to a new KV v2 mount fails for a moment while it upgrades.
seed() {
  out="$(printf '{"options":{"cas":0},"data":{"message":"Welcome to the shared vault, %s. Only you can read this folder."}}' "$1" \
    | bao write secret/data/students/"$1"/welcome - 2>&1)" && return 0
  case "$out" in *check-and-set*) return 0 ;; esac
  return 1
}

# tenancy_one NAME: the student's namespace, rate limit and welcome secret.
tenancy_one() {
  s="$1"
  BAO_NAMESPACE=students bao namespace lookup "$s" >/dev/null 2>&1 \
    || BAO_NAMESPACE=students retry 10 bao namespace create "$s" >/dev/null \
    || { log "tenancy: could not create students/$s"; exit 1; }
  # Tripwire against a runaway loop in one namespace (OPENBAO_NAMESPACE_RATE,
  # module.env; 0 = none). Quotas can only be written from the root namespace,
  # which scopes each one to a namespace with `path`. A write replaces, so a
  # re-run is harmless.
  if [ "${OPENBAO_NAMESPACE_RATE:-200}" -gt 0 ]; then
    retry 10 bao write "sys/quotas/rate-limit/students-$s" path="students/$s/" \
      rate="${OPENBAO_NAMESPACE_RATE:-200}" interval=1s >/dev/null \
      || { log "tenancy: could not set $s's rate limit"; exit 1; }
  fi
  retry 30 seed "$s" || { log "tenancy: could not seed $s's welcome secret"; exit 1; }
}
# kv_wipe PATH: delete every secret (all versions and metadata) under
# secret/PATH/, folders first. Raw list/delete on secret/metadata/, which the
# reset policy allows; `bao kv` would first ask sys/internal/ui/mounts.
kv_wipe() {
  _kw_keys="$(bao list -format=json "secret/metadata/$1/" 2>&1)" || case "$_kw_keys" in
    *"No value found"*) return 0 ;; # nothing there
    *) log "tenancy: could not list secret/$1/: $_kw_keys"; return 1 ;;
  esac
  printf '%s\n' "$_kw_keys" | sed -n 's/^ *"\(.*\)",* *$/\1/p' | sed 's/\\"/"/g; s/\\\\/\\/g' \
    | while IFS= read -r _kw_k; do
        case "$_kw_k" in
          */) kv_wipe "$1/${_kw_k%/}" || exit 1 ;;
          *) bao delete "secret/metadata/$1/$_kw_k" >/dev/null || { log "tenancy: could not delete secret/$1/$_kw_k"; exit 1; } ;;
        esac
      done
}

# tenancy_teardown NAME: the student's namespace (deleting it revokes the
# tokens and leases made in it; the database mount's leases drop their
# Postgres logins, so app-db must still be up) and their secret/ folder.
# OpenBao deletes a namespace in the background: wait until it is gone, so
# provision can make it again.
tenancy_teardown() {
  s="$1"
  if BAO_NAMESPACE=students bao namespace lookup "$s" >/dev/null 2>&1; then
    BAO_NAMESPACE=students retry 10 bao namespace delete "$s" >/dev/null \
      || { log "tenancy: could not delete students/$s"; exit 1; }
  fi
  _tt_i=0
  while BAO_NAMESPACE=students bao namespace lookup "$s" >/dev/null 2>&1; do
    _tt_i=$((_tt_i + 1))
    [ "$_tt_i" -lt 90 ] || { log "tenancy: students/$s is still being deleted after 90s"; exit 1; }
    sleep 1
  done
  kv_wipe "students/$s" || exit 1
}

if [ "${DOJO_RESET_PHASE:-}" = teardown ]; then
  par_each tenancy_teardown || exit 1
  log "tenancy: deleted students/$DOJO_ONE_USER and secret/students/$DOJO_ONE_USER/"
  return 0
fi
par_each tenancy_one || exit 1
log "tenancy: secret/, the student policy and $(class_users | wc -l) namespaces under students/"
