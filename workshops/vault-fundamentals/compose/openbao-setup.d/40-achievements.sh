# vault-fundamentals setup hook (sourced by the openbao module's setup.sh with the provisioner token).
# Mints the achievements service's read-only token (check.hcl) with the id BAO_CHECK_TOKEN, which
# module.env derives from this install's GATEWAY_TOKEN so the service can be given the same value.
# Safe to re-run: a token that already exists is left alone.

# Class-wide only: nothing to do for one student's reset (DOJO_ONE_USER).
[ -z "${DOJO_ONE_USER:-}" ] || return 0
[ -n "${BAO_CHECK_TOKEN:-}" ] || { log "achievements: no BAO_CHECK_TOKEN, skipping"; return 0 2>/dev/null || exit 0; }
retry 30 bao policy write check /etc/openbao-setup.d/check.hcl >/dev/null \
  || { log "achievements: could not write the check policy"; exit 1; }
# `bao write`, not `bao token create`: the CLI adds fields (period, renewable, ...) the provisioner's
# allowed_parameters don't list, and the server then answers 403.
out="$(bao write auth/token/create id="$BAO_CHECK_TOKEN" policies=check no_default_policy=true no_parent=true \
  ttl=720h display_name=achievements-check 2>&1)" || case "$out" in
  *exist*|*duplicate*) ;;
  *) log "achievements: could not mint the check token: $out"; exit 1 ;;
esac
