#!/bin/sh
# `./run.sh <workshop> --dry-run` for every pack, with achievements off and on
# (RV13). That checks the Compose config, every extensions.json, the
# achievements catalog and the image pins, and starts nothing. Needs podman
# (+ podman-compose) or docker, and the allocator image, which the manifest
# and catalog checks run in; this script builds it if it is missing.
#   sh .github/scripts/dry-runs.sh
set -u

root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"

[ -f engine/.env ] || ./run.sh setup --default >/dev/null || { echo "setup failed" >&2; exit 1; }

if command -v podman >/dev/null && command -v podman-compose >/dev/null; then cli=podman; else cli=docker; fi
if ! "$cli" image inspect gitopsdojo/allocator:local >/dev/null 2>&1; then
  echo "==> building gitopsdojo/allocator:local for the manifest checks"
  "$cli" build -q -t gitopsdojo/allocator:local engine/allocator >/dev/null || exit 1
fi

log="$(mktemp)"
trap 'rm -f "$log"' EXIT
failed=""
for env_file in workshops/*/workshop.env; do
  w="$(basename "$(dirname "$env_file")")"
  modes=0
  [ -f "workshops/$w/achievements/catalog.json" ] && modes="0 1"
  for a in $modes; do
    echo "==> $w (ACHIEVEMENTS_ENABLED=$a)"
    if ACHIEVEMENTS_ENABLED=$a ./run.sh "$w" --dry-run >"$log" 2>&1 \
       && ! grep -q 'Extensions: not checked' "$log"; then
      grep -E '^(extensions:|achievements:)' "$log" || true
    else
      cat "$log"
      failed="$failed $w/achievements=$a"
    fi
  done
done

if [ -n "$failed" ]; then
  echo "FAILED:$failed" >&2
  exit 1
fi
echo "Every workshop's dry run passed."
