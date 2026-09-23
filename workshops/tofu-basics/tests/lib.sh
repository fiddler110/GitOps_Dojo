#!/usr/bin/env bash
# shellcheck shell=bash disable=SC2034
# Shared helpers for the tofu-basics end-to-end (tests/e2e.sh) and load (tests/load.sh) scripts.
# Source it; do not run it. See tests/README.md for what the scripts prove and how to run them.
#
# How the scripts drive the stack (all of it works from the HOST, with podman or docker):
#   * A student is a Linux account (student01..NN) inside the container `workshop_terminal`. as_student runs a
#     command there as that user through a login zsh: /etc/zsh/zshenv then asks the credential broker
#     (SO_PEERCRED) for that user's ARM_* / TF_VAR_* / CA-bundle variables, exactly like a real shell.
#   * The portal API (/cloud/api/*) and /readyz are called from INSIDE the cloud-api container against
#     127.0.0.1:8080, by a helper script that reads that container's own GATEWAY_TOKEN. So this file never sees,
#     passes or logs the token, and no session cookie or gateway URL is needed. It does not exercise Caddy.
#
# Errors vs failures: scripts using this library do NOT use `set -e`, because a failed check must not stop the
# run. A check that fails is recorded (FAIL) and the run carries on; die() is for "cannot continue at all".
# The exit trap ALWAYS runs the cleanup hook (destroy what the run created, verify the portal is empty).

if [ -z "${BASH_VERSION:-}" ] || [ "${BASH_VERSINFO[0]}" -lt 5 ]; then
  echo "tests/lib.sh needs bash 5 or newer (found ${BASH_VERSION:-none})" >&2
  return 2 2>/dev/null || exit 2
fi
[ -n "${_TB_LIB_LOADED:-}" ] && return 0
_TB_LIB_LOADED=1

TB_LIB_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TB_WORKSHOP_DIR=$(cd "$TB_LIB_DIR/.." && pwd)
TB_REPO_ROOT=$(cd "$TB_WORKSHOP_DIR/../.." && pwd)
TB_HELPERS=$TB_LIB_DIR/helpers

# ---- configuration (override from the environment) ---------------------------------------------------------------
: "${TERMINAL_CONTAINER:=workshop_terminal}"
: "${CLOUD_API_CONTAINER:=workshop_cloud_api}"
: "${CLOUD_HOST_CONTAINER:=workshop_cloud_host}"
: "${STUDENT_PREFIX:=student}"          # replaced by the terminal container's own STUDENT_PREFIX at preflight
: "${TB_STARTER_URL_BASE:=http://git-server:3000}"
DRY_RUN=${DRY_RUN:-0}
CLI=${CONTAINER_CLI:-}
RUN_DIR=""; RUN_LOG=""; RESULTS=""; TOFU_DIRS=""; WORKDIRS_FILE=""; LOG_DIR=""; TMP_DIR=""; RUN_ID=""; SESSION_LOG=""
AREA=main; SEQ=0
RC=0; OUT=/dev/null; SECS=0; SECS_MS=0
P_FILE=/dev/null; P_STATUS=0; P_MS=0
STARTED_AT=$SECONDS
TB_CLEANUP_HOOK=""
TB_KEEP=0
TB_TITLE="tofu-basics test"

FORGEJO_ORG=$(sed -n 's/^FORGEJO_ORG=//p' "$TB_WORKSHOP_DIR/workshop.env" 2>/dev/null | head -n1)
FORGEJO_REPO=$(sed -n 's/^FORGEJO_REPO=//p' "$TB_WORKSHOP_DIR/workshop.env" 2>/dev/null | head -n1)
: "${FORGEJO_ORG:=iac-team}"; : "${FORGEJO_REPO:=tofu-basics}"

# ---- small utilities ---------------------------------------------------------------------------------------------
is_dry() { [ "${DRY_RUN:-0}" = 1 ]; }

# Hides anything that looks like a secret in text passing through (logs, evidence). Nothing the scripts run should
# print a secret, this is the belt to that pair of braces.
mask() {
  sed -E \
    -e 's/dojo~[0-9a-fA-F]{6,}/dojo~<masked>/g' \
    -e 's/eyJ[A-Za-z0-9_-]{8,}(\.[A-Za-z0-9_-]*)*/<jwt-masked>/g' \
    -e 's/((X-Gateway-Token|Authorization|client_secret|ARM_CLIENT_SECRET|GATEWAY_TOKEN|STUDENT_PASSWORD|TTYD_[A-Z_]+|SIGNING_KEY|password|passwd|secret|token)"?[ ]*[=:][ ]*"?)[^ ,"&}]+/\1<masked>/Ig'
}

