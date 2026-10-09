#!/bin/sh
# Kept so `engine/scripts/teardown.sh` still works: `./dojo stop` (the dojo
# CLI, engine/dojo/stop.py) does the teardown now. Same flags (--dry-run, --help).
exec "$(dirname "$0")/../dojo" stop "$@"
