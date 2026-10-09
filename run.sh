#!/bin/sh
# Retired: the command is ./dojo now. This stub only keeps an old `dojo` shim or
# alias (which points here) working; delete it once nothing calls it.
echo "run.sh is retired; use ./dojo (re-run './dojo alias-setup' to refresh the dojo command)." >&2
exec "$(dirname "$0")/dojo" "$@"
