#!/usr/bin/env bash
# Load test for the tofu-basics workshop (PLAN T9.3, milestone M4): N students run the Track B flow AT THE SAME TIME,
# each as their own Linux account through the terminal container, against a running stack:
#     clone -> init -> apply (2 resources) -> fetch the site -> tag edit + apply (in-place) -> destroy
# Every step's wall time is recorded per student in a CSV. While it runs the script samples, about every 2 s,
# `stats` of workshop_cloud_host / workshop_cloud_api / workshop_terminal, and polls the portal the way a class does
# (class overview every 3 s from a few users, the facilitator's progress board, /readyz), all from inside cloud-api.
# At the end it prints p50/p95/max per step, the failures with the tail of their output, peak memory per container, the
# wall time, and PASS/FAIL against thresholds. Cleanup destroys everything and asserts the portal is empty.
#
#   tests/load.sh --students 10 --wave-size 5      # a first, gentle run
#   tests/load.sh                                  # 30 students at once (see the memory warning in tests/README.md)
#   tests/load.sh --dry-run                        # print what would run; touches no stack
#   tests/load.sh --cleanup-only --students 30     # empty the students' clouds after a --keep run or a crash
#
# Exit status: 0 = thresholds met and cleanup verified, 1 = a threshold or the cleanup failed, 2 = could not run.
# Output goes to a run directory under $TMPDIR (path printed first): steps.csv, stats.csv, portal.csv, report.txt,
# failures/, students/<user>/logs/, session.log.

set -u
set -o pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=lib.sh
. "$HERE/lib.sh"

