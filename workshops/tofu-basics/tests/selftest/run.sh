#!/usr/bin/env bash
# Offline self-test of the tofu-basics test scripts (tests/lib.sh, e2e.sh, load.sh, helpers/). It needs no stack: a fake
# container CLI (mock/bin/podman) runs "student" commands locally with a fake terraform/git/curl and forwards the portal
# helpers to a mock of the portal API (mock/portal_mock.py).
#
# This proves the HARNESS: argument handling, control flow, CSV and report, thresholds, the cleanup + purge path, the refusal
# when there are too few accounts, the assertion helpers, secret masking. It proves NOTHING about the stack or the labs.
#
#   tests/selftest/run.sh            # about 1 minute; exit 0 = all self-checks passed
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TESTS=$(cd "$HERE/.." && pwd)
ROOT=$(mktemp -d "${TMPDIR:-/tmp}/tofu-basics-selftest.XXXXXX") || exit 2
: > "$ROOT/.tofu-basics-selftest"
export PYTHONDONTWRITEBYTECODE=1
PASS=0; FAIL=0
ok() { PASS=$((PASS + 1)); printf '  PASS  %s\n' "$1"; }
bad() { FAIL=$((FAIL + 1)); printf '  FAIL  %s\n' "$1"; [ -n "${2:-}" ] && printf '%s\n' "$2" | sed 's/^/          | /'; }
check() { local desc=$1; shift; if "$@" >/dev/null 2>&1; then ok "$desc"; else bad "$desc" "command failed: $*"; fi; }
contains() { grep -qF -- "$2" <<<"$1"; }
expect_out() { if contains "$3" "$2"; then ok "$1"; else bad "$1" "missing: $2"$'\n'"$(printf '%s' "$3" | tail -n 8)"; fi; }
expect_no() { if contains "$3" "$2"; then bad "$1" "unexpected: $2"; else ok "$1"; fi; }

MOCK_PID=""
finish() {
  [ -n "$MOCK_PID" ] && kill "$MOCK_PID" 2>/dev/null
  [ -e "$ROOT/.tofu-basics-selftest" ] && [[ "$ROOT" == */tofu-basics-selftest.* ]] && rm -rf -- "$ROOT"
  echo; echo "selftest: $PASS passed, $FAIL failed"
  [ "$FAIL" -eq 0 ] || exit 1
}
trap finish EXIT

