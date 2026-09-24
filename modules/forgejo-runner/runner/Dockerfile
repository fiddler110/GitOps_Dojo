# Default image for the forgejo-runner module: the upstream runner plus the
# few tools almost any workflow step uses. Jobs run in this container itself
# (the `host` label), so a workshop that needs more tools builds its own
# image instead, by setting forgejo-runner's build.context in its overlay
# (see ../compose.yml and workshops/dns-as-code/compose/runner/Dockerfile).
FROM data.forgejo.org/forgejo/runner:13

USER root
RUN apk add --no-cache curl jq
USER 1000:1000
WORKDIR /data
