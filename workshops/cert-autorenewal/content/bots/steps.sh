# Workshop bot steps for cert-autorenewal (see engine/web-terminal/bot-runner.sh's
# BOT_STEPS_FILE). Replaces the git-fundamentals default with lab1.md..lab5.md's
# real flow: trust step-ca, issue+install a cert with certbot, compare acme.sh,
# automate renewal via cron, then the dns-01 capstone. This workshop has no
# Forgejo push/PR step (content/sample-repo/README.md: "no CI in this workshop"),
# so none of bot-runner.sh's git/PR steps or PENDING_PR_* are used here.
#
# BOT_USER is "testuserN", not a seeded "studentNN" account, so two things
# dns-seed and the terminal's start.d hook only do for real students -- the DNS A record
# and the /srv/webroot/<user>/ subdirectory -- don't exist yet for a bot. The
# webroot dir is a non-issue (lab2.md's own `mkdir -p` creates+claims it on
# /srv/webroot's sticky 1777, same as a real student's first run would if it
# weren't pre-created). The DNS record isn't, so step_bot_ensure_dns below
# does ourselves, once a round, the same PowerDNS PATCH dns-seed already does
# for studentNN -- ASSUMPTION TO VERIFY LIVE.

# -- helper: this bot's own dns-api key ------------------------------------
# The dns-gate module's start.d hook writes it after bot-runner.sh has
# started (so it isn't in this shell's environment yet): read it from the
# file at the start of every step until it's there.
dns_key_env() {
  if [ -z "${DNS_API_KEY:-}" ] && [ -r "$HOME/.config/dojo/dns-api-key" ]; then
    DNS_API_KEY="$(cat "$HOME/.config/dojo/dns-api-key")"
    export DNS_API_KEY
  fi
}

step_bot_ensure_dns() {
  dns_key_env
  local me host
  me="$(whoami)"
  host="${me}.certs.dojo.test"
  narrate "(bot setup) dns-seed only seeds studentNN A records, not $me -- adding my own"
  # DEMO_APP_IP and the zone are the literal values compose/dns-seed's
  # seed.sh and lab5.md's own PATCH example use; $DNS_API_KEY is the bot's own
  # key (the dns-gate module), which may change names under its own host.
  run_cmd "curl -s -o /dev/null -w 'dns A record: HTTP %{http_code}\\n' -H \"X-API-Key: \$DNS_API_KEY\" -H 'Content-Type: application/json' -X PATCH 'http://dns-api:8081/api/v1/servers/localhost/zones/certs.dojo.test.' -d '{\"rrsets\":[{\"name\":\"${host}.\",\"type\":\"A\",\"ttl\":60,\"changetype\":\"REPLACE\",\"records\":[{\"content\":\"172.30.0.20\",\"disabled\":false}]}]}'"
}

step_lab1_trust_ca() {
  dns_key_env
  local fp
  narrate "Lab 1 -- trust step-ca's root cert"
  run_cmd "ls -l /opt/step-ca-root/root_ca.crt"
  run_cmd "step certificate inspect /opt/step-ca-root/root_ca.crt --short"
  run_cmd "step certificate fingerprint /opt/step-ca-root/root_ca.crt"
  orient
  fp="$(step certificate fingerprint /opt/step-ca-root/root_ca.crt 2>/dev/null)"
  run_cmd "step ca bootstrap --force --ca-url https://step-ca:9443 --fingerprint \"$fp\""
  run_cmd "step ca health --ca-url https://step-ca:9443"
}

