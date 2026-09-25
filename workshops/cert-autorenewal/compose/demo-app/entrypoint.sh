#!/bin/sh
# Starts nginx, then watches the shared webroot for any change a student
# makes (a new vhost, an updated cert after issuance/renewal) and reloads
# nginx to pick it up. This is the only way a student's changes ever take
# effect, since they can only write into their own subdirectory of the
# volume mounted here — they have no access to this container itself.
set -eu

# Defensive re-assertion of the Dockerfile's sticky-bit permissions — see
# the comment there. Volume mounts can start empty even when the image has
# content at the same path, depending on the container engine/version, so
# this makes the permission correct unconditionally rather than relying on
# that behavior alone.
#
# Sticky bit alone only protects an *existing* entry from deletion/rename
# by another user — it does nothing to stop a different student from
# creating a not-yet-existing studentNN/ subdirectory first and becoming
# its owner. Actual per-student write isolation for a directory that
# doesn't exist yet comes from compose/terminal/start.d/90-cert-autorenewal.sh
# pre-creating and chown'ing every student's subdirectory before any
# student can log in.
mkdir -p /srv/webroot
chmod 1777 /srv/webroot

nginx -g 'daemon off;' &
NGINX_PID=$!

(
  while true; do
    inotifywait -r -e create,modify,delete,move,close_write /srv/webroot >/dev/null 2>&1 || sleep 2
    if nginx -t >/tmp/nginx-test.log 2>&1; then
      nginx -s reload
    else
      echo "cert-autorenewal demo-app: skipped reload, nginx -t failed:"
      cat /tmp/nginx-test.log
    fi
  done
) &

wait "${NGINX_PID}"
