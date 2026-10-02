#!/bin/sh
# Bot smoke test for one workshop pack (RV19). Run from the repo root on a free machine:
#   workshops/assets/smoke.sh <workshop> [--bots N] [--timeout MIN] [--reuse]
# Starts `./run.sh <workshop> --test N --fast` with achievements on, waits for every bot's ~/.dojo-bot-done,
# then checks the achievements ledger with fired.py. FAIL when a bot doesn't finish in time or a core milestone
# never fired; extra and funny items that never fired, and steps the bots skipped (FAST: lines), are listed but
# don't fail it (bots stay lab-only, so challenges never fire here). --reuse checks a stack that is already up
# (started the same way) instead of starting one. The stack is left running for a look; `./run.sh stop` after.
set -u
. workshops/assets/test-lib.sh

ws="" bots=3 timeout=30 reuse=0
while [ $# -gt 0 ]; do
  case "$1" in
    --bots) bots="$2"; shift ;;
    --timeout) timeout="$2"; shift ;;
    --reuse) reuse=1 ;;
    -*) echo "smoke: unknown option $1" >&2; exit 2 ;;
    *) ws="$1" ;;
  esac
  shift
done
[ -n "$ws" ] && [ -f "workshops/$ws/workshop.env" ] || { echo "usage: $0 <workshop> [--bots N] [--timeout MIN] [--reuse]" >&2; exit 2; }
[ -f "workshops/$ws/achievements/catalog.json" ] || { echo "smoke: $ws has no achievements catalog to check" >&2; exit 2; }

echo "== $ws: $bots fast bots"
running="$("$DOJO_CLI" ps --format '{{.Names}}' | grep -c '^workshop_')"
if [ "$reuse" = 1 ]; then
  [ "$running" -gt 0 ] || { echo "smoke: --reuse, but no stack is running" >&2; exit 2; }
else
  [ "$running" = 0 ] || { echo "smoke: a stack is already running (podman ps); stop it or pass --reuse" >&2; exit 2; }
  start=$(date +%s)
  ACHIEVEMENTS_ENABLED=1 ./run.sh "$ws" --test "$bots" --fast > "${TMPDIR:-/tmp}/smoke-$ws.log" 2>&1
  rc=$?
  [ "$rc" = 0 ] || { tail -20 "${TMPDIR:-/tmp}/smoke-$ws.log"; echo "FAIL: $ws (./run.sh exited $rc)"; exit 1; }
  echo "  stack up in $(( $(date +%s) - start ))s"
fi

# Wait for the done markers; print progress when the count changes.
deadline=$(( $(date +%s) + timeout * 60 )) last=-1 ndone=0
while :; do
  ndone="$("$DOJO_CLI" exec "$DOJO_TERMINAL" sh -c 'ls /home/testuser*/.dojo-bot-done 2>/dev/null | wc -l' || echo 0)"
  [ "$ndone" = "$last" ] || { echo "  bots done: $ndone/$bots"; last="$ndone"; }
  [ "$ndone" -lt "$bots" ] || break
  [ "$(date +%s)" -lt "$deadline" ] || break
  sleep 10
done
result "$([ "$ndone" -ge "$bots" ]; echo $?)" "all $bots bots finished within ${timeout} min"

# Steps a bot gave up on after 3 tries.
skips="$("$DOJO_CLI" exec "$DOJO_TERMINAL" sh -c 'grep -HE "FAST: .*(skipping it|still not ready)" /home/testuser*/.dojo-bot.log 2>/dev/null' | sed 's|^/home/||; s|/.dojo-bot.log:| |')"
[ -z "$skips" ] || { echo "  skipped steps:"; printf '%s\n' "$skips" | sed 's/^/    /; s/\x1b\[[0-9;]*m//g'; }

fired="$(python3 -B modules/achievements/tools/fired.py "$ws" 2>&1)"
result $? "achievements ledger read"
missing="$(printf '%s\n' "$fired" | awk '$1 == "core" && $3 == 0 { printf "%s ", $2 }')"
[ -z "$missing" ] && pass "every core milestone fired" || fail "core milestones never fired: $missing"
other="$(printf '%s\n' "$fired" | awk '$1 != "core" && $3 == 0 && $1 !~ /^(challenge|challenges|capstone)$/ { printf "%s:%s ", $1, $2 }')"
[ -z "$other" ] || echo "  never fired (not core): $other"

finish "$ws smoke"
