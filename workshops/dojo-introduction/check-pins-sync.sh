#!/bin/sh
# Fails if a tool pin in compose/terminal/Dockerfile no longer matches the
# workshop Dockerfile it was copied from (versions and sha256 checksums).
# Usage: workshops/dojo-introduction/check-pins-sync.sh
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
mine="$here/compose/terminal/Dockerfile"
ws="$here/.."
rc=0

# check SOURCE_DOCKERFILE NAME...: each NAME is an ARG (VERSION) whose value, and
# every sha256 on the source's lines that mention the tool, must appear here too.
check() {
  src="$1"; shift
  for arg in "$@"; do
    want="$(sed -n "s/^ARG ${arg}=//p" "$src" | head -1)"
    have="$(sed -n "s/^ARG ${arg}=//p" "$mine" | head -1)"
    if [ -z "$want" ] || [ "$want" != "$have" ]; then
      echo "pin drift: $arg is '$have' here, '$want' in ${src#$ws/}"; rc=1
    fi
  done
}
# every sha256 in a source file must be present in ours
shas() {
  src="$1"; shift
  for sha in $(grep -oE '[0-9a-f]{64}' "$src" | sort -u); do
    grep -q "$sha" "$mine" || { echo "pin drift: checksum $sha from ${src#$ws/} is missing here"; rc=1; }
  done
}

check "$ws/dns-as-code/compose/terminal/Dockerfile" DNSCONTROL_VERSION
check "$ws/cert-autorenewal/compose/terminal/Dockerfile" ACMESH_VERSION STEP_CLI_VERSION
check "$ws/vault-fundamentals/compose/terminal/Dockerfile" SOPS_VERSION GITLEAKS_VERSION
check "$ws/tofu-basics/compose/terminal/Dockerfile" TOFU_VERSION OPENTOFU_VSCODE_VERSION
for d in dns-as-code cert-autorenewal vault-fundamentals tofu-basics; do shas "$ws/$d/compose/terminal/Dockerfile"; done
# the provider mirror files are copies too
for f in mirror.tf unpack-mirror.py tofurc disable-tofu-ls.py; do
  cmp -s "$ws/tofu-basics/compose/terminal/$f" "$here/compose/terminal/$f" \
    || { echo "pin drift: compose/terminal/$f differs from tofu-basics'"; rc=1; }
done
# shas() also sees vault's hvac-wheels-free Dockerfile only; hvac wheels are not used here.
[ "$rc" = 0 ] && echo "dojo-introduction tool pins match their sources"
exit "$rc"
