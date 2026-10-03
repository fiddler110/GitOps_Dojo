#!/bin/sh
# Re-run a fast bot from one lab, on a stack that is already up (RV35). Run from the repo root:
#   workshops/assets/retest.sh <workshop> <lab> [--only | --to LAST] [--bot testuser1] [--wait MIN]
# A full --fast round of a slow pack (cloud-policy-as-code: ~100 s provider waits per policy apply) takes an hour;
# after fixing one lab, this re-runs just that lab (--only) or that lab onwards, in minutes.
#
# How, without touching the engine: bot-runner.sh resumes from the step index in ~/.dojo-bot-state, and
# bot-supervisor.sh restarts a bot whose tmux session is gone. So this runs `lab-prep <lab>` as the bot (the pack's
# own "bring the workspace to the start of lab N"), points the state at the pack's lab step, and ends the session.
# With --only, once the bot has moved past that step, the state is set to the end and the session ended again, so the
# runner writes ~/.dojo-bot-done straight away. --to LAST does the same once the bot reaches lab LAST+1's step
# (--only is --to <lab>); smoke.sh --split runs one of these per bot (the next lab's first seconds may have run; nothing is half-applied
# that lab-prep can't redo). The lab's step is the first entry of the pack's STEPS=( ) in content/bots/steps.sh whose
# name ends in `lab<N>` or contains `lab<N>_`. The bot must have finished at least step_ensure_clone once.
set -u
. workshops/assets/test-lib.sh

ws="" lab="" to="" bot=testuser1 wait=30
while [ $# -gt 0 ]; do
  case "$1" in
    --only) to=only ;;
    --to) to="$2"; shift ;;
    --bot) bot="$2"; shift ;;
    --wait) wait="$2"; shift ;;
    -*) echo "retest: unknown option $1" >&2; exit 2 ;;
    *) if [ -z "$ws" ]; then ws="$1"; else lab="$1"; fi ;;
  esac
  shift
done
steps="workshops/$ws/content/bots/steps.sh"
case "$lab" in ''|*[!0-9]*) lab="" ;; esac
[ "$to" != only ] || to="$lab"
case "$to" in *[!0-9]*) lab="" ;; esac
[ -n "$ws" ] && [ -n "$lab" ] && [ -f "$steps" ] || {
  echo "usage: $0 <workshop> <lab> [--only | --to LAST] [--bot testuser1] [--wait MIN]  (the pack needs content/bots/steps.sh)" >&2; exit 2; }

# Index of the lab's step in the pack's STEPS array, and the array's length.
step_of() { awk -v lab="$1" '
  /^[[:space:]]*STEPS=\(/ { on = 1; n = 0; next }
  on && /^[[:space:]]*\)/ { on = 0; next }
  on && NF { name = $1; if (idx == "" && (name ~ ("lab" lab "$") || name ~ ("lab" lab "_"))) idx = n; n++ }
  END { printf "idx=%s len=%s\n", idx, n }' "$steps"; }
eval "$(step_of "$lab")"
[ -n "$idx" ] || { echo "retest: no step for lab $lab in $steps" >&2; exit 2; }
# Where to stop: lab LAST+1's step (none past the last lab: run to the end).
stop=""
if [ -n "$to" ]; then
  [ "$to" -ge "$lab" ] || { echo "retest: --to $to is before lab $lab" >&2; exit 2; }
  stop="$(step_of $(( to + 1 )) | sed -n 's/^idx=\([0-9]*\) .*/\1/p')"
fi

"$DOJO_CLI" exec "$DOJO_TERMINAL" id "$bot" >/dev/null 2>&1 || { echo "retest: no $bot in $DOJO_TERMINAL (is the stack up with --test?)" >&2; exit 2; }
echo "== $ws: $bot from lab $lab (step $idx of $len)$([ -n "$to" ] && echo ", to lab $to")"

# Stop the bot first, so it isn't mid-step while lab-prep rewrites its workspace: point it at the end (it parks), kill it.
park() { as_user "$bot" "printf 'ROUND=1\nSTEP=%s\nPENDING_PR_BRANCH=\nPENDING_PR_NUMBER=\n' $1 > ~/.dojo-bot-state; tmux kill-session -t main 2>/dev/null; true"; }
park "$len"
as_user "$bot" 'rm -f ~/.dojo-bot-done'
start="$(as_user "$bot" 'wc -c < ~/.dojo-bot.log 2>/dev/null || echo 0' | tr -dc 0-9)"

if as_user "$bot" 'command -v lab-prep' >/dev/null 2>&1; then
  echo "  lab-prep $lab (a slow pack's lab-prep applies policy: minutes)"
  out="$(as_user "$bot" "lab-prep $lab" 2>&1)" || { printf '%s\n' "$out" | tail -15; echo "FAIL: lab-prep $lab"; exit 1; }
  printf '%s\n' "$out" | tail -3 | sed 's/^/    /'
fi
# The supervisor restarted it parked at the end, which wrote the done marker: clear it, point at the lab, restart.
as_user "$bot" 'rm -f ~/.dojo-bot-done'
park "$idx"
echo "  restarted (bot-supervisor.sh picks it up within ~15 s)"

deadline=$(( $(date +%s) + wait * 60 )) done=0
while [ "$(date +%s)" -lt "$deadline" ]; do
  if [ -n "$stop" ]; then
    step="$(as_user "$bot" '. ~/.dojo-bot-state 2>/dev/null; echo "${STEP:-0}"' | tr -dc 0-9)"
    if [ "${step:-0}" -ge "$stop" ]; then as_user "$bot" 'rm -f ~/.dojo-bot-done'; park "$len"; stop=""; fi
  fi
  if as_user "$bot" 'test -e ~/.dojo-bot-done' 2>/dev/null; then done=1; break; fi
  sleep 5
done
result "$([ "$done" = 1 ]; echo $?)" "$bot finished within ${wait} min"

# What this run logged: failed attempts and skipped steps, then the tail.
log="$(as_user "$bot" "tail -c +$(( ${start:-0} + 1 )) ~/.dojo-bot.log" | sed 's/\x1b\[[0-9;]*m//g')"
printf '%s\n' "$log" | grep -E 'failed \(attempt|FAST: .*skipping it' | sed 's/^/  /'
printf '%s\n' "$log" | grep -qE 'FAST: .*skipping it' && fail "a step was skipped after 3 failed attempts"
printf '%s\n' "$log" | tail -8 | sed 's/^/  | /'
finish "$ws retest lab $lab$([ -n "$to" ] && [ "$to" != "$lab" ] && echo "-$to")"
