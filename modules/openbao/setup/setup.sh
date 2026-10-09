#!/bin/sh
# openbao-setup: brings the class OpenBao up with no manual step, then keeps
# it unsealed. Runs in the OpenBao image (for the bao CLI), as root with no
# capabilities. /setup (the openbao_setup volume, mounted nowhere else) keeps
# the unseal key and no live token.
#
# First start (vault not initialised): init with one key share (a lab
# shortcut, production uses auto-unseal) and unseal. The init root token is
# this start's temporary root; it waits on /setup until it is revoked below,
# so a start that dies half-way has it revoked by the next one.
# Every start:
#   1. a temporary root token, generated from the unseal key
#      (`bao operator generate-root`);
#   2. with it: revoke whatever an earlier start left (the accessors in
#      /setup/pending-accessors, the last reset token); write the provisioner
#      policy (policies/provisioner.hcl plus a workshop's
#      /etc/openbao-setup.d/provisioner.hcl) and mint a short-lived provisioner
#      token; if the workshop has /etc/openbao-setup.d/reset.hcl, mint the
#      periodic reset token (policies/reset.hcl plus that file) into this
#      container's tmpfs; revoke the temporary root;
#   3. with the provisioner: the UI's framing header, the facilitator policy,
#      SSO (sso.sh), CLI login (cli.sh), then every /etc/openbao-setup.d/*.sh
#      hook in name order (a workshop mounts its own there; each must be safe
#      to re-run). Hooks are sourced in a subshell, so they get BAO_TOKEN and
#      the helpers below; a failing hook stops setup;
#   4. revoke the provisioner.
# Then forever: unseal whenever the vault is sealed (after a restart of
# `openbao`), and renew the reset token; and, beside that, the reset worker
# (reset_worker below) runs the facilitator's student resets.
#
# Accepted (remediation D9, D11): anyone with the openbao_setup volume has the
# unseal key and can make a root token the same way. Revoking the tokens
# protects against a token read from /setup or a leaked environment, not that.
set -eu

export BAO_ADDR="${BAO_ADDR:-http://openbao:8200}"
state=/setup
run=/run/openbao-setup # tmpfs: memory only, gone when the container stops
ready=$run/ready
policies=/etc/openbao-setup/policies
hooks=/etc/openbao-setup.d
# Accessors of this start's temporary tokens (the root, the provisioner): not
# tokens, but enough for the next start to revoke them if this one dies.
pending=$state/pending-accessors
umask 077
# PID 1 ignores SIGTERM without a handler, so `stop` would wait 10 s and kill.
trap 'exit 0' TERM INT

log() { echo "openbao-setup: $*"; }

# retry N CMD...: run CMD until it succeeds, up to N times a second apart.
# For writes that fail for a moment: just after an unseal (a 500 while the
# audit device and storage come up), or the first write to a new KV v2 mount
# ("Upgrading from non-versioned to versioned data").
# sh has no local variables: these names must not clash with a caller's loop.
retry() {
  _retry_n="$1"; shift
  _retry_i=1
  until "$@"; do
    [ "$_retry_i" -lt "$_retry_n" ] || return 1
    _retry_i=$((_retry_i + 1)); sleep 1
  done
}

# class_users: every account that gets an entity, one per line: the students
# (studentNN), then the demo bots (testuserN, only with `./dojo --test`), so
# bots can walk the labs too. Loops read it as `for s in $(class_users)`.
class_users() {
  _cu_i=1
  while [ "$_cu_i" -le "$STUDENT_COUNT" ]; do
    printf '%s%02d\n' "$STUDENT_PREFIX" "$_cu_i"; _cu_i=$((_cu_i + 1))
  done
  _cu_i=1
  while [ "$_cu_i" -le "${BOT_COUNT:-0}" ]; do
    printf '%s%d\n' "${BOT_PREFIX:-testuser}" "$_cu_i"; _cu_i=$((_cu_i + 1))
  done
}

# status_field NAME: a boolean from `bao status` ("true"/"false"), empty if
# the server doesn't answer.
# par_each CMD [ARGS...]: run `CMD [ARGS...] USER` for every class user, up to
# SETUP_JOBS (default 8) at a time, and fail if any run failed. Each run is its
# own subshell, so it may `export BAO_NAMESPACE` or `exit 1` without touching
# the others. The per-user work is mostly the server making namespaces and
# mounts, which overlaps well.
par_each() {
  _pe_fail=0; _pe_n=0; _pe_pids=
  for _pe_u in $(class_users); do
    "$@" "$_pe_u" &
    _pe_pids="$_pe_pids $!"; _pe_n=$((_pe_n + 1))
    if [ "$_pe_n" -ge "${SETUP_JOBS:-8}" ]; then
      for _pe_p in $_pe_pids; do wait "$_pe_p" || _pe_fail=1; done
      _pe_pids=; _pe_n=0
    fi
  done
  for _pe_p in $_pe_pids; do wait "$_pe_p" || _pe_fail=1; done
  return "$_pe_fail"
}

