# Extends the shared web-terminal base image with one script: `lab-prep`.
# Everything else (account provisioning, code-server/ttyd, shell helpers) is
# inherited unchanged from the base image's entrypoint.
# engine/run.sh sets BASE to the image below this one in the chain (docs/archive/MODULES-PLAN.md §4.2).
ARG BASE=gitopsdojo/web-terminal:base
FROM ${BASE}

# `lab-prep <lab>` brings a student's workspace to where that lab starts, so
# they can resume mid-workshop (see the script's header for what each lab needs).
COPY lab-prep /usr/local/bin/lab-prep
RUN chmod 0755 /usr/local/bin/lab-prep

# Base image's HEALTHCHECK is inherited too; restated here so a static scan
# of this file alone (which doesn't resolve FROM) doesn't flag it missing.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD web-terminal-healthcheck
