#!/bin/sh
# Fails when a Dockerfile FROM or a compose image: names an external image
# without a digest (remediation T1.5, FIND-18). A tag alone can be moved to
# different content by whoever controls the registry; tag@sha256:... can't.
# Keep the tag in front of the digest so a human can read what it is.
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
          if (img !~ /@sha256:[0-9a-f]{64}$/) print FILENAME ":" FNR ": " img
        }' "$f")" ;;
    *)
      out="$(awk '
        $1 == "image:" {
          img = $2; gsub(/["'\'']/, "", img)
          if (img ~ /^\$/ || img ~ /^gitopsdojo\//) next
          if (img !~ /@sha256:[0-9a-f]{64}$/) print FILENAME ":" FNR ": " img
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
echo "check-pins: every external image is pinned by digest."
