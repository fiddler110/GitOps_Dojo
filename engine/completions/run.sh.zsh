# Zsh tab-completion for engine/run.sh.
#
# Usage:
#   type `./run.sh <TAB>` (from inside engine/) and it lists workshop names
#   plus `list`, same as `./run.sh list` would show.
#
# Install: source this file from your ~/.zshrc, e.g.
#   source /Users/Scott.MacLeod/Architecture/repos/GitOps_Dojo/engine/completions/run.sh.zsh
#
# This mirrors run.sh's own workshop-discovery logic (workshops/*/workshop.env
# next to engine/), so it stays correct as workshops are added or removed —
# nothing here needs to be updated by hand.

_run_sh() {
  local self_dir engine_dir workshops_dir
  self_dir="${${(%):-%x}:A:h}"
  engine_dir="${self_dir:h}"
  workshops_dir="${engine_dir}/../workshops"

  local -a entries
  entries=("list:show available workshops")

  local d name title
  if [ -d "$workshops_dir" ]; then
    for d in "$workshops_dir"/*/; do
      [ -f "${d}workshop.env" ] || continue
      name="$(basename "$d")"
      title="$(sed -n 's/^WORKSHOP_NAME=//p' "${d}workshop.env" | head -1 | tr -d '"')"
      entries+=("${name}:${title:-workshop}")
    done
  fi

  _describe 'workshop' entries
}

compdef _run_sh run.sh
