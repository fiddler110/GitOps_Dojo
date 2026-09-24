# Extends the shared web-terminal base image (built and tagged
# gitopsdojo/web-terminal:base by engine/run.sh) with the vault tools:
# bao (OpenBao CLI), sops and gitleaks. Student terminals have no internet,
# so every tool is baked in here, version-pinned and sha256-verified per
# architecture. The entrypoint and HEALTHCHECK are inherited unchanged.
FROM gitopsdojo/web-terminal:base

ARG TARGETARCH=amd64

# Checksums from each release's own checksums file:
# https://github.com/openbao/openbao/releases/tag/v2.6.3
ARG BAO_VERSION=2.6.3
RUN set -eux; \
    case "${TARGETARCH}" in \
    amd64) sha256="c6463ddd4fdc4214b62a7ffdeaa0fc6df170f7e6b75c6dea2c5e525bdc932ed3" ;; \
    arm64) sha256="47858610a9853b15e2541c69c0a884861b881e2f4a172fccc429ce5cd3f047bd" ;; \
    *) echo "Unsupported architecture for bao: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    wget -O /tmp/bao.tar.gz \
      "https://github.com/openbao/openbao/releases/download/v${BAO_VERSION}/openbao_${BAO_VERSION}_linux_${TARGETARCH}.tar.gz"; \
    echo "${sha256}  /tmp/bao.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/bao.tar.gz -C /tmp bao; \
    install -m 0755 /tmp/bao /usr/local/bin/bao; \
    rm -f /tmp/bao.tar.gz /tmp/bao

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

# The CLI talks to OpenBao directly on workshop_lab, not through the gateway
# (PLAN.md §5.4). Students run `su - <name>` (a login zsh that drops the
# container's ENV), so export it from /etc/zsh/zshenv, which zsh reads for
# every shell (ttyd, tmux panes, the code-server terminal), plus profile.d
# for sh/bash. Root-owned, so students cannot repoint it.
RUN set -eux; \
    printf '\n# vault-fundamentals: the class OpenBao server\nexport BAO_ADDR=http://openbao:8200\n' >> /etc/zsh/zshenv; \
    printf 'export BAO_ADDR=http://openbao:8200\n' > /etc/profile.d/openbao.sh
ENV BAO_ADDR=http://openbao:8200
