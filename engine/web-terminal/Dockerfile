# syntax=docker/dockerfile:1.7
# The line above enables BuildKit's `RUN --mount=type=secret` used below --
# needed for CORP_CA_BUNDLE (see run.sh), not for anything else in this
# file. Must stay the literal first line.

# Debian, not Alpine, deliberately: code-server's official releases require
# glibc (Alpine's musl libc isn't supported upstream -- the musl-compatible
# fork is explicitly work-in-progress), so this is the one image in the
# stack that isn't Alpine-based. Everything not available via apt (ttyd,
# zoxide, glow, code-server) is pinned to a specific version and
# sha256-verified below, same as this file always did on Alpine.
FROM docker.io/library/debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        bat \
        bash \
        ca-certificates \
        curl \
        fzf \
        git \
        iptables \
        nano \
        openssh-client \
        procps \
        python3 \
        ripgrep \
        sudo \
        tmux \
        vim \
        wget \
        zsh \
    && rm -rf /var/lib/apt/lists/*

# Debian's `bat` package installs the binary as `batcat` (name collision
# with an unrelated existing Debian package); alias the commonly-documented
# `bat` name to it.
RUN ln -sf /usr/bin/batcat /usr/local/bin/bat

# code-server: browser-based VS Code, the students' primary workspace.
ARG CODE_SERVER_VERSION=4.137.0
RUN set -eux; \
    case "$(dpkg --print-architecture)" in \
    amd64) cs_arch="amd64"; cs_sha256="f0165952d918092eb321a2d4e75a1e7035807d687b698ccda63aea2bfa1c58bc" ;; \
    arm64) cs_arch="arm64"; cs_sha256="0d2b58387833f328bec3723f842bf68e59031fc24b1e03a9c6c1659765a420ef" ;; \
    *) echo "Unsupported architecture for code-server: $(dpkg --print-architecture)" >&2; exit 1 ;; \
    esac; \
    wget -O /tmp/code-server.deb "https://github.com/coder/code-server/releases/download/v${CODE_SERVER_VERSION}/code-server_${CODE_SERVER_VERSION}_${cs_arch}.deb"; \
    echo "${cs_sha256}  /tmp/code-server.deb" | sha256sum -c -; \
    apt-get update && apt-get install -y --no-install-recommends /tmp/code-server.deb; \
    rm -rf /tmp/code-server.deb /var/lib/apt/lists/*; \
    # Strip built-in VS Code extensions that are dead weight in this
    # container specifically: Copilot (chat + inline-suggest) and the
    # Microsoft/GitHub account-sign-in flows that back it can't function at
    # all here -- there's no network route out once the stack is up (see
    # the curated-extensions comment below), so there's nothing to
    # authenticate against. mermaid-markdown-features goes too: no lab
    # content anywhere uses mermaid diagrams (checked workshops/*/content),
    # and it's the single largest built-in after Copilot. Deleted in this
    # same RUN/layer as the install above, not a later one -- a later
    # layer's `rm` only adds an OCI whiteout on top of the original layer
    # and doesn't shrink the image; the bytes it's "deleting" are already
    # permanently baked into that earlier layer either way.
    #
    # Note: removing github-authentication does NOT fix the "Timed out
    # waiting for authentication provider 'github' to register" error
    # visible in the browser console -- confirmed present on a stock,
    # unmodified image too (Copilot's own AgentHost feature repeatedly
    # polls api.github.com for a session regardless of which auth
    # extensions are installed). It's an existing side effect of this
    # container having no network route out, not something this trim
    # causes or fixes -- harmless, and unrelated to whether Copilot itself
    # is present.
    #
    # The Copilot *runtime* is a separate ~137 MB that the extensions/
    # deletes above don't touch: code-server ships it as node_modules/
    # @github/copilot* (a 90 MB native runtime.node plus its SDK), loaded
    # only by the AgentHost feature. Deleted too -- code-server still
    # starts and serves the workbench without it (verified), and it had no
    # network route to do anything with it regardless. The glob also
    # covers the arm64 variant (copilot-linux-arm64).
    #
    # Full removed/kept list + rationale + how to add something back:
    # see vscode-extensions.md in this directory. Keep that file in sync
    # with this list whenever it changes.
    rm -rf \
        /usr/lib/code-server/lib/vscode/extensions/copilot \
        /usr/lib/code-server/lib/vscode/extensions/copilot-chat \
        /usr/lib/code-server/lib/vscode/extensions/mermaid-markdown-features \
        /usr/lib/code-server/lib/vscode/extensions/microsoft-authentication \
        /usr/lib/code-server/lib/vscode/extensions/github-authentication \
        /usr/lib/code-server/lib/vscode/extensions/debug-auto-launch \
        /usr/lib/code-server/lib/vscode/extensions/debug-server-ready \
        /usr/lib/code-server/lib/vscode/extensions/npm \
        /usr/lib/code-server/lib/vscode/extensions/simple-browser \
        /usr/lib/code-server/lib/vscode/extensions/php \
        /usr/lib/code-server/lib/vscode/extensions/php-language-features \
        /usr/lib/code-server/lib/vscode/extensions/ipynb \
        /usr/lib/code-server/lib/vscode/extensions/notebook-renderers \
        /usr/lib/code-server/lib/vscode/extensions/ms-vscode.js-debug \
        /usr/lib/code-server/lib/vscode/extensions/ms-vscode.js-debug-companion \
        /usr/lib/code-server/lib/vscode/extensions/ms-vscode.vscode-js-profile-table \
        /usr/lib/code-server/lib/vscode/node_modules/@github/copilot*

