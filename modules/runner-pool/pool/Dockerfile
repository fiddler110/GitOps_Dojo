# The runner pool (vault-fundamentals PLAN.md §6.2 A): the upstream runner,
# what the supervisor needs to give each runner its own user and namespaces,
# and the tools jobs call. Jobs run in this container (the `host` label), so a
# workflow can only use what is installed here.
#
# JOB_TOOLS names extra tools (e.g. "bao sops") to copy from TOOLS_IMAGE's
# /usr/local/bin; compose.yml sets TOOLS_IMAGE to the terminal image run.sh
# has just built, so jobs run the very binaries the students have, pinned and
# checked once, in the terminal's Dockerfiles. They must be static binaries:
# this image is Alpine (musl), the terminal is not.
ARG TOOLS_IMAGE=gitopsdojo/web-terminal:base
FROM ${TOOLS_IMAGE} AS tools

FROM data.forgejo.org/forgejo/runner:13.2.0@sha256:ca3d5eea46004789a175d1369eec6829d3ea9bfbe2011a06625b4bdaa55f7552

USER root
# util-linux: unshare, prlimit. shadow: useradd/userdel. python3: the
# supervisor. tini: PID 1, so the processes of a killed runner that end up
# re-parented to it are reaped. bash: a workflow's default shell. curl, jq,
# git: what most steps call.
RUN apk add --no-cache util-linux shadow python3 tini bash curl jq git ca-certificates

ARG JOB_TOOLS=""
RUN --mount=type=bind,from=tools,source=/usr/local/bin,target=/tools \
    set -eu; \
    for t in ${JOB_TOOLS}; do \
      install -m 0755 "/tools/${t}" "/usr/local/bin/${t}"; \
      rc=0; "/usr/local/bin/${t}" --help >/dev/null 2>&1 || rc=$?; \
      if [ "$rc" -eq 126 ] || [ "$rc" -eq 127 ]; then \
        echo "JOB_TOOLS: ${t} doesn't run on Alpine (not a static binary?)" >&2; exit 1; \
      fi; \
    done

COPY supervise.py /usr/local/bin/supervise.py
WORKDIR /data
ENTRYPOINT ["/sbin/tini", "--", "python3", "-B", "-u", "/usr/local/bin/supervise.py"]
