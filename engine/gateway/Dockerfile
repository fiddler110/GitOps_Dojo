# Stock Caddy, pinned by multi-arch index digest. Sign-in is the allocator's
# /login page, so no plugins are needed. Bump the tag and digest together.
FROM docker.io/library/caddy:2.11.4-alpine@sha256:6aeddd44c3078b0f9a35206472a11420648a79c184603ef95957d0a20044cb2b

COPY Caddyfile /etc/caddy/Caddyfile
COPY static/ /srv/static/
COPY entrypoint.sh /usr/local/bin/gateway-entrypoint
RUN chmod +x /usr/local/bin/gateway-entrypoint

# caddy:*-alpine grants /usr/bin/caddy cap_net_bind_service and ships /data
# and /config world-writable, so it can bind 80/443 and persist certs/state
# without running as root.
USER nobody

# Hits Caddy's local admin API (always on, unauthenticated on loopback)
# rather than the site itself, which is behind the login and may be
# plain HTTP or HTTPS depending on PUBLIC_BASE_URL.
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:2019/config/ || exit 1

ENTRYPOINT ["/usr/local/bin/gateway-entrypoint"]
