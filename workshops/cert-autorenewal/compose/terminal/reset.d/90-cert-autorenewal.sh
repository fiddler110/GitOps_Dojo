#!/bin/sh
# reset.d hook (student reset, workspace-control.py): remove the student's demo site (vhost,
# page, certificates and key). demo-app sees the change and reloads without it; account.d then
# makes the empty folders again. Their cron job goes with the engine's crontab clean-up.
set -eu
user="$1"
case "$user" in ''|*/*|.*) echo "bad account name" >&2; exit 1 ;; esac
rm -rf "/srv/webroot/$user"
echo "demo site removed"
