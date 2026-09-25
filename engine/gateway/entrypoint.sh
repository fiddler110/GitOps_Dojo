#!/bin/sh
# Hashes TTYD_PASSWORD and FACILITATOR_PASSWORD at startup so the Caddyfile
# never needs a pre-computed hash pasted into .env — facilitators just set
# a plaintext password like every other credential in this project.
set -eu

# What Caddy serves: PUBLIC_BASE_URL, unless the lab sits behind another
# TLS proxy, where GATEWAY_LISTEN (e.g. http://:8080) is the gateway's own
# plain-HTTP address and PUBLIC_BASE_URL stays what the browser sees.
export GATEWAY_LISTEN="${GATEWAY_LISTEN:-$PUBLIC_BASE_URL}"

export TTYD_PASSWORD_HASH="$(caddy hash-password --plaintext "$TTYD_PASSWORD")"
export FACILITATOR_PASSWORD_HASH="$(caddy hash-password --plaintext "$FACILITATOR_PASSWORD")"

exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
