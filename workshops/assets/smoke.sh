#!/bin/sh
# Bot smoke test for one workshop pack (RV19). Run from the repo root on a free machine:
#   workshops/assets/smoke.sh <workshop> [--bots N] [--timeout MIN] [--reuse] [--split each|"0-1 2 3-4 ..."]
# Starts `./dojo <workshop> --test N --fast` with achievements on, waits for every bot's ~/.dojo-bot-done,
# then checks the achievements ledger with fired.py. FAIL when a bot doesn't finish in time or a core milestone
# never fired; extra and funny items that never fired, and steps the bots skipped (FAST: lines), are listed but
# don't fail it (bots stay lab-only, so challenges never fire here). --reuse checks a stack that is already up
# (started the same way) instead of starting one. The stack is left running for a look; `./dojo stop` after.
# --split runs the labs side by side instead of one bot doing them all (a slow pack's waits then overlap): one bot
# per range, `each` = one per lab (lab 0 rides with the first). Each bot makes its fork (step 1), then retest.sh moves
# it to its first lab (lab-prep) and stops it after its last; the milestones are counted over all bots. A pack whose
# labs need much memory at once sets WEB_TERMINAL_MEM_LIMIT in its workshop.env. The gate before a merge stays the
# full run (no --split): lab-prep's rebuilt start is not the previous lab's real leftovers.
set -u
. workshops/assets/test-lib.sh

ws="" bots=3 timeout=30 reuse=0 split=""
while [ $# -gt 0 ]; do
  case "$1" in
    --bots) bots="$2"; shift ;;
    --timeout) timeout="$2"; shift ;;
    --reuse) reuse=1 ;;
    --split) split="$2"; shift ;;
    -*) echo "smoke: unknown option $1" >&2; exit 2 ;;
    *) ws="$1" ;;
  esac
  shift
done
[ -n "$ws" ] && [ -f "workshops/$ws/workshop.env" ] || { echo "usage: $0 <workshop> [--bots N] [--timeout MIN] [--reuse]" >&2; exit 2; }
[ -f "workshops/$ws/achievements/catalog.json" ] || { echo "smoke: $ws has no achievements catalog to check" >&2; exit 2; }

if [ -n "$split" ]; then
  if [ "$split" = each ]; then
    labs="$(awk '/^[[:space:]]*STEPS=\(/ { on = 1; next } on && /^[[:space:]]*\)/ { on = 0 }
      on { for (i = 1; i <= NF; i++) if (match($i, /lab[0-9]+($|_)/)) { n = substr($i, RSTART + 3); sub(/_.*/, "", n); print n } }' \
      "workshops/$ws/content/bots/steps.sh" | sort -nu)"
    split="" first=""
    for l in $labs; do
      if [ -z "$first" ] && [ "$l" = 0 ]; then first=0; continue; fi
      if [ "$first" = 0 ]; then split="0-$l"; first=done; else split="$split $l"; fi
    done
  fi
  set -- $split
  bots=$#
  [ "$bots" -gt 0 ] || { echo "smoke: --split: no labs found" >&2; exit 2; }
fi

echo "== $ws: $bots fast bots$([ -n "$split" ] && echo ", split: $split")"
running="$("$DOJO_CLI" ps --format '{{.Names}}' | grep -c '^workshop_')"
if [ "$reuse" = 1 ]; then
  [ "$running" -gt 0 ] || { echo "smoke: --reuse, but no stack is running" >&2; exit 2; }
else
  [ "$running" = 0 ] || { echo "smoke: a stack is already running (podman ps); stop it or pass --reuse" >&2; exit 2; }
  start=$(date +%s)
  ACHIEVEMENTS_ENABLED=1 ./dojo "$ws" --test "$bots" --fast > "${TMPDIR:-/tmp}/smoke-$ws.log" 2>&1
  rc=$?
  [ "$rc" = 0 ] || { tail -20 "${TMPDIR:-/tmp}/smoke-$ws.log"; echo "FAIL: $ws (./dojo exited $rc)"; exit 1; }
  echo "  stack up in $(( $(date +%s) - start ))s"
fi

# --split: once a bot has its fork (past step_ensure_clone), retest.sh moves it to its range; all side by side.
if [ -n "$split" ]; then
  k=0 deadline=$(( $(date +%s) + 15 * 60 ))
  for r in $split; do
    k=$(( k + 1 )) a="${r%-*}" b="${r#*-}"
    (
      until [ "$(as_user "testuser$k" '. ~/.dojo-bot-state 2>/dev/null; echo "${STEP:-0}"' 2>/dev/null | tr -dc 0-9)" -ge 1 ] 2>/dev/null; do
        [ "$(date +%s)" -lt "$deadline" ] || { echo "  testuser$k: never got past step_ensure_clone"; exit 1; }
        sleep 5; done
      t0=$(date +%s)
      workshops/assets/retest.sh "$ws" "$a" --to "$b" --bot "testuser$k" --wait "$timeout" \
        > "${TMPDIR:-/tmp}/smoke-$ws-split-$k.log" 2>&1
      rc=$?
      echo "  testuser$k labs $r: $([ "$rc" = 0 ] && echo ok || echo FAIL) in $(( ($(date +%s) - t0) / 60 )) min"
    ) &
  done
  wait
  k=0
  for r in $split; do
    k=$(( k + 1 )) log="${TMPDIR:-/tmp}/smoke-$ws-split-$k.log"
    tail -1 "$log" | grep -q '^PASS' || fail "testuser$k labs $r (retest.sh)" "$(tail -12 "$log")"
  done
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
