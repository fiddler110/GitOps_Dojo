#!/bin/sh
# Fails when the same tool is pinned to two different versions (or two
# different checksums) in two Dockerfiles. Several images install the same
# tool - the OpenTofu pin is in three terminal Dockerfiles, dnscontrol's in
# two - and a pin bumped in one copy but not the others is drift nothing
# else catches: each pack builds on its own, so both versions work, and the
# labs quietly stop matching each other (RV25).
#
# Usage: engine/scripts/check-tool-pins.sh [DIR...]  (default: engine modules workshops)
# `./run.sh <workshop> --dry-run` runs it on the whole repo, as CI does.
#
# What counts as one tool: an `ARG <TOOL>_VERSION=<value>` line. Everything
# from there to the next such ARG (or the end of the file) is that tool's
# install block, and the per-arch checksums in it (`tofu_sha256="<64 hex>"`)
# belong to that version. A tool only one Dockerfile installs is never
# reported - there is nothing for it to drift from. Image digests
# (`name:tag@sha256:...`) are check-pins.sh's job, not this one's.
#
# A pack that copies more than the pin (a provider mirror, a helper script)
# checks those with its own check-pins-sync.sh; this only reads Dockerfiles.
set -eu

root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
[ "$#" -gt 0 ] || set -- engine modules workshops

files="$(find "$@" \( -name node_modules -o -name .generated \) -prune -o -type f \
  -name 'Dockerfile*' -print | sort)"
[ -n "$files" ] || { echo "check-tool-pins: no Dockerfiles under $*"; exit 0; }

records="$(mktemp)"
trap 'rm -f "$records"' EXIT INT HUP TERM

# One record per fact, tab separated: ARG, kind (VERSION or SHA), value, file.
# shellcheck disable=SC2086
awk '
  FNR == 1 { arg = "" }
  /^ARG[ \t]+[A-Z0-9_]+_VERSION=/ {
    line = $0
    sub(/^ARG[ \t]+/, "", line)
    eq = index(line, "=")
    arg = substr(line, 1, eq - 1)
    val = substr(line, eq + 1)
    gsub(/[ \t\r]+$/, "", val); gsub(/^["'\'']|["'\'']$/, "", val)
    print arg "\t" "VERSION" "\t" val "\t" FILENAME
    next
  }
  # Inside a block: per-arch checksum assignments, e.g. tofu_sha256="<64 hex>".
  arg != "" {
    rest = $0
    while (match(rest, /[A-Za-z_]*sha256=["'\'']?[0-9a-f][0-9a-f]+/)) {
      hit = substr(rest, RSTART, RLENGTH)
      rest = substr(rest, RSTART + RLENGTH)
      sub(/^[A-Za-z_]*sha256=["'\'']?/, "", hit)
      if (length(hit) == 64) print arg "\t" "SHA" "\t" hit "\t" FILENAME
    }
  }
' $files | sort -u > "$records"

awk -F'\t' '
  $2 == "VERSION" {
    if (!((($1 SUBSEP $4) in seen_file))) { seen_file[$1, $4] = 1; nfiles[$1]++ }
    if (!(($1 SUBSEP $3) in seen_val)) { seen_val[$1, $3] = 1; nvals[$1]++ }
    if (!($1 in order)) order[$1] = ++n
    where[$1, $3] = where[$1, $3] (where[$1, $3] ? ", " : "") $4
    args[order[$1]] = $1
  }
  # Records arrive sorted, so each file"s checksum list is built in sorted order.
  $2 == "SHA" { shas[$1, $4] = shas[$1, $4] (shas[$1, $4] ? "," : "") $3; if (!(($1 SUBSEP $4) in sfile)) { sfile[$1, $4] = 1; sfiles[$1] = sfiles[$1] (sfiles[$1] ? "\n" : "") $4 } }
  END {
    bad = 0
    for (i = 1; i <= n; i++) {
      a = args[i]
      if (nfiles[a] < 2) continue          # one Dockerfile owns it: nothing to drift from
      shared++
      if (nvals[a] > 1) {
        printf "pin drift: %s is pinned to %d different versions:\n", a, nvals[a] > "/dev/stderr"
        for (k in seen_val) {
          split(k, p, SUBSEP)
          if (p[1] == a) printf "  %s in %s\n", p[2], where[a, p[2]] > "/dev/stderr"
        }
        bad = 1
        continue
      }
      # Same version in every copy: the checksums under it must match too.
      split(sfiles[a], fs, "\n")
      first = ""; firstf = ""
      for (j = 1; j <= length(fs); j++) {
        if (fs[j] == "") continue
        s = shas[a, fs[j]]
        if (first == "") { first = s; firstf = fs[j]; continue }
        if (s != first) {
          printf "pin drift: %s agrees on the version but not on its checksums:\n", a > "/dev/stderr"
          printf "  %s: %s\n", firstf, first > "/dev/stderr"
          printf "  %s: %s\n", fs[j], s > "/dev/stderr"
          bad = 1
        }
      }
    }
    if (bad) {
      print "check-tool-pins: bump every copy of a shared pin together (version and checksums)." > "/dev/stderr"
      exit 1
    }
    printf "check-tool-pins: %d shared tool pin(s) agree across their Dockerfiles.\n", shared
  }
' "$records"
