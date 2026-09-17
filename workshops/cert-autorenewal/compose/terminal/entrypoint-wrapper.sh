#!/bin/sh
# Starts the system cron daemon (each student's own `crontab -e` in Lab 4
# needs it running to fire at all — nothing else in this image starts it),
# then hands off to the base image's own entrypoint unchanged.
set -eu

cron

exec /usr/local/bin/web-terminal-entrypoint "$@"
