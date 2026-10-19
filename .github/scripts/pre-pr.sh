#!/bin/sh
# Everything the CI workflow checks, run here before a push, so a PR doesn't go
# red on something a local run would have caught. Same scripts, same tool
# versions: shellcheck 0.9.0 (what ubuntu-24.04's apt installs) in a container,
# and gitleaks 8.30.1 checked against the workflow's sha256 (an older gitleaks
# misses rules CI has, e.g. curl-auth-header). Commit first: gitleaks scans
# history, plus any uncommitted changes to tracked files.
#   sh .github/scripts/pre-pr.sh            all four jobs (~4 min)
#   sh .github/scripts/pre-pr.sh lint       only some: unit, dry, lint, leaks
# Needs podman (or docker) for shellcheck and the dry runs; curl for the first
# gitleaks download (cached in engine/.cache/, git-ignored).
set -u

root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root" || exit 1

gl_version=8.30.1
gl_sha=551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb  # keep in step with ci.yml
sc_image=docker.io/koalaman/shellcheck:v0.9.0
if command -v podman >/dev/null; then cli=podman; else cli=docker; fi

jobs="${*:-unit dry lint leaks}"
failed=""
run() {  # run NAME COMMAND...: print a header, keep going on failure
  name="$1"; shift
  echo "==> $name"
  if "$@"; then echo "    $name: ok"; else echo "    $name: FAILED"; failed="$failed $name"; fi
}

shellcheck_all() {
  # Same files and exclusions as ci.yml's shellcheck step.
  # The image has no shell, so the file list goes in as arguments (xargs batches it).
  git ls-files -z '*.sh' | xargs -0 "$cli" run --rm -v "$root:/mnt:ro" -w /mnt "$sc_image" \
    -S warning -e SC2148,SC2034,SC2154,SC1090,SC1091,SC2317,SC2319,SC2016
}

gitleaks_bin() {
  dir="engine/.cache/gitleaks-$gl_version"
  if [ ! -x "$dir/gitleaks" ]; then
    [ "$(uname -m)" = x86_64 ] || { echo "gitleaks: CI's pinned build is linux x64; this is $(uname -m)" >&2; return 1; }
    mkdir -p "$dir" || return 1
    curl -fsSL -o "$dir/gl.tgz" \
      "https://github.com/gitleaks/gitleaks/releases/download/v$gl_version/gitleaks_${gl_version}_linux_x64.tar.gz" || return 1
    echo "$gl_sha  $dir/gl.tgz" | sha256sum -c - >/dev/null || { echo "gitleaks: checksum mismatch" >&2; rm -f "$dir/gl.tgz"; return 1; }
    tar -xzf "$dir/gl.tgz" -C "$dir" gitleaks && rm -f "$dir/gl.tgz"
  fi
  echo "$dir/gitleaks"
}

gitleaks_all() {
  gl="$(gitleaks_bin)" || return 1
  "$gl" detect --source . --config .gitleaks.toml --redact --no-banner || return 1
  # Not committed yet, so not in the history scan above.
  if ! git diff --quiet HEAD; then
    git diff HEAD | "$gl" stdin --config .gitleaks.toml --redact --no-banner || return 1
  fi
}

for job in $jobs; do
  case "$job" in
    unit)  run unit-tests sh .github/scripts/unit-tests.sh ;;
    dry)   run dry-runs sh .github/scripts/dry-runs.sh ;;
    lint)  run lint-repo sh .github/scripts/lint-repo.sh
           run shellcheck shellcheck_all ;;
    leaks) run gitleaks gitleaks_all ;;
    *) echo "unknown job: $job (unit, dry, lint, leaks)" >&2; exit 2 ;;
  esac
done

# The unit tests import modules from their own folders; don't leave caches behind.
find . -name __pycache__ -type d -not -path './engine/.cache/*' -prune -exec rm -rf {} + 2>/dev/null

if [ -n "$failed" ]; then
  echo "FAILED:$failed"
  exit 1
fi
echo "All CI checks pass locally."