PORT=$(python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')
python3 -B "$HERE/mock/portal_mock.py" "$PORT" "$ROOT/mock/state" > "$ROOT/portal-mock.log" 2>&1 &
MOCK_PID=$!
export MOCK_ROOT=$ROOT/mock MOCK_PORT=$PORT CONTAINER_CLI=$HERE/mock/bin/podman TMPDIR=$ROOT
export MOCK_SAMPLE_REPO=$TESTS/../content/sample-repo
mkdir -p "$MOCK_ROOT/state"
for _ in 1 2 3 4 5 6 7 8 9 10; do curl -s "http://127.0.0.1:$PORT/readyz" >/dev/null 2>&1 && break; sleep 0.3; done

echo "== syntax"
for f in "$TESTS"/lib.sh "$TESTS"/e2e.sh "$TESTS"/load.sh "$TESTS"/e2e/*.sh "$TESTS"/selftest/run.sh "$HERE"/mock/bin/*; do
  check "bash -n ${f#"$TESTS"/}" bash -n "$f"
done
for f in "$TESTS"/helpers/*.py "$HERE"/mock/portal_mock.py; do
  check "python compiles: ${f#"$TESTS"/}" python3 -B -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$f"
done

echo "== helpers"
J="python3 -B $TESTS/helpers/jq.py"
doc='{"status":200,"body":{"quota":{"containerGroups":{"used":1,"limit":2}},"events":[{"operation":"A","status":"Failed"},{"operation":"A","status":"Succeeded"},{"operation":"B","status":"Failed"}],"name":"x y","t":true}}'
[ "$($J get body.quota.containerGroups.limit <<<"$doc")" = 2 ] && ok "jq get nested" || bad "jq get nested"
[ "$($J get body.name <<<"$doc")" = "x y" ] && ok "jq get string raw" || bad "jq get string raw"
[ "$($J get body.t <<<"$doc")" = true ] && ok "jq get bool" || bad "jq get bool"
[ "$($J get body.nope.deep <<<"$doc")" = "" ] && ok "jq missing path is empty" || bad "jq missing path is empty"
[ "$($J len body.events <<<"$doc")" = 3 ] && ok "jq len" || bad "jq len"
[ "$($J count body.events operation=A status=Failed <<<"$doc")" = 1 ] && ok "jq count with two conditions" || bad "jq count"
[ "$($J pluck body.events operation <<<"$doc" | tr '\n' ,)" = "A,A,B," ] && ok "jq pluck" || bad "jq pluck"
stats=$(printf '[{"name":"c","mem_usage":"1.5GB / 4GB","mem_percent":"37.5%%","cpu_percent":"12.3%%","pids":"7"}]' | python3 -B "$TESTS/helpers/stats_csv.py" 100.5)
[ "$stats" = "100.5,c,1500000000,37.5,12.3,7" ] && ok "stats_csv parses podman json" || bad "stats_csv parses podman json" "$stats"
stats=$(printf '{"Name":"d","MemUsage":"10MiB / 1GiB","MemPerc":"1.00%%","CPUPerc":"2.00%%","PIDs":"3"}\n' | python3 -B "$TESTS/helpers/stats_csv.py" 1)
[ "$stats" = "1,d,10485760,1.00,2.00,3" ] && ok "stats_csv parses docker json lines" || bad "stats_csv parses docker json lines" "$stats"
reply=$(CLOUD_HTTP_PORT=$PORT GATEWAY_TOKEN=mocktoken FACILITATOR_USERNAME=admin python3 -B "$TESTS/helpers/cloud_http.py" GET /cloud/api/me student03)
[ "$(python3 -B "$TESTS/helpers/jq.py" get body.user <<<"$reply")" = student03 ] && ok "cloud_http sends identity and token" || bad "cloud_http sends identity and token" "$reply"
reply=$(CLOUD_HTTP_PORT=$PORT GATEWAY_TOKEN=wrong python3 -B "$TESTS/helpers/cloud_http.py" GET /cloud/api/me student03)
[ "$(python3 -B "$TESTS/helpers/jq.py" get status <<<"$reply")" = 401 ] && ok "cloud_http: a wrong token is refused (401)" || bad "cloud_http wrong token" "$reply"
reply=$(CLOUD_HTTP_PORT=1 python3 -B "$TESTS/helpers/cloud_http.py" GET /readyz -)
[ "$(python3 -B "$TESTS/helpers/jq.py" get status <<<"$reply")" = 0 ] && ok "cloud_http: connection failure is status 0, exit 0" || bad "cloud_http connection failure" "$reply"

echo "== lib: assertions, masking, timing"
out=$(
  . "$TESTS/lib.sh"; DRY_RUN=0; init_run selftest; AREA=unit
  OUT=$LOG_DIR/o.txt; printf 'Plan: 2 to add,\n   0 to change\nsecret line: password=hunter2 and dojo~0123456789abcdef0123456789abcdef01234567\n' > "$OUT"; RC=0; SECS=1.0; SECS_MS=1000
  expect_has "whitespace-insensitive match" 'Plan: 2 to add, 0 to change'
  expect_has "this one must FAIL" 'not there'
  expect_lacks "absent text passes" 'zzz'
  expect_lacks "this one must FAIL too" 'Plan: 2'
  expect_rc "rc 0 passes" 0; RC=3; expect_rc "rc 3 is not 0 (must FAIL)" 0; expect_rc "nonzero passes" nonzero
  expect_secs_le "1.0 s within 2 s" 2; expect_secs_le "1.0 s within 0 s (must FAIL)" 0
  expect_eq "eq passes" a a; expect_eq "eq FAIL" a b; expect_ge "ge" 3 3; expect_le "le FAIL" 5 4
  say "hello password=hunter2 X-Gateway-Token: abc123 dojo~0123456789abcdef0123456789abcdef01234567"
  echo "counts: PASS=$(count_status PASS) FAIL=$(count_status FAIL)"
  echo "log-has-secret: $(grep -c 'hunter2\|abc123\|0123456789abcdef' "$RUN_DIR/run.log" "$RUN_DIR/results.tsv" | tr '\n' ' ')"
)
expect_out "7 checks pass, 6 fail as designed" "counts: PASS=7 FAIL=6" "$out"
expect_no "masked text does not leak the password" "hunter2" "$(grep -v '^log-has-secret' <<<"$out" | grep -v 'secret line')"
expect_out "the run log holds no secret" "run.log:0 " "$out"
expect_out "failure evidence shows the output tail" "| Plan: 2 to add," "$out"

echo "== dry runs"
o=$("$TESTS/e2e.sh" --dry-run --with-restart 2>&1); rc=$?
[ "$rc" -eq 0 ] && ok "e2e.sh --dry-run exits 0" || bad "e2e.sh --dry-run exit status $rc"
expect_out "e2e dry run prints the labs' commands" "terraform apply -auto-approve -no-color -input=false" "$o"
expect_out "e2e dry run reads the labs' own sed line" "sed -i '/^    owner /d' locals.tf" "$o"
expect_out "e2e dry run includes the security area" "cross-tenant" "$o"
expect_out "and its cross-tenant probe" "other_subscription_write=403" "$o"
expect_no "e2e dry run has no shell errors" "unbound variable" "$o"
expect_no "e2e dry run finds every lab line" "cannot find" "$o"
o=$("$TESTS/load.sh" --dry-run --students 6 --wave-size 3 2>&1); rc=$?
[ "$rc" -eq 0 ] && ok "load.sh --dry-run exits 0" || bad "load.sh --dry-run exit status $rc"
expect_out "load dry run shows the wave schedule" "2 waves of up to 3 students" "$o"
o=$("$TESTS/e2e.sh" --only nope 2>&1); rc=$?
[ "$rc" -eq 2 ] && ok "e2e.sh rejects an unknown area (exit 2)" || bad "e2e.sh unknown area exit status $rc"

echo "== load.sh against the mock"
o=$("$TESTS/load.sh" --students 4 --wave-size 2 --wave-gap 1 --pollers 2 --sample-interval 1 2>&1); rc=$?
[ "$rc" -eq 0 ] && ok "healthy run exits 0" || bad "healthy run exit status $rc" "$(printf '%s' "$o" | tail -n 15)"
expect_out "report says PASS" "LOAD RESULT: PASS" "$o"
expect_out "report has per-step percentiles" "tag_apply" "$o"
expect_out "cleanup verified the portal is empty" "portal is empty for: student01 student02 student03 student04" "$o"
csv=$(ls -d "$ROOT"/tofu-basics-load.* | head -n1)/steps.csv
[ "$(wc -l < "$csv")" -eq 25 ] && ok "steps.csv has a header and 4 students x 6 steps" || bad "steps.csv rows: $(wc -l < "$csv")"
o=$(MOCK_FAIL_APPLY_USER=student02 "$TESTS/load.sh" --students 3 --pollers 1 --sample-interval 1 2>&1); rc=$?
[ "$rc" -eq 1 ] && ok "a failing student makes the run exit 1" || bad "failing run exit status $rc"
expect_out "the failure is listed with its output tail" "Error: mock apply failure" "$o"
expect_out "leftovers are detected" "portal still shows resources for: student02" "$o"
expect_out "and purged" "purge student02: status 200" "$o"
o=$("$TESTS/load.sh" --students 30 2>&1); rc=$?
[ "$rc" -eq 2 ] && ok "asking for more students than accounts exits 2" || bad "too many students exit status $rc"
expect_out "and says why and what to do" "only has 20 accounts" "$o"

echo "== e2e.sh against the mock (only the harness: the fake commands do not satisfy the labs, so checks FAIL)"
o=$("$TESTS/e2e.sh" --only curl_ca --student 2 2>&1); rc=$?
[ "$rc" -eq 1 ] && ok "failed checks make e2e.sh exit 1" || bad "e2e exit status $rc"
expect_out "cleanup ran and verified the portal" "portal is empty for: student02" "$o"
expect_out "summary lists the failed checks" "failed checks:" "$o"
printf '1 1\n' > "$MOCK_ROOT/state/student05"    # a subscription that is not empty
o=$("$TESTS/e2e.sh" --only curl_ca --student 5 2>&1); rc=$?
[ "$rc" -eq 2 ] && ok "a non-empty subscription is refused (exit 2)" || bad "non-empty subscription exit status $rc"
expect_out "and the message names the way out" "--purge-first" "$o"
[ "$(cat "$MOCK_ROOT/state/student05")" = "1 1" ] && ok "a refused run leaves the student's subscription alone (no purge)" || bad "a refused run purged the subscription"
o=$("$TESTS/e2e.sh" --only curl_ca --student 5 --purge-first 2>&1)
expect_out "--purge-first empties it and goes on" "purging it (--purge-first)" "$o"
