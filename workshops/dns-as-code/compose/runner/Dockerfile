# The Forgejo Actions runner for this workshop's dns-as-code CI (DNS
# Preview / DNS Apply workflows). Runs workflow steps directly inside this
# container (a `host` label, not the `docker://` executor - see
# modules/forgejo-runner/, whose service ../docker-compose.override.yml points here) so no docker.sock needs to be mounted
# into it: this container's own filesystem/tools ARE the job environment,
# same trust tier as the terminal/dns-server containers already in this
# stack. That's why dnscontrol has to be preinstalled here, same as
# ../terminal/Dockerfile does for the student terminal.
FROM data.forgejo.org/forgejo/runner:13.2.0@sha256:ca3d5eea46004789a175d1369eec6829d3ea9bfbe2011a06625b4bdaa55f7552

# The upstream image runs as uid 1000 already (see its own Dockerfile) -
# switch back to root only for these installs, then drop back down.
USER root
RUN apk add --no-cache curl jq bind-tools

ARG DNSCONTROL_VERSION=5.0.4
ARG TARGETARCH=amd64
RUN set -eux; \
    case "${TARGETARCH}" in \
    amd64) dc_arch="amd64"; dc_sha256="f1067b2d6e2242206b7140dd01ba34424fe577b0f5edd75b1fcd92caf84af35a" ;; \
    arm64) dc_arch="arm64"; dc_sha256="eeb81fcc9ec66908593a5fbb61e5e45aa3f15237821702c008000c1245c08d28" ;; \
    *) echo "Unsupported architecture for dnscontrol: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    curl -fsSL -o /tmp/dnscontrol.tar.gz \
      "https://github.com/DNSControl/dnscontrol/releases/download/v${DNSCONTROL_VERSION}/dnscontrol_${DNSCONTROL_VERSION}_linux_${dc_arch}.tar.gz"; \
    echo "${dc_sha256}  /tmp/dnscontrol.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/dnscontrol.tar.gz -C /tmp dnscontrol; \
    install -m 0755 /tmp/dnscontrol /usr/local/bin/dnscontrol; \
    rm -f /tmp/dnscontrol.tar.gz /tmp/dnscontrol

USER 1000:1000
WORKDIR /data

# Base image's ENTRYPOINT (dumb-init) and VOLUME ["/data"] are inherited.
# docker-compose.override.yml supplies the actual `daemon --config ...`
# command.
