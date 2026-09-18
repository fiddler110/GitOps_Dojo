# Bash tab-completion for engine/run.sh.
#
# Usage:
#   type `./run.sh <TAB>` (from inside engine/) and it lists workshop names
#   plus `list`, `stop`, `teardown`; after a workshop name, <TAB> offers
#   `--test`.
#
# Install: source this file from your ~/.bashrc, e.g.
#   source /path/to/GitOps_Dojo/engine/completions/run.sh.bash
#
# (engine/scripts/install-completion.sh does this for you on first run of
# ./run.sh, with confirmation.)
#
# This mirrors run.sh's own workshop-discovery logic (workshops/*/workshop.env
# next to engine/), so it stays correct as workshops are added or removed —
# nothing here needs to be updated by hand.

_run_sh_complete() {
  local cur prev engine_dir workshops_dir opts d

  COMPREPLY=()
  cur="${COMP_WORDS[COMP_CWORD]}"
  prev="${COMP_WORDS[COMP_CWORD - 1]}"

  # Resolve engine_dir from this completion script's own path (not $PWD),
  # so completion works no matter which directory you're typing ./run.sh
  # from -- same trick the zsh version uses.
  engine_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  workshops_dir="${engine_dir}/../workshops"

  if [ "$COMP_CWORD" -eq 1 ]; then
    opts="list stop teardown"
    if [ -d "$workshops_dir" ]; then
      for d in "$workshops_dir"/*/; do
        [ -f "${d}workshop.env" ] || continue
        opts="$opts $(basename "$d")"
      done
    fi
    COMPREPLY=($(compgen -W "$opts" -- "$cur"))
    return 0
  fi

  if [ "$COMP_CWORD" -eq 2 ]; then
    case "$prev" in
      list | stop | teardown) ;;
      *) COMPREPLY=($(compgen -W "--test" -- "$cur")) ;;
    esac
  fi
}

complete -F _run_sh_complete run.sh
complete -F _run_sh_complete ./run.sh
