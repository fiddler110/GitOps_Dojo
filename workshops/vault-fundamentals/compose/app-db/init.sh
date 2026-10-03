#!/bin/sh
# app-db first-start set-up (Lab 12), run once by the Postgres image's
# entrypoint on a new data volume, as the postgres user: every student's
# database and roles (students.sh, which a student reset also uses).
set -eu
umask 022
. /opt/app-db/students.sh

for s in $(users); do
  make_student "$s" || { echo "app-db: could not set up $s" >&2; exit 1; }
done
echo "app-db: databases for ${STUDENT_COUNT:-0} students and ${BOT_COUNT:-0} bots"
