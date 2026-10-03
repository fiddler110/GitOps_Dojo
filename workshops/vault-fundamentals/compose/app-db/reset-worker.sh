#!/bin/sh
# app-db's half of a facilitator's student reset (docs/archive/STUDENT-RESET-PLAN.md
# §4.5). Postgres takes no HTTP calls and its superuser works only on the
# local socket, so app-host (apphost.py) holds the reset hook and queues the
# job; this loop, started beside Postgres as the postgres user (see the
# overlay's app-db entrypoint), long-polls it, runs the SQL and posts the
# result: `ok` or `fail`, then the last lines of output. It proves itself
# with RESET_TOKEN (app-host's hook token); empty: no worker.
#
#   teardown   drop the student's database, roles and the vault's logins,
#              then make them again with a new first password (/bootstrap/<s>),
#              ready for the vault's provision (30-platform.sh). It runs after
#              the vault's teardown, whose lease revocations still log in as
#              vault_<s>.
#   provision  make them only if something is missing.
set -u
umask 022
. /opt/app-db/students.sh

[ -n "${RESET_TOKEN:-}" ] || { echo "app-db reset worker: no RESET_TOKEN, student resets are off"; exit 0; }
url="${APP_HOST_URL:-http://app-host:8080}/_dojo/db-work"
# The image's first-start set-up runs a server on the socket only; wait for the real one.
until pg_isready -q -h 127.0.0.1; do sleep 2; done
echo "app-db reset worker: taking jobs from $url"

db_reset() {
  users | grep -qx -- "$2" || { echo "$2 is not an account of this class"; return 1; }
  case "$1" in
    teardown)
      drop_student "$2" && make_student "$2" && echo "app_$2 dropped and made again" ;;
    provision)
      if student_ready "$2"; then echo "app_$2 is in place"; return 0; fi
      drop_student "$2" && make_student "$2" && echo "app_$2 made again" ;;
    *) return 1 ;;
  esac
}

while :; do
  job="$(wget -q -O - -T 60 --header "X-Dojo-Reset-Token: $RESET_TOKEN" "$url" 2>/dev/null)" \
    || { sleep 5; continue; }
  [ -n "$job" ] || continue
  # shellcheck disable=SC2086 # "<id> <phase> <user>", checked below
  set -- $job
  case "${1:-}:${2:-}:${3:-}" in
    *[!a-z0-9_:-]*) echo "app-db reset worker: refused a malformed job"; continue ;;
    [0-9a-f]*:teardown:[a-z]*|[0-9a-f]*:provision:[a-z]*) ;;
    *) echo "app-db reset worker: refused a malformed job"; continue ;;
  esac
  if out="$(db_reset "$2" "$3" 2>&1)"; then res=ok; else res=fail; fi
  echo "app-db reset worker: $2 $3: $res"
  wget -q -O /dev/null -T 10 --header "X-Dojo-Reset-Token: $RESET_TOKEN" \
    --post-data "$(printf '%s\n%s' "$res" "$(printf '%s\n' "$out" | tail -n 4)")" \
    "$url/$1" 2>/dev/null || echo "app-db reset worker: could not post the result of $2 $3"
done
