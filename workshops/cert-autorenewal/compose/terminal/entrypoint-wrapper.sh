#!/bin/sh
# Starts the system cron daemon (each student's own `crontab -e` in Lab 4
# needs it running to fire at all — nothing else in this image starts it),
# then hands off to the base image's own entrypoint unchanged.
set -eu

cron

# Pre-create every student's /srv/webroot/<studentNN>/{conf.d,html,certs}
# subdirectory, owned by that student, before any student can possibly log
# in. Without this, lab2.md's own `mkdir -p "/srv/webroot/${me}/..."` would
# be the *first* creation of that path — and demo-app/entrypoint.sh only
# chmods /srv/webroot itself 1777, not its future children. Sticky bit on a
# world-writable directory only stops another user from deleting/renaming
# an entry that already exists; it does nothing to stop a different student
# from creating studentNN's subdirectory first and becoming its owner. A
# malicious student could otherwise race a target student's first `mkdir
# -p`, win it, and leave the target with a directory they can't write into
# (owned by the attacker, default-umask mode) — or plant a spoofed vhost
# under the target's own hostname before they log in. This lives in this
# workshop's own wrapper, not the shared engine/web-terminal/entrypoint.sh,
# so that base entrypoint stays workshop-agnostic.
#
# Backgrounded (not exec'd) and gated on the base entrypoint's own account-
# creation loop having finished — signaled by the last expected student's
# home directory existing, since that loop creates accounts in order and
# nothing (code-server/ttyd) is reachable for anyone until the base
# entrypoint's own final `exec workspace-control.py` below has run anyway.
# workspace-control.py's reap_children() reaps this the same way it reaps
# any other child of PID 1 (e.g. the bot-supervisor.sh loop entrypoint.sh
# itself backgrounds) — no new reaping logic needed.
#
# Idempotent: mkdir -p/chown -R/chmod are all safe to rerun, so a container
# restart just reasserts the same ownership/mode — no extra guard needed.
(
  # set +e here, not inherited -eu: this loop must not go silently quiet
  # for every remaining student just because one command failed (e.g. a
  # transient `id -u` miss) — see the retry below.
  set +e

  last_home="/home/${STUDENT_PREFIX}$(printf '%02d' "$STUDENT_COUNT")"
  while [ ! -d "$last_home" ]; do
    sleep 0.5
  done

  counter=1
  while [ "$counter" -le "$STUDENT_COUNT" ]; do
    username="$(printf '%s%02d' "$STUDENT_PREFIX" "$counter")"

    # Accounts are created sequentially by entrypoint.sh, and we've already
    # waited for the *last* one's home directory to appear, so this should
    # never actually miss — but retry a few times rather than trust that,
    # since aborting outright here (under inherited -u, an id -u failure
    # would otherwise just stop this account and, without set +e, the
    # whole background job) would silently skip every remaining student.
    uid=""
    attempt=0
    while [ -z "$uid" ] && [ "$attempt" -lt 10 ]; do
      uid="$(id -u "$username" 2>/dev/null)"
      [ -n "$uid" ] || sleep 0.5
      attempt=$((attempt + 1))
    done

    if [ -z "$uid" ]; then
      echo "cert-autorenewal: could not resolve uid for $username, skipping webroot pre-create" >&2
      counter=$((counter + 1))
      continue
    fi

    mkdir -p "/srv/webroot/$username/conf.d" "/srv/webroot/$username/html" "/srv/webroot/$username/certs"
    chown -R "$username:$username" "/srv/webroot/$username"
    chmod 0755 "/srv/webroot/$username" "/srv/webroot/$username/conf.d" "/srv/webroot/$username/html" "/srv/webroot/$username/certs"

    counter=$((counter + 1))
  done

  # The facilitator gets a demo site of their own too (the /demo route sends
  # them to <facilitator>.<zone>, see ../../extensions.json), so pre-create
  # theirs for the same reason. Their account exists before any student's.
  fac="${FACILITATOR_USERNAME:-root}"
  if id -u "$fac" >/dev/null 2>&1; then
    mkdir -p "/srv/webroot/$fac/conf.d" "/srv/webroot/$fac/html" "/srv/webroot/$fac/certs"
    chown -R "$fac:$(id -gn "$fac")" "/srv/webroot/$fac"
    chmod 0755 "/srv/webroot/$fac" "/srv/webroot/$fac/conf.d" "/srv/webroot/$fac/html" "/srv/webroot/$fac/certs"
  else
    echo "cert-autorenewal: facilitator account $fac not found, skipping its webroot pre-create" >&2
  fi
) &

exec /usr/local/bin/web-terminal-entrypoint "$@"
