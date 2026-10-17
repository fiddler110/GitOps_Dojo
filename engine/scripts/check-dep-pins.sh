#!/bin/sh
# Fails when the same Python package is pinned to two different versions in two
# places. The range alone carries one Flask pin per target plus a copy in every
# seeded student repo and one inline in ctf-checker's Dockerfile - 18 copies of
# the same `==` - and a bump applied to some of them is drift nothing else
# catches: each image builds on its own, so every version "works", and the lab
# quietly stops running the code the student patched. Same reasoning as
# check-tool-pins.sh (RV25), which only ever reads `ARG <TOOL>_VERSION` lines
# and so cannot see any of these.
#
# Usage: engine/scripts/check-dep-pins.sh [DIR...]  (default: engine modules workshops)
# `./dojo <workshop> --dry-run` runs it on the whole repo, as CI does.
#
# Where it looks: every requirements*.txt, and `name==version` tokens on a
# Dockerfile's `pip install` line (following its `\` continuations), since a
# pin written straight into a RUN is the easiest copy to forget. Package names
# are compared the way pip compares them (PEP 503: lowercase, runs of -_.
# folded to a single -), so Flask and flask are one package, not two.
# A package only one file pins is never reported - there is nothing for it to
# drift from.
#
# engine/dojo/requirements.lock is deliberately NOT read (hence requirements*.txt,
# not requirements*): it pins the dojo CLI's own wheels, which run on the host out
# of engine/.cache/pylib-*, and it already disagrees with the targets on click
# (8.1.8 there, 8.5.0 in every target). That is correct - the CLI's click and an
# in-container app's click are unrelated - so do not "fix" it by widening the glob.
set -eu

root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
[ "$#" -gt 0 ] || set -- engine modules workshops

files="$(find "$@" \( -name node_modules -o -name .generated -o -name .cache \) -prune -o -type f \
  \( -name 'requirements*.txt' -o -name 'Dockerfile*' \) -print | sort)"
[ -n "$files" ] || { echo "check-dep-pins: nothing to read under $*"; exit 0; }

# One record per pin, tab separated: package, version, file.
# shellcheck disable=SC2086
awk '
  function norm(n) {                       # PEP 503 name normalisation
    n = tolower(n)
    gsub(/[-_.]+/, "-", n)
    return n
  }
  function emit(line, file) {
    rest = line
    while (match(rest, /[A-Za-z0-9][A-Za-z0-9._-]*==[0-9][^ \t"'\'',;\\]*/)) {
      hit = substr(rest, RSTART, RLENGTH)
      rest = substr(rest, RSTART + RLENGTH)
      eq = index(hit, "==")
      print norm(substr(hit, 1, eq - 1)) "\t" substr(hit, eq + 2) "\t" file
    }
  }
  FNR == 1 { in_pip = 0 }
  {
    line = $0
    sub(/\r$/, "", line)
  }
  FILENAME ~ /requirements[^\/]*\.txt$/ {
    sub(/[ \t]*#.*$/, "", line)            # trailing comment
    if (line ~ /^[ \t]*#/ || line ~ /^[ \t]*$/) next
    emit(line, FILENAME)
    next
  }
  # A Dockerfile: only pins on a pip install line (and its continuations).
  {
    if (line ~ /^[ \t]*#/) next
    if (line ~ /pip[0-9.]*[ \t]+install/) in_pip = 1
    if (in_pip) emit(line, FILENAME)
    if (line !~ /\\[ \t]*$/) in_pip = 0
  }
' $files | sort -u | awk -F'\t' '
  {
    if (!(($1 SUBSEP $3) in seen_file)) { seen_file[$1, $3] = 1; nfiles[$1]++ }
    if (!(($1 SUBSEP $2) in seen_val))  { seen_val[$1, $2] = 1;  nvals[$1]++ }
    if (!($1 in order)) { order[$1] = ++n; pkgs[n] = $1 }
    where[$1, $2] = where[$1, $2] (where[$1, $2] ? ", " : "") $3
  }
  END {
    bad = 0
    for (i = 1; i <= n; i++) {
      p = pkgs[i]
      if (nfiles[p] < 2) continue          # one file pins it: nothing to drift from
      shared++
      if (nvals[p] > 1) {
        printf "pin drift: %s is pinned to %d different versions:\n", p, nvals[p] > "/dev/stderr"
        for (k in seen_val) {
          split(k, q, SUBSEP)
          if (q[1] == p) printf "  %s in %s\n", q[2], where[p, q[2]] > "/dev/stderr"
        }
        bad = 1
      }
    }
    if (bad) {
      print "check-dep-pins: bump every copy of a shared pin together." > "/dev/stderr"
      exit 1
    }
    printf "check-dep-pins: %d shared package pin(s) agree across their files.\n", shared
  }
'
