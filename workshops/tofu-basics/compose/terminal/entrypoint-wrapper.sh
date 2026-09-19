#!/bin/sh
# tofu-basics wrapper around the base web-terminal entrypoint: when Dojo Cloud
# is up, trust its private CA and start the credential broker; then hand off
# to the base entrypoint unchanged. If cloud-api never appears, everything
# still works — Track A (the offline sandbox) needs none of this.
set -eu

CA=/run/cloud-pki/dojo-cloud-ca.pem
KEY=/run/cloud-secrets/signing.key

i=0
until [ -s "$CA" ] && [ -s "$KEY" ]; do
  i=$((i + 1))
  if [ "$i" -gt 60 ]; then
    echo "tofu-basics: Dojo Cloud not available; continuing without it (Track A only)." >&2
    break
  fi
  sleep 1
done

if [ -s "$CA" ]; then
  mkdir -p /etc/dojo
  cat /etc/ssl/certs/ca-certificates.crt "$CA" > /etc/dojo/ca-bundle.pem
  chmod 0644 /etc/dojo/ca-bundle.pem
fi

# Restarted if it ever dies; a child of PID 1 like cert-autorenewal's helpers.
(
  while true; do
    /usr/local/bin/dojo-broker || true
    sleep 2
  done
) &

exec /usr/local/bin/web-terminal-entrypoint "$@"