# ttyd: alternate plain-terminal workspace. Statically linked release
# binary -- no libc dependency, works the same regardless of base image.
ARG TTYD_VERSION=1.7.7
RUN set -eux; \
    case "$(dpkg --print-architecture)" in \
    amd64) ttyd_arch="x86_64"; ttyd_sha256="8a217c968aba172e0dbf3f34447218dc015bc4d5e59bf51db2f2cd12b7be4f55" ;; \
    arm64) ttyd_arch="aarch64"; ttyd_sha256="b38acadd89d1d396a0f5649aa52c539edbad07f4bc7348b27b4f4b7219dd4165" ;; \
    *) echo "Unsupported architecture for ttyd: $(dpkg --print-architecture)" >&2; exit 1 ;; \
    esac; \
    wget -O /usr/local/bin/ttyd "https://github.com/tsl0922/ttyd/releases/download/${TTYD_VERSION}/ttyd.${ttyd_arch}"; \
    echo "${ttyd_sha256}  /usr/local/bin/ttyd" | sha256sum -c -; \
    chmod +x /usr/local/bin/ttyd

ARG ZOXIDE_VERSION=0.10.0
RUN set -eux; \
    case "$(dpkg --print-architecture)" in \
    amd64) zox_arch="x86_64"; zox_sha256="2d93385b99f3e82cf2701609a1bffcad863fbeb75aa3fe7eb6be4d29be68b1ae" ;; \
    arm64) zox_arch="aarch64"; zox_sha256="f1f16c5d6298d63dee467eedea1cdcd8490e43e493bea43acd416dc9033ef641" ;; \
    *) echo "Unsupported architecture for zoxide: $(dpkg --print-architecture)" >&2; exit 1 ;; \
    esac; \
    wget -O /tmp/zoxide.tar.gz "https://github.com/ajeetdsouza/zoxide/releases/download/v${ZOXIDE_VERSION}/zoxide-${ZOXIDE_VERSION}-${zox_arch}-unknown-linux-musl.tar.gz"; \
    echo "${zox_sha256}  /tmp/zoxide.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/zoxide.tar.gz -C /usr/local/bin zoxide; \
    rm /tmp/zoxide.tar.gz

