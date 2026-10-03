#!/bin/sh
# account.d hook (engine/web-terminal/entrypoint.sh, workspace-control.py): one account's
# /srv/webroot/<user>/{conf.d,html,certs}, owned by it before anyone can log in, at start and
# again after a student reset. Why it must exist before the student's own `mkdir -p`: see
# start.d/90-cert-autorenewal.sh.
set -eu
user="$1"
mkdir -p "/srv/webroot/$user/conf.d" "/srv/webroot/$user/html" "/srv/webroot/$user/certs"
chown -R "$user:$(id -gn "$user")" "/srv/webroot/$user"
chmod 0755 "/srv/webroot/$user" "/srv/webroot/$user/conf.d" "/srv/webroot/$user/html" "/srv/webroot/$user/certs"
