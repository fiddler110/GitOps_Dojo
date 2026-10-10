# sensei module: tells the student, at their prompt, when the facilitator has answered a raised hand.
# `sensei notify` prints a banner once per reply and nothing otherwise. Two triggers:
#   - TRAPALRM: zsh runs it every $TMOUT seconds while the shell sits at an idle prompt (or mid-edit), so a reply
#     shows up within a few seconds with no Enter. The line being typed is redrawn under the banner.
#   - precmd: also checked after each command, for shells where the timer can't fire.
# A 1 s network timeout and no effect on exit status; nothing runs while a command is in the foreground.

[[ -o interactive && -x /usr/local/bin/sensei ]] || return 0

zmodload zsh/datetime 2>/dev/null
typeset -gi _sensei_last=0

_sensei_check() {
  _sensei_last=$EPOCHSECONDS
  local out
  out=$(/usr/local/bin/sensei notify </dev/null 2>/dev/null)
  [[ -n $out ]] || return 1
  if zle; then
    zle -I
    print -r -- "$out"
    zle reset-prompt
  else
    print -r -- "$out"
  fi
  return 0
}

TRAPALRM() { _sensei_check; }
typeset -gi TMOUT=3

_sensei_precmd() {
  local rc=$?
  (( EPOCHSECONDS - _sensei_last >= 3 )) && _sensei_check
  return $rc
}

precmd_functions=(${precmd_functions:#_sensei_precmd} _sensei_precmd)

# Zellij flavor: a watcher long-polls Sensei and opens each reply as a floating pane (`sensei watch`). One per
# student: the first pane's shell starts it, a pidfile keeps the rest from starting another.
if [[ -n $ZELLIJ ]]; then
  _sensei_pid=$HOME/.sensei-watch.pid
  if ! { [[ -r $_sensei_pid ]] && kill -0 "$(<$_sensei_pid)" 2>/dev/null; }; then
    ( nohup /usr/local/bin/sensei watch </dev/null >/dev/null 2>&1 & print -r -- $! > $_sensei_pid ) 2>/dev/null
  fi
  unset _sensei_pid
fi