ARG GLOW_VERSION=3.0.0
RUN set -eux; \
    case "$(dpkg --print-architecture)" in \
    amd64) glow_arch="amd64"; glow_sha256="d5df58fe71df9ff734ae3d757ae9c27db79c3e889b16146b179bfa3b18b41d4d" ;; \
    arm64) glow_arch="arm64"; glow_sha256="9d8c8f5b6caf4ff3a7e1b7365a002e47a23389912435d6afaa15c4ec6bc4181d" ;; \
    *) echo "Unsupported architecture for glow: $(dpkg --print-architecture)" >&2; exit 1 ;; \
    esac; \
    wget -O /tmp/glow.deb "https://github.com/charmbracelet/glow/releases/download/v${GLOW_VERSION}/glow_${GLOW_VERSION}_${glow_arch}.deb"; \
    echo "${glow_sha256}  /tmp/glow.deb" | sha256sum -c -; \
    apt-get update && apt-get install -y --no-install-recommends /tmp/glow.deb; \
    rm -rf /tmp/glow.deb /var/lib/apt/lists/*

# Curated extension set, pinned + sha256-verified exactly like
# ttyd/zoxide/glow above -- fetched via wget at build time, not installed
# live via `code-server --install-extension <id>` (redundant with the wget
# calls below, and Open VSX access on a network with TLS inspection needs
# the same corp-cert handling either way; see engine/README.md's
# Troubleshooting section) and not committed to this repo as binaries
# (would bloat git history for no benefit, and only grow with every
# future update). Installed into one shared, read-only
# directory every spawned code-server instance points at (see
# workspace-control.py) -- students get exactly this set and cannot
# install anything else: no runtime Marketplace access is even possible,
# since this container has no network route out at all once the stack is
# up (see docker-compose.yml -- web-terminal sits only on the
# internal-only git_lab network). Verified separately (not guessed):
# code-server starts cleanly as a non-root user against a root-owned,
# read-only --extensions-dir, with no permission errors -- it only ever
# reads from it.
#
# Both below were checked on open-vsx.org before pinning: each is
# published by the extension's real/verified namespace owner (not a
# re-upload by an unrelated account -- Open VSX flags those explicitly).
# ms-python.python's IntelliSense depends on Pylance, which is
# proprietary and unavailable on Open VSX/code-server, so it runs with
# reduced language features -- still worth having for syntax highlighting
# and basic support against scripts/dnsctl.py in the dns-as-code lab
# (entrypoint.sh's shipped settings.json also turns its Jedi language server
# off -- ~75 MB per student for completion nobody needs here).
#
# Deliberately NOT installed here, to keep this set matched to what the
# workshops actually use rather than a generic "nice to have" kit: gitlens
# (git-fundamentals teaches `git blame`/`log`/`show` on the CLI, not via an
# extension), golang.go (no workshop has a .go file, and there's no Go
# toolchain in this image either -- code-server's built-in `go` extension
# already gives the same syntax-highlighting-only experience for free),
# hashicorp.terraform (no workshop in the *base* image edits .tf files;
# tofu-basics, the one workshop that does, installs the OpenTofu extension in its
# own terminal image -- see workshops/tofu-basics/compose/terminal/Dockerfile), and markdown-all-in-one /
# markdown-preview-enhanced (no lab content uses tables/TOCs/mermaid/math
# enough to need more than code-server's built-in markdown preview).
#
# To add/update one: find its exact version + download URL on
# open-vsx.org (a Universal-platform extension uses
# .../<ns>/<name>/<version>/file/<ns>.<name>-<version>.vsix; a
# per-platform one like hashicorp.terraform adds a target segment, e.g.
# .../linux-x64/...), download it once to compute a real sha256, then add
# a fetch_ext line below.
#
# --mount=type=secret is build-time only: the file exists just for this
# RUN's shell and is never written into any image layer, so it's fine to
# pass a corporate TLS-inspection CA cert through here without it ending
# up in the shipped image. Optional -- if no secret named corp_ca_cert is
# passed at build time (see run.sh's CORP_CA_BUNDLE), the mount target
# simply doesn't exist and wget falls through to its normal system trust
# store, same as every other wget call in this file.
RUN --mount=type=secret,id=corp_ca_cert,target=/tmp/corp_ca.pem set -eux; \
    wget_ca=""; \
    if [ -s /tmp/corp_ca.pem ]; then wget_ca="--ca-certificate=/tmp/corp_ca.pem"; fi; \
    mkdir -p /opt/code-server-extensions /tmp/vsix; \
    fetch_ext() { \
        wget $wget_ca -O "/tmp/vsix/$1.vsix" "$2"; \
        echo "$3  /tmp/vsix/$1.vsix" | sha256sum -c -; \
        code-server --extensions-dir /opt/code-server-extensions --install-extension "/tmp/vsix/$1.vsix" --force; \
    }; \
    fetch_ext redhat.vscode-yaml \
        "https://open-vsx.org/api/redhat/vscode-yaml/1.25.2026090408/file/redhat.vscode-yaml-1.25.2026090408.vsix" \
        6b745b9b50673d1f2af6752e85ef73c8200983d174300e12a0b2bd83447effce; \
    fetch_ext GitHub.github-vscode-theme \
        "https://open-vsx.org/api/GitHub/github-vscode-theme/6.3.5/file/GitHub.github-vscode-theme-6.3.5.vsix" \
        a85236a58ad490b1600ec5a0fd0cea7eec56fb9d33660a1ac82c6da639ad3af4; \
    fetch_ext ms-python.python \
        "https://open-vsx.org/api/ms-python/python/2026.4.0/file/ms-python.python-2026.4.0.vsix" \
        232aeafb01f069824fdd92d3e628c1c442bbcfa1d3cc945ff97076340bb2b4a6; \
    rm -rf /tmp/vsix; \
    # ms-python.python's extensionPack pulls in ms-python.debugpy (~21 MB) as
    # a soft, optional companion (not an extensionDependency), and no
    # workshop debugs anything. --uninstall-extension keeps extensions.json
    # consistent but only marks the directory obsolete on disk, so it's
    # removed explicitly too.
    code-server --extensions-dir /opt/code-server-extensions --uninstall-extension ms-python.debugpy; \
    rm -rf /opt/code-server-extensions/ms-python.debugpy-* /opt/code-server-extensions/.obsolete; \
    chown -R root:root /opt/code-server-extensions; \
    chmod -R a+rX /opt/code-server-extensions

COPY entrypoint.sh /usr/local/bin/web-terminal-entrypoint
COPY workspace-control.py /usr/local/bin/workspace-control.py
COPY healthcheck.sh /usr/local/bin/web-terminal-healthcheck
RUN chmod +x /usr/local/bin/web-terminal-entrypoint /usr/local/bin/web-terminal-healthcheck

# Authored shell config for the facilitator/student accounts. Kept as real,
# editable files here (not inline heredocs in entrypoint.sh) so shell
# customisation (aliases, tool init, etc.) is a one-file edit + rebuild.
# entrypoint.sh symlinks each account's ~/.zshrc to these on every
# container start, so edits always take effect on next restart, and
# students can't overwrite this root-owned copy from their own shell.
COPY zshrc.facilitator zshrc.student tmux-terminal.sh /opt/dojo-shell/
RUN chmod 644 /opt/dojo-shell/zshrc.facilitator /opt/dojo-shell/zshrc.student \
    && chmod 755 /opt/dojo-shell/tmux-terminal.sh

# Demo/test bots (--test, see run.sh and engine/README.md's "Demo bots"
# section) -- same "authored file, symlinked/copied by entrypoint.sh at
# container start" pattern as the zshrc files above.
COPY bot-runner.sh bot-supervisor.sh bot-askpass.sh /opt/dojo-shell/
RUN chmod 755 /opt/dojo-shell/bot-runner.sh /opt/dojo-shell/bot-supervisor.sh /opt/dojo-shell/bot-askpass.sh

# System-wide tmux config (mouse mode, copy-mode keys, watch-tile sizing --
# see the file's own comments) -- /etc/tmux.conf is read by every account's
# tmux server on this container, not just root's.
COPY tmux.conf /etc/tmux.conf
RUN chmod 644 /etc/tmux.conf

# No USER here, deliberately: entrypoint.sh runs `useradd`/`chpasswd` for a
# variable set of student + facilitator accounts every time the container
# starts (STUDENT_COUNT can change per workshop), then execs
# workspace-control.py for the container's whole life, which itself needs
# to keep running as root to `su` into any account's code-server/ttyd
# process on demand. There's no "setup, then drop privilege" point; root is
# needed continuously, not just at startup.

EXPOSE 7682
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD web-terminal-healthcheck
ENTRYPOINT ["/usr/local/bin/web-terminal-entrypoint"]
