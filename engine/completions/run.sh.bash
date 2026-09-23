# Bash tab-completion for run.sh -- both the repo-root ./run.sh (a thin
# forwarder) and engine/run.sh, which take identical arguments.
#
# Usage:
#   type `./run.sh <TAB>` (from the repo root or engine/) and it lists
#   workshop names plus `setup`, `capacity`, `list`, `stop`, `teardown`,
#   `help`. After a workshop name, <TAB> offers `--test`/`--dry-run`; after
#   `setup`, `--default`/`--force`; after `stop`, `--dry-run`; after
#   `capacity`, its sizing flags.
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

# Resolve engine_dir from this completion script's own path (not $PWD),
# so completion works no matter which directory you're typing ./run.sh
# from -- same trick the zsh version uses. Done once, at source time: inside
# the function, a relative `source` path would be re-resolved against
# whatever directory you've since cd'd to.
_run_sh_engine_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

_run_sh_complete() {
  local cur workshops_dir opts d capacity_opts
  capacity_opts="--students --heap-mb --margin-pct --host-mem-mb --procs-per-student --reserve-mb --other-services-mb --help"

  COMPREPLY=()
  cur="${COMP_WORDS[COMP_CWORD]}"

  workshops_dir="${_run_sh_engine_dir}/../workshops"

  if [ "$COMP_CWORD" -eq 1 ]; then
    opts="setup capacity list stop teardown help --help"
    if [ -d "$workshops_dir" ]; then
      for d in "$workshops_dir"/*/; do
        [ -f "${d}workshop.env" ] || continue
        opts="$opts $(basename "$d")"
      done
    fi
    COMPREPLY=($(compgen -W "$opts" -- "$cur"))
    return 0
  fi

  # Options depend on the first word (command or workshop name), at any
  # later position -- so `./run.sh <workshop> --test --dry-run` completes too.
  case "${COMP_WORDS[1]}" in
    list | help | --help) ;;
    stop | teardown) COMPREPLY=($(compgen -W "--dry-run --help" -- "$cur")) ;;
    setup | --setup) COMPREPLY=($(compgen -W "--default --force --help" -- "$cur")) ;;
    capacity | --capacity) COMPREPLY=($(compgen -W "$capacity_opts" -- "$cur")) ;;
    *)
      # Don't offer an option that is already on the line.
      local o w remaining=""
      for o in --test --dry-run --help; do
        for w in "${COMP_WORDS[@]:2:COMP_CWORD-2}"; do
          [ "$w" = "$o" ] && continue 2
        done
        remaining="$remaining $o"
      done
      COMPREPLY=($(compgen -W "$remaining" -- "$cur")) ;;
  esac
}

# Bash can't register a pattern, so list the relative forms you'd actually
# type: from the repo root (./run.sh, ./engine/run.sh) or from engine/
# (./run.sh, ../run.sh).
complete -F _run_sh_complete run.sh ./run.sh ../run.sh engine/run.sh ./engine/run.sh
