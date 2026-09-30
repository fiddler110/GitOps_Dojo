# achievements module: sourced from /etc/zsh/zshrc in interactive shells.
#
# 1. Shell events. preexec keeps the command about to run; precmd (before the next prompt)
#    sends it, its exit status, the git state before it (from the previous prompt) and after
#    it, to the achievements service through `dojo-check --shell`, in the background and
#    disowned, so the prompt never waits. Every command is sent; the service does the matching
#    and keeps none of the text. The fields travel in the environment of that one process
#    (readable only by this user), not on its command line where `ps` would show them.
# 2. The colour echo: new unlocks printed under the prompt (at most every 5 s).

[[ -o interactive && -x /usr/local/bin/dojo-check ]] || return 0

zmodload zsh/datetime 2>/dev/null
typeset -g _dojo_cmd=''
typeset -g _dojo_branch='' _dojo_in_repo=0 _dojo_merging=0
typeset -gi _dojo_ach_last=0

# Current git state: branch ("HEAD" when detached), inside a work tree, merge in progress.
_dojo_git_state() {
  local gd
  if gd=$(command git rev-parse --git-dir 2>/dev/null); then
    _dojo_in_repo=1
    _dojo_branch=$(command git symbolic-ref --short -q HEAD 2>/dev/null) || _dojo_branch=HEAD
    if [[ -f $gd/MERGE_HEAD ]]; then _dojo_merging=1; else _dojo_merging=0; fi
  else
    _dojo_in_repo=0 _dojo_branch='' _dojo_merging=0
  fi
}

_dojo_preexec() {
  # $3 is the full text about to run, aliases expanded; $1 is what was typed.
  _dojo_cmd=${3:-$1}
}

_dojo_precmd() {
  local rc=$?     # first line: the finished command's exit status
  local cmd=$_dojo_cmd in_repo=$_dojo_in_repo merging=$_dojo_merging before=$_dojo_branch
  _dojo_cmd=''
  _dojo_git_state
  if [[ -n ${cmd//[[:space:]]/} ]]; then
    DOJO_SH_CMD=${cmd[1,2000]} DOJO_SH_EXIT=$rc DOJO_SH_IN_REPO=$in_repo DOJO_SH_MERGING=$merging \
    DOJO_SH_BRANCH_BEFORE=$before DOJO_SH_BRANCH=$_dojo_branch DOJO_SH_MERGING_AFTER=$_dojo_merging \
      /usr/local/bin/dojo-check --shell </dev/null >/dev/null 2>&1 &!
  fi
  if (( EPOCHSECONDS - _dojo_ach_last >= 5 )); then
    _dojo_ach_last=$EPOCHSECONDS
    /usr/local/bin/dojo-check --echo 2>/dev/null
  fi
  return $rc
}

# First in the list, so $? is still the command's status when it runs.
precmd_functions=(_dojo_precmd ${precmd_functions:#_dojo_precmd})
preexec_functions=(${preexec_functions:#_dojo_preexec} _dojo_preexec)