_c() { if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then printf '\033[%sm' "$1"; fi; }

# say TEXT...: to stdout and to the run log, masked. Multi-line text is fine.
say() {
  local text
  text=$(printf '%s' "$*" | mask)
  printf '%s\n' "$text"
  if [ -n "${RUN_LOG:-}" ]; then printf '%s\n' "$text" >> "$RUN_LOG"; fi
  return 0
}
say_block() { local prefix=$1 line; while IFS= read -r line; do say "${prefix}${line}"; done; }
warn() { say "WARN  $*"; }
dry() { say "  DRY   $*"; }
die() { local code=2; if [ "$#" -gt 1 ]; then code=$2; fi; printf 'ERROR: %s\n' "$1" >&2; exit "$code"; }
section() { say ""; say "== $*"; }

now_ms() { local t=${EPOCHREALTIME/[.,]/}; echo $((t / 1000)); }
fmt_secs() { local ms=$1; printf '%d.%d' $((ms / 1000)) $(((ms % 1000) / 100)); }   # 12345 -> 12.3

# ---- the container CLI -------------------------------------------------------------------------------------------
pick_cli() {
  if [ -z "$CLI" ]; then
    if command -v podman >/dev/null 2>&1; then CLI=podman
    elif command -v docker >/dev/null 2>&1; then CLI=docker
    elif is_dry; then CLI=podman
    else die "no container CLI found: install podman or docker, or set CONTAINER_CLI"; fi
  fi
  if ! is_dry && ! command -v "$CLI" >/dev/null 2>&1; then die "CONTAINER_CLI '$CLI' is not on PATH"; fi
}

