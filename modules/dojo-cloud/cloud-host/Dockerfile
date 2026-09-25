# "cloud-host": the machine the Dojo Cloud control plane runs student
# containers on. It is a Docker-in-Docker daemon, so it needs `privileged` (see
# the overlay for why that is acceptable here): it sits on an internal-only
# network with no internet, publishes nothing to the host, and is reachable only
# through the Docker socket shared with cloud-api — students never touch it.
#
# The images students may deploy are built INTO this image at build time and
# imported at start, so nothing is pulled at lab time.

# --- the hello app's filesystem: busybox + our entrypoint (a few MB) ---------
FROM docker.io/library/busybox:1.37 AS hello
COPY hello/entrypoint.sh /entrypoint.sh
RUN chmod 0755 /entrypoint.sh

# --- the cloud host itself ----------------------------------------------------
FROM docker.io/library/docker:dind

# docker:dind's entrypoint also opens an UNAUTHENTICATED tcp://0.0.0.0:2375
# listener when TLS is off. We only ever want the unix socket (shared with
# cloud-api), so remove that listener and fail the build if the upstream script
# changes shape and the removal stops working.
RUN sed -i '/--host=tcp:\/\/0.0.0.0:2375/d' /usr/local/bin/dockerd-entrypoint.sh \
    && ! grep -q -- '--host=tcp://0.0.0.0:2375' /usr/local/bin/dockerd-entrypoint.sh \
    && grep -q -- '--host="$dockerSocket"' /usr/local/bin/dockerd-entrypoint.sh

COPY --from=hello / /opt/hello-rootfs/
COPY entrypoint.sh /usr/local/bin/cloud-host-entrypoint
RUN chmod 0755 /usr/local/bin/cloud-host-entrypoint

# Socket dir shared with cloud-api (a named volume in the overlay).
ENV DOCKER_HOST=unix:///run/cloud/docker.sock \
    DOCKER_TLS_CERTDIR=
ENTRYPOINT ["cloud-host-entrypoint"]
HEALTHCHECK --interval=10s --timeout=5s --start-period=40s --retries=3 \
    CMD docker image inspect dojo/hello:2.0 >/dev/null 2>&1 || exit 1
