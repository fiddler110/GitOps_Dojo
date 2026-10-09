# The flavor-agnostic core of the terminal chain: everything both terminal
# flavors need (shell, tmux, ttyd, provisioning, the entrypoint), nothing
# either flavor-specific leaf adds on top. `web-terminal-vscode/` (code-server)
# and `zellij-terminal/` both build FROM this image's `:core` tag, as
# siblings, not one on top of the other -- so a code-server-only change
# never invalidates the Zellij leaf's cache and vice versa, and the Zellij
# flavor never pays code-server's disk/build cost (see engine/README.md's
# "Terminal flavor" section).
#
# Debian, not Alpine, deliberately: code-server's official releases (in the
# vscode leaf) require glibc (Alpine's musl libc isn't supported upstream --
# the musl-compatible fork is explicitly work-in-progress), so this stays the
# one base in the stack that isn't Alpine-based, to keep both leaves on the
# same libc. Everything not available via apt (ttyd, zoxide, glow) is pinned
# to a specific version and sha256-verified below, same as this file always
# did on Alpine.
FROM docker.io/library/debian:bookworm-slim@sha256:3783cc01769c7b2b1b83a5c5ad96c815348e28ed7da68e2e3687004faa906251

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

COPY entrypoint.sh /usr/local/bin/web-terminal-entrypoint
COPY workspace-control.py /usr/local/bin/workspace-control.py
COPY healthcheck.sh /usr/local/bin/web-terminal-healthcheck
RUN chmod +x /usr/local/bin/web-terminal-entrypoint /usr/local/bin/web-terminal-healthcheck
# One account's setup, run by the entrypoint and by a student reset.
COPY provision-account.sh forgejo-token.py dojo_secret.py /usr/local/lib/dojo/
# Root only: dojo_secret.py prints any student's Forgejo password.
RUN chmod 700 /usr/local/lib/dojo \
    && chmod 700 /usr/local/lib/dojo/provision-account.sh /usr/local/lib/dojo/forgejo-token.py \
    && chmod 600 /usr/local/lib/dojo/dojo_secret.py

# Authored shell config shared by the facilitator/student accounts. Kept as
# a real, editable file here (not inline heredocs in entrypoint.sh) so shell
# customisation (aliases, tool init, etc.) is a one-file edit + rebuild.
# entrypoint.sh symlinks each account's ~/.zshrc to it on every
# container start, so edits always take effect on next restart, and
# students can't overwrite this root-owned copy from their own shell.
COPY zshrc tmux-terminal.sh /opt/dojo-shell/
RUN chmod 644 /opt/dojo-shell/zshrc \
    && chmod 755 /opt/dojo-shell/tmux-terminal.sh

# Demo/test bots (--test, see dojo and engine/README.md's "Demo bots"
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
