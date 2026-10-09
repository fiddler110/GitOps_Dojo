# openbao module's link in the terminal build chain (dojo sets BASE
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

# CLI login with no password (T1.4): a root-owned identity broker signs a
# short-lived JWT for whoever asks (SO_PEERCRED says who), and openbao-login
# trades it for a token in ~/.vault-token on every shell start. The start.d
# hook makes the key and starts the broker.
COPY openbao-broker.py /usr/local/bin/openbao-broker
COPY openbao-login.py /usr/local/bin/openbao-login
COPY start.d/50-openbao.sh /etc/dojo/start.d/50-openbao.sh
# bao-audit: your namespace's audit trail, from the openbao-audit service.
COPY bao-audit.py /usr/local/bin/bao-audit
RUN set -eux; \
    command -v openssl; \
    chmod 0755 /usr/local/bin/openbao-broker /usr/local/bin/openbao-login /usr/local/bin/bao-audit \
      /etc/dojo/start.d/50-openbao.sh; \
    printf '\n# openbao module: sign in to OpenBao through the broker (no-op while the token is good)\nif [ -x /usr/local/bin/openbao-login ]; then /usr/local/bin/openbao-login --quiet; fi\n' >> /etc/zsh/zshenv

# HCL syntax highlighting for .hcl files (policies, server config) in
# code-server: HashiCorp's HCL extension from its verified namespace on Open
# VSX, one universal package, pinned and sha256-verified. Its only code is a
# telemetry reporter that activates whenever the workspace holds a .hcl file
# (and can't reach the internet here), so the build drops it and keeps the
# grammar, language id and bracket config: a declarative extension that
# starts no process. The Python step fails the build if a future version
# moves those fields, instead of shipping with the reporter still on.
# https://open-vsx.org/extension/hashicorp/hcl
#
# Guarded by `command -v code-server`: the Zellij flavor's leaf has no
# code-server at all (a sibling of the vscode leaf, not built on top of it
# — see engine/README.md's "Terminal flavor" section), so there's nothing
# to install the extension into.
ARG HCL_VSCODE_VERSION=0.5.0
ARG HCL_VSCODE_SHA256=09fc9348908c4c8283572bc4ec9f452907d72abc1008e328051f76d0232804e3
RUN set -eux; \
    if command -v code-server >/dev/null 2>&1; then \
      wget -O /tmp/hcl.vsix \
        "https://open-vsx.org/api/hashicorp/hcl/${HCL_VSCODE_VERSION}/file/hashicorp.hcl-${HCL_VSCODE_VERSION}.vsix"; \
      echo "${HCL_VSCODE_SHA256}  /tmp/hcl.vsix" | sha256sum -c -; \
      code-server --extensions-dir /opt/code-server-extensions --install-extension /tmp/hcl.vsix --force; \
      rm -f /tmp/hcl.vsix; \
      ext="/opt/code-server-extensions/hashicorp.hcl-${HCL_VSCODE_VERSION}"; \
      python3 -B -c 'import json, sys; p = sys.argv[1] + "/package.json"; d = json.load(open(p)); \
[d.pop(k) for k in ("main", "browser", "activationEvents")]; \
assert any(".hcl" in l.get("extensions", []) for l in d["contributes"]["languages"]); \
json.dump(d, open(p, "w"), indent=2)' "$ext"; \
      rm -rf "$ext/out"; \
      chown -R root:root /opt/code-server-extensions; \
      chmod -R a+rX /opt/code-server-extensions; \
    fi

# ENTRYPOINT and HEALTHCHECK are inherited from the base image; the
# HEALTHCHECK is restated so a static scan of this file alone (which doesn't
# resolve FROM) doesn't flag it missing.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD web-terminal-healthcheck