usage() {
  cat <<EOF
Usage: tests/load.sh [options]

  --students N          how many students run the flow (default 30): ${STUDENT_PREFIX}01..NN. Refuses if the
                        terminal container has fewer accounts (STUDENT_COUNT in engine/.env).
  --wave-size K         start K students at a time instead of all at once (default 0 = all at once)
  --wave-gap S          seconds between waves (default 20)
  --pollers P           class-overview portal pollers, one per user, every 3 s (default 3)
  --sample-interval S   seconds between container samples (default 2)
  --max-failures N      thresholds: failed steps allowed (default 0)
  --max-p95-apply S     p95 of the apply step in seconds (default 120; a single apply takes ~35 s)
  --max-portal-p95-ms M p95 of the class-overview poll in milliseconds (default 2000)
  --max-readyz-failures N  non-200 /readyz samples allowed (default 0)
  --step-timeout S      limit for one apply or destroy (default 600)
  --run-timeout S       limit for all flows together (default 1800); stragglers are killed and counted as failures
  --purge-first         empty the students' subscriptions first if they are not empty (otherwise the run refuses)
  --no-purge            never use the facilitator Purge as a cleanup fallback
  --keep                skip cleanup: deployments and ~/load-* stay (clean up later with --cleanup-only)
  --cleanup-only        do not run anything: destroy/purge what an earlier run left for students 1..N, verify, exit
  --dry-run             print the commands and the plan; do not touch any container
  -h, --help

WARNING: N students applying at once means N \`tofu\` + azurerm provider processes at once inside ONE container
(workshop_terminal). Their size is unmeasured; the run measures it. On a small machine 30 at once may exceed the
container's memory limit and get processes OOM-killed (reported as a failure). Start with --wave-size.

Environment: CONTAINER_CLI (default podman, else docker), TERMINAL_CONTAINER, CLOUD_API_CONTAINER,
CLOUD_HOST_CONTAINER, TMPDIR.
EOF
}

N=30; WAVE=0; GAP=20; POLLERS=3; SAMPLE=2
MAX_FAIL=0; MAX_P95_APPLY=120; MAX_PORTAL_P95=2000; MAX_READYZ_FAIL=0
STEP_TIMEOUT=600; RUN_TIMEOUT=1800; PURGE_FIRST=0; CLEANUP_ONLY=0
while [ $# -gt 0 ]; do
  case $1 in
    --students) [ $# -ge 2 ] || die "--students needs a value"; N=$2; shift ;;
    --wave-size) [ $# -ge 2 ] || die "--wave-size needs a value"; WAVE=$2; shift ;;
    --wave-gap) [ $# -ge 2 ] || die "--wave-gap needs a value"; GAP=$2; shift ;;
    --pollers) [ $# -ge 2 ] || die "--pollers needs a value"; POLLERS=$2; shift ;;
    --sample-interval) [ $# -ge 2 ] || die "--sample-interval needs a value"; SAMPLE=$2; shift ;;
    --max-failures) [ $# -ge 2 ] || die "--max-failures needs a value"; MAX_FAIL=$2; shift ;;
    --max-p95-apply) [ $# -ge 2 ] || die "--max-p95-apply needs a value"; MAX_P95_APPLY=$2; shift ;;
    --max-portal-p95-ms) [ $# -ge 2 ] || die "--max-portal-p95-ms needs a value"; MAX_PORTAL_P95=$2; shift ;;
    --max-readyz-failures) [ $# -ge 2 ] || die "--max-readyz-failures needs a value"; MAX_READYZ_FAIL=$2; shift ;;
    --step-timeout) [ $# -ge 2 ] || die "--step-timeout needs a value"; STEP_TIMEOUT=$2; shift ;;
    --run-timeout) [ $# -ge 2 ] || die "--run-timeout needs a value"; RUN_TIMEOUT=$2; shift ;;
    --purge-first) PURGE_FIRST=1 ;;
    --no-purge) TB_NO_PURGE=1 ;;
    --keep) TB_KEEP=1 ;;
    --cleanup-only) CLEANUP_ONLY=1 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; die "unknown option: $1" ;;
  esac
  shift
done
case $N in ''|*[!0-9]*|0) die "--students must be a positive integer" ;; esac
for v in "$WAVE" "$GAP" "$POLLERS" "$SAMPLE" "$STEP_TIMEOUT" "$RUN_TIMEOUT"; do
  case $v in ''|*[!0-9]*) die "numeric option expected, got '$v'" ;; esac
done
[ "$SAMPLE" -ge 1 ] || die "--sample-interval must be at least 1"

pick_cli
init_run load
TB_TITLE="tofu-basics load test ($N students)"
TB_CLEANUP_HOOK=load_cleanup
SAFE_TO_CLEAN=0
TB_NO_PURGE=${TB_NO_PURGE:-0}
export DRY_RUN TB_NO_PURGE
install_exit_trap

USERS=(); FLOW_PIDS=(); SAMPLER_PID=""; POLLER_PID=""; MONITORS=0
STEPS_CSV=$RUN_DIR/steps.csv
LT_U=""; LT_OK=1

# ---- one student's flow (runs in a background subshell per student) ------------------------------------------------
# _lt_step NAME TIMEOUT "command" ["text the output must contain"]  -> appends one CSV row, sets LT_OK
_lt_step() {
  local name=$1 tmo=$2 cmd=$3 needle=${4:-} t0 ok=1
  t0=$(now_ms)
  as_student "$LT_U" "$cmd" "$tmo" "$name"
  if is_dry; then LT_OK=1; return 0; fi
  if [ "$RC" -ne 0 ]; then ok=0; elif [ -n "$needle" ] && ! out_has "$needle"; then ok=0; fi
  printf '%s,%s,%s,%s,%s,%s\n' "$LT_U" "$name" "$t0" "$SECS_MS" "$RC" "$ok" >> "$STEPS_CSV"
  LT_OK=$ok
  if [ "$ok" = 0 ]; then
    mkdir -p "$RUN_DIR/failures"
    { printf 'command: %s\n' "${cmd:0:300}"; [ -n "$needle" ] && printf 'expected output to contain: %s\n' "$needle"; printf 'exit status: %s\n---\n' "$RC"; tail -n 40 "$OUT"; } > "$RUN_DIR/failures/$LT_U-$name.log"
  fi
}

student_flow() {  # student_flow USER
  local u=$1 tagsed
  local dir=/home/$u/load-$RUN_ID; local repo=$dir/$FORGEJO_REPO; local label=hello-dev-$u
  LT_U=$u; AREA=$u; SEQ=0
  LOG_DIR=$RUN_DIR/students/$u/logs; TMP_DIR=$RUN_DIR/students/$u; SESSION_LOG=$TMP_DIR/session.log; mkdir -p "$LOG_DIR"
  register_workdir "$u" "$dir"; register_tofu_dir "$u" "$repo"    # registered first, so an aborted run still cleans up
  tagsed=$(lab_line lab8.md "sed -i '/managed_by = \"opentofu\"/a") || { LT_OK=0; return 0; }   # the labs' own tag edit
  _lt_step clone 180 "mkdir -p '$dir' && cd '$dir' && git clone -q $TB_STARTER_URL_BASE/$FORGEJO_ORG/$FORGEJO_REPO.git"
  [ "$LT_OK" = 1 ] || return 0
  _lt_step init 180 "cd '$repo' && terraform init -no-color -input=false" 'OpenTofu has been successfully initialized!'
  [ "$LT_OK" = 1 ] || return 0
  _lt_step apply "$STEP_TIMEOUT" "cd '$repo' && terraform apply -auto-approve -no-color -input=false" \
    'Apply complete! Resources: 2 added, 0 changed, 0 destroyed.'
  if [ "$LT_OK" = 1 ]; then
    _lt_step site 100 "for i in \$(seq 1 45); do curl -s -m 10 http://cloud-api:8080/cloud/site/$label/ | grep -q '<h1>Hello from Dojo Cloud!</h1>' && exit 0; sleep 2; done; echo 'the site never answered'; exit 1"
    _lt_step tag_apply "$STEP_TIMEOUT" "cd '$repo' && $tagsed && terraform apply -auto-approve -no-color -input=false" \
      'Apply complete! Resources: 0 added, 2 changed, 0 destroyed.'
  fi
  # destroy whatever an apply may have created, even after a failure above
  _lt_step destroy "$STEP_TIMEOUT" "cd '$repo' && terraform destroy -auto-approve -no-color -input=false" 'Destroy complete! Resources: 2 destroyed.'
  return 0
}

student_flow_run() { student_flow "$1"; : > "$RUN_DIR/students/$1/finished"; }   # the marker says "this flow ended by itself"

# ---- monitors ------------------------------------------------------------------------------------------------------------
sampler() {  # container samples until $RUN_DIR/stop-sampling exists
  local t0 fmt=json
  [ "$CLI" = docker ] && fmt='{{json .}}'
  echo 'epoch,name,mem_bytes,mem_pct,cpu_pct,pids' > "$RUN_DIR/stats.csv"
  while [ ! -e "$RUN_DIR/stop-sampling" ]; do
    t0=$SECONDS
    "$CLI" stats --no-stream --format "$fmt" "$TERMINAL_CONTAINER" "$CLOUD_API_CONTAINER" "$CLOUD_HOST_CONTAINER" 2>/dev/null \
      | python3 -B "$TB_HELPERS/stats_csv.py" "${EPOCHREALTIME/,/.}" >> "$RUN_DIR/stats.csv"
    [ $((SECONDS - t0)) -ge "$SAMPLE" ] || sleep $((SAMPLE - (SECONDS - t0)))
  done
}

start_monitors() {
  local pollusers="" i
  for ((i = 0; i < POLLERS && i < N; i++)); do pollusers+="${USERS[$i]},"; done
  if is_dry; then
    dry "sampler: every ${SAMPLE}s: $CLI stats --no-stream --format json $TERMINAL_CONTAINER $CLOUD_API_CONTAINER $CLOUD_HOST_CONTAINER   -> stats.csv"
    dry "poller (inside $CLOUD_API_CONTAINER, one exec for the whole run): overview?scope=class as ${pollusers%,} every 3 s, admin/progress as the facilitator, /readyz every 2 s   -> portal.csv"
    return 0
  fi
  rm -f "$RUN_DIR/stop-sampling"
  sampler & SAMPLER_PID=$!
  "$CLI" exec "$CLOUD_API_CONTAINER" python3 -c "$(cat "$TB_HELPERS/poller.py")" \
    --duration $((RUN_TIMEOUT + 600)) --stop-file "/tmp/tb-poller-stop-$RUN_ID" --users "${pollusers%,}" \
    > "$RUN_DIR/portal.csv" 2> "$RUN_DIR/poller.err" &
  POLLER_PID=$!
  MONITORS=1
}
stop_monitors() {
  [ "$MONITORS" = 1 ] || return 0
  MONITORS=0
  : > "$RUN_DIR/stop-sampling"
  "$CLI" exec "$CLOUD_API_CONTAINER" touch "/tmp/tb-poller-stop-$RUN_ID" >/dev/null 2>&1
  local t0=$SECONDS
  while { kill -0 "$SAMPLER_PID" 2>/dev/null || kill -0 "$POLLER_PID" 2>/dev/null; } && [ $((SECONDS - t0)) -lt 40 ]; do sleep 1; done
  kill "$SAMPLER_PID" "$POLLER_PID" 2>/dev/null
  wait "$SAMPLER_PID" "$POLLER_PID" 2>/dev/null
  "$CLI" exec "$CLOUD_API_CONTAINER" rm -f "/tmp/tb-poller-stop-$RUN_ID" >/dev/null 2>&1
  return 0
}

collect_container_facts() {  # limits.txt, peaks.txt (kernel memory.peak; cgroup v2), oom.txt
  local c lim peak
  : > "$RUN_DIR/limits.txt"; : > "$RUN_DIR/peaks.txt"
  for c in "$TERMINAL_CONTAINER" "$CLOUD_API_CONTAINER" "$CLOUD_HOST_CONTAINER"; do
    lim=$("$CLI" inspect -f '{{.HostConfig.Memory}}' "$c" 2>/dev/null); echo "$c ${lim:-0}" >> "$RUN_DIR/limits.txt"
    peak=$("$CLI" exec "$c" cat /sys/fs/cgroup/memory.peak 2>/dev/null | head -n1)
    case $peak in ''|*[!0-9]*) ;; *) echo "$c $peak" >> "$RUN_DIR/peaks.txt" ;; esac
  done
}
oom_snapshot() {  # oom_snapshot before|after -> writes restarts into $RUN_DIR/oom.$1
  local c
  : > "$RUN_DIR/oom.$1"
  for c in "$TERMINAL_CONTAINER" "$CLOUD_API_CONTAINER" "$CLOUD_HOST_CONTAINER"; do
    echo "$c $("$CLI" inspect -f 'oomkilled={{.State.OOMKilled}} restarts={{.RestartCount}}' "$c" 2>/dev/null) oom_kill=$("$CLI" exec "$c" sh -c "grep '^oom_kill ' /sys/fs/cgroup/memory.events" 2>/dev/null | awk '{print $2}' | head -n1)" >> "$RUN_DIR/oom.$1"
  done
}
write_oom_txt() {
  local c b a
  : > "$RUN_DIR/oom.txt"
  for c in "$TERMINAL_CONTAINER" "$CLOUD_API_CONTAINER" "$CLOUD_HOST_CONTAINER"; do
    b=$(grep "^$c " "$RUN_DIR/oom.before" | head -n1); a=$(grep "^$c " "$RUN_DIR/oom.after" | head -n1)
    printf '%s oomkilled=%s restarts_before=%s restarts_after=%s oom_kill_before=%s oom_kill_after=%s\n' "$c" \
      "$(echo "$a" | sed -n 's/.*oomkilled=\([a-z]*\).*/\1/p')" \
      "$(echo "$b" | sed -n 's/.*restarts=\([0-9]*\).*/\1/p')" "$(echo "$a" | sed -n 's/.*restarts=\([0-9]*\).*/\1/p')" \
      "$(echo "$b" | sed -n 's/.*oom_kill=\([0-9]*\).*/\1/p')" "$(echo "$a" | sed -n 's/.*oom_kill=\([0-9]*\).*/\1/p')" >> "$RUN_DIR/oom.txt"
  done
}

memory_warning() {
  local limit host per=250 want fit
  limit=$("$CLI" inspect -f '{{.HostConfig.Memory}}' "$TERMINAL_CONTAINER" 2>/dev/null); : "${limit:=0}"
  host=$(awk '/^MemTotal:/ {print $2 * 1024}' /proc/meminfo 2>/dev/null); : "${host:=0}"
  want=$((N * per * 1000000))
  say "  MEMORY: $N concurrent students = up to $N tofu + azurerm provider processes at once in $TERMINAL_CONTAINER."
  say "          Their size is UNMEASURED (assuming ~${per} MB each, a guess: about $((want / 1000000000)) GB in total if all run at once);"
  say "          this run measures it (peak $TERMINAL_CONTAINER memory in the report)."
  say "          $TERMINAL_CONTAINER limit: $([ "$limit" -gt 0 ] && echo "$((limit / 1000000)) MB" || echo none); host RAM: $((host / 1000000)) MB."
  if [ "$limit" -gt 0 ] && [ "$want" -gt "$limit" ]; then
    fit=$((limit / (per * 1000000) / 2)); [ "$fit" -ge 1 ] || fit=1
    warn "the guess exceeds the terminal container's memory limit: expect OOM kills (reported as failures). Try --wave-size $fit, or raise WEB_TERMINAL_MEM_LIMIT."
  elif [ "$host" -gt 0 ] && [ "$want" -gt $((host * 7 / 10)) ]; then
    warn "the guess is above 70% of the host's RAM: the host itself may swap or kill things. Consider --wave-size."
  fi
}

# ---- cleanup (runs from the exit trap unless --keep) ---------------------------------------------------------------------
load_cleanup() {
  AREA=cleanup
  local pid
  for pid in "${FLOW_PIDS[@]:-}"; do [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && { pkill -TERM -P "$pid" 2>/dev/null; kill "$pid" 2>/dev/null; }; done
  stop_monitors
  # Never touch subscriptions the preflight refused: students who already had resources must keep them.
  if [ "${#USERS[@]}" -eq 0 ] || [ "$SAFE_TO_CLEAN" != 1 ]; then say "  nothing to clean (the run stopped before it started)"; return 0; fi
  if ! container_running "$CLOUD_HOST_CONTAINER"; then
    say "  $CLOUD_HOST_CONTAINER is not running: starting it so the destroys can work"
    "$CLI" start "$CLOUD_HOST_CONTAINER" >/dev/null 2>&1
  fi
  wait_ready 90 || say "  cloud-api is not ready: the destroys below may fail, the portal check then decides"
  destroy_registered 8
  verify_empty "${USERS[@]}"
  remove_workdirs
}

# ---- go ------------------------------------------------------------------------------------------------------------------
section "tofu-basics load test ($([ "$DRY_RUN" = 1 ] && echo dry-run || echo live)): $N students, $([ "$WAVE" -gt 0 ] && echo "waves of $WAVE every ${GAP}s" || echo "all at once"), with $CLI"
say "  run dir: $RUN_DIR"
preflight || die "preflight failed: the stack is not ready for a test"
if [ "$N" -gt "$STUDENT_COUNT_ACTUAL" ]; then
  say ""
  say "  Cannot run $N students: $TERMINAL_CONTAINER only has $STUDENT_COUNT_ACTUAL accounts (${STUDENT_PREFIX}01..$(printf '%02d' "$STUDENT_COUNT_ACTUAL"))."
  say "  Either ask for at most $STUDENT_COUNT_ACTUAL (--students $STUDENT_COUNT_ACTUAL), or raise STUDENT_COUNT in engine/.env and restart the stack"
  say "  (./run.sh stop, then ./run.sh tofu-basics). Nothing was started."
  die "not enough student accounts: asked for $N, have $STUDENT_COUNT_ACTUAL"
fi
for ((i = 1; i <= N; i++)); do USERS+=("$(user_name "$i")"); done
if ! is_dry; then
  missing=$("$CLI" exec "$TERMINAL_CONTAINER" sh -c 'for u in "$@"; do id -u "$u" >/dev/null 2>&1 || echo "$u"; done' sh "${USERS[@]}" | tr '\n' ' ')
  [ -z "$missing" ] || die "these accounts do not exist in $TERMINAL_CONTAINER: $missing"
fi

if [ "$CLEANUP_ONLY" = 1 ]; then
  SAFE_TO_CLEAN=1   # asked for explicitly
  section "Cleanup only: students ${USERS[0]}..${USERS[$((N - 1))]}"
  if ! is_dry; then
    for u in "${USERS[@]}"; do
      as_student "$u" 'ls -d /home/'"$u"'/load-* 2>/dev/null' 30 find-load-dirs
      while IFS= read -r d; do
        if safe_workdir "$d"; then register_tofu_dir "$u" "$d/$FORGEJO_REPO"; register_workdir "$u" "$d"; fi
      done < "$OUT"
    done
  fi
  exit 0    # the exit trap runs load_cleanup
fi

check_credentials "${USERS[0]}" || die "no Dojo Cloud credentials for ${USERS[0]}"
if ! is_dry; then
  busy=$(leftover_owners "${USERS[@]}" | tr '\n' ' ')
  if [ -n "$busy" ]; then
    if [ "$PURGE_FIRST" = 1 ]; then
      say "  these students' subscriptions are not empty: $busy: purging them (--purge-first)"
      for u in $busy; do portal_purge "$u"; done
    else
      die "these students' subscriptions are not empty: $busy. Empty them (Purge in the portal), or use --purge-first."
    fi
  fi
fi
SAFE_TO_CLEAN=1   # preflight passed (or the students were purged with --purge-first)
memory_warning
echo 'user,step,start_ms,ms,rc,ok' > "$STEPS_CSV"

if is_dry; then
  section "Plan (dry run): one sample student's flow, then the rest is just N copies of it"
  say "  students: ${USERS[*]}"
  if [ "$WAVE" -gt 0 ]; then say "  schedule: $(((N + WAVE - 1) / WAVE)) waves of up to $WAVE students, ${GAP}s apart"; else say "  schedule: all $N started together"; fi
  start_monitors
  student_flow "${USERS[0]}"
  section "After the flows"
  dry "stop the samplers; read memory.peak and OOM state of the three containers"
  dry "python3 helpers/report.py RUN_DIR --max-failures $MAX_FAIL --max-p95-apply $MAX_P95_APPLY --max-portal-p95-ms $MAX_PORTAL_P95 --max-readyz-failures $MAX_READYZ_FAIL"
  dry "cleanup: terraform destroy in every student's directory (8 at a time), check the portal is empty for all $N, delete ~/load-$RUN_ID"
  exit 0
fi

section "Running"
oom_snapshot before
start_monitors
FLOWS_START=$SECONDS
k=$WAVE; [ "$k" -gt 0 ] || k=$N
i=0
for u in "${USERS[@]}"; do
  student_flow_run "$u" & FLOW_PIDS+=($!)
  i=$((i + 1))
  if [ "$i" -lt "$N" ] && [ $((i % k)) -eq 0 ]; then say "  started $i of $N students; next wave in ${GAP}s"; sleep "$GAP"; fi
done
say "  all $N flows started; waiting for them (limit ${RUN_TIMEOUT}s)"
last=0
while :; do
  alive=0
  for pid in "${FLOW_PIDS[@]}"; do kill -0 "$pid" 2>/dev/null && alive=$((alive + 1)); done
  [ "$alive" -gt 0 ] || break
  if [ $((SECONDS - FLOWS_START)) -ge "$RUN_TIMEOUT" ]; then
    say "  run timeout (${RUN_TIMEOUT}s): killing $alive unfinished flows (their unfinished steps count as failures)"
    for pid in "${FLOW_PIDS[@]}"; do kill -0 "$pid" 2>/dev/null && { pkill -TERM -P "$pid" 2>/dev/null; kill "$pid" 2>/dev/null; }; done
    for u in "${USERS[@]}"; do
      [ -e "$RUN_DIR/students/$u/finished" ] || printf '%s,%s,%s,%s,%s,%s\n' "$u" timeout "$(now_ms)" $((RUN_TIMEOUT * 1000)) 124 0 >> "$STEPS_CSV"
    done
    break
  fi
  if [ $((SECONDS - last)) -ge 15 ]; then
    last=$SECONDS
    say "  t+$((SECONDS - FLOWS_START))s: $alive flows running; steps done $(($(wc -l < "$STEPS_CSV") - 1)), failed $(awk -F, 'NR > 1 && $6 == 0 {n++} END {print n + 0}' "$STEPS_CSV")"
  fi
  sleep 2
done
wait "${FLOW_PIDS[@]}" 2>/dev/null
FLOWS_WALL=$((SECONDS - FLOWS_START))
stop_monitors
oom_snapshot after; write_oom_txt; collect_container_facts
{
  echo "students=$N"; echo "wave_size=$WAVE"; echo "wave_gap=$GAP"; echo "wall_s=$FLOWS_WALL"
  echo "run_id=$RUN_ID"; echo "cli=$CLI"
} > "$RUN_DIR/meta.env"

section "Report"
python3 -B "$TB_HELPERS/report.py" "$RUN_DIR" --max-failures "$MAX_FAIL" --max-p95-apply "$MAX_P95_APPLY" \
  --max-portal-p95-ms "$MAX_PORTAL_P95" --max-readyz-failures "$MAX_READYZ_FAIL" | tee "$RUN_DIR/report.txt" | mask
report_rc=${PIPESTATUS[0]}
AREA=thresholds
case $report_rc in
  0) pass "load thresholds met (details above; also in $RUN_DIR/report.txt)" ;;
  1) fail "load thresholds NOT met (see the Verdict lines above)" ;;
  *) fail "the report could not be produced (status $report_rc)" ;;
esac
say "  raw data: $STEPS_CSV  $RUN_DIR/stats.csv  $RUN_DIR/portal.csv"
exit 0   # the exit trap runs the cleanup and prints the summary; its status is the script's