# ---- run directory, results ---------------------------------------------------------------------------------------
# One directory per run under $TMPDIR (default /tmp). It is the only host directory the scripts write to.
init_run() {  # init_run TAG
  local base=${TMPDIR:-/tmp}
  RUN_DIR=$(mktemp -d "${base%/}/tofu-basics-$1.XXXXXX") || die "cannot create a run directory under $base"
  : > "$RUN_DIR/.tofu-basics-run"
  LOG_DIR=$RUN_DIR/logs; TMP_DIR=$RUN_DIR/tmp
  mkdir -p "$LOG_DIR" "$TMP_DIR"
  RUN_LOG=$RUN_DIR/run.log; SESSION_LOG=$RUN_DIR/session.log; RESULTS=$RUN_DIR/results.tsv; TOFU_DIRS=$RUN_DIR/tofu-dirs; WORKDIRS_FILE=$RUN_DIR/workdirs
  : > "$RUN_LOG"; : > "$RESULTS"; : > "$TOFU_DIRS"; : > "$WORKDIRS_FILE"
  RUN_ID=${RUN_DIR##*.}; RUN_ID=${RUN_ID,,}
  STARTED_AT=$SECONDS
}

record() { printf '%s\t%s\t%s\n' "$1" "${2:-$AREA}" "$3" >> "$RESULTS"; }   # STATUS AREA NAME
count_status() { awk -F'\t' -v s="$1" '$1 == s {n++} END {print n + 0}' "$RESULTS" 2>/dev/null; }

# ---- running things as a student ---------------------------------------------------------------------------------
# as_student USER "command string" [TIMEOUT_SECONDS=300] [LABEL]
#   Runs the string in a login zsh as that user in the terminal container (cwd = their home).
#   Sets RC (exit status; 124 = timed out), SECS / SECS_MS (wall time) and OUT (a file with stdout+stderr, masked).
#   The command string reaches zsh as ONE argument: no extra layer of quoting to get wrong.
#   Variables named in TB_PASS_ENV (space-separated, exported by the caller) are passed through by NAME (`-e NAME`),
#   so a secret such as the Forgejo password never appears in a command line or a log.
as_student() {
  local user=$1 cmd=$2 tmo=${3:-300} label=${4:-cmd} t0 t1 safe v
  local -a xenv=(); for v in ${TB_PASS_ENV:-}; do xenv+=(-e "$v"); done
  SEQ=$((SEQ + 1)); safe=${label//[^A-Za-z0-9_.-]/_}
  OUT="$LOG_DIR/$(printf '%s-%03d-%s' "${AREA:-x}" "$SEQ" "$safe")-$user.log"
  if is_dry; then
    dry "as $user (limit ${tmo}s): $cmd"
    : > "$OUT"; RC=0; SECS=0.0; SECS_MS=0
    return 0
  fi
  t0=$(now_ms)
  timeout -k 5 "$((tmo + 30))" "$CLI" exec -u "$user" -w "/home/$user" -e "HOME=/home/$user" "${xenv[@]}" \
    "$TERMINAL_CONTAINER" timeout -k 5 "$tmo" zsh -lc "$cmd" 2>&1 | mask > "$OUT"
  RC=${PIPESTATUS[0]}
  t1=$(now_ms); SECS_MS=$((t1 - t0)); SECS=$(fmt_secs "$SECS_MS")
  {
    printf '$ [%s %s] %s\n' "$user" "$label" "$cmd"
    cat "$OUT"
    printf '[rc=%s, %ss]\n\n' "$RC" "$SECS"
  } | mask >> "$SESSION_LOG"
  return 0
}

flat() { tr -s '[:space:]' ' ' < "$1"; }          # a file with all runs of whitespace (incl. newlines) as one space
flat_out() { flat "$OUT"; }
out_has() { flat "$OUT" | grep -qF -- "$(printf '%s' "$1" | tr -s '[:space:]' ' ')"; }
out_lines() { grep -c . "$OUT" 2>/dev/null || true; }

# ---- assertions ---------------------------------------------------------------------------------------------------
pass() { record PASS "$AREA" "$1"; say "  $(_c 32)PASS$(_c 0)  $1"; }
fail() {  # fail DESC [EVIDENCE LINE...]
  local desc=$1; shift
  record FAIL "$AREA" "$desc"; say "  $(_c 31)FAIL$(_c 0)  $desc"
  local line; for line in "$@"; do say "          $line"; done
  return 0
}
_evidence() {
  say "          rc=$RC time=${SECS}s   (full log: $OUT)"
  tail -n 20 "$OUT" 2>/dev/null | say_block "          | "
}
# Every expect_* uses the result of the LAST as_student call ($RC, $OUT, $SECS_MS). In --dry-run they only print.
expect_rc() {  # expect_rc DESC WANT   (WANT: 0, or "nonzero")
  local desc=$1 want=$2 ok=0
  if is_dry; then dry "check: $desc (exit status $want)"; return 0; fi
  if [ "$want" = nonzero ]; then [ "$RC" -ne 0 ] && ok=1; else [ "$RC" -eq "$want" ] && ok=1; fi
  if [ "$ok" = 1 ]; then pass "$desc"; else fail "$desc: expected exit status $want"; _evidence; fi
}
expect_has() {  # expect_has DESC NEEDLE...   all needles present (whitespace-insensitive, fixed strings)
  local desc=$1 n; shift
  local missing=()
  if is_dry; then dry "check: $desc (output has: $*)"; return 0; fi
  for n in "$@"; do out_has "$n" || missing+=("$n"); done
  if [ "${#missing[@]}" -eq 0 ]; then pass "$desc"
  else fail "$desc: missing in output"; for n in "${missing[@]}"; do say "          expected: $n"; done; _evidence; fi
}
expect_lacks() {  # expect_lacks DESC NEEDLE...
  local desc=$1 n; shift
  local found=()
  if is_dry; then dry "check: $desc (output lacks: $*)"; return 0; fi
  for n in "$@"; do if out_has "$n"; then found+=("$n"); fi; done
  if [ "${#found[@]}" -eq 0 ]; then pass "$desc"
  else fail "$desc: unexpectedly present in output"; for n in "${found[@]}"; do say "          found: $n"; done; _evidence; fi
}
expect_secs_le() {  # expect_secs_le DESC MAX_SECONDS   (time of the last as_student call)
  local desc=$1 max=$2
  if is_dry; then dry "check: $desc (took at most ${max}s)"; return 0; fi
  if [ "$SECS_MS" -le $((max * 1000)) ]; then pass "$desc (${SECS}s <= ${max}s)"
  else fail "$desc: took ${SECS}s, limit ${max}s"; fi
}
expect_eq() {  # expect_eq DESC EXPECTED ACTUAL
  if is_dry; then dry "check: $1 (expect '$2')"; return 0; fi
  if [ "$2" = "$3" ]; then pass "$1"; else fail "$1" "expected: $2" "actual:   $3"; fi
}
expect_ge() {  # expect_ge DESC ACTUAL MIN (integers)
  if is_dry; then dry "check: $1 (>= $3)"; return 0; fi
  if [ "${2:-0}" -ge "$3" ] 2>/dev/null; then pass "$1"; else fail "$1" "expected at least $3, got '${2:-}'"; fi
}
expect_le() {  # expect_le DESC ACTUAL MAX (integers)
  if is_dry; then dry "check: $1 (<= $3)"; return 0; fi
  if [ "${2:-0}" -le "$3" ] 2>/dev/null; then pass "$1"; else fail "$1" "expected at most $3, got '${2:-}'"; fi
}
expect_ok() {  # expect_ok DESC cmd args...   passes when the command (run on the HOST) exits 0
  local desc=$1; shift
  if is_dry; then dry "check: $desc ($*)"; return 0; fi
  if "$@" >/dev/null 2>&1; then pass "$desc"; else fail "$desc: '$*' failed"; fi
}

# ---- portal API (through the cloud-api container, see the header) ----------------------------------------------------
# portal_call METHOD PATH [USER] [BODY]   USER: '-' none (default), '@facilitator', or a username.
# Sets P_FILE (JSON: {"status","ms","body"}), P_STATUS and P_MS.
portal_call() {
  local method=$1 path=$2 user=${3:--} body=${4-}
  P_FILE="$TMP_DIR/portal.$BASHPID.json"
  if is_dry; then
    dry "portal $method $path as ${user} ${body:+body=$body}"
    printf '{"status":200,"ms":0,"body":{}}\n' > "$P_FILE"; P_STATUS=200; P_MS=0
    return 0
  fi
  if [ -n "$body" ]; then
    "$CLI" exec -i "$CLOUD_API_CONTAINER" python3 - "$method" "$path" "$user" "$body" < "$TB_HELPERS/cloud_http.py" > "$P_FILE" 2> "$P_FILE.err"
  else
    "$CLI" exec -i "$CLOUD_API_CONTAINER" python3 - "$method" "$path" "$user" < "$TB_HELPERS/cloud_http.py" > "$P_FILE" 2> "$P_FILE.err"
  fi
  if ! grep -q '"status"' "$P_FILE" 2>/dev/null; then
    printf '{"status":0,"ms":0,"body":%s}\n' "$(python3 -B -c 'import json,sys; print(json.dumps(sys.stdin.read()[-300:]))' < "$P_FILE.err")" > "$P_FILE"
  fi
  P_STATUS=$(pj status); P_MS=$(pj ms)
  printf 'portal %s %s as %s -> %s (%s ms)\n' "$method" "$path" "$user" "$P_STATUS" "$P_MS" >> "$SESSION_LOG"
}
pj() { python3 -B "$TB_HELPERS/jq.py" get "$1" < "$P_FILE"; }                  # value at PATH in the last portal answer
pj_len() { python3 -B "$TB_HELPERS/jq.py" len "$1" < "$P_FILE"; }
pj_pluck() { python3 -B "$TB_HELPERS/jq.py" pluck "$1" "$2" < "$P_FILE"; }
pj_count() { python3 -B "$TB_HELPERS/jq.py" count "$@" < "$P_FILE"; }

pj_json() { python3 -B "$TB_HELPERS/jq.py" json "$1" < "$P_FILE"; }              # the value at PATH as compact JSON
expect_pj_eq() {  # expect_pj_eq DESC PATH EXPECTED   (against the last portal answer)
  local actual
  if is_dry; then dry "check: $1 (portal $2 == '$3')"; return 0; fi
  actual=$(pj "$2")
  if [ "$actual" = "$3" ]; then pass "$1"; else fail "$1" "portal $2: expected '$3', got '${actual:0:200}' (HTTP $P_STATUS)"; fi
}
expect_pj_has() {  # expect_pj_has DESC PATH NEEDLE   (substring of the value)
  local actual
  if is_dry; then dry "check: $1 (portal $2 contains '$3')"; return 0; fi
  actual=$(pj "$2")
  if printf '%s' "$actual" | grep -qF -- "$3"; then pass "$1"; else fail "$1" "portal $2: '$3' not found in '${actual:0:300}' (HTTP $P_STATUS)"; fi
}

readyz_ok() { portal_call GET /readyz -; [ "$P_STATUS" = 200 ]; }
# wait_until SECONDS INTERVAL cmd args...   -> 0 when cmd succeeded in time; WAITED = seconds spent
wait_until() {
  local limit=$1 every=$2 t0=$SECONDS; shift 2
  if is_dry; then dry "wait up to ${limit}s (every ${every}s) until: $*"; WAITED=0; return 0; fi
  until "$@"; do
    if [ $((SECONDS - t0)) -ge "$limit" ]; then WAITED=$((SECONDS - t0)); return 1; fi
    sleep "$every"
  done
  WAITED=$((SECONDS - t0)); return 0
}
wait_ready() {  # wait_ready [SECONDS=120]: cloud-api /readyz returns 200
  if wait_until "${1:-120}" 2 readyz_ok; then say "  cloud-api /readyz is 200 (waited ${WAITED}s)"; return 0; fi
  say "  cloud-api /readyz did not reach 200 within ${1:-120}s (last status $P_STATUS): $(pj body.detail)"; return 1
}

declare -A _SUB_CACHE=()
portal_sub() {  # subscription id of USER (from /me); empty if unknown
  if is_dry; then echo "00000000-0000-0000-0000-dry-run-sub"; return 0; fi
  if [ -z "${_SUB_CACHE[$1]:-}" ]; then
    portal_call GET /cloud/api/me "$1"
    _SUB_CACHE[$1]=$(pj body.subscriptionId)
  fi
  echo "${_SUB_CACHE[$1]}"
}
# portal_counts USER -> N_RG (resource groups), N_CG (container groups), QUOTA_USED, from the student's own portal view
portal_counts() {
  if is_dry; then N_RG=0; N_CG=0; QUOTA_USED=0; return 0; fi
  portal_call GET '/cloud/api/overview?scope=mine' "$1"
  N_RG=$(pj_len body.resourceGroups); N_CG=$(pj_len body.containerGroups)
  portal_call GET /cloud/api/me "$1"; QUOTA_USED=$(pj body.quota.containerGroups.used)
  : "${QUOTA_USED:=0}"
}
# activity_count USER OPERATION [STATUS] -> prints how many of the user's activity events match (exact operation text)
activity_count() {
  if is_dry; then echo 0; return 0; fi
  portal_call GET '/cloud/api/activity?scope=mine&limit=500' "$1"
  if [ -n "${3:-}" ]; then pj_count body.events "operation=$2" "status=$3"; else pj_count body.events "operation=$2"; fi
}
# leftover_owners USER... -> prints the users (of those given) that still own a resource group or container group
leftover_owners() {
  local users=" $* " owner
  if is_dry; then return 0; fi
  portal_call GET '/cloud/api/overview?scope=class' @facilitator
  if [ "$P_STATUS" != 200 ]; then echo "PORTAL-UNREADABLE(status $P_STATUS)"; return 0; fi
  { pj_pluck body.resourceGroups owner; pj_pluck body.containerGroups owner; } | sort -u | while IFS= read -r owner; do
    case "$users" in *" $owner "*) echo "$owner" ;; esac
  done
}
portal_purge() {  # portal_purge USER: facilitator empties that user's subscription. Sets nothing; logs the outcome.
  local sub; sub=$(portal_sub "$1")
  portal_call POST /cloud/api/admin/purge @facilitator "{\"subscriptionId\": \"$sub\"}"
  say "  purge $1: status $P_STATUS $(pj body.removed | mask)"
}

# ---- student sites and files ---------------------------------------------------------------------------------------------
# The class URL path the labs use is /cloud/site/<label>/ ; from a terminal it is reached on cloud-api:8080 (Lab 5's troubleshooting
# box). Through the gateway the same path needs a browser session, which these scripts do not have.
site_get() {  # site_get USER LABEL  -> OUT holds the page and a final "HTTP <code>" line
  as_student "$1" "curl -s -m 10 -w '\nHTTP %{http_code}\n' http://cloud-api:8080/cloud/site/$2/" 40 site
}
site_has() { site_get "$1" "$2"; [ "$RC" -eq 0 ] && out_has "$3"; }   # site_has USER LABEL NEEDLE (for wait_until)
cg_state() {  # cg_state USER -> "Running", "Terminated", ... of the user's first container group ("" if none)
  if is_dry; then echo Running; return 0; fi
  portal_call GET '/cloud/api/overview?scope=mine' "$1"; pj body.containerGroups.0.state
}
activity_total() {  # activity_total USER -> number of the user's activity events
  if is_dry; then echo 0; return 0; fi
  portal_call GET '/cloud/api/activity?scope=mine&limit=500' "$1"; pj_len body.events
}
activity_failed() {  # activity_failed USER -> number of Failed events
  if is_dry; then echo 0; return 0; fi
  portal_call GET '/cloud/api/activity?scope=mine&limit=500' "$1"; pj_count body.events status=Failed
}
# put_file USER PATH  (content on stdin): writes a file inside the terminal container as USER (base64, so no quoting problems)
put_file() {
  local user=$1 path=$2 b64
  b64=$(python3 -B -c 'import base64,sys; print(base64.b64encode(sys.stdin.buffer.read()).decode())')
  if is_dry; then dry "write $path ($(printf '%s' "$b64" | wc -c) base64 bytes) as $user"; return 0; fi
  as_student "$user" "mkdir -p \"\$(dirname '$path')\" && echo '$b64' | base64 -d > '$path'" 60 putfile
}
# expect_wait DESC SECONDS cmd args...   passes when cmd succeeds within SECONDS (polls every 2 s); evidence = last as_student output
expect_wait() {
  local desc=$1 secs=$2; shift 2
  if is_dry; then dry "wait up to ${secs}s until: $desc"; return 0; fi
  if wait_until "$secs" 2 "$@"; then pass "$desc (after ${WAITED}s)"; else fail "$desc: still not true after ${secs}s"; _evidence; fi
}
# lab_line LABFILE PREFIX -> the first line of content/lab/LABFILE that starts with PREFIX (the labs' own command); non-zero if none.
# The e2e scripts run the labs' real edit commands this way, so a lab that changes makes the test follow it (or fail loudly).
lab_line() {
  local line
  line=$(awk -v p="$2" 'index($0, p) == 1 {print; exit}' "$TB_WORKSHOP_DIR/content/lab/$1")
  [ -n "$line" ] || { say "  cannot find a line starting with [$2] in content/lab/$1"; return 1; }
  printf '%s' "$line"
}
# lab_block LABFILE START_REGEX END_REGEX -> lines from the first START match through the first END match after it
lab_block() {
  local block
  block=$(awk -v s="$2" -v e="$3" '$0 ~ s {on=1} on {print} on && $0 ~ e {exit}' "$TB_WORKSHOP_DIR/content/lab/$1")
  [ -n "$block" ] || { say "  cannot find the block [$2 .. $3] in content/lab/$1"; return 1; }
  printf '%s' "$block"
}

# ---- the stack, and the student's environment -------------------------------------------------------------------------
container_running() { [ "$("$CLI" inspect -f '{{.State.Running}}' "$1" 2>/dev/null)" = true ]; }
terminal_env() { "$CLI" exec "$TERMINAL_CONTAINER" printenv "$1" 2>/dev/null; }

user_name() {  # user_name 3 -> student03 ; user_name student07 -> student07
  case "$1" in
    ''|*[!0-9]*) echo "$1" ;;
    *) printf '%s%02d' "$STUDENT_PREFIX" "$((10#$1))" ;;
  esac
}

