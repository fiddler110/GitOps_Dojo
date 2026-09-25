# openbao module's link in the terminal build chain (engine/run.sh sets BASE
# to the image below this one; see workshops/README.md). Adds the OpenBao CLI
# and points it at the class server. Student terminals have no internet, so
# the CLI is baked in, version-pinned and sha256-verified per architecture.
# The entrypoint is inherited unchanged.
ARG BASE=gitopsdojo/web-terminal:base
FROM ${BASE}

ARG TARGETARCH=amd64

# Checksums from the release's checksums.txt:
# https://github.com/openbao/openbao/releases/tag/v2.7.0
ARG BAO_VERSION=2.7.0
RUN set -eux; \
    case "${TARGETARCH}" in \
    amd64) sha256="c3ab5de9e778223445487ccbfb16c291bf491642b688f3a3df5aeba23d9b3667" ;; \
    arm64) sha256="555bb2a955d88c83e4c025f63e1703a0f4c01161cd81728002992b9a82433e49" ;; \
    *) echo "Unsupported architecture for bao: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    wget -O /tmp/bao.tar.gz \
      "https://github.com/openbao/openbao/releases/download/v${BAO_VERSION}/openbao_${BAO_VERSION}_linux_${TARGETARCH}.tar.gz"; \
    echo "${sha256}  /tmp/bao.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/bao.tar.gz -C /tmp bao; \
    install -m 0755 /tmp/bao /usr/local/bin/bao; \
    rm -f /tmp/bao.tar.gz /tmp/bao

# The CLI talks to OpenBao directly on workshop_lab, not through the gateway.
# Tools built on the Vault client (sops, hvac) read VAULT_ADDR, not BAO_ADDR,
# so set both. Students run `su - <name>` (a login zsh that drops the
# container's ENV), so export them from /etc/zsh/zshenv, which zsh reads for
# every shell (ttyd, tmux panes, the code-server terminal), plus profile.d
# for sh/bash. Root-owned, so students cannot repoint them.
RUN set -eux; \
    printf '\n# openbao module: the class OpenBao server\nexport BAO_ADDR=http://openbao:8200\nexport VAULT_ADDR=http://openbao:8200\n' >> /etc/zsh/zshenv; \
    printf 'export BAO_ADDR=http://openbao:8200\nexport VAULT_ADDR=http://openbao:8200\n' > /etc/profile.d/openbao.sh
ENV BAO_ADDR=http://openbao:8200 VAULT_ADDR=http://openbao:8200

# ENTRYPOINT and HEALTHCHECK are inherited from the base image; the
# HEALTHCHECK is restated so a static scan of this file alone (which doesn't
# resolve FROM) doesn't flag it missing.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD web-terminal-healthcheck
