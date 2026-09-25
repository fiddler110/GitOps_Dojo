# Extends the shared web-terminal base image (see engine/docker-compose.yml
# and engine/run.sh, which builds and tags gitopsdojo/web-terminal:base
# before this Dockerfile runs) with the ACME tooling this workshop's lab
# needs: the `step` CLI (talks to step-ca, bootstraps trust), certbot and
# acme.sh (the two ACME clients students compare), plus openssl/dig/jq/cron
# for verification and renewal automation. Everything else (account
# provisioning, code-server/ttyd, shell helpers) is inherited unchanged
# from the base image's entrypoint. Base image is Debian (see
# engine/web-terminal/Dockerfile for why), so this uses apt, not apk.
# engine/run.sh sets BASE to the image below this one in the chain (MODULES-PLAN.md §4.2).
ARG BASE=gitopsdojo/web-terminal:base
FROM ${BASE}

RUN apt-get update && apt-get install -y --no-install-recommends \
    certbot \
    dnsutils \
    openssl \
    jq \
    cron \
    curl \
    && rm -rf /var/lib/apt/lists/*

# acme.sh installed as a shared script, not via its own installer (which
# assumes a single-user home directory and sets up its own cron job) —
# every student runs it under their own account, and it auto-creates its
# per-user state under $HOME/.acme.sh on first invocation, the same
# isolation boundary every other per-student tool in this stack already
# relies on.
ARG ACMESH_VERSION=3.1.1
RUN curl -fsSL -o /tmp/acme.sh.tar.gz \
      "https://github.com/acmesh-official/acme.sh/archive/refs/tags/${ACMESH_VERSION}.tar.gz" \
    && mkdir -p /opt/acme.sh \
    && tar -xzf /tmp/acme.sh.tar.gz -C /opt/acme.sh --strip-components=1 \
    && rm -f /tmp/acme.sh.tar.gz \
    && ln -s /opt/acme.sh/acme.sh /usr/local/bin/acme.sh

ARG STEP_CLI_VERSION=0.30.6
# TARGETARCH is set automatically by BuildKit to match the build platform
# (amd64/arm64); default keeps a manual `docker build` without BuildKit
# working. Checksums from https://github.com/smallstep/cli/releases/download/v0.30.6/checksums.txt.
ARG TARGETARCH=amd64
RUN set -eux; \
    case "${TARGETARCH}" in \
    amd64) step_arch="amd64"; step_sha256="e44a5dc5f880a694b24a0f2941a69a81b0bc6ee053170fdfde18453d4d5816de" ;; \
    arm64) step_arch="arm64"; step_sha256="eff511c3e6797039702e74fada62b10b079e413742f925703e5b7d810e611619" ;; \
    *) echo "Unsupported architecture for step CLI: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    wget -O /tmp/step.tar.gz \
      "https://github.com/smallstep/cli/releases/download/v${STEP_CLI_VERSION}/step_linux_${STEP_CLI_VERSION}_${step_arch}.tar.gz"; \
    echo "${step_sha256}  /tmp/step.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/step.tar.gz -C /tmp; \
    install -m 0755 "/tmp/step_${STEP_CLI_VERSION}/bin/step" /usr/local/bin/step; \
    rm -rf /tmp/step.tar.gz "/tmp/step_${STEP_CLI_VERSION}"

# Start-up work (cron for Lab 4's renewal crontabs, per-account webroot
# folders) runs as a start.d hook from the base entrypoint, after every
# account exists; see start.d/90-cert-autorenewal.sh. No USER override: the
# base image needs root for the whole container lifetime (dynamic useradd +
# spawning per-student code-server/ttyd processes).
COPY start.d/90-cert-autorenewal.sh /etc/dojo/start.d/90-cert-autorenewal.sh

# `lab-prep <lab>` brings a student's workspace to where that lab starts, so
# they can resume mid-workshop (see the script's header for what each lab needs).
COPY lab-prep /usr/local/bin/lab-prep
RUN chmod 0755 /usr/local/bin/lab-prep

# Base image's HEALTHCHECK is inherited too; restated here so a static scan
# of this file alone (which doesn't resolve FROM) doesn't flag it missing.
# Call the base image's script rather than copying its wget line: the command needs the
# X-Control-Token header and lives in engine/web-terminal/healthcheck.sh only.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD web-terminal-healthcheck
