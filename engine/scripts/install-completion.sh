#!/bin/sh
# One-time, interactive offer to wire up ./run.sh tab-completion for the
# caller's shell. run.sh calls this itself on every invocation; it no-ops
# instantly once a decision has been recorded (accepted, declined, or
# "don't know this shell"), so it only ever prompts once per machine.
#
# Detection: $SHELL is the user's *login* shell, which is what actually
# reads ~/.bashrc / ~/.zshrc on the next login -- it's the right thing to
# key off of even if run.sh itself happens to be running under sh right now.
set -eu

cd "$(dirname "$0")/.." # -> engine/
engine_dir="$(pwd)"
state_file=".build-state/.completion-checked"

[ -f "$state_file" ] && exit 0

# Only prompt in an interactive terminal -- never block CI, --test bot
# runs, or any other non-interactive invocation of run.sh.
if [ ! -t 0 ] || [ ! -t 1 ]; then
  exit 0
fi

mkdir -p .build-state
shell_name="$(basename "${SHELL:-}")"

case "$shell_name" in
  zsh)
    rc_file="${ZDOTDIR:-$HOME}/.zshrc"
    completion_file="${engine_dir}/completions/run.sh.zsh"
    ;;
  bash)
    # macOS's default Terminal.app starts a login shell and only reads
    # .bash_profile, not .bashrc; everywhere else .bashrc is the one read
    # on interactive, non-login shells (the common case). .bashrc is the
    # right default -- if a user's setup doesn't source it, they'll see
    # that immediately and can adjust by hand.
    rc_file="$HOME/.bashrc"
    completion_file="${engine_dir}/completions/run.sh.bash"
    ;;
  *)
    echo "Tab-completion for ./run.sh is available, but this doesn't know how to install it for \$SHELL ($shell_name)."
    echo "See engine/completions/ and source the matching file from your shell's startup config by hand."
    echo "$shell_name (unrecognized, skipped)" >"$state_file"
    exit 0
    ;;
esac

if [ ! -f "$completion_file" ]; then
  echo "not-found" >"$state_file"
  exit 0
fi

marker="# GitOps Dojo: ./run.sh tab-completion"
if [ -f "$rc_file" ] && grep -qF "$marker" "$rc_file" 2>/dev/null; then
  echo "already-installed" >"$state_file"
  exit 0
fi

echo
echo "Tab-completion is available for ./run.sh ($shell_name detected)."
echo "This would add these two lines to ${rc_file}:"
echo
echo "  ${marker}"
echo "  source \"${completion_file}\""
echo
printf 'Add it now? [y/N] '
# shellcheck disable=SC2039
read -r answer || answer=""
case "$answer" in
  y | Y | yes | Yes)
    {
      echo ""
      echo "$marker"
      echo "source \"${completion_file}\""
    } >>"$rc_file"
    echo "Added. Run 'source ${rc_file}', or open a new shell, to start using it."
    echo "accepted" >"$state_file"
    ;;
  *)
    echo "Skipped. Source ${completion_file} from your shell config any time to turn it on."
    echo "declined" >"$state_file"
    ;;
esac
