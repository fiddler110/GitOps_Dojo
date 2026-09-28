# app-host (vault-fundamentals, labs 11-13): the platform students deploy to.
# apphost.py (mounted read-only from this folder by the overlay) runs as root
# and runs each slot's app as its own user.
#
# The tools an app calls come from the terminal image run.sh has just built
# (TOOLS_IMAGE, set by the overlay), so each has one pin, in the terminal's
# Dockerfiles: bao (the Agent) and the Python packages (hvac, pg8000). Both
# images are Debian bookworm, so the Python packages fit as they are.
ARG TOOLS_IMAGE=gitopsdojo/web-terminal:base
FROM ${TOOLS_IMAGE} AS tools

FROM docker.io/library/debian:bookworm-slim@sha256:3783cc01769c7b2b1b83a5c5ad96c815348e28ed7da68e2e3687004faa906251

# python3: the platform and the apps. openssl: the platform's signing key and
# signature checks. tini: PID 1, reaping the processes of stopped apps.
# util-linux (su, unshare, prlimit) and passwd (useradd) are in the base image.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        openssl \
        python3 \
        tini \
    && rm -rf /var/lib/apt/lists/*

COPY --from=tools /usr/local/bin/bao /usr/local/bin/bao
COPY --from=tools /usr/local/lib/python3.11/dist-packages /usr/local/lib/python3.11/dist-packages
RUN bao version && python3 -c 'import hvac, pg8000'

EXPOSE 8080
ENTRYPOINT ["/usr/bin/tini", "--", "python3", "-B", "-u", "/opt/app-host/apphost.py"]
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8080/healthz", timeout=2)'
