# cloud-policy-as-code terminal: tofu-basics' OpenTofu + offline azurerm mirror, plus opa and conftest.
# Extends the shared web-terminal base image (see engine/docker-compose.yml
# and engine/run.sh, which builds and tags gitopsdojo/web-terminal:base
# before this Dockerfile runs) with OpenTofu and an offline provider mirror.
# Everything else (account provisioning, code-server/ttyd, shell helpers) is
# inherited unchanged from the base image's entrypoint. Base image is Debian
# (see engine/web-terminal/Dockerfile for why), so this uses apt, not apk.
# engine/run.sh sets BASE to the image below this one in the chain (docs/archive/MODULES-PLAN.md §4.2).
ARG BASE=gitopsdojo/web-terminal:base
FROM ${BASE}

ARG TOFU_VERSION=1.12.6
# TARGETARCH is set automatically by BuildKit to match the build platform
# (amd64/arm64); default keeps a manual `docker build` without BuildKit
# working. Checksums from
# https://github.com/opentofu/opentofu/releases/download/v1.12.6/tofu_1.12.6_SHA256SUMS.
ARG TARGETARCH=amd64
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
    # `terraform` runs OpenTofu. A symlink (not a shell alias) so it also
    # works in scripts, tmux, ttyd and the code-server terminal.
    ln -s /usr/local/bin/tofu /usr/local/bin/terraform

# Offline provider mirror. The lab network has no internet, so `tofu init`
# cannot reach registry.opentofu.org — instead every provider the labs use is
# downloaded once, here at build time, into a read-only filesystem mirror and
# the CLI config below makes that the ONLY install source. Versions are pinned
# (mirror.tf); `tofu providers mirror` verifies each download against the
# registry's signed hashes. The mirror is then UNPACKED (unpack-mirror.py) so
# `tofu init` symlinks providers into each student's folder instead of copying
# azurerm's ~218 MB thirty times over.
COPY mirror.tf /tmp/mirror/mirror.tf
COPY unpack-mirror.py /tmp/unpack-mirror.py
RUN set -eux; \
    cd /tmp/mirror; \
    tofu providers mirror -platform="linux_${TARGETARCH}" /tmp/mirror/packed; \
    python3 /tmp/unpack-mirror.py /tmp/mirror/packed /opt/tofu-providers; \
    rm -rf /tmp/mirror /tmp/unpack-mirror.py; \
    chmod -R a+rX /opt/tofu-providers

COPY tofurc /etc/tofu/tofurc
# Students run `su - <name>` (a login shell that drops the container's ENV),
# so the CLI-config variable is exported from /etc/zsh/zshenv instead: zsh
# reads it for every shell — ttyd, tmux panes, the code-server terminal.
# Root-owned, so students cannot repoint or edit it.
RUN set -eux; \
    chmod 0644 /etc/tofu/tofurc; \
    printf '\n# cloud-policy-as-code: use the offline provider mirror (see /etc/tofu/tofurc)\nexport TF_CLI_CONFIG_FILE=/etc/tofu/tofurc\n' >> /etc/zsh/zshenv; \
    printf 'export TF_CLI_CONFIG_FILE=/etc/tofu/tofurc\n' > /etc/profile.d/tofu.sh
ENV TF_CLI_CONFIG_FILE=/etc/tofu/tofurc

# State lives in Dojo Cloud's http backend (see infra/versions.tf). Its Basic auth is the
# student's ARM client id and secret, so map them onto the backend's variables. This is
# appended after the dojo-cloud module's zshenv line that sets ARM_*, so it sees them.
RUN printf '\n# cloud-policy-as-code: http state backend credentials = the ARM service principal\nif [ -n "${ARM_CLIENT_ID:-}" ]; then export TF_HTTP_USERNAME=$ARM_CLIENT_ID TF_HTTP_PASSWORD=$ARM_CLIENT_SECRET; fi\n' >> /etc/zsh/zshenv

# HCL syntax highlighting for .tf / .tfvars in code-server: the OpenTofu
# extension (published by the OpenTofu project's own verified namespace on
# Open VSX), pinned + sha256-verified per architecture and installed into the
# same shared, read-only extensions dir the base image uses. It bundles its
# own language server (tofu-ls), but that indexes the workspace and pulls
# provider schemas, which costs memory per student and can't reach the
# internet here anyway -- so the build flips its default off (highlighting
# and bracket matching don't need it). Students can still switch it on in
# Settings. disable-tofu-ls.py fails the build if a future version renames
# that setting, instead of silently shipping with the server running.
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

# Policy tools: opa (Rego tests) and conftest (checks a `tofu show -json` plan). Static binaries, so
# runner-pool's jobs copy the very same ones (JOB_TOOLS in the overlay). TARGETARCH is declared above.
ARG OPA_VERSION=1.21.1
ARG CONFTEST_VERSION=0.71.0
# Checksums: opa_linux_<arch>_static.sha256 and conftest_0.71.0_checksums.txt
RUN set -eux; \
    case "${TARGETARCH}" in \
    amd64) opa_arch="amd64"; opa_sha256="668506eb17a2eaa1fce6cc0d1f42ef85125d4ac5bda5fc74d1152d0c77145031"; \
           ct_arch="x86_64"; ct_sha256="765dfefdf0730693d7541ea0147e10d530a54ed257bbfec055ff34c837ffdf72" ;; \
    arm64) opa_arch="arm64"; opa_sha256="9a1f3625529c6f01240fe68286dde06aa0b23c5253da700ac48f4d943ff8a4de"; \
           ct_arch="arm64"; ct_sha256="542f255081cfab9919cba327d3c4014fd46d6ee3f0441c634b14b1465e9469d9" ;; \
    *) echo "Unsupported architecture for opa/conftest: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    wget -O /tmp/opa "https://github.com/open-policy-agent/opa/releases/download/v${OPA_VERSION}/opa_linux_${opa_arch}_static"; \
    echo "${opa_sha256}  /tmp/opa" | sha256sum -c -; \
    install -m 0755 /tmp/opa /usr/local/bin/opa; \
    wget -O /tmp/conftest.tar.gz "https://github.com/open-policy-agent/conftest/releases/download/v${CONFTEST_VERSION}/conftest_${CONFTEST_VERSION}_Linux_${ct_arch}.tar.gz"; \
    echo "${ct_sha256}  /tmp/conftest.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/conftest.tar.gz -C /tmp conftest; \
    install -m 0755 /tmp/conftest /usr/local/bin/conftest; \
    rm -f /tmp/opa /tmp/conftest /tmp/conftest.tar.gz

# Dojo Cloud's client side (credential broker, dojo-env, CA trust) comes from
# the dojo-cloud module's own link in the chain, below this one.

# ENTRYPOINT is inherited from the base image (web-terminal-entrypoint) —
# same account provisioning and workspace-control.py launch as every other
# workshop. No USER override: the base image needs root for the whole
# container lifetime — see the comment in engine/web-terminal/Dockerfile.

# `lab-prep <lab>` brings a student's workspace to where that lab starts, so
# they can resume mid-workshop (see the script's header for what each lab needs).
COPY lab-prep /usr/local/bin/lab-prep
RUN chmod 0755 /usr/local/bin/lab-prep

# Base image's HEALTHCHECK is inherited too; restated here so a static scan
# of this file alone (which doesn't resolve FROM) doesn't flag it missing.
# Call the base image's script rather than copying its wget line: workspace-control.py
# rejects /status without the X-Control-Token header, and that lives in
# engine/web-terminal/healthcheck.sh only.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD web-terminal-healthcheck
