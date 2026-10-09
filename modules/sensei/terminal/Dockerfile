# sensei module's link in the terminal build chain: the `sensei` command (see sensei.py).
# No ENTRYPOINT here; the chain's entrypoint is inherited unchanged.
ARG BASE=gitopsdojo/web-terminal:base
FROM ${BASE}

COPY sensei.py /usr/local/bin/sensei
RUN chmod 0755 /usr/local/bin/sensei
# Facilitator replies appear under the student's prompt (at most every 3 s; never blocks it).
COPY dojo-sensei.zsh /etc/zsh/dojo-sensei.zsh
RUN set -eux; \
    chmod 0644 /etc/zsh/dojo-sensei.zsh; \
    printf '%s\n' \
      '' \
      '# sensei module: announce the facilitator'"'"'s replies' \
      '[ -r /etc/zsh/dojo-sensei.zsh ] && . /etc/zsh/dojo-sensei.zsh' >> /etc/zsh/zshrc

# Popup inside VS Code: a plain-JS extension (vscode/), packed as a .vsix here (a zip) and installed the same way
# the achievements module installs its own. Guarded by `command -v code-server`: the Zellij flavor has no
# code-server (its popup is the `sensei watch` floating pane, started by dojo-sensei.zsh).
COPY vscode/ /tmp/dojo-sensei-vscode/
RUN set -eux; \
    if command -v code-server >/dev/null 2>&1; then \
      python3 -B -c 'import zipfile; z = zipfile.ZipFile("/tmp/dojo-sensei.vsix", "w", zipfile.ZIP_DEFLATED); \
[z.write("/tmp/dojo-sensei-vscode/" + f, "extension/" + f) for f in ("package.json", "extension.js")]; \
z.writestr("[Content_Types].xml", "<?xml version=\"1.0\" encoding=\"utf-8\"?><Types xmlns=\"http://schemas.openxmlformats.org/package/2006/Content-Types\"><Default Extension=\".json\" ContentType=\"application/json\"/><Default Extension=\".js\" ContentType=\"application/javascript\"/><Default Extension=\".vsixmanifest\" ContentType=\"text/xml\"/></Types>"); \
z.writestr("extension.vsixmanifest", "<?xml version=\"1.0\" encoding=\"utf-8\"?><PackageManifest Version=\"2.0.0\" xmlns=\"http://schemas.microsoft.com/developer/vsx-schema/2011\"><Metadata><Identity Language=\"en-US\" Id=\"dojo-sensei\" Version=\"1.0.0\" Publisher=\"gitopsdojo\"/><DisplayName>Dojo Sensei</DisplayName><Description xml:space=\"preserve\">Facilitator replies</Description></Metadata><Installation><InstallationTarget Id=\"Microsoft.VisualStudio.Code\"/></Installation><Assets><Asset Type=\"Microsoft.VisualStudio.Code.Manifest\" Path=\"extension/package.json\" Addressable=\"true\"/></Assets></PackageManifest>"); z.close()'; \
      code-server --extensions-dir /opt/code-server-extensions --install-extension /tmp/dojo-sensei.vsix --force; \
      rm -f /tmp/dojo-sensei.vsix; \
      chown -R root:root /opt/code-server-extensions; \
      chmod -R a+rX /opt/code-server-extensions; \
    fi; \
    rm -rf /tmp/dojo-sensei-vscode

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD web-terminal-healthcheck
