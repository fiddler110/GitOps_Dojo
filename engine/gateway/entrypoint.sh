#!/bin/sh
# Works out the addresses the Caddyfile needs from PUBLIC_BASE_URL. Passwords
# are not handled here: sign-in is the allocator's /login page.
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

exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
