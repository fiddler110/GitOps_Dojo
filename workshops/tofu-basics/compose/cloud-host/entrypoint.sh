#!/bin/sh
# Starts dockerd on the shared unix socket, then imports the images students
# are allowed to deploy (dojo/hello:1.0 and :2.0) from the rootfs baked into
# this image. Everything is offline.
set -eu

mkdir -p /run/cloud

# A restarted container keeps its filesystem, so the last run's leftovers are still here: dockerd's pid file, its
# runtime dir with the containerd socket, and the shared docker.sock. Start from a clean slate so dockerd never
# waits on (or trusts) a containerd from a run that is gone.
rm -rf /var/run/docker /var/run/docker.pid /run/cloud/docker.sock

# Off-the-shelf bootstrap (cgroups, iptables mode, dind wrapper); we patched
# the Dockerfile so it listens on the unix socket only.
#  --icc=false        containers cannot talk to each other
#  --iptables etc.    left default: published ports need NAT
dockerd-entrypoint.sh --icc=false --log-level=warn &
dockerd_pid=$!

# This script is PID 1, which ignores SIGTERM unless it has a handler, so `stop` used to end in a hard kill (dockerd
# and containerd never got to shut down). Pass the signal on and wait for dockerd to finish.
stopping=0
trap 'stopping=1; kill -TERM "$dockerd_pid" 2>/dev/null || true' TERM INT

# Wait for the daemon.
i=0
until docker info >/dev/null 2>&1; do
  i=$((i + 1))
  if [ "$i" -gt 120 ] || ! kill -0 "$dockerd_pid" 2>/dev/null; then
    echo "cloud-host: dockerd did not come up" >&2
    exit 1
  fi
  sleep 0.5
done

# The socket is shared with cloud-api, which runs as a different user.
chmod 0666 /run/cloud/docker.sock

import_hello() {
  version="$1"
  docker image inspect "dojo/hello:${version}" >/dev/null 2>&1 && return 0
  tar -C /opt/hello-rootfs -c . | docker import \
    --change 'ENTRYPOINT ["/entrypoint.sh"]' \
    --change "ENV HELLO_VERSION=${version}" \
    --change 'ENV PATH=/bin:/usr/bin' \
    --change 'EXPOSE 80' \
    - "dojo/hello:${version}" >/dev/null
  echo "cloud-host: imported dojo/hello:${version}"
}
import_hello 1.0
import_hello 2.0

echo "cloud-host: ready"
# A trapped signal makes `wait` return early: keep waiting until dockerd is really gone, then pass its status on.
status=0
wait "$dockerd_pid" || status=$?
while kill -0 "$dockerd_pid" 2>/dev/null; do
  wait "$dockerd_pid" || status=$?
done
# Asked to stop and dockerd did: that is a clean exit, not the 143 of a killed process.
[ "$stopping" = 1 ] && exit 0
exit "$status"
