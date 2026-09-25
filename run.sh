#!/bin/sh
# Repo-root entry point. All the logic lives in engine/run.sh; this just
# forwards to it so `./run.sh <command>` works from the top of the repo.
# One exception, which is repo upkeep rather than a class: `./run.sh
# update-decks [--all | --check | NAME...]` re-exports the talks to
# handouts/<workshop>_presentation.pptx (handouts/build-presentations.sh).
if [ "${1:-}" = update-decks ]; then
  shift
  exec "$(dirname "$0")/handouts/build-presentations.sh" "$@"
fi
exec "$(dirname "$0")/engine/run.sh" "$@"
