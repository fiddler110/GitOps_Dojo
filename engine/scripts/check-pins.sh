#!/bin/sh
# Fails when a Dockerfile FROM or a compose image: names an external image
# without a digest (remediation T1.5, FIND-18). A tag alone can be moved to
# different content by whoever controls the registry; tag@sha256:... can't.
# Keep the tag in front of the digest so a human can read what it is.
#
# Also fails when the same name:tag resolves to two different digests across
# files (RV25) - several Dockerfiles share a base image (python:3.12-slim in
# ctf-range alone), and a digest bumped in one copy but not the others is
# drift nothing else catches: each file still passes the no-digest check
# above, so the only way to see it is comparing copies against each other.
#
# Usage: engine/scripts/check-pins.sh [DIR...]   (default: engine modules workshops)
# `./run.sh <workshop> --dry-run` runs it on the whole repo.
#
# Not external, so skipped: this project's own images (gitopsdojo/*), images
# chosen by a variable (${BASE}, ${WEB_TERMINAL_IMAGE}; their defaults are
# gitopsdojo/* and run.sh builds them), `scratch`, and a FROM naming an
# earlier build stage.
set -eu

root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
[ "$#" -gt 0 ] || set -- engine modules workshops

bad=0
records="$(mktemp)"
trap 'rm -f "$records"' EXIT INT HUP TERM

files="$(find "$@" \( -name node_modules -o -name .generated \) -prune -o -type f \
  \( -name 'Dockerfile*' -o -name '*.yml' -o -name '*.yaml' \) -print | sort)"
for f in $files; do
  case "$f" in
    *Dockerfile*)
      # Stage names (FROM x AS name) are local, not images.
      out="$(awk '
        toupper($1) == "FROM" {
          img = ""; for (i = 2; i <= NF; i++) if ($i !~ /^--/) { img = $i; break }
          for (i = 2; i < NF; i++) if (toupper($i) == "AS") stage[$(i + 1)] = 1
          if (img == "" || img == "scratch" || img ~ /^\$/ || img ~ /^gitopsdojo\// || (img in stage)) next
          if (img !~ /@sha256:[0-9a-f]{64}$/) { print FILENAME ":" FNR ": " img; next }
          at = index(img, "@")
          print substr(img, 1, at - 1) "\t" substr(img, at + 1) "\t" FILENAME >> "'"$records"'"
        }' "$f")" ;;
    *)
      out="$(awk '
        $1 == "image:" {
          img = $2; gsub(/["'\'']/, "", img)
          if (img ~ /^\$/ || img ~ /^gitopsdojo\//) next
          if (img !~ /@sha256:[0-9a-f]{64}$/) { print FILENAME ":" FNR ": " img; next }
          at = index(img, "@")
          print substr(img, 1, at - 1) "\t" substr(img, at + 1) "\t" FILENAME >> "'"$records"'"
        }' "$f")" ;;
  esac
  if [ -n "$out" ]; then
    printf '%s\n' "$out" >&2
    bad=1
  fi
done

if [ "$bad" = "1" ]; then
  echo "check-pins: the images above have no digest. Pin them as name:tag@sha256:<index digest>" >&2
  echo "            (the registry's Docker-Content-Digest for the tag: the multi-arch index)." >&2
  exit 1
fi

# Drift check: the same name:tag must resolve to the same digest everywhere.
# One line per drifted name, so this reads the same shape as the no-digest
# failure above (N detail lines, then exactly 2 fixed lines) - start.py's
# dry-run strips the last 2 lines as the fixed follow-up message.
sort -u "$records" -o "$records"
drift="$(awk -F'\t' '
  { if (!(($1 SUBSEP $2) in seen)) { seen[$1, $2] = 1; where[$1] = where[$1] (where[$1] ? ", " : "") $2 " (" $3 ")"; n[$1]++ } }
  END {
    for (name in n) if (n[name] > 1) print "pin drift: " name ": " where[name]
  }
' "$records")"
if [ -n "$drift" ]; then
  printf '%s\n' "$drift" >&2
  echo "check-pins: the digests above disagree for the same name:tag. Bump every copy of a" >&2
  echo "            shared base image together so they all resolve to one digest." >&2
  exit 1
fi

echo "check-pins: every external image is pinned by digest, and shared pins agree."
