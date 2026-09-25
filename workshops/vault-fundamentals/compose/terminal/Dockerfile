# vault-fundamentals' link in the terminal build chain (engine/run.sh sets
# BASE to the image below this one, here the openbao module's link with bao;
# see workshops/README.md). Adds sops, gitleaks and Python's hvac. Student
# terminals have no internet, so every tool is baked in here, version-pinned
# and sha256-verified per architecture. The entrypoint is inherited unchanged.
ARG BASE=gitopsdojo/web-terminal:base
FROM ${BASE}

ARG TARGETARCH=amd64

# https://github.com/getsops/sops/releases/tag/v3.13.3
ARG SOPS_VERSION=3.13.3
RUN set -eux; \
    case "${TARGETARCH}" in \
    amd64) sha256="e5bec3346a873ae91d871550f3e698c1aad962aff462a080e40f25fde17fef6b" ;; \
    arm64) sha256="53b0abacd38ef1b12a66d6c100956691b9cefce018d91f81e73ddf7438b94d77" ;; \
    *) echo "Unsupported architecture for sops: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    wget -O /tmp/sops \
      "https://github.com/getsops/sops/releases/download/v${SOPS_VERSION}/sops-v${SOPS_VERSION}.linux.${TARGETARCH}"; \
    echo "${sha256}  /tmp/sops" | sha256sum -c -; \
    install -m 0755 /tmp/sops /usr/local/bin/sops; \
    rm -f /tmp/sops

# https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1 (amd64 is "x64")
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

# Python's Vault client, hvac, for lab 4 (the app reads its secret with the
# SDK), the pure-Python Postgres driver pg8000 for lab 10, and their whole
# dependency trees. Every wheel is pure Python (py3-none-any or
# py2.py3-none-any), so hvac-wheels.sha256 has one hash per package for both
# architectures. app-host copies these packages from this image (labs 9-11). wget fetches them (it uses the system CA store, as the other
# downloads do; pip would use its own) and sha256sum checks them; pip then
# runs straight from its own wheel (the base image has none) and installs
# offline. /usr/local is pip's, not apt's, hence --break-system-packages.
# https://pypi.org/project/hvac/2.4.0/
COPY hvac-wheels.sha256 /tmp/wheels/SHA256SUMS
RUN set -eux; \
    cd /tmp/wheels; \
    while read -r _sum whl; do \
      name="${whl%%-*}"; tag="$(echo "$whl" | awk -F- '{print $(NF-2)}')"; \
      wget -q -O "$whl" "https://files.pythonhosted.org/packages/${tag}/${name%"${name#?}"}/${name}/${whl}"; \
    done < SHA256SUMS; \
    sha256sum -c SHA256SUMS; \
    pip="$(ls pip-*.whl)"; \
    python3 "$pip/pip" install --no-cache-dir --disable-pip-version-check --root-user-action=ignore \
      --break-system-packages \
      --no-index --no-deps $(ls *.whl | grep -v '^pip-'); \
    cd /; rm -rf /tmp/wheels; \
    python3 -c 'import hvac, requests, pg8000'

# psql for lab 10's dynamic database logins, and jq for the JSON that bao
# and the APIs print (labs 9-11). From Debian's archive, which apt checks
# against Debian's signing keys.
RUN apt-get update && apt-get install -y --no-install-recommends jq postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# sops checks GitHub for a newer release on every run, which only prints a
# warning in the offline terminal. zshenv for `su -` login shells (see the
# openbao module's Dockerfile), profile.d for sh/bash.
RUN set -eux; \
    printf '\n# vault-fundamentals: no sops update check (no internet)\nexport SOPS_DISABLE_VERSION_CHECK=1\n' >> /etc/zsh/zshenv; \
    printf 'export SOPS_DISABLE_VERSION_CHECK=1\n' > /etc/profile.d/sops.sh
ENV SOPS_DISABLE_VERSION_CHECK=1

# ENTRYPOINT and HEALTHCHECK are inherited from the base image; the
# HEALTHCHECK is restated so a static scan of this file alone (which doesn't
# resolve FROM) doesn't flag it missing.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD web-terminal-healthcheck
