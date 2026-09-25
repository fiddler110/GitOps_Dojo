#!/bin/sh
# dojo-cloud start.d hook, run by the base web-terminal entrypoint as root
# after every account exists (see engine/web-terminal/entrypoint.sh). It never
# waits for Dojo Cloud: the terminal starts at once and anything that doesn't
# use the cloud needs none of this. It
#   1. starts a background loop that waits, with no time limit, for Dojo Cloud's CA
#      certificate and signing key (cloud-api creates them when it starts, which can
#      be after this container), then writes the trust bundle /etc/dojo/ca-bundle.pem
#      (system CAs + that CA) atomically and stops. It says so once if that has not
#      happened after 60 s, and keeps waiting;
#   2. starts the credential broker, restarted if it dies (it waits for the key too);
# then returns, leaving both running.
# A shell captures its ARM_* / SSL_CERT_FILE values when it starts, so a shell opened
# before Dojo Cloud was ready needs a new terminal tab.
set -eu

# The environment overrides exist only so the loop can be tested in a scratch directory.
CA=${DOJO_WRAPPER_CA:-/run/cloud-pki/dojo-cloud-ca.pem}
KEY=${DOJO_WRAPPER_KEY:-/run/cloud-secrets/signing.key}
BUNDLE=${DOJO_WRAPPER_BUNDLE:-/etc/dojo/ca-bundle.pem}
SYSTEM_CAS=${DOJO_WRAPPER_SYSTEM_CAS:-/etc/ssl/certs/ca-certificates.crt}
NOTICE_AFTER=${DOJO_WRAPPER_NOTICE_AFTER:-60}  # seconds
POLL=${DOJO_WRAPPER_POLL:-1}                   # seconds

# A CA that is only half copied must not end up in the bundle, hence the END line.
cloud_files_ready() {
  [ -s "$KEY" ] && [ -s "$CA" ] && grep -q -- '-----END CERTIFICATE-----' "$CA"
}

# Written next to the target and renamed into place, so a shell never reads a half-written bundle.
write_bundle() {
  mkdir -p "$(dirname "$BUNDLE")" &&
    cat "$SYSTEM_CAS" "$CA" > "$BUNDLE.tmp" &&
    chmod 0644 "$BUNDLE.tmp" &&
    mv "$BUNDLE.tmp" "$BUNDLE"
}

(
  waited=0
  until cloud_files_ready; do
    waited=$((waited + 1))
    if [ "$waited" -eq "$NOTICE_AFTER" ]; then
      echo "dojo-cloud: Dojo Cloud not available yet; still waiting for it in the background." >&2
    fi
    sleep "$POLL"
  done
  write_bundle || echo "dojo-cloud: could not write $BUNDLE; Dojo Cloud's certificate will not be trusted." >&2
) &

# Restarted if it ever dies; a child of PID 1, reaped by workspace-control.py.
(
  while true; do
    /usr/local/bin/dojo-broker || true
    sleep 2
  done
) &

