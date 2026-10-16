# Shared skeleton for each workshop's `lab-prep <lab>` script (sourced, never run).
# The script sets LAST_LAB (and MIN_LAB when lab 0 isn't a lab), defines usage(),
# sources this file, then calls `lab_arg "$@"`, which leaves the chosen lab in $lab.
USER=${USER:-$(id -un)}   # unset under a bare `podman exec`

say()   { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
done_() { printf '    already done: %s\n' "$*"; }
run()   { printf '    $ %s\n' "$*"; "$@"; }
die()   { printf '\n\033[1;31mdojo prep: %s\033[0m\n' "$*" >&2; exit 1; }

lab_arg() {
  case "${1:-}" in -h|--help|"") usage; exit 0 ;; esac
  lab=$1
  [[ "$lab" =~ ^[0-9]+$ ]] && [ "$lab" -ge "${MIN_LAB:-0}" ] && [ "$lab" -le "$LAST_LAB" ] || { usage >&2; exit 2; }
}
