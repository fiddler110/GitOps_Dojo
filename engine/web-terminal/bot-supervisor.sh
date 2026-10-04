#!/bin/sh
# Keeps each demo bot's tmux session alive for the life of the container.
# Runs as root, backgrounded by entrypoint.sh (only when BOT_COUNT > 0),
# alongside the workspace-control.py foreground process.
#
# Why this exists: a facilitator's "Release" button (see allocator/api.py
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
    # A student reset (workspace-control.py) marks the bot while it removes
    # and rebuilds its home; restarting it then would write into that home.
    if id "$user" >/dev/null 2>&1 && [ ! -e "/run/dojo-reset/$user" ]; then
      if [ "${TERMINAL_FLAVOR:-web}" = zellij ]; then
        # Same `main` session, running the "bot" layout
        # (/etc/zellij/layouts/bot.kdl), so the watch tile's `zellij watch
        # main` has something to show. Zellij needs a terminal client for its
        # layout, and a detached tmux session provides one (its background
        # sessions ignore the layout); it ends with Zellij, so it never lingers.
        if ! su - "$user" -c 'zellij list-sessions --short 2>/dev/null | grep -qx main' >/dev/null 2>&1; then
          su - "$user" -c 'tmux new-session -d -s zbot -x 100 -y 30 "zellij --new-session-with-layout /etc/zellij/layouts/bot.kdl --session main"' >/dev/null 2>&1
        fi
      elif ! su - "$user" -c 'tmux has-session -t main' >/dev/null 2>&1; then
        su - "$user" -c 'tmux new-session -d -s main /opt/dojo-shell/bot-runner.sh' >/dev/null 2>&1
      fi
    fi
    counter=$((counter + 1))
  done
  sleep "$poll_interval"
done
