#!/bin/sh
# openbao-setup: brings the class OpenBao up with no manual step, then keeps
# it unsealed. Runs in the OpenBao image (for the bao CLI), as root with no
# capabilities, with /setup (the openbao_setup volume, mounted nowhere else)
# holding the unseal key and the provisioner token.
#
# First start (vault not initialised):
#   init (one key share: a lab shortcut, production uses auto-unseal), unseal,
#   the provisioner policy and token (with root), revoke root.
# Every start, with the provisioner token:
#   the UI's framing header, the facilitator policy, then every
#   /etc/openbao-setup.d/*.sh hook in name order (a workshop mounts its own
#   there; each must be safe to re-run). Hooks are sourced in a subshell, so
#   they get BAO_TOKEN and the helpers below; a failing hook stops setup.
# Then forever: unseal whenever the vault is sealed (after a restart of
#   `openbao`), and renew the provisioner token.
set -eu

export BAO_ADDR="${BAO_ADDR:-http://openbao:8200}"
state=/setup
ready=/run/openbao-setup/ready
policies=/etc/openbao-setup/policies
umask 077

log() { echo "openbao-setup: $*"; }

# retry N CMD...: run CMD until it succeeds, up to N times a second apart.
# For writes that fail for a moment, such as the first write to a new KV v2
# mount ("Upgrading from non-versioned to versioned data").
retry() {
  n="$1"; shift
  i=1
  until "$@"; do
    [ "$i" -lt "$n" ] || return 1
    i=$((i + 1)); sleep 1
  done
}

# status_field NAME: a boolean from `bao status` ("true"/"false"), empty if
# the server doesn't answer.
status_field() {
  bao status -format=json 2>/dev/null | sed -n "s/^ *\"$1\": *\([a-z]*\),*$/\1/p"
}

unseal_if_sealed() {
  if [ "$(status_field sealed)" = "true" ]; then
    bao operator unseal "$(cat "$state/unseal-key")" >/dev/null
    log "unsealed"
  fi
}

log "waiting for $BAO_ADDR"
until [ -n "$(status_field initialized)" ]; do sleep 1; done

if [ "$(status_field initialized)" = "false" ]; then
  if [ -e "$state/unseal-key" ]; then
    # The vault's storage is new but this volume is not: the old key and
    # token are for a vault that no longer exists.
    log "stale state from an earlier vault, moving it aside"
    mkdir -p "$state/stale.$$" && mv "$state"/unseal-key "$state"/provisioner-token "$state/stale.$$/" 2>/dev/null || true
  fi
  log "initialising"
  out="$(bao operator init -key-shares=1 -key-threshold=1)"
  printf '%s\n' "$out" | sed -n 's/^Unseal Key 1: *//p' > "$state/unseal-key"
  root="$(printf '%s\n' "$out" | sed -n 's/^Initial Root Token: *//p')"
  [ -s "$state/unseal-key" ] && [ -n "$root" ] || { log "could not read the init output"; exit 1; }
  unseal_if_sealed

  # The provisioner can manage namespaces, policies, auth methods, identities
  # and mounts, and write (not read) seed secrets: policies/provisioner.hcl.
  # Periodic, so it lives as long as this container keeps renewing it.
  BAO_TOKEN="$root" bao policy write provisioner "$policies/provisioner.hcl" >/dev/null
  BAO_TOKEN="$root" bao token create -orphan -policy=provisioner -no-default-policy \
    -period=168h -display-name=openbao-setup -field=token > "$state/provisioner-token"
  BAO_TOKEN="$root" bao token revoke -self >/dev/null
  root=""
  log "initialised; root token revoked"
fi

unseal_if_sealed
BAO_TOKEN="$(cat "$state/provisioner-token")"
export BAO_TOKEN
bao token renew >/dev/null

# The UI ships frame-ancestors 'none'; the /admin Vault tab frames it from the
# same origin. Keep the rest of OpenBao's own policy as it is.
csp="$(wget -S -q -O /dev/null "$BAO_ADDR/ui/" 2>&1 \
  | sed -n 's/^ *[Cc]ontent-[Ss]ecurity-[Pp]olicy: *//p' | head -1 | tr -d '\r')"
[ -n "$csp" ] || { log "no Content-Security-Policy on /ui/"; exit 1; }
bao write sys/config/ui/headers/Content-Security-Policy \
  values="$(printf '%s' "$csp" | sed "s/frame-ancestors 'none'/frame-ancestors 'self'/")" >/dev/null

bao policy write facilitator "$policies/facilitator.hcl" >/dev/null

for hook in /etc/openbao-setup.d/*.sh; do
  [ -e "$hook" ] || continue
  log "hook $(basename "$hook")"
  ( . "$hook" ) || { log "hook $(basename "$hook") failed"; exit 1; }
done

mkdir -p "$(dirname "$ready")" && touch "$ready"
log "ready"

# Keep the vault unsealed and the provisioner token alive.
n=0
while :; do
  sleep 5
  unseal_if_sealed || log "unseal failed, retrying"
  n=$((n + 1))
  if [ "$n" -ge 720 ]; then # about an hour
    n=0
    bao token renew >/dev/null || log "provisioner token renew failed"
  fi
done
