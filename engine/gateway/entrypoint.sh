#!/bin/sh
# Hashes TTYD_PASSWORD and FACILITATOR_PASSWORD at startup so the Caddyfile
# never needs a pre-computed hash pasted into .env — facilitators just set
# a plaintext password like every other credential in this project.
set -eu

export TTYD_PASSWORD_HASH="$(caddy hash-password --plaintext "$TTYD_PASSWORD")"
export FACILITATOR_PASSWORD_HASH="$(caddy hash-password --plaintext "$FACILITATOR_PASSWORD")"

exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
