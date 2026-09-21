#!/usr/bin/env bash
# End-to-end test of the tofu-basics workshop for ONE student, against a running stack.
# Runs the labs' real commands as that student through the terminal container and checks the output the labs
# quote, plus the portal's view of the cloud. Exit status: 0 = every check passed, 1 = a check failed, 2 = could
# not run (stack not up, unknown account, subscription not empty). Nothing is left behind: the exit trap destroys
# what the run created and verifies through the portal that the subscription is empty again.
#
#   tests/e2e.sh                      # student01, all areas except the restart test
#   tests/e2e.sh --student 3          # student03
#   tests/e2e.sh --with-restart       # also restarts workshop_cloud_host (about 1 minute)
#   tests/e2e.sh --only policy,curl_ca
#   tests/e2e.sh --dry-run            # print what would run; touches no stack
# See tests/README.md for what each area proves, and what none of this can prove.

set -u
set -o pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=lib.sh
. "$HERE/lib.sh"

AREA_ORDER=(track_a track_b policy curl_ca security restart)
declare -A AREA_FILE=([track_a]=10_track_a.sh [track_b]=20_track_b.sh [policy]=30_policy.sh [curl_ca]=40_curl_ca.sh [restart]=50_restart.sh [security]=60_security.sh)
declare -A AREA_DESC=(
  [track_a]="Labs 0-3: the offline sandbox (init, validate, plan, apply, change, destroy, state left behind)"
  [track_b]="Labs 4-10: Dojo Cloud lifecycle (init, apply, site, policy in the labs, drift, in-place vs replace, quota, destroy)"
  [policy]="every policy violation with the real message text, fast, changing nothing"
  [curl_ca]="Lab 4: curl to the management endpoint works without -k (CURL_CA_BUNDLE / SSL_CERT_FILE)"
  [security]="cross-tenant access, forged tokens and headers, secrets, reaching cloud-host, student-container isolation (T9.2, T9.8)"
  [restart]="restart of workshop_cloud_host: the container comes back by itself (opt-in, --with-restart)")

usage() {
  cat <<EOF
Usage: tests/e2e.sh [options]

  --student N|NAME     which student account to drive (default 1 = ${STUDENT_PREFIX}01). Its subscription must be EMPTY
                       (the run destroys what it creates and would otherwise not know what is whose).
  --only A,B           run only these areas (names below)
  --skip A,B           run everything except these areas
  --with-restart       include the 'restart' area: restarts \$CLOUD_HOST_CONTAINER, ~1 minute
  --purge-first        if the student's subscription is not empty, empty it through the facilitator Purge first
  --no-purge           never use the facilitator Purge as a cleanup fallback (leftovers are then only reported)
  --keep               do not destroy or delete anything at the end (deployments and ~/e2e-* stay for inspection)
  --ready-bound S      restart area: seconds within which /readyz must be 200 again (default 45)
  --site-bound S       restart area: seconds within which the site must answer again (default 60)
  --policy-max S       policy area: seconds within which a refused apply must fail (default 30)
  --dry-run            print the commands and checks; do not touch any container
  -h, --help

Areas (run in this order):
$(for a in "${AREA_ORDER[@]}"; do printf '  %-9s %s\n' "$a" "${AREA_DESC[$a]}"; done)

Environment: CONTAINER_CLI (default podman, else docker), TERMINAL_CONTAINER, CLOUD_API_CONTAINER,
CLOUD_HOST_CONTAINER, TMPDIR (where the per-run directory with the logs goes).
EOF
}

STUDENT_ARG=1; ONLY=""; SKIP=""; WITH_RESTART=0; PURGE_FIRST=0
READY_BOUND=45; SITE_BOUND=60; POLICY_MAX_SECS=30
while [ $# -gt 0 ]; do
  case $1 in
    --student) [ $# -ge 2 ] || die "--student needs a value"; STUDENT_ARG=$2; shift ;;
    --only) [ $# -ge 2 ] || die "--only needs a value"; ONLY=$2; shift ;;
    --skip) [ $# -ge 2 ] || die "--skip needs a value"; SKIP=$2; shift ;;
    --with-restart) WITH_RESTART=1 ;;
    --purge-first) PURGE_FIRST=1 ;;
    --no-purge) TB_NO_PURGE=1 ;;
    --keep) TB_KEEP=1 ;;
    --ready-bound) [ $# -ge 2 ] || die "--ready-bound needs a value"; READY_BOUND=$2; shift ;;
    --site-bound) [ $# -ge 2 ] || die "--site-bound needs a value"; SITE_BOUND=$2; shift ;;
    --policy-max) [ $# -ge 2 ] || die "--policy-max needs a value"; POLICY_MAX_SECS=$2; shift ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; die "unknown option: $1" ;;
  esac
  shift
done

# Which areas run.
SELECTED=()
for a in "${AREA_ORDER[@]}"; do
  if [ -n "$ONLY" ]; then case ",$ONLY," in *",$a,"*) ;; *) continue ;; esac
  else [ "$a" = restart ] && [ "$WITH_RESTART" = 0 ] && continue; fi
  case ",$SKIP," in *",$a,"*) continue ;; esac
  SELECTED+=("$a")
