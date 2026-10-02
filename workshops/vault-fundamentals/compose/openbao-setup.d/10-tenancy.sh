# vault-fundamentals setup hook, sourced by the openbao module's setup.sh on
# every start with the provisioner token (BAO_TOKEN, `log`, `retry`,
# STUDENT_COUNT, STUDENT_PREFIX, `class_users` (students, then demo bots), `par_each` and `enable_once` are set). Safe to re-run. It makes:
#   - the shared KV v2 mount `secret/` (lab 3) and a welcome secret in each
#     student's folder, written once (a re-run doesn't add versions);
#   - the `student` policy (student.hcl), which the module attaches to every
#     student's entity: their own folder in `secret/`, admin in their own
#     namespace;
#   - the namespace students/<name> for each student (lab 4 onwards).

here=/etc/openbao-setup.d

bao secrets list -format=json 2>/dev/null | grep -q '"secret/"' \
  || retry 30 bao secrets enable -path=secret -version=2 kv >/dev/null
retry 30 bao policy write student "$here/student.hcl" >/dev/null

bao namespace lookup students >/dev/null 2>&1 || retry 30 bao namespace create students >/dev/null

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
    || BAO_NAMESPACE=students retry 10 bao namespace create "$s" >/dev/null
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
par_each tenancy_one || exit 1
log "tenancy: secret/, the student policy and $(class_users | wc -l) namespaces under students/"
