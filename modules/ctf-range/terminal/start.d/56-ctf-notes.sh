#!/bin/sh
# Give every account a ~/lab/notes.md at login, so `cat ~/lab/notes.md` works before the Notes page
# is ever opened. The page (ctf-notes/notes.py) creates the same file if it is missing; keep the
# two templates in step.
set -eu
for h in /home/*; do
  [ -d "$h" ] || continue
  u="$(basename "$h")"
  uid="$(id -u "$u" 2>/dev/null)" || continue
  [ "$uid" -ge 1000 ] || continue
  install -d -m 0755 -o "$u" -g "$u" "$h/lab"
  [ -e "$h/lab/notes.md" ] && continue
  cat > "$h/lab/notes.md" <<'NOTES'
# Lab notes

## Targets
- box / IP / ports:

## nmap results

## Credentials found
- user / password / where:

## Flags and ideas
NOTES
  chown "$u:$u" "$h/lab/notes.md"
  chmod 0644 "$h/lab/notes.md"
done
