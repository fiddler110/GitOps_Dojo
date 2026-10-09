#!/bin/sh
# Install the `dojo` command: a small script in ~/.local/bin that runs this
# repo's ./dojo, so `dojo <workshop>`, `dojo stop`, etc. work from any
# directory, in any shell and from scripts. It also adds one block to your
# shell profile that loads the tab completion (completions/dojo.zsh or
# .bash, for both `dojo` and ./dojo) and, only if ~/.local/bin isn't on your
# PATH, adds it. Safe to re-run: the block sits between marker lines and is
# replaced in place; the older `dojo` function block and the first-run
# completion lines are removed, so nothing is loaded twice.
#
# Profile: zsh -> ~/.zshrc_aliases if it exists, else ~/.zshrc;
#          bash (or anything else) -> ~/.bash_aliases if it exists, else ~/.bashrc.
# The shell is taken from $SHELL (your login shell).
#
#   --check    exit 0 if `dojo` is installed for this repo, 1 if not (no output)
#   --remove   remove the `dojo` command and the profile block
set -eu

root="$(cd "$(dirname "$0")/../.." && pwd)"
bindir="$HOME/.local/bin"
shim="${bindir}/dojo"
stamp="# Written by ./dojo alias-setup"
begin='# >>> dojo (./dojo alias-setup) >>>'
end='# <<< dojo <<<'

ours() { [ -f "$shim" ] && { grep -qF "$stamp" "$shim" || grep -qF "# Written by ./run.sh alias-setup" "$shim"; }; }

case "${1:-}" in
  -h | --help)
    sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
    exit 0 ;;
  --check)
    ours && grep -qF "root='${root}'" "$shim"
    exit ;;
  '' | --remove) ;;
  *)
    echo "Unrecognized argument: ${1} (alias-setup takes --check or --remove)" >&2
    exit 1 ;;
esac

if [ ! -f "${root}/dojo" ]; then
  echo "Cannot find ${root}/dojo" >&2
  exit 1
fi

case "$(basename "${SHELL:-}")" in
  zsh)
    if [ -f "$HOME/.zshrc_aliases" ]; then target="$HOME/.zshrc_aliases"; else target="$HOME/.zshrc"; fi
    rc="${ZDOTDIR:-$HOME}/.zshrc"
    comp="${root}/engine/completions/dojo.zsh" ;;
  *)
    if [ -f "$HOME/.bash_aliases" ]; then target="$HOME/.bash_aliases"; else target="$HOME/.bashrc"; fi
    rc="$HOME/.bashrc"
    comp="${root}/engine/completions/dojo.bash" ;;
esac
[ -f "$comp" ] || comp=""

# Drop every block this script (or an older version, or the first-run
# completion offer) wrote, from both the profile and the rc file.
strip() {
  [ -f "$1" ] || return 0
  tmp="$(mktemp)"
  awk -v b="$begin" -v e="$end" '
    $0 == b || $0 == "# >>> dojo (./run.sh alias-setup) >>>" || $0 == "# >>> dojo alias (./run.sh alias-setup) >>>" { skip = 1 }
    $0 == "# GitOps Dojo: ./run.sh tab-completion" { drop_next = 1; next }
    drop_next { drop_next = 0; if ($0 ~ /completions\/(run\.sh|dojo)\.(zsh|bash)"?$/) next }
    !skip { print }
    $0 == e || $0 == "# <<< dojo alias <<<" || $0 == "# <<< dojo <<<" { skip = 0 }' "$1" > "$tmp"
  if ! cmp -s "$tmp" "$1"; then cat "$tmp" > "$1"; fi
  rm -f "$tmp"
}

if [ -e "$shim" ] && ! ours; then
  echo "${shim} exists and isn't one this script wrote; leaving it. Remove or rename it, then re-run." >&2
  exit 1
fi

if [ "${1:-}" = "--remove" ]; then
  rm -f "$shim"
  strip "$target"
  [ "$rc" = "$target" ] || strip "$rc"
  echo "Removed ${shim} and the dojo block in ${target}. Open a new terminal to drop it from this one."
  exit 0
fi

mkdir -p "$bindir"
q_root="$(printf '%s' "$root" | sed "s/'/'\\\\''/g")"
cat > "$shim" <<EOF
#!/bin/sh
${stamp}; re-run it if the repo moves.
root='${q_root}'
if [ ! -x "\$root/dojo" ]; then
  echo "dojo: \$root/dojo not found (was the repo moved? run ./dojo alias-setup in its new place)" >&2
  exit 1
fi
DOJO_PROG=dojo exec "\$root/dojo" "\$@"
EOF
chmod 755 "$shim"

block="$begin"
case ":${PATH}:" in
  *":${bindir}:"*) ;;
  *) block="${block}
case \":\$PATH:\" in *\":\$HOME/.local/bin:\"*) ;; *) PATH=\"\$HOME/.local/bin:\$PATH\"; export PATH ;; esac" ;;
esac
if [ -n "$comp" ] && [ "${comp%.bash}" != "$comp" ]; then
  block="${block}
if [ -f '${comp}' ]; then
    . '${comp}'    # tab completion for dojo and ./dojo
fi"
elif [ -n "$comp" ]; then
  # Completion needs compinit before the compdef inside the file runs; load it if the profile hasn't yet.
  block="${block}
if [ -f '${comp}' ]; then
    (( \$+functions[compdef] )) || { autoload -Uz compinit && compinit; }
    source '${comp}'    # tab completion for dojo and ./dojo
fi"
fi
block="${block}
${end}"

touch "$target"
strip "$target"
[ "$rc" = "$target" ] || strip "$rc"
# Keep a blank line between the existing content and the block.
if [ -s "$target" ] && [ -n "$(tail -c1 "$target")" ]; then echo >> "$target"; fi
printf '%s\n' "$block" >> "$target"

# Any other line that loads a dojo completion file (another clone's, or one added by
# hand) would load it a second time, possibly from a different repo: point it out.
case "$(basename "${SHELL:-}")" in
  zsh) profiles="$HOME/.zshrc_aliases ${rc} $HOME/.zprofile" ;;
  *) profiles="$HOME/.bash_aliases ${rc} $HOME/.bash_profile $HOME/.profile" ;;
esac
others=""
for f in $profiles; do
  [ -f "$f" ] || continue
  found="$(awk -v b="$begin" -v e="$end" -v f="$f" '
    $0 == b { skip = 1 } !skip && /completions\/run\.sh\.(zsh|bash)/ { print "  " f ":" NR ": " $0 } $0 == e { skip = 0 }' "$f")"
  [ -n "$found" ] && others="${others}${found}
"
done

echo "Installed ${shim} (runs ${root}/dojo)."
if [ -n "$others" ]; then
  echo "Warning: these lines also load a dojo completion file, so it may load twice (remove them if they're stale):"
  printf '%s' "$others"
fi
if [ -n "$comp" ]; then
  echo "${target} loads tab completion for 'dojo' and ./dojo."
else
  echo "No tab completion for ${SHELL:-your shell} (bash and zsh only)."
fi
case ":${PATH}:" in
  *":${bindir}:"*) ;;
  *) echo "${target} also puts ${bindir} on your PATH." ;;
esac
if [ "$target" != "$rc" ]; then
  echo "Note: ${target} only takes effect if ${rc} sources it."
fi
echo
echo "Open a new terminal (or run: exec \$SHELL) to start using it."
