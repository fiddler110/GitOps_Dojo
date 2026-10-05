#!/bin/sh
# This pack's terminal image is a copy of two others': dnscontrol from
# dns-as-code, OpenTofu and its provider mirror from tofu-basics. Fails if a
# copied file here no longer matches the one it came from.
#
# Tool versions and checksums are NOT checked here: a shared `ARG
# <TOOL>_VERSION` is checked across the whole repo by
# engine/scripts/check-tool-pins.sh, which every `--dry-run` runs (RV25).
# This covers only what that cannot see - whole files copied between packs.
#
# Usage: workshops/dojo-introduction/check-pins-sync.sh  (CI: .github/scripts/dry-runs.sh)
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
ws="$here/.."
rc=0

# The provider mirror and its helpers are byte-for-byte copies of tofu-basics'.
for f in mirror.tf unpack-mirror.py tofurc disable-tofu-ls.py; do
  cmp -s "$ws/tofu-basics/compose/terminal/$f" "$here/compose/terminal/$f" \
    || { echo "copy drift: compose/terminal/$f differs from tofu-basics'"; rc=1; }
done

[ "$rc" = 0 ] && echo "dojo-introduction: copied terminal files match tofu-basics'"
exit "$rc"