# preflight [USER...]: containers up, /readyz 200, accounts exist and hold Dojo Cloud credentials.
# Sets STUDENT_COUNT_ACTUAL. Returns non-zero (after saying why) if the run cannot go on.
preflight() {
  local c u ok=0
  section "Preflight"
  if is_dry; then dry "check containers $TERMINAL_CONTAINER $CLOUD_API_CONTAINER $CLOUD_HOST_CONTAINER are running, /readyz is 200, accounts exist"; STUDENT_COUNT_ACTUAL=99; return 0; fi
  for c in "$TERMINAL_CONTAINER" "$CLOUD_API_CONTAINER" "$CLOUD_HOST_CONTAINER"; do
    if container_running "$c"; then say "  $c is running"; else say "  $c is NOT running (start the stack: cd engine && ./run.sh tofu-basics)"; ok=1; fi
  done
  [ "$ok" = 0 ] || return 1
  STUDENT_PREFIX=$(terminal_env STUDENT_PREFIX || true); : "${STUDENT_PREFIX:=student}"
  STUDENT_COUNT_ACTUAL=$(terminal_env STUDENT_COUNT || true)
  if [ -z "$STUDENT_COUNT_ACTUAL" ]; then
    STUDENT_COUNT_ACTUAL=$(sed -n 's/^STUDENT_COUNT=//p' "$TB_REPO_ROOT/engine/.env" 2>/dev/null | head -n1)   # only this key is read from .env
  fi
  : "${STUDENT_COUNT_ACTUAL:=0}"
  say "  accounts: ${STUDENT_PREFIX}01..$(printf '%02d' "$STUDENT_COUNT_ACTUAL") (STUDENT_COUNT=$STUDENT_COUNT_ACTUAL)"
  wait_ready 120 || return 1
  for u in "$@"; do
    if ! "$CLI" exec "$TERMINAL_CONTAINER" id -u "$u" >/dev/null 2>&1; then say "  account $u does not exist in $TERMINAL_CONTAINER"; return 1; fi
  done
  return 0
}
# check_credentials USER: the broker gave this shell ARM_* variables and a CA bundle (never printed, only tested).
check_credentials() {
  as_student "$1" 'test -n "$ARM_CLIENT_ID" && test -n "$ARM_CLIENT_SECRET" && test -n "$ARM_SUBSCRIPTION_ID" && test -n "$SSL_CERT_FILE" && test -s "$SSL_CERT_FILE" && echo creds-ok' 60 creds
  if is_dry; then return 0; fi
  if [ "$RC" -eq 0 ] && out_has creds-ok; then return 0; fi
  say "  $1's shell has no Dojo Cloud credentials. The broker gives none until cloud-api has created its CA and key and"
  say "  the terminal wrapper has written /etc/dojo/ca-bundle.pem (Lab 4: a shell needs to start after that)."
  say "  Wait for the Dojo Cloud chip on /admin to be green and re-run."
  return 1
}

