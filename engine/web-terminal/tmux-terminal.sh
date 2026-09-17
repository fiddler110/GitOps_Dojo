#!/bin/sh
# Entry point for every VS Code integrated terminal (the auto-opened task
# AND any terminal the student opens manually, e.g. via a split or a new
# tab -- see entrypoint.sh's tasks.json and settings.json for where this
# is wired in). Each invocation gets its own uniquely-named tmux session
# (this shell's own PID is always free at the moment it runs) instead of
# a shared one, so splitting the terminal panel still gives independent
# shells -- two terminals attached to the SAME tmux session would mirror
# each other's input/output, which is not what a split is for.
#
# A facilitator's /admin/watch/<studentId> then finds and attaches
# read-only to whichever of a student's tmux sessions (this one, or the
# standalone Terminal tool's `main`) was most recently active -- see
# workspace-control.py's most_active_session().
exec tmux new-session -A -s "vscode-$$"