# enable_once ARGS...: `bao auth enable ARGS` or `bao secrets enable ARGS`,
# where a path that is already mounted counts as done. One call instead of a
# list, a grep and an enable.
enable_once() {
  _eo_out="$(bao "$@" 2>&1)" && return 0
  case "$_eo_out" in *"already in use"*) return 0 ;; esac
  printf '%s\n' "$_eo_out" >&2
  return 1
}

status_field() {
  bao status -format=json 2>/dev/null | sed -n "s/^ *\"$1\": *\([a-z]*\),*$/\1/p"
}

unseal_if_sealed() {
  if [ "$(status_field sealed)" = "true" ]; then
    bao operator unseal "$(cat "$state/unseal-key")" >/dev/null
    log "unsealed"
  fi
}

# json_string NAME: a string field from `bao ... -format=json` on stdin.
json_string() {
  sed -n "s/^ *\"$1\": *\"\([^\"]*\)\",*$/\1/p" | head -1
}

# generate_root: print a new root token, made from the unseal key (one share,
# so one step). Cancels any attempt an earlier start left half-way. It talks to
# the legacy sys/generate-root/* paths through `bao write`: the `bao operator
# generate-root` CLI uses sys/generate-root-token/*, which OpenBao 2.7 refuses
# unauthenticated whatever the listener's disable_unauthed_generate_root_endpoints says,
# and this runs with no token.
generate_root() {
  bao delete sys/generate-root/attempt >/dev/null 2>&1 || true
  _gr_init="$(bao write -format=json -f sys/generate-root/attempt)" || return 1
  _gr_otp="$(printf '%s\n' "$_gr_init" | json_string otp)"
  _gr_nonce="$(printf '%s\n' "$_gr_init" | json_string nonce)"
  [ -n "$_gr_otp" ] && [ -n "$_gr_nonce" ] || return 1
  _gr_out="$(bao write -format=json sys/generate-root/update nonce="$_gr_nonce" key="$(cat "$state/unseal-key")")" || return 1
  _gr_enc="$(printf '%s\n' "$_gr_out" | json_string encoded_token)"
  [ -n "$_gr_enc" ] || _gr_enc="$(printf '%s\n' "$_gr_out" | json_string encoded_root_token)"
  [ -n "$_gr_enc" ] || return 1
  # Decode by hand (`-decode` asks the server for its status first): the token is the
  # base64 of the root token XORed byte by byte with the OTP.
  while [ $(( ${#_gr_enc} % 4 )) -ne 0 ]; do _gr_enc="${_gr_enc}="; done
  _gr_i=0
  for _gr_b in $(printf '%s' "$_gr_enc" | base64 -d | od -An -v -tu1); do
    _gr_c="$(printf '%s' "$_gr_otp" | cut -c$((_gr_i + 1)))"
    _gr_k="$(printf '%d' "'$_gr_c")"
    printf "\\$(printf '%03o' $((_gr_b ^ _gr_k)))"
    _gr_i=$((_gr_i + 1))
  done
}

# accessor_of TOKEN: the token's accessor.
accessor_of() {
  _ao_out="$(BAO_TOKEN="$1" bao token lookup -format=json)" || return 1
  printf '%s\n' "$_ao_out" | json_string accessor | grep .
}

# mint VAR_TOKEN VAR_ACCESSOR ARGS...: `bao token create ARGS`, setting the two
# variables (sh has no arrays or out-parameters, hence eval on fixed names).
mint() {
  _m_t="$1"; _m_a="$2"; shift 2
  _m_out="$(bao token create -format=json "$@")" || return 1
  eval "$_m_t=\$(printf '%s\n' \"\$_m_out\" | json_string client_token)"
  eval "$_m_a=\$(printf '%s\n' \"\$_m_out\" | json_string accessor)"
  eval "[ -n \"\$$_m_t\" ] && [ -n \"\$$_m_a\" ]"
}

# policy NAME FILE [EXTRA]: write FILE (plus EXTRA, a workshop's file, if it
# exists) as policy NAME.
policy() {
  { cat "$2"; [ -n "${3:-}" ] && [ -e "$3" ] && { echo; cat "$3"; }; true; } \
    | bao policy write "$1" - >/dev/null
}

log "waiting for $BAO_ADDR"
until [ -n "$(status_field initialized)" ]; do sleep 1; done

if [ "$(status_field initialized)" = "false" ]; then
  if [ -e "$state/unseal-key" ]; then
    # The vault's storage is new but this volume is not: the old key and
    # accessors are for a vault that no longer exists.
    log "stale state from an earlier vault, moving it aside"
    mkdir -p "$state/stale.$$"
    for f in unseal-key root-token provisioner-token reset-accessor pending-accessors; do
      if [ -e "$state/$f" ]; then mv "$state/$f" "$state/stale.$$/"; fi
    done
  fi
  log "initialising"
  out="$(bao operator init -key-shares=1 -key-threshold=1)"
  printf '%s\n' "$out" | sed -n 's/^Unseal Key 1: *//p' > "$state/unseal-key"
  printf '%s\n' "$out" | sed -n 's/^Initial Root Token: *//p' > "$state/root-token"
  [ -s "$state/unseal-key" ] && [ -s "$state/root-token" ] || { log "could not read the init output"; exit 1; }
fi

unseal_if_sealed

# 1. The temporary root: the init root token if this is (or finishes) the
# first start, else a new one from the unseal key.
mkdir -p "$run"
root=
if [ -s "$state/root-token" ] && retry 5 env BAO_TOKEN="$(cat "$state/root-token")" bao token lookup >/dev/null 2>&1; then
  root="$(cat "$state/root-token")"
else
  rm -f "$state/root-token"
  root="$(retry 30 generate_root)" && [ -n "$root" ] || { log "could not generate a root token"; exit 1; }
fi
BAO_TOKEN="$root"; export BAO_TOKEN

# 2. Clean up after earlier starts (not this root: a first start that died
# half-way left it listed too), then mint this start's tokens.
root_acc="$(retry 30 accessor_of "$root")" || { log "could not look up the root token"; exit 1; }
if [ -s "$pending" ]; then
  while read -r acc; do
    if [ -n "$acc" ] && [ "$acc" != "$root_acc" ]; then
      bao token revoke -accessor "$acc" >/dev/null 2>&1 || true
    fi
  done < "$pending"
  log "revoked the tokens an earlier start left"
fi
echo "$root_acc" > "$pending"
if [ -s "$state/provisioner-token" ]; then
  # A long-lived provisioner token from before remediation T5.3.
  bao token revoke "$(cat "$state/provisioner-token")" >/dev/null 2>&1 || true
  rm -f "$state/provisioner-token"
fi

retry 30 policy provisioner "$policies/provisioner.hcl" "$hooks/provisioner.hcl" \
  || { log "could not write the provisioner policy"; exit 1; }
# Short-lived, not renewed: a start takes minutes. -orphan so revoking the
# root doesn't revoke it with it.
retry 30 mint prov prov_acc -orphan -policy=provisioner -no-default-policy \
  -ttl=2h -explicit-max-ttl=2h -display-name=openbao-setup \
  || { log "could not mint the provisioner token"; exit 1; }
echo "$prov_acc" >> "$pending"

# The reset token (student-reset R9): the last start's is revoked, a new one
# kept in memory only. Its accessor stays on /setup for the next start.
if [ -s "$state/reset-accessor" ]; then
  bao token revoke -accessor "$(cat "$state/reset-accessor")" >/dev/null 2>&1 || true
  rm -f "$state/reset-accessor"
fi
rm -f "$run/reset-token"
if [ -e "$hooks/reset.hcl" ]; then
  retry 30 policy reset "$policies/reset.hcl" "$hooks/reset.hcl" \
    || { log "could not write the reset policy"; exit 1; }
  retry 30 mint reset reset_acc -orphan -policy=reset -no-default-policy \
    -period=24h -display-name=openbao-reset \
    || { log "could not mint the reset token"; exit 1; }
  printf '%s\n' "$reset" > "$run/reset-token"
  echo "$reset_acc" > "$state/reset-accessor"
  unset reset
fi

# Revoke the temporary root. "permission denied" means it is gone already.
revoke_self() {
  bao token revoke -self >/dev/null 2>&1 \
    || bao token lookup 2>&1 | grep -q 'permission denied'
}
retry 30 revoke_self || { log "could not revoke the root token"; exit 1; }
rm -f "$state/root-token"
echo "$prov_acc" > "$pending"
unset root root_acc
log "root token revoked"

# 3. The set-up, as the provisioner.
BAO_TOKEN="$prov"; export BAO_TOKEN
unset prov

# The UI ships frame-ancestors 'none'; the /admin Vault tab frames it from the
# same origin. Keep the rest of OpenBao's own policy as it is.
csp="$(wget -S -q -O /dev/null "$BAO_ADDR/ui/" 2>&1 \
  | sed -n 's/^ *[Cc]ontent-[Ss]ecurity-[Pp]olicy: *//p' | head -1 | tr -d '\r')"
[ -n "$csp" ] || { log "no Content-Security-Policy on /ui/"; exit 1; }
retry 30 bao write sys/config/ui/headers/Content-Security-Policy \
  values="$(printf '%s' "$csp" | sed "s/frame-ancestors 'none'/frame-ancestors 'self'/")" >/dev/null

retry 30 bao policy write facilitator "$policies/facilitator.hcl" >/dev/null

# Single sign-on through Forgejo (sso.sh).
. /etc/openbao-setup/sso.sh
# CLI login from the terminal through its identity broker (cli.sh).
. /etc/openbao-setup/cli.sh

for hook in "$hooks"/*.sh; do
  [ -e "$hook" ] || continue
  log "hook $(basename "$hook")"
  ( . "$hook" ) || { log "hook $(basename "$hook") failed"; bao token revoke -self >/dev/null 2>&1; exit 1; }
done

# 4. Revoke the provisioner.
retry 30 revoke_self || { log "could not revoke the provisioner token"; exit 1; }
rm -f "$pending"
unset BAO_TOKEN prov_acc
log "provisioner token revoked"

mkdir -p "$(dirname "$ready")" && touch "$ready"
log "ready"

# reset_one PHASE USER: one student's part of every hook, with the reset
# token. The hooks are sourced as at start, in a subshell, with DOJO_ONE_USER
# and DOJO_RESET_PHASE (teardown|provision) set and class_users narrowed to
# that student, so par_each runs once; each hook skips its class-wide part.
# Teardown runs the hooks in reverse name order.
reset_one() {
  class_users | grep -qx -- "$2" || { echo "$2 is not an account of this class"; return 1; }
  [ -s "$run/reset-token" ] || { echo "no reset token: the workshop has no openbao-setup.d/reset.hcl"; return 1; }
  (
    BAO_TOKEN="$(cat "$run/reset-token")"; export BAO_TOKEN
    DOJO_RESET_PHASE="$1"; DOJO_ONE_USER="$2"; export DOJO_RESET_PHASE DOJO_ONE_USER
    class_users() { printf '%s\n' "$DOJO_ONE_USER"; }
    if [ "$1" = teardown ]; then _ro_order="sort -r"; else _ro_order="sort"; fi
    for hook in $(ls "$hooks"/*.sh 2>/dev/null | $_ro_order); do
      ( . "$hook" ) || { echo "hook $(basename "$hook") failed"; exit 1; }
    done
    echo "$1 of $2 done"
  )
}

# reset_worker: takes the jobs openbao-reset (reset/reset.py) queues for the
# allocator's reset hook, one at a time, and posts each result back: `ok` or
# `fail`, then the last lines of output. It long-polls, proving itself with
# RESET_TOKEN; the reset token itself never leaves this container.
reset_worker() {
  _rw_url="${OPENBAO_RESET_URL:-http://openbao-reset:8080}/_dojo/work"
  log "reset worker: taking jobs from $_rw_url"
  while :; do
    _rw_job="$(wget -q -O - -T 60 --header "X-Dojo-Reset-Token: $RESET_TOKEN" "$_rw_url" 2>/dev/null)" \
      || { sleep 5; continue; }
    [ -n "$_rw_job" ] || continue
    # shellcheck disable=SC2086 # "<id> <phase> <user>", checked below
    set -- $_rw_job
    case "${1:-}:${2:-}:${3:-}" in
      *[!a-z0-9_:-]*) log "reset worker: refused a malformed job"; continue ;;
      [0-9a-f]*:teardown:[a-z]*|[0-9a-f]*:provision:[a-z]*) ;;
      *) log "reset worker: refused a malformed job"; continue ;;
    esac
    log "reset worker: $2 $3"
    if _rw_out="$(reset_one "$2" "$3" 2>&1)"; then _rw_res=ok; else _rw_res=fail; fi
    log "reset worker: $2 $3: $_rw_res"
    wget -q -O /dev/null -T 10 --header "X-Dojo-Reset-Token: $RESET_TOKEN" \
      --post-data "$(printf '%s\n%s' "$_rw_res" "$(printf '%s\n' "$_rw_out" | tail -n 4)")" \
      "$_rw_url/$1" 2>/dev/null || log "reset worker: could not post the result of $2 $3"
  done
}
if [ -n "${RESET_TOKEN:-}" ] && [ -s "$run/reset-token" ]; then
  reset_worker &
else
  log "student resets off (no RESET_TOKEN or no reset.hcl)"
fi

# Keep the vault unsealed and the reset token alive.
n=0
while :; do
  sleep 5 & wait $! # in the background, so the TERM trap runs at once
  unseal_if_sealed || log "unseal failed, retrying"
  n=$((n + 1))
  if [ "$n" -ge 720 ]; then # about an hour
    n=0
    if [ -s "$run/reset-token" ]; then
      BAO_TOKEN="$(cat "$run/reset-token")" bao token renew >/dev/null || log "reset token renew failed"
    fi
  fi
done