# ---- cleanup that always runs --------------------------------------------------------------------------------------------
register_tofu_dir() { printf '%s\t%s\n' "$1" "$2" >> "$TOFU_DIRS"; }   # USER DIR (inside the terminal container)

# A directory we made (and may delete): /home/<user>/e2e-<runid> or /home/<user>/load-<runid>, nothing else.
safe_workdir() { [[ "$1" =~ ^/home/[a-z0-9_]+/(e2e|load)-[a-z0-9]{6}$ ]]; }

destroy_registered_one() {  # USER DIR
  local user=$1 dir=$2
  AREA=cleanup
  as_student "$user" "cd '$dir' 2>/dev/null || { echo no-dir; exit 0; }; if [ -f terraform.tfstate ]; then git checkout -q -- . 2>/dev/null; terraform destroy -auto-approve -no-color -input=false; else echo no-state; fi" 480 "destroy-${dir##*/}"
  if is_dry; then return 0; fi
  if [ "$RC" -eq 0 ]; then say "  cleanup: $user $dir: destroy ok ($(tail -n1 "$OUT" | cut -c1-80))"
  else fail "cleanup: terraform destroy in $dir (as $user) failed" ; _evidence; fi
}

# destroy_registered [PARALLEL=1]: terraform destroy in every registered directory that has a state file.
destroy_registered() {
  local par=${1:-1} user dir n=0
  [ -s "$TOFU_DIRS" ] || { say "  cleanup: nothing registered to destroy"; return 0; }
  while IFS=$'\t' read -r user dir; do
    [ -n "$dir" ] || continue
    ( destroy_registered_one "$user" "$dir" ) &
    n=$((n + 1))
    if [ "$n" -ge "$par" ]; then wait -n 2>/dev/null || true; n=$((n - 1)); fi
  done < "$TOFU_DIRS"
  wait
}

