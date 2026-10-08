#!/bin/sh
# Entry point for the project; the repo-root ./run.sh forwards here. All the
# work is the dojo CLI (engine/dojo/, Python 3.9+, which podman-compose already
# needs). This wrapper only finds python3, keeps two old spellings working and
# makes the one-time offer to install tab completion.
#
#   ./run.sh <workshop> [--test [N]] [--env NAME] [--dry-run] [--build-only] [--allow-default-passwords]
#   ./run.sh restart [<service> ...] [--clean] | stop [--dry-run] | status | doctor | config | logs
#   ./run.sh list | modules | build-all | setup | capacity | alias-setup | help
#
# './run.sh help' (or any command with --help) has the details; README.md and
# engine/README.md have the background.
set -eu

cd "$(dirname "$0")"

case "${1:-}" in
  --setup) shift; set -- setup "$@" ;;
  --capacity) shift; set -- capacity "$@" ;;
esac

# One-time, interactive offer to wire up tab completion (scripts/install-completion.sh
# no-ops after the first answer, and outside a terminal). Not before help, stop
# or a read-only command, not for a preview, and never while completing.
if [ -z "${_DOJO_COMPLETE:-}" ] && [ -f ./scripts/install-completion.sh ]; then
  case "${1:-}" in
    '' | help | -h | --help | stop | teardown | alias-setup | restart | status | doctor | config | list | modules | logs | completion | _*) ;;
    *)
      case " $* " in
        *" --dry-run "* | *" --build-only "*) ;;
        *) ./scripts/install-completion.sh ;;
      esac ;;
  esac
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "./run.sh needs python3 (3.9 or newer); podman-compose needs it too. Install python3 and try again." >&2
  exit 1
fi
DOJO_PROG="${DOJO_PROG:-./run.sh}"
export DOJO_PROG
exec python3 -B ./dojo/boot.py "$@"