done
for a in ${ONLY//,/ } ${SKIP//,/ }; do [ -n "${AREA_FILE[$a]:-}" ] || die "unknown area '$a' (areas: ${AREA_ORDER[*]})"; done
[ "${#SELECTED[@]}" -gt 0 ] || die "no area selected"

pick_cli
init_run e2e
TB_TITLE="tofu-basics e2e"
TB_CLEANUP_HOOK=e2e_cleanup
SAFE_TO_CLEAN=0
TB_NO_PURGE=${TB_NO_PURGE:-0}
export DRY_RUN TB_NO_PURGE READY_BOUND SITE_BOUND POLICY_MAX_SECS
install_exit_trap

STUDENT=""; WORK=""; REPO=""

# Clone the starter repo once per run (Lab 0). Falls back to a copy of content/sample-repo if Forgejo has no repo
# yet, and says so: the fallback does not test the Forgejo seeding.
prepare_repo() {
  [ -e "$RUN_DIR/repo-ready" ] && return 0
  local url="$TB_STARTER_URL_BASE/$FORGEJO_ORG/$FORGEJO_REPO.git"
  as_student "$STUDENT" "mkdir -p '$WORK' && cd '$WORK' && git clone -q $url" 120 clone
  if is_dry; then :
  elif [ "$RC" -eq 0 ]; then
    as_student "$STUDENT" "test -f '$REPO/sandbox/main.tf' && test -f '$REPO/main.tf' && echo repo-ok" 30 repo-check
    out_has repo-ok || { say "  cloned $url but it lacks sandbox/main.tf or main.tf"; return 1; }
  else
    warn "git clone of $url failed (rc=$RC); using a copy of content/sample-repo instead. Lab 0's clone is NOT tested."
    tail -n 5 "$OUT" | say_block "        | "
    "$CLI" exec -u root "$TERMINAL_CONTAINER" rm -rf "$REPO" >/dev/null 2>&1
    "$CLI" cp "$TB_WORKSHOP_DIR/content/sample-repo/." "$TERMINAL_CONTAINER:$REPO" >/dev/null 2>&1 \
      || { say "  could not copy the starter repo into the terminal container"; return 1; }
    "$CLI" exec -u root "$TERMINAL_CONTAINER" chown -R "$STUDENT:$STUDENT" "$REPO"
    as_student "$STUDENT" "cd '$REPO' && git init -q -b main && git add -A && git commit -q -m seed && echo repo-ok" 60 repo-init
    out_has repo-ok || { say "  could not initialise the local starter repo"; return 1; }
  fi
  : > "$RUN_DIR/repo-ready"
  register_tofu_dir "$STUDENT" "$REPO"
}

# Called by each area file to stop that area (the run continues with the next one).
abort_area() { say "  ABORT  area $AREA: $*"; record FAIL "$AREA" "area aborted: $*"; exit 3; }

run_area() {
  local name=$1 rc
  section "Area: $name: ${AREA_DESC[$name]}"
  ( AREA=$name; SEQ=0; . "$HERE/e2e/${AREA_FILE[$name]}" && "area_$name" )
  rc=$?
  if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ]; then record FAIL "$name" "area exited with status $rc"; say "  FAIL  area $name exited with status $rc"; fi
}

e2e_cleanup() {
  AREA=cleanup
  # Never touch a subscription the preflight refused: a student who already had resources must keep them.
  if [ -z "$STUDENT" ] || [ "$SAFE_TO_CLEAN" != 1 ]; then say "  nothing to clean (the run stopped before it started)"; return 0; fi
  if ! container_running "$CLOUD_HOST_CONTAINER"; then
    say "  $CLOUD_HOST_CONTAINER is not running: starting it so the destroy can work"
    "$CLI" start "$CLOUD_HOST_CONTAINER" >/dev/null 2>&1
  fi
  wait_ready 90 || say "  cloud-api is not ready: the destroy below may fail, the portal check then decides"
  destroy_registered 1
  verify_empty "$STUDENT"
  remove_workdirs
}

# ---- go ------------------------------------------------------------------------------------------------------
section "tofu-basics e2e ($([ "$DRY_RUN" = 1 ] && echo dry-run || echo live)) with $CLI, areas: ${SELECTED[*]}"
say "  run dir: $RUN_DIR   (session.log has every command and its output, results.tsv every check)"
preflight || die "preflight failed: the stack is not ready for a test"
STUDENT=$(user_name "$STUDENT_ARG")
WORK=/home/$STUDENT/e2e-$RUN_ID
REPO=$WORK/$FORGEJO_REPO
export STUDENT WORK REPO
safe_workdir "$WORK" || die "refusing to use an unsafe work directory name: $WORK"
say "  student: $STUDENT   work dir (in $TERMINAL_CONTAINER): $WORK"
if ! is_dry; then
  "$CLI" exec "$TERMINAL_CONTAINER" id -u "$STUDENT" >/dev/null 2>&1 || die "account '$STUDENT' does not exist (STUDENT_COUNT=$STUDENT_COUNT_ACTUAL)"
  check_credentials "$STUDENT" || die "no Dojo Cloud credentials for $STUDENT"
  portal_counts "$STUDENT"
  if [ "$N_RG" != 0 ] || [ "$N_CG" != 0 ]; then
    if [ "$PURGE_FIRST" = 1 ]; then
      say "  $STUDENT's subscription is not empty ($N_RG resource groups, $N_CG container groups): purging it (--purge-first)"
      portal_purge "$STUDENT"
    else
      die "$STUDENT's subscription is not empty ($N_RG resource groups, $N_CG container groups). Use another --student, or --purge-first to empty it."
    fi
  fi
fi
SAFE_TO_CLEAN=1
register_workdir "$STUDENT" "$WORK"

for a in "${SELECTED[@]}"; do run_area "$a"; done
# The exit trap now runs the cleanup and prints the summary; its status is the script's.
exit 0
