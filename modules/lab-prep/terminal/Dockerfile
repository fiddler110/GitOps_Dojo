# lab-prep module's link in the terminal build chain (dojo sets BASE to the image
# below this one). Installs the shared skeleton the workshops' own `lab-prep`
# scripts source; each workshop still ships its own steps in compose/terminal/.
# ENTRYPOINT is inherited unchanged.
ARG BASE=topiary/web-terminal:base
FROM ${BASE}

COPY lab-prep-lib.sh /usr/local/lib/dojo/lab-prep-lib.sh
RUN chmod 0755 /usr/local/lib/dojo && chmod 0644 /usr/local/lib/dojo/lab-prep-lib.sh
# `dojo prep N`: a link to the workshop's own lab-prep (dangling here, filled in by the workshop's
# terminal image; dojo skips a command whose target isn't there).
RUN mkdir -p /usr/local/share/dojo/cmd.d && ln -sf /usr/local/bin/lab-prep /usr/local/share/dojo/cmd.d/prep

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD web-terminal-healthcheck
