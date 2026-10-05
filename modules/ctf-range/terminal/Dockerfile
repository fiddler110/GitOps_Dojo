# ctf-range module's link in the terminal build chain (engine/run.sh sets
# BASE to the image below this one; see workshops/README.md). Adds
# `dojo-flag` (plan §5) and the per-uid ctf_net firewall hook (CTF-S2/S3).
#
# Deliberately NOT here yet: the offensive tool suite (nmap, sqlmap, ncat,
# ...) and the Lab Info library (plan §9, CTF-P2b/P3) - a separate, larger
# piece of work than the submission plumbing and the isolation wiring this
# layer exists for. A pack that needs those tools adds its own
# `compose/terminal/Dockerfile` link on top of this one meanwhile.
ARG BASE=gitopsdojo/web-terminal:base
FROM ${BASE}

COPY dojo-flag.py /usr/local/bin/dojo-flag
COPY start.d/50-ctf-range.sh /etc/dojo/start.d/50-ctf-range.sh
RUN chmod 0755 /usr/local/bin/dojo-flag /etc/dojo/start.d/50-ctf-range.sh

# dojo-flag talks to ctf-flags directly on workshop_lab, not through the
# gateway (same shape as openbao's BAO_ADDR - see modules/openbao/terminal).
ENV CTF_FLAGS_ADDR=http://ctf-flags:8080

# ENTRYPOINT and HEALTHCHECK are inherited from the base image; the
# HEALTHCHECK is restated so a static scan of this file alone (which doesn't
# resolve FROM) doesn't flag it missing.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD web-terminal-healthcheck
