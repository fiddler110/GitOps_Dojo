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

# A fake, always-reachable, instantly-answering DNS stub for the inner
# dockerd's embedded per-container resolver to forward to. ctf_ops/ctf_net
# are both `internal: true` (CTF-D24 - no real resolver reachable at all),
# so with no --dns configured, a slot container's DNS query has nowhere to
# go and the kernel just drops it, with nothing coming back until the
# client gives up - and in the meantime a shell `cmd1; cmd2` chain never
# even reaches cmd2, since cmd1 (whatever triggered the lookup) hasn't
# returned yet. Caught live (2026-10-06): ping-tool's whole command-
# injection teaching point (`host <input>; <injected command>`) silently
# broke this way - the injected half never ran, because `host 127.0.0.1`
# just hung until Flask's own subprocess timeout killed the lot. dnsmasq
# here answers every query immediately (everything maps to 127.0.0.1,
# meaningless by design - this is not a real resolver) and never itself
# touches a network (--no-resolv --no-hosts, nothing to forward to even if
# it wanted to), so a lookup fails or resolves FAST either way.
dnsmasq --no-daemon --no-resolv --no-hosts --address=/#/127.0.0.1 \
  --listen-address=127.0.0.1 --port=53 --bind-interfaces \
  --pid-file=/run/ctf/fake-dns.pid &

#  --icc=false         inner containers (the slots) cannot talk to each other (S14).
#  --dns                every slot's embedded per-container DNS proxy forwards
#                        here (the fake stub above) instead of nowhere.
#  --insecure-registry  the in-lab registry (spike S6) has no TLS — it is
#                        internal-only, so plaintext within ctf_ops is the
#                        accepted trade-off (CTF-D24's offline posture is
#                        about reaching outward, not about TLS inward).
set -- --icc=false --log-level=warn --dns 127.0.0.1
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
  # CTF-D26: a per-pack ctf-host image (ctf-host-ctf1/ctf-host-ctf2, ...)
  # never bakes this rootfs in at all — skip gracefully rather than failing.
  [ -d /opt/portal-rootfs ] || return 0
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
  # CTF-D26: same guard as import_target above.
  [ -d /opt/portal-deps-rootfs ] || return 0
  docker image inspect gitopsdojo/ctf-customer-portal-base:pinned >/dev/null 2>&1 && return 0
  tar -C /opt/portal-deps-rootfs -c . | docker import - gitopsdojo/ctf-customer-portal-base:pinned >/dev/null
  echo "ctf-host: imported gitopsdojo/ctf-customer-portal-base:pinned"
}
import_portal_deps_base

# Import the 8 attack-ladder target rootfses (CTF-1/CTF-2, plan §7.3). Each
# is never rebuilt (students attack, never patch, these), so a plain import
# is the whole story — no offline-rebuild base to vendor alongside, unlike
# customer-portal above. The --change lines reproduce each target's own
# Dockerfile (ENTRYPOINT/ENV/EXPOSE/USER/WORKDIR); a workshop pack's
# CTF_ATTACK_TARGETS (controller.py's AttackManager, CTF-D20) must name these
# exact tags.
import_attack_target() {
  tag="$1" rootfs="$2" user="$3" expose="$4" env="$5"
  # CTF-D26: a per-pack ctf-host image bakes in only its own session's
  # targets; skip any rootfs this particular image doesn't have, rather
  # than failing the whole start over a target this pack doesn't expose.
  [ -d "$rootfs" ] || return 0
  docker image inspect "$tag" >/dev/null 2>&1 && return 0
  tar -C "$rootfs" -c . | docker import \
    --change 'ENTRYPOINT ["python3", "/app/app.py"]' \
    --change "ENV $env" \
    --change "EXPOSE $expose" \
    --change "USER $user" \
    --change 'WORKDIR /app' \
    - "$tag" >/dev/null
  echo "ctf-host: imported $tag"
}
import_attack_target ctf-sqli-login:base /opt/sqli-login-rootfs sqli "5000 2222" \
  "PORT=5000 PYTHONUNBUFFERED=1 PATH=/usr/local/bin:/usr/bin:/bin"
import_attack_target ctf-idor-pcap:base /opt/idor-pcap-rootfs idor "5000 2222 2121" \
  "PORT=5000 PYTHONUNBUFFERED=1 PATH=/usr/local/bin:/usr/bin:/bin"
import_attack_target ctf-weak-auth-portal:base /opt/weak-auth-portal-rootfs weakauth "5000 2222" \
  "PORT=5000 PYTHONUNBUFFERED=1 PATH=/usr/local/bin:/usr/bin:/bin"
import_attack_target ctf-cert-trust-bypass:base /opt/cert-trust-bypass-rootfs certbypass "5000 2222" \
  "PORT=5000 PYTHONUNBUFFERED=1 PATH=/usr/local/bin:/usr/bin:/bin"
import_attack_target ctf-ping-tool:base /opt/ping-tool-rootfs pingtool "5000 2222" \
  "PORT=5000 PYTHONUNBUFFERED=1 PATH=/usr/local/bin:/usr/bin:/bin"
import_attack_target ctf-ssrf-fetcher:base /opt/ssrf-fetcher-rootfs ssrffetcher "5000 2222" \
  "PORT=5000 INTERNAL_PORT=5001 PYTHONUNBUFFERED=1 PATH=/usr/local/bin:/usr/bin:/bin"
import_attack_target ctf-api-mass-assignment:base /opt/api-mass-assignment-rootfs massassign "5000 2222" \
  "PORT=5000 PYTHONUNBUFFERED=1 PATH=/usr/local/bin:/usr/bin:/bin"
import_attack_target ctf-api-bfla:base /opt/api-bfla-rootfs apibfla "5000 2222" \
  "PORT=5000 PYTHONUNBUFFERED=1 PATH=/usr/local/bin:/usr/bin:/bin"
# leaky-config (target 5, CTF-3) only ever bakes into the full-catalog
# `ctf-host` stage today (no CTF-3 pack decided yet — CTF-D26 only scoped
# CTF-1/CTF-2) so this is a no-op on ctf-host-ctf1/ctf-host-ctf2.
import_attack_target ctf-leaky-config:base /opt/leaky-config-rootfs leakyconfig "5000 2222" \
  "PORT=5000 PYTHONUNBUFFERED=1 PATH=/usr/local/bin:/usr/bin:/bin"
# git-secrets (target 8, CTF-3) only ever bakes into the full-catalog
# `ctf-host` stage today, same as leaky-config above.
import_attack_target ctf-git-secrets:base /opt/git-secrets-rootfs gitsecrets "5000 2222" \
  "PORT=5000 PYTHONUNBUFFERED=1 PATH=/usr/local/bin:/usr/bin:/bin"

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
