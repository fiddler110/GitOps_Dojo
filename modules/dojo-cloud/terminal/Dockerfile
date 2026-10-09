# dojo-cloud's link in the terminal build chain (dojo sets BASE to
# the image below this one; see docs/archive/MODULES-PLAN.md §4.2).
#
# Dojo Cloud client side: a root-owned credential broker (SO_PEERCRED tells it
# which student is asking, so each gets only their own ARM_* values), the
# `dojo-env` client, and a start.d hook that trusts the cloud's private CA and
# starts the broker. Without a running cloud-api all of this quietly does
# nothing, so the rest of the lab still works.
ARG BASE=gitopsdojo/web-terminal:base
FROM ${BASE}

COPY dojo-broker.py /usr/local/bin/dojo-broker
COPY dojo-env /usr/local/bin/dojo-env
COPY start.d/50-dojo-cloud.sh /etc/dojo/start.d/50-dojo-cloud.sh
RUN set -eux; \
    chmod 0755 /usr/local/bin/dojo-broker /usr/local/bin/dojo-env; \
    printf '\n# dojo-cloud: Dojo Cloud credentials for this user (from the broker)\nif [ -z "${ARM_CLIENT_ID:-}" ] && [ -x /usr/local/bin/dojo-env ]; then eval "$(/usr/local/bin/dojo-env 2>/dev/null)"; fi\n' >> /etc/zsh/zshenv

# ENTRYPOINT and HEALTHCHECK are inherited from the base image; the
# HEALTHCHECK is restated so a static scan of this file alone (which doesn't
# resolve FROM) doesn't flag it missing.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD web-terminal-healthcheck
