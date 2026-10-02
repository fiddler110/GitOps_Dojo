#!/bin/sh
# Every unit-test suite in the repo, the way each one is meant to be run
# (RV13), plus the shell test harnesses' offline self-tests. Stdlib Python
# only; no containers. Runs locally too:
#   sh .github/scripts/unit-tests.sh
# Each suite runs from its own folder (the modules import their siblings by
# plain name), so a new folder with test_*.py files is picked up by itself.
set -u

root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"

failed=""
run() { # name, then the command
  name="$1"; shift
  echo "==> $name"
  if "$@"; then :; else failed="$failed $name"; fi
}

# The dojo CLI needs its pinned wheels; any run.sh call unpacks them first.
./run.sh list >/dev/null || { echo "could not unpack the CLI's wheels" >&2; exit 1; }
pylib="$(echo engine/.cache/pylib-*)"
run engine/dojo env PYTHONPATH="engine:$pylib" python3 -B -m unittest discover -s engine/dojo/tests -t engine
run engine/allocator sh -c 'cd engine/allocator && python3 -B -m unittest discover -s tests'

for dir in $(find modules workshops -name 'test_*.py' -not -path '*/node_modules/*' -exec dirname {} \; | sort -u); do
  run "$dir" sh -c "cd '$dir' && python3 -B -m unittest discover -p 'test_*.py'"
done

# The live-stack test harnesses' own offline self-tests (fake container CLI, mock portal).
run workshops/assets/test-lib sh workshops/assets/test-lib-selftest.sh
run workshops/tofu-basics/tests/selftest bash workshops/tofu-basics/tests/selftest/run.sh

if [ -n "$failed" ]; then
  echo "FAILED:$failed" >&2
  exit 1
fi
echo "All unit-test suites passed."
