#!/bin/sh
# This pack's three seed repos are copies of the range's targets: a student
# clones content/sample-repos/<target>/ and patches it, while the live slot
# they attack is built from modules/ctf-range/targets/<target>/. The two must
# hold the same app, or a student's fix is written against code the lab is not
# running. content/sync-sample-repos.sh makes the copies and has to be run by
# hand after a target changes; this fails when that was forgotten.
#
# Dependency pins are NOT checked here: a `<pkg>==<version>` in any
# requirements.txt or `pip install` line is checked across the whole repo by
# engine/scripts/check-dep-pins.sh, which every `--dry-run` runs. This covers
# only what that cannot see - whole files copied out of modules/.
#
# Usage: workshops/ctf-defend/check-pins-sync.sh  (CI: .github/scripts/dry-runs.sh)
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
targets="$here/../../modules/ctf-range/targets"
seeds="$here/content/sample-repos"
rc=0

# Exactly what content/sync-sample-repos.sh copies, target by target. Keep the
# two lists together: a file added to the sync has to be added here too.
check() { # target file...
  t="$1"; shift
  for f in "$@"; do
    [ -f "$targets/$t/$f" ] || { echo "sync drift: $t has no $f to copy"; rc=1; continue; }
    cmp -s "$targets/$t/$f" "$seeds/$t/$f" \
      || { echo "sync drift: sample-repos/$t/$f differs from the target's (run content/sync-sample-repos.sh)"; rc=1; }
  done
  # The target's student-facing README is copied in under its plain name.
  if [ -f "$targets/$t/README.defend.md" ]; then
    cmp -s "$targets/$t/README.defend.md" "$seeds/$t/README.md" \
      || { echo "sync drift: sample-repos/$t/README.md differs from the target's README.defend.md"; rc=1; }
  fi
}

check customer-portal app.py seed.py entrypoint.sh Dockerfile requirements.txt
check policy-bypass   app.py policy_engine.py Dockerfile requirements.txt
check leaky-config    app.py Dockerfile requirements.txt

# content/sample-repo/ is the engine's master seed and a copy of the
# customer-portal one (plus _common/), so it drifts the same way.
for f in app.py seed.py entrypoint.sh Dockerfile requirements.txt README.md; do
  cmp -s "$seeds/customer-portal/$f" "$here/content/sample-repo/$f" \
    || { echo "sync drift: content/sample-repo/$f differs from sample-repos/customer-portal/$f"; rc=1; }
done

[ "$rc" = 0 ] && echo "ctf-defend: the three seed repos match modules/ctf-range/targets/"
exit "$rc"
