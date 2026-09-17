#!/bin/sh
# GIT_ASKPASS target for bot-runner.sh. The bot's clone/remote URL embeds
# its own username (http://<BOT_USER>@git-server:3000/...), so git only
# ever calls this for the password prompt -- it just echoes BOT_PASSWORD,
# which bot-runner.sh exports before running any git command. Never printed
# to the terminal itself (git captures this script's stdout directly).
echo "$BOT_PASSWORD"
