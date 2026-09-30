# achievements module's link in the terminal build chain (engine/run.sh sets BASE to the image
# below this one). Adds `dojo-check` and the prompt hook (dojo-achievements.zsh) that sends each
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
    chmod 0644 /etc/zsh/dojo-achievements.zsh /etc/dojo/bot.d/50-achievements.sh; \
    printf '%s\n' \
      '' \
      '# achievements module: shell events and the unlock echo (never blocks the prompt)' \
      '[ -r /etc/zsh/dojo-achievements.zsh ] && . /etc/zsh/dojo-achievements.zsh' >> /etc/zsh/zshrc

# ENTRYPOINT and HEALTHCHECK are inherited from the base image; the HEALTHCHECK is restated so a
# static scan of this file alone doesn't flag it missing.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD web-terminal-healthcheck
