#!/bin/sh
# Refresh content/sample-repos/<target>/ (and content/sample-repo/, the engine's master seed, which is
# the customer-portal copy) from modules/ctf-range/targets/<target>/. Run after a target changes.
# Student repos get app source only: no exploit script, no SAST. README.defend.md (the target's
# student-facing README) becomes README.md when the target ships one.
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
t_root="$here/../../../modules/ctf-range/targets"
copy() { # target files...
  t="$1"; shift
  dst="$here/sample-repos/$t"; rm -rf "$dst"; mkdir -p "$dst"
  for f in "$@"; do [ -f "$t_root/$t/$f" ] && cp "$t_root/$t/$f" "$dst/$f"; done
  [ -f "$t_root/$t/README.defend.md" ] && cp "$t_root/$t/README.defend.md" "$dst/README.md"
  [ -f "$dst/README.md" ] || cp "$here/sample-repos/_fallback/$t.README.md" "$dst/README.md"
}
copy customer-portal app.py seed.py entrypoint.sh Dockerfile requirements.txt
copy policy-bypass   app.py policy_engine.py Dockerfile requirements.txt
copy leaky-config    app.py Dockerfile requirements.txt
rm -rf "$here/sample-repo"; cp -R "$here/sample-repos/customer-portal" "$here/sample-repo"
cp -R "$here/sample-repos/_common/." "$here/sample-repo/"
echo "synced"