# verify_empty USER...: the facilitator's class view shows nothing owned by them. Anything left is a FAIL, and is
# purged (unless TB_NO_PURGE=1) so that the run still leaves nothing behind.
verify_empty() {
  local left u still
  if is_dry; then dry "check the portal shows no resource group or container group for: $*"; return 0; fi
  left=$(leftover_owners "$@")
  if [ -z "$left" ]; then pass "portal is empty for: $*"; return 0; fi
  if [[ "$left" == PORTAL-UNREADABLE* ]]; then fail "cleanup: could not read the portal to verify it is empty: $left"; return 0; fi
  fail "cleanup: portal still shows resources for: $(echo "$left" | tr '\n' ' ')(terraform destroy did not remove everything)"
  if [ "${TB_NO_PURGE:-0}" = 1 ]; then return 0; fi
  for u in $left; do portal_purge "$u"; done
  still=$(leftover_owners "$@")
  if [ -n "$still" ]; then fail "cleanup: portal STILL not empty after a purge for: $(echo "$still" | tr '\n' ' ')"; fi
}

remove_workdirs() {  # remove_workdirs: rm -rf the registered directories that are ours (checked by name), as their owner
  local user dir seen=" "
  if is_dry; then dry "remove the run's working directories inside $TERMINAL_CONTAINER"; return 0; fi
  [ -s "$WORKDIRS_FILE" ] || return 0
  while IFS=$'\t' read -r user dir; do
    if safe_workdir "$dir" && [[ "$seen" != *" $user:$dir "* ]]; then
      seen="$seen$user:$dir "
      as_student "$user" "rm -rf -- '$dir'" 120 rmwork
    fi
  done < "$WORKDIRS_FILE"
}
register_workdir() { printf '%s\t%s\n' "$1" "$2" >> "$WORKDIRS_FILE"; }

