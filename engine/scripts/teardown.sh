#!/bin/sh
# End-of-workshop cleanup. Stops the stack and destroys every volume, so the
# next workshop always starts from a clean slate. Nothing here is recoverable
# after it runs.
#
# Usage:
#   ./run.sh stop            # (also: ./run.sh teardown) -- or run this script directly
#   ./run.sh stop --dry-run  # list what would be removed; removes nothing
#   ./run.sh stop --help
set -eu

usage() {
  cat <<'EOF'
Usage: ./run.sh stop [--dry-run]        (alias: ./run.sh teardown)

Stops the workshop stack and deletes every volume -- each student's terminal
home and all Forgejo data (repos, accounts, PRs). There is no undo and no
archive step, so export anything you want to keep first.

Uses the same Compose files the last ./run.sh <workshop> started with,
including that workshop's overlay, so overlay services and volumes are
cleaned up too.

Options:
  --dry-run     show the Compose files, services, volumes, and containers this
                would act on, and the exact command it would run -- without
                removing anything
  -h, --help    show this message (does not tear anything down)
EOF
}

dry_run=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) dry_run=1 ;;
    -h | --help) usage; exit 0 ;;
    *)
      echo "Unrecognized argument: ${arg}" >&2
      usage >&2
      exit 1 ;;
  esac
done

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
# .last-overlay holds one extra -f file per line (each module's compose.yml,
# then the workshop overlay), as the last ./run.sh <workshop> wrote it.
compose_args="-f docker-compose.yml"
overlay=""
if [ -f .last-overlay ]; then
  overlay="$(grep -v '^$' .last-overlay | tr '\n' ' ' || true)"
  overlay="${overlay% }"
  for f in $overlay; do
    compose_args="$compose_args -f $f"
  done
fi

if [ "$dry_run" = "1" ]; then
  echo "DRY RUN -- nothing will be removed."
  echo
  if [ -n "$overlay" ]; then
    echo "Compose files: docker-compose.yml ${overlay} (from .last-overlay)"
  else
    echo "Compose files: docker-compose.yml only (no overlay recorded in .last-overlay)"
  fi
  echo
  echo "Services in this Compose project:"
  # shellcheck disable=SC2086
  services="$(compose $compose_args config --services 2>/dev/null)" || services=""
  if [ -n "$services" ]; then
    echo "$services" | sed 's/^/  /'
  else
    echo "  (none found -- 'compose ${compose_args} config' may have failed, e.g. no .env yet)"
  fi
  echo
  echo "Volumes that --volumes would delete:"
  # Parsed from the top-level `volumes:` block of the merged config rather
  # than `config --volumes`: podman-compose doesn't support that flag, and
  # this works the same on docker compose and podman-compose.
  # shellcheck disable=SC2086
  volumes="$(compose $compose_args config 2>/dev/null |
    awk '/^volumes:/ {f=1; next} /^[^ ]/ {f=0} f && /^  [^ ]/ {sub(/:.*/, ""); print $1}')" || volumes=""
  if [ -n "$volumes" ]; then
    echo "$volumes" | sed 's/^/  /'
  else
    echo "  (none found -- 'compose ${compose_args} config' may have failed)"
  fi
  echo
  echo "Containers currently up for this project:"
  # shellcheck disable=SC2086
  compose $compose_args ps 2>/dev/null | sed 's/^/  /' || true
  echo
  echo "Would run: compose ${compose_args} down --volumes --remove-orphans"
  echo "Dry run complete: nothing was removed."
  exit 0
fi

echo "Tearing down the workshop stack and all volumes (student homes, Forgejo data)..."
# shellcheck disable=SC2086
compose $compose_args down --volumes --remove-orphans
rm -f .last-overlay
echo "Done. No workshop data was retained."
