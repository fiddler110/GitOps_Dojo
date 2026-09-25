#!/usr/bin/env bash
# End-to-end test of vault-fundamentals against a running stack (T5.5): runs every existing test in order, adds
# the facilitator's Audit tab and the demo bots, and with --load watches a class of bots for a while and records
# memory, CPU, runner and app-host load for the sizing notes (README.md, "Sizing"). From the repo root:
#
#   ./run.sh vault-fundamentals --test 20                       # the stack, with 20 demo bots
#   bash workshops/vault-fundamentals/tests/e2e.sh              # every area but load
#   bash workshops/vault-fundamentals/tests/e2e.sh --load 30    # also watch the bots for 30 minutes
#   bash workshops/vault-fundamentals/tests/e2e.sh --only audit,bots
#   bash workshops/vault-fundamentals/tests/e2e.sh --list       # the areas, and what each proves
#
# The lab scripts reset what they create in their student's account, so a run can be repeated. Output (each
# area's log, stats.csv, report.txt, screenshots) goes to a run directory under $TMPDIR (printed first); the
# console shows one line per area and the tail of any failure. Exit status: 0 = every area passed, 1 = one
# failed, 2 = could not run.

set -u
set -o pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
cd "$ROOT" || exit 2
T=workshops/vault-fundamentals/tests

AREAS=(unit tenancy cli_login labs_4_6 labs_7_8 labs_9_11 pool audit bots browser load)
declare -A DESC=(
  [unit]="unit tests without the stack: openbao-audit, app-host, runner-controller"
  [tenancy]="labs 0-3: the shared secret/ and each namespace are private (tenancy.sh)"
  [cli_login]="the terminal's CLI login signs in as the right entity (modules/openbao/tests/cli_login.sh)"
  [labs_4_6]="labs 4-6: the SDK, the Agent, sops + transit, as one student"
  [labs_7_8]="labs 7-8: Actions secrets and masking, AppRole, the job's OIDC identity, a branch refused"
  [labs_9_11]="labs 9-11: deploy by workload identity, dynamic DB logins, the incident drill"
  [pool]="runner-pool: warm pool, isolated one-job runners, the Runners panel (modules/runner-pool/tests/pool.sh)"
  [audit]="the Audit tab's API: facilitator only, filters, and a student's own bao-audit still works"
  [bots]="with --test: each bot has a vault login, a namespace and an app slot, and no bot is stuck on a step"
  [browser]="Playwright: SSO, the Apps and Audit tabs, the lab reader, slides within 16:9 (p4/p5_browser.py, sso_browser.py)"
  [load]="opt-in (--load MIN): watch the bots MIN minutes; peak memory and CPU, runner queue, app slots, bot rounds")

only="" skip="" load_min=0 student=student03
while [ $# -gt 0 ]; do
  case "$1" in
    --only) only=",$2,"; shift ;;
    --skip) skip=",$2,"; shift ;;
    --load) load_min="${2:-20}"; shift ;;
    --student) student="$2"; shift ;;
    --list) for a in "${AREAS[@]}"; do printf '  %-10s %s\n' "$a" "${DESC[$a]}"; done; exit 0 ;;
    -h|--help) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1 (try --help)" >&2; exit 2 ;;
  esac
  shift
done

set -a; . engine/.env; [ -z "${DOJO_ENV:-}" ] || . "engine/.env.$DOJO_ENV"; set +a
podman container exists workshop_terminal 2>/dev/null || { echo "the stack isn't up (./run.sh vault-fundamentals)" >&2; exit 2; }
OUT="$(mktemp -d "${TMPDIR:-/tmp}/vf-e2e.XXXXXX")"
echo "run directory: $OUT"
bots="$(podman exec workshop_terminal printenv BOT_COUNT 2>/dev/null || echo 0)"
bot_prefix="$(podman exec workshop_terminal printenv BOT_PREFIX 2>/dev/null || echo testuser)"
failed=0

wanted() {
  [ "$1" = load ] && [ "$load_min" = 0 ] && return 1
  [ -n "$only" ] && [[ "$only" != *",$1,"* ]] && return 1
  [[ "$skip" == *",$1,"* ]] && return 1
  return 0
}

# area NAME CMD...: run CMD, its output to $OUT/NAME.log; one line on the console.
area() {
  local name="$1" start rc; shift
  wanted "$name" || return 0
  start=$(date +%s)
  "$@" > "$OUT/$name.log" 2>&1
  rc=$?
  if [ "$rc" = 0 ]; then
    printf '  PASS  %-10s (%ss)\n' "$name" "$(( $(date +%s) - start ))"
  else
    printf '  FAIL  %-10s (%ss): %s\n' "$name" "$(( $(date +%s) - start ))" "$OUT/$name.log"
    grep -E 'FAIL|Error|error' "$OUT/$name.log" | head -5 | sed 's/^/          /'
    failed=1
  fi
}

term() { podman exec -i workshop_terminal "$@"; }
code() { term curl -s -o /dev/null -w '%{http_code}' "$@"; }
say() { if [ "$1" = ok ]; then echo "  ok:   $2"; else echo "  FAIL: $2"; bad=1; fi; }

