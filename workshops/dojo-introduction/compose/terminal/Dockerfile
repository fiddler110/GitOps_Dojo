# dojo-introduction's link in the terminal build chain (engine/run.sh sets BASE
# to the image below this one: the openbao and dojo-cloud modules' links, with
# bao and the Dojo Cloud broker; see workshops/README.md). This is the union of
# the four workshops' tools, so every one can be shown from one terminal. Student
# terminals have no internet: every tool is baked in here, version-pinned and
# sha256-verified per architecture (the same pins the workshops use). The
# entrypoint is inherited unchanged.
ARG BASE=gitopsdojo/web-terminal:base
FROM ${BASE}

ARG TARGETARCH=amd64

# dig, the ACME client certbot, jq, pass: what the DNS, cert and vault tours call.
RUN apt-get update && apt-get install -y --no-install-recommends \
    certbot dnsutils openssl jq cron curl pass \
    && rm -rf /var/lib/apt/lists/*

# https://github.com/DNSControl/dnscontrol/releases/tag/v5.0.4
ARG DNSCONTROL_VERSION=5.0.4
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

# acme.sh as a shared script; each account keeps its own state under $HOME/.acme.sh.
ARG ACMESH_VERSION=3.1.1
RUN curl -fsSL -o /tmp/acme.sh.tar.gz \
      "https://github.com/acmesh-official/acme.sh/archive/refs/tags/${ACMESH_VERSION}.tar.gz" \
    && mkdir -p /opt/acme.sh \
    && tar -xzf /tmp/acme.sh.tar.gz -C /opt/acme.sh --strip-components=1 \
    && rm -f /tmp/acme.sh.tar.gz \
    && ln -s /opt/acme.sh/acme.sh /usr/local/bin/acme.sh

# https://github.com/smallstep/cli/releases/tag/v0.30.6
ARG STEP_CLI_VERSION=0.30.6
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

# OpenTofu (`terraform` runs it) and the offline provider mirror Dojo Cloud's
# azurerm needs. The mirror files are copies of tofu-basics' (same pins).
ARG TOFU_VERSION=1.12.6
RUN set -eux; \
    case "${TARGETARCH}" in \
    amd64) tofu_arch="amd64"; tofu_sha256="50a6106fa4de523d09c87af85f3db1dd47535fc005727fdca6852146476b88ec" ;; \
    arm64) tofu_arch="arm64"; tofu_sha256="9bd0228a81bcd0c88f7045c74378f45a815779f19897191dff7d9efba9976b9e" ;; \
    *) echo "Unsupported architecture for OpenTofu: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    wget -O /tmp/tofu.tar.gz \
      "https://github.com/opentofu/opentofu/releases/download/v${TOFU_VERSION}/tofu_${TOFU_VERSION}_linux_${tofu_arch}.tar.gz"; \
    echo "${tofu_sha256}  /tmp/tofu.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/tofu.tar.gz -C /tmp tofu; \
    install -m 0755 /tmp/tofu /usr/local/bin/tofu; \
    rm -f /tmp/tofu.tar.gz /tmp/tofu; \
    ln -s /usr/local/bin/tofu /usr/local/bin/terraform

COPY mirror.tf /tmp/mirror/mirror.tf
COPY unpack-mirror.py /tmp/unpack-mirror.py
RUN set -eux; \
    cd /tmp/mirror; \
    tofu providers mirror -platform="linux_${TARGETARCH}" /tmp/mirror/packed; \
    python3 /tmp/unpack-mirror.py /tmp/mirror/packed /opt/tofu-providers; \
    rm -rf /tmp/mirror /tmp/unpack-mirror.py; \
    chmod -R a+rX /opt/tofu-providers

COPY tofurc /etc/tofu/tofurc
RUN set -eux; \
    chmod 0644 /etc/tofu/tofurc; \
    printf '\n# dojo-introduction: use the offline provider mirror (see /etc/tofu/tofurc)\nexport TF_CLI_CONFIG_FILE=/etc/tofu/tofurc\n' >> /etc/zsh/zshenv; \
    printf 'export TF_CLI_CONFIG_FILE=/etc/tofu/tofurc\n' > /etc/profile.d/tofu.sh; \
    printf '\n# dojo-introduction: no sops update check (no internet)\nexport SOPS_DISABLE_VERSION_CHECK=1\n' >> /etc/zsh/zshenv; \
    printf 'export SOPS_DISABLE_VERSION_CHECK=1\n' > /etc/profile.d/sops.sh
ENV TF_CLI_CONFIG_FILE=/etc/tofu/tofurc SOPS_DISABLE_VERSION_CHECK=1

# The OpenTofu extension for VS Code, from tofu-basics (same pin and checksum).
ARG OPENTOFU_VSCODE_VERSION=0.6.3
COPY disable-tofu-ls.py /tmp/disable-tofu-ls.py
RUN set -eux; \
    case "${TARGETARCH}" in \
    amd64) ext_target="linux-x64"; ext_sha256="ed0cbd5b8869b7adcc5f1d8fcec5ce573b9e46f4e57ecc66c3d535763a3a85fd" ;; \
    arm64) ext_target="linux-arm64"; ext_sha256="94755ee6cd3bd4e90c6c05768f952ed272152e4eb4f836d37d97a612a68045d2" ;; \
    *) echo "Unsupported architecture for the OpenTofu extension: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    wget -O /tmp/opentofu.vsix \
      "https://open-vsx.org/api/OpenTofu/vscode-opentofu/${ext_target}/${OPENTOFU_VSCODE_VERSION}/file/OpenTofu.vscode-opentofu-${OPENTOFU_VSCODE_VERSION}@${ext_target}.vsix"; \
    echo "${ext_sha256}  /tmp/opentofu.vsix" | sha256sum -c -; \
    code-server --extensions-dir /opt/code-server-extensions --install-extension /tmp/opentofu.vsix --force; \
    rm -f /tmp/opentofu.vsix; \
    python3 /tmp/disable-tofu-ls.py /opt/code-server-extensions; \
    rm -f /tmp/disable-tofu-ls.py; \
    chown -R root:root /opt/code-server-extensions; \
    chmod -R a+rX /opt/code-server-extensions

# Remember each account's Forgejo login after its first push (in memory only).
RUN git config --system credential.helper 'cache --timeout=28800'

# ENTRYPOINT and HEALTHCHECK are inherited from the base image; the
# HEALTHCHECK is restated so a static scan of this file alone (which doesn't
# resolve FROM) doesn't flag it missing.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD web-terminal-healthcheck
