FROM docker.io/library/caddy:2-alpine

COPY Caddyfile /etc/caddy/Caddyfile
COPY static/ /srv/static/
COPY entrypoint.sh /usr/local/bin/gateway-entrypoint
RUN chmod +x /usr/local/bin/gateway-entrypoint

# caddy:2-alpine already grants /usr/bin/caddy cap_net_bind_service via
# setcap, and ships /data and /config world-writable, specifically so it
# can bind 80/443 and persist certs/state without running as root.
USER nobody

# Hits Caddy's local admin API (always on, unauthenticated on loopback)
# rather than the site itself, which is behind basic_auth and may be
# plain HTTP or HTTPS depending on PUBLIC_BASE_URL.
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:2019/config/ || exit 1

ENTRYPOINT ["/usr/local/bin/gateway-entrypoint"]
