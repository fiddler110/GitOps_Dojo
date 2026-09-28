# Caddy plus github.com/mholt/caddy-ratelimit (remediation T1.1c, D10: the
# brute-force limit in front of basic_auth, see the Caddyfile). Both images
# are pinned by multi-arch index digest; the plugin by module version, which
# go verifies against the checksum database (sum.golang.org) at build time.
# Bump CADDY_VERSION together with both digests.
ARG CADDY_VERSION=v2.11.4
ARG RATELIMIT_VERSION=v0.1.1-0.20260612195517-5625512f24f6

FROM docker.io/library/caddy:2.11.4-builder-alpine@sha256:0aa610043dab5da82ad0a0268e46bb852785e6f5160f12f1c6fe3f42903d7e1b AS builder
ARG CADDY_VERSION
ARG RATELIMIT_VERSION
RUN xcaddy build ${CADDY_VERSION} \
      --with github.com/mholt/caddy-ratelimit@${RATELIMIT_VERSION}

FROM docker.io/library/caddy:2.11.4-alpine@sha256:6aeddd44c3078b0f9a35206472a11420648a79c184603ef95957d0a20044cb2b

# Same path and file capability as the stock binary it replaces (below).
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
RUN setcap cap_net_bind_service=+ep /usr/bin/caddy

COPY Caddyfile /etc/caddy/Caddyfile
COPY static/ /srv/static/
COPY entrypoint.sh /usr/local/bin/gateway-entrypoint
RUN chmod +x /usr/local/bin/gateway-entrypoint

# caddy:*-alpine grants /usr/bin/caddy cap_net_bind_service via setcap
# (re-applied above to the rebuilt binary), and ships /data and /config world-writable, specifically so it
# can bind 80/443 and persist certs/state without running as root.
USER nobody

# Hits Caddy's local admin API (always on, unauthenticated on loopback)
# rather than the site itself, which is behind basic_auth and may be
# plain HTTP or HTTPS depending on PUBLIC_BASE_URL.
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:2019/config/ || exit 1

ENTRYPOINT ["/usr/local/bin/gateway-entrypoint"]
