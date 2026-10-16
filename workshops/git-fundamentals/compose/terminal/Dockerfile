# Extends the shared web-terminal base image with one script: `lab-prep`.
# Everything else (account provisioning, code-server/ttyd, shell helpers) is
# inherited unchanged from the base image's entrypoint.
# dojo sets BASE to the image below this one in the chain (docs/archive/MODULES-PLAN.md §4.2).
ARG BASE=gitopsdojo/web-terminal:base
FROM ${BASE}

# `lab-prep <lab>` brings a student's workspace to where that lab starts, so
# they can resume mid-workshop (see the script's header for what each lab needs).
COPY lab-prep /usr/local/bin/lab-prep
# `lab-history` builds ~/lab/history-repo, the 15-commit practice repo for Lab 4.
COPY lab-history /usr/local/bin/lab-history
RUN chmod 0755 /usr/local/bin/lab-prep /usr/local/bin/lab-history

# gitleaks, for the secret scan in Lab 4 (same pinned release and checksums as vault-fundamentals).
# https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1 (amd64 is "x64")
ARG TARGETARCH
ARG GITLEAKS_VERSION=8.30.1
RUN set -eux; \
    case "${TARGETARCH}" in \
    amd64) arch="x64";   sha256="551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb" ;; \
    arm64) arch="arm64"; sha256="e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080" ;; \
    *) echo "Unsupported architecture for gitleaks: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    wget -O /tmp/gitleaks.tar.gz \
      "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_${arch}.tar.gz"; \
    echo "${sha256}  /tmp/gitleaks.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/gitleaks.tar.gz -C /tmp gitleaks; \
    install -m 0755 /tmp/gitleaks /usr/local/bin/gitleaks; \
    rm -f /tmp/gitleaks.tar.gz /tmp/gitleaks

# Base image's HEALTHCHECK is inherited too; restated here so a static scan
# of this file alone (which doesn't resolve FROM) doesn't flag it missing.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD web-terminal-healthcheck
