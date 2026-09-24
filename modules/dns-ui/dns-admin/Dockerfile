# PowerDNS-Admin, wrapped so it can sit under /dns-admin behind the engine's
# gateway (no prefix-stripping) and log the facilitator in from the
# gateway's identity headers instead of its own /login form. See
# dojo_wsgi.py, dojo_config.py, dojo_seed.py and dojo-entrypoint.sh for the
# three pieces; none of them patch PowerDNS-Admin's own source.
#
# Pinned to the manifest-list digest so both amd64 and arm64 resolve
# (checked with `podman manifest inspect`: linux/amd64 and linux/arm64 are
# both present under this digest, plus two attestation-only sub-manifests
# with no runnable content).
FROM docker.io/powerdnsadmin/pda-legacy@sha256:66dd8522c19a3950556ec2d3d3de7f7b9f9672f6442a6692e36349e636abae3b

# The sqlite file lives in the container's own /data (the base image has the
# directory; no VOLUME): ephemeral like dns-server itself, so a restart never
# pairs a fresh PowerDNS with stale zone copies in PowerDNS-Admin.
ENV DATABASE_DRIVER=sqlite \
    DATABASE_NAME=/data/pda.db \
    PATH_PREFIX=/dns-admin \
    FACILITATOR_USERNAME=root

COPY dojo_wsgi.py dojo_config.py dojo_seed.py /app/
COPY dojo-entrypoint.sh /app/dojo-entrypoint.sh
RUN chmod +x /app/dojo-entrypoint.sh

# curl is already in the base image (no wget); PATH_PREFIX is expanded by
# the shell HEALTHCHECK runs under, so this tracks a non-default prefix too.
# /healthz answers before auth (see dojo_wsgi.py) so the check needs no
# GATEWAY_TOKEN.
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
    CMD curl -fs "http://127.0.0.1:80${PATH_PREFIX}/healthz" || exit 1

ENTRYPOINT ["/app/dojo-entrypoint.sh"]
# Unused by dojo-entrypoint.sh (it never reads "$@"), kept for
# `podman inspect`/`podman run --entrypoint ''` readability only.
CMD ["gunicorn", "dojo_wsgi:application"]
