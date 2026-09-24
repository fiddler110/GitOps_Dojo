# P0 spike T0.8 (PLAN.md §6.2 A): one unprivileged container, one Linux user
# per runner, each runner in its own user + PID namespace. Throwaway.
FROM data.forgejo.org/forgejo/runner:13
USER root
# util-linux: unshare with --map-current-user; shadow: useradd/userdel.
RUN apk add --no-cache util-linux shadow bash
COPY supervise.sh /usr/local/bin/supervise
ENTRYPOINT ["/bin/sh", "/usr/local/bin/supervise"]