unit() {
  python3 -B -m unittest discover -s modules/openbao/tests -p 'test_*.py' &&
  python3 -B -m unittest discover -s workshops/vault-fundamentals/compose/app-host/tests -p 'test_*.py' &&
  python3 -B -m unittest discover -s modules/runner-pool/tests -p 'test_*.py'
}

audit() {
  local bad=0 base=http://openbao-audit:8080 gw=(-H "X-Gateway-Token: $GATEWAY_TOKEN")
  [ "$(code "$base/api/entries")" = 403 ] && say ok "no gateway token: 403" || say no "no gateway token"
  [ "$(code "${gw[@]}" -H 'X-Auth-User: student01' "$base/api/entries")" = 403 ] \
    && say ok "a student with the token: 403" || say no "a student with the token"
  [ "$(code -H 'X-Gateway-Token: wrong' -H "X-Auth-User: $FACILITATOR_USERNAME" "$base/")" = 403 ] \
    && say ok "a forged token: 403" || say no "a forged token"
  local doc
  term su - student01 -c 'openbao-login --quiet; bao token lookup >/dev/null' >/dev/null 2>&1  # at least one entry
  doc="$(term curl -s "${gw[@]}" -H "X-Auth-User: $FACILITATOR_USERNAME" "$base/api/entries?student=student01&limit=50")"
  echo "$doc" | python3 -B -c '
import json, sys
d = json.load(sys.stdin)
ns = {e["namespace"] for e in d["entries"]}
assert d["entries"], "no entries for student01"
assert ns <= {"students/student01", ""}, ns
assert "student01" in d["students"], d["students"]
print("  ok:   the facilitator reads student01 only (%d entries of %d)" % (len(d["entries"]), d["total"]))' \
    || say no "the facilitator's student filter"
  local csp
  csp="$(term curl -s -D - -o /dev/null "${gw[@]}" -H "X-Auth-User: $FACILITATOR_USERNAME" "$base/" | tr -d '\r' | grep -i '^content-security-policy')"
  [[ "$csp" == *"script-src 'self'"* && "$csp" != *unsafe* ]] && say ok "the page's CSP is strict" || say no "CSP: $csp"
  [ "$(curl -s -o /dev/null -w '%{http_code}' -u "${TTYD_USERNAME:-student}:$TTYD_PASSWORD" "$PUBLIC_BASE_URL/vault-audit/")" != 200 ] \
    && say ok "through the gateway, the class login is refused" || say no "the class login reached /vault-audit/"
  term su - "$student" -c 'bao-audit >/dev/null' && say ok "$student's own bao-audit still works" || say no "$student's bao-audit"
  return "$bad"
}

bots() {
  local bad=0 i b log
  if [ "${bots:-0}" -lt 1 ]; then echo "  no bots in this run (./run.sh vault-fundamentals --test N); nothing to check"; return 0; fi
  local slots
  slots="$(term curl -s -H "X-Gateway-Token: $GATEWAY_TOKEN" -H "X-Auth-User: $FACILITATOR_USERNAME" http://app-host:8080/api/status)"
  for i in $(seq 1 "$bots"); do
    b="$bot_prefix$i"
    term su - "$b" -c 'openbao-login --quiet && BAO_NAMESPACE=students/$USER bao secrets list >/dev/null' 2>/dev/null \
      && say ok "$b signs in and administers students/$b" || say no "$b has no vault login or namespace"
    echo "$slots" | grep -q "\"name\": *\"$b\"" && say ok "$b has an app slot" || say no "$b has no app slot"
    log="$(term sh -c "tail -n 200 /home/$b/.dojo-bot.log 2>/dev/null")"
    if echo "$log" | tail -n 3 | grep -Eq 'failed \(attempt ([5-9]|[1-9][0-9])\)'; then
      say no "$b is stuck: $(echo "$log" | grep 'failed (attempt' | tail -1)"
    else
      say ok "$b: round $(term sh -c "sed -n 's/^ROUND=//p' /home/$b/.dojo-bot-state 2>/dev/null" || echo '?'), not stuck"
    fi
  done
  return "$bad"
}

playwright() { # SCRIPT_DIR SCRIPT
  mkdir -p "$OUT/shots"
  podman run --rm --network host -v "$PWD/$1:/t:ro" -v "$OUT/shots:/s" \
    mcr.microsoft.com/playwright/python:v1.55.0-noble sh -c \
    'pip install -q --break-system-packages playwright==1.55.0 2>/dev/null && python3 -B "/t/$0" "$1" "$2" "$3" "$4" "$5"' \
    "$2" "$PUBLIC_BASE_URL" "${TTYD_USERNAME:-student}" "$TTYD_PASSWORD" "$FACILITATOR_USERNAME" "$FACILITATOR_PASSWORD"
}
browser() {
  playwright modules/openbao/tests sso_browser.py && playwright "$T" p4_browser.py && playwright "$T" p5_browser.py
}

