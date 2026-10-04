# ctf-host — the boxed Docker-in-Docker daemon the CTF range runs its target
# slots inside (decision CTF-D21, spike S14). It is the `cloud-host` pattern
# from dojo-cloud: privileged is acceptable ONLY because it sits on an
# `internal: true` network with no route to the internet, to students, to the
# gateway or to Forgejo; it publishes nothing to the host; and its only client
# is ctf-controller, over a unix socket in a shared volume. Students never
# speak Docker.
#
# The target image is built INTO this image at build time (network is available
# then) and imported into the inner daemon at start (offline, nothing pulled at
# lab time) — exactly how cloud-host handles dojo/hello. The build context is
# the module root (modules/ctf-range) so this can COPY the target's source; see
# the overlay's `build.context`.

# --- the target's filesystem: a ready-to-run customer-portal rootfs ----------
# Mirrors targets/customer-portal/Dockerfile (same deps, same non-root user) so
# the imported image behaves like the standalone one.
FROM docker.io/library/python:3.12-slim@sha256:02108f5d322dd89f1c9e552442c25acb0543dfdbc455693a5599624f20d9155d AS portal
COPY targets/customer-portal/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY targets/customer-portal/app.py targets/customer-portal/seed.py targets/customer-portal/entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh \
    && useradd --uid 10014 --no-create-home --home-dir /app --shell /usr/sbin/nologin portal \
    && mkdir -p /data \
    && chown portal:portal /data

# --- the range host itself ----------------------------------------------------
FROM docker.io/library/docker:29.8.1-dind@sha256:3f3c01aaaebf7cce837356b688b7c059a4749f10bd7660dec7c58fc454a283f0

# docker:dind's entrypoint also opens an UNAUTHENTICATED tcp://0.0.0.0:2375
# listener when TLS is off. We only ever want the unix socket (shared with
# ctf-controller), so remove it and fail the build if the upstream script
# changes shape and the removal stops working (identical guard to cloud-host).
RUN sed -i '/--host=tcp:\/\/0.0.0.0:2375/d' /usr/local/bin/dockerd-entrypoint.sh \
    && ! grep -q -- '--host=tcp://0.0.0.0:2375' /usr/local/bin/dockerd-entrypoint.sh \
    && grep -q -- '--host="$dockerSocket"' /usr/local/bin/dockerd-entrypoint.sh

COPY --from=portal / /opt/portal-rootfs/
COPY ctf-host/entrypoint.sh /usr/local/bin/ctf-host-entrypoint
RUN chmod 0755 /usr/local/bin/ctf-host-entrypoint

# Socket dir shared with ctf-controller (a named volume in the overlay).
ENV DOCKER_HOST=unix:///run/ctf/docker.sock \
    DOCKER_TLS_CERTDIR=
ENTRYPOINT ["ctf-host-entrypoint"]
HEALTHCHECK --interval=10s --timeout=5s --start-period=40s --retries=3 \
    CMD docker image inspect ctf-customer-portal:base >/dev/null 2>&1 || exit 1
