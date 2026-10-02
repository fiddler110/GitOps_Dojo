#!/bin/sh
# One-time, interactive offer to install the `dojo` command and tab
# completion (scripts/alias-setup.sh does the work). run.sh calls this itself
# on every invocation; it no-ops instantly once a decision has been recorded
# (accepted, declined, already installed), so it only ever prompts once per
# machine, and never outside an interactive terminal.
set -eu

cd "$(dirname "$0")/.." # -> engine/
state_file=".build-state/.completion-checked"

[ -f "$state_file" ] && exit 0

# Only prompt in an interactive terminal -- never block CI, --test bot
# runs, or any other non-interactive invocation of run.sh.
if [ ! -t 0 ] || [ ! -t 1 ]; then
  exit 0
fi

mkdir -p .build-state
if ./scripts/alias-setup.sh --check; then
  echo "already-installed" >"$state_file"
  exit 0
fi

echo
echo "Install the 'dojo' command? It runs this ./run.sh from any directory"
echo "(dojo <workshop>, dojo stop, ...) and adds tab completion for both."
echo "It writes ~/.local/bin/dojo and one marked block in your shell profile."
printf 'Install it now? [y/N] '
read -r answer || answer=""
case "$answer" in
  y | Y | yes | Yes)
    ./scripts/alias-setup.sh || true
    echo "accepted" >"$state_file"
    ;;
  *)
    echo "Skipped; './run.sh alias-setup' installs it any time."
    echo "declined" >"$state_file"
    ;;
esac
echo