# load: sample every 15 s for $load_min minutes, then summarise.
load() {
  [ "${bots:-0}" -ge 1 ] || { echo "--load needs bots: ./run.sh vault-fundamentals --test 20"; return 1; }
  local end=$(( $(date +%s) + load_min * 60 )) now st ap
  echo "time,container,mem_mib,cpu_pct" > "$OUT/stats.csv"
  echo "time,runners_alive,runners_busy,jobs_waiting,apps_running" > "$OUT/queue.csv"
  local restarts_before
  restarts_before="$(podman ps -a --filter name=workshop_ --format '{{.Names}} {{.Restarts}}' | sort)"
  while [ "$(date +%s)" -lt "$end" ]; do
    now=$(date +%s)
    podman stats --no-stream --format '{{.Name}},{{.MemUsage}},{{.CPUPerc}}' 2>/dev/null \
      | awk -F, -v t="$now" '{ split($2, m, " / "); v=m[1]; u=v; gsub(/[0-9.]/, "", u); gsub(/[^0-9.]/, "", v);
          mib = (u ~ /^G/) ? v * 1024 : (u ~ /^k/) ? v / 1024 : (u ~ /^M/) ? v : v / 1048576;
          c=$3; gsub(/%/, "", c); printf "%s,%s,%.1f,%s\n", t, $1, mib, c }' >> "$OUT/stats.csv"
    st="$(term curl -s -H "X-Gateway-Token: $GATEWAY_TOKEN" -H "X-Auth-User: $FACILITATOR_USERNAME" http://runner-controller:8080/api/state)"
    ap="$(term curl -s -H "X-Gateway-Token: $GATEWAY_TOKEN" -H "X-Auth-User: $FACILITATOR_USERNAME" http://app-host:8080/api/status)"
    python3 -B -c '
import json, sys
t, st, ap = sys.argv[1], sys.argv[2], sys.argv[3]
try: s = json.loads(st)
except ValueError: s = {}
try: a = json.loads(ap)
except ValueError: a = {}
running = sum(1 for x in a.get("slots", []) if x.get("state") == "running")
print(f"{t},{s.get(\"alive\",\"\")},{s.get(\"busy\",\"\")},{len(s.get(\"waiting\", []))},{running}")' "$now" "$st" "$ap" >> "$OUT/queue.csv"
    sleep 15
  done
  local restarts_after
  restarts_after="$(podman ps -a --filter name=workshop_ --format '{{.Names}} {{.Restarts}}' | sort)"
  python3 -B - "$OUT" "$load_min" "$bots" <<'EOF' | tee "$OUT/report.txt"
import csv, collections, sys
out, minutes, bots = sys.argv[1], sys.argv[2], sys.argv[3]
peak, cpu, total = collections.defaultdict(float), collections.defaultdict(float), collections.defaultdict(float)
for r in csv.DictReader(open(f"{out}/stats.csv")):
    m = float(r["mem_mib"] or 0)
    peak[r["container"]] = max(peak[r["container"]], m)
    total[r["time"]] += m
    try: cpu[r["container"]] = max(cpu[r["container"]], float(r["cpu_pct"] or 0))
    except ValueError: pass
q = list(csv.DictReader(open(f"{out}/queue.csv")))
num = lambda k: [int(x[k]) for x in q if x[k].isdigit()]
print(f"load: {bots} bots watched for {minutes} min, {len(q)} samples")
print(f"stack memory, peak sum: {max(total.values() or [0]):.0f} MiB")
for c, m in sorted(peak.items(), key=lambda x: -x[1])[:12]:
    print(f"  {c:32s} peak {m:7.0f} MiB   cpu peak {cpu[c]:5.0f} %")
for k in ("runners_alive", "runners_busy", "jobs_waiting", "apps_running"):
    v = num(k)
    print(f"{k:14s} max {max(v or [0]):3d}   last {v[-1] if v else '-'}")
EOF
  if [ "$restarts_before" != "$restarts_after" ]; then
    echo "FAIL: a container restarted during the run (out of memory?)"
    diff <(echo "$restarts_before") <(echo "$restarts_after")
    return 1
  fi
  local w
  w="$(tail -n 1 "$OUT/queue.csv" | cut -d, -f4)"
  [ "${w:-0}" -le 3 ] || { echo "FAIL: $w jobs still waiting at the end"; return 1; }
  bots
}

area unit       unit
area tenancy    sh "$T/tenancy.sh"
area cli_login  sh modules/openbao/tests/cli_login.sh
area labs_4_6   sh "$T/labs_4_6.sh" "$student"
area labs_7_8   sh "$T/labs_7_8.sh" "$student"
area labs_9_11  sh "$T/labs_9_11.sh" "$student"
# pool.sh counts idle runners and scales by hand: with bots, their jobs take the runners and it fails.
if [ "${bots:-0}" -gt 0 ] && wanted pool; then
  echo "  SKIP  pool       (bots are using the runners; run it on a stack without --test)"
else
  area pool     sh modules/runner-pool/tests/pool.sh
fi
area audit      audit
area bots       bots
area browser    browser
area load       load

[ "$failed" = 0 ] && echo "PASS (logs in $OUT)" || echo "FAIL (logs in $OUT)"
exit "$failed"
