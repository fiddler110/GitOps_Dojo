# achievements module's link in the terminal build chain (dojo sets BASE to the image
# below this one). Adds `dojo-check` (and `dojo-challenge`, a link to the same file, so the
# client hash still matches) and the prompt hook (dojo-achievements.zsh) that sends each
# command to the service and echoes new unlocks in colour.
# The client is copied unchanged: the service hashes the same file to spot an edited copy.
# The entrypoint is inherited unchanged.
ARG BASE=gitopsdojo/web-terminal:base
FROM ${BASE}

COPY dojo-check.py /usr/local/bin/dojo-check
COPY dojo-achievements.zsh /etc/zsh/dojo-achievements.zsh
# The --test bots' version of the hook (bot-runner.sh sources /etc/dojo/bot.d/*.sh).
COPY dojo-achievements-bot.sh /etc/dojo/bot.d/50-achievements.sh
RUN set -eux; \
    chmod 0755 /usr/local/bin/dojo-check; \
    ln -sf dojo-check /usr/local/bin/dojo-challenge; \
    chmod 0644 /etc/zsh/dojo-achievements.zsh /etc/dojo/bot.d/50-achievements.sh; \
    printf '%s\n' \
      '' \
      '# achievements module: shell events and the unlock echo (never blocks the prompt)' \
      '[ -r /etc/zsh/dojo-achievements.zsh ] && . /etc/zsh/dojo-achievements.zsh' >> /etc/zsh/zshrc

# Toasts inside VS Code: a tiny plain-JS extension (vscode/), packed as a .vsix here (a zip) and
# installed the same way the base image installs its own, into the shared read-only directory.
# Guarded by `command -v code-server`: the Zellij flavor's leaf (engine/zellij-terminal/) has no
# code-server at all (it builds FROM web-terminal:core, a sibling of the vscode leaf, not on top
# of it — see engine/README.md's "Terminal flavor" section), so there is nothing to install into.
COPY vscode/ /tmp/dojo-vscode/
RUN set -eux; \
    if command -v code-server >/dev/null 2>&1; then \
      python3 -B -c 'import zipfile; z = zipfile.ZipFile("/tmp/dojo-achievements.vsix", "w", zipfile.ZIP_DEFLATED); \
[z.write("/tmp/dojo-vscode/" + f, "extension/" + f) for f in ("package.json", "extension.js")]; \
z.writestr("[Content_Types].xml", "<?xml version=\"1.0\" encoding=\"utf-8\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/Content-Types\"><Default Extension=\".json\" ContentType=\"application/json\"/><Default Extension=\".js\" ContentType=\"application/javascript\"/><Default Extension=\".vsixmanifest\" ContentType=\"text/xml\"/></Types>"); \
z.writestr("extension.vsixmanifest", "<?xml version=\"1.0\" encoding=\"utf-8\"?><PackageManifest Version=\"2.0.0\" xmlns=\"http://schemas.microsoft.com/developer/vsx-schema/2011\"><Metadata><Identity Language=\"en-US\" Id=\"dojo-achievements\" Version=\"1.0.0\" Publisher=\"gitopsdojo\"/><DisplayName>Dojo achievements</DisplayName><Description xml:space=\"preserve\">Achievement toasts</Description></Metadata><Installation><InstallationTarget Id=\"Microsoft.VisualStudio.Code\"/></Installation><Assets><Asset Type=\"Microsoft.VisualStudio.Code.Manifest\" Path=\"extension/package.json\" Addressable=\"true\"/></Assets></PackageManifest>"); z.close()'; \
      code-server --extensions-dir /opt/code-server-extensions --install-extension /tmp/dojo-achievements.vsix --force; \
      rm -f /tmp/dojo-achievements.vsix; \
      chown -R root:root /opt/code-server-extensions; \
      chmod -R a+rX /opt/code-server-extensions; \
    fi; \
    rm -rf /tmp/dojo-vscode

# ENTRYPOINT and HEALTHCHECK are inherited from the base image; the HEALTHCHECK is restated so a
# static scan of this file alone doesn't flag it missing.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD web-terminal-healthcheck
