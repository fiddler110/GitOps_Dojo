# Zsh tab-completion for ./run.sh (repo root or engine/) and the `dojo`
# command from `./run.sh alias-setup` (~/.local/bin/dojo).
#
# Everything it offers comes from the dojo CLI's own definitions (Click's
# completion protocol), with descriptions: commands, workshop names, each
# command's options, the profile NAME files for --env, and the running
# stack's services for `restart` and `logs`. Nothing here needs updating when
# commands, workshops or options change.
#
# Install: source this file from ~/.zshrc after compinit (./run.sh alias-setup,
# or the first-run offer, does it for you).

# This file's engine/, resolved once at source time.
_run_sh_engine_dir="${${(%):-%x}:A:h:h}"

_run_sh() {
  local -a completions completions_with_descriptions response
  local type key descr
  response=("${(@f)$(env COMP_WORDS="${words[*]}" COMP_CWORD=$((CURRENT - 1)) _DOJO_COMPLETE=zsh_complete \
    python3 -B "${_run_sh_engine_dir}/dojo/boot.py" 2>/dev/null)}")
  for type key descr in ${response}; do
    if [[ "$type" == "plain" ]]; then
      if [[ "$descr" == "_" ]]; then
        completions+=("$key")
      else
        completions_with_descriptions+=("${key//:/\\:}:$descr")
      fi
    elif [[ "$type" == "dir" ]]; then
      _path_files -/
    elif [[ "$type" == "file" ]]; then
      _path_files -f
    fi
  done
  [ -n "$completions_with_descriptions" ] && _describe -V unsorted completions_with_descriptions -U
  [ -n "$completions" ] && compadd -U -V unsorted -a completions
  return 0
}

compdef _run_sh run.sh ./run.sh ../run.sh engine/run.sh ./engine/run.sh dojo