step_lab2_issue_and_install() {
  dns_key_env
  local me host demo_ip
  me="$(whoami)"
  host="${me}.certs.dojo.test"
  narrate "Lab 2 -- issue and install a cert with certbot"

  run_cmd "mkdir -p \"/srv/webroot/${me}/conf.d\" \"/srv/webroot/${me}/html\" \"/srv/webroot/${me}/certs\""
  run_cmd "echo \"<h1>${host} (round $ROUND)</h1>\" > \"/srv/webroot/${me}/html/index.html\""
  run_cmd "sed \"s/studentNN/${me}/g\" ~/lab/sample-repo/vhost-http.conf.template > \"/srv/webroot/${me}/conf.d/${me}.conf\""

  demo_ip="$(dig @dns-server "$host" +short 2>/dev/null | head -1)"
  orient
  run_cmd "curl -s --resolve \"${host}:80:${demo_ip}\" \"http://${host}/\""

  run_cmd "mkdir -p ~/certbot/config ~/certbot/work ~/certbot/logs"

  if [ $(( ROUND % MISTAKE_MOD )) -eq "$MISTAKE_REM" ]; then
    narrate "(demo) issuing for the template's literal studentNN placeholder instead of my own hostname"
    run_cmd "REQUESTS_CA_BUNDLE=/opt/step-ca-root/root_ca.crt certbot certonly --config-dir ~/certbot/config --work-dir ~/certbot/work --logs-dir ~/certbot/logs --webroot -w \"/srv/webroot/${me}/html\" -d studentNN.certs.dojo.test --server https://step-ca:9443/acme/acme/directory --agree-tos --non-interactive --email \"${me}@example.com\""
    narrate "right -- studentNN.certs.dojo.test doesn't resolve anywhere. Using $host."
  fi

  run_cmd "REQUESTS_CA_BUNDLE=/opt/step-ca-root/root_ca.crt certbot certonly --config-dir ~/certbot/config --work-dir ~/certbot/work --logs-dir ~/certbot/logs --webroot -w \"/srv/webroot/${me}/html\" -d \"$host\" --server https://step-ca:9443/acme/acme/directory --agree-tos --non-interactive --email \"${me}@example.com\""

  run_cmd "openssl x509 -in ~/certbot/config/live/${host}/fullchain.pem -noout -dates -subject"
  run_cmd "cp ~/certbot/config/live/${host}/fullchain.pem \"/srv/webroot/${me}/certs/fullchain.pem\""
  run_cmd "cp ~/certbot/config/live/${host}/privkey.pem \"/srv/webroot/${me}/certs/privkey.pem\""
  run_cmd "sed \"s/studentNN/${me}/g\" ~/lab/sample-repo/vhost-tls.conf.template >> \"/srv/webroot/${me}/conf.d/${me}.conf\""

  run_cmd "curl -s --resolve \"${host}:443:${demo_ip}\" --cacert /opt/step-ca-root/root_ca.crt \"https://${host}/\" -o /dev/null -w 'verify: HTTP %{http_code}\\n'"
}

step_lab3_acmesh() {
  dns_key_env
  local me host
  me="$(whoami)"
  host="${me}.certs.dojo.test"
  narrate "Lab 3 (optional) -- same task with acme.sh, for comparison"
  run_cmd "acme.sh --issue --webroot \"/srv/webroot/${me}/html\" -d \"$host\" --server https://step-ca:9443/acme/acme/directory --ca-bundle /opt/step-ca-root/root_ca.crt --cert-home ~/acmesh-lab3 --accountemail \"${me}@example.com\""
  orient
  run_cmd "openssl x509 -in ~/acmesh-lab3/${host}_ecc/${host}.cer -noout -dates -subject -issuer"
}

