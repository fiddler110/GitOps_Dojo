# The shared ACME CA. Built on Smallstep's official image, but with our
# own entrypoint instead of theirs: the upstream image's DOCKER_STEPCA_INIT_*
# env vars can create an ACME provisioner (DOCKER_STEPCA_INIT_ACME=true) but
# can't shorten its certificate lifetime, and a short lifetime is the whole
# point here — it's what makes automated renewal (Lab 4) observable inside
# a lab session instead of weeks later. So entrypoint.sh calls `step ca
# init` directly and patches the ACME provisioner's claims immediately
# after, before step-ca ever starts serving.
#
# Stays root (no final USER step, unlike upstream) because entrypoint.sh
# needs root once, at startup, to point /etc/resolv.conf at the workshop's
# own DNS server — see the comment there for why. su-exec drops to the
# unprivileged `step` user for everything else, including the CA process
# itself, so the running server has the same privilege as upstream's image.
FROM docker.io/smallstep/step-ca:latest

USER root
RUN apk add --no-cache jq su-exec
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

# The upstream image's HEALTHCHECK runs `step ca health` against the CA's configured name (`step-ca`), but entrypoint.sh
# points this container's resolver at PowerDNS, which knows only the lab zone -- so that lookup fails and the container
# reports unhealthy while serving fine. Ask localhost instead (one of the CA's configured hostnames, so the cert matches).
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD step ca health --ca-url https://localhost:9000 --root "${STEPPATH:-/home/step}/certs/root_ca.crt" 2>/dev/null | grep -q '^ok'
