#!/bin/sh
# Add a `dojo` shell function to your shell profile, so `dojo <workshop>`,
# `dojo stop`, etc. work from any directory. Safe to re-run: the function sits
# between marker lines and is replaced in place, never duplicated.
#
# Target file: zsh -> ~/.zshrc_aliases if it exists, else ~/.zshrc;
#              bash (or anything else) -> ~/.bash_aliases if it exists, else ~/.bashrc.
# The shell is taken from $SHELL (your login shell).
#
# A script can't change the shell that launched it, so it cannot `source` the
# file for you; it prints the one line to run (or `exec $SHELL` for a fresh one).
set -eu

case "${1:-}" in
  -h | --help)
    sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'
    exit 0 ;;
  '') ;;
  *)
    echo "Unrecognized argument: ${1} ('alias-setup' takes no options)" >&2
    exit 1 ;;
esac

root="$(cd "$(dirname "$0")/../.." && pwd)"
if [ ! -f "${root}/run.sh" ]; then
  echo "Cannot find ${root}/run.sh" >&2
  exit 1
fi

case "$(basename "${SHELL:-}")" in
  zsh)
    if [ -f "$HOME/.zshrc_aliases" ]; then target="$HOME/.zshrc_aliases"; else target="$HOME/.zshrc"; fi
    rc="$HOME/.zshrc" ;;
  *)
    if [ -f "$HOME/.bash_aliases" ]; then target="$HOME/.bash_aliases"; else target="$HOME/.bashrc"; fi
    rc="$HOME/.bashrc" ;;
esac

begin='# >>> dojo alias (./run.sh alias-setup) >>>'
end='# <<< dojo alias <<<'

block="${begin}
dojo() {
    if [ -x '${root}/run.sh' ]; then
        '${root}/run.sh' \"\$@\"
    else
        echo \"Error: ${root}/run.sh not found (was the repo moved? re-run ./run.sh alias-setup)\" >&2
        return 1
    fi
}
${end}"

touch "$target"
if grep -qF "$begin" "$target"; then
  tmp="$(mktemp)"
  awk -v b="$begin" -v e="$end" '
    $0 == b { skip = 1 }
    !skip { print }
    $0 == e { skip = 0 }' "$target" > "$tmp"
  cat "$tmp" > "$target"
  rm -f "$tmp"
  action="Updated"
else
  action="Added"
fi
# Keep a blank line between the existing content and the block.
if [ -s "$target" ] && [ -n "$(tail -c1 "$target")" ]; then echo >> "$target"; fi
printf '%s\n' "$block" >> "$target"

echo "${action} the 'dojo' function in ${target} (runs ${root}/run.sh)."
if [ "$target" != "$rc" ]; then
  echo "Note: ${target} only takes effect if ${rc} sources it."
fi
echo
echo "Load it into this terminal with:"
echo "  source ${target}"
