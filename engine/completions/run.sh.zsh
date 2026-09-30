# Zsh tab-completion for run.sh -- both the repo-root ./run.sh (a thin
# forwarder) and engine/run.sh, which take identical arguments.
#
# Usage:
#   type `./run.sh <TAB>` (from the repo root or engine/) and it lists
#   workshop names plus `setup`, `capacity`, `list`, `modules`, `stop`,
#   `teardown`, `help`. After a workshop name, <TAB> offers `--test`/`--dry-run`; after
#   `setup`, `--default`/`--force`; after `stop`, `--dry-run`; after
#   `capacity`, its sizing flags.
#
# Install: source this file from your ~/.zshrc, e.g.
#   source /path/to/GitOps_Dojo/engine/completions/run.sh.zsh
#
# (engine/scripts/install-completion.sh does this for you on first run of
# ./run.sh, with confirmation.)
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
  entries=(
    "setup:create engine/.env (interactive, or --default)"
    "capacity:size the terminal resource limits for this machine"
    "help:show usage (also: ./run.sh <command> --help)"
    "list:show available workshops"
    "modules:show available modules and which workshops use them"
    "stop:stop the stack, wipe all volumes"
    "teardown:same as stop"
  )

  local d name title
  if [ -d "$workshops_dir" ]; then
    for d in "$workshops_dir"/*/; do
      [ -f "${d}workshop.env" ] || continue
      name="$(basename "$d")"
      title="$(sed -n 's/^WORKSHOP_NAME=//p' "${d}workshop.env" | head -1 | tr -d '"')"
      entries+=("${name}:${title:-workshop}")
    done
  fi

  if [ "$CURRENT" -eq 2 ]; then
    _describe 'workshop' entries
  elif [ "$CURRENT" -ge 3 ]; then
    case "${words[2]}" in
      list | modules)
        _values 'option' '--help[show usage]' ;;
      help) ;;
      stop | teardown)
        _values 'option' \
          '--dry-run[list what would be removed, remove nothing]' \
          '--help[show help without tearing anything down]' ;;
      setup | --setup)
        _values 'option' \
          '--default[fixed lazy credentials, no prompts]' \
          '--force[overwrite an existing .env without asking]' \
          '--help[show help]' ;;
      capacity | --capacity)
        _values 'option' \
          '--students[number of concurrent students to size for]' \
          '--heap-mb[per-process code-server heap cap]' \
          '--margin-pct[extra headroom percentage]' \
          '--host-mem-mb[plan for a machine you have not provisioned yet]' \
          '--procs-per-student[node processes assumed per student]' \
          '--reserve-mb[host OS and daemon headroom]' \
          '--other-services-mb[combined mem_limits of the other services]' \
          '--help[show help]' ;;
      *)
        _values 'option' \
          '--test[also spin up demo/test bot students; optionally --test N for N bots (max 35)]' \
          '--env[also load engine/.env.NAME on top of engine/.env]' \
          '--dry-run[preview what would be rebuilt and started, change nothing]' \
          '--help[show help]' ;;
    esac
  fi
}

# The relative forms you'd actually type: from the repo root (./run.sh,
# ./engine/run.sh) or from engine/ (./run.sh, ../run.sh), and `dojo`, the
# function `./run.sh alias-setup` adds.
compdef _run_sh run.sh ./run.sh ../run.sh engine/run.sh ./engine/run.sh dojo
