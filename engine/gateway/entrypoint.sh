#!/bin/sh
# Hashes TTYD_PASSWORD and FACILITATOR_PASSWORD at startup so the Caddyfile
# never needs a pre-computed hash pasted into .env — facilitators just set
# a plaintext password like every other credential in this project.
set -eu

# What Caddy serves: PUBLIC_BASE_URL, unless the lab sits behind another
# TLS proxy, where GATEWAY_LISTEN (e.g. http://:8080) is the gateway's own
# plain-HTTP address and PUBLIC_BASE_URL stays what the browser sees.
export GATEWAY_LISTEN="${GATEWAY_LISTEN:-$PUBLIC_BASE_URL}"

# The TLS name for clients that send none: browsers and curl send no SNI for
# an IP address (https://192.168.1.50:8443, Caddy's own CA), and without a
# default Caddy can't pick the certificate and aborts the handshake.
public_host="${PUBLIC_BASE_URL#*://}"; public_host="${public_host%%/*}"
case "$public_host" in
  \[*\]*) public_host="${public_host%%\]*}"; public_host="${public_host#\[}" ;;
  *) public_host="${public_host%:*}" ;;
esac
export GATEWAY_DEFAULT_SNI="$public_host"

export TTYD_PASSWORD_HASH="$(caddy hash-password --plaintext "$TTYD_PASSWORD")"
export FACILITATOR_PASSWORD_HASH="$(caddy hash-password --plaintext "$FACILITATOR_PASSWORD")"

# The exact Authorization headers a signed-in browser sends. The Caddyfile's
# rate limit counts only requests that carry neither, i.e. wrong guesses (and
# the one unauthenticated request before a login prompt), so a whole class
# behind one NAT address is never limited for being signed in.
export CLASS_BASIC_AUTH="Basic $(printf '%s:%s' "$TTYD_USERNAME" "$TTYD_PASSWORD" | base64 | tr -d '\n')"
export FACILITATOR_BASIC_AUTH="Basic $(printf '%s:%s' "$FACILITATOR_USERNAME" "$FACILITATOR_PASSWORD" | base64 | tr -d '\n')"

exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
