#!/bin/sh
# start.d hook, run once by the base entrypoint (engine/web-terminal/
# entrypoint.sh) as root, after every account exists and before any
# workspace is served.
#
# 1. Starts the system cron daemon: each student's own `crontab -e` in Lab 4
#    needs it running to fire at all, and nothing else in this image starts it.
#
# 2. Pre-creates the facilitator's /srv/webroot/<user>/{conf.d,html,certs} (every
#    other account's comes from account.d/90-cert-autorenewal.sh, the same way),
#    owned by that account, before anyone can log in. Without this, lab2.md's
#    own `mkdir -p "/srv/webroot/${me}/..."` would be the *first* creation of
#    that path, and demo-app/entrypoint.sh only chmods /srv/webroot itself
#    1777, not its future children. The sticky bit only stops another user
#    deleting or renaming an entry that already exists; it does nothing to stop
#    a different student creating studentNN's subdirectory first and becoming
#    its owner. A malicious student could otherwise race a target student's
#    first `mkdir -p`, win it, and leave the target with a directory they can't
#    write into, or plant a spoofed vhost under the target's own hostname. The
#    facilitator gets one too: they have their own demo site
#    (<facilitator>.<zone>, see dns-seed/seed.sh).
set -eu

cron

make_webroot() {
  user="$1"
  mkdir -p "/srv/webroot/$user/conf.d" "/srv/webroot/$user/html" "/srv/webroot/$user/certs"
  chown -R "$user:$(id -gn "$user")" "/srv/webroot/$user"
  chmod 0755 "/srv/webroot/$user" "/srv/webroot/$user/conf.d" "/srv/webroot/$user/html" "/srv/webroot/$user/certs"
}

# Students and bots: account.d/90-cert-autorenewal.sh (run after this, and again after a student reset).
make_webroot "${FACILITATOR_USERNAME:-root}"
