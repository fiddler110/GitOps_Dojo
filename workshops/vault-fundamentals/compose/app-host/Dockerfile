# app-host (vault-fundamentals, labs 11-13): the platform students deploy to.
# apphost.py (mounted read-only from this folder by the overlay) runs as root
# and runs each slot's app as its own user.
#
# The tools an app calls come from the terminal image dojo has just built
# (TOOLS_IMAGE, set by the overlay), so each has one pin, in the terminal's
# Dockerfiles: bao (the Agent) and the Python packages (hvac, pg8000). Both
# images are Debian bookworm, so the Python packages fit as they are.
ARG TOOLS_IMAGE=gitopsdojo/web-terminal:base
FROM ${TOOLS_IMAGE} AS tools

FROM docker.io/library/debian:bookworm-slim@sha256:7c7b2c966bc9ee8cedfeef67e0e279108992c77681fa595db4a9d65c06ccc587

# python3: the platform and the apps. openssl: the platform's signing key and
# signature checks. tini: PID 1, reaping the processes of stopped apps.
# util-linux (su, unshare, prlimit, setpriv) and passwd (useradd) are in the base image.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        iptables \
        openssl \
        python3 \
        tini \
    && rm -rf /var/lib/apt/lists/*

COPY --from=tools /usr/local/bin/bao /usr/local/bin/bao
COPY --from=tools /usr/local/lib/python3.11/dist-packages /usr/local/lib/python3.11/dist-packages
RUN bao version && python3 -c 'import hvac, pg8000'

EXPOSE 8080
ENTRYPOINT ["/usr/bin/tini", "--", "sh", "/opt/app-host/start.sh"]
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8080/healthz", timeout=2)'
