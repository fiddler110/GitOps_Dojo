#!/usr/bin/env bash
# Achievement catalog editor: a local page to switch achievements on and off and edit their text.
#
#   modules/achievements/edit.sh <workshop|all>      (PORT=8099 by default)
#
# Binds 127.0.0.1 only and needs no stack. Save validates the whole catalog, writes the changed
# JSON and regenerates ACHIEVEMENTS.md; commit both as usual.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../.." && pwd)"

if [[ $# -ne 1 || "$1" == -* ]]; then
  echo "usage: $0 <workshop|all>" >&2
  echo "workshops with a catalog:" >&2
  for d in "$repo"/workshops/*/achievements/catalog.json; do
    [[ -f "$d" ]] && echo "  $(basename "$(dirname "$(dirname "$d")")")" >&2
  done
  exit 2
fi

exec python3 -B "$here/editor/server.py" --root "$repo" --workshop "$1" --port "${PORT:-8099}"
