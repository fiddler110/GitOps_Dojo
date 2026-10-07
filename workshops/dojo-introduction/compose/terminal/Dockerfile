# dojo-introduction's link in the terminal build chain (engine/run.sh sets BASE
# to the image below this one: the dojo-cloud and dns-gate modules' links, with
# the Dojo Cloud broker and the DNS key; see workshops/README.md). It has the
# tools of dns-as-code and tofu-basics, the two the tour shows. Student
# terminals have no internet: every tool is baked in here, version-pinned and
# sha256-verified per architecture (the same pins the workshops use). The
# entrypoint is inherited unchanged.
ARG BASE=gitopsdojo/web-terminal:base
FROM ${BASE}

ARG TARGETARCH=amd64

# dig and jq: what the DNS tour calls.
RUN apt-get update && apt-get install -y --no-install-recommends \
    dnsutils jq curl \
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
    printf 'export TF_CLI_CONFIG_FILE=/etc/tofu/tofurc\n' > /etc/profile.d/tofu.sh
ENV TF_CLI_CONFIG_FILE=/etc/tofu/tofurc

# The OpenTofu extension for VS Code, from tofu-basics (same pin and checksum).
# Guarded by `command -v code-server`: the Zellij flavor's leaf has no
# code-server at all (a sibling of the vscode leaf, not built on top of it
# — see engine/README.md's "Terminal flavor" section), so there's nothing
# to install the extension into.
ARG OPENTOFU_VSCODE_VERSION=0.6.3
COPY disable-tofu-ls.py /tmp/disable-tofu-ls.py
RUN set -eux; \
    if command -v code-server >/dev/null 2>&1; then \
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
      chown -R root:root /opt/code-server-extensions; \
      chmod -R a+rX /opt/code-server-extensions; \
    fi; \
    rm -f /tmp/disable-tofu-ls.py

# Remember each account's Forgejo login after its first push (in memory only).
RUN git config --system credential.helper 'cache --timeout=28800'

# ENTRYPOINT and HEALTHCHECK are inherited from the base image; the
# HEALTHCHECK is restated so a static scan of this file alone (which doesn't
# resolve FROM) doesn't flag it missing.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD web-terminal-healthcheck
