#!/bin/sh
# Keeps each demo bot's tmux session alive for the life of the container.
# Runs as root, backgrounded by entrypoint.sh (only when BOT_COUNT > 0),
# alongside the workspace-control.py foreground process.
#
# Why this exists: a facilitator's "Release" button (see allocator/server.py
# and workspace-control.py's /stop/<username>) does `pkill -KILL -u
# <username>` -- for a bot account that kills its tmux server and, with it,
# the bot-runner.sh process inside. Without something to notice and restart
# it, a released bot would just stay dead for the rest of the workshop.
# This loop polls every account's tmux sessions and (re)starts `main` -- the
# same session name workspace-control.py uses for a real student's `term`
# tool -- whenever it's missing, so the facilitator's watch tile and the
# bot's own progress (persisted in ~/.dojo-bot-state, untouched by any of
# this) both pick back up automatically, no facilitator action needed.
set -u

bot_count="${BOT_COUNT:-0}"
bot_prefix="${BOT_PREFIX:-testuser}"
poll_interval="${BOT_SUPERVISOR_INTERVAL:-15}"

[ "$bot_count" -gt 0 ] || exit 0

while true; do
  counter=1
  while [ "$counter" -le "$bot_count" ]; do
    user="$(printf '%s%d' "$bot_prefix" "$counter")"
    if id "$user" >/dev/null 2>&1; then
      if ! su - "$user" -c 'tmux has-session -t main' >/dev/null 2>&1; then
        su - "$user" -c 'tmux new-session -d -s main /opt/dojo-shell/bot-runner.sh' >/dev/null 2>&1
      fi
    fi
    counter=$((counter + 1))
  done
  sleep "$poll_interval"
done
