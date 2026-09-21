#!/bin/sh
# Repo-root entry point. All the logic lives in engine/run.sh; this just
# forwards to it so `./run.sh <command>` works from the top of the repo.
exec "$(dirname "$0")/engine/run.sh" "$@"
