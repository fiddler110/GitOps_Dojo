#!/bin/sh
# app-host start-up (the Dockerfile's ENTRYPOINT runs it under tini). The
# slots' egress allowlist needs NET_ADMIN once; the platform, which runs the
# students' apps, doesn't get it: setpriv drops NET_ADMIN (and SETPCAP, needed
# only to drop) from the bounding set before the platform starts. A container
# restart gets both again and re-runs the idempotent allowlist.
set -e
python3 -B -u /opt/app-host/apphost.py --isolate-only
export APPHOST_ISOLATED=1
exec setpriv --bounding-set -net_admin,-setpcap -- python3 -B -u /opt/app-host/apphost.py
