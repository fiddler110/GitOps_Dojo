# Zellij terminal flavor: the flavor-agnostic web-terminal:core image plus
# Zellij, micro (editor) and a read-only file listing that follows the
# shell, so a student works in the browser terminal alone, with no VS Code.
# Selected by TERMINAL_FLAVOR=zellij (.env or a workshop.env);
# dojo builds this on top of web-terminal:core -- a sibling of
# web-terminal-vscode/ (code-server), not downstream of it, so this image
# never carries code-server's disk weight at all -- and chains every
# module and workshop terminal/ link on top of it, exactly as it does for
# the web flavor. workspace-control.py does the rest at runtime: it sees
# TERMINAL_FLAVOR and runs Zellij instead of tmux.
ARG BASE=gitopsdojo/web-terminal:core
FROM ${BASE}

RUN apt-get update && apt-get install -y --no-install-recommends file less micro \
    && rm -rf /var/lib/apt/lists/*

# Pinned and sha256-verified like ttyd/zoxide/glow in the base Dockerfile. The
# optional corp_ca_cert secret is the same build-time-only mount (see the base
# Dockerfile's note on it).
ARG ZELLIJ_VERSION=0.45.1
RUN --mount=type=secret,id=corp_ca_cert,target=/tmp/corp_ca.pem set -eux; \
    wget_ca=""; \
    if [ -s /tmp/corp_ca.pem ]; then wget_ca="--ca-certificate=/tmp/corp_ca.pem"; fi; \
    case "$(dpkg --print-architecture)" in \
    amd64) arch="x86_64"; zj_sha256="40bcc2e03f5d5ae8e054e39f676081fe12ab70871506996ba595834c3718eefc" ;; \
    arm64) arch="aarch64"; zj_sha256="05f0802afadd53f8db9514e7cae53c9ae8432fed1b35b8294aa816ee3044a16b" ;; \
    *) echo "Unsupported architecture for zellij: $(dpkg --print-architecture)" >&2; exit 1 ;; \
    esac; \
    wget $wget_ca -O /tmp/zellij.tar.gz "https://github.com/zellij-org/zellij/releases/download/v${ZELLIJ_VERSION}/zellij-${arch}-unknown-linux-musl.tar.gz"; \
    echo "${zj_sha256}  /tmp/zellij.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/zellij.tar.gz -C /usr/local/bin zellij; \
    rm -f /tmp/zellij.tar.gz

# System-wide, like /etc/tmux.conf in the base: Zellij reads /etc/zellij for every
# account, so no per-student provisioning is needed.
COPY config.kdl /etc/zellij/config.kdl
COPY layouts/ /etc/zellij/layouts/
RUN chmod -R a+rX /etc/zellij

# The side pane: a read-only listing of the shell's current directory. The shell
# records its directory in ~/.dojo-cwd (zshrc-zellij) and dojo-sidebar redraws when
# that or the directory's contents change.
COPY dojo-sidebar zshrc-zellij /usr/local/share/dojo-zellij/
RUN install -m 0755 /usr/local/share/dojo-zellij/dojo-sidebar /usr/local/bin/dojo-sidebar \
    && cat /usr/local/share/dojo-zellij/zshrc-zellij >> /opt/dojo-shell/zshrc

# Prompt (starship), pinned and sha256-verified, with its plain-Unicode config, and the
# guides the `guide` command opens. The zshrc block above is appended to the shared
# /opt/dojo-shell/zshrc rather than /etc/zsh/zshrc because that file sets the prompt
# and aliases, and the modern prompt has to be applied after it.
ARG STARSHIP_VERSION=1.26.0
RUN --mount=type=secret,id=corp_ca_cert,target=/tmp/corp_ca.pem set -eux; \
    wget_ca=""; \
    if [ -s /tmp/corp_ca.pem ]; then wget_ca="--ca-certificate=/tmp/corp_ca.pem"; fi; \
    case "$(dpkg --print-architecture)" in \
    amd64) arch="x86_64"; sp_sha256="b7c232b0e8249d8e55a40beb79c5c43a7d370f3f9408bd215deb0170daeaadf3" ;; \
    arm64) arch="aarch64"; sp_sha256="dc30189378d2f2e287384e8a692d3f95ad1df64cf0e8c36aa9201516028aed6b" ;; \
    *) echo "Unsupported architecture for starship: $(dpkg --print-architecture)" >&2; exit 1 ;; \
    esac; \
    wget $wget_ca -O /tmp/starship.tar.gz "https://github.com/starship/starship/releases/download/v${STARSHIP_VERSION}/starship-${arch}-unknown-linux-musl.tar.gz"; \
    echo "${sp_sha256}  /tmp/starship.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/starship.tar.gz -C /usr/local/bin starship; \
    rm -f /tmp/starship.tar.gz
COPY starship.toml /etc/starship.toml
COPY guides/ /usr/share/dojo-guides/
RUN chmod 644 /etc/starship.toml && chmod -R a+rX /usr/share/dojo-guides

# micro as the editor: Ctrl-S / Ctrl-Q work as in any desktop editor. zsh reads /etc/zsh/zshenv for every invocation, including
# the `su - <account> -c ...` commands workspace-control.py runs (su clears the
# environment, so an ENV line here would not reach them).
# ZELLIJ_CONFIG_DIR points Zellij at /etc/zellij explicitly. Without it Zellij sees
# no per-account config and shows its "First Run Setup Wizard" over the layout.
RUN printf 'export EDITOR=micro\nexport VISUAL=micro\nexport ZELLIJ_CONFIG_DIR=/etc/zellij\n' >> /etc/zsh/zshenv

ENV TERMINAL_FLAVOR=zellij

# The base image's HEALTHCHECK is inherited; restated for static scans (see the
# workshops' terminal Dockerfiles).
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD web-terminal-healthcheck
