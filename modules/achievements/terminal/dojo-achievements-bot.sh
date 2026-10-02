# achievements module: the --test demo bots' counterpart of dojo-achievements.zsh.
# bot-runner.sh (bash, not an interactive zsh) sources /etc/dojo/bot.d/*.sh and calls
# bot_cmd_pre / bot_cmd_post around every command it runs, so each bot command reaches
# POST /api/shell through `dojo-check --shell` with the same DOJO_SH_* fields the zsh hook
# sends, in the background so the bot never waits.
#
# Identity: dojo-check proves who it is with the Forgejo token in ~/.git-credentials.
# forgejo-token.py can't make one for a bot (a bot's Forgejo password is BOT_PASSWORD, not
# the derived student one), so the first command makes one here with the bot's own password
# (read from its netrc, never an argv), named and scoped like forgejo-token.py's.

[ -x /usr/local/bin/dojo-check ] || return 0

_dojo_bot_host=git-server:3000
_dojo_bot_branch='' _dojo_bot_in_repo=0 _dojo_bot_merging=0
_dojo_bot_tok_ok=0 _dojo_bot_tok_try=-999

# Current git state: branch ("HEAD" when detached), inside a work tree, merge in progress.
_dojo_bot_git_state() {
  local gd
  if gd=$(command git rev-parse --git-dir 2>/dev/null); then
    _dojo_bot_in_repo=1
    _dojo_bot_branch=$(command git symbolic-ref --short -q HEAD 2>/dev/null) || _dojo_bot_branch=HEAD
    if [ -f "$gd/MERGE_HEAD" ]; then _dojo_bot_merging=1; else _dojo_bot_merging=0; fi
  else
    _dojo_bot_in_repo=0 _dojo_bot_branch='' _dojo_bot_merging=0
  fi
}

# 0 when ~/.git-credentials holds a working token for this bot; makes one if not (at most
# every 30 s: Forgejo's bootstrap may not have created the bot's account yet). A --fast bot
# tries on every command: it can finish a whole round inside those 30 s.
_dojo_bot_token() {
  [ "$_dojo_bot_tok_ok" = 1 ] && return 0
  [ "${BOT_FAST:-0}" = 1 ] || [ $(( SECONDS - _dojo_bot_tok_try )) -ge 30 ] || return 1
  _dojo_bot_tok_try=$SECONDS
  local api="http://$_dojo_bot_host/api/v1" netrc="${NETRC:-$HOME/.dojo-bot-netrc}" tok
  tok=$(sed -n "s|^http://[^:]*:\(.*\)@$_dojo_bot_host\$|\1|p" "$HOME/.git-credentials" 2>/dev/null | head -1)
  if [ -n "$tok" ] && [ "$(curl -s -o /dev/null -w '%{http_code}' -K - "$api/user" <<<"header = \"Authorization: token $tok\"")" = 200 ]; then
    _dojo_bot_tok_ok=1; return 0
  fi
  [ -r "$netrc" ] || return 1
  curl -s -o /dev/null --netrc-file "$netrc" -X DELETE "$api/users/$BOT_USER/tokens/dojo-git"
  tok=$(curl -s --netrc-file "$netrc" -H 'Content-Type: application/json' \
    -d '{"name":"dojo-git","scopes":["write:repository","write:issue","read:user"]}' \
    "$api/users/$BOT_USER/tokens" | sed -n 's/.*"sha1":"\([0-9a-f]*\)".*/\1/p')
  [ -n "$tok" ] || return 1
  (umask 077; printf 'http://%s:%s@%s\n' "$BOT_USER" "$tok" "$_dojo_bot_host" > "$HOME/.git-credentials")
  _dojo_bot_tok_ok=1
}

# "history_size cursor_y" of this tmux pane (the bots run inside one): with it, a line's absolute number
# is their sum, so the lines a command printed can be read back, as dojo-achievements.zsh does.
_dojo_bot_pane_pos() { command tmux display-message -p '#{history_size} #{cursor_y}' 2>/dev/null; }
_dojo_bot_out_from=''

# For bot-runner.sh's --fast start: 0 once this bot has its token and the service answers, so no command of
# the round is lost.
bot_ready() {
  _dojo_bot_token && curl -s -o /dev/null -m 3 "${ACHIEVEMENTS_URL:-http://achievements:8080}/healthz"
}

bot_cmd_pre() {
  _dojo_bot_git_state
  _dojo_bot_out_from=''
  [ -n "${TMUX:-}" ] && _dojo_bot_out_from=$(_dojo_bot_pane_pos)
}

bot_cmd_post() { # <command> <exit code>
  local cmd=$1 rc=$2 in_repo=$_dojo_bot_in_repo merging=$_dojo_bot_merging before=$_dojo_bot_branch
  _dojo_bot_git_state
  [ -n "${cmd//[[:space:]]/}" ] || return 0
  _dojo_bot_token || return 0
  local out='' a b
  if [ -n "$_dojo_bot_out_from" ] && [ -n "${TMUX:-}" ]; then
    read -r -a a <<<"$_dojo_bot_out_from"
    read -r -a b <<<"$(_dojo_bot_pane_pos)"
    if [ "${#a[@]}" = 2 ] && [ "${#b[@]}" = 2 ]; then
      local first=$(( a[0] + a[1] - b[0] )) last=$(( b[1] - 1 ))
      [ "$last" -ge "$first" ] && out=$(command tmux capture-pane -p -J -S "$first" -E "$last" 2>/dev/null | tail -n 40 | tail -c 4000)
    fi
  fi
  _dojo_bot_out_from=''
  DOJO_SH_OUT=$out DOJO_SH_CMD=${cmd:0:2000} DOJO_SH_EXIT=$rc DOJO_SH_IN_REPO=$in_repo DOJO_SH_MERGING=$merging \
  DOJO_SH_BRANCH_BEFORE=$before DOJO_SH_BRANCH=$_dojo_bot_branch DOJO_SH_MERGING_AFTER=$_dojo_bot_merging \
    /usr/local/bin/dojo-check --shell </dev/null >/dev/null 2>&1 &
  disown $! 2>/dev/null
  # The service drops a user's shell events past 40 per 10 s (store.py's shell_rate); a --fast bot has no pacing
  # of its own to stay under that.
  [ "${BOT_FAST:-0}" = 1 ] && sleep 0.3
  return 0
}