step_lab4_renew() {
  dns_key_env
  local me host script demo_ip
  me="$(whoami)"
  host="${me}.certs.dojo.test"
  script="$HOME/renew-and-reload.sh"
  demo_ip="$(dig @dns-server "$host" +short 2>/dev/null | head -1)"
  narrate "Lab 4 -- automate renewal with cron"

  run_cmd "cp ~/lab/sample-repo/renew-and-reload.sh $script"

  # The lab has you hand-edit the copied skeleton in an editor (set
  # YOUR_STUDENT_ID, uncomment the certbot block, export REQUESTS_CA_BUNDLE).
  # No editor here -- write the same finished script by hand instead, using
  # a quoted heredoc (so nothing but the two __TOKEN__ placeholders expands
  # now) plus sed, then fill in this bot's own username/hostname.
  cat > "$script" <<'SCRIPT'
#!/bin/sh
set -eu
export REQUESTS_CA_BUNDLE=/opt/step-ca-root/root_ca.crt
YOUR_STUDENT_ID="__ME__"
DEST="/srv/webroot/${YOUR_STUDENT_ID}/certs"
mkdir -p "${DEST}"
certbot renew \
  --config-dir "$HOME/certbot/config" --work-dir "$HOME/certbot/work" --logs-dir "$HOME/certbot/logs" \
  --no-random-sleep-on-renew \
  --deploy-hook "cp -f $HOME/certbot/config/live/__HOST__/fullchain.pem ${DEST}/fullchain.pem && cp -f $HOME/certbot/config/live/__HOST__/privkey.pem ${DEST}/privkey.pem"
SCRIPT
  sed -i "s/__ME__/${me}/; s/__HOST__/${host}/g" "$script"
  narrate "filled in ~/renew-and-reload.sh (certbot block, my own student id)"

  if [ $(( (ROUND + 1) % MISTAKE_MOD )) -eq "$MISTAKE_REM" ]; then
    narrate "(demo) trying to run it before making it executable"
    run_cmd "$script"
    narrate "right -- not executable yet. Fixing that."
  fi
  run_cmd "chmod +x $script"

  narrate "running it once by hand first -- never trust an automation script's first run to cron"
  run_cmd "$script"
  run_cmd "openssl x509 -in \"/srv/webroot/${me}/certs/fullchain.pem\" -noout -dates"

  run_cmd "(crontab -l 2>/dev/null | grep -v 'renew-and-reload.sh'; echo \"* * * * * $script >> $HOME/renew.log 2>&1\") | crontab -"
  run_cmd "crontab -l"

  run_cmd "curl -s --resolve \"${host}:443:${demo_ip}\" --cacert /opt/step-ca-root/root_ca.crt \"https://${host}/\" -o /dev/null -w 'renewed cert still serves: HTTP %{http_code}\\n'"
}

step_lab5_dns01() {
  dns_key_env
  local me host hookdir
  me="$(whoami)"
  host="${me}.certs.dojo.test"
  hookdir="$HOME/dns01-hooks"
  narrate "Lab 5 (optional capstone) -- prove control via dns-01 instead of http-01"
  mkdir -p "$hookdir"

  # lab5.md has a human paste the TXT value into a second pane. Standing in
  # for that: --manual-auth-hook/--manual-cleanup-hook run the exact same
  # PowerDNS PATCH, driven by certbot's own $CERTBOT_DOMAIN/$CERTBOT_VALIDATION,
  # so the whole thing runs non-interactively instead of pausing for Enter.
  cat > "$hookdir/auth.sh" <<'HOOK'
#!/bin/sh
set -eu
curl -s -H "X-API-Key: $DNS_API_KEY" -H "Content-Type: application/json" \
  -X PATCH "http://dns-api:8081/api/v1/servers/localhost/zones/certs.dojo.test." \
  -d "{\"rrsets\":[{\"name\":\"_acme-challenge.${CERTBOT_DOMAIN}.\",\"type\":\"TXT\",\"ttl\":60,\"changetype\":\"REPLACE\",\"records\":[{\"content\":\"\\\"${CERTBOT_VALIDATION}\\\"\",\"disabled\":false}]}]}" >/dev/null
sleep 2
HOOK
  cat > "$hookdir/cleanup.sh" <<'HOOK'
#!/bin/sh
set -eu
curl -s -H "X-API-Key: $DNS_API_KEY" -H "Content-Type: application/json" \
  -X PATCH "http://dns-api:8081/api/v1/servers/localhost/zones/certs.dojo.test." \
  -d "{\"rrsets\":[{\"name\":\"_acme-challenge.${CERTBOT_DOMAIN}.\",\"type\":\"TXT\",\"changetype\":\"DELETE\"}]}" >/dev/null
HOOK
  chmod +x "$hookdir/auth.sh" "$hookdir/cleanup.sh"

  # --cert-name pins the lineage explicitly (instead of relying on certbot's
  # own "-0001" disambiguation lab5.md describes) so re-running this step
  # every round reuses the same lineage rather than growing a new one.
  run_cmd "REQUESTS_CA_BUNDLE=/opt/step-ca-root/root_ca.crt certbot certonly --manual --preferred-challenges dns-01 --manual-auth-hook $hookdir/auth.sh --manual-cleanup-hook $hookdir/cleanup.sh --manual-public-ip-logging-ok --config-dir ~/certbot/config --work-dir ~/certbot/work --logs-dir ~/certbot/logs --cert-name ${me}-dns01 -d \"$host\" --server https://step-ca:9443/acme/acme/directory --agree-tos --non-interactive --email \"${me}@example.com\""

  run_cmd "openssl x509 -in ~/certbot/config/live/${me}-dns01/fullchain.pem -noout -dates -subject"
  run_cmd "dig @dns-server _acme-challenge.${host} TXT +short"
}

