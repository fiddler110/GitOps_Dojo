# Extra terminal tools for {{name}}. ./dojo builds it on top of the base
# image and any module's tools (BASE is set to the image below this one in the
# chain). Students have no internet: pin each tool's version and check its
# sha256 for every architecture. Don't set ENTRYPOINT. Start-up work goes in
# /etc/dojo/start.d/90-<name>.sh hooks (run as root, after accounts exist).
ARG BASE=gitopsdojo/web-terminal:base
FROM ${BASE}

# TODO: install tools, e.g.
# ARG TOOL_VERSION=1.2.3
# ARG TARGETARCH
# RUN case "${TARGETARCH}" in \
#       amd64) sha=<sha256 for amd64> ;; \
#       arm64) sha=<sha256 for arm64> ;; \
#       *) echo "unsupported arch ${TARGETARCH}" >&2; exit 1 ;; \
#     esac \
#  && curl -fsSL -o /tmp/tool.tgz "https://example.com/tool-${TOOL_VERSION}-linux-${TARGETARCH}.tgz" \
#  && echo "${sha}  /tmp/tool.tgz" | sha256sum -c - \
#  && tar -xzf /tmp/tool.tgz -C /usr/local/bin tool \
#  && rm /tmp/tool.tgz
