#!/bin/sh
# This pack's terminal image takes OpenTofu and its provider mirror from
# tofu-basics. Fails if a copied file here no longer matches the one it came
# from. `mirror.tf` is deliberately NOT compared: this pack mirrors its own
# set of providers.
#
# Tool versions and checksums are NOT checked here: a shared `ARG
# <TOOL>_VERSION` is checked across the whole repo by
# engine/scripts/check-tool-pins.sh, which every `--dry-run` runs (RV25).
#
# Usage: workshops/cloud-policy-as-code/check-pins-sync.sh  (CI: .github/scripts/dry-runs.sh)
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
ws="$here/.."
rc=0

for f in unpack-mirror.py tofurc disable-tofu-ls.py; do
  cmp -s "$ws/tofu-basics/compose/terminal/$f" "$here/compose/terminal/$f" \
    || { echo "copy drift: compose/terminal/$f differs from tofu-basics'"; rc=1; }
done

[ "$rc" = 0 ] && echo "cloud-policy-as-code: copied terminal files match tofu-basics'"
exit "$rc"
