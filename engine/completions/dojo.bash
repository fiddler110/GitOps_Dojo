# Bash tab-completion for ./dojo (repo root or engine/) and the `dojo`
# command from `./dojo alias-setup` (~/.local/bin/dojo).
#
# Everything it offers comes from the dojo CLI's own definitions (Click's
# completion protocol): commands, workshop names, each command's options, the
# profile NAME files for --env, and the running stack's services for
# `restart` and `logs`. Nothing here needs updating when commands, workshops
# or options change.
#
# Install: source this file from ~/.bashrc (./dojo alias-setup, or the
# first-run offer, does it for you).

# This file's engine/, resolved once at source time (a relative path inside
# the function would be re-resolved against wherever you've since cd'd to).
_dojo_engine_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

_dojo_complete() {
  local IFS=$'\n' response completion type value
  response=$(env COMP_WORDS="${COMP_WORDS[*]}" COMP_CWORD="$COMP_CWORD" _DOJO_COMPLETE=bash_complete \
    python3 -B "${_dojo_engine_dir}/dojo/boot.py" 2>/dev/null)
  COMPREPLY=()
  for completion in $response; do
    IFS=',' read -r type value <<< "$completion"
    case "$type" in
      dir) compopt -o dirnames 2>/dev/null ;;
      file) compopt -o default 2>/dev/null ;;
      plain) COMPREPLY+=("$value") ;;
    esac
  done
  return 0
}

# -o nosort keeps the CLI's order (bash 4.4+); older bash (macOS's 3.2) sorts.
complete -o nosort -F _dojo_complete dojo ./dojo ../dojo 2>/dev/null \
  || complete -F _dojo_complete dojo ./dojo ../dojo