# ---- exit handling ---------------------------------------------------------------------------------------------------------
print_summary() {  # print_summary [EXIT_STATUS_SO_FAR]
  local p f k total status=${1:-0}
  p=$(count_status PASS); f=$(count_status FAIL); k=$(count_status SKIP)
  total=$((SECONDS - STARTED_AT))
  say ""
  say "== Summary: $TB_TITLE"
  if [ "$((p + f + k))" -gt 0 ]; then
    awk -F'\t' '{c[$2 " " $1]++; a[$2]=1} END {for (x in a) printf "  %-12s PASS %-3d FAIL %-3d\n", x, c[x " PASS"], c[x " FAIL"]}' "$RESULTS" | sort | say_block ""
  fi
  if [ "$f" -gt 0 ]; then
    say "  failed checks:"
    awk -F'\t' '$1 == "FAIL" {print "    [" $2 "] " $3}' "$RESULTS" | say_block ""
  fi
  say "  $p passed, $f failed, $k skipped, in ${total}s   (run dir: ${RUN_DIR:-none})"
  if is_dry; then say "  RESULT: DRY RUN (nothing was executed; this is not a pass)"
  elif [ "$f" -gt 0 ]; then say "  RESULT: FAIL"
  elif [ "$status" -ne 0 ]; then say "  RESULT: ERROR (the run stopped early with exit status $status; not a pass)"
  else say "  RESULT: PASS"; fi
}

