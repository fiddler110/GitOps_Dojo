#!/bin/sh
# Repo lint (P13): code-fence language tags, retired student command names,
# pin checks and the Caddy header rules. No containers. Runs locally too:
#   sh .github/scripts/lint-repo.sh
set -u
root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root" || exit 1
failed=""
step() { name="$1"; shift; echo "==> $name"; if "$@"; then :; else failed="$failed $name"; fi; }

# 1. Every opening ``` fence in a lab or slide names a language (text for output).
fence_tags() {
  git ls-files 'workshops/*/content/*.md' 'workshops/*/content/**/*.md' 'modules/*/*.md' 'modules/*/**/*.md' \
    | grep -v '/sample-repo' | sort -u | while read -r f; do
    awk -v f="$f" '
      /^[ \t]*(```|~~~)/ {
        if (open) { open = 0; next }
        open = 1
        t = $0; sub(/^[ \t]*(```|~~~)+/, "", t)
        if (t ~ /^[ \t]*$/) { printf "%s:%d: code fence with no language\n", f, NR; bad = 1 }
      }
      END { exit bad }' "$f" || echo x
    done | grep -v '^x$' | tee /dev/stderr | { ! grep -q . ; }
}

# 2. Retired student commands used as bare commands in labs, slides and bots (the modules' own
#    terminal scripts legitimately implement them) (the `dojo <sub>` form replaced them).
old_names() {
  hits="$(git ls-files 'workshops/*/content' 'workshops/*/bots' 'workshops/*/achievements' \
      | grep -Ev '(^|/)(cmd\.d|archive|tests?)/|\.py$|/README\.md$|\.json$' \
      | xargs grep -nE '(^|[`$(|;&[:space:]])(dojo-check|dojo-challenge|lab-prep)([[:space:]`]|$)|(^|[`$(|;&])[[:space:]]*(\$ )?sensei ([a-z-]+|-)' 2>/dev/null)"
  [ -z "$hits" ] || { echo "$hits"; echo "use 'dojo check|challenge|prep|sensei ...' instead"; return 1; }
}

# 3. Image/tool/dependency pins agree.
pins() {
  rc=0
  for s in workshops/*/check-pins-sync.sh; do [ -f "$s" ] && { sh "$s" || rc=1; }; done
  for s in check-pins check-tool-pins check-dep-pins; do sh "engine/scripts/$s.sh" || rc=1; done
  return $rc
}

step "fence tags" fence_tags
step "retired command names" old_names
step "pin sync" pins
step "caddy headers" python3 -B .github/scripts/caddy-lint.py

if [ -n "$failed" ]; then echo "LINT FAILED:$failed" >&2; exit 1; fi
echo "Repo lint passed."
