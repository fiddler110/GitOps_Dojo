#!/bin/sh
# openbao start.d hook, run by the base web-terminal entrypoint as root after
# every account exists. It
#   1. makes the broker's RSA key once (kept on openbao_broker_key, root-only)
#      and publishes its public half on openbao_broker_pub, where openbao-setup
#      reads it for the `jwt` auth method;
#   2. starts the identity broker, restarted if it dies;
# then returns, leaving the broker running.
set -eu

key=/var/lib/openbao-broker/key.pem
pub=/run/openbao-broker-pub/pub.pem

mkdir -p "$(dirname "$key")" && chmod 0700 "$(dirname "$key")"
if [ ! -s "$key" ]; then
  (umask 077 && openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$key.tmp" 2>/dev/null)
  mv "$key.tmp" "$key"
fi
openssl pkey -in "$key" -pubout -out "$pub.tmp" && chmod 0644 "$pub.tmp" && mv "$pub.tmp" "$pub"

# A child of PID 1, reaped by workspace-control.py.
(
  while true; do
    /usr/local/bin/openbao-broker || true
    sleep 2
  done
) &