_on_exit() {
  local rc=$? f
  trap - EXIT; trap '' INT TERM   # a second Ctrl-C must not interrupt the cleanup
  if [ -n "${RUN_DIR:-}" ]; then
    AREA=cleanup
    if is_dry; then :
    elif [ "$TB_KEEP" = 1 ]; then say ""; say "== Cleanup skipped (--keep): deployments and working directories were left in place"
    elif [ -n "$TB_CLEANUP_HOOK" ]; then section "Cleanup"; "$TB_CLEANUP_HOOK"; fi
    print_summary "$rc"
    f=$(count_status FAIL)
    if [ "$f" -gt 0 ] && [ "$rc" -eq 0 ]; then rc=1; fi
    # A dry run has nothing worth keeping: remove its own run directory (checked: named and marked by us).
    if is_dry && [ -e "$RUN_DIR/.tofu-basics-run" ] && [[ "$RUN_DIR" == */tofu-basics-* ]]; then rm -rf -- "$RUN_DIR"; fi
  fi
  exit "$rc"
}
_on_signal() { say ""; say "Interrupted ($1): cleaning up before exiting"; record FAIL "$AREA" "run was interrupted by $1"; exit 130; }
install_exit_trap() { trap _on_exit EXIT; trap '_on_signal INT' INT; trap '_on_signal TERM' TERM; }
