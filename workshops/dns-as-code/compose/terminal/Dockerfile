# Extends the shared web-terminal base image (see engine/docker-compose.yml
# and engine/run.sh, which builds and tags gitopsdojo/web-terminal:base
# before this Dockerfile runs) with the tools this workshop's lab needs:
# dnscontrol itself and `dig` for querying it. python3 is already in the
# base image (it runs workshop-control.py). Everything else (account
# provisioning, code-server/ttyd, shell helpers) is inherited unchanged
# from the base image's entrypoint. Base image is Debian (see
# engine/web-terminal/Dockerfile for why), so this uses apt, not apk.
FROM gitopsdojo/web-terminal:base

RUN apt-get update && apt-get install -y --no-install-recommends dnsutils \
    && rm -rf /var/lib/apt/lists/*

ARG DNSCONTROL_VERSION=5.0.4
# TARGETARCH is set automatically by BuildKit to match the build platform
# (amd64/arm64); default keeps a manual `docker build` without BuildKit working.
ARG TARGETARCH=amd64
RUN set -eux; \
    case "${TARGETARCH}" in \
    amd64) dc_arch="amd64"; dc_sha256="f1067b2d6e2242206b7140dd01ba34424fe577b0f5edd75b1fcd92caf84af35a" ;; \
    arm64) dc_arch="arm64"; dc_sha256="eeb81fcc9ec66908593a5fbb61e5e45aa3f15237821702c008000c1245c08d28" ;; \
    *) echo "Unsupported architecture for dnscontrol: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    wget -O /tmp/dnscontrol.tar.gz \
      "https://github.com/DNSControl/dnscontrol/releases/download/v${DNSCONTROL_VERSION}/dnscontrol_${DNSCONTROL_VERSION}_linux_${dc_arch}.tar.gz"; \
    echo "${dc_sha256}  /tmp/dnscontrol.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/dnscontrol.tar.gz -C /tmp dnscontrol; \
    install -m 0755 /tmp/dnscontrol /usr/local/bin/dnscontrol; \
    rm -f /tmp/dnscontrol.tar.gz /tmp/dnscontrol

# ENTRYPOINT is inherited from the base image (web-terminal-entrypoint) —
# same account provisioning and workspace-control.py launch as every other
# workshop. No USER override either: the base image needs root for the
# whole container lifetime (dynamic useradd + spawning per-student
# code-server/ttyd processes), not just setup — see the comment in
# engine/web-terminal/Dockerfile.

# Base image's HEALTHCHECK is inherited too; restated here so a static scan
# of this file alone (which doesn't resolve FROM) doesn't flag it missing.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:7682/status || exit 1
