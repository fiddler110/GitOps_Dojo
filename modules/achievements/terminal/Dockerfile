# achievements module's link in the terminal build chain (engine/run.sh sets BASE to the image
# below this one). Adds `dojo-check` and the prompt hook that echoes new unlocks in colour.
# The client is copied unchanged: the service hashes the same file to spot an edited copy.
# The entrypoint is inherited unchanged.
ARG BASE=gitopsdojo/web-terminal:base
FROM ${BASE}

COPY dojo-check.py /usr/local/bin/dojo-check
RUN set -eux; \
    chmod 0755 /usr/local/bin/dojo-check; \
    printf '%s\n' \
      '' \
      '# achievements module: echo new unlocks under the prompt (at most every 5 s, never blocks)' \
      'if [ -x /usr/local/bin/dojo-check ]; then' \
      '  zmodload zsh/datetime 2>/dev/null' \
      '  typeset -gi _dojo_ach_last=0' \
      '  _dojo_ach_echo() {' \
      '    (( EPOCHSECONDS - _dojo_ach_last < 5 )) && return' \
      '    _dojo_ach_last=$EPOCHSECONDS' \
      '    /usr/local/bin/dojo-check --echo 2>/dev/null' \
      '  }' \
      '  precmd_functions+=(_dojo_ach_echo)' \
      'fi' >> /etc/zsh/zshrc

# ENTRYPOINT and HEALTHCHECK are inherited from the base image; the HEALTHCHECK is restated so a
# static scan of this file alone doesn't flag it missing.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD web-terminal-healthcheck