# cert-flavored look-around commands, in place of bot-runner.sh's git-status
# defaults, so a facilitator watching sees this workshop's own tools.
orient() {
  [ $(( RANDOM % 100 )) -lt "$ORIENT_FREQ" ] || return 0
  local me; me="$(whoami)"
  case "$PERSONA" in
    expert)
      run_cmd "step ca health --ca-url https://step-ca:9443"
      ;;
    intermediate)
      case $(( RANDOM % 3 )) in
        0) run_cmd "ls /srv/webroot/${me}" ;;
        1) run_cmd "crontab -l" ;;
        2) run_cmd "step path" ;;
      esac
      ;;
    novice)
      case $(( RANDOM % 4 )) in
        0) run_cmd "whoami" ;;
        1) run_cmd "ls -la ~/lab/sample-repo" ;;
        2) run_cmd "openssl version" ;;
        3) run_cmd "cat /opt/step-ca-root/root_ca.crt | head -3" ;;
      esac
      ;;
  esac
}

# Cron fires every minute against a 5-10 minute cert -- fine while a round
# runs, but left in place across a multi-minute round break it'd just keep
# renewing unwatched. Clear it each wrap; step_lab4_renew installs it fresh
# next round it runs, so nothing piles up across rounds either way.
step_wrap_round() {
  dns_key_env
  narrate "round $ROUND done -- clearing this round's cron entry before the break"
  run_cmd "(crontab -l 2>/dev/null | grep -v 'renew-and-reload.sh') | crontab -"
  narrate "taking a short break before round $((ROUND + 1))"
  sleep "$(rand_between "$BOT_ROUND_BREAK_MIN" "$BOT_ROUND_BREAK_MAX")"
}

# Expert: every lab, every round (1-5). Intermediate: the required path plus
# the acme.sh comparison, skipping the dns-01 capstone (lab5.md's own
# "optional" pair). Novice: about the first two, same as the default's
# lab1+lab2 shape.
case "$PERSONA" in
  expert)
    STEPS=(
      step_bot_ensure_dns
      step_lab1_trust_ca
      step_lab2_issue_and_install
      step_lab3_acmesh
      step_lab4_renew
      step_lab5_dns01
      step_wrap_round
    )
    ;;
  intermediate)
    STEPS=(
      step_bot_ensure_dns
      step_lab1_trust_ca
      step_lab2_issue_and_install
      step_lab3_acmesh
      step_lab4_renew
      step_wrap_round
    )
    ;;
  novice)
    STEPS=(
      step_bot_ensure_dns
      step_lab1_trust_ca
      step_lab2_issue_and_install
      step_wrap_round
    )
    ;;
esac
