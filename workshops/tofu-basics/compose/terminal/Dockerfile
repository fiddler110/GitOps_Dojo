# Extends the shared web-terminal base image (see engine/docker-compose.yml
# and engine/run.sh, which builds and tags gitopsdojo/web-terminal:base
# before this Dockerfile runs) with OpenTofu and an offline provider mirror.
# Everything else (account provisioning, code-server/ttyd, shell helpers) is
# inherited unchanged from the base image's entrypoint. Base image is Debian
# (see engine/web-terminal/Dockerfile for why), so this uses apt, not apk.
FROM gitopsdojo/web-terminal:base

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
# the CLI config below makes that the ONLY install source. Versions are
# pinned; the checksums are verified by `tofu providers mirror` against the
# registry's signed hashes. Track B adds its cloud provider to this list.
COPY mirror.tf /tmp/mirror/mirror.tf
RUN set -eux; \
    cd /tmp/mirror; \
    tofu providers mirror -platform="linux_${TARGETARCH}" /opt/tofu-providers; \
    rm -rf /tmp/mirror; \
    chmod -R a+rX /opt/tofu-providers

COPY tofurc /etc/tofu/tofurc
# Students run `su - <name>` (a login shell that drops the container's ENV),
# so the CLI-config variable is exported from /etc/zsh/zshenv instead: zsh
# reads it for every shell — ttyd, tmux panes, the code-server terminal.
# Root-owned, so students cannot repoint or edit it.
RUN set -eux; \
    chmod 0644 /etc/tofu/tofurc; \
    printf '\n# tofu-basics: use the offline provider mirror (see /etc/tofu/tofurc)\nexport TF_CLI_CONFIG_FILE=/etc/tofu/tofurc\n' >> /etc/zsh/zshenv; \
    printf 'export TF_CLI_CONFIG_FILE=/etc/tofu/tofurc\n' > /etc/profile.d/tofu.sh
ENV TF_CLI_CONFIG_FILE=/etc/tofu/tofurc

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

# ENTRYPOINT is inherited from the base image (web-terminal-entrypoint) —
# same account provisioning and workspace-control.py launch as every other
# workshop. No USER override: the base image needs root for the whole
# container lifetime — see the comment in engine/web-terminal/Dockerfile.

# Base image's HEALTHCHECK is inherited too; restated here so a static scan
# of this file alone (which doesn't resolve FROM) doesn't flag it missing.
# Keep identical to engine/web-terminal/Dockerfile: workspace-control.py
# rejects /status without the X-Control-Token header.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null --header="X-Control-Token: ${CONTROL_TOKEN}" http://127.0.0.1:7682/status || exit 1
