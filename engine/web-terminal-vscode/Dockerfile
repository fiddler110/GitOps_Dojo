# syntax=docker/dockerfile:1.7
# The line above enables BuildKit's `RUN --mount=type=secret` used below --
# needed for CORP_CA_BUNDLE (see run.sh), not for anything else in this
# file. Must stay the literal first line.

# The VS Code terminal flavor's own leaf: code-server plus its curated
# extensions, built FROM the flavor-agnostic `web-terminal:core` (see that
# Dockerfile's header) as a sibling of `zellij-terminal/`, not a parent of
# it -- so a code-server-only change here never invalidates the Zellij
# flavor's cache, and the Zellij flavor never pays this leaf's disk/build
# cost at all (engine/README.md's "Terminal flavor" section). Every module
# and workshop terminal/ link then chains onto whichever leaf `run.sh`
# selected for this run (TERMINAL_FLAVOR) -- this split is invisible to
# them; they only ever see an opaque `ARG BASE`.
#
# Debian glibc is required upstream by code-server's official releases
# (Alpine's musl libc isn't supported -- the musl-compatible fork is
# explicitly work-in-progress), which is why `web-terminal:core` itself
# stays Debian-based rather than Alpine, to keep this leaf on the same libc.
ARG BASE=gitopsdojo/web-terminal:core
FROM ${BASE}

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
        /usr/lib/code-server/lib/vscode/extensions/github \
        /usr/lib/code-server/lib/vscode/extensions/typescript-language-features \
        /usr/lib/code-server/lib/vscode/extensions/terminal-suggest \
        /usr/lib/code-server/lib/vscode/extensions/extension-editing \
        /usr/lib/code-server/lib/vscode/extensions/markdown-math \
        /usr/lib/code-server/lib/vscode/node_modules/@github/copilot*

# Curated extension set, pinned + sha256-verified exactly like
# ttyd/zoxide/glow in web-terminal:core -- fetched via wget at build time,
# not installed live via `code-server --install-extension <id>` (redundant
# with the wget calls below, and Open VSX access on a network with TLS
# inspection needs the same corp-cert handling either way; see
# engine/README.md's Troubleshooting section) and not committed to this
# repo as binaries (would bloat git history for no benefit, and only grow
# with every future update). Installed into one shared, read-only
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
#
# Deliberately NOT installed here, to keep this set matched to what the
# workshops actually use rather than a generic "nice to have" kit:
# ms-python.python (the built-in `python` extension already highlights .py
# files; the Microsoft one only added an extension-host activation plus the
# python-envs companion per student, since its IntelliSense needs Pylance,
# which isn't on Open VSX), gitlens
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
    rm -rf /tmp/vsix; \
    chown -R root:root /opt/code-server-extensions; \
    chmod -R a+rX /opt/code-server-extensions

# The base image's HEALTHCHECK/ENTRYPOINT are inherited; restated for
# static scans (see modules' terminal Dockerfiles for the same pattern).
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD web-terminal-healthcheck
