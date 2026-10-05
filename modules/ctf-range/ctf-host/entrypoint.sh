#!/bin/sh
# Starts the inner dockerd on the shared unix socket, locks it down, loads the
# base image archive(s) baked into this image, then imports the
# customer-portal target image from the rootfs also baked in. Everything here
# is offline — nothing is pulled at lab time. Closely follows dojo-cloud's
# cloud-host/entrypoint.sh; see it for the why behind the signal handling and
# the DOCKER-USER rule.
set -eu

mkdir -p /run/ctf

# A restarted container keeps its filesystem; start from a clean slate so
# dockerd never waits on a containerd from a run that is gone.
rm -rf /var/run/docker /var/run/docker.pid /run/ctf/docker.sock

#  --icc=false         inner containers (the slots) cannot talk to each other (S14).
#  --insecure-registry  the in-lab registry (spike S6) has no TLS — it is
#                        internal-only, so plaintext within ctf_ops is the
#                        accepted trade-off (CTF-D24's offline posture is
#                        about reaching outward, not about TLS inward).
set -- --icc=false --log-level=warn
[ -n "${CTF_REGISTRY:-}" ] && set -- "$@" --insecure-registry "$CTF_REGISTRY"
dockerd-entrypoint.sh "$@" &
dockerd_pid=$!

# PID 1 ignores SIGTERM without a handler; pass it on so `stop` is clean.
stopping=0
trap 'stopping=1; kill -TERM "$dockerd_pid" 2>/dev/null || true' TERM INT

# Wait for the daemon.
i=0
until docker info >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -gt 120 ] || ! kill -0 "$dockerd_pid" 2>/dev/null; then
    echo "ctf-host: dockerd did not come up" >&2
    exit 1
  fi
  sleep 0.5
done

# --icc=false only stops slot-to-slot traffic. A slot's NEW outbound connection
# still leaves through this container's address onto ctf_ops, where the
# controller lives. Slots never need to start a connection (published ports are
# inbound DNAT, replies are not NEW), so drop NEW outbound. Fail closed.
iptables -C DOCKER-USER -i docker0 ! -o docker0 -m conntrack --ctstate NEW -j DROP 2>/dev/null ||
  iptables -I DOCKER-USER -i docker0 ! -o docker0 -m conntrack --ctstate NEW -j DROP

# The socket is shared with ctf-controller only: 0660, group CTF_GID (fixed so
# compose can group_add the same gid to the controller). No other container
# mounts the volume; dropping "other" means a stray process without the group
# cannot speak to dockerd.
CTF_GID="${CTF_GID:-1901}"
getent group "$CTF_GID" >/dev/null 2>&1 || addgroup -g "$CTF_GID" ctf
chgrp "$CTF_GID" /run/ctf/docker.sock
chmod 0660 /run/ctf/docker.sock

# Load the base image archives baked in at build time (offline, nothing
# pulled at lab time — see ctf-host/Dockerfile's base-image-fetch stage).
# ctf-builder's rebuild of the patched target has its own `FROM
# python:3.12-slim@sha256:...` and runs with pull=0, so that digest has to
# already be in the inner dockerd's image store before ctf-builder ever runs.
# `docker image load` is idempotent on its own (re-loading an already-present
# image is a no-op), so this is safe to run on every start.
for archive in /opt/base-images/*.tar; do
  [ -e "$archive" ] || continue
  docker image load -i "$archive" >/dev/null
  echo "ctf-host: loaded base image archive $(basename "$archive")"
done

# Import the target image from the baked rootfs (offline). The --change lines
# reproduce targets/customer-portal/Dockerfile's runtime config, since
# `docker import` keeps only the filesystem. This is the BASE image a slot runs
# until a student's merged fix is rebuilt and pushed to the in-lab registry
# (then the controller pulls that tag instead — spike S6).
import_target() {
  docker image inspect ctf-customer-portal:base >/dev/null 2>&1 && return 0
  tar -C /opt/portal-rootfs -c . | docker import \
    --change 'ENTRYPOINT ["/app/entrypoint.sh"]' \
    --change 'ENV CTF_DB_PATH=/data/portal.db PORT=5000 PYTHONUNBUFFERED=1 PATH=/usr/local/bin:/usr/bin:/bin' \
    --change 'EXPOSE 5000' \
    --change 'USER portal' \
    --change 'WORKDIR /app' \
    - ctf-customer-portal:base >/dev/null
  echo "ctf-host: imported ctf-customer-portal:base"
}
import_target

# Import the vendored-Flask base for ctf-builder's offline rebuild (offline).
# See ctf-host/Dockerfile's portal-deps stage and docs/CTF-SPIKES.md S6
# "Scoped" (2026-10-05): targets/customer-portal/Dockerfile now FROMs this tag
# instead of installing Flask itself, so it has to already be in the inner
# dockerd's image store before ctf-builder's rebuild runs.
import_portal_deps_base() {
  docker image inspect gitopsdojo/ctf-customer-portal-base:pinned >/dev/null 2>&1 && return 0
  tar -C /opt/portal-deps-rootfs -c . | docker import - gitopsdojo/ctf-customer-portal-base:pinned >/dev/null
  echo "ctf-host: imported gitopsdojo/ctf-customer-portal-base:pinned"
}
import_portal_deps_base

echo "ctf-host: ready"
# A trapped signal makes `wait` return early: keep waiting until dockerd is
# really gone, then pass its status on.
status=0
wait "$dockerd_pid" || status=$?
while kill -0 "$dockerd_pid" 2>/dev/null; do
  wait "$dockerd_pid" || status=$?
done
[ "$stopping" = 1 ] && exit 0
exit "$status"
