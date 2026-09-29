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

# Same container CLI as compose() above, for the status table.
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  cli=docker
else
  cli=podman
fi
c_green="$(printf '\033[32m')"; c_yellow="$(printf '\033[33m')"; c_red="$(printf '\033[31m')"
c_off="$(printf '\033[0m')"; c_cyan="$(printf '\033[1;36m')"; c_dim="$(printf '\033[2m')"
fmt_elapsed() { printf '%d:%02d' "$(($1 / 60))" "$(($1 % 60))"; }

# One block, redrawn in place: every container that was up when teardown began
# and every volume, going from "up" to "removed". Terminal only.
td_draw() {
  n=0; [ ! -s "$td_state" ] || n="$(cat "$td_state")"
  [ "$n" -eq 0 ] || printf '\033[%dA\033[J' "$n"
  now_c="$($cli ps -a --filter name=workshop_ --format '{{.Names}}|{{.Status}}' 2>/dev/null)"
  vols_left="$($cli volume ls -q 2>/dev/null | grep -c '^engine_' || true)"
  rows="$(for c in $td_containers; do
    st="$(printf '%s\n' "$now_c" | awk -F'|' -v c="$c" '$1 == c { print $2 }')"
    if [ -z "$st" ]; then echo "$c|removed"
    elif printf '%s' "$st" | grep -q '^Exited'; then echo "$c|stopped"
    else echo "$c|up"; fi
  done)"
  gone="$(printf '%s\n' "$rows" | grep -c '|removed$' || true)"
  out="$(printf '  %s%s%s   %s%s of %s containers removed%s   volumes left: %s of %s\n' "$c_dim" "$(fmt_elapsed $(($(date +%s) - td_start)))" "$c_off" "$c_cyan" "$gone" "$td_total" "$c_off" "$vols_left" "$td_vols")"
  shown="$rows"
  [ "$td_total" -le 25 ] || shown="$(printf '%s\n' "$rows" | grep -v '|removed$')"
  [ -z "$shown" ] || out="${out}
$(printf '%s\n' "$shown" | awk -F'|' -v g="$c_green" -v y="$c_yellow" -v o="$c_off" '
    { col = ($2 == "removed") ? g : y; mark = ($2 == "removed") ? "+" : "~"
      printf "  %s%s %-36s %s%s\n", col, mark, $1, $2, o }')"
  printf '%s\n' "$out"
  printf '%s\n' "$(printf '%s\n' "$out" | wc -l)" > "$td_state"
}

echo "Tearing down the workshop stack and all volumes (student homes, Forgejo data)..."
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  td_containers="$($cli ps -a --filter name=workshop_ --format '{{.Names}}' 2>/dev/null | sort)"
  td_total="$(printf '%s\n' "$td_containers" | grep -c . || true)"
  td_vols="$($cli volume ls -q 2>/dev/null | grep -c '^engine_' || true)"
  td_start="$(date +%s)"; td_state="$(mktemp)"; echo 0 > "$td_state"
  td_log="$(mktemp "${TMPDIR:-/tmp}/dojo-down.XXXXXX")"
  echo "Compose output is in ${td_log}"
  printf '\033[?25l'
  ( while :; do td_draw; sleep 1; done ) &
  watch_pid=$!
  trap 'kill "$watch_pid" 2>/dev/null; printf "\033[?25h"' EXIT INT TERM
  rc=0
  # shellcheck disable=SC2086
  compose $compose_args down --volumes --remove-orphans > "$td_log" 2>&1 || rc=$?
  kill "$watch_pid" 2>/dev/null; wait "$watch_pid" 2>/dev/null || true
  td_draw
  printf '\033[?25h'
  trap - EXIT INT TERM
  rm -f "$td_state"
  if [ "$rc" != 0 ]; then
    printf '%scompose down failed (exit %s); the last lines of its output:%s\n' "$c_red" "$rc" "$c_off"
    tail -n 20 "$td_log"
    exit "$rc"
  fi
else
  # shellcheck disable=SC2086
  compose $compose_args down --volumes --remove-orphans
fi
rm -f .last-overlay
echo "Done. No workshop data was retained."
