#!/bin/sh
# End-of-workshop cleanup. Stops the stack and destroys every volume, so the
# next workshop always starts from a clean slate. Nothing here is recoverable
# after it runs.
set -eu

cd "$(dirname "$0")/.."

compose() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  else
    podman-compose "$@"
  fi
}

# run.sh records whichever overlay it started the stack with in
# .last-overlay. Tearing down with only docker-compose.yml -- when the
# stack was actually started with an overlay layered on top -- leaves
# Compose blind to that overlay's services (so it can't respect their
# depends_on shutdown order) and its volumes (so they survive --volumes).
# Use the same -f set run.sh used, falling back to the base file alone if
# no overlay was recorded (or nothing was ever started).
compose_args="-f docker-compose.yml"
if [ -f .last-overlay ]; then
  overlay="$(cat .last-overlay)"
  [ -n "$overlay" ] && compose_args="$compose_args -f ${overlay}"
fi

echo "Tearing down the workshop stack and all volumes (student homes, Forgejo data)..."
# shellcheck disable=SC2086
compose $compose_args down --volumes --remove-orphans
rm -f .last-overlay
echo "Done. No workshop data was retained."
