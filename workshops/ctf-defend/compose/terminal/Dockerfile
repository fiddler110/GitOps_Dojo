# Extra terminal tools for ctf-defend. ./dojo builds it on top of the base
# image and any module's tools (BASE is set to the image below this one in the
# chain). Students have no internet: pin each tool's version and check its
# sha256 for every architecture. Don't set ENTRYPOINT. Start-up work goes in
# /etc/dojo/start.d/90-<name>.sh hooks (run as root, after accounts exist).
ARG BASE=topiary/web-terminal:base
FROM ${BASE}

# No extra tools: target 14's exploit/dump.py and sast/scan.py are stdlib
# python3, already on the base image. Just the provisioning hook below (gives
# each student their own customer-portal repo and its Actions secrets).
COPY start.d/90-ctf-defend.sh /etc/dojo/start.d/90-ctf-defend.sh
RUN chmod 0755 /etc/dojo/start.d/90-ctf-defend.sh

# Two programs want the name `dojo-check`: the achievements module's (score, hints, --echo
# prompt hook) and ctf-range's target checker (installed here as dojo-check-targets). Keep
# both: no argument or a target name goes to the checker, anything else to achievements.
RUN if [ -x /usr/local/bin/dojo-check-targets ] && [ -f /usr/local/bin/dojo-check ] && ! grep -q dojo-check-targets /usr/local/bin/dojo-check; then \
      mv /usr/local/bin/dojo-check /usr/local/bin/dojo-check-achievements; \
      printf '%s\n' '#!/bin/sh' \
        'case "$1" in' \
        '  ""|customer-portal|policy-bypass|leaky-config) exec /usr/local/bin/dojo-check-targets "$@" ;;' \
        '  *) exec /usr/local/bin/dojo-check-achievements "$@" ;;' \
        'esac' > /usr/local/bin/dojo-check; \
      chmod 0755 /usr/local/bin/dojo-check; \
    fi
